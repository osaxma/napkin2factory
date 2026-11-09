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
    _shown,
    _yaml_block,
    append_reason,
    display_units,
    held_requirement,
)
from napkin2factory.concepts.promote.decision import (
    _card_text,
    _labelled,
    _one_line,
    plain_reason,
    verdict_words,
)
from napkin2factory.concepts.promote.form import form_requirements
from napkin2factory.concepts.promote.modules import plan_modules
from napkin2factory.concepts.promote.parameters import append_param_lines, plan_parameters
from napkin2factory.concepts.promote.result import PromotionResult
from napkin2factory.concepts.promote.seeding import plan_seed
from napkin2factory.concepts.promote.site import site_requirements
from napkin2factory.concepts.promote.style import plan_style, stated_style_keys
from napkin2factory.concepts.screens import SPACE_WORDS
from napkin2factory.core import concepts as cm
from napkin2factory.core.errors import GateBlocked, N2FError
from napkin2factory.core.model.concepts import ConceptCard
from napkin2factory.core.packs import product_words
from napkin2factory.core.units import is_quantity, parse_quantity


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


def _is_broken(fig_mag: float, lim_mag: float, op: str) -> bool:
    if op == "<":
        return fig_mag >= lim_mag
    if op == "<=":
        return fig_mag > lim_mag
    if op == ">":
        return fig_mag <= lim_mag
    if op == ">=":
        return fig_mag < lim_mag
    return False


