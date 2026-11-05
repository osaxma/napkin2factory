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

from napkin2factory.core.vcs import SnapshotInfo, Vcs

KEY_MASS = "Checkpoint-Mass"
KEY_COST = "Checkpoint-Cost"
KEY_RESTORES = "Checkpoint-Restores"
KEY_UNDOES = "Checkpoint-Undoes"
KEY_REDOES = "Checkpoint-Redoes"

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Vitals:
    """What a checkpoint measured: plain strings as the owner reads them (``46.0 kg``, ``$340``).

    None means "not measured" (the build was stale or nothing was built).
    """

    mass: str | None = None
    cost: str | None = None


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
    allow_empty: bool = False,
) -> Checkpoint:
    """Save everything as a new checkpoint.

    A restore (any of ``restores``, ``undoes``, ``redoes``) is always recorded, even when
    the folder equals the last checkpoint, because the stacks are read from the log. With
    nothing changed and none of those set, no checkpoint is made and the latest one is
    returned unchanged.
    """
    forced = allow_empty or any((restores, undoes, redoes))
    message = checkpoint_message(label, vitals, restores, undoes, redoes)
    ident = vcs.snapshot(message, allow_empty=forced)
    infos = vcs.snapshots(ident, limit=1)
    return Checkpoint.from_snapshot(infos[0], vcs.snapshot_count(ident))


def save_edits(vcs: Vcs, label_fmt: str = "edits since {last}") -> Checkpoint | None:
    """Save unsaved edits as their own checkpoint; None when the folder has nothing unsaved.

    ``{last}`` in ``label_fmt`` is the label of the newest checkpoint, so ``undo`` can undo
    the edits and ``redo`` bring them back (R3).
    """
    if vcs.is_clean():
        return None
    newest = vcs.snapshots(limit=1)
    last = newest[0].label if newest else "the start"
    return record(vcs, label_fmt.format(last=last))


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
