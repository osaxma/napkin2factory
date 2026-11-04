"""The self-contained HTML report (decisions D13, D17 as amended by S-050).

One page, zero external references: three.js and the viewer inlined as a single module
script, GLBs and renders embedded as base64, drawings inlined as SVG, manuals as HTML
fragments.  One layout for everyone: a sticky section index, sections grouped by purpose
(overview, safety, product, verification, design record, manuals), and every model URI
rendered as a hyperlink to the row that describes it.  The operator persona only picks
the words used for check statuses and whether visible URIs keep their ``scheme://`` prefix
(the owner reads ``lid``, the engineer ``part://lid``; attributes and
anchors always carry the full URI); safety content is always visible.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jinja2

from napkin2factory import __version__
from napkin2factory.core.checks.results import SUMMARY_KEYS
from napkin2factory.core.graph.hashing import sha256_text
from napkin2factory.core.loader import Product
from napkin2factory.core.uris import display_uri
from napkin2factory.report.builder_common import (
    MAX_REPORT_BYTES,
    TEMPLATES,
    VOCAB,
    anchor_for,
    ref_html,
    report_reads,
    scope_reads,
    sections,
)
from napkin2factory.report.builder_plan import (
    _between_units,
    _bom_by_uri,
    _build_steps,
    _by_module,
    _doc_html,
    _flatten_bom,
    _read_json,
    _spec_summary,
    _viewer_options,
    waiting_on_you,
)
from napkin2factory.report.units import display

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext, RunResult


def __getattr__(name: str) -> Any:
    """``SECTIONS`` is the report-section registry's view (F5), read on each access."""
    if name == "SECTIONS":
        return sections()
    raise AttributeError(name)


def _cost_basis_line(product: Product) -> str:
    """One plain line naming the region and date of the cost bands behind the estimates.

    Read from the bands of the processes the parts use; empty when no part's process has a
    band (the costs are then the owner's own numbers). The region is the product's; with none
    declared the line says the US bands were read (gate I, B2, S-227).
    """
    from napkin2factory.calckit import mass_cost

    region = getattr(product.manifest, "region", None)
    declared = region is not None
    if declared and str(region).upper() not in mass_cost.band_regions():
        region, declared = None, False  # a supply-only region: the US bands, said as such
    bands = []
    for process in sorted({p.process for p in product.parts.values() if p.process}):
        band = mass_cost.cost_band(process, region=region)
        if band.known:
            bands.append(band)
    if not bands:
        return ""
    return f"Estimated from the {mass_cost.bands_words(bands, declared=declared)}."


