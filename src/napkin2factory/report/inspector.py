"""Structured inspector index for the interactive report workbench (M2).

Builds a URI-keyed dictionary of plain-JSON entries for ``manifest://product`` and every
``part://``, ``asm://``, ``iface://``, ``req://``, ``rule://`` and ``doc://`` object in the
product, merged with domain entries from :meth:`Registry.inspector_entries`.  Every model
field shown is read through ``sctx.proxy`` (D5) so edits to shown fields invalidate the
``report`` rule.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from napkin2factory.bom.rollups import cost_basis_of, top_assemblies
from napkin2factory.core.build_units import BuildUnits
from napkin2factory.core.checks.results import OWNER_WORDS
from napkin2factory.core.checks.stage import compute_stage
from napkin2factory.core.registry import registry
from napkin2factory.core.uris import Uri
from napkin2factory.report.builder_common import VOCAB
from napkin2factory.report.builder_plan import _build_steps, _spec_summary, waiting_on_you
from napkin2factory.report.units import display

if TYPE_CHECKING:
    from napkin2factory.core.checks.stage import StageReport
    from napkin2factory.core.domain import SectionContext
    from napkin2factory.core.loader import Product

_STATUS_RANK = {
    "fail": 0,
    "warn": 1,
    "needs-human": 2,
    "choice": 3,
    "pass": 4,
    "signed": 4,
    "skip": 5,
    "example": 6,
    "later": 7,
}


def inspector_json(index: dict[str, dict[str, Any]]) -> str:
    """Serialize ``index`` for embedding in ``<script type="application/json">``.

    Escapes ``</`` and ``<!--`` using valid JSON escapes so script tags cannot close early
    and ``json.loads`` recovers the exact ``inspector_index`` dictionary.
    """
    raw = json.dumps(index, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw.replace("</", "<\\/").replace("<!--", "\\u003c!--")


def _walk_bom_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten nested BOM lines from ``rollups.json``."""
    out: list[dict[str, Any]] = []
    for ln in lines:
        out.append(ln)
        out.extend(_walk_bom_lines(ln.get("children", [])))
    return out


def _find_asm_node(
    structure: dict[str, list[dict[str, Any]]], asm_uri: str
) -> tuple[list[dict[str, Any]], int] | None:
    """Return ``(child_lines, parent_multiplier)`` for ``asm_uri`` in ``rollups.structure``."""
    if asm_uri in structure:
        return structure[asm_uri], 1
    for top_lines in structure.values():
        for ln in _walk_bom_lines(top_lines):
            if ln.get("uri") == asm_uri and ln.get("kind") == "assembly":
                mult = max(int(ln.get("total_qty", 1) or 1), 1)
                return ln.get("children", []), mult
    return None


