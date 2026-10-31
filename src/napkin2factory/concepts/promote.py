"""``n2f concept promote``: the chosen concept becomes model content (NAPKIN_STAGE N8).

Promotion is the bridge from the napkin stage to the factory and the arbitration event
between directions. In this order, **all or nothing** (every edit is computed in memory and
validated before the first byte is written; a refusal writes nothing):

1. **Gates** — the card was built (it has a screening); green, or red with ``--override``
   and ``--reason``; no other card is promoted. Refusals raise
   :class:`~napkin2factory.core.errors.GateBlocked` (exit 3).
2. **Parameters** — ``envelope`` numbers seed ``model/parameters.yaml`` (``owner:
   napkin``): a quantity becomes one parameter, a 3-list ``<key>-width/-depth/-height``,
   another list ``<key>-1..n``, a list of named layers ``<layer>-thickness`` (and
   ``-clearance``); ``power`` seeds ``element-power``. A parameter already declared with
   the same value is left alone ("already declared"); a different value refuses the whole
   promotion unless ``--override`` (then it is overwritten and listed in the decision).
3. **Site constraints → requirements** — the alcove (width with the door-swing term,
   depth, height), the supply circuit and a mass limit become ordinary ``req://`` rows
   allocated to the top assembly, so DEC-011 cannot happen again.
4. **Form requirements** — style and layout choices become requirements verified by the
   ``form-v0`` rule pack (``verify: {kind: rule, target: rule://form-v0/<rule>}``).
5. **style.yaml** — the card's ``style`` keys (and its ``layout``) override the product's.
6. **The decision** — one ``DEC-`` entry with every sibling attached as a rejected
   alternative.
7. **Cards** — the chosen card becomes ``promoted``; exploring siblings ``rejected``.
8. **Snapshot** — ``Promote C-00x: <title>`` (napkin verbs otherwise never snapshot, S-062).

Model files are edited as text where that keeps the owner's formatting (new parameters,
requirements and decisions are appended in the files' own style; an overwritten parameter
is a one-line change); ``style.yaml`` and the cards go through ruamel round-trip, so
comments and key order survive.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from napkin2factory.core import concepts as cm
from napkin2factory.core.errors import GateBlocked, N2FError
from napkin2factory.core.model.concepts import ConceptCard, LabelledValue
from napkin2factory.core.model.style import PRESETS, StyleFile
from napkin2factory.core.units import format_quantity, is_quantity, parse_quantity
from napkin2factory.core.uris import SLUG
from napkin2factory.rulepacks.concept_checks import circuit_headroom, parse_circuit

#: ``owner`` of every seeded parameter.
SEED_OWNER = "napkin"
#: Envelope keys that seed a parameter under another name (the kiln's names, M6 retrofit).
PARAM_ALIASES: dict[str, str] = {"power": "element-power"}
#: Suffixes of a three-value envelope entry.
AXIS_SUFFIXES: tuple[str, str, str] = ("width", "depth", "height")
#: The rule pack the form requirements point at.
FORM_PACK = "form-v0"
#: Screening values quoted in the decision's rationale, in this order.
RATIONALE_KEYS: tuple[str, ...] = (
    "width",
    "depth",
    "height",
    "footprint_with_door_swing",
    "mass",
    "total_mass",
    "heat_up_time",
    "power",
    "required_power",
    "current",
    "circuit_class",
    "cost_low",
    "cost_high",
    "lift_class",
)
STYLE_HEADER = (
    "# style.yaml: how the product looks (preset, colours and finishes by part role, shape cues).\n"
    "# Filled from the chosen concept by `n2f concept promote`; you may also edit it by hand.\n"
)
_SLUG_RE = re.compile(rf"^{SLUG}$")


@dataclass
class SeededParam:
    """One parameter promotion seeded, found already declared, or overwrote."""

    name: str
    value: str
    status: str  # new | declared | overwritten
    was: str | None = None
    source: str = ""


@dataclass
class NewRequirement:
    """One requirement promotion wrote."""

    id: str
    title: str
    about: str  # alcove | supply | weight | form
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class PromotionResult:
    """What ``n2f concept promote`` did (or, with ``dry_run``, would do)."""

    card_id: str
    title: str
    dec_id: str
    override: bool
    params: list[SeededParam] = field(default_factory=list)
    requirements: list[NewRequirement] = field(default_factory=list)
    style_file: str = "style.yaml"
    style_created: bool = False
    rejected: list[str] = field(default_factory=list)
    already_rejected: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    snapshot: str | None = None
    files: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """The owner's line: what changed, what was kept, what to do next."""
        new = [p for p in self.params if p.status == "new"]
        declared = [p for p in self.params if p.status == "declared"]
        over = [p for p in self.params if p.status == "overwritten"]
        extra = []
        if declared:
            extra.append(f"{len(declared)} already declared")
        if over:
            extra.append(f"{len(over)} overwritten")
        params = f"Seeded {_count(len(new), 'parameter')}" + (
            f" ({', '.join(extra)})" if extra else ""
        )
        abouts: dict[str, int] = {}
        for r in self.requirements:
            abouts[r.about] = abouts.get(r.about, 0) + 1
        order = ("form", "alcove", "supply", "weight")
        parts = [f"{abouts[a]} about {_ABOUT_WORDS[a]}" for a in order if a in abouts]
        reqs = _count(len(self.requirements), "requirement") + (
            f" ({', '.join(parts)})" if parts else ""
        )
        style = "wrote style.yaml" if self.style_created else "updated style.yaml"
        line = (
            f"{self.card_id} is now the design direction ({self.dec_id}). {params}, {reqs}, {style}"
        )
        if self.rejected:
            names = _and(self.rejected)
            verb = "is" if len(self.rejected) == 1 else "are"
            noun = "alternative" if len(self.rejected) == 1 else "alternatives"
            line += f"; {names} {verb} kept as rejected {noun}"
        return line + ". Next: `n2f build && n2f check`."

    def to_dict(self) -> dict[str, Any]:
        """JSON form for ``--json``: every id."""
        return {
            "id": self.card_id,
            "title": self.title,
            "dec": self.dec_id,
            "override": self.override,
            "parameters": [
                {
                    "uri": f"param://{p.name}",
                    "value": p.value,
                    "status": p.status,
                    "was": p.was,
                    "from": p.source,
                }
                for p in self.params
            ],
            "requirements": [
                {
                    "uri": f"req://{r.id}",
                    "title": r.title,
                    "about": r.about,
                    "verify": r.data.get("verify"),
                }
                for r in self.requirements
            ],
            "style": {"file": self.style_file, "created": self.style_created},
            "rejected": self.rejected,
            "already_rejected": self.already_rejected,
            "snapshot": self.snapshot,
            "files": self.files,
            "notes": self.notes,
            "summary": self.summary(),
        }


