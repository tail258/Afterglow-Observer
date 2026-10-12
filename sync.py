"""Synchronize this public source repository, never the user's note vault."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

REMOTE = "https://github.com/tail258/Afterglow-Observer.git"
ROOT_FILES = {"app.py", "history.py", "sync.py", "README.md", ".gitignore", ".gitattributes",
              "启动.ps1", "启动.cmd", "同步.ps1", "启用自动同步.ps1", "停用自动同步.ps1"}
PRIVATE_PARTS = {"work", "outputs", "notes", "vault", ".obsidian", ".trash", ".env", "__pycache__"}
SENSITIVE = [
    re.compile(r"(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{30,}"),
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)[A-Z]:[\\/]+Users[\\/]+(?!Public\b|Default\b)[^\\/\s\"']+"),
    re.compile(r"(?i)(?:api[_-]?key|password|access[_-]?token)\s*[:=]\s*[\"'][A-Za-z0-9_+/=-]{16,}[\"']"),
]


class SyncError(Exception):
    pass


def run_git(repo: Path, *args: str, check=True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    env["GIT_EDITOR"] = "true"
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_EXTERNAL_DIFF"):
        env.pop(key, None)
    try:
        result = subprocess.run(
            [shutil.which("git") or "git", "--no-optional-locks", "-c", "core.fsmonitor=false",
             "-c", "core.hooksPath=", "-C", str(repo), *args], capture_output=True,
            env=env, timeout=90, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SyncError(f"Git 无法执行：{exc}") from exc
    if check and result.returncode:
        raise SyncError(result.stderr.decode("utf-8", "replace").strip() or "Git 操作失败")
    return result


def output(repo, *args):
    return run_git(repo, *args).stdout.decode("utf-8", "surrogateescape").strip()


def normalized_remote(url):
    return url.strip().replace("git@github.com:", "https://github.com/").removesuffix("/").removesuffix(".git").casefold()


def public_path(path: str) -> bool:
    p = PurePosixPath(path)
    if PRIVATE_PARTS.intersection(p.parts) or ".local." in p.name:
        return False
    if path in ROOT_FILES:
        return True
    # New source modules require an explicit `git add` before automatic syncing.
    if p.suffix == ".py" and (len(p.parts) == 1 or p.parts[0] == "tests"):
        return not any(word in p.stem.casefold() for word in ("secret", "private", "credential"))
    return p.parts[:2] == (".github", "workflows") and p.suffix in {".yml", ".yaml"}


def private_values(repo: Path) -> list[str]:
    values = []
    try:
        vault = json.loads((repo / "settings.local.json").read_text(encoding="utf-8")) .get("vault", "")
        if isinstance(vault, str) and vault:
            values.extend([vault, vault.replace("\\", "/"), vault.replace("\\", "\\\\")])
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return values


def audit_content(path: str, content: bytes, private=()):
    if not public_path(path):
        raise SyncError(f"拒绝同步非公开源码路径：{path}")
    if len(content) > 2_000_000:
        raise SyncError(f"拒绝同步过大的源码文件：{path}")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SyncError(f"拒绝同步非 UTF-8 文本：{path}") from exc
    if any(pattern.search(text) for pattern in SENSITIVE) or any(value in text for value in private):
        raise SyncError(f"隐私检查阻止同步：{path} 含疑似凭据、用户主目录或本地笔记路径")


def audit_tree(repo: Path, ref: str | None = None):
    private = private_values(repo)
    if ref:
        raw = run_git(repo, "ls-tree", "-r", "-z", ref).stdout
        entries = []
        for record in raw.split(b"\0"):
            if record:
                metadata, name = record.split(b"\t", 1)
                mode, kind, oid = metadata.decode().split()
                if mode not in {"100644", "100755"} or kind != "blob":
                    raise SyncError("拒绝同步链接、子模块或其他非普通源码文件")
                entries.append((name.decode("utf-8", "surrogateescape"), oid))
    else:
        entries = []
        for record in run_git(repo, "ls-files", "--stage", "-z").stdout.split(b"\0"):
            if record:
                metadata, name = record.split(b"\t", 1)
                mode, oid, stage = metadata.decode().split()
                if stage != "0" or mode not in {"100644", "100755"}:
                    raise SyncError("索引包含冲突或非普通源码文件")
                entries.append((name.decode("utf-8", "surrogateescape"), oid))
    for path, oid in entries:
        if not public_path(path):
            raise SyncError(f"拒绝同步非公开源码路径：{path}")
        audit_content(path, run_git(repo, "cat-file", "blob", oid).stdout, private)


@contextlib.contextmanager
def repo_lock(git_dir: Path):
    file = (git_dir / "afterglow-sync.lock").open("a+b")
    file.seek(0)
    if not file.read(1):
        file.write(b"0")
        file.flush()
    file.seek(0)
    locked = False
    try:
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            raise SyncError("另一次同步正在运行，本次跳过") from exc
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt
                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)
        file.close()


def synchronize(repo: Path, expected_remote=REMOTE) -> str:
    repo = Path(repo).resolve()
    top = Path(output(repo, "rev-parse", "--show-toplevel")).resolve()
    if top != repo:
        raise SyncError("同步目录必须是该项目的 Git 仓库根目录")
    remote = output(repo, "remote", "get-url", "origin")
    push_remote = output(repo, "remote", "get-url", "--push", "origin")
    if any(normalized_remote(url) != normalized_remote(expected_remote) for url in (remote, push_remote)):
        raise SyncError("origin 与指定源码仓库不符，拒绝同步")
    if output(repo, "branch", "--show-current") != "main":
        raise SyncError("自动同步仅处理 main 分支；其他分支请手动操作")
    git_dir = Path(output(repo, "rev-parse", "--absolute-git-dir"))
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "index.lock"):
        if (git_dir / marker).exists():
            raise SyncError("仓库有尚未完成的 Git 操作，本次同步停止")
    with repo_lock(git_dir):
        audit_tree(repo)
        # Validate all tracked working copies before staging any change.
        tracked = run_git(repo, "ls-files", "-z").stdout.decode("utf-8", "surrogateescape").split("\0")
        private = private_values(repo)
        for path in filter(None, tracked):
            file = repo / path
            if file.is_symlink():
                raise SyncError(f"拒绝同步源码链接：{path}")
            if file.exists():
                audit_content(path, file.read_bytes(), private)
        # Only tracked modifications/deletions are added. Unknown personal files stay local.
        run_git(repo, "add", "--update", "--", ".")
        audit_tree(repo)
        if run_git(repo, "diff", "--cached", "--quiet", check=False).returncode == 1:
            run_git(repo, "commit", "-m", "Auto-sync: update public source")
        run_git(repo, "fetch", "--no-tags", "origin", "main")
        audit_tree(repo, "origin/main")
        counts = output(repo, "rev-list", "--left-right", "--count", "HEAD...origin/main").split()
        ahead, behind = map(int, counts)
        if behind:
            if ahead:
                result = run_git(repo, "-c", "rebase.autoStash=false", "-c", "rebase.updateRefs=false",
                                 "rebase", "origin/main", check=False)
                if result.returncode:
                    # Local work was committed before rebasing; abort restores that saved commit.
                    abort = run_git(repo, "rebase", "--abort", check=False)
                    if abort.returncode:
                        raise SyncError("合并失败且自动退出失败，请手动检查仓库；没有强制推送")
                    raise SyncError("两台设备的代码发生冲突，已恢复本地提交，请手动合并后再次同步")
            else:
                run_git(repo, "merge", "--ff-only", "origin/main")
        audit_tree(repo, "HEAD")
        # Audit every outgoing commit, so a removed secret cannot leak via history.
        outgoing = output(repo, "rev-list", "origin/main..HEAD").splitlines()
        for commit in outgoing:
            audit_tree(repo, commit)
        # An editor may save during fetch/rebase. Never commit that mid-sync change implicitly.
        run_git(repo, "push", "origin", "HEAD:main")
        return "已同步" if ahead or behind or outgoing else "已是最新，无需同步"


def main():
    parser = argparse.ArgumentParser(description="只同步 Afterglow Observer 公开源码")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--audit", action="store_true", help="只检查暂存区，不提交、不联网")
    args = parser.parse_args()
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    status = ""
    success = False
    try:
        if args.audit:
            audit_tree(args.repo)
            status = "公开源码与隐私检查通过"
        else:
            status = synchronize(args.repo)
        success = True
    except Exception as exc:
        status = str(exc)
    if not args.quiet and sys.stdout:
        print(status)
    if not args.audit:
        # Store only the latest result under .git; this is never committed.
        try:
            if normalized_remote(output(args.repo, "remote", "get-url", "origin")) != normalized_remote(REMOTE):
                raise SyncError("不在源码仓库写入同步状态")
            git_dir = Path(output(args.repo, "rev-parse", "--absolute-git-dir"))
            result = {"time": datetime.now(timezone.utc).isoformat(), "ok": success, "message": status}
            (git_dir / "afterglow-sync-status.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
