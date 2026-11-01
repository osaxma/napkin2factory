"""The ``hardware`` check stage (P9 as amended by S-105): joint hardware is counted.

One row per build unit whose joints need hardware or whose lines list some
(``hardware://<unit>``).  For each hardware part, the quantity listed in the unit and its
phantoms (folded, :class:`~napkin2factory.core.build_units.BuildUnits`) must be at least what
the joints closing there need:

- fewer → ``fail``, naming the joints and the number missing;
- more → ``warn``, unless a line of that part says why with ``spare: "<reason>"``;
- equal, or more with a reason → ``pass``.

Where two interfaces share holes (S-051), each item is listed once, on the interface whose
joint it closes, so a shared hole counts once.  ``count`` is D18's instance-count stage; this
one is named ``hardware`` to keep them apart.  Owner text names parts and units by name; the
row id, interface ids and the fix stay in ``--json`` (N5, D17).
"""

from __future__ import annotations

from typing import Any

from napkin2factory.core.build_units import BuildUnits
from napkin2factory.core.checks.results import CheckResult
from napkin2factory.core.loader import Product


def _part_name(product: Product, uri: str) -> str:
    part = product.parts.get(uri.removeprefix("part://"))
    return part.name if part is not None else uri


def joint_words(product: Product, iface_id: str) -> str:
    """A joint in plain words: the two parties by name ("guard shell to stand")."""
    iface = product.interfaces[iface_id]
    a, b = (_part_name(product, str(p)) for p in iface.parties)
    return f"{a} to {b}"


def joints_words(product: Product, iface_ids: list[str]) -> str:
    """Several joints in plain words, the same pair of parts said once with a count."""
    counts: dict[str, int] = {}
    for i in iface_ids:
        w = joint_words(product, i)
        counts[w] = counts.get(w, 0) + 1
    return "; ".join(w if n == 1 else f"{w} ({n} joints)" for w, n in counts.items())


def hardware_checks(product: Product, units: BuildUnits | None = None) -> list[CheckResult]:
    """One ``hardware://<unit>`` row per build unit that has joint hardware (P9)."""
    units = units or BuildUnits(product)
    out: list[CheckResult] = []
    for uid in units.order():
        if not units.has_hardware(uid):
            continue
        asm = product.assemblies[uid]
        demand = units.demand(uid)
        declared = units.declared(uid)
        spares = units.spares(uid)
        short: list[str] = []
        extra: list[str] = []
        spared: list[str] = []
        parts: dict[str, Any] = {}
        for part in sorted(set(demand) | set(declared)):
            need, ifaces = demand.get(part, (0, []))
            have = declared.get(part, 0)
            name = _part_name(product, part)
            joints = joints_words(product, ifaces)
            row: dict[str, Any] = {"declared": have, "demand": need, "interfaces": ifaces}
            if have < need:
                short.append(
                    f"{name}: {need - have} missing, {have} listed where its joints need "
                    f"{need} ({joints})"
                )
                row["missing"] = need - have
            elif have > need:
                reasons = spares.get(part, [])
                row["surplus"] = have - need
                if reasons:
                    row["spare"] = reasons
                    spared.append(f"{name}: {have - need} spare ({'; '.join(reasons)})")
                else:
                    why = (
                        f"its joints need {need} ({joints})"
                        if ifaces
                        else "no joint here needs any"
                    )
                    extra.append(
                        f"{name}: {have - need} more than needed, {have} listed where {why}"
                    )
            parts[part] = row
        if short:
            status, message = "fail", "; ".join(short + extra)
            fix = "list the missing hardware on the assembly's child lines"
        elif extra:
            status, message = "warn", "; ".join(extra)
            fix = 'list fewer, or say why on the line: spare: "<reason>"'
        else:
            status = "pass"
            message = f"the hardware for its {len(units.joints(uid))} joint(s) is all listed"
            if spared:
                message += "; " + "; ".join(spared)
            fix = ""
        out.append(
            CheckResult(
                id=f"hardware://{uid}",
                subject=asm.uri,
                status=status,
                kind="hardware",
                title=f"{asm.name}: joint hardware",
                message=message,
                detail={
                    "assembly": asm.uri,
                    "folded": [f"asm://{a}" for a in units.folded_ids(uid)[1:]],
                    "parts": parts,
                    **({"fix": fix} if fix else {}),
                },
            )
        )
    return out