_ABOUT_WORDS = {
    "form": "form",
    "alcove": "the alcove",
    "supply": "the supply",
    "weight": "the weight",
}


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" + ("" if n == 1 else "s")


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" and {items[-1]}"


# --- small helpers --------------------------------------------------------------------


def _num(x: float) -> str:
    """A magnitude for YAML: integers without a decimal point, else up to 6 digits."""
    return str(int(round(x))) if abs(x - round(x)) < 1e-9 else f"{x:.6g}"


def _q_text(q: Any) -> str:
    return format_quantity(q)


def _split(q: Any) -> tuple[float | int, str]:
    text = format_quantity(q)
    mag, _, unit = text.partition(" ")
    f = float(mag)
    return (int(f) if f.is_integer() else f), unit


def _same(a: Any, b: Any) -> bool:
    try:
        bb = b.to(a.units)
    except Exception:  # pint DimensionalityError: different kinds of quantity
        return False
    x, y = float(a.magnitude), float(bb.magnitude)
    return abs(x - y) <= 1e-9 * max(1.0, abs(x), abs(y))


def _lv_quantity(lv: LabelledValue | None) -> Any:
    if lv is None:
        return None
    try:
        return parse_quantity(lv.value)
    except Exception:  # a word ("16 A socket") is not a quantity
        return None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")


