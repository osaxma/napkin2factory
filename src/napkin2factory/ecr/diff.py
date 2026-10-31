"""``n2f diff A B``: what changed between two Revisions (or a Revision and the working tree).

Builds each ref in a scratch worktree unless ``build/site/<ref>/data`` already holds its
frozen data (released Revisions).  Produces one self-contained page under
``build/site/diff/<A>..<B>/index.html``: drawing overlays (old red, new green, re-scaled to
one shared scale, title blocks excluded), BOM delta with cost and mass impact, parameter and
requirement deltas, changed/added/removed parts, and side-by-side 3D with changed parts
highlighted.  ``B`` may be ``working`` for the current build.
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import jinja2

from napkin2factory import __version__
from napkin2factory.core.errors import N2FError
from napkin2factory.core.loader import Product, load_product
from napkin2factory.core.vcs import Vcs
from napkin2factory.ecr.release import export_data
from napkin2factory.report.brand import favicon_link, footer_mark
from napkin2factory.report.builder import TEMPLATES

TITLEBLOCK_RE = re.compile(r'<g id="titleblock".*?</g>\s*', re.DOTALL)
CHANGED, ADDED, REMOVED = "changed", "added", "removed"


class DiffError(N2FError):
    """A diff could not be produced."""

    exit_code = 3


def _data_for_ref(product: Product, ref: str, scratch: Path, render: bool) -> Path:
    """Return a data dir for ``ref``: frozen site data, the working build, or a worktree build."""
    if ref == "working":
        data = scratch / "working"
        from napkin2factory.core.graph.runner import run_build

        run_build(product, quiet=True, render=render)
        export_data(product, product.paths.build, data)
        return data
    frozen = product.paths.build / "site" / ref / "data"
    if (frozen / "model.json").is_file():
        return frozen
    vcs = Vcs(product.root)
    vcs.require_repo_root()
    if not vcs.ref_exists(ref):
        raise DiffError(
            f"{ref!r} is not a released Revision of this product; "
            "build/site/versions.html lists them (or use 'working' for the current model)"
        )
    wt = scratch / f"wt-{re.sub(r'[^A-Za-z0-9.]+', '-', ref)}"
    vcs.worktree_add(ref, wt)
    try:
        other = load_product(wt)
        from napkin2factory.core.graph.runner import run_build

        run_build(other, quiet=True, render=render, build_dir=wt / "build")
        data = scratch / f"data-{wt.name}"
        export_data(other, wt / "build", data)
    finally:
        vcs.worktree_remove(wt)
        shutil.rmtree(wt, ignore_errors=True)
    return data


def _load(data: Path, name: str) -> Any:
    p = data / name
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def _parse_scale(svg: str) -> float:
    """``data-scale="1:3"`` → 1/3; ``"2:1"`` → 2; bare numbers pass through."""
    m = re.search(r'data-scale="([0-9.]+)(?::([0-9.]+))?"', svg)
    if not m:
        return 1.0
    num = float(m.group(1))
    den = float(m.group(2)) if m.group(2) else 1.0
    return num / den if den else 1.0


def _view_groups(svg: str) -> dict[str, tuple[str, tuple[float, float, float, float]]]:
    """``{view id: (group markup, bbox x y w h)}`` for every ``<g id="view-…" data-bbox>``."""
    out: dict[str, tuple[str, tuple[float, float, float, float]]] = {}
    for m in re.finditer(r'<g id="(view-[a-z]+)" data-bbox="([^"]+)"[^>]*>', svg):
        gid = m.group(1)
        bbox = tuple(float(v) for v in m.group(2).split())
        # find the matching close tag by depth counting
        depth, i = 0, m.start()
        for tag in re.finditer(r"<g\b|</g>", svg[m.start() :]):
            depth += 1 if tag.group(0).startswith("<g") else -1
            if depth == 0:
                i = m.start() + tag.end()
                break
        if len(bbox) == 4:
            out[gid] = (svg[m.start() : i], (bbox[0], bbox[1], bbox[2], bbox[3]))
    return out


def _overlay(old_svg: str | None, new_svg: str | None) -> str:
    """Old geometry (red) over new (green), view by view, at the new drawing's scale.

    Each old view group is scaled by new/old and translated so its bbox centre lands on the
    new view's bbox centre, so a taller box shows as red walls shorter than green ones in
    the same place rather than two sheets offset from each other.  Title blocks are dropped;
    the new drawing's dimensions and hole table are kept.
    """

    def strip(svg: str) -> str:
        svg = TITLEBLOCK_RE.sub("", svg)
        svg = re.sub(r"<\?xml.*?\?>", "", svg, flags=re.DOTALL)
        return svg.split(">", 1)[1].rsplit("</svg>", 1)[0] if "<svg" in svg else svg

    parts: list[str] = []
    if new_svg:
        parts.append(f'<g class="new">{strip(new_svg)}</g>')
    if old_svg:
        if new_svg:
            factor = _parse_scale(new_svg) / (_parse_scale(old_svg) or 1.0)
            old_groups = _view_groups(old_svg)
            new_groups = _view_groups(new_svg)
            placed: list[str] = []
            for gid, (markup, ob) in old_groups.items():
                if gid in new_groups:
                    nb = new_groups[gid][1]
                    ocx, ocy = ob[0] + ob[2] / 2, ob[1] + ob[3] / 2
                    ncx, ncy = nb[0] + nb[2] / 2, nb[1] + nb[3] / 2
                    tx, ty = ncx - ocx * factor, ncy - ocy * factor
                    transform = f"translate({tx:.4f} {ty:.4f}) scale({factor:.6f})"
                    placed.append(f'<g transform="{transform}">{markup}</g>')
                else:
                    placed.append(markup)
            parts.insert(0, f'<g class="old">{"".join(placed)}</g>')
        else:
            parts.insert(0, f'<g class="old">{strip(old_svg)}</g>')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 297" width="100%">'
        "<style>.old *{stroke:#c0392b !important;fill:none !important;opacity:.8}"
        ".old text{fill:#c0392b !important;stroke:none !important}"
        ".new *{stroke:#1e8449 !important;fill:none !important;opacity:.9}"
        ".new text{fill:#1e8449 !important;stroke:none !important}</style>"
        + "".join(parts)
        + "</svg>"
    )


def compute_diff(a: Path, b: Path) -> dict[str, Any]:
    """Structured delta between two data dirs."""
    ma, mb = _load(a, "model.json") or {}, _load(b, "model.json") or {}
    ra, rb = _load(a, "rollups.json") or {}, _load(b, "rollups.json") or {}
    ca, cb = _load(a, "checks.json") or {}, _load(b, "checks.json") or {}
    parts_a, parts_b = ma.get("parts", {}), mb.get("parts", {})
    props_a = (
        {p.stem: json.loads(p.read_text()) for p in (a / "parts").glob("*.json")}
        if (a / "parts").is_dir()
        else {}
    )
    props_b = (
        {p.stem: json.loads(p.read_text()) for p in (b / "parts").glob("*.json")}
        if (b / "parts").is_dir()
        else {}
    )
    parts: list[dict[str, Any]] = []
    for pid in sorted(set(parts_a) | set(parts_b)):
        if pid not in parts_a:
            parts.append(
                {
                    "id": pid,
                    "uri": f"part://{pid}",
                    "state": ADDED,
                    "rev": parts_b[pid]["rev"],
                    "name": parts_b[pid]["name"],
                }
            )
        elif pid not in parts_b:
            parts.append(
                {
                    "id": pid,
                    "uri": f"part://{pid}",
                    "state": REMOVED,
                    "rev": parts_a[pid]["rev"],
                    "name": parts_a[pid]["name"],
                }
            )
        else:
            geo_changed = (
                (props_a.get(pid, {}).get("tess_hash") != props_b.get(pid, {}).get("tess_hash"))
                if (pid in props_a or pid in props_b)
                else False
            )
            decl_changed = parts_a[pid] != parts_b[pid]
            if geo_changed or decl_changed:
                rev_a, rev_b = parts_a[pid]["rev"], parts_b[pid]["rev"]
                parts.append(
                    {
                        "id": pid,
                        "uri": f"part://{pid}",
                        "state": CHANGED,
                        "rev": f"{rev_a} → {rev_b}"
                        if rev_a != rev_b
                        else f"{rev_b} (bumps when the change request closes)",
                        "name": parts_b[pid]["name"],
                        "geometry": geo_changed,
                        "declared": decl_changed,
                        "bbox_a": props_a.get(pid, {}).get("bbox", {}),
                        "bbox_b": props_b.get(pid, {}).get("bbox", {}),
                        "mass_a": props_a.get(pid, {}).get("mass"),
                        "mass_b": props_b.get(pid, {}).get("mass"),
                    }
                )
    params = []
    for k in sorted(set(ma.get("parameters", {})) | set(mb.get("parameters", {}))):
        va, vb = ma.get("parameters", {}).get(k), mb.get("parameters", {}).get(k)
        if va != vb:
            params.append({"slug": k, "a": va, "b": vb})
    bom = []
    pa, pb = ra.get("parts", {}), rb.get("parts", {})
    for uri in sorted(set(pa) | set(pb)):
        xa, xb = pa.get(uri, {}), pb.get(uri, {})
        qa, qb = int(xa.get("total_qty", 0)), int(xb.get("total_qty", 0))
        ua, ub = xa.get("unit_cost"), xb.get("unit_cost")
        ea = (ua or 0.0) * qa
        eb = (ub or 0.0) * qb
        mass_a = (xa.get("mass_kg") or 0.0) * qa
        mass_b = (xb.get("mass_kg") or 0.0) * qb
        if qa != qb or ua != ub or xa.get("mass_kg") != xb.get("mass_kg"):
            bom.append(
                {
                    "uri": uri,
                    "name": xb.get("name") or xa.get("name"),
                    "qty_a": qa,
                    "qty_b": qb,
                    "unit_a": ua,
                    "unit_b": ub,
                    "ext_delta": round(eb - ea, 2),
                    "mass_delta": round(mass_b - mass_a, 4),
                }
            )
    reqs = []
    sa = {r["id"]: r for r in ca.get("matrix", {}).get("requirements", [])}
    sb = {r["id"]: r for r in cb.get("matrix", {}).get("requirements", [])}
    for rid in sorted(set(sa) | set(sb)):
        xa, xb = sa.get(rid), sb.get(rid)
        if (xa or {}).get("status") != (xb or {}).get("status") or (xa or {}).get("message") != (
            xb or {}
        ).get("message"):
            reqs.append(
                {
                    "id": rid,
                    "title": (xb or xa or {}).get("title", ""),
                    "a": (xa or {}).get("status", "—"),
                    "b": (xb or {}).get("status", "—"),
                    "msg_a": (xa or {}).get("message", ""),
                    "msg_b": (xb or {}).get("message", ""),
                }
            )
    totals = {
        "cost_a": ra.get("total_cost"),
        "cost_b": rb.get("total_cost"),
        "cost_delta": round(float(rb.get("total_cost", 0)) - float(ra.get("total_cost", 0)), 2),
        "mass_a": ra.get("total_mass"),
        "mass_b": rb.get("total_mass"),
        "mass_delta": round(float(rb.get("total_mass", 0)) - float(ra.get("total_mass", 0)), 4),
        "parts_a": ra.get("part_count"),
        "parts_b": rb.get("part_count"),
    }
    return {
        "parts": parts,
        "params": params,
        "bom": bom,
        "requirements": reqs,
        "totals": totals,
        "changed_uris": [p["uri"] for p in parts if p["state"] == CHANGED],
        "added_uris": [p["uri"] for p in parts if p["state"] == ADDED],
        "removed_uris": [p["uri"] for p in parts if p["state"] == REMOVED],
    }


def _glb_b64(data: Path) -> str:
    """The top-level assembly's GLB (not a sub-assembly that happens to sort first)."""
    if not (data / "assemblies").is_dir():
        return ""
    glbs = {p.name[: -len(".model.glb")]: p for p in (data / "assemblies").glob("*.model.glb")}
    if not glbs:
        return ""
    model = _load(data, "model.json") or {}
    children = {
        c["uri"].split("://")[1]
        for a in model.get("assemblies", {}).values()
        for c in a.get("children", [])
        if c["uri"].startswith("asm://")
    }
    tops = [name for name in sorted(glbs) if name not in children] or sorted(glbs)
    return base64.b64encode(glbs[tops[0]].read_bytes()).decode()


