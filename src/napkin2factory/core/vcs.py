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
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from napkin2factory.core.errors import EnvironmentProblem
from napkin2factory.core.yamlio import read_yaml

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
NO_ONLINE_COPY = (
    "this product has no online copy yet. Make an empty project for it on GitHub (on the "
    "website, signed in to your account), then have your agent link this folder to it; "
    "napkin2factory never creates accounts or online projects itself"
)
# The line of the online copy that GitHub serves as web pages (share mode, S-094). It holds
# nothing but the shared pages, is rewritten on every send, and is never shown to the owner.
PAGES_LINE = "gh-pages"


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

    _identity: dict[str, str] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()

    # ---- plumbing ---------------------------------------------------------

    def _product_name(self) -> str:
        """The product's display name from ``n2f.yaml``, else the folder name."""
        try:
            data = read_yaml(self.root / "n2f.yaml")
            name = data["product"]["name"]
        except (OSError, KeyError, TypeError, yaml.YAMLError):
            return self.root.name
        return name if isinstance(name, str) and name.strip() else self.root.name

    def _fallback_identity(self) -> dict[str, str]:
        """Author/committer variables for whatever identity git has no value for (S-011).

        A configured ``user.name``/``user.email`` (or ``GIT_*`` variables) always wins; an
        owner who has never heard of git gets the product name, so snapshots still work.
        """
        if self._identity is None:
            cwd = self.root if self.root.is_dir() else None
            missing: dict[str, str] = {}
            for field_, value in (("name", self._product_name()), ("email", "n2f@localhost")):
                proc = subprocess.run(
                    ["git", "config", f"user.{field_}"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if not proc.stdout.strip():
                    upper = field_.upper()
                    missing[f"GIT_AUTHOR_{upper}"] = value
                    missing[f"GIT_COMMITTER_{upper}"] = value
            self._identity = missing
        return self._identity

    def _git(
        self, *args: str, check: bool = True, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        if shutil.which("git") is None:
            raise VcsError(NO_GIT, code="no-git")
        full_env = dict(os.environ)
        # Never let a user's global hooks/pager/identity gaps break unattended runs.
        full_env.update({"GIT_PAGER": "cat", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"})
        for key, value in self._fallback_identity().items():
            full_env.setdefault(key, value)
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

    def revision_snapshot(self, name: str) -> str | None:
        """The snapshot id a released Revision (tag) marks, or None when there is no such one."""
        proc = self._git("rev-parse", "--verify", "--quiet", f"{name}^{{commit}}", check=False)
        return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else None

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

    # ---- the online copy (share mode, `n2f publish --online`) ----------------

    def online_copy(self) -> str | None:
        """The name of the linked online copy: ``origin``, else the only one, else None."""
        proc = self._git("remote", check=False)
        names = [n for n in proc.stdout.split() if n] if proc.returncode == 0 else []
        if "origin" in names:
            return "origin"
        return names[0] if len(names) == 1 else None

    def online_address(self, name: str) -> str:
        """Where the online copy ``name`` lives (its fetch address)."""
        return self._git("remote", "get-url", name).stdout.strip()

    def current_line(self) -> str | None:
        """Name of the draft line being worked on (None when detached from any line)."""
        proc = self._git("symbolic-ref", "--short", "-q", "HEAD", check=False)
        if proc.returncode != 0:
            return None
        return proc.stdout.strip() or None

    def snapshot_of_folder(self, folder: Path, message: str) -> str:
        """Record ``folder``'s files as a stand-alone snapshot with no history; returns its id.

        The working tree, the index and every named line stay untouched: a scratch index
        file is used and nothing points at the result until :meth:`send_online` sends it.
        """
        folder = Path(folder).resolve()
        git_dir = self._git("rev-parse", "--absolute-git-dir").stdout.strip()
        index = Path(git_dir) / "n2f-publish.index"
        index.unlink(missing_ok=True)
        env = {"GIT_INDEX_FILE": str(index)}
        where = (f"--git-dir={git_dir}", f"--work-tree={folder}")
        try:
            for args in (
                (*where, "-C", str(folder), "add", "--all", "--force", "."),
                (*where, "write-tree"),
            ):
                proc = self._git(*args, check=False, env=env)
                if proc.returncode != 0:
                    raise VcsError(
                        "could not prepare the pages for sending; run with --json to see the "
                        "detail",
                        detail=(proc.stderr or proc.stdout).strip(),
                        code="pages",
                    )
            tree = proc.stdout.strip()
            return self._git("commit-tree", tree, "-m", message).stdout.strip()
        finally:
            index.unlink(missing_ok=True)

    def send_online(self, name: str, line: str, pages: str | None = None) -> None:
        """Send ``line``, every Revision and (optionally) the pages snapshot to ``name``.

        All or nothing (``--atomic``): the online copy never ends up half updated. The pages
        line is replaced each time (it is generated, nobody builds on it); the draft line and
        the Revisions are only ever added to, never overwritten.
        """
        refspecs = [f"refs/heads/{line}:refs/heads/{line}", "refs/tags/*:refs/tags/*"]
        if pages:
            refspecs.append(f"+{pages}:refs/heads/{PAGES_LINE}")
        # Never wait for a password or a host-key question nobody is there to answer.
        env = {"GIT_SSH_COMMAND": os.environ.get("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")}
        proc = self._git("push", "--atomic", "--porcelain", name, *refspecs, check=False, env=env)
        if proc.returncode == 0:
            return
        text = f"{proc.stdout}\n{proc.stderr}".lower()
        detail = (proc.stderr or proc.stdout).strip()
        if "fetch first" in text or "non-fast-forward" in text:
            raise VcsError(
                "the online copy has snapshots this folder does not have (saved from another "
                "computer?), so nothing was sent; bring them into this folder first, then "
                "publish again",
                detail=detail,
                code="online-newer",
            )
        if "already exists" in text:
            raise VcsError(
                "the online copy already holds a Revision with the same name but different "
                "content, so nothing was sent; released Revisions are never replaced",
                detail=detail,
                code="online-revision-differs",
            )
        raise VcsError(
            "could not reach the online copy (no network, a wrong address, or this computer "
            "is not signed in to it), so nothing was sent; run with --json to see the detail",
            detail=detail,
            code="online-unreachable",
        )

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
