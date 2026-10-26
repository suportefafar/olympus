#!/usr/bin/env bash
set -Eeuo pipefail

release_dir="$(cd "$(dirname "$0")/.." && pwd -P)"
commit="$(basename "$release_dir")"
app_dir="$release_dir/codex-api"
codex_source="$(readlink -f /root/.local/bin/codex)"

[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || { echo '[ERROR] Invalid release id.' >&2; exit 1; }
[[ -x "$codex_source" && -f /root/.codex/auth.json ]] || { echo '[ERROR] Root Codex login is missing.' >&2; exit 1; }
id codex-api >/dev/null 2>&1 || useradd --system --home-dir /var/lib/codex-api --create-home --shell /usr/sbin/nologin codex-api
install -d -m 0755 /opt/codex-api/bin
install -d -o codex-api -g codex-api -m 0700 /var/lib/codex-api/.codex /var/lib/codex-api/work
install -d -m 0700 /etc/codex-api
if [[ ! -f /var/lib/codex-api/.codex/auth.json ]]; then
  install -o codex-api -g codex-api -m 0600 /root/.codex/auth.json /var/lib/codex-api/.codex/auth.json
fi
if [[ ! -f /etc/codex-api/.env.production ]]; then
  umask 077
  token="$(openssl rand -hex 32)"
  printf 'CODEX_API_TOKEN=%s\nCODEX_ALLOWED_MODELS=gpt-6.1-sol,gpt-6-astra,gpt-6-luna\nCODEX_DEFAULT_MODEL=gpt-6.1-sol\n' "$token" > /etc/codex-api/.env.production
  unset token
fi
chmod 0600 /etc/codex-api/.env.production
if [[ ! -f /etc/codex-api/tls.crt || ! -f /etc/codex-api/tls.key ]]; then
  openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 3650 \
    -subj '/CN=150.164.110.3' -addext 'subjectAltName=IP:150.164.110.3' \
    -keyout /etc/codex-api/tls.key -out /etc/codex-api/tls.crt >/dev/null 2>&1
fi
chmod 0600 /etc/codex-api/tls.key
chmod 0644 /etc/codex-api/tls.crt
if [[ ! -x /opt/codex-api/bin/codex ]] || ! cmp -s "$codex_source" /opt/codex-api/bin/codex; then
  install -m 0755 "$codex_source" /opt/codex-api/bin/codex
fi
ln -sfn "$app_dir" /opt/codex-api/current
install -m 0644 "$app_dir/codex-api.service" /etc/systemd/system/codex-api.service
for port in 8084 8086; do
  file="/etc/nginx/sites-available/nginx-$port"
  if [[ -f "$file" && ! -f "$file.before-codex" ]]; then cp -a "$file" "$file.before-codex"; fi
  install -m 0644 "$app_dir/nginx-$port" "$file"
  ln -sfn "$file" "/etc/nginx/sites-enabled/nginx-$port"
done
nginx -t
systemctl daemon-reload
systemctl enable --now codex-api
systemctl restart codex-api
systemctl reload nginx
curl --fail --silent --show-error --max-time 10 --cacert /etc/codex-api/tls.crt https://150.164.110.3:8084/healthz >/dev/null
echo "[INFO] Codex API release $commit is healthy on HTTPS port 8084."
