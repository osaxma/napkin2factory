"""The checkpoint calls every state-changing command shares (v0.8 R4, R5; S-253).

A command that changes the design follows one pattern:

1. :func:`save_edits_first` before it changes anything, so the owner's loose edits are a
   checkpoint of their own and never folded into the command's step;
2. its change;
3. :func:`checkpoint` with a plain label ("Promoted C-002 (Steel frame)"), which replaces the
   command's old snapshot.

After a restore (``undo``, ``redo``, ``rollback``, a change request's ``abort``),
:func:`stale_after_restore` lists what the restored state no longer matches, and never revives
it (R5). :func:`open_change_request` tells ``undo`` where it must stop (R5) and ``rollback``
that it must refuse.
"""

from __future__ import annotations

from pathlib import Path

from napkin2factory.core import checkpoints as cps
from napkin2factory.core.checkpoints import Checkpoint, Vitals
from napkin2factory.core.loader import Product, load_product
from napkin2factory.core.vcs import Vcs

#: What an approval hash leaves out: the requests' own records (S-252) and sign-offs, which are
#: checked at close, not approved (S-254 widens S-252); impact, approve, close and the
#: staleness report all use it.
APPROVAL_HASH_EXCLUDE = ("changes/", "model/signoffs/")
#: The states in which a change request is still open: edits count towards it (R5, R6).
OPEN_STATUSES = ("draft", "approved")


def _product(product: Product | Path) -> Product | None:
    """The loaded product; None when the model does not load (its vitals are then unknown)."""
    if isinstance(product, Product):
        return product
    try:
        return load_product(Path(product))
    except Exception:  # an unloadable model is the command's to report, not the checkpoint's
        return None


def _root(product: Product | Path) -> Path:
    return product.root if isinstance(product, Product) else Path(product)


def checkpoint(
    product: Product | Path,
    label: str,
    *,
    restores: str | None = None,
    undoes: str | None = None,
    redoes: str | None = None,
    vitals: Vitals | None = None,
) -> Checkpoint:
    """Save everything as a checkpoint with ``label`` and the product's current vitals.

    The vitals come from a fresh build only (``core/vitals.py``); pass ``vitals`` to copy
    them from the checkpoint a restore brings back (the folder then equals that state). The
    trailers ``restores`` / ``undoes`` / ``redoes`` make a restore (always recorded). With
    nothing changed and no trailer, no checkpoint is made and the newest is returned. The
    folder must be a tracked product root: callers keep their own guard.
    """
    from napkin2factory.core.vitals import current_vitals

    if vitals is None:
        loaded = _product(product)
        vitals = current_vitals(loaded) if loaded is not None else Vitals()
    vcs = Vcs(_root(product))
    return cps.record(vcs, label, vitals, restores=restores, undoes=undoes, redoes=redoes)


def save_edits_first(product: Product | Path) -> Checkpoint | None:
    """Save unsaved edits as their own checkpoint ("edits since #12 Promoted C-002").

    None when there is nothing unsaved, or when the folder is not a tracked product root
    (those commands never saved anything). Call it before the command changes anything.
    """
    vcs = Vcs(_root(product))
    if not (vcs.is_tracked() and vcs.is_repo_root()) or vcs.is_clean():
        return None
    newest = vcs.snapshots(limit=1)
    if not newest:  # a folder with no history yet: the first save is the command's own
        return None
    from napkin2factory.core.vitals import current_vitals

    loaded = _product(product)
    vitals = current_vitals(loaded) if loaded is not None else Vitals()
    label = f"edits since #{vcs.snapshot_count()} {newest[0].label}"
    return cps.record(vcs, label, vitals)


