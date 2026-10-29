import importlib.util
from pathlib import Path
import subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('components',ROOT/'wordpress/prepare-institutional-components.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class ComponentTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.repo=self.root/'repo';self.repo.mkdir()
  self.git('init','-q','-b','main')
 def git(self,*args):
  return subprocess.check_output(['git','-C',str(self.repo),*args],text=True).strip()
 def commit(self):
  self.git('add','.');self.git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture');return self.git('rev-parse','HEAD')
 def test_export_contains_only_public_tracked_files(self):
  for name in ['plugin.php','.env.production','tests/test.php','node_modules/secret','example.env']:
   path=self.repo/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
  sha=self.commit();target=self.root/'release';module.export(self.repo/'.git',sha,target)
  self.assertTrue((target/'plugin.php').is_file())
  self.assertEqual({'.release.json','plugin.php'},{p.name for p in target.iterdir()})
 def test_archive_symlink_rejected_atomically(self):
  (self.repo/'escape').symlink_to('/etc/passwd');sha=self.commit();target=self.root/'release'
  with self.assertRaises(ValueError):module.export(self.repo/'.git',sha,target)
  self.assertFalse(target.exists());self.assertFalse(list(self.root.glob('.component-*')))
 def test_manifest_requires_both_exact_pins(self):
  path=self.root/'manifest';path.write_text('fafar-cf7crud\turl\t'+'a'*40+'\n')
  with self.assertRaises(ValueError):module.manifest(path)
  path.write_text(path.read_text()+'institutional-astra-child-theme\turl\t'+'b'*40+'\n')
  self.assertEqual(2,len(module.manifest(path)))
 def test_uncached_no_pull_fails_without_network(self):
  path=self.root/'manifest';path.write_text(''.join(f'{name}\tunused-url\t'+ 'a'*40+'\n' for name in module.NAMES))
  result=subprocess.run(['python3',str(ROOT/'wordpress/prepare-institutional-components.py'),'--manifest',str(path),'--cache',str(self.root/'cache'),'--releases',str(self.root/'releases'),'--no-pull'],capture_output=True,text=True)
  self.assertNotEqual(0,result.returncode);self.assertIn('not cached',result.stderr)
if __name__=='__main__':unittest.main()
