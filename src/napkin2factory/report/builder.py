"""The self-contained HTML report (decisions D13, D17 as amended by S-050).

One page, zero external references: three.js and the viewer inlined as a single module
script, GLBs and renders embedded as base64, drawings inlined as SVG, manuals as HTML
fragments.  One layout for everyone: a sticky section index, sections grouped by purpose
(overview, safety, product, verification, design record, manuals), and every model URI
rendered as a hyperlink to the row that describes it.  The operator persona only picks
the words used for check statuses and whether visible URIs keep their ``scheme://`` prefix
(the owner reads ``outer-shell``, the engineer ``part://outer-shell``; attributes and
anchors always carry the full URI); safety content is always visible.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jinja2
from markupsafe import Markup

from napkin2factory import __version__
from napkin2factory.core.checks.results import SUMMARY_KEYS
from napkin2factory.core.graph.hashing import sha256_text
from napkin2factory.core.loader import Product
from napkin2factory.core.units import format_quantity
from napkin2factory.core.uris import display_uri

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext, RunResult

TEMPLATES = Path(__file__).parent / "templates"
MAX_REPORT_BYTES = 20 * 1024 * 1024

#: Page sections in reading order: (anchor, nav label, group).  The nav groups them.
SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("overview", "Overview", ""),
    ("safety", "Safety", ""),
    ("model", "3D model", "Product"),
    ("parts", "Parts & cost", "Product"),
    ("drawings", "Drawings", "Product"),
    ("interfaces", "Interfaces", "Product"),
    ("requirements", "Requirements", "Verification"),
    ("rules", "Rule checks", "Verification"),
    ("signoffs", "Sign-offs", "Verification"),
    ("parameters", "Parameters", "Design record"),
    ("decisions", "Decisions", "Design record"),
    ("changes", "Change requests", "Design record"),
    ("manuals", "Manuals", ""),
)

VOCAB: dict[str, dict[str, str]] = {
    "owner": {
        "pass": "OK",
        "fail": "needs attention",
        "warn": "worth a look",
        "skip": "not checked",
        "needs-human": "needs your sign-off",
        "signed": "signed off",
        "example": "example sign-offs — not reviews",
        "example_one": "example sign-off — not a review",
        "changes": "Change requests",
    },
    "engineer": {
        "pass": "pass",
        "fail": "fail",
        "warn": "warn",
        "skip": "skip",
        "needs-human": "needs-human",
        "signed": "signed",
        "example": "example sign-offs — not reviews",
        "example_one": "example sign-off — not a review",
        "changes": "Change requests (ECRs)",
    },
}


def anchor_for(uri: str, anchors: dict[str, str]) -> str | None:
    """The in-page anchor a model URI points at, ignoring any ``#selector`` suffix."""
    base = uri.split("#", 1)[0]
    if base in anchors:
        return anchors[base]
    scheme = base.split("://", 1)[0] if "://" in base else ""
    return {
        "bom": "parts",
        "rule": "rules",
        "manifest": "overview",
        "param": "parameters",
        "req": "requirements",
        "dec": "decisions",
        "ecr": "changes",
        "doc": "manuals",
        "iface": "interfaces",
        "asm": "model",
    }.get(scheme)


def ref_html(uri: Any, anchors: dict[str, str], persona: str = "engineer") -> Markup:
    """Render a URI as a hyperlink to its row when the page has one, else as plain text.

    The link target always uses the full URI; the visible text follows the persona's
    display rule (:func:`~napkin2factory.core.uris.display_uri`).
    """
    text = str(uri)
    anchor = anchor_for(text, anchors)
    shown = display_uri(text, persona)
    if anchor is None:
        return Markup('<span class="mono">{}</span>').format(shown)
    return Markup('<a class="ref mono" href="#{}">{}</a>').format(anchor, shown)


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


