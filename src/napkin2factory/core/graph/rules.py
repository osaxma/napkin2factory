"""Rule definitions and the ordered rule list for a product (GRAND_PLAN §6.1).

Order: ``validate`` → ``part:<id>`` → ``asm:<id>`` → ``drawing:<id>`` → ``bom`` →
``asmsheet:<id>`` (one per build unit, P8) → ``doc:<id>`` → ``checks`` → ``report`` →
``site``.  A rule knows its declared inputs (file and code hashes), the URI it produces
(so downstream reads can be resolved to its output hash), and which ``--target`` groups
include it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from napkin2factory import __version__
from napkin2factory.core.graph.hashing import sha256_file, sha256_text, sha256_tree
from napkin2factory.core.loader import Product
from napkin2factory.core.model import KitGeometry, ModuleGeometry

#: Which rule kinds each ``--target`` runs (cumulative in dependency order).
TARGET_KINDS: dict[str, tuple[str, ...]] = {
    "geometry": ("validate", "part", "asm"),
    "drawings": ("validate", "part", "asm", "drawing"),
    "bom": ("validate", "part", "asm", "bom"),
    "docs": ("validate", "part", "asm", "bom", "doc"),
    "checks": ("validate", "part", "asm", "drawing", "bom", "asmsheet", "doc", "checks"),
    "report": ("validate", "part", "asm", "drawing", "bom", "asmsheet", "doc", "checks", "report"),
    "site": (
        "validate",
        "part",
        "asm",
        "drawing",
        "bom",
        "asmsheet",
        "doc",
        "checks",
        "report",
        "site",
    ),
    "all": (
        "validate",
        "part",
        "asm",
        "drawing",
        "bom",
        "asmsheet",
        "doc",
        "checks",
        "report",
        "site",
    ),
}


@dataclass
class RunResult:
    """What a rule run reports back."""

    reads: list[str]
    outputs: list[Path]  # absolute paths written
    output_hash: str  # what downstream depends on (geometry/content, not timing)
    payload: Any = None  # in-memory object (BuiltPart, rollups…) for later rules in this run
    iface_reads: list[str] = field(default_factory=list)  # reads only through an interface (P5)


@dataclass
class Rule:
    """A node of the DAG."""

    id: str
    kind: str
    produces: str | None  # part://x, asm://x, doc://x, bom://rollups, rule:checks…
    inputs: dict[str, str]  # declared input name → hash (computed at list time)
    run: Callable[["RunContext"], RunResult]
    version: int = 1
    description: str = ""
    depends_on: list[str] = field(
        default_factory=list
    )  # static upstream rule ids (for graph output)


@dataclass
class RunContext:
    """Shared state during one build."""

    product: Product
    build_dir: Path
    render: bool = True
    built_parts: dict[str, Any] = field(default_factory=dict)
    built_asms: dict[str, Any] = field(default_factory=dict)
    payloads: dict[str, Any] = field(default_factory=dict)
    snapshot_date: str = "unsnapshotted"


SYSTEM_ROOT = Path(__file__).resolve().parents[2]  # src/napkin2factory


@lru_cache(maxsize=32)
def package_hash(*subdirs: str) -> str:
    """Hash of the system package trees a rule's code lives in (gate-1 B6)."""
    parts = {
        d: sha256_tree(SYSTEM_ROOT / d, (".py", ".js", ".html", ".css", ".yaml", ".j2"))
        for d in subdirs
    }
    parts["version"] = __version__
    return sha256_text("\n".join(f"{k}={v}" for k, v in sorted(parts.items())))


def code_hash_for_part(product: Product, part_id: str) -> str:
    """Hash of everything that can change a part's geometry output.

    That is the whole geometry package (kit, exporters, materials, tessellation settings)
    and, for module parts, the product's entire ``model/geometry`` tree (helpers imported
    by the module included).
    """
    g = product.parts[part_id].geometry
    system = package_hash("geometry")
    if isinstance(g, ModuleGeometry):
        return sha256_text(system + sha256_tree(product.paths.geometry))
    if isinstance(g, KitGeometry):
        return sha256_text(system + f":kit:{g.kit}")
    return sha256_text(system + ":none")


def code_hash_for_asm(product: Product, asm_id: str) -> str:
    """Hash of the geometry package plus the product's ``model/geometry`` tree."""
    g = product.assemblies[asm_id].geometry
    system = package_hash("geometry")
    if isinstance(g, ModuleGeometry):
        return sha256_text(system + sha256_tree(product.paths.geometry))
    return sha256_text(system + ":auto-layout")


