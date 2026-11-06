"""In-place YAML editing of a change request's ``--set`` edits (comments and order kept).

Split from lifecycle.py (S-248). The patch-based ``apply`` step and the sign-off mover that
went with it were removed with schema 2 (S-261): a change request is edited in place.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Protocol

from napkin2factory.core.model import Edit
from napkin2factory.core.product import Paths
from napkin2factory.core.units import UnitError, format_quantity, parse_quantity
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip
from napkin2factory.ecr.state import EcrError


class HasPaths(Protocol):
    """What editing needs of a product: where its files live.

    A loaded product has it; so does the upgrade's stand-in for a folder whose files are not
    readable as a product yet.
    """

    @property
    def paths(self) -> Paths:
        """The folder's file locations."""
        ...


def _set_in_yaml(product: HasPaths, edit: Edit) -> str:
    """Apply one edit to the right YAML file in place; return a human line."""
    u = edit.set
    if u.scheme == "param":
        path = product.paths.parameters
        data = load_roundtrip(path)
        params = data.setdefault("parameters", {})
        if u.id not in params:
            raise EcrError(f"param://{u.id} does not exist")
        entry = params[u.id]
        unit = entry.get("unit", "") or None
        try:
            q = parse_quantity(str(edit.to), unit)
            value: Any = q.to(unit).magnitude if unit else q.magnitude
        except Exception as exc:
            raise EcrError(f"cannot set param://{u.id} to {edit.to!r}: {exc}") from exc
        if "expr" in entry:
            raise EcrError(
                f"param://{u.id} is an expression ({entry['expr']}); "
                "set the parameters it depends on instead"
            )
        old = entry.get("value")
        new_value = int(value) if float(value).is_integer() else float(value)
        if not _edit_param_line(path, u.id, new_value):
            entry["value"] = new_value
            dump_roundtrip(path, data)
        return f"param://{u.id}: {old} → {new_value} {unit or ''}".strip()
    # selector edits on requirements, parts, assemblies, interfaces, decisions
    if u.scheme == "req":
        path = product.paths.requirements
        data = load_roundtrip(path)
        target = next((r for r in data.get("requirements", []) if r.get("id") == u.id), None)
    elif u.scheme == "dec":
        path = product.paths.decisions
        data = load_roundtrip(path)
        target = next((d for d in data.get("decisions", []) if d.get("id") == u.id), None)
    elif u.scheme in ("part", "asm", "iface"):
        folder = {
            "part": product.paths.parts,
            "asm": product.paths.assemblies,
            "iface": product.paths.interfaces,
        }[u.scheme]
        path = folder / f"{u.id}.yaml"
        data = load_roundtrip(path)
        target = data
    else:
        raise EcrError(
            f"edits cannot target {u.scheme}:// ({u}); supported: param, req, part, asm, iface, dec"
        )
    if target is None:
        raise EcrError(f"{u.base} does not exist")
    cur: Any = target
    for key in u.selector[:-1]:
        if key not in cur or cur[key] is None:
            cur[key] = {}
        cur = cur[key]
    last = u.selector[-1]
    old = cur.get(last) if isinstance(cur, dict) else None
    cur[last] = _coerce(edit.to, old)
    dump_roundtrip(path, data)
    return f"{u}: {old!r} → {cur[last]!r}"


def _edit_param_line(path: Path, slug: str, value: Any) -> bool:
    """Change ``value:`` on the parameter's own line, touching nothing else (one-line diff).

    Works for the flow-mapping style ``n2f init`` writes (``slug: {value: 1, unit: mm}``);
    returns False when the parameter is written in block style, so the caller falls back
    to a ruamel round-trip.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    pat = re.compile(
        rf"^(\s*{re.escape(slug)}\s*:\s*\{{.*?)(value\s*:\s*)([-+0-9.eE]+)(.*)$", re.DOTALL
    )
    for i, line in enumerate(lines):
        m = pat.match(line)
        if m:
            lines[i] = f"{m.group(1)}{m.group(2)}{value}{m.group(4)}"
            path.write_text("".join(lines), encoding="utf-8")
            return True
    return False


def _coerce(value: Any, old: Any) -> Any:
    """Keep the field's type where obvious: numbers stay numbers, quantities stay strings."""
    if isinstance(old, bool):
        return str(value).lower() in ("true", "yes", "1")
    if isinstance(old, (int, float)) and not isinstance(value, (int, float)):
        try:
            f = float(str(value).split()[0])
            return int(f) if f.is_integer() and isinstance(old, int) else f
        except ValueError:
            return value
    if isinstance(value, str):
        try:
            q = parse_quantity(value)
            return format_quantity(q) if not q.dimensionless else value
        except UnitError:
            return value
    return value


__all__ = [
    "HasPaths",
    "_coerce",
    "_edit_param_line",
    "_set_in_yaml",
]
