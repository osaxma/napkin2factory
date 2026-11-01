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
    EXTERNAL_WORDS,
    PHANTOM_WORDS,
    BuildUnits,
    driver_sentence,
    driver_words,
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
        if a.build == "external":  # its ports are the joints that fit it (F11, S-127)
            log.add(f"{a.uri}#ports")
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


#: A joint with no hardware to count, in owner words (gate D, S-118).
NO_FIXINGS = "no loose fixings"


def plan_joint_words(product: Product, iface_id: str) -> str:
    """A joint in plain words, an external stub said by its name, never its URI (F11).

    :func:`~napkin2factory.core.checks.hardware.joint_words` names part parties; a stub
    (``build: external``) is the one assembly an interface may join (S-124).
    """
    iface = product.interfaces[iface_id]
    parties = [str(p) for p in iface.parties]
    if iface.name or not any(p.startswith("asm://") for p in parties):
        return joint_words(product, iface_id)
    a, b = (_name(product, p) for p in parties)
    return f"{a} to {b}"


def _supplied(product: Product, units: BuildUnits, uid: str) -> list[dict[str, Any]]:
    """The external stubs the step fits (F11): each with the joints that fit it."""
    out = []
    for aid, qty, ports in units.supplied(uid):
        out.append(
            {
                "asm": f"asm://{aid}",
                "id": aid,
                "name": product.assemblies[aid].name,
                "qty": qty,
                "words": EXTERNAL_WORDS,
                "ports": ports,
                "joints": [plan_joint_words(product, p.removeprefix("iface://")) for p in ports],
            }
        )
    return out


def supplied_sentence(s: dict[str, Any]) -> str:
    """Say "Controls: supplied, not built here; fitted at Frame to Controls." (F11)."""
    qty = f"{s['qty']} × " if s["qty"] != 1 else ""
    joints = s.get("joints") or []
    fits = f"; fitted at {'; '.join(joints)}" if joints else ""
    return f"{qty}{s['name']}: {s['words']}{fits}."


def joint_kind_words(kind: str, holes: int, has_hardware: bool) -> str:
    """How a joint is made, in owner words (N5): "bolted, 4 holes", "faces that meet"."""
    if kind == "bolt-pattern":
        return f"bolted, {holes} holes" if holes else "bolted"
    if kind != "mating-face":  # a domain's interface kind: its own title (F6)
        from napkin2factory.core.registry import registry

        return registry().interface_kind(kind).title.lower() or kind
    if has_hardware:
        return "faces that meet, with fasteners"
    return f"faces that meet, {NO_FIXINGS} (welded, riveted or clamped)"


def lower_name(name: str) -> str:
    """A name inside a sentence ("Lining" → "lining"); acronyms keep their capitals."""
    if len(name) > 1 and name[0].isupper() and not name[1].isupper():
        return name[0].lower() + name[1:]
    return name


def item_range(numbers: list[int]) -> str:
    """Say "items 18–26", "item 4", "items 3, 5 and 7" for a folded grouping's lines."""
    if not numbers:
        return ""
    if len(numbers) == 1:
        return f"item {numbers[0]}"
    if numbers == list(range(numbers[0], numbers[-1] + 1)):
        return f"items {numbers[0]}–{numbers[-1]}"
    head = ", ".join(str(n) for n in numbers[:-1])
    return f"items {head} and {numbers[-1]}"


