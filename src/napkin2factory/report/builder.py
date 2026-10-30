"""The self-contained HTML report (decisions D13, D17).

One page, zero external references: three.js and the viewer inlined as a single module
script, GLBs and renders embedded as base64, drawings inlined as SVG, manuals as HTML
fragments.  An owner/engineer toggle reorders sections and swaps vocabulary; safety
content is never behind the toggle.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jinja2

from napkin2factory import __version__
from napkin2factory.core.graph.hashing import sha256_text
from napkin2factory.core.loader import Product
from napkin2factory.core.units import format_quantity

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext, RunResult

TEMPLATES = Path(__file__).parent / "templates"
MAX_REPORT_BYTES = 20 * 1024 * 1024

#: Section order per persona (owner, engineer): lower first.
SECTION_ORDER: dict[str, tuple[int, int]] = {
    "safety": (0, 0),
    "next": (1, 1),
    "3d": (2, 5),
    "cost": (3, 6),
    "drawings": (4, 7),
    "checks": (5, 2),
    "reqs": (6, 3),
    "params": (7, 4),
    "decisions": (8, 8),
    "changes": (9, 9),
    "docs": (10, 10),
    "signoffs": (11, 11),
}

VOCAB: dict[str, dict[str, str]] = {
    "owner": {
        "pass": "OK",
        "fail": "needs attention",
        "warn": "worth a look",
        "skip": "not checked",
        "needs-human": "needs your sign-off",
        "signed": "signed off",
        "changes": "Change requests",
    },
    "engineer": {
        "pass": "pass",
        "fail": "fail",
        "warn": "warn",
        "skip": "skip",
        "needs-human": "needs-human",
        "signed": "signed",
        "changes": "Change requests (ECRs)",
    },
}


def report_reads(ctx: RunContext) -> list[str]:
    """The report depends on every artifact: checks, parts, assemblies, drawings, docs, BOM."""
    product = ctx.product
    reads = ["rule:checks", "bom://rollups"]
    reads += [p.uri for p in product.parts_with_geometry()]
    reads += [f"drawing://{p.id}" for p in product.parts_with_geometry()]
    reads += [a.uri for a in product.assemblies.values()]
    reads += [f"doc://{d}" for d in product.docs]
    reads += [f"req://{r}#title" for r in product.requirements]
    reads += [f"req://{r}#statement" for r in product.requirements]
    reads += [f"dec://{d}#title" for d in product.decisions]
    reads += [f"ecr://{e}#status" for e in product.ecrs]
    reads += [f"param://{p}" for p in product.parameters]
    reads += [f"signoff:{s}" for s in product.signoffs]
    reads += [
        "set://parts",
        "set://asms",
        "set://docs",
        "set://reqs",
        "set://decs",
        "set://ecrs",
        "set://signoffs",
        "set://params",
        "set://ifaces",
        "manifest://product#name",
    ]
    return reads


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _doc_html(build_dir: Path, doc_id: str, markdown: str) -> str:
    """Prefer the docs engine's fragment renderer; fall back to a plain markdown-it render.

    The page's own top-level title is dropped: the report shows the title itself.
    """
    try:
        from napkin2factory.docs.html import render_fragment

        html = str(render_fragment(markdown))
    except ImportError:
        from markdown_it import MarkdownIt

        html = str(MarkdownIt("gfm-like").render(markdown))
    return re.sub(r"^\s*<h1[^>]*>.*?</h1>\s*", "", html, count=1, flags=re.DOTALL)


def _flatten_bom(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ln in lines:
        out.append(ln)
        out.extend(_flatten_bom(ln.get("children", [])))
    return out


def _bom_by_uri(flat: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for ln in flat:
        agg = out.setdefault(
            ln["uri"],
            {
                "name": ln["name"],
                "kind": ln["kind"],
                "total_qty": 0,
                "unit_cost": ln.get("unit_cost"),
                "manufacturer": ln.get("manufacturer", ""),
            },
        )
        agg["total_qty"] += int(ln.get("total_qty", 0))
    return out


def gather(product: Product, build_dir: Path, snapshot_date: str) -> dict[str, Any]:
    """Collect everything the template needs from ``build/`` and the model."""
    from napkin2factory.bom.rollups import top_assemblies
    from napkin2factory.core.checks.stage import compute_stage

    checks = _read_json(build_dir / "checks" / "checks.json") or {
        "summary": {},
        "results": [],
        "matrix": {"requirements": [], "rules": {"parts": [], "rules": {}, "cells": {}}},
    }
    rollups = _read_json(build_dir / "bom" / "rollups.json") or {
        "structure": {},
        "total_cost": 0.0,
        "total_mass": 0.0,
        "part_count": 0,
        "custom_count": 0,
        "max_lead_time": 0,
        "cost_complete": True,
    }
    summary = {
        k: int(checks.get("summary", {}).get(k, 0))
        for k in ("pass", "fail", "warn", "skip", "needs-human", "signed")
    }
    results = {r["id"]: r for r in checks.get("results", [])}
    stage = compute_stage(product, build_dir)
    persona = product.operator.persona

    # 3D: the top assemblies' GLBs (or every part's GLB when there is no assembly)
    glb_paths = [build_dir / "assemblies" / a / "model.glb" for a in top_assemblies(product)]
    if not glb_paths:
        glb_paths = [
            build_dir / "parts" / p.id / "model.glb" for p in product.parts_with_geometry()
        ]
    glb_paths = [p for p in glb_paths if p.is_file()]
    glb_b64 = base64.b64encode(glb_paths[0].read_bytes()).decode() if glb_paths else ""
    exploded = {"axis": "z", "spacing": 80.0}
    tops = top_assemblies(product)
    if tops:
        ex = product.assemblies[tops[0]].exploded
        exploded = {"axis": ex.axis, "spacing": float(ex.spacing.to("mm").magnitude)}
    renders = []
    for a in tops:
        for view in ("iso", "section"):
            p = build_dir / "assemblies" / a / "renders" / f"{view}.png"
            if p.is_file():
                renders.append(
                    {
                        "label": f"asm://{a} · {view}",
                        "b64": base64.b64encode(p.read_bytes()).decode(),
                    }
                )
    if not tops:
        for part in product.parts_with_geometry():
            p = build_dir / "parts" / part.id / "renders" / "iso.png"
            if p.is_file():
                renders.append(
                    {"label": f"{part.uri} · iso", "b64": base64.b64encode(p.read_bytes()).decode()}
                )

    drawings = []
    for part in product.parts_with_geometry():
        svg = build_dir / "drawings" / f"{part.id}.svg"
        if svg.is_file():
            text = svg.read_text(encoding="utf-8")
            if text.startswith("<?xml"):
                text = text.split("?>", 1)[1]
            drawings.append(
                {
                    "id": part.id,
                    "uri": part.uri,
                    "rev": part.rev,
                    "svg": text,
                    "has_flat": (build_dir / "drawings" / f"{part.id}-flat.dxf").is_file(),
                }
            )

    flat = _flatten_bom([ln for lines in rollups.get("structure", {}).values() for ln in lines])
    bom_by_uri = _bom_by_uri(flat)
    for p in product.parts.values():
        bom_by_uri.setdefault(
            p.uri,
            {"name": p.name, "kind": p.kind, "total_qty": 0, "unit_cost": None, "manufacturer": ""},
        )

    def signoff_example(rid: str) -> bool:
        so = product.signoffs.get(rid)
        return bool(so and so.example)

    req_rows = []
    for row in checks.get("matrix", {}).get("requirements", []):
        res = results.get(f"req://{row['id']}", {})
        req_rows.append(
            {
                **row,
                "message": res.get("message", row.get("message", "")),
                "signoff_example": signoff_example(row["id"])
                and res.get("status") in ("signed", "pass"),
            }
        )
    safety_reqs = [r for r in req_rows if r.get("safety")]
    other_rows = [
        r for r in checks.get("results", []) if r["kind"] != "requirement" and r["status"] != "pass"
    ]

    docs = []
    safety_docs = []
    for doc in sorted(product.docs.values(), key=lambda d: (d.meta.order, d.meta.id)):
        md_path = build_dir / "docs" / doc.meta.id / "page.md"
        html = (
            _doc_html(build_dir, doc.meta.id, md_path.read_text(encoding="utf-8"))
            if md_path.is_file()
            else "<p class='muted'>not rendered</p>"
        )
        entry = {
            "id": doc.meta.id,
            "title": doc.meta.title,
            "audience": doc.meta.audience,
            "html": html,
            "safety": doc.meta.safety,
        }
        (safety_docs if doc.meta.safety else docs).append(entry)

    satisfied_by: dict[str, list[str]] = {}
    for p in product.parts.values():
        for r in p.satisfies:
            satisfied_by.setdefault(r.id, []).append(p.uri)
    for a in product.assemblies.values():
        for r in a.satisfies:
            satisfied_by.setdefault(r.id, []).append(a.uri)
    trace = [
        {
            "id": r.id,
            "statement": r.statement,
            "allocation": [str(a) for a in r.allocation]
            if isinstance(r.allocation, list)
            else [str(r.allocation or "")],
            "satisfied_by": satisfied_by.get(r.id, []),
        }
        for r in product.requirements.values()
    ]
    params = []
    for slug, p in product.parameters.items():
        try:
            value = format_quantity(product.parameter_value(slug))
        except Exception as exc:
            value = f"invalid: {exc}"
        params.append(
            {"slug": slug, "value": value, "description": p.description or "", "expr": p.expr}
        )
    decisions = [
        {
            "id": d.id,
            "title": d.title,
            "date": d.date.isoformat(),
            "made_by": d.made_by,
            "decision": d.decision,
            "rationale": d.rationale,
            "sources": d.sources,
            "links": [str(x) for x in d.links],
            "verify": d.verify,
        }
        for d in product.decisions.values()
    ]
    ecrs = [
        {
            "id": e.id,
            "title": e.title,
            "kind": e.kind,
            "status": e.status,
            "released_in": e.released_in,
        }
        for e in product.ecrs.values()
    ]
    signoffs = []
    for s in product.signoffs.values():
        res = results.get(f"req://{s.requirement.id}", {})
        so = res.get("detail", {}).get("signoff", {})
        signoffs.append(
            {
                "requirement": str(s.requirement),
                "by": s.by,
                "date": s.date.isoformat(),
                "statement": s.statement,
                "example": s.example,
                "valid": bool(so.get("valid")),
                "why": so.get("why", "not evaluated"),
            }
        )

    from napkin2factory.core.vcs import Vcs

    revision = None
    last_revision = None
    clean = True
    try:
        v = Vcs(product.root)
        if v.is_tracked():
            clean = v.is_clean()
            revision = v.tag_for_head()
            tags = v.tags()
            last_revision = tags[-1] if tags else None
    except Exception:
        revision = None
    if revision and not clean:
        revision = None  # an edited model is not the released Revision (gate-2 B4)
    stage_label = {
        "intake": "Intake",
        "design": "Design",
        "verify": "Verify",
        "released": f"Released {revision or ''}".strip(),
    }[stage.stage]
    if revision:
        revision_label = f"Revision {revision}"
    elif last_revision:
        revision_label = f"draft — changed since Revision {last_revision}"
    elif snapshot_date == "unsnapshotted":
        revision_label = "draft — not saved yet"
    else:
        revision_label = f"draft · saved {snapshot_date}"

    return {
        "product": product.manifest.product,
        "persona": persona,
        "vocab": VOCAB,
        "section_order": SECTION_ORDER,
        "stage": stage,
        "stage_label": stage_label,
        "revision_label": revision_label,
        "summary": summary,
        "glb_b64": glb_b64,
        "exploded": exploded,
        "renders": renders,
        "drawings": drawings,
        "rollups": rollups,
        "bom_lines": flat,
        "bom_json": json.dumps(bom_by_uri),
        "req_rows": req_rows,
        "safety_reqs": safety_reqs,
        "other_rows": other_rows,
        "rule_matrix": checks.get("matrix", {}).get(
            "rules", {"parts": [], "rules": {}, "cells": {}}
        ),
        "trace": trace,
        "params": params,
        "decisions": decisions,
        "ecrs": ecrs,
        "docs": docs,
        "safety_docs": safety_docs,
        "signoffs": signoffs,
        "version": __version__,
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def render_report(product: Product, build_dir: Path, snapshot_date: str, build_id: str = "") -> str:
    """Render the page HTML (the viewer bundle inlined)."""
    from napkin2factory.report.inline import bundle_viewer, inline_module_script

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES)),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )
    data = gather(product, build_dir, snapshot_date)
    data["viewer_script"] = inline_module_script(bundle_viewer()) if data["glb_b64"] else ""
    data["build_id"] = build_id
    return env.get_template("report.html.j2").render(**data)


def build_report(ctx: RunContext) -> RunResult:
    """The ``report`` rule body."""
    from napkin2factory.core.graph.rules import RunResult

    html = render_report(ctx.product, ctx.build_dir, ctx.snapshot_date)
    out = ctx.build_dir / "report" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    size = out.stat().st_size
    meta = {"bytes": size, "max_bytes": MAX_REPORT_BYTES, "within_budget": size <= MAX_REPORT_BYTES}
    meta_path = ctx.build_dir / "report" / "report.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    # the generated timestamp must not change the output hash
    stable = html.split("<footer", 1)[0]
    return RunResult(
        reads=report_reads(ctx),
        outputs=[out, meta_path],
        output_hash=sha256_text(stable),
        payload=meta,
    )
