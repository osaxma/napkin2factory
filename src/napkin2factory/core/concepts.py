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
    """Envelope keys that seed a parameter under another name, as their screens declare."""
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


def _reads_lines(section: str, fields: list[Any]) -> list[str]:
    """``#   screens read: width (a length, like 800 mm), …`` wrapped as comment lines."""
    items = [
        f"{f.key} ({f.kind}, like {f.example})" if f.unit else f"{f.key} (like {f.example})"
        for f in fields
        if f.section == section
    ]
    if not items:
        return ["#   (no installed screen reads this section)"]
    lines, line = [], "#   screens read:"
    for i, item in enumerate(items):
        piece = f" {item}" + ("," if i < len(items) - 1 else "")
        if len(line) + len(piece) > 92:
            lines.append(line)
            line = "#    "
        line += piece
    return [*lines, line]


def render_card(data: dict[str, Any], fields: list[Any] | None = None) -> str:
    """A card as commented YAML, every §3 section present, in the canonical order.

    ``data`` holds plain values (strings, lists, dicts) as read from YAML or dumped from a
    :class:`ConceptCard` in JSON mode with aliases. The comments name the fields the
    installed screens read (``fields``, default the system's and the domains'), so the
    skeleton follows the screens (F8).
    """
    fields = fields if fields is not None else screen_fields()
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
        "# layout: where things go, in words",
        *_reads_lines("layout", fields),
        f"layout: {_flow(data.get('layout') or {})}",
        "# envelope: named rough sizes, any name; they seed parameters when this card is chosen",
        *_reads_lines("envelope", fields),
        f"envelope: {_flow(data.get('envelope') or {})}",
        "# site: the space it must fit and what it plugs into; screening checks what its",
        "#   screens read, and these become requirements when chosen",
        *_reads_lines("site", fields),
        f"site: {_flow(data.get('site') or {})}",
        "# style: look and feel,",
        "#   e.g. {preset: appliance, corner_radius: 8 mm, fastener_visibility: hidden-front}",
        f"style: {_flow(data.get('style') or {})}",
        "# modules: the units it is built from and why, when a reason applies (else leave it",
        "#   empty), e.g. {door: {driver: [built-as-unit, serviced-as-unit]}};",
        "#   a massing line joins one with `module: door`",
        f"modules: {_flow(data.get('modules') or {})}",
        "# massing: rough shapes from the kit, one line each, e.g.",
        "#   - {kit: enclosure, as: body, args: {length: 540 mm, width: 540 mm, height: 620 mm}}",
        "#   - {kit: block, as: door, module: door, args: {…}, at: {…}}",
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