def _yaml_block(entry: dict[str, Any], indent: str) -> str:
    """One list item as YAML text in the model files' style (flow leaves, ``- id:`` first)."""
    body = yaml.safe_dump(
        [entry], sort_keys=False, default_flow_style=None, allow_unicode=True, width=100
    )
    return "".join(f"{indent}{line}\n" for line in body.splitlines())


def _list_indent(text: str, key: str) -> str:
    """The indentation of the first ``- id:`` item under ``key:`` (two spaces by default)."""
    m = re.search(r"^(\s*)- id:", text, re.MULTILINE)
    return m.group(1) if m else "  "


def _append_items(text: str, key: str, blocks: list[str]) -> str:
    """Append list items under the top-level ``key:`` (an empty ``key: []`` is opened)."""
    text = re.sub(rf"^{key}:\s*\[\]\s*$", f"{key}:", text, count=1, flags=re.MULTILINE)
    if not text.endswith("\n"):
        text += "\n"
    return text + "".join(blocks)


# --- step 2: parameters ---------------------------------------------------------------


def seed_plan(card: ConceptCard, notes: list[str]) -> list[tuple[str, Any, str]]:
    """``(parameter name, quantity, envelope source)`` for every envelope number."""
    plan: list[tuple[str, Any, str]] = []
    for key, value in card.envelope.items():
        base = PARAM_ALIASES.get(key, _slug(key))
        if not _SLUG_RE.match(base):
            notes.append(f"envelope.{key}: not usable as a parameter name; not seeded")
            continue
        if is_quantity(value):
            plan.append((base, value, f"envelope.{key}"))
        elif isinstance(value, list) and value and all(is_quantity(v) for v in value):
            names = (
                [f"{base}-{s}" for s in AXIS_SUFFIXES]
                if len(value) == 3
                else [f"{base}-{i + 1}" for i in range(len(value))]
            )
            for i, (name, v) in enumerate(zip(names, value, strict=True)):
                plan.append((name, v, f"envelope.{key}[{i}]"))
        elif isinstance(value, list) and all(isinstance(v, dict) for v in value):
            skipped: set[str] = set()
            for i, layer in enumerate(value):
                name = _slug(str(layer.get("name") or f"{base}-{i + 1}"))
                for prop in ("thickness", "clearance"):
                    q = layer.get(prop)
                    if is_quantity(q):
                        plan.append((f"{name}-{prop}", q, f"envelope.{key}[{i}].{prop}"))
                skipped |= {k for k in layer if k not in ("name", "thickness", "clearance")}
            if skipped:
                notes.append(
                    f"envelope.{key}: layer {', '.join(sorted(skipped))} stay on the card "
                    "(screening values), not seeded as parameters"
                )
        else:
            notes.append(f"envelope.{key}: not a quantity or a list of them; not seeded")
    return plan


_PARAM_LINE = r"^(\s*{slug}\s*:\s*\{{.*?)(value\s*:\s*)([-+0-9.eE]+)(.*)$"


def _edit_param_value(text: str, slug: str, value: str) -> str | None:
    """Change ``value:`` on the parameter's own flow line (``_edit_param_line``'s pattern)."""
    pat = re.compile(_PARAM_LINE.format(slug=re.escape(slug)))
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = pat.match(line)
        if m:
            lines[i] = f"{m.group(1)}{m.group(2)}{value}{m.group(4)}"
            return "".join(lines)
    return None


