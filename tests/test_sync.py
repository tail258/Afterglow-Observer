import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from sync import SyncError, audit_content, synchronize


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="afterglow-sync-test-")
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        self.a = self.root / "device-a"
        self.b = self.root / "device-b"
        self.git(self.root, "init", "--bare", "-b", "main", str(self.remote))
        self.git(self.root, "clone", str(self.remote), str(self.a))
        self.identity(self.a)
        self.write(self.a, "app.py", "value = 1\n")
        self.write(self.a, "history.py", "other = 1\n")
        self.write(self.a, ".gitignore", "settings.local.json\nwork/\n.env\n")
        self.commit(self.a)
        self.git(self.a, "push", "origin", "main")
        self.git(self.root, "clone", str(self.remote), str(self.b))
        self.identity(self.b)

    def tearDown(self):
        def repair(function, path, _):
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            function(path)
        shutil.rmtree(self.root, onerror=repair)
        self.temp.cleanup()

    def git(self, repo, *args):
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, timeout=30)
        if result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", "replace"))
        return result.stdout.decode("utf-8", "replace").strip()

    def identity(self, repo):
        self.git(repo, "config", "user.name", "Test")
        self.git(repo, "config", "user.email", "test@example.invalid")

    def write(self, repo, path, text):
        file = repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")

    def commit(self, repo):
        self.git(repo, "add", "--all")
        self.git(repo, "commit", "-m", "test")

    def sync(self, repo):
        return synchronize(repo, expected_remote=str(self.remote))

    def test_push_changes_but_never_untracked_notes_or_settings(self):
        self.write(self.a, "app.py", "value = 2\n")
        self.write(self.a, "个人笔记.md", "synthetic private fixture")
        self.write(self.a, "settings.local.json", '{"vault":"local-only"}')
        self.sync(self.a)
        self.sync(self.b)
        self.assertEqual((self.b / "app.py").read_text(), "value = 2\n")
        self.assertFalse((self.b / "个人笔记.md").exists())
        self.assertFalse((self.b / "settings.local.json").exists())

    def test_pull_remote_changes(self):
        self.write(self.b, "history.py", "other = 2\n")
        self.sync(self.b)
        self.sync(self.a)
        self.assertEqual((self.a / "history.py").read_text(), "other = 2\n")

    def test_independent_dual_device_changes_are_combined(self):
        self.write(self.a, "app.py", "value = 2\n")
        self.write(self.b, "history.py", "other = 2\n")
        self.sync(self.b)
        self.sync(self.a)
        self.sync(self.b)
        self.assertEqual((self.a / "history.py").read_text(), "other = 2\n")
        self.assertEqual((self.b / "app.py").read_text(), "value = 2\n")

    def test_conflict_aborts_and_preserves_both_devices(self):
        self.write(self.a, "app.py", "value = 2\n")
        self.write(self.b, "app.py", "value = 3\n")
        self.sync(self.b)
        remote_before = self.git(self.remote, "rev-parse", "main")
        with self.assertRaisesRegex(SyncError, "冲突"):
            self.sync(self.a)
        self.assertEqual((self.a / "app.py").read_text(), "value = 2\n")
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), remote_before)
        self.assertFalse((self.a / ".git" / "rebase-merge").exists())
        self.assertEqual(self.git(self.a, "status", "--porcelain"), "")

    def test_manually_staged_note_is_blocked(self):
        self.write(self.a, "note.md", "synthetic fixture")
        self.git(self.a, "add", "note.md")
        old = self.git(self.remote, "rev-parse", "main")
        with self.assertRaisesRegex(SyncError, "非公开源码"):
            self.sync(self.a)
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), old)

    def test_secret_in_working_source_is_blocked_before_staging(self):
        token = "gh" + "p_" + "A" * 40
        self.write(self.a, "app.py", f"secret = '{token}'\n")
        old = self.git(self.remote, "rev-parse", "main")
        with self.assertRaisesRegex(SyncError, "隐私检查"):
            self.sync(self.a)
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), old)
        self.assertEqual(self.git(self.a, "diff", "--cached", "--name-only"), "")

    def test_secret_in_an_older_outgoing_commit_is_blocked(self):
        token = "gh" + "p_" + "A" * 40
        self.write(self.a, "app.py", f"secret = '{token}'\n")
        self.commit(self.a)
        self.write(self.a, "app.py", "value = 2\n")
        self.commit(self.a)
        old = self.git(self.remote, "rev-parse", "main")
        with self.assertRaisesRegex(SyncError, "隐私检查"):
            self.sync(self.a)
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), old)

    def test_wrong_repository_remote_and_branch_are_rejected(self):
        with self.assertRaisesRegex(SyncError, "不符"):
            synchronize(self.a)
        self.git(self.a, "checkout", "-b", "feature")
        with self.assertRaisesRegex(SyncError, "main"):
            self.sync(self.a)

    def test_no_change_does_not_create_versions(self):
        before = self.git(self.a, "rev-parse", "HEAD")
        self.sync(self.a)
        self.assertEqual(before, self.git(self.a, "rev-parse", "HEAD"))

    def test_configured_private_path_is_rejected(self):
        self.write(self.a, "settings.local.json", '{"vault":"private-vault-location"}')
        self.write(self.a, "app.py", "path = 'private-vault-location'\n")
        with self.assertRaisesRegex(SyncError, "隐私检查"):
            self.sync(self.a)


if __name__ == "__main__":
    unittest.main()