def render_diff(
    product: Product, ref_a: str, ref_b: str, a: Path, b: Path, delta: dict[str, Any]
) -> str:
    """Render the diff page."""
    from napkin2factory.report.inline import bundle_viewer, inline_module_script

    overlays = []
    for p in delta["parts"]:
        if p["state"] in (CHANGED, ADDED, REMOVED):
            old_svg = a / "drawings" / f"{p['id']}.svg"
            new_svg = b / "drawings" / f"{p['id']}.svg"
            if old_svg.is_file() or new_svg.is_file():
                overlays.append(
                    {
                        "id": p["id"],
                        "uri": p["uri"],
                        "state": p["state"],
                        "svg": _overlay(
                            old_svg.read_text(encoding="utf-8") if old_svg.is_file() else None,
                            new_svg.read_text(encoding="utf-8") if new_svg.is_file() else None,
                        ),
                    }
                )
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES)),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )
    env.globals["n2f_favicon"] = favicon_link()
    env.globals["n2f_mark"] = footer_mark()
    glb_a, glb_b = _glb_b64(a), _glb_b64(b)
    return env.get_template("diff.html.j2").render(
        product=product.manifest.product,
        ref_a=ref_a,
        ref_b=ref_b,
        delta=delta,
        overlays=overlays,
        glb_a=glb_a,
        glb_b=glb_b,
        changed=json.dumps(delta["changed_uris"]),
        added=json.dumps(delta["added_uris"]),
        removed=json.dumps(delta["removed_uris"]),
        viewer_script=inline_module_script(bundle_viewer()) if (glb_a or glb_b) else "",
        version=__version__,
    )


def diff(
    product: Product, ref_a: str, ref_b: str, out: Path | None = None, render: bool = False
) -> dict[str, Any]:
    """Build both refs as needed and write the diff page; returns paths and the delta."""
    scratch = Path(tempfile.mkdtemp(prefix="n2f-diff-"))
    try:
        a = _data_for_ref(product, ref_a, scratch, render)
        b = _data_for_ref(product, ref_b, scratch, render)
        delta = compute_diff(a, b)
        html = render_diff(product, ref_a, ref_b, a, b, delta)
    finally:
        pass
    out_dir = out or (product.paths.build / "site" / "diff" / f"{ref_a}..{ref_b}")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "diff.json").write_text(
        json.dumps(delta, indent=2, default=str) + "\n", encoding="utf-8"
    )
    shutil.rmtree(scratch, ignore_errors=True)
    from napkin2factory.ecr.release import write_site_index

    if out is None:
        write_site_index(product, product.paths.build / "site")
    return {"page": str(out_dir / "index.html"), "delta": delta}
