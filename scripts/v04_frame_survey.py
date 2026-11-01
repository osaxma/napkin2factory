"""Survey every interface's two frames in the world, after a build (v0.4 M0, S-105).

For each interface of a built product this prints, from the top assembly's
``build/assemblies/<top>/instances.json`` (leaves there are already in the top assembly's
world frame, the door's group transform included: ``geometry/assembly.py::flatten``):

* each party's world frame: origin, normal and x axis, using the same basis the holes are
  cut with (``geometry/kit/hole_pattern.py::frame_basis``) and the frames resolved through
  ``geometry/accessors.py::resolve_interface``;
* whether the two normals point the same way in the world (the P1 convention of
  ``PRODUCT_STRUCTURE.md``) or face each other, and whether the x axes agree;
* the signed offset along the first party's normal from the first party's origin to the
  second's, and the in-plane miss between the two origins;
* the worst in-plane miss between the two parties' hole centres (nearest-neighbour pairing),
  which catches an x-axis disagreement that a symmetric pattern hides;
* whether each frame names its ``x_axis`` explicitly.

Not part of the package and not run by CI: M1's alignment check replaces it. Kept as the
reference for M1's test vectors.

Usage::

    uv run python scripts/v04_frame_survey.py --fresh examples/kiln     # copy, build, survey
    uv run python scripts/v04_frame_survey.py path/to/built/product     # survey a built copy
    uv run python scripts/v04_frame_survey.py --json ...                # machine-readable
    uv run python scripts/v04_frame_survey.py --lines examples/kiln     # placement line count
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from napkin2factory.core.loader import load_product
from napkin2factory.geometry.accessors import resolve_interface
from napkin2factory.geometry.kit.hole_pattern import centers_from_spec, frame_basis

Vec3 = tuple[float, float, float]


def _rotate(q: list[float], v: Vec3) -> Vec3:
    """Rotate ``v`` by the unit quaternion ``q`` (x, y, z, w)."""
    x, y, z, w = q
    # v' = v + 2w (u × v) + 2 u × (u × v), with u = (x, y, z)
    ux = (y * v[2] - z * v[1], z * v[0] - x * v[2], x * v[1] - y * v[0])
    uux = (y * ux[2] - z * ux[1], z * ux[0] - x * ux[2], x * ux[1] - y * ux[0])
    return (
        v[0] + 2 * (w * ux[0] + uux[0]),
        v[1] + 2 * (w * ux[1] + uux[1]),
        v[2] + 2 * (w * ux[2] + uux[2]),
    )


def _to_world(inst: dict[str, Any], p: Vec3) -> Vec3:
    r = _rotate(inst["rotation"], p)
    t = inst["translation"]
    return (r[0] + t[0], r[1] + t[1], r[2] + t[2])


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _len(a: Vec3) -> float:
    return math.sqrt(_dot(a, a))


def _r(v: Vec3, nd: int = 1) -> list[float]:
    return [round(c, nd) + 0.0 for c in v]


def _direction(d: float) -> str:
    if d > 1 - 1e-6:
        return "same"
    if d < -1 + 1e-6:
        return "facing"
    return f"angle {math.degrees(math.acos(max(-1.0, min(1.0, d)))):.1f} deg"


def survey(product_dir: Path) -> list[dict[str, Any]]:
    """Return one row per interface (and per occurrence pair when a party occurs twice)."""
    product = load_product(product_dir)
    # the top assembly is the one no other assembly lists as a child
    children = {c.asm.id for a in product.assemblies.values() for c in a.children if c.asm}
    top_id = next(a for a in sorted(product.assemblies) if a not in children)
    asm_dir = product_dir / "build" / "assemblies"
    instances = json.loads((asm_dir / top_id / "instances.json").read_text())
    by_uri: dict[str, list[dict[str, Any]]] = {}
    for inst in instances:
        by_uri.setdefault(inst["uri"], []).append(inst)

    rows: list[dict[str, Any]] = []
    for iface_id in sorted(product.interfaces):
        raw = product.interfaces[iface_id]
        iface = resolve_interface(product, raw)
        a_uri, b_uri = (str(p) for p in iface.parties)
        row: dict[str, Any] = {"interface": iface_id, "kind": iface.kind, "parties": [a_uri, b_uri]}
        row["x_axis_explicit"] = {
            u: raw.frames.get(u, raw.frame).x_axis is not None for u in (a_uri, b_uri)
        }
        row["frame_fallback"] = [u for u in (a_uri, b_uri) if u not in raw.frames]
        occ_a, occ_b = by_uri.get(a_uri, []), by_uri.get(b_uri, [])
        if not occ_a or not occ_b:
            row["note"] = "a party has no placed occurrence"
            rows.append(row)
            continue
        pairs = []
        for ia in occ_a:
            for ib in occ_b:
                fa, fb = iface.frame_for(a_uri), iface.frame_for(b_uri)
                oa, xa, _, za = frame_basis(fa)
                ob, xb, _, zb = frame_basis(fb)
                wa = _to_world(ia, oa)
                wb = _to_world(ib, ob)
                na, nb = _rotate(ia["rotation"], za), _rotate(ib["rotation"], zb)
                xwa, xwb = _rotate(ia["rotation"], xa), _rotate(ib["rotation"], xb)
                d = _sub(wb, wa)
                offset = _dot(d, na)
                in_plane = _len(_sub(d, (offset * na[0], offset * na[1], offset * na[2])))
                hole_miss = None
                if iface.kind == "bolt-pattern":
                    ca = [_to_world(ia, c) for c in centers_from_spec(iface.spec, fa)]
                    cb = [_to_world(ib, c) for c in centers_from_spec(iface.spec, fb)]
                    worst = 0.0
                    for p in ca:
                        best = math.inf
                        for q in cb:
                            v = _sub(q, p)
                            off = _dot(v, na)
                            best = min(best, _len(_sub(v, (off * na[0], off * na[1], off * na[2]))))
                        worst = max(worst, best)
                    hole_miss = round(worst, 2)
                pairs.append(
                    {
                        "occurrences": [ia["node"], ib["node"]],
                        "world": {
                            a_uri: {"origin": _r(wa), "normal": _r(na, 3), "x_axis": _r(xwa, 3)},
                            b_uri: {"origin": _r(wb), "normal": _r(nb, 3), "x_axis": _r(xwb, 3)},
                        },
                        "normals": _direction(_dot(na, nb)),
                        "x_axes": _direction(_dot(xwa, xwb)),
                        "offset_mm": round(offset, 2) + 0.0,
                        "in_plane_miss_mm": round(in_plane, 2) + 0.0,
                        "hole_miss_mm": hole_miss,
                    }
                )
        row["pairs"] = pairs
        rows.append(row)
    return rows


def placement_lines(module: Path) -> dict[str, int]:
    """Count the placement code in an assembly module's ``build()`` (the M0 baseline metric).

    Each top-level statement of ``build()`` is put in one class, and its physical lines that
    are neither blank nor comment-only are counted:

    * ``place``: a statement that calls ``place(...)`` (or ``place_by(...)``) anywhere inside,
      e.g. ``res.add(place(...))`` or a ``for`` loop around one;
    * ``coordinates``: any other assignment, i.e. position arithmetic (``cx = go_w / 2 + …``);
    * ``reads``: an assignment whose value only reads parameters (``P.mm("…")``);
    * ``other``: the docstring, the import, ``res = AssemblyResult()`` and ``return``.

    ``place_calls`` is the number of ``place(...)`` call sites; ``literal_offsets`` counts
    numeric literals other than 0 and ±90/180 (rotations) inside ``translate=`` arguments.
    """
    import ast

    src = module.read_text().splitlines()
    tree = ast.parse("\n".join(src))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build")

    def code_lines(node: ast.AST) -> int:
        lo, hi = node.lineno, node.end_lineno or node.lineno  # type: ignore[attr-defined]
        return sum(1 for ln in src[lo - 1 : hi] if ln.strip() and not ln.strip().startswith("#"))

    def calls(node: ast.AST, names: set[str]) -> int:
        return sum(
            1
            for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in names
        )

    def only_param_reads(value: ast.AST) -> bool:
        cs = [n for n in ast.walk(value) if isinstance(n, ast.Call)]
        return bool(cs) and all(
            isinstance(c.func, ast.Attribute)
            and isinstance(c.func.value, ast.Name)
            and c.func.value.id == "P"
            for c in cs
        )

    out = {"place": 0, "coordinates": 0, "reads": 0, "other": 0, "place_calls": 0}
    literals = 0
    for stmt in fn.body:
        n = code_lines(stmt)
        if calls(stmt, {"place", "place_by"}):
            out["place"] += n
            out["place_calls"] += calls(stmt, {"place", "place_by"})
            for kw in (k for c in ast.walk(stmt) if isinstance(c, ast.Call) for k in c.keywords):
                if kw.arg == "translate":
                    # scale factors (``w / 2``) are not offsets
                    scales = {
                        id(b.right)
                        for b in ast.walk(kw.value)
                        if isinstance(b, ast.BinOp) and isinstance(b.op, (ast.Div, ast.Mult))
                    }
                    literals += sum(
                        1
                        for c in ast.walk(kw.value)
                        if isinstance(c, ast.Constant)
                        and isinstance(c.value, (int, float))
                        and c.value != 0
                        and id(c) not in scales
                    )
        elif isinstance(stmt, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            value = stmt.value
            if value is not None and only_param_reads(value):
                out["reads"] += n
            elif isinstance(value, ast.Call) and getattr(value.func, "id", "") == "AssemblyResult":
                out["other"] += n
            else:
                out["coordinates"] += n
        else:
            out["other"] += n
    out["literal_offsets"] = literals
    out["file_lines"] = len(src)
    return out


def _table(rows: list[dict[str, Any]]) -> str:
    head = (
        "| interface | normals | x axes | offset (mm) | origin miss (mm) | hole miss (mm) "
        "| x_axis explicit |\n|---|---|---|---|---|---|---|"
    )
    out = [head]
    for row in rows:
        explicit = "both" if all(row["x_axis_explicit"].values()) else "no"
        for p in row.get("pairs", []):
            out.append(
                f"| {row['interface']} | {p['normals']} | {p['x_axes']} | {p['offset_mm']} "
                f"| {p['in_plane_miss_mm']} | {p['hole_miss_mm']} | {explicit} |"
            )
        if "note" in row:
            out.append(f"| {row['interface']} | {row['note']} | | | | | {explicit} |")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    """Survey a built product, or copy and build one first with ``--fresh``."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("product", type=Path, help="product folder (built unless --fresh)")
    ap.add_argument("--fresh", action="store_true", help="copy to a temp folder and build first")
    ap.add_argument("--json", action="store_true", help="print the rows as JSON")
    ap.add_argument(
        "--lines", action="store_true", help="count placement code per assembly module (no build)"
    )
    args = ap.parse_args(argv)
    product_dir = args.product.resolve()
    if args.fresh:
        tmp = Path(tempfile.mkdtemp(prefix="n2f-survey-")) / product_dir.name
        shutil.copytree(
            product_dir, tmp, ignore=shutil.ignore_patterns("build", "__pycache__", ".git")
        )
        n2f = Path(sys.executable).with_name("n2f")
        subprocess.run([str(n2f), "build"], cwd=tmp, check=True, stdout=subprocess.DEVNULL)
        product_dir = tmp
        print(f"built a copy in {tmp}", file=sys.stderr)
    if args.lines:
        product = load_product(product_dir)
        counts = {}
        for asm_id, asm in sorted(product.assemblies.items()):
            module = getattr(asm.geometry, "module", None)
            if module:
                counts[asm_id] = placement_lines(product.paths.model / module)
        print(json.dumps(counts, indent=2))
        return 0
    rows = survey(product_dir)
    print(json.dumps(rows, indent=2) if args.json else _table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
