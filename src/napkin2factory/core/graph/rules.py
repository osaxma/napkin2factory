"""Rule definitions and the ordered rule list for a product (GRAND_PLAN §6.1, FOUNDATION F3).

The list is the rule-family registry walked in dependency order (``core/registry.py``).
With the mechanical domain alone that is, as before: ``validate`` → ``part:<id>`` →
``asm:<id>`` → ``drawing:<id>`` → ``bom`` → ``asmsheet:<id>`` (one per build unit, P8) →
``doc:<id>`` → ``checks`` → ``report`` → ``site``; a domain's family goes after the families
it names in ``after`` and before ``checks``.  A rule knows its declared inputs (file and
code hashes), the URI it produces (so downstream reads can be resolved to its output hash),
and which ``--target`` groups include it.  The mechanical families' ``make_rules`` live
here, registered in place by ``domains/mechanical`` (F2).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.core.graph.hashing import sha256_file, sha256_text, sha256_tree
from napkin2factory.core.loader import Product
from napkin2factory.core.model import KitGeometry, ModuleGeometry


def __getattr__(name: str) -> Any:
    """``TARGET_KINDS`` is derived from the registered rule families on each read (F3)."""
    if name == "TARGET_KINDS":
        return target_kinds()
    raise AttributeError(name)


def target_kinds() -> dict[str, tuple[str, ...]]:
    """Which rule kinds each ``--target`` runs (cumulative in dependency order).

    From the rule-family registry: ``geometry``, ``drawings``, ``bom``, ``docs``, ``checks``,
    ``report``, ``site`` and ``all`` as before, plus one per registered family.
    """
    from napkin2factory.core.registry import registry

    return registry().target_kinds()


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
    #: Further outputs others read by key, e.g. the bom rule's ``bom://build-plan`` (S-117).
    also_produces: tuple[str, ...] = ()

    @property
    def produced(self) -> tuple[str, ...]:
        """Every key this rule produces: ``produces`` then ``also_produces``."""
        return ((self.produces,) if self.produces else ()) + self.also_produces


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


def package_hash(*subdirs: str) -> str:
    """Hash of the system package trees a rule's code lives in (gate-1 B6, S-031)."""
    from napkin2factory.core.registry import package_hash as _package_hash

    return _package_hash(*subdirs)


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


@dataclass
class RuleBuild:
    """What a rule family's ``make_rules`` sees.

    The product, the render flag, the rules the families before it made (in build order),
    and the family itself.
    """

    product: Product
    render: bool
    rules: list[Rule]
    family: Any = None

    @property
    def render_flag(self) -> str:
        """The ``render`` input of part and assembly rules."""
        return "render" if self.render else "no-render"

    def code_hash(self) -> str:
        """The family's code hash (from the package that registered it, F3)."""
        from napkin2factory.core.registry import registry

        return registry().family_hash(self.family)


def build_rules(product: Product, render: bool = True) -> list[Rule]:
    """The ordered rule list for ``product``: every registered rule family's rules (F3).

    The families are walked in dependency order.

    A rule's ``kind`` is its family's name.  A rule whose ``inputs`` carry no ``code`` gets
    its family's code hash, and every domain registry the rule reads (verify kinds, check
    stages, report sections, doc helpers, model families …) adds its contributing domains'
    hashes (:meth:`~napkin2factory.core.registry.Registry.domain_inputs`), so a domain's code
    change reruns exactly the rules that use it (gate E).  ``render`` is a declared input of
    part and assembly rules.
    """
    from napkin2factory.core.registry import registry

    reg = registry()
    rules: list[Rule] = []
    for family in reg.rule_families():
        made = family.make_rules(RuleBuild(product, render, list(rules), family))
        in_place = reg.owner("rule family", family.name).in_place
        for rule in made:
            if "code" not in rule.inputs and not in_place:  # validate has none (F2: unchanged)
                rule.inputs["code"] = reg.family_hash(family)
            rule.inputs.update(reg.domain_inputs(*_REGISTRIES_READ.get(rule.kind, ())))
        rules += made
    return rules


#: The domain registries each mechanical rule kind reads (their contributors' code hashes
#: are inputs of its rules, gate E); a domain's own families read their own code.
_REGISTRIES_READ: dict[str, tuple[str, ...]] = {
    "validate": ("families", "interface_kinds", "processes", "finishes", "categories", "drivers"),
    "doc": ("doc_helpers",),
    "checks": ("verify_kinds", "check_stages"),
    "report": ("report_sections", "gate_rows", "vocabulary"),
}


# ---- the mechanical rule families (registered in place, F2: domains/mechanical) ----------


def validate_rules(b: RuleBuild) -> list[Rule]:
    """``validate``: load and cross-check the model."""
    from napkin2factory.core.graph import runs

    paths = b.product.paths
    return [
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


def part_rules(b: RuleBuild) -> list[Rule]:
    """``part:<id>``: 3D, props, features and renders, one rule per part with geometry."""
    from napkin2factory.core.graph import runs

    product = b.product
    return [
        Rule(
            id=f"part:{pid}",
            kind="part",
            produces=f"part://{pid}",
            inputs={
                "code": code_hash_for_part(product, pid),
                "render": b.render_flag,
            },
            run=runs.make_part_run(pid),
            description=f"3D, props, features, renders for part://{pid}",
            depends_on=["validate"],
        )
        for pid in sorted(p.id for p in product.parts_with_geometry())
    ]


def asm_rules(b: RuleBuild) -> list[Rule]:
    """``asm:<id>``: placements, GLB and props, children first."""
    from napkin2factory.core.graph import runs
    from napkin2factory.geometry.build import assembly_order

    product = b.product
    rules = []
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
                inputs={"code": code_hash_for_asm(product, aid), "render": b.render_flag},
                run=runs.make_asm_run(aid),
                description=f"placements, GLB, props for asm://{aid}",
                depends_on=["validate", *deps],
            )
        )
    return rules


