"""The mechanical domain (FOUNDATION F2): what v0.4 already does, registered in place.

Parts, assemblies, drawings, the BOM and build plan, manuals, checks, the report and the
site stay where they are (``geometry/``, ``drawings/``, ``bom/``, ``docs/``, ``report/``,
``rulepacks/``, ``core/checks/``); this module only declares them through the domain
contract (``core/domain.py``), so the registries list them and the core no longer does.
Every function is named by its import path (:func:`~napkin2factory.core.domain.lazy`) and
imported on first use.  The families' ``code`` folders are the subtrees each rule hashed
before the registry, so no rule key moved (FOUNDATION §7 risk 1).
"""

from __future__ import annotations

from pathlib import Path

from napkin2factory.core.domain import (
    CheckStage,
    Domain,
    ModelFamily,
    ReportSection,
    RuleFamily,
    VerifyKind,
    lazy,
)

_RULES = "napkin2factory.core.graph.rules"
_IMPACT = "napkin2factory.core.graph.impact"
_EVAL = "napkin2factory.core.checks.evaluators"
_ENGINE = "napkin2factory.core.checks.engine"
_DOCS = "napkin2factory.docs.engine"

RULE_FAMILIES = (
    RuleFamily("validate", lazy(f"{_RULES}:validate_rules"), produces="rule:validate"),
    RuleFamily(
        "part",
        lazy(f"{_RULES}:part_rules"),
        after=("validate",),
        produces="part://",
        code=("geometry",),
        output_dir="parts",
        static_reads=lazy(f"{_IMPACT}:part_static_reads"),
    ),
    RuleFamily(
        "asm",
        lazy(f"{_RULES}:asm_rules"),
        after=("part",),
        produces="asm://",
        code=("geometry",),
        targets=("geometry",),
        output_dir="assemblies",
        static_reads=lazy(f"{_IMPACT}:asm_static_reads"),
    ),
    RuleFamily(
        "drawing",
        lazy(f"{_RULES}:drawing_rules"),
        after=("part", "asm"),  # the drawings target has always built the assemblies too
        produces="drawing://",
        code=("drawings",),
        targets=("drawings",),
        static_reads=lazy(f"{_IMPACT}:drawing_static_reads"),
    ),
    RuleFamily(
        "bom",
        lazy(f"{_RULES}:bom_rules"),
        after=("part", "asm"),
        produces="bom://rollups",
        also_produces=("bom://build-plan",),
        code=("bom", "catalog"),
        static_reads=lazy(f"{_IMPACT}:bom_static_reads"),
    ),
    RuleFamily(
        "asmsheet",
        lazy(f"{_RULES}:asmsheet_rules"),
        after=("asm", "bom"),
        produces="rule:asmsheet",
        code=("drawings", "bom"),
        static_reads=lazy(f"{_IMPACT}:asmsheet_static_reads"),
    ),
    RuleFamily(
        "doc",
        lazy(f"{_RULES}:doc_rules"),
        after=("bom",),
        produces="doc://",
        code=("docs",),
        targets=("docs",),
        output_dir="docs",
        static_reads=lazy(f"{_IMPACT}:doc_static_reads"),
    ),
    RuleFamily(
        "checks",
        lazy(f"{_RULES}:checks_rules"),
        produces="rule:checks",
        code=("core/checks", "rulepacks", "bom", "catalog"),
        reads_all=True,
    ),
    RuleFamily(
        "report",
        lazy(f"{_RULES}:report_rules"),
        after=("checks",),
        produces="rule:report",
        code=("report", "docs"),
        reads_all=True,
    ),
    RuleFamily(
        "site",
        lazy(f"{_RULES}:site_rules"),
        after=("report",),
        produces="rule:site",
        code=("report",),
        reads_all=True,
    ),
)

