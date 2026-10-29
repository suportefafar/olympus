from component_fixture import install_components
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / 'olymctl').exists():
    ROOT = Path('/home/geovani/app/fafar/olympus')
SERVICES = ['athenas','athenas-worker','athenas-ollama','athenas-model-setup','athenas-setup']

class AthenasControlTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.olympus = self.workspace/'olympus'
        self.olympus.mkdir()
        install_components(ROOT, self.olympus)
        (self.olympus/'olymctl').write_text((ROOT/'olymctl').read_text().replace('ensure_dev_hosts() {', 'ensure_dev_hosts() { return 0; }\nunused_ensure_dev_hosts() {', 1))
        (self.olympus/'olymctl').chmod(0o755)
        self.log = self.workspace/'calls.jsonl'
        bins = self.workspace/'bin'; bins.mkdir()
        docker = bins/'docker'
        docker.write_text("""#!/usr/bin/env python3
import json,os,sys
with open(os.environ["FAKE_DOCKER_LOG"], "a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")
if "ps" in sys.argv: print("fixture-init\\nfixture-worker")
if "inspect" in sys.argv:
    print("/olympus-athenas-setup-1|exited|sem healthcheck|0|oneshot" if sys.argv[-1]=="fixture-init" else "/olympus-athenas-worker-1|running|sem healthcheck|0|")
if "stats" in sys.argv: print("olympus-athenas-worker-1|0%|10MiB / 2GiB|1%|0B / 0B|0B / 0B|1")
""")
        docker.chmod(0o755)
        self.env = {**os.environ, 'PATH': str(bins)+os.pathsep+os.environ['PATH'], 'FAKE_DOCKER_LOG': str(self.log)}
        # Avoid touching /etc/hosts; actual routing is verified separately.
        (self.olympus/'apps.tsv').write_text('athenas\tgit@example.invalid:athenas.git\t'+','.join(SERVICES)+'\tathenas.example.invalid\ttrue\tdev\nreverse-proxy\tgit@example.invalid:proxy.git\treverse-proxy\t-\ttrue\n')
        (self.olympus/'.env').write_text('\n'.join(key+'=test-only-value' for key in ('POSTGRES_USER','POSTGRES_PASSWORD','MYSQL_USER','MYSQL_PASSWORD','MYSQL_ROOT_PASSWORD','WORDPRESS_INSTITUTIONAL_PATH','WORDPRESS_INTRANET_PATH','CRONOS_ALLOWED_NETWORKS'))+'\n')
        for app in ('athenas','reverse-proxy'):
            path=self.workspace/app;path.mkdir()
            subprocess.run(['git','init','-q',str(path)],check=True)
            (path/'.gitignore').write_text('.env\n')
            (path/'.env.example').write_text('APP_NAME=example\n')
            dockerignore=path/'.dockerignore'
            if app=='reverse-proxy':
                (path/'web-server').mkdir();dockerignore=path/'web-server/.dockerignore'
            dockerignore.write_text('.env\n')
            subprocess.run(['git','-C',str(path),'add','.'],check=True)
            subprocess.run(['git','-C',str(path),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','Fixture'],check=True)

    def run_cli(self,*args):
        return subprocess.run([str(self.olympus/'olymctl'),*args],env=self.env,text=True,capture_output=True)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_up_selects_entire_group_and_reloads_proxy(self):
        result=self.run_cli('dev','up','athenas','--no-pull')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        calls=self.calls()
        up=next(c for c in calls if 'up' in c)
        self.assertEqual(SERVICES+['reverse-proxy'], up[-6:])
        self.assertTrue(any(c[-9:]==['exec','-T','reverse-proxy','caddy','reload','--config','/etc/caddy/Caddyfile','--adapter','caddyfile'] for c in calls))
        self.assertTrue((self.workspace/'reverse-proxy/.env').exists())

    def test_down_stops_only_athenas_group(self):
        result=self.run_cli('dev','down','athenas')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        stop=next(c for c in self.calls() if 'stop' in c)
        self.assertEqual(SERVICES,stop[-5:])
        self.assertNotIn('postgres-db',stop)

    def test_status_reports_successful_initializer_as_completed(self):
        result=self.run_cli('dev','status')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertIn('[OK] concluído',result.stdout)
        self.assertIn('olympus-athenas-worker-1',result.stdout)
        self.assertNotIn('[ERRO]',result.stdout)

    def test_production_rejects_dev_only_app(self):
        for command in ('up','down'):
            result=self.run_cli('prod',command,'athenas',*(['--no-pull'] if command=='up' else []))
            self.assertNotEqual(0,result.returncode)
            self.assertIn('is not enabled in prod',result.stderr)
        self.assertFalse(any('up' in c or 'stop' in c for c in self.calls()))

if __name__=='__main__': unittest.main()
