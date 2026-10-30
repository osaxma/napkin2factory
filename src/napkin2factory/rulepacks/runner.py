"""Load rule packs and evaluate them against every part's ``features.json``."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from napkin2factory.core.checks.results import CheckResult
from napkin2factory.core.loader import Product
from napkin2factory.rulepacks import RULEPACKS_DIR
from napkin2factory.rulepacks.checks import CHECKS


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
    packs = packs if packs is not None else load_packs([product.paths.model / "rulepacks"])
    results: list[CheckResult] = []
    for part in product.parts.values():
        feats_path = build_dir / "parts" / part.id / "features.json"
        feats: dict[str, Any] = (
            json.loads(feats_path.read_text(encoding="utf-8")) if feats_path.is_file() else {}
        )
        feats["_has_flat_pattern"] = (build_dir / "parts" / part.id / "flat_pattern.json").is_file()
        for pack in packs:
            if not pack_applies(pack, part):
                continue
            for rule in pack.rules:
                rid = f"rule://{pack.id}/{rule['id']}"
                fn = CHECKS.get(str(rule.get("check")))
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
                violations = fn(part, feats, dict(rule.get("params") or {}), product)
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
    return results


def _fmt(template: str, values: dict[str, Any]) -> str:
    try:
        return template.format(**values)
    except (KeyError, IndexError):
        return template