def _arrival(units: BuildUnits, uid: str, items: list[dict[str, Any]], party: str) -> int:
    """The item number at which a joint's party arrives in the step (build order, gate D).

    A part listed in the step arrives with its line; a part inside an earlier unit arrives
    with that unit's line.  Unknown: after every line.
    """
    for it in items:
        if it["uri"] == party:
            return int(it["item"])
    home = units.unit_of(units.tree.home(party))
    for it in items:
        if home is not None and it["uri"] == f"asm://{home}":
            return int(it["item"])
    return len(items) + 1


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
        # build order (gate D): a joint is closed once the later of its two parts is in
        # place, so the child lines' order is the joints' order; ties by interface id
        order_key = {
            j.iface: (
                max(_arrival(units, uid, items, p) for p in j.parties),
                min(_arrival(units, uid, items, p) for p in j.parties),
                j.iface,
            )
            for j in units.joints(uid)
        }
        for j in sorted(units.joints(uid), key=lambda j: order_key[j.iface]):
            kind = product.interfaces[j.iface].kind
            later = units.closed_later(j.iface)
            joints.append(
                {
                    "interface": f"iface://{j.iface}",
                    **({"closed_later_in": f"asm://{later}"} if later else {}),
                    "parties": list(j.parties),
                    "words": plan_joint_words(product, j.iface),
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
        supplied = _supplied(product, units, uid)
        out_units[uid] = {
            "step": step_of[uid],
            "unit": asm.uri,
            "name": asm.name,
            "rev": asm.rev,
            "title": unit_title(asm.name, top),
            "top": top,
            "driver": list(asm.driver),
            "driver_words": [driver_words()[d] for d in asm.driver],  # F6: the table
            "driver_sentence": driver_sentence(list(asm.driver)),
            "built_per_product": sum(_count_asm(product, t, uid) for t in tops),
            "parents": parents,
            "folded": [
                {
                    "asm": f"asm://{aid}",
                    "name": product.assemblies[aid].name,
                    "qty": mult,
                    "words": PHANTOM_WORDS,
                    # gate D: which lines of the step are this grouping's
                    "items": [it["item"] for it in items if it["via"] == f"asm://{aid}"],
                }
                for aid, mult in units.folded(uid)[1:]
            ],
            "items": items,
            "joints": joints,
            "hardware": hardware,
            "checks": units.check_ids(uid),
            # F11: only a step that fits a stub says so; a product without one keeps its plan
            **({"supplied": supplied} if supplied else {}),
        }
    for step in out_units.values():
        # gate D: grouped lines carry the grouping's name ("lining") for the note column
        names = {f["asm"]: lower_name(f["name"]) for f in step["folded"]}
        for it in step["items"]:
            if it["via"] in names:
                it["group"] = names[it["via"]]
        step["parent_steps"] = [
            {
                "unit": pa,
                "step": out_units[pa.removeprefix("asm://")]["step"],
                "title": out_units[pa.removeprefix("asm://")]["title"],
            }
            for pa in step["parents"]
        ]
    # S-118: a joint closed later (``closed_in``) is listed again in the step that closes
    # it, marked as carried; its hardware stays counted where its parts meet
    for step in list(out_units.values()):
        for j in step["joints"]:
            target = j.get("closed_later_in")
            if target is None:
                continue
            later = out_units[target.removeprefix("asm://")]
            j["closed_later_step"] = later["step"]
            carried = {k: v for k, v in j.items() if not k.startswith("closed_later")}
            later["joints"].append({**carried, "from_step": step["step"]})
    # P13: every joint where two units built separately meet, in build order, with the step
    # that closes it (the verdicts are joined by the report: ``bom`` runs before ``checks``)
    between = [
        {**j, "step": step["step"], "closed_by": step["unit"], "closed_by_name": step["name"]}
        for step in out_units.values()
        for j in step["joints"]
        if j["between_units"] and "from_step" not in j
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
    sentence = step.get("driver_sentence") or driver_sentence(step["driver"])
    if sentence:
        lines[0] += f" {sentence}"
    for f in step["folded"]:
        lines.append(folded_sentence(f))
    for s in step.get("supplied", []):
        lines.append(supplied_sentence(s))
    lines += ["", "| item | part | qty | note |", "|---:|---|---:|---|"]
    for it in step["items"]:
        lines.append(f"| {it['item']} | {it['name']} | {it['qty']} | {'; '.join(item_notes(it))} |")
    if step["joints"]:
        lines += ["", "Joints closed in this step:", ""]
        for j in step["joints"]:
            lines.append(f"- {joint_line(j)}")
    return "\n".join(lines) + "\n"


def folded_sentence(f: dict[str, Any]) -> str:
    """A grouping's lines in the step: "The lining (items 18–26) is not put together …"."""
    qty = f", {f['qty']} ×" if f["qty"] != 1 else ""
    where = item_range(f.get("items", []))
    inside = f" ({where}{qty})" if where or qty else ""
    return (
        f"The {lower_name(f['name'])}{inside} is {PHANTOM_WORDS}: lay it in place during this step."
    )


def item_notes(it: dict[str, Any]) -> list[str]:
    """The note column of one item, in owner words (the report, the manual, the sheet)."""
    notes = []
    if it["kind"] == "unit":
        notes.append(f"built in step {it['step']}" if it.get("step") else "built earlier")
    elif it["kind"] == "cots":
        notes.append("bought")
    if it.get("group"):
        notes.append(it["group"])
    if it.get("loose"):
        notes.append("packed loose for the installer")
    if it.get("spare"):
        notes.append(f"spare: {it['spare']}")
    return notes


def hardware_words(j: dict[str, Any]) -> str:
    """Say "8 × M6 x 16 socket-head cap screw, 4 × …", or "no loose fixings"."""
    hw = ", ".join(f"{h['qty']} × {h['name']}" for h in j["hardware"])
    if hw and "from_step" in j:
        return f"{hw} (listed in step {j['from_step']})"
    return hw or NO_FIXINGS


def joint_status_words(j: dict[str, Any]) -> str:
    """Say "closed later, in step 3" / "from step 1" / "a joint between units" (or empty)."""
    out = []
    if j.get("closed_later_step"):
        out.append(f"closed later, in step {j['closed_later_step']}")
    if "from_step" in j:
        out.append(f"left open in step {j['from_step']}")
    if j["between_units"]:
        out.append(BETWEEN_UNITS_WORDS)
    return "; ".join(out)


def joint_line(j: dict[str, Any]) -> str:
    """One joint as a manual line: "2 × Shell to guard, …, 4 holes each: 8 × …"."""
    times = f"{j['occurrences']} × " if j["occurrences"] != 1 else ""
    each = " each" if j["occurrences"] != 1 else ""
    holes = f", {j['holes']} holes{each}" if j["holes"] else ""
    status = joint_status_words(j)
    return f"{times}{j['words']}{holes}{f' ({status})' if status else ''}: {hardware_words(j)}"
