import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("escuta_rename", Path(__file__).resolve().parents[1] / "scripts/migrate-escuta-name.py")
rename = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rename)


class EscutaRenameTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.legacy = self.workspace / "escuta-website"
        self.target = self.workspace / "escuta"
        self.legacy.mkdir()
        self.git("init", "-q")
        self.git("remote", "add", "origin", "git@github.com:suportefafar/escuta-website.git")
        (self.legacy / ".gitignore").write_text(".env\nstorage/\n")
        self.git("add", ".gitignore")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "Initial checkout")
        (self.legacy / ".env").write_text("PRIVATE_SETTING=preserved\n")
        (self.legacy / "storage").mkdir()
        (self.legacy / "storage/attachment").write_bytes(b"existing attachment")
        self.override = self.workspace / "compose.prod.local.yaml"

    def git(self, *arguments):
        return subprocess.check_output(["git", "-C", str(self.legacy), *arguments], text=True).strip()

    def test_migration_preserves_private_files_and_external_storage_and_is_idempotent(self):
        self.override.write_text(f"services:\n  escuta-website:\n    volumes:\n      - {self.legacy}/storage:/rails/storage\n      - /var/services-infra/escuta-website/archive:/legacy:ro\n    env_file: [../escuta-website/.env]\n")
        rename.migrate(self.workspace, self.override)
        self.assertFalse(self.legacy.exists())
        self.assertEqual("PRIVATE_SETTING=preserved\n", (self.target / ".env").read_text())
        self.assertEqual(b"existing attachment", (self.target / "storage/attachment").read_bytes())
        self.assertEqual(rename.ORIGIN, rename.git(self.target, "remote", "get-url", "origin"))
        expected = f"services:\n  escuta:\n    volumes:\n      - {self.target}/storage:/rails/storage\n      - /var/services-infra/escuta-website/archive:/legacy:ro\n    env_file: [../escuta/.env]\n"
        self.assertEqual(expected, self.override.read_text())
        self.assertEqual(0o600, self.override.stat().st_mode & 0o777)
        backups = list(self.workspace.glob(".escuta-override-backup-*"))
        self.assertEqual(1, len(backups))
        self.assertIn("  escuta-website:", backups[0].read_text())
        self.assertEqual(0o600, backups[0].stat().st_mode & 0o777)
        rename.migrate(self.workspace, self.override)
        self.assertEqual(expected, self.override.read_text())
        self.assertEqual(backups, list(self.workspace.glob(".escuta-override-backup-*")))

    def test_conflicting_checkouts_are_preserved(self):
        self.target.mkdir()
        with self.assertRaises(RuntimeError):
            rename.migrate(self.workspace)
        self.assertTrue(self.legacy.exists())
        self.assertTrue(self.target.exists())

    def test_conflicting_override_does_not_move_the_checkout(self):
        self.override.write_text("services:\n  escuta: {}\n  escuta-website: {}\n")
        with self.assertRaises(RuntimeError):
            rename.migrate(self.workspace, self.override)
        self.assertTrue(self.legacy.exists())
        self.assertFalse(self.target.exists())

    def test_dirty_checkout_is_preserved(self):
        (self.legacy / "uncommitted.txt").write_text("User work")
        with self.assertRaises(RuntimeError):
            rename.migrate(self.workspace)
        self.assertTrue((self.legacy / "uncommitted.txt").exists())


if __name__ == "__main__":
    unittest.main()