def build_rules(product: Product, render: bool = True) -> list[Rule]:
    """The ordered rule list for ``product`` (``render`` is a declared input of part/asm rules)."""
    from napkin2factory.core.graph import runs

    paths = product.paths
    render_flag = "render" if render else "no-render"
    rules: list[Rule] = [
        Rule(
            id="validate",
            kind="validate",
            produces="rule:validate",
            inputs={
                "model": sha256_tree(paths.model),
                "manifest": sha256_file(paths.manifest),
                "operator": sha256_file(paths.operator),
                "changes": sha256_tree(paths.changes),
            },
            run=runs.run_validate,
            description="load and cross-check the model",
        )
    ]
    part_ids = sorted(p.id for p in product.parts_with_geometry())
    for pid in part_ids:
        rules.append(
            Rule(
                id=f"part:{pid}",
                kind="part",
                produces=f"part://{pid}",
                inputs={
                    "code": code_hash_for_part(product, pid),
                    "render": render_flag,
                },
                run=runs.make_part_run(pid),
                description=f"3D, props, features, renders for part://{pid}",
                depends_on=["validate"],
            )
        )
    from napkin2factory.geometry.build import assembly_order

    for aid in assembly_order(product):
        asm = product.assemblies[aid]
        deps = [
            f"part:{c.part.id}"
            for c in asm.children
            if c.part is not None and product.parts[c.part.id].has_geometry
        ]
        deps += [f"asm:{c.asm.id}" for c in asm.children if c.asm is not None]
        rules.append(
            Rule(
                id=f"asm:{aid}",
                kind="asm",
                produces=f"asm://{aid}",
                inputs={"code": code_hash_for_asm(product, aid), "render": render_flag},
                run=runs.make_asm_run(aid),
                description=f"placements, GLB, props for asm://{aid}",
                depends_on=["validate", *deps],
            )
        )
    for pid in part_ids:
        rules.append(
            Rule(
                id=f"drawing:{pid}",
                kind="drawing",
                produces=f"drawing://{pid}",
                inputs={"code": package_hash("drawings")},
                run=runs.make_drawing_run(pid),
                description=f"SVG views (+ DXF flat pattern) for part://{pid}",
                depends_on=[f"part:{pid}"],
            )
        )
    rules.append(
        Rule(
            id="bom",
            kind="bom",
            produces="bom://rollups",
            inputs={"code": package_hash("bom", "catalog")},
            run=runs.run_bom,
            description="rollups, validation, CSV, XLSX",
            depends_on=["validate", *[f"part:{p}" for p in part_ids]],
        )
    )
    from napkin2factory.core.build_units import BuildUnits

    for aid in BuildUnits(product).order():  # P8: one assembly sheet per build unit
        rules.append(
            Rule(
                id=f"asmsheet:{aid}",
                kind="asmsheet",
                produces=f"rule:asmsheet:{aid}",
                inputs={"code": package_hash("drawings", "bom")},
                run=runs.make_asmsheet_run(aid),
                description=f"assembly sheet for the build step of asm://{aid}",
                depends_on=[f"asm:{aid}", "bom"],
            )
        )
    for did in sorted(product.docs):
        rules.append(
            Rule(
                id=f"doc:{did}",
                kind="doc",
                produces=f"doc://{did}",
                inputs={
                    "source": sha256_file(product.docs[did].path),
                    "code": package_hash("docs"),
                },
                run=runs.make_doc_run(did),
                description=f"manual page doc://{did} (Markdown, HTML, PDF, reads.json)",
                depends_on=["validate", "bom"],
            )
        )
    rules.append(
        Rule(
            id="checks",
            kind="checks",
            produces="rule:checks",
            inputs={
                "code": package_hash("core/checks", "rulepacks", "bom", "catalog"),
                "calcs": sha256_tree(paths.calcs),
                "signoffs": sha256_tree(paths.signoffs),
            },
            run=runs.run_checks,
            description="requirement verification, rule packs, check matrix, stage",
            depends_on=[
                "bom",
                *[f"doc:{d}" for d in sorted(product.docs)],
                *[r.id for r in rules if r.kind in ("part", "asm", "drawing")],
            ],
        )
    )
    rules.append(
        Rule(
            id="report",
            kind="report",
            produces="rule:report",
            inputs={"code": package_hash("report", "docs")},
            run=runs.run_report,
            description="self-contained HTML report",
            depends_on=["checks"],
        )
    )
    rules.append(
        Rule(
            id="site",
            kind="site",
            produces="rule:site",
            inputs={"code": package_hash("report")},
            run=runs.run_site,
            description="site layout (latest, frozen versions, diffs)",
            depends_on=["report"],
        )
    )
    return rules


def rules_for_target(
    rules: list[Rule], target: str, only_part: str | None = None, only_asm: str | None = None
) -> list[Rule]:
    """Filter the ordered list to a ``--target`` (and optionally one part or one assembly).

    ``only_asm`` (``n2f build --asm``, P6) keeps what that assembly needs, through the DAG:
    ``validate``, its rule and every part and assembly rule it depends on, transitively, plus
    those parts' drawings when the target makes drawings.  The BOM, assembly sheets, manuals,
    checks, report and site are the whole product's and are left out.
    """
    kinds = TARGET_KINDS[target]
    selected = [r for r in rules if r.kind in kinds]
    if only_part:
        selected = [
            r
            for r in selected
            if r.kind == "validate" or r.id in (f"part:{only_part}", f"drawing:{only_part}")
        ]
    if only_asm:
        by_id = {r.id: r for r in rules}
        need: set[str] = set()
        todo = [f"asm:{only_asm}"] if f"asm:{only_asm}" in by_id else []
        while todo:
            rid = todo.pop()
            if rid in need:
                continue
            need.add(rid)
            todo += [d for d in by_id[rid].depends_on if d in by_id]
        selected = [
            r
            for r in selected
            if r.id in need or (r.kind == "drawing" and set(r.depends_on) <= need)
        ]
    return selected
