"""``electrical-v0.yaml`` read: each rule's owner words, severity and cited params (E6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

#: The wiring rule pack, beside this module.
PACK_FILE = Path(__file__).with_name("electrical-v0.yaml")
SEVERITIES = ("fail", "warn", "choice")


@dataclass(frozen=True)
class RuleText:
    """One rule of the pack: ``title`` and ``fix`` in owner words, its params with sources."""

    id: str
    title: str
    severity: str
    does: str
    fix: str
    params: dict[str, dict[str, Any]] = field(default_factory=dict)

    def param(self, name: str) -> Any:
        """A param's value: a quantity when it has a unit, else the plain value."""
        row = self.params[name]
        unit = row.get("unit")
        if unit:
            from napkin2factory.core.units import parse_quantity

            return parse_quantity(row["value"], unit)
        return row["value"]


@lru_cache(maxsize=1)
def rules() -> dict[str, RuleText]:
    """The pack's rules by id; every param must cite its source and carry ``verify``."""
    from napkin2factory.core.yamlio import read_yaml

    data = read_yaml(PACK_FILE)
    out: dict[str, RuleText] = {}
    for row in data["rules"]:
        rid = str(row["id"])
        if row["severity"] not in SEVERITIES:
            raise ValueError(f"{PACK_FILE.name}: rule {rid} has severity {row['severity']!r}")
        params = dict(row.get("params") or {})
        for name, p in params.items():
            if not str(p.get("source", "")).strip() or "verify" not in p:
                raise ValueError(
                    f"{PACK_FILE.name}: rule {rid} param {name} needs a `source` and `verify`"
                )
        out[rid] = RuleText(
            id=rid,
            title=str(row["title"]),
            severity=str(row["severity"]),
            does=" ".join(str(row.get("does", "")).split()),
            fix=" ".join(str(row["fix"]).split()),
            params=params,
        )
    return out


def rule(rid: str) -> RuleText:
    """The rule ``rid`` (a ``KeyError`` names a rule the pack does not hold)."""
    return rules()[rid]
