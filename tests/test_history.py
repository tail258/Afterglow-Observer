import os
import hashlib
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from history import SHANGHAI, HistoryError, git_read, load_history, metadata_events, summary


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="footprints-test-")
        self.root = Path(self.temp.name)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")

    def tearDown(self):
        # Git objects are read-only on Windows; only remove this test-owned directory.
        import shutil
        import stat
        def repair(function, path, _):
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            function(path)
        shutil.rmtree(self.root, onerror=repair)
        self.temp.cleanup()

    def git(self, *args, when=None):
        env = os.environ.copy()
        if when:
            env["GIT_AUTHOR_DATE"] = when
            env["GIT_COMMITTER_DATE"] = when
        result = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, env=env)
        if result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", "replace"))
        return result.stdout

    def write(self, path, text):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")

    def commit(self, when):
        self.git("add", "--all")
        self.git("commit", "-m", "test", when=when)

    def test_same_day_rename_modify_delete_and_untracked(self):
        self.write("笔记本/原 名.md", "hello\n" * 30)
        self.write(".obsidian/插件说明.md", "ignore")
        self.commit("2020-01-01T10:00:00+08:00")
        self.git("mv", "笔记本/原 名.md", "笔记本/新 名.md")
        self.write("笔记本/新 名.md", "hello\n" * 30 + "edit\n")
        self.commit("2020-01-01T12:00:00+08:00")
        self.git("rm", "笔记本/新 名.md")
        self.commit("2020-01-01T13:00:00+08:00")
        self.write("未提交.md", "not counted")
        snapshot = load_history(self.root)
        notes = list(snapshot.daily(2020).values())[0]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].operations, {"创建", "修改", "删除"})
        self.assertTrue(notes[0].renamed)
        self.assertEqual(summary(snapshot, 2020)["current_notes"], 1)
        self.assertEqual(summary(snapshot, 2020)["metadata_events"], 0)

    def test_timestamp_cutoff_is_strict(self):
        cutoff = datetime(2020, 2, 2, 12, tzinfo=SHANGHAI)
        self.assertEqual(metadata_events("n.md", cutoff.timestamp(), cutoff.timestamp(), cutoff), [])
        events = metadata_events("n.md", (cutoff - timedelta(seconds=1)).timestamp(),
                                 (cutoff + timedelta(seconds=1)).timestamp(), cutoff)
        self.assertEqual([e.operation for e in events], ["创建"])
        self.assertEqual(events[0].day.isoformat(), "2020-02-02")

    def test_both_devices_merge_without_duplicate(self):
        self.write("公共.md", "base")
        self.commit("2020-01-01T10:00:00+08:00")
        self.git("checkout", "-b", "device2")
        self.write("第二台/笔记.md", "device2")
        self.commit("2020-01-02T10:00:00+08:00")
        self.git("checkout", "main")
        self.write("第一台/笔记.md", "device1")
        self.commit("2020-01-03T10:00:00+08:00")
        self.git("merge", "--no-ff", "device2", "-m", "sync", when="2020-01-04T10:00:00+08:00")
        s = summary(load_history(self.root), 2020)
        self.assertEqual(s["daily_counts"], {"2020-01-01": 1, "2020-01-02": 1, "2020-01-03": 1})
        self.assertEqual(s["commits"], 4)

    def test_conflict_resolution_is_counted(self):
        self.write("冲突.md", "base\n")
        self.commit("2020-01-01T10:00:00+08:00")
        self.git("checkout", "-b", "device2")
        self.write("冲突.md", "two\n")
        self.commit("2020-01-02T10:00:00+08:00")
        self.git("checkout", "main")
        self.write("冲突.md", "one\n")
        self.commit("2020-01-03T10:00:00+08:00")
        with self.assertRaises(RuntimeError):
            self.git("merge", "device2")
        self.write("冲突.md", "resolution\n")
        self.commit("2020-01-04T10:00:00+08:00")
        s = summary(load_history(self.root), 2020)
        self.assertEqual(s["daily_counts"]["2020-01-04"], 1)

    def test_timezone_and_folder_move(self):
        self.write("旧本/note.md", "same\n" * 30)
        self.commit("2020-12-31T18:00:00+00:00")
        (self.root / "新本").mkdir()
        self.git("mv", "旧本/note.md", "新本/note.md")
        self.commit("2021-01-02T18:00:00+08:00")
        snapshot = load_history(self.root)
        self.assertEqual(summary(snapshot, 2021)["unique_notes"], 1)
        self.assertEqual(summary(snapshot, 2021, "旧本")["active_days"], 2)
        self.assertEqual(summary(snapshot, 2021, "新本")["active_days"], 1)
        self.assertEqual(summary(load_history(self.root / "新本"), 2021)["active_days"], 1)

    def test_unborn_repository(self):
        self.write("新笔记.md", "new")
        snapshot = load_history(self.root)
        self.assertIsNone(snapshot.cutoff)
        self.assertEqual(snapshot.commits, 0)
        self.assertTrue(snapshot.events)

    def test_metadata_old_modification_new_creation(self):
        self.write("笔记.md", "before git")
        old = datetime(2018, 1, 1, tzinfo=SHANGHAI).timestamp()
        os.utime(self.root / "笔记.md", (old, old))
        self.commit("2020-01-01T10:00:00+08:00")
        snapshot = load_history(self.root)
        notes = snapshot.daily(2018)
        self.assertEqual(sum(len(n) for n in notes.values()), 1)
        self.assertEqual(list(notes.values())[0][0].operations, {"修改"})

    def test_note_with_tab_path_and_deleted_history(self):
        # A tab in the Git tree works on POSIX; spaces and Chinese work on Windows.
        path = "中文 文件夹/删掉 的笔记.md"
        self.write(path, "x")
        self.commit("2020-02-29T10:00:00+08:00")
        self.git("rm", path)
        self.commit("2020-03-01T10:00:00+08:00")
        snapshot = load_history(self.root)
        self.assertEqual(summary(snapshot, 2020, "中文 文件夹")["active_days"], 2)
        self.assertIn("中文 文件夹", snapshot.folders)

    def test_shallow_repository_is_rejected(self):
        self.write("n.md", "x")
        self.commit("2020-01-01T10:00:00+08:00")
        (self.root / ".git" / "shallow").write_bytes(self.git("rev-parse", "HEAD"))
        with self.assertRaisesRegex(HistoryError, "浅克隆"):
            load_history(self.root)

    def test_read_does_not_change_repository_or_notes(self):
        self.write("笔记/n.md", "some writing")
        self.commit("2020-01-01T10:00:00+08:00")

        def manifest():
            return {p.relative_to(self.root).as_posix():
                    (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
                    for p in self.root.rglob("*") if p.is_file()}
        before = manifest()
        load_history(self.root)
        self.assertEqual(before, manifest())

    def test_git_failure_does_not_fall_back_to_metadata(self):
        with patch("history.git_read", side_effect=HistoryError("permission denied")):
            with self.assertRaisesRegex(HistoryError, "permission denied"):
                load_history(self.root)

    def test_without_git_uses_metadata_and_shows_warning(self):
        self.write("n.md", "x")
        with patch("history.git_read", side_effect=HistoryError("fatal: not a git repository")):
            snapshot = load_history(self.root)
        self.assertTrue(snapshot.events)
        self.assertTrue(snapshot.warnings)
        self.assertIsNone(snapshot.repo)

    def test_author_date_used_instead_of_later_sync_date(self):
        self.write("n.md", "x")
        self.git("add", "--all")
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = "2020-01-01T10:00:00+08:00"
        env["GIT_COMMITTER_DATE"] = "2020-01-03T10:00:00+08:00"
        subprocess.run(["git", "-C", str(self.root), "commit", "-m", "sync"], env=env,
                       capture_output=True, check=True)
        snapshot = load_history(self.root)
        self.assertEqual(snapshot.cutoff.day, 3)
        self.assertEqual(list(snapshot.daily(2020))[0].day, 1)


if __name__ == "__main__":
    unittest.main()
