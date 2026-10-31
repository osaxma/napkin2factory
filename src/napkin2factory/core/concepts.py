"""Concept cards on disk: load, number, write, change status, lint (NAPKIN_STAGE §3, N1).

Cards live in ``concepts/C-xxx.yaml`` (images in ``concepts/refs/``) and sit **outside the
build graph**: nothing here is called by a build rule, ``load_product`` never reads them and
``n2f validate`` ignores them.  ``n2f concept lint`` (:func:`lint_concepts`) is their only
validator, and it is deliberately light: divergence must be free.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from napkin2factory.core.errors import N2FError, Problems
from napkin2factory.core.model.concepts import CONCEPT_STATUSES, ConceptCard
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip, read_yaml

CONCEPTS_DIR = "concepts"
REFS_DIR = "refs"
ID_RE = re.compile(r"C-(\d{3})")
#: Site keys concept screening knows; any other key is kept but draws a warning (C5).
SITE_KEYS: frozenset[str] = frozenset(
    {
        "alcove_width",
        "alcove_depth",
        "alcove_height",
        "floor_load",
        "circuit",
        "region",
        "lift_class",
        "mass_limit",
        "door_clearance",
        "ambient_max",
        "outdoor",
    }
)
#: Sections ``n2f concept new --from`` copies from the card it starts from.
COPIED_SECTIONS: tuple[str, ...] = ("layout", "envelope", "site", "style", "massing", "notes")
SCHEMA_RULE = "C0-schema"


def concepts_dir(root: Path) -> Path:
    """``<product>/concepts/``."""
    return Path(root) / CONCEPTS_DIR


def card_path(root: Path, concept_id: str) -> Path:
    """``<product>/concepts/<id>.yaml``."""
    return concepts_dir(root) / f"{concept_id}.yaml"


def card_files(root: Path) -> list[Path]:
    """Every ``*.yaml`` directly under ``concepts/``, sorted by name."""
    d = concepts_dir(root)
    return sorted(p for p in d.glob("*.yaml") if p.is_file()) if d.is_dir() else []


def has_concepts(root: Path) -> bool:
    """True when ``concepts/`` holds at least one card file."""
    return bool(card_files(root))


def normalize_concept_id(text: str) -> str:
    """Accept ``C-002``, ``c-2`` or ``2`` and return ``C-002``; anything else is returned as is."""
    m = re.fullmatch(r"(?:[cC]-?)?0*(\d{1,3})", text.strip())
    return f"C-{int(m.group(1)):03d}" if m else text.strip()


def kit_generators() -> tuple[str, ...]:
    """The kit generator names, imported lazily (the kit index loads no CAD kernel)."""
    from napkin2factory.geometry.kit import GENERATORS

    return GENERATORS


def _schema_hint(err: Any) -> str:
    loc = ".".join(str(x) for x in err["loc"]) or "(top level)"
    if err["type"] == "extra_forbidden":
        known = ", ".join(ConceptCard.model_fields)
        return f"remove or rename the key {loc!r}; a card's keys are: {known}"
    if err["type"] == "missing":
        return f"add the required key {loc!r}"
    if loc == "status":
        return f"use one of: {', '.join(CONCEPT_STATUSES)}"
    if loc == "id" or loc == "based_on":
        return "concept ids look like C-001 (C, a hyphen, three digits)"
    return "fix the value, then run `n2f concept lint`"


def _read_card(path: Path, problems: Problems) -> ConceptCard | None:
    try:
        data = read_yaml(path)
    except yaml.YAMLError as exc:
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else "unreadable"
        problems.add(
            path,
            path.stem,
            f"the card is not readable YAML ({first})",
            "fix the indentation, colons or brackets, then run `n2f concept lint`",
            rule=SCHEMA_RULE,
        )
        return None
    if not isinstance(data, dict):
        problems.add(
            path,
            path.stem,
            "the card is not a set of keys (id, title, status, …)",
            "start it again with `n2f concept new <title>` and copy the content across",
            rule=SCHEMA_RULE,
        )
        return None
    try:
        return ConceptCard.model_validate(data)
    except ValidationError as exc:
        subject = data.get("id") if isinstance(data.get("id"), str) else path.stem
        for err in exc.errors():
            loc = ".".join(str(x) for x in err["loc"]) or "(top level)"
            problems.add(
                path, str(subject), f"{loc}: {err['msg']}", _schema_hint(err), rule=SCHEMA_RULE
            )
        return None


def load_concepts(root: Path, problems: Problems | None = None) -> dict[str, ConceptCard]:
    """Every readable card keyed by its file name (``C-001``), sorted.

    With ``problems`` given, schema findings are appended to it and the readable cards are
    returned; without, any finding raises :class:`~napkin2factory.core.errors.ModelError`.
    """
    collect = problems if problems is not None else Problems()
    cards: dict[str, ConceptCard] = {}
    for path in card_files(root):
        card = _read_card(path, collect)
        if card is not None:
            cards[path.stem] = card
    if problems is None:
        collect.raise_if_any()
    return dict(sorted(cards.items()))


def load_card(root: Path, concept_id: str) -> ConceptCard:
    """One card by id; a missing card or a schema problem is an actionable error."""
    cid = normalize_concept_id(concept_id)
    path = card_path(root, cid)
    if not path.is_file():
        known = [p.stem for p in card_files(root)]
        listing = f"known: {', '.join(known)}" if known else "there are no concepts yet"
        raise N2FError(
            f"there is no concept {cid} ({listing}) — `n2f concept list` shows them, "
            '`n2f concept new "<title>"` starts one'
        )
    problems = Problems()
    card = _read_card(path, problems)
    problems.raise_if_any()
    assert card is not None
    return card


def next_concept_id(root: Path) -> str:
    """The next free id: one above the highest ``C-xxx.yaml`` already present."""
    numbers = [int(m.group(1)) for p in card_files(root) if (m := ID_RE.fullmatch(p.stem))]
    n = max(numbers, default=0) + 1
    if n > 999:
        raise N2FError(
            "concepts/ already holds C-999; archive old cards elsewhere before starting more"
        )
    return f"C-{n:03d}"


def _flow(value: Any) -> str:
    return str(
        yaml.safe_dump(
            value, default_flow_style=True, sort_keys=False, allow_unicode=True, width=4096
        )
    ).strip()


def _scalar(key: str, value: Any) -> str:
    return str(yaml.safe_dump({key: value}, sort_keys=False, allow_unicode=True, width=88)).rstrip(
        "\n"
    )


def render_card(data: dict[str, Any]) -> str:
    """A card as commented YAML, every §3 section present, in the canonical order.

    ``data`` holds plain values (strings, lists, dicts) as read from YAML or dumped from a
    :class:`ConceptCard` in JSON mode with aliases.
    """
    cid = data["id"]
    lines = [
        f"# Concept card {cid}: one possible direction for the product.",
        "# Concepts sit outside the build: nothing here changes `n2f build`; edit freely.",
        f"# Read it back with `n2f concept show {cid}`; check it with `n2f concept lint`.",
        _scalar("id", cid),
        _scalar("title", data.get("title", "")),
        "# status: exploring | rejected | promoted (reject and promote set it for you)",
        _scalar("status", data.get("status", "exploring")),
    ]
    if data.get("based_on"):
        lines.append(_scalar("based_on", data["based_on"]) + "  # the card this one started from")
    lines += [
        "# refs: images under concepts/refs/ that informed this card (never geometry),",
        "#   e.g. [refs/sketch-01.jpg]",
        f"refs: {_flow(data.get('refs') or [])}",
        "# layout: where things go, in words,",
        "#   e.g. {load: front, door: hinged-left, controls: side-right, stand: four-leg}",
        f"layout: {_flow(data.get('layout') or {})}",
        "# envelope: named rough sizes; they seed parameters when this card is chosen,",
        "#   e.g. {chamber: [200 mm, 200 mm, 200 mm], insulation: 170 mm}",
        f"envelope: {_flow(data.get('envelope') or {})}",
        "# site: where it must fit and plug in, e.g. {alcove_width: 800 mm, circuit: 240V-13A,",
        "#   region: SA}; screening checks these, and they become requirements when chosen",
        f"site: {_flow(data.get('site') or {})}",
        "# style: look and feel,",
        "#   e.g. {preset: appliance, corner_radius: 8 mm, fastener_visibility: hidden-front}",
        f"style: {_flow(data.get('style') or {})}",
        "# massing: rough shapes from the kit, one line each, e.g.",
        "#   - {kit: enclosure, as: body, args: {length: 540 mm, width: 540 mm, height: 620 mm}}",
        "#   - {kit: block, as: door, args: {…}, at: {…}}",
    ]
    massing = data.get("massing") or []
    if massing:
        lines.append("massing:")
        lines += [f"  - {_flow(m)}" for m in massing]
    else:
        lines.append("massing: []")
    lines += [
        "# notes: anything worth remembering about this direction",
        _scalar("notes", data.get("notes")),
        "# written for you: screening by `n2f concept build`, decision by reject or promote",
        _scalar("screening", data.get("screening")),
        _scalar("decision", data.get("decision")),
    ]
    return "\n".join(lines) + "\n"


def new_card(root: Path, title: str, based_on: str | None = None) -> ConceptCard:
    """Write the next free card (status ``exploring``); ``based_on`` copies a card's content."""
    if not title.strip():
        raise N2FError('give the concept a short title, e.g. `n2f concept new "Squared shell"`')
    cid = next_concept_id(root)
    data: dict[str, Any] = {
        "id": cid,
        "title": title.strip(),
        "status": "exploring",
        "based_on": None,
        "refs": [],
        "layout": {},
        "envelope": {},
        "site": {},
        "style": {},
        "massing": [],
        "notes": None,
        "screening": None,
        "decision": None,
    }
    if based_on is not None:
        source = load_card(root, based_on)
        raw = read_yaml(card_path(root, normalize_concept_id(based_on)))
        for key in COPIED_SECTIONS:
            if key in raw:
                data[key] = raw[key]
        data["based_on"] = source.id
    card = ConceptCard.model_validate(data)
    path = card_path(root, cid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_card(data), encoding="utf-8")
    return card


