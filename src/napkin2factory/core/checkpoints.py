"""Checkpoints: the saved states of a product, with their label and vitals (v0.8 R3, S-246).

A checkpoint is a snapshot whose message is a plain label, optionally followed by trailers
(``Key: value`` lines that only ``--json`` shows). The trailers carry the vitals (mass and
priced cost from a fresh build; absent means "not measured") and, for a restore, the state it
restored (``Restores``), the checkpoint it undid (``Undoes``) or brought back (``Redoes``).

``undo`` and ``redo`` are derived from the log alone, no pointer file (R3), by two stacks
built walking the checkpoints from the oldest:

* a checkpoint with ``Undoes: X`` moves X from ``done`` to ``redo``;
* a checkpoint with ``Redoes: X`` moves X from ``redo`` back to ``done``;
* any other checkpoint (a command's, saved edits, a rollback, an abort) is pushed on ``done``
  and empties ``redo``.

Undo restores the state of the checkpoint below the top of ``done`` and records itself as
``Undoes`` the top; redo restores the state of the top of ``redo`` and records ``Redoes``.
History only moves forward (R2): both are new checkpoints, nothing is ever rewritten.

The planning functions are pure (lists of :class:`Checkpoint` in, a plan out) so they can be
property-tested; :func:`record`, :func:`save_edits` and :func:`read` touch the store.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from napkin2factory.core.vcs import SnapshotInfo, Vcs
from napkin2factory.core.yamlio import safe_load

KEY_MASS = "Checkpoint-Mass"
KEY_COST = "Checkpoint-Cost"
KEY_RESTORES = "Checkpoint-Restores"
KEY_UNDOES = "Checkpoint-Undoes"
KEY_REDOES = "Checkpoint-Redoes"
KEY_SINCE = "Checkpoint-Since"

_WHITESPACE = re.compile(r"\s+")
_SIGNOFF_PREFIX = "Signed off "
_SIGNOFF_LABEL_RE = re.compile(
    r"^Signed off (?P<id>REQ-[A-Za-z0-9_-]+)(?::\s*(?P<title>.+?))?(?P<ex>\s+\(EXAMPLE\))?$"
)


@dataclass(frozen=True)
class Vitals:
    """What a checkpoint measured: plain strings as the owner reads them (``46.0 kg``, ``$340``).

    None means "not measured" (the build was stale or nothing was built).
    """

    mass: str | None = None
    cost: str | None = None

    def __bool__(self) -> bool:
        """True when at least one figure (mass or cost) is recorded."""
        return bool(self.mass or self.cost)


@dataclass(frozen=True)
class Checkpoint:
    """One checkpoint, read from the log.

    ``number`` counts from 1 (the oldest) along the main line, so it never changes as the
    history grows. ``restores``, ``undoes`` and ``redoes`` hold checkpoint ids.
    """

    id: str
    number: int
    label: str
    when: int
    vitals: Vitals = Vitals()
    restores: str | None = None
    undoes: str | None = None
    redoes: str | None = None
    since: str | None = None

    @classmethod
    def from_snapshot(cls, info: SnapshotInfo, number: int) -> Checkpoint:
        """A checkpoint from a snapshot; older ones without trailers have no vitals."""
        t = info.trailers
        return cls(
            id=info.id,
            number=number,
            label=info.label,
            when=info.when,
            vitals=Vitals(mass=t.get(KEY_MASS) or None, cost=t.get(KEY_COST) or None),
            restores=t.get(KEY_RESTORES) or None,
            undoes=t.get(KEY_UNDOES) or None,
            redoes=t.get(KEY_REDOES) or None,
            since=t.get(KEY_SINCE) or None,
        )


@dataclass(frozen=True)
class UndoPlan:
    """What ``undo`` does: restore ``restores``'s state, record that ``undoes`` was undone."""

    undoes: Checkpoint
    restores: Checkpoint


