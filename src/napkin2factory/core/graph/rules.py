"""Rule definitions and the ordered rule list for a product (GRAND_PLAN §6.1).

Order: ``validate`` → ``part:<id>`` → ``asm:<id>`` → ``drawing:<id>`` → ``bom`` →
``doc:<id>`` → ``checks`` → ``report`` → ``site``.  A rule knows its declared inputs
(file and code hashes), the URI it produces (so downstream reads can be resolved to its
output hash), and which ``--target`` groups include it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
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
    "checks": ("validate", "part", "asm", "drawing", "bom", "doc", "checks"),
    "report": ("validate", "part", "asm", "drawing", "bom", "doc", "checks", "report"),
    "site": ("validate", "part", "asm", "drawing", "bom", "doc", "checks", "report", "site"),
    "all": ("validate", "part", "asm", "drawing", "bom", "doc", "checks", "report", "site"),
}


@dataclass
class RunResult:
    """What a rule run reports back."""

    reads: list[str]
    outputs: list[Path]  # absolute paths written
    output_hash: str  # what downstream depends on (geometry/content, not timing)
    payload: Any = None  # in-memory object (BuiltPart, rollups…) for later rules in this run


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


def code_hash_for_part(product: Product, part_id: str) -> str:
    """Hash of the generator source that builds a part plus the geometry package version."""
    from napkin2factory.geometry import kit as kit_mod

    part = product.parts[part_id]
    g = part.geometry
    if isinstance(g, KitGeometry):
        mod = kit_mod.get_module(g.kit)
        src = Path(mod.__file__).read_bytes() if mod.__file__ else b""
        shared = b"".join(
            (Path(kit_mod.__file__).parent / n).read_bytes()
            for n in ("_common.py", "_sheet.py", "hole_pattern.py")
            if (Path(kit_mod.__file__).parent / n).is_file()
        )
        return sha256_text(
            f"{__version__}:"
            + sha256_text(src.decode("utf-8", "replace") + shared.decode("utf-8", "replace"))
        )
    if isinstance(g, ModuleGeometry):
        return sha256_text(f"{__version__}:" + sha256_file(product.paths.model / g.module))
    return sha256_text(f"{__version__}:none")


def code_hash_for_asm(product: Product, asm_id: str) -> str:
    """Hash of an assembly module's source (or the auto-layout marker)."""
    g = product.assemblies[asm_id].geometry
    if isinstance(g, ModuleGeometry):
        return sha256_text(f"{__version__}:" + sha256_file(product.paths.model / g.module))
    return sha256_text(f"{__version__}:auto-layout")


def build_rules(product: Product) -> list[Rule]:
    """The ordered rule list for ``product``."""
    from napkin2factory.core.graph import runs

    paths = product.paths
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
                    "yaml": sha256_file(paths.parts / f"{pid}.yaml"),
                    "code": code_hash_for_part(product, pid),
                    "interfaces": sha256_text(
                        ",".join(
                            sorted(
                                sha256_file(paths.interfaces / f"{i.id}.yaml")
                                for i in product.parts[pid].interfaces
                            )
                        )
                    ),
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
                inputs={
                    "yaml": sha256_file(paths.assemblies / f"{aid}.yaml"),
                    "code": code_hash_for_asm(product, aid),
                },
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
                inputs={"drawings_version": runs.DRAWINGS_VERSION},
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
            inputs={"bom_version": runs.BOM_VERSION, "catalog": runs.catalog_hash()},
            run=runs.run_bom,
            description="rollups, validation, CSV, XLSX",
            depends_on=["validate", *[f"part:{p}" for p in part_ids]],
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
                    "docs_version": runs.DOCS_VERSION,
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
                "checks_version": runs.CHECKS_VERSION,
                "rulepacks": runs.rulepacks_hash(),
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
            inputs={"report_version": runs.REPORT_VERSION, "viewer": runs.viewer_hash()},
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
            inputs={"site_version": runs.SITE_VERSION},
            run=runs.run_site,
            description="site layout (latest, frozen versions, diffs)",
            depends_on=["report"],
        )
    )
    return rules


def rules_for_target(rules: list[Rule], target: str, only_part: str | None = None) -> list[Rule]:
    """Filter the ordered list to a ``--target`` (and optionally one part)."""
    kinds = TARGET_KINDS[target]
    selected = [r for r in rules if r.kind in kinds]
    if only_part:
        selected = [
            r
            for r in selected
            if r.kind == "validate" or r.id in (f"part:{only_part}", f"drawing:{only_part}")
        ]
    return selected