def write_card(root: Path, card: ConceptCard) -> Path:
    """Write ``card`` to ``concepts/<id>.yaml``.

    A new file gets the commented layout of :func:`render_card`; an existing file is edited
    in place, replacing only the sections whose value changed, so hand-written comments and
    key order survive.
    """
    path = card_path(root, card.id)
    data = card.model_dump(mode="json", by_alias=True)
    doc = load_roundtrip(path) if path.is_file() else None
    if not isinstance(doc, dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_card(data), encoding="utf-8")
        return path
    try:
        old: ConceptCard | None = ConceptCard.model_validate(read_yaml(path))
    except ValidationError:
        old = None
    for key, value in data.items():
        if key not in doc and value in (None, [], {}):
            continue  # an absent optional section stays absent
        if old is not None and key in doc and getattr(old, key) == getattr(card, key):
            continue
        doc[key] = value
    dump_roundtrip(path, doc, explicit_null=True)
    return path


def update_card_status(
    root: Path, concept_id: str, status: str, decision: dict[str, Any] | None = None
) -> ConceptCard:
    """Set a card's ``status`` (and ``decision``) in place, keeping comments and key order."""
    from ruamel.yaml.comments import CommentedMap

    card = load_card(root, concept_id)
    path = card_path(root, card.id)
    merged = {**read_yaml(path), "status": status}
    if decision is not None:
        merged["decision"] = decision
    ConceptCard.model_validate(merged)  # refuse before touching the file
    doc = load_roundtrip(path)
    doc["status"] = status
    if decision is not None:
        flow = CommentedMap(decision)
        flow.fa.set_flow_style()
        doc["decision"] = flow
    dump_roundtrip(path, doc, explicit_null=True)
    return load_card(root, card.id)


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


def lint_concepts(root: Path) -> Problems:
    """``n2f concept lint``: schema plus rules C1–C7; only C5 (site keys) is a warning."""
    problems = Problems()
    cards = load_concepts(root, problems)
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
        for key in card.site:
            if key not in SITE_KEYS:
                problems.add(
                    path,
                    card.id,
                    f"site key {key!r} is not one screening knows; it is kept but not checked",
                    f"known keys: {', '.join(sorted(SITE_KEYS))}",
                    severity="warn",
                    rule="C5-site-keys",
                )
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
