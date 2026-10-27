import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WordPressControlTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.olympus = self.workspace / 'olympus'
        self.olympus.mkdir()
        script = (ROOT / 'olymctl').read_text().replace(
            'ensure_dev_hosts() {',
            'ensure_dev_hosts() { return 0; }\nunused_ensure_dev_hosts() {', 1)
        self.cli = self.olympus / 'olymctl'
        self.cli.write_text(script)
        self.cli.chmod(0o755)
        # Use the real registration so a production-only scope regresses here.
        (self.olympus / 'apps.tsv').write_text((ROOT / 'apps.tsv').read_text())
        keys = ('POSTGRES_USER', 'POSTGRES_PASSWORD', 'MYSQL_USER', 'MYSQL_PASSWORD',
                'MYSQL_ROOT_PASSWORD', 'WORDPRESS_INSTITUTIONAL_PATH',
                'WORDPRESS_INTRANET_PATH', 'CRONOS_ALLOWED_NETWORKS')
        (self.olympus / '.env').write_text(''.join(f'{key}=test-value\n' for key in keys))
        (self.olympus / '.gitignore').write_text('.env\nstate/\n')
        self.content = self.workspace / 'institutional-website/html'
        self.content.mkdir(parents=True)
        self.marker = self.content / 'operator-content.txt'
        self.marker.write_text('preserve uploads and plugins\n')
        self.log = self.workspace / 'docker.jsonl'
        bins = self.workspace / 'bin'
        bins.mkdir()
        docker = bins / 'docker'
        docker.write_text('''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['FAKE_DOCKER_LOG'], 'a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
''')
        docker.chmod(0o755)
        self.env = {**os.environ, 'PATH': str(bins) + os.pathsep + os.environ['PATH'],
                    'FAKE_DOCKER_LOG': str(self.log)}
        self.git('init', '-q', '-b', 'main')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'Fixture')
        # A local origin exercises normal self-update without network access.
        self.git('remote', 'add', 'origin', str(self.olympus))

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.olympus), *args], text=True).strip()

    def run_cli(self, *args):
        return subprocess.run([str(self.cli), *args], env=self.env,
                              text=True, capture_output=True)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_dev_up_uses_existing_content_without_app_checkout_or_env(self):
        for options in ([], ['--no-pull']):
            with self.subTest(options=options):
                result = self.run_cli('dev', 'up', 'institutional-website', *options)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        ups = [call for call in self.calls() if 'up' in call]
        self.assertEqual(2, len(ups))
        for call in ups:
            self.assertEqual(['institutional-website', 'reverse-proxy'], call[-2:])
            self.assertIn(str(self.olympus / 'compose.dev.yaml'), call)
        self.assertTrue(any('reload' in call for call in self.calls()))
        self.assertFalse(any(call[0] in ('build', 'run') for call in self.calls()))
        self.assertFalse((self.content.parent / '.git').exists())
        self.assertFalse((self.content.parent / '.env').exists())
        self.assertEqual('preserve uploads and plugins\n', self.marker.read_text())
        sha = self.git('rev-parse', 'HEAD')
        self.assertIn(f'\t{sha}\t{sha}\tsuccess',
                      (self.olympus / 'state/events.tsv').read_text())

    def test_dev_down_stops_only_institutional_site(self):
        result = self.run_cli('dev', 'down', 'institutional-website')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        stop = next(call for call in self.calls() if 'stop' in call)
        self.assertEqual(['stop', 'institutional-website'], stop[-2:])

    def test_wordpress_revision_options_are_rejected_before_startup(self):
        for environment in ('dev', 'prod'):
            for option, value in (('--branch', 'main'), ('--commit', 'abc123')):
                with self.subTest(environment=environment, option=option):
                    result = self.run_cli(environment, 'up', 'institutional-website',
                                          '--no-pull', option, value)
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn('--branch and --commit do not apply', result.stderr)
        self.assertFalse(any('up' in call for call in self.calls()))

    def test_missing_content_fails_before_startup(self):
        self.marker.unlink()
        self.content.rmdir()
        result = self.run_cli('dev', 'up', 'institutional-website', '--no-pull')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Missing local WordPress content', result.stderr)
        self.assertFalse(any('up' in call for call in self.calls()))
        self.assertFalse(self.content.exists())

    def test_prod_preparation_still_uses_olympus_revision(self):
        for service in ('institutional-website', 'intranet-website'):
            with self.subTest(service=service):
                result = self.run_cli('prod', 'up', service, '--no-pull', '--prepare-only')
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertFalse(any('up' in call or call[0] == 'build' for call in self.calls()))


if __name__ == '__main__':
    unittest.main()