def _cost_notes(product: Product, flat: list[dict[str, Any]]) -> list[str]:
    """Number the distinct cost notes of the parts on the page; each line gets ``cost_note_no``.

    A price taken from the middle of a cost band says so here (``mid-point of the US controls
    band``), so equal prices on different parts do not look invented (gate J, S-227).
    """
    by_uri = {p.uri: p for p in product.parts.values()}
    notes: list[str] = []
    for ln in flat:
        ln["cost_note_no"] = 0  # no note (the template is strict about missing keys)
        part = by_uri.get(ln["uri"])
        note = part.cost.note if part is not None and part.cost is not None else None
        if note:
            shown = display(note, getattr(product.manifest, "units", "metric"))
            if shown not in notes:
                notes.append(shown)
            ln["cost_note_no"] = notes.index(shown) + 1
    return notes


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
    stage = compute_stage(product, build_dir, napkin=False)  # concepts never reach a build (N1)
    persona = product.operator.persona
    manifest_units = getattr(product.manifest, "units", "metric")

    # 3D: the top assemblies' GLBs (or every part's GLB when there is no assembly)
    glb_paths = [build_dir / "assemblies" / a / "model.glb" for a in top_assemblies(product)]
    if not glb_paths:
        glb_paths = [
            build_dir / "parts" / p.id / "model.glb" for p in product.parts_with_geometry()
        ]
    glb_paths = [p for p in glb_paths if p.is_file()]
    glb_b64 = base64.b64encode(glb_paths[0].read_bytes()).decode() if glb_paths else ""
    viewer_options = _viewer_options(product)
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
        ln["name"] = display(ln.get("name", ""), manifest_units)
        ln["manufacturer"] = display(ln.get("manufacturer", ""), manifest_units)
    cost_notes = _cost_notes(product, flat)
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
        msg = res.get("message", (row or {}).get("message", "not checked yet"))
        req_rows.append(
            {
                "id": rid,
                "title": req.title,
                "statement": display(req.statement, manifest_units),
                "category": req.category,
                "priority": req.priority,
                "safety": req.safety,
                "kind": req.verify.kind if req.verify else "—",
                "target": str(req.verify.target) if req.verify and req.verify.target else "",
                "status": status,
                "message": display(msg, manifest_units),
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
    module_groups, other_groups, rule_matrix = _by_module(checks, other_rows)

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

    build_steps = _build_steps(build_dir, results, VOCAB[persona])
    waiting = waiting_on_you(build_dir)
    between_units = _between_units(build_dir, product, results)

    interfaces = [
        {
            "id": i.id,
            "kind": i.kind,
            "parties": [str(p) for p in i.parties],
            "description": i.description or "",
            "spec": _spec_summary(i.spec, product, manifest_units),
        }
        for i in product.interfaces.values()
    ]
    params = []
    for slug, p in product.parameters.items():
        try:
            value = display(product.parameter_value(slug), manifest_units)
        except Exception as exc:
            value = f"invalid: {exc}"
        description = display(p.description, manifest_units) if p.description else ""
        params.append({"slug": slug, "value": value, "description": description, "expr": p.expr})
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
    # the badge names the stage being worked in, as `n2f status` does (S-090)
    stage_label = stage.current_words
    if stage.current == "ready":
        stage_label = "Ready to release"
    elif stage.current == "released":
        stage_label = f"Released {revision or ''}".strip()
    verify_gate = next(g for g in stage.gates if g.name == "verify")
    if stage.current == "released":
        stage_class = "ok"
    elif stage.current == "ready" or verify_gate.open_only_by_caveats:
        stage_class = "warn"  # nothing blocks a release (example sign-offs need --allow…)
    else:
        stage_class = "skip"
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
        "sections": sections(product),
        "anchors": anchors,
        "stage": stage,
        "waiting": waiting,
        "stage_label": stage_label,
        "stage_class": stage_class,
        "revision_label": revision_label,
        "summary": summary,
        "glb_b64": glb_b64,
        "viewer_options": viewer_options,
        "exploded": exploded,
        "renders": renders,
        "drawings": drawings,
        "rollups": rollups,
        "bom_lines": flat,
        "cost_notes": cost_notes,
        "cost_basis_line": _cost_basis_line(product),
        "bom_json": json.dumps(bom_by_uri),
        "req_rows": req_rows,
        "safety_reqs": safety_reqs,
        "other_rows": other_rows,
        "rule_summary": rule_summary,
        "rule_matrix": rule_matrix,
        "module_groups": module_groups,
        "other_groups": other_groups,
        "interfaces": interfaces,
        "build_steps": build_steps,
        "between_units": between_units,
        "params": params,
        "decisions": decisions,
        "ecrs": ecrs,
        "docs": docs,
        "safety_docs": safety_docs,
        "signoffs": signoffs,
        "units": manifest_units,
        "version": __version__,
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def render_report(
    product: Product, build_dir: Path, snapshot_date: str, build_id: str = "", log: Any = None
) -> str:
    """Render the page HTML (the viewer bundle inlined).

    ``log`` (the ``report`` rule's) receives what a section's ``data`` read through its
    context's ``proxy`` (D5, S-138).
    """
    from napkin2factory.core.domain import SectionContext
    from napkin2factory.core.registry import registry
    from napkin2factory.report.brand import favicon_link, footer_mark, footer_wordmark
    from napkin2factory.report.inline import bundle_viewer, inline_module_script

    reg = registry()
    fragments = {f"section:{sec.id}": reg.fragment_path(sec) for sec in reg.report_sections()}

    def load_fragment(name: str) -> str | None:
        path = fragments.get(name)
        return path.read_text(encoding="utf-8") if path is not None else None

    # the page shell, then one fragment per registered section (F5): a domain adds a section
    # without editing the page
    env = jinja2.Environment(
        loader=jinja2.ChoiceLoader(
            [jinja2.FileSystemLoader(str(TEMPLATES)), jinja2.FunctionLoader(load_fragment)]
        ),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )
    env.globals["n2f_favicon"] = favicon_link()
    env.globals["n2f_mark"] = footer_mark()
    env.globals["n2f_wordmark"] = footer_wordmark()
    data = gather(product, build_dir, snapshot_date)
    anchors = data["anchors"]
    persona = data["persona"]
    env.filters["ref"] = lambda uri: ref_html(uri, anchors, persona)
    env.filters["disp"] = lambda uri: display_uri(str(uri), persona)
    env.filters["display"] = lambda q: display(q, data["units"])
    data["viewer_script"] = inline_module_script(bundle_viewer()) if data["glb_b64"] else ""
    data["build_id"] = build_id
    shown = {sid for sid, _, _ in data["sections"]}
    data["page_sections"] = [
        {"id": sec.id, "template": f"section:{sec.id}"}
        for sec in reg.report_sections()
        if sec.id in shown
    ]
    sctx = SectionContext(product, build_dir)
    if log is not None:
        sctx.log = log
    data["section_data"] = {
        sec.id: sec.data(sctx)
        for sec in reg.report_sections()
        if sec.id in shown and sec.data is not None
    }
    return env.get_template("report.html.j2").render(**data)


def build_report(ctx: RunContext) -> RunResult:
    """The ``report`` rule body."""
    from napkin2factory.core.graph.rules import RunResult

    html = render_report(ctx.product, ctx.build_dir, ctx.snapshot_date, log=ctx.log)
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


__all__ = [
    "MAX_REPORT_BYTES",
    "TEMPLATES",
    "VOCAB",
    "_between_units",
    "_bom_by_uri",
    "_build_steps",
    "_by_module",
    "_doc_html",
    "_flatten_bom",
    "_read_json",
    "_spec_summary",
    "_viewer_options",
    "anchor_for",
    "build_report",
    "gather",
    "ref_html",
    "render_report",
    "report_reads",
    "scope_reads",
    "sections",
    "waiting_on_you",
]