def _check_conflict(
    card: ConceptCard,
    about: str,
    data: dict[str, Any],
    root: Path | None = None,
    override: bool = False,
) -> dict[str, Any] | None:
    """Check whether a planned requirement conflicts with the card's screening figures (B-0324).

    If the card's recorded screening figure breaks the limit in the requirement,
    returns ``{title, limit, figure, say}``; otherwise None. An explicit override seeds the
    requirement anyway.
    """
    if override or card.screening is None:
        return None
    verify = data.get("verify")
    if not isinstance(verify, dict):
        return None

    op = verify.get("op")
    raw_limit = verify.get("value")
    target = str(verify.get("target") or "")
    category = str(data.get("category") or "")
    title_lower = str(data.get("title") or "").lower()

    # 1. Mass / weight
    if about == "weight" or target.endswith("#props.mass") or category == "mass":
        if raw_limit is None:
            ml = card.site.get("mass_limit")
            if not is_quantity(ml) and isinstance(card.site.get("lift_class"), str):
                from napkin2factory.calckit import load_table

                lbl = card.site["lift_class"]
                row = next((r for r in load_table("lift_classes") if r["label"] == lbl), None)
                if row is not None and row.get("max_kg") is not None:
                    raw_limit = f"{row['max_kg']} kg"
            elif ml is not None:
                raw_limit = ml
            op = "<"

        if raw_limit is not None and op:
            lv = card.screening.values.get("total_mass") or card.screening.values.get("mass")
            if lv is not None:
                try:
                    limit = parse_quantity(raw_limit)
                    figure = parse_quantity(lv.value)
                    fig_mag = figure.to(limit.units).magnitude
                    lim_mag = limit.magnitude
                    if _is_broken(fig_mag, lim_mag, op):
                        units = display_units(root)
                        fig_str = _shown(figure, units)
                        lim_str = _shown(limit, units)
                        lift_class = card.site.get("lift_class")
                        limit_name = f"{lift_class} lift limit" if lift_class else "lift limit"
                        say = (
                            f"The design weighs {fig_str} on the napkin, over the "
                            f"{lim_str} {limit_name}. Ask the owner: drop the limit, "
                            "or change the design."
                        )
                        return {
                            "title": data["title"],
                            "limit": lim_str,
                            "figure": fig_str,
                            "say": say,
                        }
                except Exception:
                    pass

    # 2. Cost / budget
    if about == "cost" or target.endswith("#total_cost") or category == "cost":
        if raw_limit is None:
            raw_limit = card.site.get("budget")
            op = "<="
        if raw_limit is not None and op:
            lv = (
                card.screening.estimates.get("cost_high")
                or card.screening.values.get("cost_high")
                or card.screening.estimates.get("cost_low")
                or card.screening.values.get("cost_low")
            )
            if lv is not None:
                try:
                    limit = parse_quantity(raw_limit)
                    figure = parse_quantity(lv.value)
                    fig_mag = figure.to(limit.units).magnitude
                    lim_mag = limit.magnitude
                    if _is_broken(fig_mag, lim_mag, op):
                        units = display_units(root)
                        fig_str = _shown(figure, units)
                        lim_str = _shown(limit, units)
                        say = (
                            f"The design costs {fig_str} on the napkin, over the "
                            f"{lim_str} budget. Ask the owner: drop the limit, "
                            "or change the design."
                        )
                        return {
                            "title": data["title"],
                            "limit": lim_str,
                            "figure": fig_str,
                            "say": say,
                        }
                except Exception:
                    pass

    # 3. Sag / deflection
    if about == "sag" or target.endswith("#props.deflection"):
        if raw_limit is None:
            raw_limit = card.site.get("max_deflection")
            op = "<="
        if raw_limit is not None and op:
            lv = card.screening.computed.get("deflection") or card.screening.values.get(
                "deflection"
            )
            if lv is not None:
                try:
                    limit = parse_quantity(raw_limit)
                    figure = parse_quantity(lv.value)
                    fig_mag = figure.to(limit.units).magnitude
                    lim_mag = limit.magnitude
                    if _is_broken(fig_mag, lim_mag, op):
                        units = display_units(root)
                        fig_str = _shown(figure, units)
                        lim_str = _shown(limit, units)
                        say = (
                            f"The design sags {fig_str} on the napkin, over the "
                            f"{lim_str} sag limit. Ask the owner: drop the limit, "
                            "or change the design."
                        )
                        return {
                            "title": data["title"],
                            "limit": lim_str,
                            "figure": fig_str,
                            "say": say,
                        }
                except Exception:
                    pass

    # 4. Dimensions / space
    if about == "space":
        if "bbox.x" in target or "width" in title_lower:
            name = "width"
        elif "bbox.y" in target or "depth" in title_lower or "deep" in title_lower:
            name = "depth"
        elif "bbox.z" in target or "height" in title_lower or "tall" in title_lower:
            name = "height"
        else:
            name = None

        if name:
            if raw_limit is None:
                raw_limit = card.site.get(name)
                op = "<="
            if raw_limit is not None and op:
                word = "wide" if name == "width" else ("deep" if name == "depth" else "tall")
                lv = card.screening.computed.get(name) or card.screening.values.get(name)
                if lv is not None:
                    try:
                        limit = parse_quantity(raw_limit)
                        figure = parse_quantity(lv.value)
                        fig_mag = figure.to(limit.units).magnitude
                        lim_mag = limit.magnitude
                        if _is_broken(fig_mag, lim_mag, op):
                            units = display_units(root)
                            fig_str = _shown(figure, units)
                            lim_str = _shown(limit, units)
                            say = (
                                f"The design is {fig_str} {word} on the napkin, over the "
                                f"{lim_str} space limit. Ask the owner: drop the limit, "
                                "or change the design."
                            )
                            return {
                                "title": data["title"],
                                "limit": lim_str,
                                "figure": fig_str,
                                "say": say,
                            }
                    except Exception:
                        pass

    # 5. Structural safety factors
    if about in ("yield", "buckling", "tip-over"):
        factor_name = target.split("#props.")[-1] if "#props." in target else f"{about}_factor"
        if raw_limit is not None and op:
            lv = card.screening.computed.get(factor_name) or card.screening.values.get(factor_name)
            if lv is not None:
                try:
                    limit = parse_quantity(raw_limit)
                    figure = parse_quantity(lv.value)
                    fig_mag = figure.magnitude
                    lim_mag = limit.magnitude
                    if _is_broken(fig_mag, lim_mag, op):
                        fig_str = f"{fig_mag:g}"
                        lim_str = f"{lim_mag:g}"
                        say = (
                            f"The structural factor for {about} is {fig_str} on the napkin, "
                            f"under the {lim_str} minimum. Ask the owner: drop the limit, "
                            "or change the design."
                        )
                        return {
                            "title": data["title"],
                            "limit": lim_str,
                            "figure": fig_str,
                            "say": say,
                        }
                except Exception:
                    pass

    return None


def _parked_sibling_built(root: Path, card: ConceptCard, at: str) -> dict[str, Any]:
    """The ``built`` record promotion writes on a built sibling it parks (B-0289).

    Mirrors how ``concept switch`` parks the current direction: the saved state a later
    ``concept switch`` restores from is the newest checkpoint (the state before this
    promotion), and the figures are the built design's own. A built card cannot exist
    without saved history (``concept fork-from-model`` refuses it), so the newest checkpoint
    is always available; the card's own checkpoint is the fallback.
    """
    from napkin2factory.core import checkpoints as cps
    from napkin2factory.core.vcs import Vcs

    assert card.built is not None
    built: dict[str, Any] = {
        "event": "parked",
        "checkpoint": card.built.checkpoint,
        "number": card.built.number,
        "at": at,
    }
    if card.built.mass:
        built["mass"] = card.built.mass
    if card.built.cost:
        built["cost"] = card.built.cost
    newest = cps.read(Vcs(root), limit=1)
    if newest:
        built["checkpoint"] = newest[0].id
        built["number"] = newest[0].number
    return built


