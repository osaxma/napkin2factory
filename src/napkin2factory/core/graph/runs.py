"""The run functions behind each rule kind.

M3 ships real runs for validate, part, asm, bom and doc (Markdown + reads.json) and
placeholders for drawing, checks, report and site that record their true read sets so
invalidation is exact from the start; M4/M5 replace the bodies, bumping the version
constants so every product rebuilds those artifacts once.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from napkin2factory.core.errors import Problem
from napkin2factory.core.graph.hashing import sha256_file, sha256_json, sha256_text, sha256_tree

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext, RunResult

DRAWINGS_VERSION = "1"
BOM_VERSION = "1"
DOCS_VERSION = "1"
CHECKS_VERSION = "1"
REPORT_VERSION = "1"
SITE_VERSION = "1"


def _result(
    reads: list[str], outputs: list[Path], output_hash: str, payload: Any = None
) -> RunResult:
    from napkin2factory.core.graph.rules import RunResult

    return RunResult(reads=reads, outputs=outputs, output_hash=output_hash, payload=payload)


def _write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return path


def catalog_hash() -> str:
    """Hash of the curated catalog (M4)."""
    p = Path(__file__).resolve().parents[2] / "catalog"
    return sha256_tree(p, (".yaml",)) if p.is_dir() else "none"


def rulepacks_hash() -> str:
    """Hash of the shipped rule packs (M4)."""
    p = Path(__file__).resolve().parents[2] / "rulepacks"
    return sha256_tree(p, (".yaml",)) if p.is_dir() else "none"


def viewer_hash() -> str:
    """Hash of the report templates and viewer (M5)."""
    p = Path(__file__).resolve().parents[2] / "report"
    return sha256_tree(p, (".js", ".html", ".css", ".py"))


# ---- validate ----------------------------------------------------------------


def problem_record(problem: Problem, root: Path) -> dict[str, str]:
    """A problem for ``validate.json``, its file relative to the product root (B-0006).

    The build folder then reads the same wherever the product sits, and names no local path.
    """
    record = problem.to_dict()
    try:
        record["file"] = Path(record["file"]).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        pass  # outside the product (a system file): keep it as given
    return record


def run_validate(ctx: RunContext) -> RunResult:
    """Re-validate from disk (the product is already loaded, but record the outcome)."""
    from napkin2factory.core import lint as lint_mod
    from napkin2factory.core.loader import validate

    product, problems = validate(ctx.product.root)
    lint_problems = (
        lint_mod.lint(product).items if product is not None and not problems.errors else []
    )
    payload = {
        "ok": not problems.errors,
        "problems": [problem_record(p, ctx.product.root) for p in problems.items],
        "lint": [problem_record(p, ctx.product.root) for p in lint_problems],
    }
    out = _write_json(ctx.build_dir / "validate.json", payload)
    return _result([], [out], sha256_json(payload), payload)


# ---- parts and assemblies --------------------------------------------------------


def part_output_hash(part_dir: Path) -> str:
    """Hash of the geometry-relevant outputs (props minus reads/timing, features, flat)."""
    props_path = part_dir / "props.json"
    if not props_path.is_file():
        return "unbuilt"
    props = json.loads(props_path.read_text(encoding="utf-8"))
    props.pop("reads", None)
    return sha256_json(
        {
            "props": props,
            "features": sha256_file(part_dir / "features.json"),
            "flat": sha256_file(part_dir / "flat_pattern.json"),
        }
    )


def make_part_run(part_id: str) -> Any:
    """Run function for ``part:<id>``."""

    def run(ctx: RunContext) -> RunResult:
        from napkin2factory.geometry.build import build_part

        built = build_part(ctx.product, part_id, ctx.build_dir, render=ctx.render)
        ctx.built_parts[part_id] = built
        outputs = sorted(p for p in built.out_dir.rglob("*") if p.is_file())
        res = _result(built.reads, outputs, part_output_hash(built.out_dir), built)
        res.iface_reads = list(built.iface_reads)
        return res

    return run


def make_asm_run(asm_id: str) -> Any:
    """Run function for ``asm:<id>``; loads children from disk if not built this run."""

    def run(ctx: RunContext) -> RunResult:
        from napkin2factory.geometry.build import (
            build_assembly,
            load_built_assembly,
            load_built_part,
        )

        asm = ctx.product.assemblies[asm_id]
        for c in asm.children:
            if (
                c.part is not None
                and c.part.id not in ctx.built_parts
                and ctx.product.parts[c.part.id].has_geometry
            ):
                ctx.built_parts[c.part.id] = load_built_part(ctx.product, c.part.id, ctx.build_dir)
            if c.asm is not None and c.asm.id not in ctx.built_asms:
                # The sub-assembly's own run was skipped as up to date (S-049): reload it.
                ctx.built_asms[c.asm.id] = load_built_assembly(
                    ctx.product, c.asm.id, ctx.build_dir, ctx.built_parts
                )
        built = build_assembly(
            ctx.product, asm_id, ctx.built_parts, ctx.built_asms, ctx.build_dir, render=ctx.render
        )
        ctx.built_asms[asm_id] = built
        outputs = sorted(p for p in built.out_dir.rglob("*") if p.is_file())
        props = dict(built.props)
        props.pop("reads", None)
        placements = sha256_file(built.out_dir / "instances.json")
        res = _result(
            built.reads, outputs, sha256_json({"props": props, "placements": placements}), built
        )
        res.iface_reads = list(built.iface_reads)
        return res

    return run


# ---- drawings (placeholder until M5) ---------------------------------------------


def make_drawing_run(part_id: str) -> Any:
    """Run function for ``drawing:<id>``."""

    def run(ctx: RunContext) -> RunResult:
        from napkin2factory.drawings.engine import make_drawing

        return make_drawing(ctx, part_id)

    return run


# ---- bom ---------------------------------------------------------------------------


def run_bom(ctx: RunContext) -> RunResult:
    """Rollups (M3) + validation and CSV/XLSX files (M4/M5)."""
    from napkin2factory.bom.build_plan import PLAN_FILE, derive_build_plan
    from napkin2factory.bom.files import write_bom_files
    from napkin2factory.bom.rollups import compute_rollups
    from napkin2factory.geometry.accessors import ReadLog

    log = ReadLog()
    rollups = compute_rollups(ctx.product, ctx.build_dir, log)
    plan = derive_build_plan(ctx.product, log)  # P8: the build plan, from the tree
    out_dir = ctx.build_dir / "bom"
    outputs = [_write_json(out_dir / "rollups.json", rollups)]
    outputs.append(_write_json(out_dir / PLAN_FILE, plan))
    outputs += write_bom_files(ctx, rollups, plan)
    ctx.payloads["rollups"] = rollups
    ctx.payloads["build_plan"] = plan
    content = dict(rollups)
    content.pop("reads", None)
    # The output hash stays the rollups' (P14: a `bom://` sign-off key made under v0.3 holds);
    # pages and sheets read the plan through `bom://build-plan#units.<id>` instead.
    return _result(log.keys, outputs, sha256_json(content), rollups)


# ---- assembly sheets (P8) --------------------------------------------------------------


def make_asmsheet_run(asm_id: str) -> Any:
    """Run function for ``asmsheet:<id>``: the build unit's assembly sheet."""

    def run(ctx: RunContext) -> RunResult:
        from napkin2factory.drawings.assembly_sheet import make_assembly_sheet

        return make_assembly_sheet(ctx, asm_id)

    return run