def _spec_summary(spec: Any) -> str:
    kind = type(spec).__name__
    if kind == "BoltPatternSpec":
        return f"{spec.count} × ⌀{spec.diameter}, {spec.pattern}"
    if kind == "MatingFaceSpec":
        return f"{spec.width} × {spec.depth}"
    return kind


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
    summary = {k: int(checks.get("summary", {}).get(k, 0)) for k in SUMMARY_KEYS}
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
    drawn = {d["uri"] for d in drawings}
    seen_rows: set[str] = set()
    for ln in flat:
        ln["anchor"] = ln["uri"] not in seen_rows  # the first row of a URI is its anchor
        seen_rows.add(ln["uri"])
        ln["has_drawing"] = ln["uri"] in drawn
    for uri, row in bom_by_uri.items():
        row["id"] = uri.split("://", 1)[-1]
        row["has_drawing"] = uri in drawn
        row["in_bom"] = uri in seen_rows

    # every URI that has a row on this page, so references can be hyperlinks
    anchors: dict[str, str] = {}
    for uri in seen_rows:
        anchors[uri] = f"part-{uri.split('://', 1)[-1]}"
    for r in product.requirements:
        anchors[f"req://{r}"] = f"req-{r}"
    for d in product.decisions:
        anchors[f"dec://{d}"] = f"dec-{d}"
    for slug in product.parameters:
        anchors[f"param://{slug}"] = f"param-{slug}"
    for e in product.ecrs:
        anchors[f"ecr://{e}"] = f"ecr-{e}"
    for d in product.docs:
        anchors[f"doc://{d}"] = f"doc-{d}"
    for i in product.interfaces:
        anchors[f"iface://{i}"] = f"iface-{i}"
    for a in product.assemblies.values():
        anchors.setdefault(a.uri, "model")

    def signoff_example(rid: str) -> bool:
        so = product.signoffs.get(rid)
        return bool(so and so.example)

    satisfied_by: dict[str, list[str]] = {}
    for p in product.parts.values():
        for r in p.satisfies:
            satisfied_by.setdefault(r.id, []).append(p.uri)
    for a in product.assemblies.values():
        for r in a.satisfies:
            satisfied_by.setdefault(r.id, []).append(a.uri)
    matrix_rows = {row["id"]: row for row in checks.get("matrix", {}).get("requirements", [])}
    req_rows = []
    for rid, req in product.requirements.items():
        row = matrix_rows.get(rid)
        res = results.get(f"req://{rid}", {})
        status = res.get("status", row["status"] if row else "skip")
        req_rows.append(
            {
                "id": rid,
                "title": req.title,
                "statement": req.statement,
                "category": req.category,
                "priority": req.priority,
                "safety": req.safety,
                "kind": req.verify.kind if req.verify else "—",
                "target": str(req.verify.target) if req.verify and req.verify.target else "",
                "status": status,
                "message": res.get("message", (row or {}).get("message", "not checked yet")),
                "allocation": [str(a) for a in req.allocation]
                if isinstance(req.allocation, list)
                else [str(req.allocation or "")],
                "satisfied_by": satisfied_by.get(rid, []),
                "signoff_example": signoff_example(rid) and status in ("signed", "pass"),
                "signed": rid in product.signoffs,
            }
        )
    safety_reqs = [r for r in req_rows if r.get("safety")]
    other_rows = [
        r for r in checks.get("results", []) if r["kind"] != "requirement" and r["status"] != "pass"
    ]
    rule_results = [r for r in checks.get("results", []) if r["kind"] != "requirement"]
    rule_summary = {k: sum(1 for r in rule_results if r["status"] == k) for k in SUMMARY_KEYS}

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

    interfaces = [
        {
            "id": i.id,
            "kind": i.kind,
            "parties": [str(p) for p in i.parties],
            "description": i.description or "",
            "spec": _spec_summary(i.spec),
        }
        for i in product.interfaces.values()
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
    for s in sorted(product.signoffs.values(), key=lambda x: str(x.requirement)):
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
        "words": VOCAB[persona],
        "sections": SECTIONS,
        "anchors": anchors,
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
        "rule_summary": rule_summary,
        "rule_matrix": checks.get("matrix", {}).get(
            "rules", {"parts": [], "rules": {}, "cells": {}}
        ),
        "interfaces": interfaces,
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
    anchors = data["anchors"]
    persona = data["persona"]
    env.filters["ref"] = lambda uri: ref_html(uri, anchors, persona)
    env.filters["disp"] = lambda uri: display_uri(str(uri), persona)
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