def _asm_rollup_stats(
    product: Product,
    aid: str,
    asm: Any,
    rollups: dict[str, Any],
    bom_by_uri: dict[str, dict[str, Any]],
    build_dir: Any,
) -> tuple[int, float | None, float]:
    """Compute ``(part_count, mass_kg, cost_usd)`` for ``asm://<aid>`` from ``rollups.json``."""
    asm_uri = f"asm://{aid}"
    structure: dict[str, list[dict[str, Any]]] = rollups.get("structure", {})
    found = _find_asm_node(structure, asm_uri)
    if found is not None:
        child_lines, mult = found
        leaves = [
            ln
            for ln in _walk_bom_lines(child_lines)
            if ln.get("kind") not in ("assembly", "reference")
        ]
        part_count = sum(max(int(ln.get("total_qty", 0) or 0) // mult, 0) for ln in leaves)
        mass_total = 0.0
        has_mass = False
        cost_total = 0.0
        for ln in leaves:
            qty = max(int(ln.get("total_qty", 0) or 0) // mult, 0)
            m = ln.get("mass_kg")
            if m is not None:
                mass_total += float(m) * qty
                has_mass = True
            u = ln.get("unit_cost")
            if u is not None:
                cost_total += float(u) * qty
        props_path = build_dir / "assemblies" / aid / "props.json"
        if not has_mass and props_path.is_file():
            props = json.loads(props_path.read_text(encoding="utf-8"))
            if props.get("mass") is not None:
                mass_total = float(props["mass"])
                has_mass = True
        return part_count, (round(mass_total, 4) if has_mass else None), round(cost_total, 2)

    # Fallback when the assembly is not in rollups.structure (e.g. external or unbuilt).
    part_count = 0
    mass_total = 0.0
    has_mass = False
    cost_total = 0.0
    for ch in asm.children:
        if ch.part is not None:
            puri = str(ch.part)
            p_obj = product.parts.get(ch.part.id)
            if p_obj is not None and p_obj.kind == "reference":
                continue
            part_count += int(ch.qty)
            b = bom_by_uri.get(puri, {})
            if b.get("mass_kg") is not None:
                mass_total += float(b["mass_kg"]) * int(ch.qty)
                has_mass = True
            if b.get("unit_cost") is not None:
                cost_total += float(b["unit_cost"]) * int(ch.qty)
    props_path = build_dir / "assemblies" / aid / "props.json"
    if props_path.is_file():
        props = json.loads(props_path.read_text(encoding="utf-8"))
        if not has_mass and props.get("mass") is not None:
            mass_total = float(props["mass"])
            has_mass = True
    return part_count, (round(mass_total, 4) if has_mass else None), round(cost_total, 2)


def _strip_step_for_inspector(step: dict[str, Any]) -> dict[str, Any]:
    """Copy a build step without its inline ``sheet_svg`` markup (D13/N10 size budget)."""
    out: dict[str, Any] = {
        "step": step.get("step"),
        "id": step.get("id"),
        "unit": step.get("unit"),
        "title": step.get("title", ""),
        "why": step.get("why", ""),
        "anchor": f"step-{step.get('id', '')}",
        "items": [
            {
                "item": it.get("item"),
                "uri": it.get("uri"),
                "name": it.get("name"),
                "qty": it.get("qty"),
                "notes": list(it.get("notes", [])),
            }
            for it in step.get("items", [])
        ],
        "joints": [
            {
                "interface": j.get("interface"),
                "words": j.get("words", ""),
                "occurrences": j.get("occurrences", 0),
                "holes": j.get("holes", 0),
                "hardware_words": j.get("hardware_words", ""),
                "status_words": j.get("status_words", ""),
            }
            for j in step.get("joints", [])
        ],
        "check_summary": step.get("check_summary", ""),
    }
    if step.get("sheet_svg"):
        out["sheet_anchor"] = f"sheet-{step.get('id', '')}"
    return out


def _part_checks_trace(
    pid: str,
    part_uri: str,
    checks_data: dict[str, Any],
    manifest_data: dict[str, Any],
    words: dict[str, str],
    units: str,
) -> list[dict[str, Any]]:
    """Return rule checks that read ``part://<pid>`` with their evaluation status.

    Trace source: ``build/checks/checks.json`` (``matrix.rules.cells[pid]`` and ``results``
    rows whose ``subject`` or ``evidence_keys`` reference ``part://<id>``), supplemented by
    ``build/.n2f/manifest.json`` when present.  We use ``checks.json`` as the primary trace
    because it records per-rule, per-part verdicts and messages (`rule://<pack>/<rule>@<id>`),
    whereas ``manifest.json`` aggregates recorded reads at the whole ``checks`` rule level
    without per-rule status.
    """
    rules_matrix = checks_data.get("matrix", {}).get("rules", {})
    rule_titles: dict[str, str] = dict(rules_matrix.get("rules", {}))
    part_cells: dict[str, str] = dict(rules_matrix.get("cells", {}).get(pid, {}))
    results_list: list[dict[str, Any]] = checks_data.get("results", [])

    # Index result rows by (rule_uri, part_id) for message lookup and extra rule rows.
    row_by_rule: dict[str, dict[str, Any]] = {}
    for r in results_list:
        rid_full = str(r.get("id", ""))
        if not rid_full.startswith("rule://"):
            continue
        base_rule, sep, target = rid_full.partition("@")
        ev = r.get("evidence_keys") or {}
        if target == pid or r.get("subject") == part_uri or part_uri in ev:
            row_by_rule[base_rule] = r
            part_cells.setdefault(base_rule, str(r.get("status", "skip")))
            rule_titles.setdefault(base_rule, str(r.get("title", base_rule)))

    # Touch manifest entries when available so recorded build provenance is consulted.
    _ = manifest_data.get("entries", {}).get(f"part:{pid}", {}).get("reads", [])

    out: list[dict[str, Any]] = []
    for rule_uri in sorted(part_cells):
        try:
            Uri.parse(rule_uri)
        except ValueError:
            continue
        status = str(part_cells[rule_uri])
        row = row_by_rule.get(rule_uri, {})
        title = display(str(rule_titles.get(rule_uri) or row.get("title") or rule_uri), units)
        msg_raw = str(row.get("persona_message") or row.get("message") or "")
        out.append(
            {
                "uri": rule_uri,
                "title": title,
                "status": status,
                "status_words": words.get(status, status),
                "message": display(msg_raw, units),
            }
        )
    return out


def inspector_index(
    sctx: SectionContext,
    *,
    rollups: dict[str, Any] | None = None,
    checks: dict[str, Any] | None = None,
    stage: StageReport | None = None,
    waiting: list[dict[str, Any]] | None = None,
    build_steps: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build the URI-keyed inspector index from recorded model reads and build outputs."""
    product, build_dir = sctx.product, sctx.build_dir
    units = product.manifest.units
    words = dict(OWNER_WORDS)

    if rollups is None:
        rollups_path = build_dir / "bom" / "rollups.json"
        rollups = (
            json.loads(rollups_path.read_text(encoding="utf-8"))
            if rollups_path.is_file()
            else {
                "flat": [],
                "structure": {},
                "part_count": 0,
                "total_mass": 0.0,
                "total_cost": 0.0,
            }
        )
    if checks is None:
        checks_path = build_dir / "checks" / "checks.json"
        checks = (
            json.loads(checks_path.read_text(encoding="utf-8"))
            if checks_path.is_file()
            else {"status": "unknown", "summary": {}, "results": [], "matrix": {}, "calcs": {}}
        )
    if waiting is None:
        waiting = waiting_on_you(build_dir)
    if stage is None:
        stage = compute_stage(product, build_dir, napkin=False)

    manifest_path = build_dir / ".n2f" / "manifest.json"
    manifest_data: dict[str, Any] = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    )

    bom_by_uri: dict[str, dict[str, Any]] = {
        ln["uri"]: ln for ln in rollups.get("flat", []) if "uri" in ln
    }
    results_list: list[dict[str, Any]] = checks.get("results", [])
    results_by_id: dict[str, dict[str, Any]] = {str(r["id"]): r for r in results_list if "id" in r}
    if build_steps is None:
        persona = product.operator.persona
        build_steps = _build_steps(build_dir, results_by_id, VOCAB[persona])

    # Merge domain inspector entries first so parts can cross-reference domain objects if needed.
    domain_entries = registry().inspector_entries(sctx)

    index: dict[str, dict[str, Any]] = {}

    # ---- 1. manifest://product -------------------------------------------------------------------
    prod_info = sctx.proxy(product.manifest.product, "manifest://product")
    prod_name = display(str(prod_info.name), units)
    prod_id = str(prod_info.id)
    prod_desc = display(str(prod_info.description or ""), units)

    part_count = int(rollups.get("part_count", 0) or 0)
    custom_count = int(rollups.get("custom_count", 0) or 0)
    total_mass = float(rollups.get("total_mass", 0.0) or 0.0)
    mass_complete = bool(rollups.get("mass_complete", True))
    total_cost = float(rollups.get("total_cost", 0.0) or 0.0)
    cost_complete = bool(rollups.get("cost_complete", True))

    flat_parts = [
        ln for ln in rollups.get("flat", []) if ln.get("kind") not in ("assembly", "reference")
    ]
    all_mass_declared = bool(flat_parts) and all(
        ln.get("mass_source") == "declared" for ln in flat_parts if ln.get("mass_kg") is not None
    )
    mass_label = "given" if all_mass_declared else "computed"
    basis_raw = cost_basis_of(rollups)
    cost_label = "estimate" if basis_raw == "estimate" else "given"

    tops = top_assemblies(product)
    unit_uris = [f"asm://{a}" for a in tops]
    build_unit_uris = [f"asm://{u}" for u in BuildUnits(product).order()]

    n_choices = len(waiting)
    choice_val = (
        "no open choices"
        if n_choices == 0
        else ("1 open choice" if n_choices == 1 else f"{n_choices} open choices")
    )

    vitals: dict[str, Any] = {
        "part_count": {
            "value": f"{part_count} parts",
            "raw": part_count,
            "custom_count": custom_count,
            "label": "computed",
        },
        "total_mass": {
            "value": display(f"{round(total_mass, 3)} kg", units),
            "raw": round(total_mass, 4),
            "complete": mass_complete,
            "label": mass_label,
        },
        "total_cost": {
            "value": f"{round(total_cost, 2):.2f} USD",
            "raw": round(total_cost, 2),
            "complete": cost_complete,
            "label": cost_label,
        },
        "open_choices": {
            "value": choice_val,
            "raw": n_choices,
            "label": "given",
        },
    }

    # Envelope: combined bbox of all top units from build_dir/assemblies/<id>/props.json.
    top_ids = [u.removeprefix("asm://") for u in (unit_uris if unit_uris else build_unit_uris)]
    props_bboxes: list[dict[str, Any]] = []
    if top_ids and build_dir is not None:
        all_props_found = True
        for aid in top_ids:
            props_file = build_dir / "assemblies" / aid / "props.json"
            if not props_file.is_file():
                all_props_found = False
                break
            try:
                pdata = json.loads(props_file.read_text(encoding="utf-8"))
                if isinstance(pdata, dict) and isinstance(pdata.get("bbox"), dict):
                    props_bboxes.append(pdata["bbox"])
                else:
                    all_props_found = False
                    break
            except Exception:
                all_props_found = False
                break
        if all_props_found and props_bboxes:
            min_pts = [b["min"] for b in props_bboxes if "min" in b]
            max_pts = [b["max"] for b in props_bboxes if "max" in b]
            if (
                min_pts
                and max_pts
                and len(min_pts) == len(props_bboxes)
                and len(max_pts) == len(props_bboxes)
            ):
                raw_x = round(float(max(p[0] for p in max_pts) - min(p[0] for p in min_pts)), 4)
                raw_y = round(float(max(p[1] for p in max_pts) - min(p[1] for p in min_pts)), 4)
                raw_z = round(float(max(p[2] for p in max_pts) - min(p[2] for p in min_pts)), 4)
            elif len(props_bboxes) == 1 and all(k in props_bboxes[0] for k in ("x", "y", "z")):
                raw_x = round(float(props_bboxes[0]["x"]), 4)
                raw_y = round(float(props_bboxes[0]["y"]), 4)
                raw_z = round(float(props_bboxes[0]["z"]), 4)
            else:
                raw_x = raw_y = raw_z = None

            if raw_x is not None and raw_y is not None and raw_z is not None:

                def _format_dim(v: float) -> str:
                    r = round(v, 1)
                    if r.is_integer() or round(v) == r:
                        return str(round(v))
                    return f"{r:.1f}"

                dim_str = f"{_format_dim(raw_x)} × {_format_dim(raw_y)} × {_format_dim(raw_z)} mm"
                vitals["envelope"] = {
                    "value": display(dim_str, units),
                    "raw": [raw_x, raw_y, raw_z],
                    "label": "computed",
                }

    summary_counts: dict[str, int] = {
        k: int(v) for k, v in (checks.get("summary") or {}).items() if isinstance(v, (int, float))
    }
    gates_list: list[dict[str, Any]] = []
    if stage is not None:
        for g in stage.gates:
            g_status = "ok" if g.ok else ("warn" if g.open_only_by_caveats else "skip")
            gates_list.append(
                {
                    "name": g.name,
                    "ok": bool(g.ok),
                    "status": g_status,
                    "blockers": [display(str(b), units) for b in g.blockers],
                    "caveats": [display(str(c), units) for c in g.caveats],
                }
            )

    open_choices = [
        {
            "id": str(c.get("id", "")),
            "title": display(str(c.get("title", "")), units),
            "holds": display(str(c.get("holds", "")), units),
            "command": str(c.get("command", "")),
        }
        for c in waiting
    ]

    needs_human: list[dict[str, Any]] = []
    for r in results_list:
        if r.get("status") == "needs-human":
            rid_str = str(r.get("id", ""))
            needs_human.append(
                {
                    "id": rid_str.removeprefix("req://"),
                    "uri": rid_str if "://" in rid_str else f"req://{rid_str}",
                    "title": display(str(r.get("title", "")), units),
                    "message": display(
                        str(r.get("persona_message") or r.get("message", "")), units
                    ),
                }
            )

    param_rows: list[dict[str, Any]] = []
    for slug, raw_p in product.parameters.items():
        p = sctx.proxy(raw_p, f"param://{slug}")
        sctx.log.add(f"param://{slug}")
        p_expr = p.expr
        p_desc = p.description
        try:
            p_val = display(str(product.parameter_value(slug)), units)
        except Exception as exc:
            p_val = f"error: {exc}"
        param_rows.append(
            {
                "slug": slug,
                "uri": f"param://{slug}",
                "value": p_val,
                "kind": "computed" if p_expr is not None else "given",
                "expr": p_expr,
                "description": display(str(p_desc), units) if p_desc else "",
            }
        )

    index["manifest://product"] = {
        "kind": "product",
        "id": prod_id,
        "uri": "manifest://product",
        "name": prod_name,
        "title": prod_name,
        "description": prod_desc,
        "vitals": vitals,
        "gate_summary": summary_counts,
        "gates": gates_list,
        "open_choices": open_choices,
        "needs_human": needs_human,
        "parameters": param_rows,
        "unit_uris": unit_uris,
        "units": unit_uris,
        "build_units": build_unit_uris,
    }

    # ---- Pre-index interfaces and requirements by party/satisfaction -----------------------------
    ifaces_by_party: dict[str, list[str]] = {}
    for iid, raw_iface in sorted(product.interfaces.items()):
        iuri = raw_iface.uri
        for party in raw_iface.parties:
            p_str = str(party)
            if iuri not in ifaces_by_party.setdefault(p_str, []):
                ifaces_by_party[p_str].append(iuri)

    satisfied_by: dict[str, list[str]] = {rid: [] for rid in product.requirements}
    for part_val in product.parts.values():
        for req_ref in part_val.satisfies:
            if req_ref.id in satisfied_by and part_val.uri not in satisfied_by[req_ref.id]:
                satisfied_by[req_ref.id].append(part_val.uri)
    for asm_val in product.assemblies.values():
        for req_ref in asm_val.satisfies:
            if req_ref.id in satisfied_by and asm_val.uri not in satisfied_by[req_ref.id]:
                satisfied_by[req_ref.id].append(asm_val.uri)

    steps_by_unit: dict[str, list[dict[str, Any]]] = {}
    if build_steps:
        for st in build_steps:
            u = str(st.get("unit") or (f"asm://{st['id']}" if st.get("id") else ""))
            if u:
                steps_by_unit.setdefault(u, []).append(_strip_step_for_inspector(st))

    # ---- 2. asm://<id> ---------------------------------------------------------------------------
    for aid, raw_asm in sorted(product.assemblies.items()):
        auri = raw_asm.uri
        asm = sctx.proxy(raw_asm, auri)
        aname = display(str(asm.name), units)
        abuild = str(asm.build)
        aports = [str(p) for p in asm.ports]
        _ = asm.satisfies
        _ = asm.children

        asm_ifaces = list(aports)
        for iuri in ifaces_by_party.get(auri, []):
            if iuri not in asm_ifaces:
                asm_ifaces.append(iuri)

        a_part_count, a_mass_kg, a_cost_usd = _asm_rollup_stats(
            product, aid, raw_asm, rollups, bom_by_uri, build_dir
        )
        a_mass_str = display(f"{round(a_mass_kg, 3)} kg", units) if a_mass_kg is not None else None
        a_cost_str = f"{round(a_cost_usd, 2):.2f} USD"

        structure: dict[str, list[dict[str, Any]]] = rollups.get("structure", {})
        found = _find_asm_node(structure, auri)
        asm_children: list[dict[str, Any]] = []
        if found is not None:
            child_lines, mult = found
            for ln in child_lines:
                if "uri" in ln:
                    child_qty = (
                        int(ln["qty"])
                        if "qty" in ln
                        else max(int(ln.get("total_qty", 0) or 0) // mult, 0)
                    )
                    asm_children.append({"uri": str(ln["uri"]), "qty": child_qty})

        asm_entry: dict[str, Any] = {
            "kind": "assembly",
            "id": aid,
            "uri": auri,
            "name": aname,
            "title": aname,
            "build": abuild,
            "part_count": a_part_count,
            "children": asm_children,
            "mass": a_mass_str,
            "mass_kg": a_mass_kg,
            "mass_label": "computed",
            "cost": a_cost_str,
            "bom_cost": a_cost_usd,
            "cost_usd": a_cost_usd,
            "cost_label": cost_label,
            "ports": aports,
            "interfaces": asm_ifaces,
        }

        sheet_file = build_dir / "drawings" / "assemblies" / f"{aid}.svg"
        if sheet_file.is_file():
            rel_sheet = f"build/drawings/assemblies/{aid}.svg"
            asm_entry["drawing"] = rel_sheet
            asm_entry["sheet"] = rel_sheet
            asm_entry["sheet_anchor"] = f"sheet-{aid}"

        unit_steps = steps_by_unit.get(auri)
        if unit_steps:
            asm_entry["build_steps"] = unit_steps

        index[auri] = asm_entry

    # ---- 3. part://<id> --------------------------------------------------------------------------
    for pid, raw_part in sorted(product.parts.items()):
        puri = raw_part.uri
        part = sctx.proxy(raw_part, puri)
        pname = display(str(part.name), units)
        pkind = str(part.kind)
        pproc = str(part.process)
        pfinish = part.finish
        ptol = part.tolerance_class
        pmat_proxy = part.material
        if pmat_proxy is not None:
            mat_name = pmat_proxy.name
            mat_spec = pmat_proxy.spec
            pmat: str | None = str(mat_spec or mat_name)
        else:
            pmat = None

        # Mass: declared on model (given) or computed from geometry props.json (computed).
        pmass_decl = part.mass
        props_file = build_dir / "parts" / pid / "props.json"
        if pmass_decl is not None:
            pmass_kg: float | None = round(float(pmass_decl.to("kg").magnitude), 4)
            pmass_label: str | None = "given"
        elif props_file.is_file():
            sctx.log.add(f"{puri}#props.mass")
            props_data = json.loads(props_file.read_text(encoding="utf-8"))
            pmass_kg = (
                round(float(props_data["mass"]), 4) if props_data.get("mass") is not None else None
            )
            pmass_label = str(props_data.get("mass_source", "computed"))
            if pmass_label == "declared":
                pmass_label = "given"
        else:
            pmass_kg = None
            pmass_label = None
        pmass_str = display(f"{round(pmass_kg, 3)} kg", units) if pmass_kg is not None else None

        # Cost: read through part.cost proxy + rollups quantity.
        pcost_proxy = part.cost
        bom_line = bom_by_uri.get(puri, {})
        if pcost_proxy is not None:
            unit_cost: float | None = round(float(pcost_proxy.unit.to("USD").magnitude), 2)
            p_basis = str(pcost_proxy.basis)
            _ = pcost_proxy.note
            pcost_label: str | None = "estimate" if p_basis == "estimate" else "given"
            pcost_str: str | None = f"{unit_cost:.2f} USD"
        elif bom_line.get("unit_cost") is not None:
            unit_cost = round(float(bom_line["unit_cost"]), 2)
            pcost_label = "estimate"
            pcost_str = f"{unit_cost:.2f} USD"
        else:
            unit_cost = None
            pcost_label = None
            pcost_str = None

        # Supplier / MPN (COTS or sourced part) read through part.source proxy.
        psrc_proxy = part.source
        supplier: str | None = None
        mpn: str | None = None
        source_dict: dict[str, Any] | None = None
        if psrc_proxy is not None:
            supplier = str(psrc_proxy.vendor)
            mpn = str(psrc_proxy.mpn)
            source_dict = {
                "vendor": supplier,
                "mpn": mpn,
                "url": psrc_proxy.url,
                "verified": bool(psrc_proxy.verified),
            }

        # Artifacts: check each path on disk with is_file(); omit when absent; no STL.
        artifacts: dict[str, str] = {}
        step_path = build_dir / "parts" / pid / "model.step"
        if step_path.is_file():
            artifacts["step"] = f"build/parts/{pid}/model.step"
        flat_path = build_dir / "drawings" / f"{pid}-flat.dxf"
        if flat_path.is_file():
            artifacts["flat"] = f"build/drawings/{pid}-flat.dxf"
        draw_path = build_dir / "drawings" / f"{pid}.svg"
        if draw_path.is_file():
            artifacts["drawing"] = f"build/drawings/{pid}.svg"

        # Interfaces touching this part (model declaration + interface party cross-ref).
        p_ifaces = [str(u) for u in part.interfaces]
        for iuri in ifaces_by_party.get(puri, []):
            if iuri not in p_ifaces:
                p_ifaces.append(iuri)

        # Requirements that name this part (satisfies + allocation).
        p_req_ids = [r.id for r in part.satisfies]
        for rid, raw_req in product.requirements.items():
            alloc = raw_req.allocation or []
            alloc_strs = [str(a) for a in alloc] if isinstance(alloc, list) else [str(alloc)]
            if puri in alloc_strs and rid not in p_req_ids:
                p_req_ids.append(rid)

        p_reqs: list[dict[str, Any]] = []
        for rid in p_req_ids:
            if rid not in product.requirements:
                continue
            r_uri = f"req://{rid}"
            res = results_by_id.get(r_uri)
            st = str(res["status"]) if res else "skip"
            msg = (
                display(str(res.get("persona_message") or res.get("message", "")), units)
                if res
                else ""
            )
            p_reqs.append(
                {
                    "uri": r_uri,
                    "id": rid,
                    "title": display(str(product.requirements[rid].title), units),
                    "status": st,
                    "status_words": words.get(st, st),
                    "message": msg,
                }
            )

        # Rule checks that read this part (from checks.json + manifest.json).
        p_checks = _part_checks_trace(pid, puri, checks, manifest_data, words, units)

        part_entry: dict[str, Any] = {
            "kind": "part",
            "part_kind": pkind,
            "id": pid,
            "uri": puri,
            "name": pname,
            "title": pname,
            "material": pmat,
            "process": pproc,
            "finish": pfinish,
            "tolerance_class": ptol,
            "mass": pmass_str,
            "mass_kg": pmass_kg,
            "mass_label": pmass_label,
            "cost": pcost_str,
            "unit_cost": unit_cost,
            "cost_label": pcost_label,
            "supplier": supplier,
            "mpn": mpn,
            "part_anchor": f"part-{pid}",
            "artifacts": artifacts,
            "interfaces": p_ifaces,
            "requirements": p_reqs,
            "checks": p_checks,
        }
        if source_dict is not None:
            part_entry["source"] = source_dict
        if draw_path.is_file():
            part_entry["drawing_id"] = pid
            part_entry["drawing_anchor"] = f"drawing-{pid}"
            part_entry["anchor"] = f"drawing-{pid}"
        else:
            part_entry["anchor"] = f"part-{pid}"

        index[puri] = part_entry

    # ---- 4. iface://<id> -------------------------------------------------------------------------
    for iid, raw_iface in sorted(product.interfaces.items()):
        iuri = raw_iface.uri
        iface = sctx.proxy(raw_iface, iuri)
        ikind = str(iface.kind)
        iname = iface.name
        idesc = display(str(iface.description or ""), units)
        iparties = [str(p) for p in iface.parties]
        _ = bool(iface.spec)
        spec_text = _spec_summary(raw_iface.spec, product, units)
        ititle = display(
            str(iname or raw_iface.description or f"{ikind} ({', '.join(iparties)})"), units
        )
        hw_uris = [str(h.part) for h in raw_iface.hardware_items()]
        ilinks = list(iparties) + [u for u in hw_uris if u not in iparties]

        res = results_by_id.get(iuri)
        istatus = str(res["status"]) if res else "skip"
        istatus_words = words.get(istatus, istatus)
        imsg = (
            display(str(res.get("persona_message") or res.get("message", "not checked yet")), units)
            if res
            else "not checked yet"
        )

        index[iuri] = {
            "kind": "interface",
            "interface_kind": ikind,
            "id": iid,
            "uri": iuri,
            "anchor": f"iface-{iid}",
            "title": ititle,
            "name": ititle,
            "description": idesc,
            "spec": spec_text,
            "status": istatus,
            "status_words": istatus_words,
            "message": imsg,
            "parties": iparties,
            "links": ilinks,
        }

    # ---- 5. req://<id> ---------------------------------------------------------------------------
    for rid, raw_req in sorted(product.requirements.items()):
        ruri = f"req://{rid}"
        req = sctx.proxy(raw_req, ruri)
        rtitle = display(str(req.title), units)
        rstmt = display(str(req.statement), units)
        rcat = str(req.category)
        rprio = str(req.priority)
        rsafety = bool(req.safety)
        raw_alloc = req.allocation or []
        ralloc = [str(a) for a in raw_alloc] if isinstance(raw_alloc, list) else [str(raw_alloc)]
        rsat = list(satisfied_by.get(rid, []))
        rlinks = list(ralloc) + [u for u in rsat if u not in ralloc]

        res = results_by_id.get(ruri)
        rstatus = str(res["status"]) if res else "skip"
        rstatus_words = words.get(rstatus, rstatus)
        rmsg = (
            display(str(res.get("persona_message") or res.get("message", "")), units) if res else ""
        )

        index[ruri] = {
            "kind": "requirement",
            "id": rid,
            "uri": ruri,
            "anchor": f"req-{rid}",
            "title": rtitle,
            "statement": rstmt,
            "category": rcat,
            "priority": rprio,
            "safety": rsafety,
            "allocation": ralloc,
            "satisfied_by": rsat,
            "parties": rlinks,
            "links": rlinks,
            "status": rstatus,
            "status_words": rstatus_words,
            "message": rmsg,
        }

    # ---- 6. rule://<pack>/<rule> -----------------------------------------------------------------
    rules_matrix = checks.get("matrix", {}).get("rules", {})
    rule_titles: dict[str, str] = dict(rules_matrix.get("rules", {}))
    rule_rows: dict[str, list[dict[str, Any]]] = {r_uri: [] for r_uri in rule_titles}
    for r in results_list:
        rid_full = str(r.get("id", ""))
        if not rid_full.startswith("rule://"):
            continue
        base_rule = rid_full.partition("@")[0]
        rule_rows.setdefault(base_rule, []).append(r)
        rule_titles.setdefault(base_rule, str(r.get("title", base_rule)))

    for rule_uri in sorted(rule_rows):
        try:
            Uri.parse(rule_uri)
        except ValueError:
            continue
        r_list = rule_rows[rule_uri]
        if r_list:
            worst_st = min(
                (str(x.get("status", "skip")) for x in r_list),
                key=lambda s: _STATUS_RANK.get(s, 9),
            )
            non_pass = [x for x in r_list if x.get("status") not in ("pass", "skip")]
            chosen = non_pass[0] if non_pass else r_list[0]
            r_msg = display(str(chosen.get("persona_message") or chosen.get("message", "")), units)
        else:
            worst_st = "skip"
            r_msg = ""
        r_parties: list[str] = []
        for x in r_list:
            subj = str(x.get("subject", ""))
            if subj and "://" in subj and subj not in r_parties:
                r_parties.append(subj)
        r_title = display(str(rule_titles.get(rule_uri, rule_uri)), units)
        index[rule_uri] = {
            "kind": "rule",
            "uri": rule_uri,
            "title": r_title,
            "status": worst_st,
            "status_words": words.get(worst_st, worst_st),
            "message": r_msg,
            "parties": r_parties,
            "links": r_parties,
        }

    # ---- 7. doc://<id> ---------------------------------------------------------------------------
    for did, doc in sorted(product.docs.items()):
        duri = f"doc://{did}"
        meta = sctx.proxy(doc.meta, duri)
        dtitle = display(str(meta.title), units)
        daudience = list(meta.audience)
        dsafety = bool(meta.safety)
        dlinks = [str(u) for u in meta.depends_on]

        res = results_by_id.get(duri)
        page_md = build_dir / "docs" / did / "page.md"
        dstatus = str(res["status"]) if res else ("pass" if page_md.is_file() else "skip")
        dstatus_words = words.get(dstatus, dstatus)
        dmsg = (
            display(str(res.get("persona_message") or res.get("message", "")), units) if res else ""
        )

        index[duri] = {
            "kind": "doc",
            "id": did,
            "uri": duri,
            "anchor": "safety" if dsafety else f"doc-{did}",
            "title": dtitle,
            "audience": daudience,
            "safety": dsafety,
            "status": dstatus,
            "status_words": dstatus_words,
            "message": dmsg,
            "parties": dlinks,
            "links": dlinks,
        }

    # ---- 8. Merge domain inspector entries -------------------------------------------------------
    index.update(domain_entries)
    return index