def open_change_request(product: Product | Path) -> tuple[str, str] | None:
    """``(change request id, its start checkpoint id)`` for the open change request, or None.

    Open means status ``draft`` or ``approved`` with a ``baseline`` (M2b keeps at most one;
    the newest id wins). Its start checkpoint is the first checkpoint on the line right after
    ``baseline.checkpoint`` (the "Started ECR-x" step; the baseline itself when nothing
    follows it yet). ``undo`` stops there (R5) and ``rollback`` refuses while it exists.
    """
    loaded = _product(product)
    if loaded is None:
        return None
    open_ones = [
        e for e in loaded.ecrs.values() if e.status in OPEN_STATUSES and e.baseline is not None
    ]
    if not open_ones:
        return None
    ecr = max(open_ones, key=lambda e: e.id)
    assert ecr.baseline is not None
    log = cps.read(Vcs(loaded.root))
    base = next((c for c in log if c.id == ecr.baseline.checkpoint), None)
    if base is None:  # not on this line: undo reports it cannot tell where the request began
        return ecr.id, ecr.baseline.checkpoint
    after = next((c for c in log if c.number == base.number + 1), base)
    return ecr.id, after.id


def _title(text: str) -> str:
    return f" ({text})" if text else ""


def stale_after_restore(product: Product | Path) -> list[str]:
    """Plain-words lines for every sign-off and approval the folder's state no longer matches.

    * a sign-off whose evidence changed since signing (read from the checks, which rebuild
      what the restore touched; the words are the ones ``n2f check`` shows);
    * an approved change request whose recorded model hash differs from the folder's
      (``Vcs.working_hash`` without ``changes/``, S-252).

    Nothing is revived or written (R5). If the checks cannot run, one line says so.
    """
    root = _root(product)
    lines: list[str] = []
    loaded = _product(root)
    if loaded is None:
        return ["the restored model does not load; run `n2f validate` to see why"]
    if loaded.signoffs:
        lines += _stale_signoffs(loaded)
    approved = [
        e
        for e in loaded.ecrs.values()
        if e.status == "approved" and e.approval is not None and e.approval.model_hash
    ]
    if approved:
        now = Vcs(root).working_hash(exclude=APPROVAL_HASH_EXCLUDE)
        for e in sorted(approved, key=lambda e: e.id):
            assert e.approval is not None
            if e.approval.model_hash != now:
                lines.append(
                    f"the approval of {e.id}{_title(e.title)} no longer matches the model; "
                    f"look at its impact again (`n2f ecr impact {e.id}`), then approve it again"
                )
    return lines


def _stale_signoffs(product: Product) -> list[str]:
    import json

    from napkin2factory.core.graph.runner import run_build

    try:
        # No renders: a sign-off is held against what the build measured, not against pictures,
        # and a restore should not wait for them (R12).
        run_build(product, target="checks", quiet=True, render=False)
        path = product.paths.build / "checks" / "checks.json"
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # a restored model that does not build: say so, do not hide it
        return [
            "could not check the sign-offs against the restored model "
            f"({str(exc).splitlines()[0] if str(exc) else type(exc).__name__}); "
            "run `n2f check` to see which are still valid"
        ]
    lines: list[str] = []
    for row in data.get("results", []):
        so = (row.get("detail") or {}).get("signoff") or {}
        if so.get("present") and not so.get("valid"):
            rid = str(row["id"]).removeprefix("req://")
            lines.append(
                f"the sign-off for {rid}{_title(row.get('title') or '')} no longer holds: "
                f"{so.get('why', 'the evidence changed')}; sign it again with `n2f signoff {rid}`"
            )
    return lines


def approved_checkpoint(vcs: Vcs, ecr_id: str) -> cps.Checkpoint | None:
    """The newest ``Approved <id> …`` checkpoint of the history, or None."""
    from napkin2factory.ecr.upgrade import carried_approval_label

    carried = carried_approval_label(ecr_id)
    for cp in cps.read(vcs):  # newest first
        if cp.label.startswith(f"Approved {ecr_id} ") or cp.label == carried:
            return cp
    return None


def matches_approval(vcs: Vcs, ecr_id: str) -> bool:
    """Whether the model is the one in the approval's checkpoint (same files left out as the hash).

    The hash in the request file can be typed by anyone; the checkpoint cannot (S-273).
    """
    cp = approved_checkpoint(vcs, ecr_id)
    if cp is None:
        return False
    return not [c for c in vcs.diff_working(cp.id) if not c.path.startswith(APPROVAL_HASH_EXCLUDE)]