def plan_parameters(
    card: ConceptCard, product: Any, text: str, override: bool, notes: list[str]
) -> tuple[list[SeededParam], str, list[str]]:
    """Seeded parameters, the new ``parameters.yaml`` text, and refusals (collisions)."""
    seeded: list[SeededParam] = []
    conflicts: list[str] = []
    new_lines: list[str] = []
    for name, q, source in seed_plan(card, notes):
        value_text = _q_text(q)
        if name in product.parameters:
            declared = product.parameters[name]
            try:
                current = product.parameter_value(name)
            except Exception as exc:  # an expression that does not evaluate
                conflicts.append(f"{name} cannot be read in the model ({exc})")
                continue
            if _same(current, q):
                seeded.append(SeededParam(name, value_text, "declared", source=source))
                continue
            was = _q_text(current)
            if not override:
                conflicts.append(f"{name} is {was} in the model but {value_text} on {card.id}")
                continue
            if declared.expr is not None:
                conflicts.append(
                    f"{name} is computed by an expression ({declared.expr}), so it cannot be "
                    "overwritten; change the card or the expression by hand"
                )
                continue
            unit = declared.unit or None
            converted = q.to(unit) if unit else q
            edited = _edit_param_value(text, name, _num(float(converted.magnitude)))
            if edited is None:
                conflicts.append(
                    f"{name} is not written as one line ({{value: …, unit: …}}), so it "
                    "cannot be overwritten safely; change it by hand"
                )
                continue
            text = edited
            seeded.append(SeededParam(name, value_text, "overwritten", was=was, source=source))
            continue
        mag, unit = _split(q)
        entry = {
            name: {
                "value": mag,
                "unit": unit,
                "description": f"from concept {card.id}",
                "owner": SEED_OWNER,
            }
        }
        line = yaml.safe_dump(
            entry, sort_keys=False, default_flow_style=None, allow_unicode=True, width=10**6
        )
        new_lines.append(line)
        seeded.append(SeededParam(name, value_text, "new", source=source))
    if new_lines:
        m = re.search(r"^(\s+)[a-z0-9][a-z0-9-]*\s*:", text, re.MULTILINE)
        indent = m.group(1) if m else "  "
        text = re.sub(r"^parameters:\s*\{\}\s*$", "parameters:", text, count=1, flags=re.M)
        if not text.endswith("\n"):
            text += "\n"
        text += f"{indent}# --- from concept {card.id} (n2f concept promote) ---\n"
        text += "".join(f"{indent}{ln}" for ln in new_lines)
    return seeded, text, conflicts


# --- step 3: site constraints -----------------------------------------------------------


def _site_length(card: ConceptCard, key: str) -> Any:
    v: Any = card.site.get(key)
    if is_quantity(v):
        try:
            return v.to("mm")
        except Exception:  # pint DimensionalityError: not a length
            return None
    return None


def door_swing_term(card: ConceptCard) -> tuple[Any, str]:
    """The screening's computed door-swing term (mm) and its basis.

    ``footprint_with_door_swing − width`` from the card's computed values (0 when the door
    is not hinged); the basis is the footprint's ``source`` text.
    """
    from napkin2factory.core.units import Quantity

    sc = card.screening
    assert sc is not None
    foot = sc.computed.get("footprint_with_door_swing")
    width = _lv_quantity(sc.computed.get("width"))
    footq = _lv_quantity(foot)
    if foot is None or width is None or footq is None:
        return Quantity(0.0, "mm"), "no footprint in the screening: no door swing counted"
    term = (footq - width).to("mm")
    basis = foot.source.removeprefix("width + open door (").removesuffix(")")
    return term, basis