def drawing_rules(b: RuleBuild) -> list[Rule]:
    """``drawing:<id>``: SVG views (and the DXF flat pattern) per part with geometry."""
    from napkin2factory.core.graph import runs

    return [
        Rule(
            id=f"drawing:{pid}",
            kind="drawing",
            produces=f"drawing://{pid}",
            inputs={"code": b.code_hash()},
            run=runs.make_drawing_run(pid),
            description=f"SVG views (+ DXF flat pattern) for part://{pid}",
            depends_on=[f"part:{pid}"],
        )
        for pid in sorted(p.id for p in b.product.parts_with_geometry())
    ]


def bom_rules(b: RuleBuild) -> list[Rule]:
    """``bom``: rollups, validation, CSV, XLSX and the build plan."""
    from napkin2factory.core.graph import runs

    part_ids = sorted(p.id for p in b.product.parts_with_geometry())
    return [
        Rule(
            id="bom",
            kind="bom",
            produces="bom://rollups",
            also_produces=("bom://build-plan",),  # P8: the plan, read per step (S-117)
            inputs={"code": b.code_hash()},
            run=runs.run_bom,
            description="rollups, validation, CSV, XLSX",
            depends_on=["validate", *[f"part:{p}" for p in part_ids]],
        )
    ]


def asmsheet_rules(b: RuleBuild) -> list[Rule]:
    """``asmsheet:<id>``: one assembly sheet per build unit (P8)."""
    from napkin2factory.core.build_units import BuildUnits
    from napkin2factory.core.graph import runs

    return [
        Rule(
            id=f"asmsheet:{aid}",
            kind="asmsheet",
            produces=f"rule:asmsheet:{aid}",
            inputs={"code": b.code_hash()},
            run=runs.make_asmsheet_run(aid),
            description=f"assembly sheet for the build step of asm://{aid}",
            depends_on=[f"asm:{aid}", "bom"],
        )
        for aid in BuildUnits(b.product).order()
    ]


def doc_rules(b: RuleBuild) -> list[Rule]:
    """``doc:<id>``: one manual page each (Markdown, HTML, PDF, reads.json)."""
    from napkin2factory.core.graph import runs

    product = b.product
    return [
        Rule(
            id=f"doc:{did}",
            kind="doc",
            produces=f"doc://{did}",
            inputs={
                "source": sha256_file(product.docs[did].path),
                "code": b.code_hash(),
            },
            run=runs.make_doc_run(did),
            description=f"manual page doc://{did} (Markdown, HTML, PDF, reads.json)",
            depends_on=["validate", "bom"],
        )
        for did in sorted(product.docs)
    ]


def checks_rules(b: RuleBuild) -> list[Rule]:
    """``checks``: requirement verification, rule packs, check matrix, stage."""
    from napkin2factory.core.graph import runs

    product = b.product
    produced_before = [r.id for r in b.rules if r.kind not in ("validate", "bom", "doc")]
    produced_before = [
        rid
        for rid in produced_before
        if not rid.startswith("asmsheet:")  # the sheets are read by the report, not checks
    ]
    return [
        Rule(
            id="checks",
            kind="checks",
            produces="rule:checks",
            inputs={
                "code": b.code_hash(),
                "calcs": sha256_tree(product.paths.calcs),
                "signoffs": sha256_tree(product.paths.signoffs),
            },
            run=runs.run_checks,
            description="requirement verification, rule packs, check matrix, stage",
            depends_on=[
                "bom",
                *[f"doc:{d}" for d in sorted(product.docs)],
                *produced_before,
            ],
        )
    ]


def report_rules(b: RuleBuild) -> list[Rule]:
    """``report``: the self-contained HTML report."""
    from napkin2factory.core.graph import runs

    return [
        Rule(
            id="report",
            kind="report",
            produces="rule:report",
            inputs={"code": b.code_hash()},
            run=runs.run_report,
            description="self-contained HTML report",
            depends_on=["checks"],
        )
    ]


def site_rules(b: RuleBuild) -> list[Rule]:
    """``site``: the site layout (latest, frozen versions, diffs)."""
    from napkin2factory.core.graph import runs

    return [
        Rule(
            id="site",
            kind="site",
            produces="rule:site",
            inputs={"code": b.code_hash()},
            run=runs.run_site,
            description="site layout (latest, frozen versions, diffs)",
            depends_on=["report"],
        )
    ]


def rules_for_target(
    rules: list[Rule], target: str, only_part: str | None = None, only_asm: str | None = None
) -> list[Rule]:
    """Filter the ordered list to a ``--target`` (and optionally one part or one assembly).

    ``only_asm`` (``n2f build --asm``, P6) keeps what that assembly needs, through the DAG:
    ``validate``, its rule and every part and assembly rule it depends on, transitively, plus
    those parts' drawings when the target makes drawings.  The BOM, assembly sheets, manuals,
    checks, report and site are the whole product's and are left out.
    """
    targets = target_kinds()
    if target not in targets:
        from napkin2factory.core.registry import unknown

        raise unknown("build target", target, list(targets))
    kinds = targets[target]
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
