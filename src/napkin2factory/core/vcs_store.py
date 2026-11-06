"""Store primitives of :class:`~napkin2factory.core.vcs.Vcs` (v0.8 R1, S-246).

Callers use ``Vcs``; this mixin only keeps ``vcs.py`` under the module size the project holds
(S-184). It lists saved states with their messages, reads a file at one, diffs one against the
unsaved folder, hashes the folder without saving it, restores a saved state into the folder and
keeps named markers under ``refs/n2f/``. Every git call goes through ``self._git`` (D31); error
texts are in the owner's words (``docs/vocabulary.md``).

History only moves forward (R2): nothing here moves the current snapshot or switches a line.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Literal, NoReturn

# Every named marker lives under this prefix, so `publish` (which sends one line and the
# Revision tags only) never carries one and a fresh copy of the folder has none (R1, R2).
REF_PREFIX = "refs/n2f/"

NO_SUCH_STATE = "that saved state is not in this product's history"
BAD_PATH = "that path is outside the product folder"
BAD_MARKER = (
    "that name cannot be used as a marker: use letters, digits, '-', '_', '.' and '/' "
    "between parts, with no spaces or '..'"
)

ChangeStatus = Literal["added", "changed", "removed"]

_TRAILER = re.compile(r"^([A-Za-z][A-Za-z0-9-]*):[ \t]+(.*)$")
# unit separator between the fields of one log record; never part of a label
_SEP = "\x1f"


@dataclass(frozen=True)
class SnapshotInfo:
    """One saved state: its id, parents, time, label and the trailers of its message."""

    id: str
    parents: tuple[str, ...]
    when: int  # unix seconds
    label: str  # the message's first line
    body: str = ""  # the message after the label, without the trailer block
    trailers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class FileChange:
    """A file that differs between a saved state and the folder (or between two states).

    ``added``: present in the folder but not in the saved state. ``removed``: in the saved
    state, gone from the folder. ``changed``: in both, content or mode differs.
    """

    path: str
    status: ChangeStatus


def split_trailers(body: str) -> tuple[str, dict[str, str]]:
    """Split a message body into its text and its trailer block (``Key: value`` lines).

    The trailer block is the last paragraph when every one of its lines is ``Key: value``.
    """
    paragraphs = re.split(r"\n[ \t]*\n", body.strip("\n"))
    last = paragraphs[-1].splitlines() if paragraphs and paragraphs[-1].strip() else []
    matches = [_TRAILER.match(line) for line in last]
    if not last or not all(matches):
        return body.strip(), {}
    trailers = {m.group(1): m.group(2).strip() for m in matches if m}
    return "\n\n".join(paragraphs[:-1]).strip(), trailers


class StoreMixin:
    """R1's store primitives, written against ``Vcs``'s ``_git`` and ``root``."""

    root: Path

    if TYPE_CHECKING:

        def _git(
            self,
            *args: str,
            check: bool = True,
            env: dict[str, str] | None = None,
            input_text: str | None = None,
        ) -> subprocess.CompletedProcess[str]: ...

        def _git_bytes(
            self, *args: str, env: dict[str, str] | None = None
        ) -> subprocess.CompletedProcess[bytes]: ...

        def _fail(self, message: str, *, code: str, detail: str = "") -> NoReturn: ...

        def head(self) -> str | None:
            """Stub: see ``Vcs.head``."""

        def is_clean(self) -> bool:
            """Stub: see ``Vcs.is_clean``."""

    # ---- argument checks ---------------------------------------------------

    def _check_state(self, ref: str) -> str:
        if not ref or ref.startswith("-") or "\x00" in ref:
            self._fail(NO_SUCH_STATE, code="no-such-state")
        return ref

    def _rel_path(self, path: str) -> str:
        """A normalised path inside the folder, or an error."""
        pure = PurePosixPath(path.replace("\\", "/"))
        if pure.is_absolute() or ".." in pure.parts or "\x00" in path:
            self._fail(BAD_PATH, code="bad-path")
        text = str(pure)
        return "" if text == "." else text

    def _scope(self, paths: Sequence[str] | None) -> tuple[str, ...] | None:
        if paths is None:
            return None
        prefixes = tuple(self._rel_path(p) for p in paths)
        return None if "" in prefixes else prefixes

    @staticmethod
    def _in_scope(path: str, scope: tuple[str, ...] | None) -> bool:
        if scope is None:
            return True
        return any(path == p or path.startswith(p + "/") for p in scope)

    # ---- reading saved states ----------------------------------------------

    def snapshot_count(self, ref: str = "@") -> int:
        """How many saved states lead up to ``ref`` along the main line (0 before the first)."""
        proc = self._git(
            "rev-list", "--count", "--first-parent", self._check_state(ref), check=False
        )
        return int(proc.stdout.strip()) if proc.returncode == 0 and proc.stdout.strip() else 0

    def snapshots(self, ref: str = "@", limit: int | None = None) -> list[SnapshotInfo]:
        """Saved states leading up to ``ref`` (``@`` is the newest), newest first.

        Follows the main line only; history in this package is linear (R2). An empty list
        before the first snapshot; an error when ``ref`` names nothing.
        """
        fmt = _SEP.join(("%H", "%P", "%ct", "%s", "%b"))
        args = ["log", "-z", "--first-parent", f"--format={fmt}"]
        if limit is not None:
            args.append(f"--max-count={max(limit, 0)}")
        proc = self._git(*args, self._check_state(ref), "--", check=False)
        if proc.returncode != 0:
            if ref == "@" and self.head() is None:
                return []
            self._fail(NO_SUCH_STATE, code="no-such-state", detail=proc.stderr.strip())
        out: list[SnapshotInfo] = []
        for record in proc.stdout.split("\x00"):
            if not record.strip():
                continue
            ident, parents, when, label, body = (record.lstrip("\n").split(_SEP, 4) + [""] * 5)[:5]
            text, trailers = split_trailers(body)
            out.append(
                SnapshotInfo(
                    id=ident.strip(),
                    parents=tuple(parents.split()),
                    when=int(when) if when.strip().isdigit() else 0,
                    label=label,
                    body=text,
                    trailers=trailers,
                )
            )
        return out

    def tree_of(self, ref: str) -> str:
        """The id of the tree of files a saved state holds (equal states have equal ids)."""
        proc = self._git(
            "rev-parse", "--verify", "--quiet", f"{self._check_state(ref)}^{{tree}}", check=False
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            self._fail(NO_SUCH_STATE, code="no-such-state")
        return proc.stdout.strip()

    def read_file(self, ref: str, path: str) -> bytes | None:
        """A file's bytes at saved state ``ref``; None when the state has no such file."""
        rel = self._rel_path(path)
        if not rel:
            return None
        self._check_state(ref)
        proc = self._git_bytes("cat-file", "blob", f"{ref}:{rel}")
        if proc.returncode == 0:
            return proc.stdout
        self.tree_of(ref)  # raises when it is the state that does not exist
        return None

    def files(self, ref: str = "@") -> list[str]:
        """Every file saved in state ``ref``, sorted, as ``/``-separated paths in the folder.

        Paths are relative to the product folder, even when the folder sits inside a larger
        repository. An error when ``ref`` names no saved state.
        """
        tree = self.tree_of(ref)  # the owner's error for a missing state
        proc = self._git("ls-tree", "-r", "--name-only", "-z", tree)
        return sorted(name for name in proc.stdout.split("\x00") if name)

    # ---- the folder against a saved state ----------------------------------

    @contextmanager
    def _temp_index(self, *, from_real: bool = True) -> Iterator[dict[str, str]]:
        """A throw-away index file: the real index, HEAD and the folder stay untouched.

        Starts as a copy of the real index (same stat data, so unchanged files are not read
        again) or empty. Yields the environment that makes git use it.
        """
        git_dir = Path(self._git("rev-parse", "--absolute-git-dir").stdout.strip())
        temp = git_dir / f"n2f-store-{os.getpid()}-{uuid.uuid4().hex[:10]}.index"
        real = git_dir / "index"
        if from_real and real.is_file():
            shutil.copy2(real, temp)
        try:
            yield {"GIT_INDEX_FILE": str(temp)}
        finally:
            temp.unlink(missing_ok=True)
            Path(f"{temp}.lock").unlink(missing_ok=True)

    def working_hash(self, exclude: Sequence[str] = ()) -> str:
        """The tree id the folder would have if saved now (nothing is saved or changed).

        Equal folders give equal ids, and the id equals the tree of the snapshot
        ``snapshot()`` would make next. Ignored files (``build/``) do not count. ``exclude``
        leaves out files under those folder prefixes (``"changes/"``): a change request's
        approval hashes the model without its own record, which approving rewrites (S-252).
        """
        with self._temp_index() as env:
            self._git("add", "-A", env=env)
            for prefix in exclude:
                self._git("rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", prefix, env=env)
            return self._git("write-tree", env=env).stdout.strip()

    def diff_working(self, ref: str) -> list[FileChange]:
        """Every file that differs between saved state ``ref`` and the folder as it is now.

        Unsaved and not-yet-tracked files count, ignored ones do not: exactly the set a
        snapshot would save. Sorted by path.
        """
        return self._diff_trees(self.tree_of(ref), self.working_hash())

    def _diff_trees(self, old: str, new: str) -> list[FileChange]:
        if old == new:
            return []
        proc = self._git("diff-tree", "-r", "-z", "--no-renames", "--name-status", old, new)
        tokens = proc.stdout.split("\x00")
        changes: list[FileChange] = []
        for i in range(0, len(tokens) - 1, 2):
            code, path = tokens[i].strip(), tokens[i + 1]
            status: ChangeStatus = (
                "added" if code == "A" else "removed" if code == "D" else "changed"
            )
            changes.append(FileChange(path, status))
        return sorted(changes, key=lambda c: c.path)

    def restore(self, ref: str, paths: Sequence[str] | None = None) -> list[FileChange]:
        """Make the folder's saveable files equal saved state ``ref`` (all, or under ``paths``).

        Files in the state are written back, files the state does not have are removed
        (unsaved new files included, they are part of what a snapshot saves), ignored files
        (``build/``) are never touched. It does not move the current snapshot and saves
        nothing: the caller records a new snapshot afterwards (R2). Returns what changed, as
        seen from the state (``added`` means the folder had it and it was removed).
        """
        scope = self._scope(paths)
        target = self.tree_of(ref)
        changes = [
            c
            for c in self._diff_trees(target, self.working_hash())
            if self._in_scope(c.path, scope)
        ]
        for change in changes:
            if change.status == "added":
                self._remove_file(change.path)
        to_write = [c.path for c in changes if c.status != "added"]
        for start in range(0, len(to_write), 400):
            batch = to_write[start : start + 400]
            self._git(
                "restore",
                f"--source={target}",
                "--worktree",
                "--pathspec-from-file=-",
                "--pathspec-file-nul",
                env={"GIT_LITERAL_PATHSPECS": "1"},
                input_text="\x00".join(batch) + "\x00",
            )
        return changes

    def _remove_file(self, rel: str) -> None:
        """Delete one file of the folder, then the folders it leaves empty (never the root)."""
        target = self.root / rel
        if target.is_symlink() or target.is_file():
            target.unlink()
        parent = target.parent
        while parent != self.root and self.root in parent.parents:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

    # ---- named markers under refs/n2f/ -------------------------------------

    def _marker(self, name: str) -> str:
        """The full ref of marker ``name`` after validating it, or an error."""
        bad = (
            not name
            or name.startswith(("/", "-", "."))
            or name.endswith(("/", "."))
            or ".." in name
            or "//" in name
            or "\\" in name
            or "\x00" in name
        )
        full = f"{REF_PREFIX}{name}"
        if bad or self._git("check-ref-format", full, check=False).returncode != 0:
            self._fail(BAD_MARKER, code="bad-marker")
        return full

    def set_ref(self, name: str, target: str) -> None:
        """Create or move marker ``name`` (relative, as ``parked/C-002``) to saved state ``target``.

        A marker keeps its state reachable and never travels with ``publish``.
        """
        full = self._marker(name)
        proc = self._git(
            "rev-parse", "--verify", "--quiet", f"{self._check_state(target)}^0", check=False
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            self._fail(NO_SUCH_STATE, code="no-such-state")
        done = self._git("update-ref", full, proc.stdout.strip(), check=False)
        if done.returncode != 0:
            self._fail(
                f"could not set the marker {name!r}: another marker already uses part of that name",
                code="marker-conflict",
                detail=done.stderr.strip(),
            )

    def read_ref(self, name: str) -> str | None:
        """The saved state marker ``name`` points at, or None when there is no such marker."""
        proc = self._git("rev-parse", "--verify", "--quiet", self._marker(name), check=False)
        return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else None

    def delete_ref(self, name: str) -> None:
        """Remove marker ``name`` (nothing happens when it does not exist)."""
        full = self._marker(name)
        if self.read_ref(name) is not None:
            self._git("update-ref", "-d", full)

    def list_refs(self, prefix: str = "") -> dict[str, str]:
        """Markers whose name starts with ``prefix`` (whole parts): ``{name: saved state id}``."""
        prefix = prefix.strip("/")
        pattern = REF_PREFIX + (self._marker(prefix)[len(REF_PREFIX) :] if prefix else "")
        proc = self._git("for-each-ref", "--format=%(refname) %(objectname)", pattern, check=False)
        found: dict[str, str] = {}
        for line in proc.stdout.splitlines():
            ref, _, ident = line.rpartition(" ")
            if ref.startswith(REF_PREFIX):
                found[ref[len(REF_PREFIX) :]] = ident
        return dict(sorted(found.items()))
