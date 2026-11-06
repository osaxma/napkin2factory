"""Concept cards on disk: load, number, write, change status, lint (NAPKIN_STAGE §3, N1).

Cards live in ``concepts/C-xxx.yaml`` (images in ``concepts/refs/``) and sit **outside the
build graph**: nothing here is called by a build rule, ``load_product`` never reads them and
``n2f validate`` ignores them.  ``n2f concept lint`` (:func:`lint_concepts`) is their only
validator, and it is deliberately light: divergence must be free.

Split across concept_render.py and concept_lint.py (S-259).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from napkin2factory.core.concept_render import (  # noqa: F401
    _flow,
    _group_lines,
    _reads_lines,
    _scalar,
    render_card,
)
from napkin2factory.core.errors import N2FError, Problems
from napkin2factory.core.model.concepts import CONCEPT_STATUSES, ConceptCard
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip, read_yaml

CONCEPTS_DIR = "concepts"
REFS_DIR = "refs"
ID_RE = re.compile(r"C-(\d{3})")
#: Card fields are free-form (F8): ``envelope`` and ``site`` accept any named quantity. The
#: fields screening reads, with their kind of number and an example, are declared by the
#: installed screens (:func:`napkin2factory.concepts.screens.card_fields`), never listed here.
#: Sections ``n2f concept new --from`` copies from the card it starts from.
COPIED_SECTIONS: tuple[str, ...] = (
    "layout",
    "envelope",
    "site",
    "style",
    "modules",
    "massing",
    "notes",
)
SCHEMA_RULE = "C0-schema"


def screen_fields(root: Path | None = None) -> list[Any]:
    """The card fields the screens installed for ``root`` read (generic, domains', product's)."""
    from napkin2factory.concepts.screens import card_fields

    return card_fields(root)


def param_names(root: Path | None = None) -> dict[str, str]:
    """Envelope keys that seed a parameter under another name, as their screens declare.

    Any screen declaring the field may name the parameter, not only the first: a domain's
    screens are declared before the product's own (S-160, ``declared_fields``).
    """
    return {f.key: f.param for f in screen_fields(root) if f.section == "envelope" and f.param}


def wrong_kind(
    section: str, key: str, value: Any, fields: list[Any] | None = None
) -> tuple[str, str, str] | None:
    """Why a card number is not the kind its screen reads, else ``None``.

    Returns ``(the value as written, the kind it should be, an example)``. Only fields a
    screen declares are checked (``key`` may be an alias); a missing value is not a problem.
    """
    for f in fields if fields is not None else screen_fields():
        if f.section == section and key in (f.key, *f.aliases):
            return f.wrong_kind(value)  # type: ignore[no-any-return]
    return None


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


def _field_home(key: str, fields: list[Any] | None = None) -> str | None:
    """The card section whose screen reads ``key`` (``site``), else ``None`` (B-0253)."""
    for f in fields if fields is not None else screen_fields():
        if key in (f.key, *f.aliases):
            return str(f.section)
    return None


def _load_keys(fields: list[Any] | None = None) -> str:
    """The ``site`` keys a screen reads that describe loads, ``point_load, …`` (B-0253)."""
    fs = fields if fields is not None else screen_fields()
    return ", ".join(f.key for f in fs if f.section == "site" and f.group)


def _schema_hint(err: Any) -> str:
    loc = ".".join(str(x) for x in err["loc"]) or "(top level)"
    if err["type"] == "extra_forbidden":
        known = ", ".join(ConceptCard.model_fields)
        key = str(err["loc"][-1]) if err["loc"] else ""
        if len(err["loc"]) == 1 and key in ("loads", "load"):
            return (
                f"loads are not a card section; give each as its own key under `site:`, "
                f"e.g. `site: {{point_load: 2000 N}}` (the keys: {_load_keys() or 'point_load'}); "
                f"a card's keys are: {known}"
            )
        home = _field_home(key) if len(err["loc"]) == 1 else None
        if home is not None:
            return (
                f"{key!r} goes inside `{home}:` (for example `{home}: {{{key}: …}}`), "
                f"not at the top of the card; a card's keys are: {known}"
            )
        return f"remove or rename the key {loc!r}; a card's keys are: {known}"
    if err["loc"] and err["loc"][0] == "site" and str(err["loc"][-1]) in ("loads", "load"):
        return (
            "a site entry is one number or word, not a group: write each load as its own key "
            f"under `site:` (the keys: {_load_keys() or 'point_load'}), "
            "e.g. `point_load: 2000 N`"
        )
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
        "modules": {},
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
    path.write_text(render_card(data, screen_fields(root)), encoding="utf-8")
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
        path.write_text(render_card(data, screen_fields(root)), encoding="utf-8")
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


# Re-exported from concept_lint at the end to avoid circular imports (S-259).
from napkin2factory.core.concept_lint import (  # noqa: E402, F401
    _NOT_CHOSEN,
    MODULES_RULE,
    NO_REASON_WORDS,
    RENAMED_RULE,
    _lint_fields,
    _lint_modules,
    chosen_instead,
    lint_concepts,
    module_words,
    recorded_promotion,
    set_aside_words,
)
from napkin2factory.core.concept_lint import (  # noqa: E402, F401
    decision_ids as decision_ids,
)
from napkin2factory.core.concept_lint import (  # noqa: E402, F401
    promotion_problem as promotion_problem,
)
