#!/usr/bin/env python3
"""Apache + PHP integration check using isolated files and fake WP roles."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


source = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="intranet-backup-test-") as tmp:
    root = Path(tmp)
    root.chmod(0o755)
    backups = root / "wp-content/ai1wm-backups"
    backups.mkdir(parents=True)
    payload = bytes(range(256)) * 8192
    (backups / "export.wpress").write_bytes(payload)
    (root / "outside.wpress").write_bytes(b"must never download")
    (backups / "escape.wpress").symlink_to('/var/www/html/outside.wpress')
    (backups / "secret.sql").write_text("private")
    original = """# BEGIN Intranet Protected Uploads
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteRule ^wp-content/ai1wm-backups(?:/|$) - [F,L,NC]
RewriteRule ^wp-content/uploads/(.+\\.pdf)$ index.php?intranet_protected_upload=$1 [B,L,NC,QSA]
</IfModule>
# END Intranet Protected Uploads
# Existing WordPress rules must stay unchanged.
"""
    (root / ".htaccess").write_text(original)
    (root / "index.php").write_text("""<?php
define('ABSPATH', __DIR__ . '/');
define('WP_CONTENT_DIR', __DIR__ . '/wp-content');
function add_action(...$args) {}
function nocache_headers() { header('Cache-Control: private, no-store'); }
function is_user_logged_in() { return isset($_SERVER['HTTP_X_TEST_ROLE']); }
function current_user_can($cap) { return ($_SERVER['HTTP_X_TEST_ROLE'] ?? '') === 'admin'; }
function auth_redirect() { header('Location: /wp-login.php', true, 302); exit; }
function status_header($status) { http_response_code($status); }
require '/opt/download/intranet-backup-download.php';
intranet_backup_download();
http_response_code(404);
""")
    container = docker(
        "run", "-d", "--rm", "-p", "127.0.0.1::80",
        "--mount", f"type=bind,source={root},target=/var/www/html",
        "--mount", f"type=bind,source={source},target=/opt/download,readonly",
        "--entrypoint", "/bin/sh", "wordpress:php8.3-apache", "-ec",
        "php /opt/download/prepare-intranet-download.php; "
        "php /opt/download/prepare-intranet-download.php; exec apache2-foreground",
    )
    try:
        info = json.loads(docker("inspect", container))[0]
        port = info["NetworkSettings"]["Ports"]["80/tcp"][0]["HostPort"]
        base = "http://127.0.0.1:" + port

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        opener = urllib.request.build_opener(NoRedirect)

        def request(path="/wp-content/ai1wm-backups/export.wpress", role="admin", method="GET", byte_range=None):
            headers = {}
            if role:
                headers["X-Test-Role"] = role
            if byte_range:
                headers["Range"] = byte_range
            req = urllib.request.Request(base + path, headers=headers, method=method)
            try:
                response = opener.open(req, timeout=5)
            except urllib.error.HTTPError as error:
                response = error
            return response.code, response.headers, response.read()

        for _ in range(40):
            try:
                status, headers, body = request()
                break
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.25)
        assert status == 200 and body == payload
        assert headers["Content-Disposition"].startswith("attachment;")
        assert headers["Content-Length"] == str(len(payload))
        assert "no-store" in headers["Cache-Control"]
        assert request(role=None)[0] == 302
        assert request(role="viewer")[0] == 403
        assert request(method="POST")[0] == 405
        status, headers, body = request(method="HEAD")
        assert status == 200 and body == b"" and headers["Content-Length"] == str(len(payload))
        for byte_range, expected in [("bytes=100-299", payload[100:300]), ("bytes=-10", payload[-10:]), ("bytes=2097140-", payload[2097140:])]:
            status, headers, body = request(byte_range=byte_range)
            assert status == 206 and body == expected and headers["Content-Range"].startswith("bytes ")
        for byte_range in ["bytes=999999999-", "bytes=10-5", "bytes=-0", "bytes=-", "bytes=0-1,4-5"]:
            assert request(byte_range=byte_range)[0] == 416
        assert request("/wp-content/ai1wm-backups/escape.wpress")[0] == 404
        assert request("/wp-content/ai1wm-backups/missing.wpress")[0] == 404
        assert request("/wp-content/ai1wm-backups/secret.sql")[0] == 403
        assert request("/wp-content/ai1wm-backups/")[0] == 403
        assert request("/index.php?intranet_protected_backup=../outside.wpress")[0] == 404
        assert request("/index.php?intranet_protected_backup[]=export.wpress")[0] == 404
        updated = (root / ".htaccess").read_text()
        assert updated.count("intranet_protected_backup=") == 1
        assert "\n".join(line for line in updated.splitlines() if "intranet_protected_backup=" not in line) + "\n" == original
        print("PASS: full download, authentication, HEAD, ranges, path containment, Apache routing and idempotent setup")
    finally:
        docker("rm", "-f", container)