def site_requirements(
    card: ConceptCard,
    seeded: list[SeededParam],
    top: str | None,
    notes: list[str],
) -> list[tuple[str, dict[str, Any]]]:
    """``(about, requirement fields)`` for each site constraint on the card."""
    from napkin2factory.core.units import Quantity

    src = f"concept {card.id} site constraint"
    allocation: Any = [f"asm://{top}"] if top else "unallocated"
    out: list[tuple[str, dict[str, Any]]] = []

    def geometry(axis: str, op: str, value: Any) -> dict[str, Any]:
        if top is None:
            return {
                "kind": "manual",
                "note": "there is no assembly yet: check this against the built product, "
                "or re-target it at the top assembly once it exists",
            }
        return {
            "kind": "geometry_prop",
            "target": f"asm://{top}#props.{axis}",
            "op": op,
            "value": _q_text(value),
        }

    width = _site_length(card, "alcove_width")
    if width is not None:
        term, basis = door_swing_term(card)
        limit = (width - term).to("mm")
        term_mm = float(term.magnitude)
        swing = (
            f"the door swing of {_q_text(term)}"
            if term_mm > 0
            else "no door swing (the door does not open sideways)"
        )
        out.append(
            (
                "alcove",
                {
                    "title": "Fits the alcove with the door open",
                    "statement": f"The closed width plus {swing} stays within the "
                    f"{_q_text(width)} alcove.",
                    "category": "geometry",
                    "verify": geometry("bbox.x", "<=", limit),
                    "rationale": f"Door-swing term {_q_text(term)} (computed by screening: "
                    f"{basis}); {_q_text(width)} − {_q_text(term)} = {_q_text(limit)} for the "
                    "closed width.",
                },
            )
        )
    for key, axis, word in (
        ("alcove_depth", "bbox.y", "deep"),
        ("alcove_height", "bbox.z", "tall"),
    ):
        limit = _site_length(card, key)
        if limit is None:
            continue
        out.append(
            (
                "alcove",
                {
                    "title": f"Fits the alcove {key.removeprefix('alcove_')}",
                    "statement": f"The assembled product is at most {_q_text(limit)} {word}.",
                    "category": "geometry",
                    "verify": geometry(axis, "<=", limit),
                    "rationale": f"site.{key} on {card.id}.",
                },
            )
        )
    circuit = card.site.get("circuit")
    if circuit is not None:
        parsed = parse_circuit(circuit) if isinstance(circuit, str) else None
        power = next((p for p in seeded if p.name == PARAM_ALIASES["power"]), None)
        if parsed is None:
            notes.append(
                f"site.circuit {circuit!r} is not like 240V-13A: no supply requirement written"
            )
        elif power is None:
            notes.append(
                "no power on the card (envelope.power): no supply requirement written — "
                "add one once the element power is known"
            )
        else:
            volts, amps = parsed
            # One margin for the napkin and the factory (review gate A, B1): the bound is
            # read from rule circuit-available's `headroom`, the number screening used, so a
            # green circuit row cannot become a failing requirement on the same inputs.
            headroom = circuit_headroom()
            raw = float((volts * amps).to("W").magnitude) / headroom
            # rounded *up* to 0.1 W so a card exactly at the screening limit still passes
            limit = Quantity(math.ceil(round(raw * 10, 6)) / 10, "W")
            out.append(
                (
                    "supply",
                    {
                        "title": "Runs on the site circuit",
                        "statement": f"The element power is at most {_q_text(limit)}, so the "
                        f"{circuit} site circuit keeps a {headroom:g} headroom.",
                        "category": "performance",
                        "verify": {
                            "kind": "param_bound",
                            "target": f"param://{power.name}",
                            "op": "<=",
                            "value": _q_text(limit),
                        },
                        "allocation": [f"param://{power.name}"] + ([f"asm://{top}"] if top else []),
                        "rationale": f"{_q_text(volts)} × {_q_text(amps)} / {headroom:g}: the "
                        f"same {headroom:g} headroom screening used (rule circuit-available); "
                        "the NEC 210.20 continuous-load factor 1.25 is stricter [verify].",
                    },
                )
            )
    elif card.site.get("region") is not None and any(p.name == "element-power" for p in seeded):
        notes.append(
            f"site.region {card.site['region']} but no site.circuit: no supply requirement "
            "written — add site.circuit (e.g. 230V-16A) once the socket is known"
        )
    mass_limit: Any = card.site.get("mass_limit")
    basis = f"site.mass_limit on {card.id}"
    if not is_quantity(mass_limit) and isinstance(card.site.get("lift_class"), str):
        from napkin2factory.calckit import load_table

        row = next(
            (r for r in load_table("lift_classes") if r["label"] == card.site["lift_class"]),
            None,
        )
        if row is not None and row.get("max_kg") is not None:
            mass_limit = Quantity(float(row["max_kg"]), "kg")
            basis = f"site.lift_class {row['label']} (HSE guideline weight) [verify]"
    if is_quantity(mass_limit):
        try:
            kg = mass_limit.to("kg")
        except Exception:  # pint DimensionalityError
            notes.append(f"site.mass_limit {mass_limit} is not a mass: no weight requirement")
        else:
            out.append(
                (
                    "weight",
                    {
                        "title": "Light enough to move as planned",
                        "statement": f"The assembled product weighs less than {_q_text(kg)}.",
                        "category": "mass",
                        "verify": geometry("mass", "<", kg),
                        "rationale": basis + ".",
                    },
                )
            )
    for _, data in out:
        data.setdefault("allocation", allocation)
        data["source"] = src
    if top is None and out:
        notes.append(
            "the product has no assembly yet: site requirements are allocated `unallocated` "
            "and checked by a person until an assembly exists"
        )
    return out


