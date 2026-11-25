from component_fixture import install_components
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.olympus = root / 'olympus'
        self.olympus.mkdir()
        install_components(ROOT, self.olympus)
        self.cli = self.olympus / 'olymctl'
        self.cli.write_text((ROOT / 'olymctl').read_text())
        self.cli.chmod(0o755)
        bins = root / 'bin'
        bins.mkdir()
        self.log = root / 'calls.jsonl'
        docker = bins / 'docker'
        docker.write_text('''#!/usr/bin/env python3
import json,os,sys
args=sys.argv[1:]
with open(os.environ['FAKE_DOCKER_LOG'],'a') as f: f.write(json.dumps(args)+'\\n')
if 'ps' in args: print('worker\\nmongo\\nsetup\\nlegacy-setup\\nweb\\npaused')
if 'inspect' in args:
    states={'worker':'intranet-worker|exited|unless-stopped|',
            'mongo':'mongo-db|restarting|unless-stopped|',
            'setup':'intranet-setup|exited|no|oneshot',
            'legacy-setup':'legacy-setup|exited|always|oneshot',
            'web':'intranet|running|unless-stopped|',
            'paused':'other|paused|unless-stopped|'}
    value=states[args[-1]]
    if os.environ.get('ALL_HEALTHY') and args[-1] in ('worker','mongo'): value=value.replace('|exited|','|running|').replace('|restarting|','|running|')
    print(value)
if 'up' in args and os.environ.get('FAIL_UP'): sys.exit(1)
''')
        docker.chmod(0o755)
        self.env = {**os.environ, 'PATH': str(bins) + os.pathsep + os.environ['PATH'],
                    'FAKE_DOCKER_LOG': str(self.log)}

    def run_cli(self, *args, **environment):
        return subprocess.run([str(self.cli), *args], env={**self.env, **environment},
                              capture_output=True, text=True)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_recovers_failed_continuous_services_without_rerunning_initializers(self):
        result = self.run_cli('prod', 'up', '--recover-stopped', '--no-pull')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        up = next(c for c in self.calls() if 'up' in c)
        self.assertEqual(['up','-d','--no-deps','--no-build','--pull','never','--force-recreate',
                          'intranet-worker','mongo-db'], up[up.index('up'):])
        self.assertIn('compose.logging.yaml', ' '.join(up))
        self.assertIn('\tsuccess;', (self.olympus / 'state/events.tsv').read_text())

    def test_no_restart_when_remaining_continuous_services_are_healthy(self):
        result = self.run_cli('prod', 'up', '--recover-stopped', '--no-pull', ALL_HEALTHY='1')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertFalse(any('up' in c for c in self.calls()))
        self.assertFalse((self.olympus / 'state/events.tsv').exists())

    def test_failed_recovery_is_recorded_as_failure(self):
        result = self.run_cli('prod', 'up', '--recover-stopped', '--no-pull', FAIL_UP='1')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('\tfailed;', (self.olympus / 'state/events.tsv').read_text())

    def test_recovery_rejects_other_deployment_modes_before_docker_calls(self):
        for args in [('dev','up','--recover-stopped'),
                     ('prod','up','intranet','--recover-stopped'),
                     ('prod','up','--recover-stopped','--logging-only')]:
            result = self.run_cli(*args)
            self.assertNotEqual(0, result.returncode)
            self.assertIn('--recover-stopped requires prod up', result.stderr)
        self.assertFalse(self.log.exists())


if __name__ == '__main__':
    unittest.main()
