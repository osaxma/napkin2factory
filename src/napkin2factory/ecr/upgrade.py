"""The schema 1 → 2 migration of change requests (v0.8 R8, S-261).

Schema 1 filed a change request as a draft, assessed its impact, approved it, applied it
(a patch or edits) and closed it. Schema 2 edits the model in place: ``draft → approved →
closed`` or ``draft | approved → aborted``, one open at a time, each open one with the
checkpoint it started from (``baseline``) and an approved one with the hash of the model it
approved. ``n2f init .`` calls :func:`upgrade_change_requests` after it saved the folder.

The mapping, per request:

* ``draft`` or ``impact`` (with or without a patch) and ``approved`` but not applied: open
  (``draft``). Its baseline is the folder as it stands once the file format is upgraded; its
  edits, or its patch, are then applied to the model files, as ``ecr start --set`` would. An
  approved one loses its approval and is told to approve it again.
* ``applied`` but not closed: ``approved`` for the model as it is, started from the state
  before it was applied when the history still has it.
* ``closed`` and ``rejected``: unchanged (the patch file stays as a record).
* More than one open: the lowest id stays open; the others become ``aborted`` with their
  edit kept in their file (or their patch file), because one request is open at a time.

Nothing is changed unless the open request's edits and patch still fit the model (checked on
a scratch copy first); then the refusal names the request and the file. The steps leave
checkpoints (before, upgraded, started, carried over), so an owner can go back.
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from napkin2factory.core import checkpoints as cps
from napkin2factory.core.checkpoints import Vitals
from napkin2factory.core.errors import N2FError
from napkin2factory.core.loader import load_product
from napkin2factory.core.model import Edit
from napkin2factory.core.model.migrate import write_schema
from napkin2factory.core.product import Paths
from napkin2factory.core.vcs import Vcs, VcsError
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip
from napkin2factory.ecr.apply import _set_in_yaml
from napkin2factory.ecr.checkpointing import APPROVAL_HASH_EXCLUDE, checkpoint

#: The version this migration writes.
TO_VERSION = 2
#: Schema 1 states that were still being worked on.
_UNFINISHED = ("draft", "impact", "approved", "applied")
#: What a scratch copy for a trial leaves out (the build, the history).
_NOT_COPIED = frozenset({"build", ".git", ".worktrees", "__pycache__"})
BEFORE_LABEL = "Before upgrading the format"
UPGRADED_LABEL = f"Upgraded the file format to {TO_VERSION}"


def carried_approval_label(ecr_id: str) -> str:
    """The upgrade's checkpoint for an applied request it carries over as approved."""
    return f"{UPGRADED_LABEL}: approved {ecr_id} carried over"


CARRIED_LABEL = "carried over from the old format"


class UpgradeRefused(N2FError):
    """A change request could not be carried over; nothing was changed."""

    exit_code = 3


@dataclass
class _Folder:
    """A folder whose files are not readable as a product yet; editing needs only its paths."""

    paths: Paths


@dataclass
class _Old:
    """One change request file as schema 1 wrote it.

    ``status``, ``patch`` and ``edits`` are read once, up front: the steps below rewrite
    ``data`` in place, and the report must still say what the request was.
    """

    id: str
    path: Path
    data: Any
    status: str
    patch: str | None
    edits: list[Edit]

    @property
    def title(self) -> str:
        return str(self.data.get("title", self.id))

    @property
    def name(self) -> str:
        return f"{self.id} ({self.title})"

    @property
    def number(self) -> int:
        m = re.search(r"\d+", self.id)
        return int(m.group()) if m else 0


def _edits_of(path: Path, data: Any) -> list[Edit]:
    try:
        return [
            Edit.model_validate({"set": str(e["set"]), "to": e["to"]})
            for e in (data.get("edits") or [])
        ]
    except (ValueError, KeyError, TypeError) as exc:
        raise UpgradeRefused(
            f"the files could not be brought up to date and nothing was changed: the edits of "
            f"{path.name} are not readable ({exc}). Fix them, or set that change request aside "
            "by hand (status: rejected), then run `n2f init .` again"
        ) from exc


def _read_all(root: Path) -> list[_Old]:
    found: list[_Old] = []
    for path in sorted((root / "changes").glob("ECR-*.yaml")):
        data = load_roundtrip(path)
        if isinstance(data, dict):
            patch = data.get("patch")
            status = str(data.get("status", "draft"))
            found.append(
                _Old(
                    path.stem,
                    path,
                    data,
                    status,
                    str(patch) if patch else None,
                    _edits_of(path, data) if status in _UNFINISHED else [],
                )
            )
    return sorted(found, key=lambda o: o.number)


def _copy_without_build(root: Path, dest: Path) -> None:
    shutil.copytree(root, dest, ignore=lambda d, names: [n for n in names if n in _NOT_COPIED])