# --- step 4: form requirements ----------------------------------------------------------


def form_requirements(
    card: ConceptCard, style: StyleFile, top: str | None, notes: list[str]
) -> list[tuple[str, dict[str, Any]]]:
    """Form requirements from the merged style and the card's layout (the template library)."""
    src = f"concept {card.id} style"
    allocation: Any = [f"asm://{top}"] if top else "unallocated"
    out: list[tuple[str, dict[str, Any]]] = []

    def rule(rule_id: str) -> dict[str, Any]:
        return {"kind": "rule", "target": f"rule://{FORM_PACK}/{rule_id}"}

    radius = style.corner_radius
    if float(radius.to("mm").magnitude) > 0:
        out.append(
            (
                "form",
                {
                    "title": "Rounded exposed corners",
                    "statement": "Exposed bends and corners of the body, door, stand, controls "
                    f"and trim have a radius of at least {_q_text(radius)}.",
                    "category": "geometry",
                    "verify": rule("form-corner-radius"),
                    "rationale": f"Chosen with {card.id} (style corner_radius "
                    f"{_q_text(radius)}); the threshold lives in style.yaml.",
                },
            )
        )
    if style.fastener_visibility == "hidden-front":
        out.append(
            (
                "form",
                {
                    "title": "No visible fasteners on the front",
                    "statement": "No fastener holes show on the front face of the body or "
                    "the door.",
                    "category": "usability",
                    "verify": rule("form-fasteners-hidden-front"),
                    "rationale": f"Chosen with {card.id} (style fastener_visibility hidden-front).",
                },
            )
        )
    controls = str(card.layout.get("controls", "")).strip()
    if controls:
        out.append(
            (
                "form",
                {
                    "title": "Controls where they were sketched",
                    "statement": f"The controls sit {controls.replace('-', ' ')} on the "
                    f"product, as on {card.id}.",
                    "category": "usability",
                    "priority": "should",
                    "verify": rule("form-controls-placement"),
                    "rationale": f"Layout chosen with {card.id} (layout.controls {controls}); "
                    "a misplaced control is a warning, never a failure.",
                },
            )
        )
    if len(out) < 2:
        why = []
        if float(radius.to("mm").magnitude) <= 0:
            why.append("no corner radius")
        if style.fastener_visibility != "hidden-front":
            why.append(f"fasteners {style.fastener_visibility}")
        if not controls:
            why.append("no controls placement in the layout")
        notes.append(
            f"only {_count(len(out), 'form requirement')} applies: the style chose "
            f"{', '.join(why)} — add corner_radius or fastener_visibility: hidden-front to "
            "the card's style for more"
        )
    for _, data in out:
        data["allocation"] = allocation
        data["source"] = src
    return out


