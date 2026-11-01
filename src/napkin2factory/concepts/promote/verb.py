"""``promote``: the gates, every seeder in order, one validated write, the snapshot."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import yaml

from napkin2factory.concepts.promote.common import (
    NewRequirement,
    _and,
    _append_items,
    _count,
    _list_indent,
    _next_id,
    _rel,
    _yaml_block,
)
from napkin2factory.concepts.promote.decision import _card_text, _labelled, _one_line
from napkin2factory.concepts.promote.form import form_requirements
from napkin2factory.concepts.promote.modules import plan_modules
from napkin2factory.concepts.promote.parameters import plan_parameters
from napkin2factory.concepts.promote.result import PromotionResult
from napkin2factory.concepts.promote.site import site_requirements
from napkin2factory.concepts.promote.style import plan_style
from napkin2factory.concepts.screens import SPACE_WORDS
from napkin2factory.core import concepts as cm
from napkin2factory.core.errors import GateBlocked, N2FError
from napkin2factory.core.model.concepts import ConceptCard
from napkin2factory.core.packs import product_words


def _refuse_red(card: ConceptCard) -> GateBlocked:
    assert card.screening is not None
    reasons = "; ".join(r.message for r in card.screening.failing) or "screening is red"
    return GateBlocked(
        f"{card.id} — this direction has problems: {reasons}. Promote anyway with --override "
        '--reason "…"; the reason is recorded as a decision.'
    )


def _top_assembly(product: Any, notes: list[str]) -> str | None:
    from napkin2factory.bom.rollups import top_assemblies

    tops = top_assemblies(product)
    if len(tops) > 1:
        notes.append(f"more than one top assembly ({', '.join(tops)}): allocated to {tops[0]}")
    return tops[0] if tops else None


def promote(
    root: Path,
    card_id: str,
    override: bool = False,
    reason: str | None = None,
    by: str | None = None,
    *,
    now: dt.datetime | None = None,
    snapshot: bool = True,
) -> PromotionResult:
    """Promote one concept card into the product model (see the module docstring).

    Args:
        root: the product folder.
        card_id: the card (``C-003``, ``3``…).
        override: promote a red card, or overwrite parameters that differ (needs ``reason``).
        reason: why (recorded in the decision's context).
        by: the person who chose (``made_by: human``); without it the agent made the call.
        now: the timestamp to record (default: now, to the second).
        snapshot: take the ``Promote C-00x`` snapshot (when the folder is a project root).

    Raises:
        GateBlocked: a gate refused (exit 3); nothing was written.
        N2FError: the model or a card does not load, or the edits would not validate.
    """
    from napkin2factory.core.loader import validate

    root = Path(root)
    stamp = (now or dt.datetime.now()).replace(microsecond=0)
    card = cm.load_card(root, card_id)
    cid = card.id
    cards = cm.load_concepts(root)
    # 1. gates
    if card.screening is None or card.verdict is None:
        raise GateBlocked(
            f"{cid} has no screening yet — build it first: `n2f concept build {cid}`, "
            "look at it on the board, then promote"
        )
    # only a promotion on record counts; a `promoted` typed by hand is redone properly (B2)
    if cm.recorded_promotion(card, root):
        raise GateBlocked(f"{cid} is already the chosen direction")
    chosen = [c for c in cards.values() if cm.recorded_promotion(c, root) and c.id != cid]
    if chosen:
        raise GateBlocked(
            f"{chosen[0].id} is already the chosen direction — changing direction after "
            "promotion is a change request: `n2f ecr new --kind design --title …`"
        )
    reason = (reason or "").strip() or None
    if override and not reason:
        raise GateBlocked('--override needs --reason "…": the reason is recorded as a decision')
    if card.verdict == "red" and not override:
        raise _refuse_red(card)
    product, problems = validate(root)
    if product is None or problems.errors:
        first = problems.errors[0] if problems.errors else None
        what = f" ({first.subject}: {first.message})" if first else ""
        raise N2FError(
            f"the product model has problems{what}, so nothing was promoted — "
            "fix them first (`n2f validate`)"
        )
    paths = product.paths
    notes: list[str] = []
    dec_id = _next_id("DEC", list(product.decisions))
    # 2. parameters
    params_text = paths.parameters.read_text(encoding="utf-8")
    seeded, params_text, conflicts = plan_parameters(card, product, params_text, override, notes)
    if conflicts:
        hint = (
            'promote with --override --reason "…" to overwrite them (listed in the decision)'
            if not override
            else "change them by hand"
        )
        raise GateBlocked(
            f"{cid} would change parameters already in the model: {'; '.join(conflicts)}. "
            f"Nothing was written — make them agree, or {hint}."
        )
    # 5. style (before the form requirements: they read the merged style)
    style_text, style, style_created = plan_style(card, root, notes)
    # 3b. modules (P10): the structure and its budgets, or only a suggestion
    modules = plan_modules(card, product, notes)
    # 3 + 4. requirements: at the seeded top assembly when there was none before
    top = _top_assembly(product, notes) or modules.top
    planned = (
        site_requirements(card, seeded, top, notes, root)
        + form_requirements(card, style, top, notes)
        + modules.budgets
    )
    req_ids: list[str] = []
    existing_reqs = list(product.requirements)
    new_reqs: list[NewRequirement] = []
    req_text = paths.requirements.read_text(encoding="utf-8")
    indent = _list_indent(req_text, "requirements")
    blocks = []
    for about, data in planned:
        rid = _next_id("REQ", existing_reqs + req_ids)
        req_ids.append(rid)
        entry = {
            "id": rid,
            "title": data["title"],
            "statement": data["statement"],
            "category": data["category"],
            "priority": data.get("priority", "must"),
            "verify": data["verify"],
            "allocation": data["allocation"],
            "rationale": data["rationale"],
            "source": data["source"],
        }
        blocks.append(_yaml_block(entry, indent))
        new_reqs.append(NewRequirement(rid, data["title"], about, entry))
    req_text = _append_items(req_text, "requirements", blocks)
    # 6. the decision
    siblings = [c for c in cards.values() if c.id != cid]
    alternatives = [
        f'{c.id} "{c.title}" ({_one_line(c, root)})'
        + (
            f" — {cm.set_aside_words(c.decision.reason)}"
            if c.status == "rejected" and c.decision is not None and c.decision.reason
            else ""
        )
        for c in siblings
    ]
    context = [
        f"Chosen among {len(cards)} concept direction(s) compared on the concept board"
        + (f" by {by}" if by else "")
        + "."
    ]
    if alternatives:
        context.append("Rejected alternatives: " + "; ".join(alternatives) + ".")
    red_override = card.verdict == "red"
    if red_override:
        assert card.screening is not None
        failing = "; ".join(f"{r.id}: {r.message}" for r in card.screening.failing)
        context.append(f"Promoted despite screening, which says: {failing}.")
    if override:
        context.append(f"Reason given for --override: {reason}.")
    over = [p for p in seeded if p.status == "overwritten"]
    if over:
        context.append(
            "Overwrote existing parameters: "
            + ", ".join(f"{p.name} (was {p.was}, now {p.value})" for p in over)
            + "."
        )
    n_new = len([p for p in seeded if p.status == "new"])
    decision_text = (
        f"Take {cid} ({card.title}) forward as the design direction: its envelope seeds "
        f"{_count(n_new, 'parameter')}, its site constraints and style choices become "
        f"{_count(len(new_reqs), 'requirement')}, and style.yaml takes its look."
    )
    stubs = [a for a in modules.seeded if not a.top]
    if stubs:
        decision_text += (
            f" The product starts from the modules it sketched: the top assembly {top} "
            f"holds {_and(modules.words)}, each an empty sub-assembly with "
            f"{_count(len(modules.budgets), 'size budget')} in all from the rough shapes."
        )
    elif modules.suggestion is not None:
        context.append(
            f"{cid} sketches the modules {_and(modules.words)}; the product already had its "
            "assemblies, so they were suggested, not written."
        )
    rationale = (
        f"Screening of {cid} ({card.verdict}): " + "; ".join(_labelled(card, root)) + "."
        if _labelled(card, root)
        else f"Screening of {cid} ({card.verdict})."
    )
    links = (
        [f"req://{r.id}" for r in new_reqs]
        + [f"param://{p.name}" for p in seeded]
        + [f"asm://{a.id}" for a in modules.seeded]
    )
    assert card.screening is not None
    title = f"Design direction: {card.title}" + (", despite screening" if red_override else "")
    dec_entry = {
        "id": dec_id,
        "date": stamp.date(),
        "title": title,
        "context": " ".join(context),
        "decision": decision_text,
        "rationale": rationale,
        "links": links,
        "made_by": "human" if by else "agent",
        "disclosed": True,
        "verify": bool(card.screening.estimates) or override,
        "sources": [f"concepts/{c.id}.yaml" for c in [card, *siblings]],
    }
    dec_text = paths.decisions.read_text(encoding="utf-8")
    dec_text = _append_items(
        dec_text, "decisions", [_yaml_block(dec_entry, _list_indent(dec_text, "decisions"))]
    )
    # 7. cards
    at = stamp.isoformat()
    card_texts = {cid: _card_text(root, cid, "promoted", {"dec": dec_id, "at": at})}
    rejected: list[str] = []
    already: list[str] = []
    for c in siblings:
        # an exploring card, or one marked promoted by hand with no decision (B2)
        by_hand = c.status == "promoted" and not cm.recorded_promotion(c, root)
        if c.status == "exploring" or by_hand:
            card_texts[c.id] = _card_text(
                root,
                c.id,
                "rejected",
                {"reason": cm.chosen_instead(cid, dec_id), "at": at},
            )
            rejected.append(c.id)
        else:
            already.append(c.id)
    # validate the texts on their own before touching the disk
    _check_texts(params_text, req_text, dec_text, len(existing_reqs) + len(new_reqs))
    from napkin2factory.core.style import style_path

    writes: dict[Path, str] = {
        paths.parameters: params_text,
        paths.requirements: req_text,
        paths.decisions: dec_text,
        style_path(root): style_text,
        **{cm.card_path(root, k): v for k, v in card_texts.items()},
        **{root / rel: text for rel, text in modules.texts.items()},
    }
    _write_all(root, writes, validate)
    result = PromotionResult(
        card_id=cid,
        title=card.title,
        dec_id=dec_id,
        override=override,
        params=seeded,
        requirements=new_reqs,
        style_created=style_created,
        rejected=rejected,
        already_rejected=already,
        notes=notes,
        files=sorted(_rel(root, p) for p in writes),
        assemblies=modules.seeded,
        modules=modules.words,
        suggestion=modules.suggestion,
        space=product_words(root).get("space", SPACE_WORDS),
    )
    # 8. snapshot
    if snapshot:
        from napkin2factory.core.vcs import Vcs

        vcs = Vcs(root)
        if vcs.is_tracked() and vcs.is_repo_root():
            result.snapshot = vcs.snapshot(f"Promote {cid}: {card.title}")
        else:
            notes.append("this folder is not a tracked project, so no snapshot was taken")
    return result


def _check_texts(params: str, reqs: str, decs: str, n_reqs: int) -> None:
    """Each edited model file still parses into its schema (and nothing was lost)."""
    from napkin2factory.core.model import DecisionsFile
    from napkin2factory.core.model.parameters import ParametersFile
    from napkin2factory.core.model.requirements import RequirementsFile

    checked: dict[str, Any] = {}
    for name, schema, text in (
        ("parameters", ParametersFile, params),
        ("requirements", RequirementsFile, reqs),
        ("decisions", DecisionsFile, decs),
    ):
        try:
            checked[name] = schema.model_validate(yaml.safe_load(text) or {})
        except Exception as exc:
            # gate C, C4: plain words first; the validator's own text stays in the chain
            raise N2FError(
                f"promotion could not edit model/{name}.yaml cleanly, so nothing was written; "
                f"check that the file still reads (`n2f lint`) — {_first_error(exc)}"
            ) from exc
    rf = checked["requirements"]
    if len(rf.requirements) != n_reqs:
        raise N2FError(
            "promotion could not append to model/requirements.yaml in its layout; nothing "
            "was written — check that `requirements:` is the file's only top-level key"
        )


def _first_error(exc: Exception) -> str:
    """The first problem of a validation error in one line ("requirements: not a list")."""
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            first = errors()[0]
            where = ".".join(str(p) for p in first.get("loc", ()))
            return f"{where}: {first.get('msg', '')}" if where else str(first.get("msg", ""))
        except Exception:  # noqa: BLE001 — fall back to the message itself
            pass
    return str(exc).splitlines()[0]


def _write_all(root: Path, writes: dict[Path, str], validate: Any) -> None:
    """Write every file; if the product no longer validates, put every file back."""
    before: dict[Path, str | None] = {
        p: p.read_text(encoding="utf-8") if p.is_file() else None for p in writes
    }
    try:
        for path, text in writes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        product, problems = validate(root)
        if product is None or problems.errors:
            first = problems.errors[0]
            raise N2FError(
                f"promotion would leave the model invalid ({first.subject}: {first.message}); "
                "nothing was written"
            )
    except BaseException:
        for path, old in before.items():
            if old is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(old, encoding="utf-8")
        raise