def check_change_requests(root: Path) -> None:
    """Refuse, touching nothing, when the open request's edits or patch no longer fit."""
    unfinished = [o for o in _read_all(Path(root)) if o.status in _UNFINISHED]
    if unfinished and unfinished[0].status != "applied":
        _preflight(Path(root), unfinished[0])


def _preflight(root: Path, old: _Old) -> None:
    """Try the open request's edits and patch on a scratch copy; refuse before changing anything."""
    edits = old.edits
    if not edits and not old.patch:
        return
    patch_file = (root / old.patch) if old.patch else None
    where = f"{old.name}, {old.path.relative_to(root).as_posix()}"
    if patch_file is not None and not patch_file.is_file():
        raise UpgradeRefused(
            f"the files could not be brought up to date and nothing was changed: the patch "
            f"{old.patch} of {where} is not there. Put it back, or set that change request "
            "aside by hand (status: rejected), then run `n2f init .` again"
        )
    with tempfile.TemporaryDirectory(prefix="n2f-upgrade-") as tmp:
        copy = Path(tmp) / "copy"
        _copy_without_build(root, copy)
        try:
            for e in edits:
                _set_in_yaml(_Folder(Paths(copy)), e)
        except N2FError as exc:
            raise UpgradeRefused(
                f"the files could not be brought up to date and nothing was changed: the edit "
                f"of {where} no longer fits the model ({exc}). Fix the edit, or set that change "
                "request aside by hand (status: rejected), then run `n2f init .` again"
            ) from exc
        if patch_file is not None:
            tracker = Vcs(copy)
            tracker.init()
            try:
                tracker.apply_patch(patch_file.resolve())
            except VcsError as exc:
                raise UpgradeRefused(
                    f"the files could not be brought up to date and nothing was changed: the "
                    f"patch {old.patch} of {where} no longer fits the model (it was written "
                    "against an earlier state). Re-make the patch, or set that change request "
                    "aside by hand (status: rejected), then run `n2f init .` again"
                ) from exc


def _save_before(vcs: Vcs) -> str:
    """The folder as it is, saved ("Before upgrading the format"); its checkpoint id."""
    vcs.init()
    if not vcs.is_clean() or vcs.head() is None:
        cps.record(vcs, BEFORE_LABEL, Vitals())
    head = vcs.head()
    assert head is not None
    return head


def _set_aside(old: _Old) -> str:
    """Make ``old`` aborted, its edit kept; returns the report line."""
    again = "start it again with `n2f ecr start`"
    if old.status == "applied":
        kept = "Its edit is already part of the model (it was applied but never closed)."
        shown = "its edit is already part of the model, so there is nothing to start again"
    elif old.patch:
        kept = f"Its edit is kept in {old.patch}; {again}."
        shown = f"its patch stays in {old.patch}; {again}"
    elif old.edits:
        kept = f"Its edit is kept in the edits listed above; {again}."
        shown = f"its edits stay in its file; {again}"
    else:
        kept = f"Its tasks are kept in the list above; {again}."
        shown = f"its tasks stay in its file; {again}"
    reason = f"set aside when upgrading: one change request is open at a time. {kept}"
    data = old.data
    data["status"] = "aborted"
    data["aborted_reason"] = reason
    for key in ("patch", "impact", "approval", "applied"):
        data.pop(key, None)
    if "released_in" in data and data["released_in"] is None:
        data.pop("released_in")
    dump_roundtrip(old.path, data)
    return f"{old.name}: set aside, because one change request is open at a time; {shown}."


def _baseline_before_apply(vcs: Vcs, old: _Old) -> tuple[str | None, Vitals]:
    """The saved state just before an applied request was applied, with its vitals, or None."""
    applied = old.data.get("applied") or {}
    snap = str(applied.get("snapshot") or "")
    if not snap or not vcs.ref_exists(snap):
        return None, Vitals()
    parent = f"{snap}~1"
    if not vcs.ref_exists(parent):
        return None, Vitals()
    infos = vcs.snapshots(parent, limit=1)
    if not infos:
        return None, Vitals()
    ident = infos[0].id
    vitals = next((c.vitals for c in cps.read(vcs) if c.id == ident), Vitals())
    return ident, vitals


def _live_payload(old: _Old, status: str) -> Any:
    """The request's file content for the live format: the old fields, those gone removed."""
    data = old.data
    data["status"] = status
    for key in ("patch", "impact", "applied"):
        data.pop(key, None)
    if status == "draft":
        data.pop("approval", None)
    for key in ("approval", "released_in"):
        if key in data and data[key] is None:
            data.pop(key)
    return data


def _carry(root: Path, old: _Old) -> list[str]:
    """Apply the request's edits, then its patch, to the model files; the report lines."""
    lines: list[str] = []
    folder = _Folder(Paths(root))
    for e in old.edits:
        lines.append(_set_in_yaml(folder, e))
    if old.patch:
        Vcs(root).apply_patch((root / old.patch).resolve())
        lines.append(f"applied {old.patch}")
    return lines


