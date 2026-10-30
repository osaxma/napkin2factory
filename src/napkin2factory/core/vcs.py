"""The one git wrapper (decision D31).

Every git invocation goes through :class:`Vcs`.  stdout and stderr are captured and
every failure is translated into persona vocabulary before it reaches a user: a
"draft" is a branch, a "snapshot" is a commit, a "Revision" is a tag.  Raw git text
never reaches a user-facing stream; it is kept on the exception as ``detail`` for
``--json`` and logs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from napkin2factory.core.errors import EnvironmentProblem

NOT_A_PROJECT = (
    "this folder isn't a napkin2factory project yet — run `n2f init <dir>` to start one "
    "(it also sets up change tracking)"
)
NOT_TRACKED = (
    "this product folder isn't under change tracking yet — run `n2f init .` inside it "
    "to set tracking up (nothing else changes)"
)
UNSAVED = (
    "you have changes that are not saved yet: `n2f snapshot` saves them, "
    "`n2f discard` drops them, or `n2f ecr new …` files them as a change request"
)
NO_GIT = "git is not installed or not on PATH; install git (https://git-scm.com) and try again"


class VcsError(EnvironmentProblem):
    """A change-tracking problem, worded for the operator; raw git text is on ``detail``."""

    def __init__(self, message: str, detail: str = "", code: str = "vcs") -> None:
        super().__init__(message)
        self.detail = detail
        self.code = code


@dataclass
class Vcs:
    """Change tracking for one product repository."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()

    # ---- plumbing ---------------------------------------------------------

    def _git(
        self, *args: str, check: bool = True, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        if shutil.which("git") is None:
            raise VcsError(NO_GIT, code="no-git")
        full_env = dict(os.environ)
        # Never let a user's global hooks/pager/identity gaps break unattended runs.
        full_env.update({"GIT_PAGER": "cat", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"})
        if "GIT_AUTHOR_NAME" not in full_env:
            full_env.setdefault("GIT_AUTHOR_NAME", "napkin2factory")
            full_env.setdefault("GIT_AUTHOR_EMAIL", "n2f@localhost")
            full_env.setdefault("GIT_COMMITTER_NAME", "napkin2factory")
            full_env.setdefault("GIT_COMMITTER_EMAIL", "n2f@localhost")
        if env:
            full_env.update(env)
        proc = subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=full_env,
            check=False,
        )
        if check and proc.returncode != 0:
            raise VcsError(
                self._translate(args, proc),
                detail=(proc.stderr or proc.stdout).strip(),
                code=self._code(proc),
            )
        return proc

    @staticmethod
    def _code(proc: subprocess.CompletedProcess[str]) -> str:
        err = (proc.stderr or "").lower()
        if "not a git repository" in err:
            return "not-a-repo"
        if "nothing to commit" in err or "nothing to commit" in (proc.stdout or "").lower():
            return "nothing-to-snapshot"
        if "already exists" in err:
            return "exists"
        return "vcs"

    def _translate(self, args: tuple[str, ...], proc: subprocess.CompletedProcess[str]) -> str:
        code = self._code(proc)
        verb = args[0] if args else ""
        if code == "not-a-repo":
            return NOT_TRACKED
        if code == "nothing-to-snapshot":
            return "nothing changed since the last snapshot"
        if code == "exists" and verb == "tag":
            return f"Revision {args[-1]} already exists; pick the next version number"
        if verb == "worktree":
            return (
                "could not create a scratch copy of an earlier Revision; make sure the "
                "Revision exists (`n2f ecr list` shows released versions)"
            )
        return f"change tracking failed during '{verb}'; run with --json to see the detail"

    # ---- state queries ----------------------------------------------------

    def is_repo_root(self) -> bool:
        """True if ``root`` is itself the top of a tracked repository (D23)."""
        proc = self._git("rev-parse", "--show-toplevel", check=False)
        if proc.returncode != 0:
            return False
        return Path(proc.stdout.strip()).resolve() == self.root

    def is_tracked(self) -> bool:
        """True if ``root`` is inside any repository."""
        return self._git("rev-parse", "--git-dir", check=False).returncode == 0

    def require_repo_root(self) -> None:
        """Raise the persona-worded error unless this folder is a repository root."""
        if not self.is_tracked():
            raise VcsError(NOT_TRACKED, code="not-a-repo")
        if not self.is_repo_root():
            raise VcsError(
                "this product folder is inside a larger tracked folder; napkin2factory needs each "
                "product to be its own project root — copy it out and run `n2f init` there",
                code="not-root",
            )

    def is_clean(self) -> bool:
        """True when there are no unsaved changes (ignored files excluded)."""
        proc = self._git("status", "--porcelain", "--untracked-files=all")
        return proc.stdout.strip() == ""

    def require_clean(self) -> None:
        """Raise unless the tree has no unsaved changes."""
        if not self.is_clean():
            raise VcsError(
                UNSAVED, detail=self._git("status", "--porcelain").stdout, code="unsaved"
            )

    def head(self) -> str | None:
        """Current snapshot id, or None before the first snapshot."""
        proc = self._git("rev-parse", "--verify", "HEAD", check=False)
        return proc.stdout.strip() if proc.returncode == 0 else None

    def short_head(self) -> str:
        """Short snapshot id (``"none"`` before the first snapshot)."""
        h = self.head()
        return h[:10] if h else "none"

    def tags(self) -> list[str]:
        """Released Revisions (tags), oldest first."""
        proc = self._git("tag", "--list", "--sort=creatordate", check=False)
        return [t for t in proc.stdout.split() if t] if proc.returncode == 0 else []

    def tag_for_head(self) -> str | None:
        """Revision name if HEAD is exactly a released Revision."""
        proc = self._git("describe", "--tags", "--exact-match", "HEAD", check=False)
        return proc.stdout.strip() if proc.returncode == 0 else None

    def commit_date(self, ref: str = "HEAD") -> str:
        """ISO date of a snapshot (used for title blocks, D14)."""
        proc = self._git("log", "-1", "--format=%cs", ref, check=False)
        return (
            proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else "unsnapshotted"
        )

    def ref_exists(self, ref: str) -> bool:
        """True if a Revision or snapshot id resolves."""
        return (
            self._git(
                "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False
            ).returncode
            == 0
        )

    # ---- actions ----------------------------------------------------------

    def init(self) -> None:
        """Start change tracking in ``root`` (idempotent)."""
        if self.is_tracked() and self.is_repo_root():
            return
        self._git("init", "-q", "-b", "main")

    def snapshot(self, message: str, allow_empty: bool = False) -> str:
        """Record a snapshot of everything; returns its id."""
        self._git("add", "-A")
        args = ["commit", "-q", "-m", message]
        if allow_empty:
            args.append("--allow-empty")
        proc = self._git(*args, check=False)
        if proc.returncode != 0:
            code = self._code(proc)
            if code == "nothing-to-snapshot":
                h = self.head()
                if h:
                    return h
            raise VcsError(
                self._translate(tuple(args), proc), detail=proc.stderr.strip(), code=code
            )
        return self.head() or ""

    def tag(self, name: str, message: str) -> None:
        """Mark the current snapshot as a released Revision."""
        self._git("tag", "-a", name, "-m", message)

    def discard(self) -> None:
        """Drop every change since the last snapshot (tracked files restored, new files removed)."""
        self._git("checkout", "--", ".")
        self._git("clean", "-fdq", "--exclude=build")

    def worktree_add(self, ref: str, path: Path) -> None:
        """Materialise an earlier Revision in a scratch folder (for `n2f diff`)."""
        self._git("worktree", "add", "--detach", str(path), ref)

    def worktree_remove(self, path: Path) -> None:
        """Remove a scratch folder created by :meth:`worktree_add`."""
        self._git("worktree", "remove", "--force", str(path), check=False)

    def changed_in_last_snapshot(self) -> list[str]:
        """Files the most recent snapshot changed (empty before the second snapshot)."""
        proc = self._git("diff", "--name-only", "HEAD~1", "HEAD", check=False)
        return [ln for ln in proc.stdout.splitlines() if ln.strip()] if proc.returncode == 0 else []

    def diff_names(self, ref_a: str, ref_b: str) -> list[str]:
        """Files that differ between two Revisions."""
        proc = self._git("diff", "--name-only", ref_a, ref_b)
        return [ln for ln in proc.stdout.splitlines() if ln.strip()]

    def apply_patch(self, patch_path: Path) -> None:
        """Apply a unified diff over the working tree (design change requests, D7)."""
        proc = self._git("apply", "--whitespace=nowarn", str(patch_path), check=False)
        if proc.returncode != 0:
            raise VcsError(
                f"the change request's patch ({patch_path.name}) no longer fits the model; "
                "it was written against an earlier state — re-create it with "
                "`n2f ecr new --kind design`",
                detail=proc.stderr.strip(),
                code="patch",
            )
