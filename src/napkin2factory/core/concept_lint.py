"""Promotion words and the concept lint; split from core/concepts.py (S-259)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from napkin2factory.core.concepts import (
    ID_RE,
    card_files,
    concepts_dir,
    kit_generators,
    load_concepts,
    next_concept_id,
    screen_fields,
)
from napkin2factory.core.errors import Problems
from napkin2factory.core.model.concepts import ConceptCard
from napkin2factory.core.yamlio import read_yaml


def decision_ids(root: Path) -> set[str]:
    """The ids in ``model/decisions.yaml``, read raw (empty when the file is missing or odd).

    Read without loading the product so ``n2f concept lint`` and the Napkin gate work while
    the model has unrelated problems.
    """
    path = Path(root) / "model" / "decisions.yaml"
    try:
        data = read_yaml(path) if path.is_file() else None
    except Exception:  # an unreadable file is n2f validate's to report
        return set()
    rows = data.get("decisions") if isinstance(data, dict) else None
    return {str(r["id"]) for r in rows or [] if isinstance(r, dict) and "id" in r}


def promotion_problem(card: ConceptCard, dec_ids: set[str]) -> str | None:
    """Why a ``promoted`` card's promotion is not on record, or None when it is (or N/A).

    ``n2f concept promote`` always leaves a screening and ``decision.dec`` naming a decision
    in ``model/decisions.yaml``; a status typed by hand has neither, and must not complete
    the Napkin stage (review gate A, B2; D10).
    """
    if card.status != "promoted":
        return None
    dec = card.decision.dec if card.decision is not None else None
    if dec is None:
        return f"{card.id} says promoted but no decision records it"
    if dec not in dec_ids:
        return f"{card.id} says promoted by {dec}, but model/decisions.yaml has no {dec}"
    if card.screening is None:
        return f"{card.id} says promoted but was never built (no screening)"
    return None


def recorded_promotion(card: ConceptCard, root: Path) -> bool:
    """True when the card's promotion is on record: ``promoted`` with no :func:`promotion_problem`.

    A ``decision.dec`` naming a decision that ``model/decisions.yaml`` does not hold is not a
    record, so ``n2f concept reject`` and ``promote`` treat such a card as typed by hand.
    """
    return card.status == "promoted" and promotion_problem(card, decision_ids(root)) is None


_NOT_CHOSEN = re.compile(r"^not chosen: (C-\d{3}) promoted \((DEC-\d+)\)$")


def chosen_instead(chosen: str, dec: str) -> str:
    """The reason promotion records on a sibling: ``set aside when C-003 was chosen (DEC-001)``."""
    return f"set aside when {chosen} was chosen ({dec})"


def set_aside_words(reason: str | None) -> str:
    """Why a card was set aside, in one phrase starting ``set aside`` (review gate B, C12).

    Promotion's own reason reads as is; the wording cards carried before (``not chosen: C-003
    promoted (DEC-001)``) is read the same way; an owner's reason follows ``set aside:``.
    """
    text = (reason or "").strip()
    m = _NOT_CHOSEN.match(text)
    if m:
        return chosen_instead(m.group(1), m.group(2))
    if not text:
        return "set aside"
    if text.startswith("set aside"):
        return text
    return f"set aside: {text}"


MODULES_RULE = "C9-modules"
#: A module whose card gives no reason it is built on its own (shown on the board).
NO_REASON_WORDS = "no reason given yet"


def module_words(card: ConceptCard) -> list[str]:
    """Each module the card names, in plain words: ``door (built as one unit)`` (P10).

    The reasons are the assemblies' owner words (``core.build_units.DRIVER_WORDS``,
    ``docs/vocabulary.md``); a word outside the vocabulary is left out (lint names it).
    """
    from napkin2factory.core.build_units import DRIVER_WORDS, PHANTOM_WORDS

    out = []
    for name in card.module_names():
        entry = card.module_entry(name)
        if entry.build == "phantom":
            why = [PHANTOM_WORDS]
        else:
            why = [DRIVER_WORDS[d] for d in entry.driver if d in DRIVER_WORDS] or [NO_REASON_WORDS]
        out.append(f"{name.replace('-', ' ')} ({', '.join(why)})")
    return out


def _lint_modules(card: ConceptCard, path: Path, problems: Problems) -> None:
    """C9 (warnings only, P10): the card's modules use the assemblies' words (P7).

    A driver or build word outside the vocabulary, a massing line naming a module with no
    entry under ``modules:`` (allowed: it promotes with no reason given), and an entry no
    massing line belongs to (it promotes without a size budget).
    """
    from napkin2factory.core.model.assemblies import DRIVERS

    for name, entry in card.modules.items():
        unknown = [d for d in entry.driver if d not in DRIVERS]
        if unknown:
            problems.add(
                path,
                card.id,
                f"module {name}: {', '.join(repr(d) for d in unknown)} is not a reason a "
                "module is built on its own",
                f"use one of: {', '.join(DRIVERS)}",
                severity="warn",
                rule=MODULES_RULE,
            )
        if entry.build not in ("unit", "phantom"):
            problems.add(
                path,
                card.id,
                f"module {name}: build {entry.build!r} is neither unit nor phantom",
                "use `build: unit` (built as one unit, the default) or `build: phantom` "
                "(a grouping only)",
                severity="warn",
                rule=MODULES_RULE,
            )
        if not any(call.module == name for call in card.massing):
            problems.add(
                path,
                card.id,
                f"module {name}: no rough shape belongs to it, so promotion gives it no "
                "size budget",
                f"add `module: {name}` to the massing lines that make it up",
                severity="warn",
                rule=MODULES_RULE,
            )
    for i, call in enumerate(card.massing):
        if call.module is not None and call.module not in card.modules:
            problems.add(
                path,
                card.id,
                f"massing[{i}] ({call.as_}): module {call.module} has no entry under "
                "modules:, so nothing says why it is built on its own",
                f"add `{call.module}: {{driver: [built-as-unit]}}` (or another reason) under "
                "`modules:`",
                severity="warn",
                rule=MODULES_RULE,
            )


RENAMED_RULE = "C10-renamed-keys"


def _lint_fields(card: ConceptCard, path: Path, fields: list[Any], problems: Problems) -> None:
    """Rules C8, C5 and C10 on one card's fields (F8, F16).

    C8: a number of the wrong kind; C5 (a warning): a site key no screen reads; C10 (a
    warning): a key read under an earlier name for this version only.
    """
    for f in fields:
        key = f.written(card)
        if key is None:
            continue
        wrong = f.wrong_kind(f.raw(card))
        if wrong is not None:
            shown, kind, example = wrong
            problems.add(
                path,
                card.id,
                f"{f.section}.{key} is {shown}, which is not {kind}",
                f"give it as {kind} with its unit, like {example}",
                rule="C8-number-kinds",
            )
        if key != f.key:
            problems.add(
                path,
                card.id,
                f"{f.section}.{key} is read as {f.name} for this version only",
                f"rename it to {f.key} (same value); the old name stops being read in the "
                "next version",
                severity="warn",
                rule=RENAMED_RULE,
            )
    site = [f for f in fields if f.section == "site"]
    known = sorted({f.key for f in site})
    old = sorted({a for f in site for a in f.aliases})
    for key in card.site:
        if key not in known and key not in old:
            problems.add(
                path,
                card.id,
                f"site key {key!r} is not one any screen reads; it is kept but not checked",
                f"known keys: {', '.join(known)}"
                + (f"; read for this version only: {', '.join(old)}" if old else ""),
                severity="warn",
                rule="C5-site-keys",
            )


def lint_concepts(root: Path) -> Problems:
    """``n2f concept lint``: schema plus rules C1–C10; C5, C9 and C10 are warnings.

    The fields checked are those the screens installed for ``root`` declare: the system's,
    the domains' and the product's own (``model/screens/``, F8, F10).
    """
    problems = Problems()
    cards = load_concepts(root, problems)
    fields = screen_fields(root)
    files = {p.stem: p for p in card_files(root)}
    cdir = concepts_dir(root).resolve()
    generators = kit_generators()
    for stem, path in files.items():
        if not ID_RE.fullmatch(stem):
            problems.add(
                path,
                stem,
                f"the file name {path.name} is not a concept id",
                f"rename it to {next_concept_id(root)}.yaml (ids look like C-001) "
                "and set the same id inside",
                rule="C1-id-matches-file",
            )
    for cid, card in cards.items():
        path = files[cid]
        if ID_RE.fullmatch(cid) and card.id != cid:
            problems.add(
                path,
                card.id,
                f"id {card.id} does not match the file name {path.name}",
                f"make them agree: set `id: {cid}` or rename the file to {card.id}.yaml",
                rule="C1-id-matches-file",
            )
        for ref in card.refs:
            target = (cdir / ref).resolve()
            if not target.is_relative_to(cdir):
                problems.add(
                    path,
                    card.id,
                    f"refs entry {ref!r} points outside concepts/",
                    "copy the image into concepts/refs/ and refer to it as refs/<name>",
                    rule="C2-refs-exist",
                )
            elif not target.is_file():
                problems.add(
                    path,
                    card.id,
                    f"refs entry {ref!r} not found",
                    f"put the image at concepts/{ref}, or remove it from refs",
                    rule="C2-refs-exist",
                )
        for i, call in enumerate(card.massing):
            if call.kit not in generators:
                problems.add(
                    path,
                    card.id,
                    f"massing[{i}] ({call.as_}): {call.kit!r} is not a kit generator",
                    f"use one of: {', '.join(generators)}",
                    rule="C3-kit-known",
                )
        if card.based_on is not None:
            if card.based_on == card.id:
                problems.add(
                    path,
                    card.id,
                    "based_on names the card itself",
                    "name the card this one started from, or remove based_on",
                    rule="C4-based-on-exists",
                )
            elif card.based_on not in files:
                known = ", ".join(s for s in files if s != cid) or "none"
                problems.add(
                    path,
                    card.id,
                    f"based_on {card.based_on}: there is no such card",
                    f"name an existing card ({known}) or remove based_on",
                    rule="C4-based-on-exists",
                )
        _lint_fields(card, path, fields, problems)
        _lint_modules(card, path, problems)
    dec_ids = decision_ids(root)
    for cid, card in cards.items():
        why = promotion_problem(card, dec_ids)
        if why is not None:
            problems.add(
                files[cid],
                card.id,
                why,
                f"promote it with `n2f concept build {card.id}` then `n2f concept promote "
                f"{card.id}` (that records the decision), or set it aside with "
                f'`n2f concept reject {card.id} --reason "…"`',
                rule="C7-promoted-has-decision",
            )
        elif card.status == "rejected" and (card.decision is None or not card.decision.reason):
            problems.add(
                files[cid],
                card.id,
                f"{card.id} is rejected but says nothing about why",
                "give it `decision: {reason: …}`, or use "
                f'`n2f concept reject {card.id} --reason "…"`',
                rule="C7-promoted-has-decision",
            )
    promoted = [cid for cid, c in cards.items() if c.status == "promoted"]
    if len(promoted) > 1:
        for cid in promoted:
            problems.add(
                files[cid],
                cards[cid].id,
                f"more than one card is promoted ({', '.join(promoted)})",
                "a product has one chosen direction: set the others to `status: rejected`",
                rule="C6-one-promoted",
            )
    return problems