VERIFY_KINDS = (
    VerifyKind(
        "param_bound",
        lazy(f"{_EVAL}:eval_param_bound"),
        target_schemes=("param",),
        compares=True,
        hypothetical=lazy(f"{_IMPACT}:hyp_param_bound"),
    ),
    VerifyKind(
        "geometry_prop",
        lazy(f"{_EVAL}:eval_geometry_prop"),
        target_schemes=("part", "asm"),
        compares=True,
        check=lazy(f"{_EVAL}:check_geometry_prop"),
        hypothetical=lazy(f"{_IMPACT}:hyp_after_rebuild"),
    ),
    VerifyKind(
        "bom_rollup",
        lazy(f"{_EVAL}:eval_bom_rollup"),
        target_schemes=("bom",),
        compares=True,
        check=lazy(f"{_EVAL}:check_bom_rollup"),
        hypothetical=lazy(f"{_IMPACT}:hyp_bom_rollup"),
    ),
    VerifyKind(
        "calc",
        lazy(f"{_EVAL}:eval_calc"),
        target_schemes=("calc",),
        compares=True,
        hypothetical=lazy(f"{_IMPACT}:hyp_calc"),
    ),
    VerifyKind(
        "interference",
        lazy(f"{_EVAL}:eval_interference"),
        target_schemes=("asm",),
        binary=True,
        hypothetical=lazy(f"{_IMPACT}:hyp_after_rebuild"),
    ),
    VerifyKind(
        "count",
        lazy(f"{_EVAL}:eval_count"),
        target_schemes=("asm", "part"),
        compares=True,
        hypothetical=lazy(f"{_IMPACT}:hyp_after_rebuild"),
    ),
    VerifyKind(
        "interface",
        lazy(f"{_EVAL}:eval_interface"),
        target_schemes=("iface",),
        binary=True,
        hypothetical=lazy(f"{_IMPACT}:hyp_after_rebuild"),
    ),
    VerifyKind(
        "manual",
        lazy(f"{_EVAL}:eval_manual"),
        binary=True,
        hypothetical=lazy(f"{_IMPACT}:hyp_manual"),
    ),
    VerifyKind(
        "rule",
        lazy(f"{_EVAL}:eval_rule"),
        target_schemes=("rule",),
        binary=True,
        check=lazy(f"{_EVAL}:check_rule"),
        hypothetical=lazy(f"{_IMPACT}:hyp_after_rebuild"),
    ),
)

#: The stages of ``n2f check`` in the order their rows were always written (checks.json).
CHECK_STAGES = (
    CheckStage("interface", lazy(f"{_ENGINE}:interface_stage")),
    CheckStage("interference", lazy(f"{_ENGINE}:interference_stage"), after=("interface",)),
    # rule-pack rows first inside: `rule` requirements (form requirements) read them
    CheckStage(
        "requirements",
        lazy(f"{_ENGINE}:requirements_stage"),
        after=("interface", "interference"),
    ),
    CheckStage("count", lazy(f"{_ENGINE}:count_stage"), after=("requirements",)),
    CheckStage("hardware", lazy(f"{_ENGINE}:hardware_stage"), after=("count",)),
    CheckStage("reach", lazy(f"{_ENGINE}:reach_stage"), after=("hardware",)),
    CheckStage("docs", lazy(f"{_ENGINE}:docs_stage"), after=("reach",), whole_product=True),
    CheckStage("sourcing", lazy(f"{_ENGINE}:sourcing_stage"), after=("docs",), whole_product=True),
)


def _section(sid: str, label: str, group: str) -> ReportSection:
    """A section whose data the report builder gathers (``report/builder.py::gather``)."""
    return ReportSection(sid, label, group, f"report/sections/{sid}.html.j2")


#: The report's sections in reading order (anchor, side-index label, group).
REPORT_SECTIONS = (
    _section("overview", "Overview", ""),
    _section("safety", "Safety", ""),
    _section("model", "3D model", "Product"),
    _section("parts", "Parts & cost", "Product"),
    _section("drawings", "Drawings", "Product"),
    _section("interfaces", "Interfaces", "Product"),
    _section("build", "Build plan", "Product"),
    _section("joints", "Joints between units", "Product"),
    _section("requirements", "Requirements", "Verification"),
    _section("rules", "Rule checks", "Verification"),
    _section("signoffs", "Sign-offs", "Verification"),
    _section("parameters", "Parameters", "Design record"),
    _section("decisions", "Decisions", "Design record"),
    _section("changes", "Change requests", "Design record"),
    _section("manuals", "Manuals", ""),
)

#: The names a manual page's template can use (D8): each a factory of the helper.
DOC_HELPERS = {
    name: lazy(f"{_DOCS}:helper_{name}")
    for name in ("P", "part", "asm", "req", "iface", "dec", "build_step", "bom", "product")
}


#: Load cases (F11, the reserved slot): ``model/loads/*.yaml`` as ``load://<id>``; no solver
#: reads them in v0.5.
def _load_schema() -> type:
    from napkin2factory.core.model.loads import Load

    return Load


FAMILIES = (
    ModelFamily(
        "loads",
        schema=_load_schema(),
        folder="model/loads",
        validate_refs=lazy("napkin2factory.core.model.loads:validate_refs"),
        scheme="load",
    ),
)

DOMAIN = Domain(
    name="mechanical",
    title="Parts, assemblies, drawings, the parts list, manuals and the report",
    root=Path(__file__).resolve().parents[2],  # src/napkin2factory: registered in place (F2)
    rule_families=RULE_FAMILIES,
    verify_kinds=VERIFY_KINDS,
    check_stages=CHECK_STAGES,
    report_sections=REPORT_SECTIONS,
    doc_helpers=DOC_HELPERS,
    in_place=True,
    families=FAMILIES,
)