@dataclass(frozen=True)
class RedoPlan:
    """What ``redo`` does: restore ``redoes``'s own state, record that it came back."""

    redoes: Checkpoint

    @property
    def restores(self) -> Checkpoint:
        """The checkpoint whose state is restored (the one brought back)."""
        return self.redoes


@dataclass(frozen=True)
class Stacks:
    """The derived undo and redo stacks, oldest first (the top is the last item)."""

    done: tuple[Checkpoint, ...]
    redo: tuple[Checkpoint, ...]


# ---- the message ------------------------------------------------------------------------


def _flat(text: str) -> str:
    """One line: runs of whitespace (newlines included) become a single space."""
    return _WHITESPACE.sub(" ", text).strip()


def checkpoint_message(
    label: str,
    vitals: Vitals | None = None,
    restores: str | None = None,
    undoes: str | None = None,
    redoes: str | None = None,
    since: str | None = None,
) -> str:
    """The snapshot message: the label, a blank line, then one ``Key: value`` line per trailer.

    A multi-line label is flattened to one line (the label is a subject, never a paragraph);
    an empty label becomes ``checkpoint``. Absent trailers are not written.
    """
    lines = [
        (KEY_MASS, vitals.mass if vitals else None),
        (KEY_COST, vitals.cost if vitals else None),
        (KEY_RESTORES, restores),
        (KEY_UNDOES, undoes),
        (KEY_REDOES, redoes),
        (KEY_SINCE, since),
    ]
    trailers = [f"{key}: {_flat(value)}" for key, value in lines if value and _flat(value)]
    head = _flat(label) or "checkpoint"
    return head + ("\n\n" + "\n".join(trailers) if trailers else "")


# ---- the store --------------------------------------------------------------------------


def build(infos: Sequence[SnapshotInfo], total: int | None = None) -> list[Checkpoint]:
    """Checkpoints from snapshots listed newest first; ``total`` is how many exist in all.

    Without ``total`` the list is taken to reach back to the first snapshot.
    """
    count = len(infos) if total is None else total
    return [Checkpoint.from_snapshot(info, count - i) for i, info in enumerate(infos)]


def read(vcs: Vcs, limit: int | None = None) -> list[Checkpoint]:
    """Checkpoints, newest first. Undo and redo need the whole log: call without ``limit``."""
    infos = vcs.snapshots(limit=limit)
    total = vcs.snapshot_count() if limit is not None else len(infos)
    return build(infos, total)


def record(
    vcs: Vcs,
    label: str,
    vitals: Vitals | None = None,
    *,
    restores: str | None = None,
    undoes: str | None = None,
    redoes: str | None = None,
    since: str | None = None,
    allow_empty: bool = False,
) -> Checkpoint:
    """Save everything as a new checkpoint.

    A restore (any of ``restores``, ``undoes``, ``redoes``) is always recorded, even when
    the folder equals the last checkpoint, because the stacks are read from the log. With
    nothing changed and none of those set, no checkpoint is made and the latest one is
    returned unchanged.
    """
    forced = allow_empty or any((restores, undoes, redoes))
    message = checkpoint_message(label, vitals, restores, undoes, redoes, since)
    ident = vcs.snapshot(message, allow_empty=forced)
    infos = vcs.snapshots(ident, limit=1)
    return Checkpoint.from_snapshot(infos[0], vcs.snapshot_count(ident))