# ---- docs ---------------------------------------------------------------------------


def make_doc_run(doc_id: str) -> Any:
    """Run function for ``doc:<id>``: Markdown with recorded reads (+ HTML/PDF at M5)."""

    def run(ctx: RunContext) -> RunResult:
        from napkin2factory.docs.engine import render_doc
        from napkin2factory.docs.outputs import write_doc_outputs

        rollups = ctx.payloads.get("rollups")
        if rollups is None:
            p = ctx.build_dir / "bom" / "rollups.json"
            rollups = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
        plan = ctx.payloads.get("build_plan")
        if plan is None:
            pp = ctx.build_dir / "bom" / "build-plan.json"
            plan = json.loads(pp.read_text(encoding="utf-8")) if pp.is_file() else None
        doc = ctx.product.docs[doc_id]
        rendered = render_doc(ctx.product, doc, rollups, plan)
        out_dir = ctx.build_dir / "docs" / doc_id
        out_dir.mkdir(parents=True, exist_ok=True)
        md = out_dir / "page.md"
        md.write_text(rendered.markdown, encoding="utf-8")
        reads_payload = {
            "doc": doc.uri,
            "reads": rendered.reads,
            "values": {k: ctx_value(ctx, k) for k in rendered.reads},
        }
        outputs = [md, _write_json(out_dir / "reads.json", reads_payload)]
        outputs += write_doc_outputs(ctx, doc, rendered)
        return _result(rendered.reads, outputs, sha256_text(rendered.markdown))

    return run


def ctx_value(ctx: RunContext, key: str) -> str:
    """Current value of a key (for reads.json, so staleness can be judged later)."""
    from napkin2factory.core.graph.manifest import Manifest
    from napkin2factory.core.graph.values import value_of

    return value_of(ctx.product, Manifest.load(ctx.build_dir), ctx.build_dir, key)


# ---- checks / report / site --------------------------------------------------------


def run_checks(ctx: RunContext) -> RunResult:
    """Requirement verification, rule packs, matrix, stage (real at M4)."""
    from napkin2factory.core.checks.engine import run_all_checks

    return run_all_checks(ctx)


def run_report(ctx: RunContext) -> RunResult:
    """The self-contained HTML report (real at M5)."""
    from napkin2factory.report.builder import build_report

    return build_report(ctx)


def run_site(ctx: RunContext) -> RunResult:
    """Site layout: ``build/site/index.html`` → latest report (M6 adds versions/diffs)."""
    from napkin2factory.report.site import build_site

    return build_site(ctx)
