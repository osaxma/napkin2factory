"""Helpers every seeder shares: what was seeded, quantities as text, appending YAML items."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from napkin2factory.core.model.concepts import LabelledValue
from napkin2factory.core.units import format_quantity, parse_quantity
from napkin2factory.core.uris import SLUG

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
    about: str  # space | supply | weight | form | budget (a module size, P10)
    data: dict[str, Any] = field(default_factory=dict)


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" + ("" if n == 1 else "s")


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" and {items[-1]}"


def _num(x: float) -> str:
    """A magnitude for YAML: integers without a decimal point, else up to 6 digits."""
    return str(int(round(x))) if abs(x - round(x)) < 1e-9 else f"{x:.6g}"


def _q_text(q: Any) -> str:
    return format_quantity(q)


def display_units(root: Path | None) -> str:
    """The product's display units (``metric`` or ``imperial``, ``n2f.yaml`` ``units``, S-219)."""
    manifest = Path(root) / "n2f.yaml" if root is not None else None
    if manifest is None or not manifest.is_file():
        return "metric"
    try:
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return "metric"
    return "imperial" if isinstance(data, dict) and data.get("units") == "imperial" else "metric"


def _shown(q: Any, units: str) -> str:
    """A quantity in the owner's words: the display units, rounded by the display rules.

    The stored bound stays exact in the model's units; only the statement a person reads
    uses this: ``150 lb``, never ``68.0389 kg``. The metric figure in brackets that the
    report adds is left out, since it is the unrounded number (B-0230).
    """
    from napkin2factory.report.units import display

    text = display(q, units)
    return re.sub(r" \([^()]*\)$", "", text) if units == "imperial" else text


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
    """Append list items under the top-level ``key:`` (an empty ``key: []`` is opened).

    With nothing to append the text is left as it is: opening ``requirements: []`` with no
    item under it would read as ``None`` (gate C, C4).
    """
    if not blocks:
        return text
    text = re.sub(rf"^{key}:\s*\[\]\s*$", f"{key}:", text, count=1, flags=re.MULTILINE)
    if not text.endswith("\n"):
        text += "\n"
    return text + "".join(blocks)


def _yaml_scalar(text: str) -> str:
    """A name as one YAML scalar (quoted only when YAML would read it otherwise)."""
    return yaml.safe_dump(text, allow_unicode=True, width=10**6).strip().removesuffix("\n...")


def _next_id(prefix: str, existing: list[str]) -> str:
    nums = [int(m.group(1)) for x in existing if (m := re.fullmatch(rf"{prefix}-(\d{{3}})", x))]
    return f"{prefix}-{max(nums, default=0) + 1:03d}"


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def held_requirement(held: Any, verify: dict[str, Any]) -> str | None:
    """The id of a requirement the model already holds that asks what ``verify`` asks.

    "Already asks" means the same verify target, operator and value, the values compared as
    quantities (``0.2 m`` equals ``200 mm``); a requirement without a target (a manual one)
    is never matched (S-277).

    Args:
        held: the model's requirements (``Product.requirements``: id -> Requirement).
        verify: the planned requirement's ``verify`` mapping.
    """
    from napkin2factory.core.units import UnitError, parse_quantity

    target, op, value = verify.get("target"), verify.get("op"), verify.get("value")
    if target is None or op is None or value is None:
        return None
    try:
        want = parse_quantity(value)
    except UnitError:
        return None
    for rid, req in held.items():
        v = req.verify
        if v is None or v.target is None or str(v.target) != str(target) or v.op != op:
            continue
        try:
            if v.value is not None and v.value == want:
                return str(rid)
        except Exception:  # noqa: BLE001 — units that do not compare are not the same ask
            continue
    return None
