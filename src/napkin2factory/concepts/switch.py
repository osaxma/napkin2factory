"""``n2f concept switch``: move the chosen direction to another card (v0.8 R10, S-264).

In this order, all or nothing (a refusal before step 2 writes nothing; a failure after it
puts the folder back to the saved state taken there and the parked marker as it was):

1. refusals: no saved history, a released Revision, an open change request, no recorded
   promotion, the card already chosen, a tracked folder ``concepts/direction.py`` does not
   name, a parked card whose marker this copy lacks (without ``fresh``);
2. unsaved edits are saved as their own checkpoint (R4);
3. the current card is parked: marker ``parked/<id>`` set to the saved state, its card marked
   ``parked`` with the figures measured there;
4. the target comes in: a parked card with its marker has its direction files put back (by
   file) and a decision recorded; any other card (or ``fresh``) is promoted as it is;
5. the model is validated; 6. a checkpoint ``Switched to …`` is recorded.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from napkin2factory.concepts.direction import direction_paths, unnamed_entries
from napkin2factory.concepts.promote.common import (
    _append_items,
    _list_indent,
    _next_id,
    _yaml_block,
)
from napkin2factory.core import checkpoints as cps
from napkin2factory.core import concepts as cm
from napkin2factory.core.concept_lint import recorded_promotion
from napkin2factory.core.errors import GateBlocked, N2FError
from napkin2factory.core.model.concepts import ConceptCard
from napkin2factory.core.vcs import FileChange, Vcs
from napkin2factory.ecr.checkpointing import (
    checkpoint,
    open_change_request,
    save_edits_first,
    stale_after_restore,
)

NO_HISTORY = (
    "this folder has no saved history to switch from (it was copied without it, or change "
    "tracking was never set up): the steps before this copy are not in it; "
    "`n2f init .` starts saving from now"
)
REQUIREMENTS = "model/requirements.yaml"
DECISIONS = "model/decisions.yaml"


@dataclass
class SwitchResult:
    """What a switch did, for the words and ``--json``."""

    card_id: str
    title: str
    parked_id: str
    parked_title: str
    dec_id: str
    route: str  # restored | seeded
    checkpoint: str = ""
    number: int = 0
    saved_edits: int | None = None
    changes: list[FileChange] = field(default_factory=list)
    seeded_parameters: int = 0
    seeded_requirements: int = 0
    notes: list[str] = field(default_factory=list)
    #: what the card's screening fails, in plain words ("Sag stays within the limit: …")
    failing: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)


def failing_words(card: ConceptCard) -> list[str]:
    """The card's failing screening checks as ``n2f concept show`` prints them (S-277)."""
    if card.screening is None:
        return []
    out = []
    for row in card.screening.failing:
        name = (row.title or row.id).rstrip(".")
        out.append(f"{name}: {row.message}" if row.message else name)
    return out


def marker_name(card_id: str) -> str:
    """The parked marker of a card (relative name under the store's markers)."""
    return f"parked/{card_id}"


def _figures(mass: str | None, cost: str | None) -> str:
    parts = [x for x in (f"{mass}" if mass else None, f"{cost}" if cost else None) if x]
    return ", ".join(parts) if parts else "not measured"


def _dec_ids(root: Path) -> list[str]:
    data = yaml.safe_load((root / DECISIONS).read_text(encoding="utf-8")) or {}
    return [str(d.get("id")) for d in data.get("decisions", []) if isinstance(d, dict)]


