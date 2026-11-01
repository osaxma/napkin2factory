"""Load rule packs and evaluate them against every part's ``features.json``.

Checks are looked up in :data:`~napkin2factory.rulepacks.checks.CHECKS` and the form pack's
:data:`~napkin2factory.rulepacks.form_checks.FORM_CHECKS`.  A check that raises
``RuleNotApplicable`` writes no row for that part; ``RuleSkip`` writes a ``skip`` row.
``features`` carries two private keys for the checks: ``_has_flat_pattern`` and
``_build_dir`` (where assembly placements are read).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from napkin2factory.core.checks.results import CheckResult
from napkin2factory.core.loader import Product
from napkin2factory.rulepacks import RULEPACKS_DIR
from napkin2factory.rulepacks.checks import ASSEMBLY_CHECKS, CHECKS, RuleNotApplicable, RuleSkip
from napkin2factory.rulepacks.form_checks import FORM_CHECKS

#: Every named check a pack may use on a part.
ALL_CHECKS = {**CHECKS, **FORM_CHECKS}
#: A rule's ``subject``: ``part`` (the default, one row per part) or ``assembly``.
ASSEMBLY_SUBJECT = "assembly"


def _on_assemblies(rule: dict[str, Any]) -> bool:
    return str(rule.get("subject", "part")) == ASSEMBLY_SUBJECT


@dataclass
class RulePack:
    """A parsed pack."""

    id: str
    title: str
    applies_to: dict[str, Any]
    rules: list[dict[str, Any]]
    path: Path = field(default_factory=Path)


def load_packs(extra_dirs: list[Path] | None = None) -> list[RulePack]:
    """All shipped packs (plus any product-local ``model/rulepacks/*.yaml``)."""
    packs: list[RulePack] = []
    dirs = [RULEPACKS_DIR, *(extra_dirs or [])]
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.yaml")):
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            packs.append(
                RulePack(
                    id=str(data["pack"]),
                    title=str(data.get("title", data["pack"])),
                    applies_to=dict(data.get("applies_to") or {}),
                    rules=list(data.get("rules") or []),
                    path=p,
                )
            )
    return packs


def pack_applies(pack: RulePack, part: Any) -> bool:
    """A pack with ``applies_to: {process: sheet-metal}`` runs only on such parts."""
    for key, val in pack.applies_to.items():
        if getattr(part, key, None) != val:
            return False
    return True


def run_rulepacks(
    product: Product, build_dir: Path, packs: list[RulePack] | None = None
) -> list[CheckResult]:
    """One CheckResult per (rule, part) the pack applies to."""
    from napkin2factory.core.packs import pack_checks

    packs = packs if packs is not None else load_packs([product.paths.model / "rulepacks"])
    # the product's own checks (model/rulepacks/*.py, F10) beside the shipped ones
    own_parts, own_assemblies = pack_checks(product.paths.root)
    part_checks = {**ALL_CHECKS, **own_parts}
    results: list[CheckResult] = []
    for part in product.parts.values():
        feats_path = build_dir / "parts" / part.id / "features.json"
        feats: dict[str, Any] = (
            json.loads(feats_path.read_text(encoding="utf-8")) if feats_path.is_file() else {}
        )
        feats["_has_flat_pattern"] = (build_dir / "parts" / part.id / "flat_pattern.json").is_file()
        feats["_build_dir"] = str(build_dir)
        for pack in packs:
            if not pack_applies(pack, part):
                continue
            for rule in pack.rules:
                if _on_assemblies(rule):
                    continue  # run once per assembly below
                rid = f"rule://{pack.id}/{rule['id']}"
                fn = part_checks.get(str(rule.get("check")))
                if fn is None:
                    results.append(
                        CheckResult(
                            id=f"{rid}@{part.id}",
                            subject=part.uri,
                            status="skip",
                            kind="rule",
                            title=str(rule.get("title", rule["id"])),
                            message=f"unknown check {rule.get('check')!r} in {pack.path.name}",
                        )
                    )
                    continue
                if part.has_geometry is False and pack.applies_to:
                    results.append(
                        CheckResult(
                            id=f"{rid}@{part.id}",
                            subject=part.uri,
                            status="skip",
                            kind="rule",
                            title=str(rule.get("title", rule["id"])),
                            message="no geometry",
                        )
                    )
                    continue
                try:
                    violations = fn(part, feats, dict(rule.get("params") or {}), product)
                except RuleNotApplicable:
                    continue
                except RuleSkip as why:
                    results.append(
                        CheckResult(
                            id=f"{rid}@{part.id}",
                            subject=part.uri,
                            status="skip",
                            kind="rule",
                            title=str(rule.get("title", rule["id"])),
                            message=str(why),
                            detail={"pack": pack.id, "rule": rule["id"]},
                        )
                    )
                    continue
                severity = str(rule.get("severity", "fail"))
                if violations:
                    msg = "; ".join(
                        _fmt(str(rule.get("message", rule["id"])), v) for v in violations
                    )
                    results.append(
                        CheckResult(
                            id=f"{rid}@{part.id}",
                            subject=part.uri,
                            status=severity,
                            kind="rule",
                            title=str(rule.get("title", rule["id"])),
                            message=msg,
                            detail={"violations": violations, "pack": pack.id, "rule": rule["id"]},
                        )
                    )
                else:
                    results.append(
                        CheckResult(
                            id=f"{rid}@{part.id}",
                            subject=part.uri,
                            status="pass",
                            kind="rule",
                            title=str(rule.get("title", rule["id"])),
                            message="ok",
                            detail={"pack": pack.id, "rule": rule["id"]},
                        )
                    )
    results += _assembly_rows(product, packs, {**ASSEMBLY_CHECKS, **own_assemblies})
    return results


def _assembly_rows(
    product: Product, packs: list[RulePack], checks: dict[str, Any] | None = None
) -> list[CheckResult]:
    """One row per (``subject: assembly`` rule, assembly), from packs with no ``applies_to``.

    The row id is ``rule://<pack>/<rule>@<assembly id>`` and its subject ``asm://<id>``
    (P10, S-112: the "module has parts" rule).
    """
    rows: list[CheckResult] = []
    for pack in packs:
        if pack.applies_to:  # part properties (process, …) say nothing about an assembly
            continue
        for rule in pack.rules:
            if not _on_assemblies(rule):
                continue
            rid = f"rule://{pack.id}/{rule['id']}"
            title = str(rule.get("title", rule["id"]))
            fn = (checks if checks is not None else ASSEMBLY_CHECKS).get(str(rule.get("check")))
            for asm in product.assemblies.values():
                if fn is None:
                    rows.append(
                        CheckResult(
                            id=f"{rid}@{asm.id}",
                            subject=asm.uri,
                            status="skip",
                            kind="rule",
                            title=title,
                            message=f"unknown check {rule.get('check')!r} in {pack.path.name}",
                        )
                    )
                    continue
                violations = fn(asm, dict(rule.get("params") or {}), product)
                status = str(rule.get("severity", "fail")) if violations else "pass"
                message = (
                    "; ".join(_fmt(str(rule.get("message", rule["id"])), v) for v in violations)
                    if violations
                    # gate D: a rule may say its pass in words ("Door has its parts")
                    else _fmt(
                        str(rule.get("pass_message", "ok")), {"uri": asm.uri, "name": asm.name}
                    )
                )
                detail: dict[str, Any] = {"pack": pack.id, "rule": rule["id"]}
                if violations:
                    detail["violations"] = violations
                rows.append(
                    CheckResult(
                        id=f"{rid}@{asm.id}",
                        subject=asm.uri,
                        status=status,
                        kind="rule",
                        title=title,
                        message=message,
                        detail=detail,
                    )
                )
    return rows


def _fmt(template: str, values: dict[str, Any]) -> str:
    try:
        return template.format(**values)
    except (KeyError, IndexError):
        return template