# --- step 5: style.yaml -----------------------------------------------------------------


def _plain(value: Any) -> Any:
    return format_quantity(value) if is_quantity(value) else value


def plan_style(card: ConceptCard, root: Path, notes: list[str]) -> tuple[str, StyleFile, bool]:
    """The new ``style.yaml`` text, the resolved style it gives, and whether it is new.

    The card's ``style`` keys override the file's (``palette``/``finish`` per role) and its
    ``layout`` is recorded. When the card names a different preset, the file's values that
    still equal the old preset's take the new preset's (so the product looks like the
    pictures on the board); hand-edited values are kept and noted.
    """
    from ruamel.yaml.comments import CommentedMap

    from napkin2factory.core.style import style_path
    from napkin2factory.core.yamlio import dumps_roundtrip, load_roundtrip

    path = style_path(root)
    created = not path.is_file()
    fields = set(StyleFile.model_fields)
    card_style = {k: v for k, v in card.style.items() if k in fields}
    unknown = sorted(k for k in card.style if k not in fields)
    if unknown:
        notes.append(f"card style keys not used: {', '.join(unknown)}")
    if created:
        preset = str(card_style.get("preset", "industrial"))
        if preset not in PRESETS:
            raise N2FError(f"{card.id}: style preset {preset!r} is not one of {', '.join(PRESETS)}")
        doc: Any = CommentedMap(
            StyleFile.model_validate({"preset": preset}).resolved().model_dump(mode="json")
        )
        doc.pop("layout", None)
    else:
        doc = load_roundtrip(path)
        if not isinstance(doc, dict):
            raise N2FError("style.yaml is not a mapping; fix it (or delete it) and promote again")
        old = str(doc.get("preset", "industrial"))
        new = str(card_style.get("preset", old))
        if new != old and new in PRESETS and old in PRESETS:
            kept: list[str] = []
            for key in list(doc):
                if key in ("preset", "layout") or key not in PRESETS[old]:
                    continue
                if key in ("palette", "finish") and isinstance(doc[key], dict):
                    for role in list(doc[key]):
                        if str(doc[key][role]).lower() == str(PRESETS[old][key].get(role)).lower():
                            doc[key][role] = PRESETS[new][key].get(role)
                        else:
                            kept.append(f"{key}.{role}")
                elif str(_plain(doc[key])) == str(PRESETS[old][key]):
                    doc[key] = PRESETS[new][key]
                else:
                    kept.append(key)
            if kept:
                notes.append(
                    f"style.yaml moved from the {old} to the {new} preset; kept your own "
                    f"{', '.join(kept)}"
                )
    for key, value in card_style.items():
        if key in ("palette", "finish") and isinstance(value, dict):
            sub = doc.get(key)
            if not isinstance(sub, dict):
                sub = CommentedMap()
                doc[key] = sub
            for role, v in value.items():
                sub[role] = v
        else:
            doc[key] = _plain(value)
    if card.layout:
        flow = CommentedMap(card.layout)
        flow.fa.set_flow_style()
        doc["layout"] = flow
    text = dumps_roundtrip(doc, explicit_null=True)
    if created:
        text = STYLE_HEADER + f"# Seeded from concept {card.id}.\n" + text
    try:
        style = StyleFile.model_validate(yaml.safe_load(text) or {}).resolved()
    except Exception as exc:
        raise N2FError(
            f"{card.id}: its style does not fit style.yaml ({exc}); fix the card's `style:` "
            "and promote again"
        ) from exc
    return text, style, created