def _preflight(root: Path, vcs: Vcs, card: ConceptCard, fresh: bool) -> ConceptCard:
    """Every refusal that needs nothing written; returns the current direction's card."""
    if not (vcs.is_tracked() and vcs.is_repo_root()) or vcs.snapshot_count() == 0:
        raise GateBlocked(NO_HISTORY)
    if vcs.tags():
        raise GateBlocked(
            "a Revision has been released, so a change of direction is a design change request: "
            '`n2f ecr start --kind design --title "…"`'
        )
    found = open_change_request(root)
    if found:
        raise GateBlocked(
            f"the change request {found[0]} is still open: finish it, or leave it with "
            f"`n2f ecr abort {found[0]}`, then switch"
        )
    current = [c for c in cm.load_concepts(root).values() if recorded_promotion(c, root)]
    if not current:
        raise GateBlocked(
            "no direction has been chosen yet, so there is nothing to switch from: "
            f"`n2f concept promote {card.id}`"
        )
    if card.id == current[0].id:
        raise GateBlocked(f"{card.id} is already the chosen direction")
    # the saved and the unsaved files together: a new unsaved folder is checked too (S-277)
    unnamed = unnamed_entries(sorted({*vcs.files(), *vcs.unsaved_files()}))
    if unnamed:
        raise GateBlocked(
            f"the product has {', '.join(unnamed)}, which the switch does not know to belong to "
            "the design direction or to the product, so nothing was changed. Ask whoever "
            "maintains napkin2factory to name it."
        )
    if card.status == "parked" and not fresh and vcs.read_ref(marker_name(card.id)) is None:
        raise GateBlocked(
            f"{card.id} was parked, but this folder does not hold its saved direction "
            "(it was copied without it). Run `n2f concept switch "
            f"{card.id} --fresh` to start from its sketch instead."
        )
    return current[0]


def switch(
    root: Path,
    card_id: str,
    *,
    fresh: bool = False,
    override: bool = False,
    reason: str | None = None,
    by: str | None = None,
    now: dt.datetime | None = None,
) -> SwitchResult:
    """Make ``card_id`` the chosen direction and park the current one (see the module docstring).

    Raises:
        GateBlocked: a refusal (exit 3); nothing was written.
        N2FError: the result would not validate, or a card does not load; the folder is
            back as it was.
    """
    from napkin2factory.concepts.promote import promote
    from napkin2factory.core.loader import load_product, validate
    from napkin2factory.core.vitals import current_vitals, recorded_vitals

    root = Path(root)
    stamp = (now or dt.datetime.now()).replace(microsecond=0)
    at = stamp.isoformat()
    vcs = Vcs(root)
    target = cm.load_card(root, card_id)
    current = _preflight(root, vcs, target, fresh)
    assert current.decision is not None and current.decision.dec is not None
    old_dec = current.decision.dec
    marker = vcs.read_ref(marker_name(target.id))
    restoring = target.status == "parked" and marker is not None and not fresh
    reason = (reason or "").strip() or None
    if not restoring:  # promotion's own gates, asked before anything is saved or written
        if override and not reason:
            raise GateBlocked('--override needs --reason "…": the reason is recorded as a decision')
        if target.screening is None or target.verdict is None:
            raise GateBlocked(
                f"{target.id} has no screening yet: build it first (`n2f concept build "
                f"{target.id}`), then switch"
            )
        if target.verdict == "red" and not override:
            found = failing_words(target)
            raise GateBlocked(
                f"{target.id} has problems the screening found"
                + (f": {'; '.join(found)}" if found else "")
                + ". Switch anyway with --override "
                '--reason "…"; the reason is recorded as a decision.'
            )
    # 2. unsaved edits are their own step (R4)
    saved = save_edits_first(root)
    start = cps.read(vcs, limit=1)[0]
    loaded = None
    try:
        loaded = load_product(root)
    except Exception:  # an unloadable model has no figures; validation reports it below
        loaded = None
    vitals = (current_vitals(loaded) if loaded is not None else cps.Vitals()) or start.vitals
    dec_id = _next_id("DEC", _dec_ids(root))
    old_marker = vcs.read_ref(marker_name(current.id))
    result = SwitchResult(
        card_id=target.id,
        title=target.title,
        parked_id=current.id,
        parked_title=current.title,
        dec_id=dec_id,
        route="restored" if restoring else "seeded",
        saved_edits=saved.number if saved else None,
    )
    try:
        # 3. park the current direction
        vcs.set_ref(marker_name(current.id), start.id)
        built: dict[str, Any] = {"event": "parked", "checkpoint": start.id, "number": start.number}
        if vitals.mass:
            built["mass"] = vitals.mass
        if vitals.cost:
            built["cost"] = vitals.cost
        built["at"] = at
        cm.update_card_status(
            root,
            current.id,
            "parked",
            {"reason": f"parked when {target.id} was chosen ({dec_id})", "at": at},
            built=built,
        )
        # 4. bring the target
        if restoring:
            assert marker is not None
            _restore(root, vcs, target, current, marker, old_dec, dec_id, by, stamp, result)
            cm.update_card_status(
                root, target.id, "promoted", {"dec": dec_id, "at": at}, clear_built=True
            )
            # 5. validate the result as a whole
            product, problems = validate(root)
            if product is None or problems.errors:
                first = problems.errors[0] if problems.errors else None
                what = f" ({first.subject}: {first.message})" if first else ""
                raise N2FError(
                    f"{target.id} does not fit the product as it stands now{what}, so nothing "
                    "was switched"
                )
        else:
            done = promote(
                root,
                target.id,
                override,
                reason,
                by,
                now=stamp,
                snapshot=False,
                supersedes=old_dec,
            )
            if done.dec_id != dec_id:  # never expected: keep the parked card's words true
                cm.update_card_status(
                    root,
                    current.id,
                    "parked",
                    {"reason": f"parked when {target.id} was chosen ({done.dec_id})", "at": at},
                )
            result.dec_id = done.dec_id
            result.seeded_parameters = len([p for p in done.params if p.status != "declared"])
            result.seeded_requirements = len(done.requirements)
            result.notes += done.notes
            result.notes.append(
                f"{current.id}'s parts stay in the model until you change them; "
                f"{target.id} brought only its sketch"
            )
            result.failing = failing_words(target)
            if result.failing:
                result.notes.append(
                    f"the model's parts are still {current.id}'s, so a check judges those "
                    f"until the design changes"
                )
            cm.update_card_status(
                root, target.id, "promoted", {"dec": done.dec_id, "at": at}, clear_built=True
            )
    except BaseException:
        vcs.restore(start.id)
        if old_marker is None:
            vcs.delete_ref(marker_name(current.id))
        else:
            vcs.set_ref(marker_name(current.id), old_marker)
        raise
    # 6. one checkpoint, then what the restore left stale
    cp = checkpoint(
        root,
        f"Switched to {target.id} ({target.title}); {current.id} parked",
        vitals=recorded_vitals(root, marker if restoring else None)
        or (
            cps.Vitals(target.built.mass, target.built.cost) if restoring and target.built else None
        ),
    )
    result.checkpoint, result.number = cp.id, cp.number
    result.stale = stale_after_restore(root)
    if restoring:
        assert marker is not None
        old = vcs.read_file(marker, REQUIREMENTS)
        now_text = (root / REQUIREMENTS).read_bytes() if (root / REQUIREMENTS).is_file() else None
        if old != now_text:
            result.stale.append(
                f"the requirements changed since {target.id} was parked; the next build "
                "checks it against them"
            )
    return result