def promote(
    root: Path,
    card_id: str,
    override: bool = False,
    reason: str | None = None,
    by: str | None = None,
    *,
    now: dt.datetime | None = None,
    snapshot: bool = True,
    supersedes: str | None = None,
) -> PromotionResult:
    """Promote one concept card into the product model (see the module docstring).

    Args:
        root: the product folder.
        card_id: the card (``C-003``, ``3``…).
        override: promote a red card, or overwrite parameters that differ (needs ``reason``).
        reason: why (recorded in the decision's context).
        by: the person who chose (``made_by: human``); without it the agent made the call.
        now: the timestamp to record (default: now, to the second).
        snapshot: save the ``Promoted C-00x`` checkpoint (when the folder is a project root).
        supersedes: the decision (``DEC-0xx``) this promotion replaces, as ``concept switch``
            does (R10): its words join the new decision's context and ``dec://`` joins its links.

    Raises:
        GateBlocked: a gate refused (exit 3); nothing was written.
        N2FError: the model or a card does not load, or the edits would not validate.
    """
    from napkin2factory.core.loader import validate

    root = Path(root)
    stamp = (now or dt.datetime.now()).replace(microsecond=0)
    try:
        card = cm.load_card(root, card_id)
    except N2FError as exc:
        where = f" --dir {root}" if root != Path.cwd() else ""
        raise N2FError(str(exc), next=f"n2f concept list{where}") from exc
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
        from napkin2factory.core.vcs import Vcs

        vcs = Vcs(root)
        released = vcs.is_tracked() and bool(vcs.tags())
        way = (
            'start a design change: `n2f ecr start --kind design --title "…"`'
            if released
            else f"run `n2f concept switch {cid}`"
        )
        raise GateBlocked(
            f"{chosen[0].id} is already the chosen direction — to choose {cid} instead, {way}"
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
        where = f" --dir {root}" if root != Path.cwd() else ""
        raise N2FError(
            f"the product model has problems{what}, so nothing was promoted — "
            "fix them first (`n2f validate`)",
            next=f"n2f validate{where}",
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
    # 3c. the rough shapes become parts, sizes and a layout, or nothing (S-336)
    seed = plan_seed(card, product, seeded, modules, notes)
    for rel in seed.texts:
        if (root / rel).exists():
            raise GateBlocked(
                f"{rel} already exists; promotion never overwrites a file — move it away, "
                "then promote again"
            )
    if seed.seeded:
        params_text = append_param_lines(
            params_text,
            cid,
            seed.param_lines,
            f"from the rough shapes of {cid} (n2f concept promote)",
        )
        seeded = seeded + seed.new_params
    # 3 + 4. requirements: at the seeded top assembly when there was none before
    top = _top_assembly(product, notes) or modules.top or seed.top
    planned = (
        site_requirements(card, seeded, top, notes, root, structure=seed.seeded)
        + form_requirements(card, style, top, notes, stated_style_keys(card, root))
        + modules.budgets
    )
    req_ids: list[str] = []
    existing_reqs = list(product.requirements)
    new_reqs: list[NewRequirement] = []
    conflicts: list[dict[str, Any]] = []
    req_text = paths.requirements.read_text(encoding="utf-8")
    indent = _list_indent(req_text, "requirements")
    blocks = []
    for about, data in planned:
        conflict = _check_conflict(card, about, data, root, override=override)
        if conflict is not None:
            conflicts.append(conflict)
            continue
        asked = held_requirement(product.requirements, data["verify"], card_field=about)
        if asked is not None:  # the model already asks this: no second copy to sign off (S-277)
            notes.append(f"{asked} already asks this: {product.requirements[asked].title}")
            continue
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
            "tags": [f"card-field:{about}"],
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
        context.append("Other ideas considered: " + "; ".join(alternatives) + ".")
    red_override = card.verdict == "red"
    if red_override:
        assert card.screening is not None
        failing = "; ".join(f"{r.id}: {plain_reason(r.message)}" for r in card.screening.failing)
        context.append(f"Promoted despite screening, which says: {failing}.")
    if override:
        context.append(f"Reason given for --override: {reason}.")
    if supersedes:
        context.append(f"This supersedes {supersedes}.")
    over = [p for p in seeded if p.status == "overwritten"]
    if over:
        context.append(
            "Overwrote existing parameters: "
            + ", ".join(f"{p.name} (was {p.was}, now {p.value})" for p in over)
            + "."
        )
    n_new = len([p for p in seeded if p.status == "new"])
    from_site = any(p.source.startswith("site.") for p in seeded)
    decision_text = (
        f"Take {cid} ({card.title}) forward as the design direction: its "
        f"{'envelope and loads seed ' if from_site else 'envelope seeds '}"
        f"{_count(n_new, 'parameter')}, its site constraints and style choices become "
        f"{_count(len(new_reqs), 'requirement')}, and style.yaml takes its look."
    )
    stubs = [a for a in modules.seeded if not a.top]
    if stubs:
        filling = (
            "each with the parts its rough shapes became and"
            if seed.seeded
            else "each an empty sub-assembly with"
        )
        decision_text += (
            f" The product starts from the modules it sketched: the top assembly {top} "
            f"holds {_and(modules.words)}, {filling} "
            f"{_count(len(modules.budgets), 'size budget')} in all from the rough shapes."
        )
    if seed.seeded:
        decision_text += (
            f" Its rough shapes become {_count(len(seed.parts), 'part')} placed where the card "
            "drew them, driven by the overall sizes, and the sag and strength limits are "
            "checked on the built model."
        )
    if modules.suggestion is not None and not stubs:
        context.append(
            f"{cid} sketches the modules {_and(modules.words)}; the product already had its "
            "assemblies, so they were suggested, not written."
        )
    rationale = (
        f"Screening of {cid} ({verdict_words(card)}): " + "; ".join(_labelled(card, root)) + "."
        if _labelled(card, root)
        else f"Screening of {cid} ({verdict_words(card)})."
    )
    links = (
        [f"req://{r.id}" for r in new_reqs]
        + [f"param://{p.name}" for p in seeded]
        + [f"asm://{a.id}" for a in modules.seeded]
        + [f"part://{p.id}" for p in seed.parts]
        + ([f"dec://{supersedes}"] if supersedes else [])
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
    chosen_decision: dict[str, Any] = {"dec": dec_id, "at": at}
    # a card promoted again keeps its earlier rejection reason so a later parking does not
    # lose it (B-0282: "The frame sags …" stays in front of "parked when …")
    if card.decision is not None and card.decision.reason:
        chosen_decision["reason"] = card.decision.reason
    card_texts = {cid: _card_text(root, cid, "promoted", chosen_decision)}
    rejected: list[str] = []
    parked: list[str] = []
    already: list[str] = []
    for c in siblings:
        # an exploring card, or one marked promoted by hand with no decision (B2)
        by_hand = c.status == "promoted" and not cm.recorded_promotion(c, root)
        if c.status == "exploring" or by_hand:
            earlier = c.decision.reason if c.decision is not None else None
            if c.built is not None:
                # a card holding a built design (forked) is parked, not rejected (B-0289):
                # record the saved state a later switch restores from, like switch parks
                card_texts[c.id] = _card_text(
                    root,
                    c.id,
                    "parked",
                    {
                        "reason": append_reason(
                            earlier, f"parked when {cid} was chosen ({dec_id})"
                        ),
                        "at": at,
                    },
                    built=_parked_sibling_built(root, c, at),
                )
                parked.append(c.id)
            else:
                card_texts[c.id] = _card_text(
                    root,
                    c.id,
                    "rejected",
                    {"reason": append_reason(earlier, cm.chosen_instead(cid, dec_id)), "at": at},
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
        **{root / rel: text for rel, text in {**modules.texts, **seed.texts}.items()},
    }
    if snapshot:
        from napkin2factory.ecr.checkpointing import save_edits_first

        save_edits_first(root)  # the owner's loose edits stay their own step (R4)
    _write_all(root, writes, validate)
    result = PromotionResult(
        card_id=cid,
        title=card.title,
        dec_id=dec_id,
        override=override,
        params=seeded,
        requirements=new_reqs,
        conflicts=conflicts,
        style_created=style_created,
        rejected=rejected,
        parked=parked,
        already_rejected=already,
        notes=notes,
        files=sorted(_rel(root, p) for p in writes),
        assemblies=seed.assemblies if seed.seeded else modules.seeded,
        seed=seed,
        modules=modules.words,
        suggestion=modules.suggestion,
        space=product_words(root).get("space", SPACE_WORDS),
    )
    # 8. snapshot
    if snapshot:
        from napkin2factory.core.vcs import Vcs

        vcs = Vcs(root)
        if vcs.is_tracked() and vcs.is_repo_root():
            from napkin2factory.core.vitals import recorded_vitals
            from napkin2factory.ecr.checkpointing import checkpoint

            cp = checkpoint(root, f"Promoted {cid} ({card.title})", vitals=recorded_vitals(root))
            result.snapshot, result.checkpoint = cp.id, cp.number
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
                f"check that the file still reads (`n2f lint`) — {_first_error(exc)}",
                next="n2f lint",
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
            where = f" --dir {root}" if root != Path.cwd() else ""
            raise N2FError(
                f"promotion would leave the model invalid ({first.subject}: {first.message}); "
                "nothing was written",
                next=f"n2f validate{where}",
            )
    except BaseException:
        for path, old in before.items():
            if old is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(old, encoding="utf-8")
        raise
