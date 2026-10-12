"""Read-only history collection. No note contents, index writes, or network access."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Callable

SHANGHAI = timezone(timedelta(hours=8), "Asia/Shanghai")
EXCLUDED = {".git", ".obsidian", ".trash", "node_modules"}
ROOT_FOLDER = "（根目录）"


def is_note(path: str) -> bool:
    return path.lower().endswith(".md") and not EXCLUDED.intersection(PurePosixPath(path).parts)


def in_folder(path: str, folder: str) -> bool:
    if not folder:
        return True
    if folder == ROOT_FOLDER:
        return "/" not in path
    return path.startswith(folder + "/")


class HistoryError(Exception):
    pass


def git_executable() -> str:
    found = shutil.which("git")
    if found:
        return found
    for candidate in (r"E:\Git\cmd\git.exe", r"C:\Program Files\Git\cmd\git.exe"):
        if Path(candidate).is_file():
            return candidate
    raise HistoryError("未找到 Git。请安装 Git，或将 git.exe 所在目录加入 PATH。")


def git_read(root: Path, *args: str) -> bytes:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    # Remove ambient Git overrides so the selected folder is authoritative.
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_EXTERNAL_DIFF"):
        env.pop(key, None)
    try:
        result = subprocess.run(
            [git_executable(), "--no-optional-locks", "-c", "core.fsmonitor=false",
             "-c", "core.quotePath=false", "-C", str(root), *args],
            capture_output=True, env=env, timeout=180,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HistoryError(f"读取 Git 失败：{exc}") from exc
    if result.returncode:
        error = result.stderr.decode("utf-8", "replace").strip()
        raise HistoryError(error or "读取 Git 失败")
    return result.stdout


@dataclass
class Commit:
    sha: str
    authored: datetime
    committed: datetime
    parents: list[str]
    changes: list[tuple[str, tuple[str, ...]]]


def parse_log(raw: bytes) -> list[Commit]:
    """NUL-separated paths preserve spaces, Unicode, and tabs."""
    tokens = raw.decode("utf-8", "surrogateescape").split("\0")
    result: list[Commit] = []
    i = 0
    current = None
    while i < len(tokens):
        token = tokens[i].lstrip("\n")
        i += 1
        if not token:
            continue
        if token.startswith("\x1e"):
            sha, authored, committed, parents = token[1:].split("\x1f")
            current = Commit(sha, datetime.fromisoformat(authored),
                             datetime.fromisoformat(committed), parents.split(), [])
            result.append(current)
            continue
        if current is None or not re.fullmatch(r"[ACDMRTUXB]+\d*", token):
            raise HistoryError("无法解析 Git 历史记录")
        count = 2 if re.fullmatch(r"[RC]\d+", token) else 1
        paths = tuple(tokens[i:i + count])
        if len(paths) != count or any(not p for p in paths):
            raise HistoryError("Git 路径记录不完整")
        i += count
        current.changes.append((token, paths))
    return result


@dataclass(frozen=True)
class Event:
    when: datetime
    path: str
    operation: str
    source: str
    commit: str = ""
    old_path: str = ""

    @property
    def day(self) -> date:
        return self.when.astimezone(SHANGHAI).date()


class Identities:
    """Recognized Git renames share an identity; copies remain separate."""
    def __init__(self):
        self.parents: dict[str, str] = {}

    def find(self, path: str) -> str:
        self.parents.setdefault(path, path)
        head = path
        while self.parents[head] != head:
            head = self.parents[head]
        while self.parents[path] != path:
            old = self.parents[path]
            self.parents[path] = head
            path = old
        return head

    def join(self, old: str, new: str):
        self.parents[self.find(new)] = self.find(old)


@dataclass
class DayNote:
    identity: str
    path: str
    operations: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    paths: set[str] = field(default_factory=set)
    commits: set[str] = field(default_factory=set)
    renamed: bool = False


@dataclass
class Snapshot:
    vault: Path
    repo: Path | None
    cutoff: datetime | None
    commits: int
    head: str
    events: list[Event]
    identities: Identities
    current_paths: set[str]
    folders: list[str]
    warnings: list[str]

    def daily(self, year: int, folder: str = "") -> dict[date, list[DayNote]]:
        grouped: dict[date, dict[str, DayNote]] = defaultdict(dict)
        for event in self.events:
            if event.day.year != year:
                continue
            if not (in_folder(event.path, folder) or
                    (event.old_path and in_folder(event.old_path, folder))):
                continue
            identity = self.identities.find(event.path)
            note = grouped[event.day].setdefault(identity, DayNote(identity, event.path))
            note.path = event.path
            note.operations.add(event.operation)
            note.sources.add(event.source)
            note.paths.add(event.path)
            if event.old_path:
                note.paths.add(event.old_path)
                note.renamed = True
            if event.commit:
                note.commits.add(event.commit)
        return {day: sorted(notes.values(), key=lambda n: n.path.casefold())
                for day, notes in grouped.items()}

    @property
    def years(self) -> list[int]:
        years = {e.day.year for e in self.events} | {datetime.now(SHANGHAI).year}
        return list(range(max(years), min(years) - 1, -1))


def metadata_events(path: str, created: float | None, modified: float,
                    cutoff: datetime | None) -> list[Event]:
    result = []
    for timestamp, operation in ((created, "创建"), (modified, "修改")):
        if timestamp is None:
            continue
        when = datetime.fromtimestamp(timestamp, SHANGHAI)
        if cutoff is None or when < cutoff:
            result.append(Event(when, path, operation, "文件时间"))
    return result


def scan_files(vault: Path) -> tuple[dict[str, os.stat_result], list[str]]:
    files = {}
    warnings = []

    def onerror(error):
        warnings.append(f"无法读取目录：{error.filename}")

    def linked(path: Path) -> bool:
        # Windows junctions and symlinks must not take the scan outside the vault.
        return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)

    for parent, dirs, names in os.walk(vault, followlinks=False, onerror=onerror):
        kept = []
        for name in dirs:
            try:
                if name not in EXCLUDED and not linked(Path(parent) / name):
                    kept.append(name)
            except OSError:
                warnings.append(f"无法读取目录：{Path(parent) / name}")
        dirs[:] = kept
        for name in names:
            file = Path(parent) / name
            relative = file.relative_to(vault).as_posix()
            if not is_note(relative):
                continue
            try:
                if not linked(file):
                    files[relative] = file.stat()
            except OSError:
                warnings.append(f"无法读取文件时间：{relative}")
    return files, warnings


def load_history(vault: str | Path, progress: Callable[[str], None] = lambda _: None) -> Snapshot:
    vault = Path(vault).expanduser().resolve()
    if not vault.is_dir():
        raise HistoryError(f"笔记目录不存在：{vault}")
    progress("正在读取 Git 历史…")
    repo = None
    head = ""
    commits = []
    cutoff = None
    warnings = []
    # A missing repository is valid; other failures must not silently become metadata data.
    try:
        repo = Path(git_read(vault, "rev-parse", "--show-toplevel").decode("utf-8").strip()).resolve()
    except HistoryError as exc:
        if "not a git repository" not in str(exc):
            raise
    if repo:
        if git_read(repo, "rev-parse", "--is-shallow-repository").strip() == b"true":
            raise HistoryError("这是浅克隆仓库，无法确定首次提交。请使用具有完整历史的本地仓库。")
        try:
            head = git_read(repo, "rev-parse", "--verify", "HEAD").decode().strip()
        except HistoryError:
            # An unborn branch is only accepted when there really are no commits.
            if git_read(repo, "rev-list", "--all").strip():
                raise
            warnings.append("仓库尚无提交，当前仅使用文件时间。")
        if head:
            commits = parse_log(git_read(
                repo, "log", "--reverse", "--topo-order", "--root", "--diff-merges=combined",
                "--format=%x1e%H%x1f%aI%x1f%cI%x1f%P", "-z", "--name-status", "-M",
                "--no-ext-diff", "--no-textconv", head, "--"))
            roots = [c.committed for c in commits if not c.parents]
            if not roots:
                raise HistoryError("Git 历史缺少根提交，无法确定文件时间的截止点。")
            cutoff = min(roots)
    else:
        warnings.append("目录没有 Git 仓库，当前仅使用文件时间。")

    prefix = vault.relative_to(repo).as_posix() if repo else "."

    def scoped(path):
        if prefix == ".":
            return path
        return path[len(prefix) + 1:] if path.startswith(prefix + "/") else None

    identities = Identities()
    events = []
    for commit in commits:
        for status, paths in commit.changes:
            old = scoped(paths[0]) if len(paths) == 2 else None
            path = scoped(paths[-1])
            if status.startswith("R") and len(paths) == 2:
                if old and path:
                    identities.join(old, path)
                if old and is_note(old) and (path is None or not is_note(path)):
                    events.append(Event(commit.authored, old, "删除", "Git", commit.sha))
                if path and is_note(path):
                    operation = "修改" if old and is_note(old) else "创建"
                    events.append(Event(commit.authored, path, operation, "Git", commit.sha,
                                        old if old and is_note(old) else ""))
            elif path and is_note(path):
                operation = "删除" if "D" in status else "创建" if set(status) <= {"A", "C"} or status.startswith("C") else "修改"
                events.append(Event(commit.authored, path, operation, "Git", commit.sha))
    progress("正在读取文件时间…")
    files, scan_warnings = scan_files(vault)
    warnings.extend(scan_warnings)
    for path, stat in files.items():
        # POSIX ctime is inode change time, never a creation time.
        created = stat.st_ctime if os.name == "nt" else getattr(stat, "st_birthtime", None)
        events.extend(metadata_events(path, created, stat.st_mtime, cutoff))
    events.sort(key=lambda e: (e.when, e.commit, e.path))
    all_paths = set(files) | {e.path for e in events} | {e.old_path for e in events if e.old_path}
    folders = set()
    for path in all_paths:
        parts = PurePosixPath(path).parts[:-1]
        if not parts:
            folders.add(ROOT_FOLDER)
        for i in range(1, len(parts) + 1):
            folders.add("/".join(parts[:i]))
    return Snapshot(vault, repo, cutoff, len(commits), head, events, identities,
                    set(files), sorted(folders, key=str.casefold), warnings)


def summary(snapshot: Snapshot, year: int, folder: str = "") -> dict:
    daily = snapshot.daily(year, folder)
    return {
        "year": year, "active_days": len(daily),
        "unique_notes": len({n.identity for notes in daily.values() for n in notes}),
        "note_days": sum(map(len, daily.values())),
        "current_notes": sum(in_folder(p, folder) for p in snapshot.current_paths),
        "commits": snapshot.commits, "head": snapshot.head,
        "first_commit": snapshot.cutoff.isoformat() if snapshot.cutoff else None,
        "metadata_events": sum(e.source == "文件时间" for e in snapshot.events),
        "daily_counts": {d.isoformat(): len(n) for d, n in sorted(daily.items())},
        "warnings": snapshot.warnings,
    }
