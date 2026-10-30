"""Stage computation (D10, §4.3): derived from repo state, never stored.

Intake complete when requirements and operator pass lint; Design complete when every
custom part has geometry and the build succeeded; Verify complete when checks have no
``fail`` and every ``needs-human`` has a valid sign-off; Released when a Revision tag
exists for the current tree.  ``warn`` never blocks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.loader import Product

STAGES = ("intake", "design", "verify", "released")


@dataclass
class Gate:
    """One gate's state and what blocks it."""

    name: str
    ok: bool
    blockers: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class StageReport:
    """Current stage plus every gate."""

    stage: str
    gates: list[Gate]
    next_step: str

    def to_dict(self) -> dict[str, Any]:
        """JSON form."""
        return {
            "stage": self.stage,
            "gates": [g.__dict__ for g in self.gates],
            "next_step": self.next_step,
        }


def _checks_stale(product: Product, build_dir: Path, manifest: Manifest) -> bool:
    """True when the ``checks`` rule would rerun (something it read changed)."""
    try:
        from napkin2factory.core.graph.rules import build_rules
        from napkin2factory.core.graph.runner import needs_run

        rule = next(r for r in build_rules(product) if r.id == "checks")
        return needs_run(rule, product, manifest, build_dir)[0]
    except Exception:
        return False


def compute_stage(product: Product, build_dir: Path | None = None) -> StageReport:
    """Derive the stage from the model, the build manifest, checks.json and change tracking."""
    from napkin2factory.core import lint as lint_mod

    build_dir = build_dir or product.paths.build
    gates: list[Gate] = []
    # Intake
    lint_problems = lint_mod.lint(product)
    req_errors = [
        p
        for p in lint_problems.errors
        if p.subject.startswith("req://") or p.subject == "operator.yaml"
    ]
    intake_blockers = [p.format(product.root) for p in req_errors]
    if not product.requirements:
        intake_blockers.append("no requirements yet — run intake with the n2f-pm skill")
    gates.append(Gate("intake", not intake_blockers, intake_blockers))
    # Design
    design_blockers: list[str] = []
    for part in product.custom_parts():
        if not part.has_geometry:
            design_blockers.append(f"{part.uri} has no geometry yet")
    manifest = Manifest.load(build_dir)
    for part in product.parts_with_geometry():
        if f"part:{part.id}" not in manifest.entries:
            design_blockers.append(f"{part.uri} has not been built — run `n2f build`")
    for asm in product.assemblies.values():
        if f"asm:{asm.id}" not in manifest.entries:
            design_blockers.append(f"{asm.uri} has not been built — run `n2f build`")
    if not product.parts:
        design_blockers.append("no parts yet — the designer role composes the kit")
    gates.append(Gate("design", not design_blockers and not intake_blockers, design_blockers))
    # Verify
    verify_blockers: list[str] = []
    checks_path = build_dir / "checks" / "checks.json"
    if not checks_path.is_file() or "checks" not in manifest.entries:
        verify_blockers.append("checks have not run — run `n2f check`")
        counts: dict[str, int] = {}
    elif _checks_stale(product, build_dir, manifest):
        verify_blockers.append("the checks are out of date — run `n2f check` to refresh")
        counts = {}
    else:
        data = json.loads(checks_path.read_text(encoding="utf-8"))
        counts = data.get("summary", {})
        for r in data.get("results", []):
            if r["status"] == "fail":
                verify_blockers.append(f"{r['id']}: {r['persona_message'] or r['message']}")
            elif r["status"] == "needs-human":
                why = r.get("message") or "needs a human sign-off"
                verify_blockers.append(
                    f"{r['id']}: needs a human sign-off ({why}) — `n2f signoff "
                    f'{r["id"].split("://")[-1]} --by <name> --statement "…"`'
                )
        if data.get("status") == "placeholder":
            verify_blockers.append("checks are placeholders in this build")
    gates.append(
        Gate(
            "verify",
            not verify_blockers and not design_blockers and not intake_blockers,
            verify_blockers,
            {"counts": counts},
        )
    )
    # Released
    released_blockers: list[str] = []
    tag = None
    try:
        from napkin2factory.core.vcs import Vcs

        v = Vcs(product.root)
        if not v.is_tracked():
            released_blockers.append("change tracking is not set up — run `n2f init` here")
        else:
            if not v.is_clean():
                released_blockers.append("unsaved changes since the last snapshot")
            tag = v.tag_for_head()
            if tag is None:
                released_blockers.append(
                    "no Revision for the current snapshot — "
                    "`n2f release vX.Y.Z` when the checks are green"
                )
    except Exception as exc:  # never crash status on a tracking problem
        released_blockers.append(f"change tracking unavailable: {exc}")
    gates.append(
        Gate(
            "released", not released_blockers and gates[2].ok, released_blockers, {"revision": tag}
        )
    )
    stage = "intake"
    for g, name in zip(gates, STAGES, strict=True):
        if g.ok:
            stage = name
        else:
            break
    first_blocked = next((g for g in gates if not g.ok), None)
    next_step = (
        "released: send the Revision to the manufacturer"
        if first_blocked is None
        else (first_blocked.blockers[0] if first_blocked.blockers else first_blocked.name)
    )
    return StageReport(stage=stage, gates=gates, next_step=next_step)