# --- step 7: cards ------------------------------------------------------------------------


def _card_text(root: Path, card_id: str, status: str, decision: dict[str, Any]) -> str:
    """The card file with ``status`` and ``decision`` set (comments and order kept)."""
    from ruamel.yaml.comments import CommentedMap

    from napkin2factory.core.yamlio import dumps_roundtrip, load_roundtrip, read_yaml

    path = cm.card_path(root, card_id)
    ConceptCard.model_validate({**read_yaml(path), "status": status, "decision": decision})
    doc = load_roundtrip(path)
    doc["status"] = status
    flow = CommentedMap(decision)
    flow.fa.set_flow_style()
    doc["decision"] = flow
    return dumps_roundtrip(doc, explicit_null=True)


# --- step 6: the decision ----------------------------------------------------------------


def _one_line(card: ConceptCard) -> str:
    from napkin2factory.concepts.build import summary_line

    if card.screening is None or card.verdict is None:
        return "not built"
    if card.verdict == "red":
        return "red: " + "; ".join(r.message for r in card.screening.failing)
    return "green: " + summary_line(card, card.screening)


def _labelled(card: ConceptCard) -> list[str]:
    sc = card.screening
    assert sc is not None
    values = sc.values
    out = []
    for key in RATIONALE_KEYS:
        lv = values.get(key)
        if lv is not None:
            out.append(f"{key.replace('_', ' ')} {lv.value} ({lv.label})")
    return out


# --- the verb ----------------------------------------------------------------------------


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


def _next_id(prefix: str, existing: list[str]) -> str:
    nums = [int(m.group(1)) for x in existing if (m := re.fullmatch(rf"{prefix}-(\d{{3}})", x))]
    return f"{prefix}-{max(nums, default=0) + 1:03d}"


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
            "promotion is a change request (`n2f ecr new --kind design --title …`)"
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
    # 3 + 4. requirements
    top = _top_assembly(product, notes)
    planned = site_requirements(card, seeded, top, notes) + form_requirements(
        card, style, top, notes
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
        f'{c.id} "{c.title}" ({_one_line(c)})'
        + (
            f" — set aside earlier: {c.decision.reason}"
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
    rationale = (
        f"Screening of {cid} ({card.verdict}): " + "; ".join(_labelled(card)) + "."
        if _labelled(card)
        else f"Screening of {cid} ({card.verdict})."
    )
    links = [f"req://{r.id}" for r in new_reqs] + [f"param://{p.name}" for p in seeded]
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
                {"reason": f"not chosen: {cid} promoted ({dec_id})", "at": at},
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


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _check_texts(params: str, reqs: str, decs: str, n_reqs: int) -> None:
    """Each edited model file still parses into its schema (and nothing was lost)."""
    from napkin2factory.core.model import DecisionsFile
    from napkin2factory.core.model.parameters import ParametersFile
    from napkin2factory.core.model.requirements import RequirementsFile

    try:
        ParametersFile.model_validate(yaml.safe_load(params) or {})
        rf = RequirementsFile.model_validate(yaml.safe_load(reqs) or {})
        DecisionsFile.model_validate(yaml.safe_load(decs) or {})
    except Exception as exc:
        raise N2FError(
            f"promotion could not edit the model files cleanly ({exc}); nothing was written"
        ) from exc
    if len(rf.requirements) != n_reqs:
        raise N2FError(
            "promotion could not append to model/requirements.yaml in its layout; nothing "
            "was written — check that `requirements:` is the file's only top-level key"
        )


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


__all__ = [
    "NewRequirement",
    "PromotionResult",
    "SeededParam",
    "door_swing_term",
    "form_requirements",
    "plan_parameters",
    "plan_style",
    "promote",
    "seed_plan",
    "site_requirements",
]