def _restore(
    root: Path,
    vcs: Vcs,
    target: ConceptCard,
    current: ConceptCard,
    marker: str,
    old_dec: str,
    dec_id: str,
    by: str | None,
    stamp: dt.datetime,
    result: SwitchResult,
) -> None:
    """Put the target's direction files back from its marker and record the decision."""
    result.changes = vcs.restore(marker, paths=direction_paths())
    b = target.built
    figures = _figures(b.mass, b.cost) if b else "not measured"
    where = f" at checkpoint #{b.number}" if b and b.number else ""
    entry = {
        "id": dec_id,
        "date": stamp.date(),
        "title": f"Design direction back to {target.title}",
        "context": (
            f'{target.id} "{target.title}" was parked{where} ({figures}) when {current.id} '
            f"was chosen ({old_dec}). The design direction is switched back to it"
            + (f" by {by}" if by else "")
            + "."
        ),
        "decision": (
            f"Take {target.id} ({target.title}) back as the design direction: its parts, "
            "parameters, interfaces, calculations and style come back as they were when it "
            f"was parked. This supersedes {old_dec}."
        ),
        "rationale": (
            f"The direction files are the parked ones, unchanged; the requirements, decisions "
            f"and cards stayed as they are now. {current.id} ({current.title}) is parked and "
            "can be chosen again."
        ),
        "links": [f"dec://{old_dec}"],
        "made_by": "human" if by else "agent",
        "disclosed": True,
        "verify": False,
        "sources": [f"concepts/{target.id}.yaml", f"concepts/{current.id}.yaml"],
    }
    path = root / DECISIONS
    text = path.read_text(encoding="utf-8")
    text = _append_items(text, "decisions", [_yaml_block(entry, _list_indent(text, "decisions"))])
    path.write_text(text, encoding="utf-8")


__all__ = ["SwitchResult", "marker_name", "switch"]