def _carry_words(old: _Old, carried: list[str]) -> str:
    if not carried:
        return "it carries no edit to apply"
    if old.patch and not old.edits:
        what = "its patch was"
    elif len(old.edits) == 1 and not old.patch:
        what = "its edit was"
    else:
        what = "its edits were"
    return f"{what} applied to the model files ({'; '.join(carried)})"


def upgrade_change_requests(root: Path) -> list[str]:
    """Carry every change request of a schema 1 folder into schema 2; one report line each.

    The folder is saved first. Returns the plain-words lines ``n2f init .`` prints, and leaves
    the new ``schema:`` to the caller.

    Raises:
        UpgradeRefused: an open request's edit or patch no longer fits; nothing was changed.
    """
    root = Path(root)
    olds = _read_all(root)
    unfinished = [o for o in olds if o.status in _UNFINISHED]
    history = [o for o in olds if o.status not in _UNFINISHED]
    if not unfinished:
        return [f"{len(history)} finished change request(s) kept as they were"] if history else []
    live, aside = unfinished[0], unfinished[1:]
    if live.status != "applied":
        _preflight(root, live)
    vcs = Vcs(root)
    before = _save_before(vcs)
    lines: list[str] = []
    try:
        lines += _mutate(root, vcs, live, aside, before)
    except Exception:
        vcs.restore(before)  # the folder as it was; the checkpoints made so far stay in the log
        vcs.delete_ref(f"ecr/{live.id}/baseline")
        raise
    if history:
        lines.append(f"{len(history)} finished change request(s) kept as they were")
    number = vcs.snapshot_count(before)
    lines.append(
        f"to go back to how everything was before upgrading: `n2f ecr abort {live.id}`, "
        f"then `n2f rollback #{number}`"
    )
    return lines


def _mutate(root: Path, vcs: Vcs, live: _Old, aside: list[_Old], before: str) -> list[str]:
    """The upgrade proper (the folder is saved and the request fits)."""
    lines = [_set_aside(o) for o in aside]
    live.path.unlink()  # the request's own file is written once its baseline exists
    write_schema(root, TO_VERSION)
    if live.status == "applied":
        return _applied(root, vcs, live, before) + lines
    upgraded = checkpoint(root, UPGRADED_LABEL)
    live_data = _live_payload(live, "draft")
    live_data["baseline"] = {
        "checkpoint": upgraded.id,
        **{k: v for k, v in (("mass", upgraded.vitals.mass), ("cost", upgraded.vitals.cost)) if v},
    }
    dump_roundtrip(live.path, live_data)
    vcs.set_ref(f"ecr/{live.id}/baseline", upgraded.id)
    checkpoint(root, f"Started {live.id}: {live.title}")
    carried = _carry(root, live)
    checkpoint(root, f"{live.id}: {CARRIED_LABEL}")
    load_product(root)  # the carried-over model must load, or the whole upgrade is undone
    first = (
        f"{live.name}: stays open; {_carry_words(live, carried)}. "
        f"Look at its impact with `n2f ecr impact {live.id}`."
    )
    if live.status == "approved":
        first += (
            " Its approval was cleared: approve it again after reviewing the impact "
            f"(`n2f ecr approve {live.id} --by <name>`)."
        )
    return [first, *lines]


def _applied(root: Path, vcs: Vcs, live: _Old, before: str) -> list[str]:
    """An applied but not closed request becomes approved for the model as it is."""
    base, vitals = _baseline_before_apply(vcs, live)
    where = "the state before it was applied"
    if base is None:
        base = before
        vitals = next((c.vitals for c in cps.read(vcs) if c.id == before), Vitals())
        where = "the last saved state before upgrading"
    data = _live_payload(live, "approved")
    old_approval = dict(live.data.get("approval") or {})
    data["approval"] = {
        "by": str(old_approval.get("by", "the upgrade")),
        "at": old_approval.get("at") or dt.datetime.now().isoformat(timespec="seconds"),
        **({"note": old_approval["note"]} if old_approval.get("note") else {}),
        "model_hash": vcs.working_hash(exclude=APPROVAL_HASH_EXCLUDE),
    }
    data["baseline"] = {
        "checkpoint": base,
        **{k: v for k, v in (("mass", vitals.mass), ("cost", vitals.cost)) if v},
    }
    dump_roundtrip(live.path, data)
    vcs.set_ref(f"ecr/{live.id}/baseline", base)
    # `ecr close` compares the model with this checkpoint, as with an "Approved <id>" one (S-273)
    checkpoint(root, carried_approval_label(live.id))
    load_product(root)
    return [
        f"{live.name}: was applied but not closed; it is open again and approved for the model "
        f"as it is now, started from {where}. Close it with `n2f ecr close {live.id}`."
    ]
