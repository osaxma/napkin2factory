"""The build plan, derived from the assembly tree (P8): ``build/bom/build-plan.json``.

One step per build unit, children before parents, phantoms folded into their parent's step
(:class:`~napkin2factory.core.build_units.BuildUnits`).  Each step lists its items (the BOM
lines it fits, numbered: the same item numbers appear on the unit's assembly sheet and in
``build_step()``), the joints it closes with their hardware and derived counts, and the ids
of the check rows that cover it.  The ids are static because ``bom`` runs before
``checks``; the report joins them to the verdicts.

Every model value the plan reads goes through the ``bom`` rule's read log (D5), so editing a
driver, a child line or an interface's hardware re-runs the rule and every page that read
the plan (``bom://build-plan#units.<id>``).
"""

from __future__ import annotations

from typing import Any

from napkin2factory.core.build_units import (
    BETWEEN_UNITS_WORDS,
    DRIVER_WORDS,
    PHANTOM_WORDS,
    BuildUnits,
    unit_title,
)
from napkin2factory.core.checks.hardware import joint_words
from napkin2factory.core.loader import Product
from napkin2factory.geometry.accessors import ReadLog

PLAN_FILE = "build-plan.json"
SCHEMA = 1


def plan_key(unit_id: str) -> str:
    """The recorded-read key of one step (``bom://build-plan#units.<id>``)."""
    return f"bom://build-plan#units.{unit_id}"


def _record_reads(product: Product, log: ReadLog) -> None:
    for key in ("set://asms", "set://parts", "set://ifaces", "set://reqs"):
        log.add(key)
    for a in product.assemblies.values():
        for field in ("name", "rev", "children", "build", "driver", "satisfies"):
            log.add(f"{a.uri}#{field}")
    for p in product.parts.values():
        for field in ("name", "kind", "satisfies"):
            log.add(f"{p.uri}#{field}")
    for i in product.interfaces:
        log.add(f"iface://{i}")  # parties, holes and hardware
    for r in product.requirements:
        log.add(f"req://{r}#allocation")


def _count_asm(product: Product, under: str, aid: str) -> int:
    """Occurrences of sub-assembly ``aid`` in one ``under`` (``under`` itself counts 1)."""
    if under == aid:
        return 1
    total = 0
    for c in product.assemblies[under].children:
        if c.asm is not None and c.asm.id in product.assemblies:
            total += c.qty * _count_asm(product, c.asm.id, aid)
    return total


def _name(product: Product, uri: str) -> str:
    if uri.startswith("asm://"):
        a = product.assemblies.get(uri.removeprefix("asm://"))
        return a.name if a is not None else uri
    p = product.parts.get(uri.removeprefix("part://"))
    return p.name if p is not None else uri


def joint_kind_words(kind: str, holes: int, has_hardware: bool) -> str:
    """How a joint is made, in owner words (N5): "bolted, 4 holes", "faces that meet"."""
    if kind == "bolt-pattern":
        return f"bolted, {holes} holes" if holes else "bolted"
    if has_hardware:
        return "faces that meet, with fasteners"
    return "faces that meet (welded, riveted or clamped: no loose hardware)"


def _sides(product: Product, units: BuildUnits, parties: tuple[str, str]) -> list[dict[str, Any]]:
    """Each party of a joint with the build unit it is built into (P13)."""
    out = []
    for party in parties:
        uid = units.unit_of(units.tree.home(party))
        out.append(
            {
                "part": party,
                "name": _name(product, party),
                "unit": f"asm://{uid}" if uid else None,
                "unit_name": product.assemblies[uid].name if uid else None,
            }
        )
    return out