def _param_value_words(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return None
    if entry.get("value") is not None:
        unit = str(entry.get("unit") or "").strip()
        return f"{entry['value']} {unit}".strip()
    if entry.get("expr") is not None:
        return f"= {entry['expr']}"
    return None


def _load_yaml_dict(raw: bytes | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        loaded = safe_load(raw.decode("utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _read_pair(vcs: Vcs, ref: str, path: str) -> tuple[dict[str, Any], dict[str, Any]]:
    old_raw = vcs.read_file(ref, path)
    full = vcs.root / path
    new_raw = full.read_bytes() if full.is_file() else None
    return _load_yaml_dict(old_raw), _load_yaml_dict(new_raw)


def _param_edits(vcs: Vcs, ref: str) -> list[str]:
    old_doc, new_doc = _read_pair(vcs, ref, "model/parameters.yaml")
    old_p = old_doc.get("parameters")
    new_p = new_doc.get("parameters")
    old_map = old_p if isinstance(old_p, dict) else {}
    new_map = new_p if isinstance(new_p, dict) else {}
    slugs = list(new_map) + [k for k in old_map if k not in new_map]
    items: list[str] = []
    for slug in slugs:
        old_e, new_e = old_map.get(slug), new_map.get(slug)
        if old_e == new_e:
            continue
        old_w, new_w = _param_value_words(old_e), _param_value_words(new_e)
        if old_w is not None and new_w is not None and old_w != new_w:
            items.append(f"{slug} {old_w} → {new_w}")
        else:
            items.append(str(slug))
    return items


def _list_id_edits(vcs: Vcs, ref: str, path: str, key: str) -> list[str]:
    old_doc, new_doc = _read_pair(vcs, ref, path)
    old_list = old_doc.get(key)
    new_list = new_doc.get(key)
    old_map = {
        str(x["id"]): x
        for x in (old_list if isinstance(old_list, list) else [])
        if isinstance(x, dict) and x.get("id")
    }
    new_map = {
        str(x["id"]): x
        for x in (new_list if isinstance(new_list, list) else [])
        if isinstance(x, dict) and x.get("id")
    }
    ids = list(new_map) + [k for k in old_map if k not in new_map]
    return [oid for oid in ids if old_map.get(oid) != new_map.get(oid)]


_MODEL_OBJECT_DIRS = frozenset(
    {
        "parts",
        "assemblies",
        "interfaces",
        "signoffs",
        "loads",
        "electrical",
        "process",
        "controls",
        "software",
        "architecture",
        "test_plans",
    }
)


def _changed_object_id(path: str) -> str | None:
    p = Path(path)
    parts = p.parts
    if len(parts) >= 3 and parts[0] == "model":
        sub = parts[1]
        if sub in _MODEL_OBJECT_DIRS and p.suffix in {".yaml", ".yml"}:
            return p.stem
        if sub == "docs" and p.suffix == ".md":
            return p.stem
        if sub in {"calcs", "geometry", "screens", "rulepacks"} and p.suffix == ".py":
            if not p.stem.startswith(("_", "test_")):
                return p.stem
    if len(parts) == 2 and parts[0] in {"concepts", "changes"} and p.suffix in {".yaml", ".yml"}:
        return p.stem
    if path == "style.yaml":
        return "style"
    if path == "n2f.yaml":
        return "n2f.yaml"
    return None


def describe_edits(vcs: Vcs, ref: str) -> str | None:
    """Owner-words summary of what changed between ``ref`` and the working folder, or None.

    Changed parameter values read ``slug old → new``; other changed model objects name their
    id; at most three items are listed before ``and N more`` (B-0293). Returns None when
    nothing nameable changed, so callers fall back to ``edits since <last>``.
    """
    changes = vcs.diff_working(ref)
    if not changes:
        return None
    items: list[str] = []
    for ch in changes:
        if ch.path == "model/parameters.yaml":
            items.extend(_param_edits(vcs, ref))
        elif ch.path == "model/requirements.yaml":
            items.extend(_list_id_edits(vcs, ref, ch.path, "requirements"))
        elif ch.path == "model/decisions.yaml":
            items.extend(_list_id_edits(vcs, ref, ch.path, "decisions"))
        else:
            oid = _changed_object_id(ch.path)
            if oid is not None:
                items.append(oid)
    unique = list(dict.fromkeys(items))
    if not unique:
        return None
    shown = ", ".join(unique[:3])
    return f"{shown} and {len(unique) - 3} more" if len(unique) > 3 else shown


def save_edits(vcs: Vcs, label_fmt: str = "edits since {last}") -> Checkpoint | None:
    """Save unsaved edits as their own checkpoint; None when the folder has nothing unsaved.

    ``{last}`` in ``label_fmt`` is the label of the newest checkpoint, so ``undo`` can undo
    the edits and ``redo`` bring them back (R3). When nameable model values or objects
    changed, the label names them and ``Checkpoint-Since`` keeps the ``edits since …`` text
    recoverable (B-0293).
    """
    if vcs.is_clean():
        return None
    newest = vcs.snapshots(limit=1)
    last = newest[0].label if newest else "the start"
    fallback = label_fmt.format(last=last)
    described = (
        describe_edits(vcs, newest[0].id) if newest and label_fmt == "edits since {last}" else None
    )
    return record(vcs, described or fallback, since=fallback if described else None)


def is_signoff(cp: Checkpoint) -> bool:
    """True when ``cp`` is a requirement sign-off checkpoint (not a restore of one)."""
    return (
        cp.restores is None
        and cp.undoes is None
        and cp.redoes is None
        and cp.label.startswith(_SIGNOFF_PREFIX)
    )


def signoff_first_title(cp: Checkpoint) -> str:
    """The requirement title (or id when untitled) from a sign-off checkpoint's label."""
    m = _SIGNOFF_LABEL_RE.match(cp.label)
    if m:
        return (m.group("title") or m.group("id")).strip()
    return cp.label.removeprefix(_SIGNOFF_PREFIX).strip()


def fold_signoffs(
    checkpoints: Sequence[Checkpoint], undone: set[str] | frozenset[str] = frozenset()
) -> list[list[Checkpoint]]:
    """Group consecutive sign-off checkpoints (sharing ``undone`` state) into single rows."""
    groups: list[list[Checkpoint]] = []
    for cp in checkpoints:
        if (
            groups
            and is_signoff(cp)
            and is_signoff(groups[-1][-1])
            and (cp.id in undone) == (groups[-1][-1].id in undone)
        ):
            groups[-1].append(cp)
        else:
            groups.append([cp])
    return groups


# ---- undo and redo, derived from the log --------------------------------------------------


def stacks(checkpoints: Sequence[Checkpoint]) -> Stacks:
    """The ``done`` and ``redo`` stacks the log implies (input order does not matter)."""
    done: list[Checkpoint] = []
    redo: list[Checkpoint] = []
    for cp in sorted(checkpoints, key=lambda c: c.number):
        if cp.undoes is not None:
            for i in range(len(done) - 1, -1, -1):
                if done[i].id == cp.undoes:
                    redo.append(done.pop(i))
                    break
        elif cp.redoes is not None:
            for i in range(len(redo) - 1, -1, -1):
                if redo[i].id == cp.redoes:
                    done.append(redo.pop(i))
                    break
        else:
            done.append(cp)
            redo.clear()
    return Stacks(tuple(done), tuple(redo))


def undo_plan(checkpoints: Sequence[Checkpoint], stop_at: str | None = None) -> UndoPlan | None:
    """Undo the newest checkpoint still standing, by restoring the one before it.

    None when nothing is left to undo (the first checkpoint cannot be undone) or when the
    undo would go past ``stop_at``, the id of a draft change request's baseline: the
    baseline itself stays and cannot be undone (R5). The caller saves unsaved edits first
    (:func:`save_edits`) so they are part of what can be undone. Raises ``ValueError`` when
    ``stop_at`` is not a known checkpoint.
    """
    done = stacks(checkpoints).done
    if len(done) < 2:
        return None
    top, below = done[-1], done[-2]
    if stop_at is not None:
        baseline = next((c for c in checkpoints if c.id == stop_at), None)
        if baseline is None:
            raise ValueError(f"unknown checkpoint {stop_at!r}")
        if top.number <= baseline.number:
            return None
    return UndoPlan(undoes=top, restores=below)


def redo_plan(checkpoints: Sequence[Checkpoint]) -> RedoPlan | None:
    """Bring back the checkpoint undone last, by restoring its own state; None if none."""
    redo = stacks(checkpoints).redo
    return RedoPlan(redoes=redo[-1]) if redo else None