def derive_build_plan(product: Product, log: ReadLog | None = None) -> dict[str, Any]:
    """The ``build-plan.json`` payload (P8); records its reads in ``log``."""
    log = log if log is not None else ReadLog()
    _record_reads(product, log)
    units = BuildUnits(product)
    order = units.order()
    step_of = {uid: n for n, uid in enumerate(order, start=1)}
    tops = units.tops()
    out_units: dict[str, Any] = {}
    for uid in order:
        asm = product.assemblies[uid]
        top = uid in tops
        hardware_parts = units.hardware_parts()
        items = []
        for n, it in enumerate(units.items(uid), start=1):
            row: dict[str, Any] = {
                "item": n,
                "uri": it.uri,
                "id": it.uri.split("://", 1)[1],
                "name": _name(product, it.uri),
                "qty": it.qty,
                "via": f"asm://{it.via}",
            }
            if it.is_unit:
                row["kind"] = "unit"
                row["step"] = step_of.get(it.uri.removeprefix("asm://"))
            else:
                row["kind"] = product.parts[it.uri.removeprefix("part://")].kind
                row["hardware"] = it.uri in hardware_parts
            if it.spare:
                row["spare"] = it.spare
            if it.loose:
                row["loose"] = True
            items.append(row)
        joints = []
        for j in units.joints(uid):
            kind = product.interfaces[j.iface].kind
            joints.append(
                {
                    "interface": f"iface://{j.iface}",
                    "parties": list(j.parties),
                    "words": joint_words(product, j.iface),
                    "kind": kind,
                    "how": joint_kind_words(kind, j.holes, bool(j.hardware)),
                    "sides": _sides(product, units, j.parties),
                    "closes_in": f"asm://{j.closes_in}",
                    "occurrences": j.occurrences,
                    "holes": j.holes,
                    "between_units": j.between_units,
                    "hardware": [
                        {
                            "part": h.part,
                            "name": _name(product, h.part),
                            **({"per_hole": h.per_hole} if h.per_hole is not None else {}),
                            **({"per_joint": h.per_joint} if h.per_joint is not None else {}),
                            "qty": h.qty,
                        }
                        for h in j.hardware
                    ],
                }
            )
        demand = units.demand(uid)
        declared = units.declared(uid)
        spares = units.spares(uid)
        hardware = [
            {
                "part": part,
                "name": _name(product, part),
                "demand": demand.get(part, (0, []))[0],
                "declared": declared.get(part, 0),
                **({"spare": spares[part]} if part in spares else {}),
            }
            for part in sorted(set(demand) | set(declared))
        ]
        parents = [
            f"asm://{v}"
            for v in order
            if any(it.uri == asm.uri for it in units.items(v)) and v != uid
        ]
        out_units[uid] = {
            "step": step_of[uid],
            "unit": asm.uri,
            "name": asm.name,
            "rev": asm.rev,
            "title": unit_title(asm.name, top),
            "top": top,
            "driver": list(asm.driver),
            "driver_words": [DRIVER_WORDS[d] for d in asm.driver],
            "built_per_product": sum(_count_asm(product, t, uid) for t in tops),
            "parents": parents,
            "folded": [
                {
                    "asm": f"asm://{aid}",
                    "name": product.assemblies[aid].name,
                    "qty": mult,
                    "words": PHANTOM_WORDS,
                }
                for aid, mult in units.folded(uid)[1:]
            ],
            "items": items,
            "joints": joints,
            "hardware": hardware,
            "checks": units.check_ids(uid),
        }
    # P13: every joint where two units built separately meet, in build order, with the step
    # that closes it (the verdicts are joined by the report: ``bom`` runs before ``checks``)
    between = [
        {**j, "step": step["step"], "closed_by": step["unit"], "closed_by_name": step["name"]}
        for step in out_units.values()
        for j in step["joints"]
        if j["between_units"]
    ]
    return {
        "schema": SCHEMA,
        "order": order,
        "units": out_units,
        "between_units": between,
        "joints_in_no_step": [f"iface://{i}" for i in units.unplaced_joints()],
        "words": {"phantom": PHANTOM_WORDS, "between_units": BETWEEN_UNITS_WORDS},
    }


def step_markdown(plan: dict[str, Any], unit_id: str) -> str:
    """One step as Markdown for a manual page: items, then the joints and their hardware.

    Owner words only (N5): parts and units by name, quantities, no ids.
    """
    step = plan["units"][unit_id]
    lines = [f"**Step {step['step']}: {step['title']}.**"]
    if step["driver_words"]:
        lines[0] += f" Built on its own because it is {', '.join(step['driver_words'])}."
    for f in step["folded"]:
        qty = f" ({f['qty']} ×)" if f["qty"] != 1 else ""
        lines.append(f"It includes {f['name']}{qty}: {f['words']}.")
    lines += ["", "| item | part | qty | note |", "|---:|---|---:|---|"]
    for it in step["items"]:
        notes = []
        if it["kind"] == "unit":
            notes.append(f"built in step {it['step']}" if it.get("step") else "built earlier")
        elif it["kind"] == "cots":
            notes.append("bought")
        if it.get("loose"):
            notes.append("packed loose for the installer")
        if it.get("spare"):
            notes.append(f"spare: {it['spare']}")
        lines.append(f"| {it['item']} | {it['name']} | {it['qty']} | {'; '.join(notes)} |")
    if step["joints"]:
        lines += ["", "Joints closed in this step:", ""]
        for j in step["joints"]:
            hw = ", ".join(f"{h['qty']} × {h['name']}" for h in j["hardware"]) or "no hardware"
            times = f"{j['occurrences']} × " if j["occurrences"] != 1 else ""
            each = " each" if j["occurrences"] != 1 else ""
            holes = f", {j['holes']} holes{each}" if j["holes"] else ""
            between = f" ({BETWEEN_UNITS_WORDS})" if j["between_units"] else ""
            lines.append(f"- {times}{j['words']}{holes}{between}: {hw}")
    return "\n".join(lines) + "\n"
