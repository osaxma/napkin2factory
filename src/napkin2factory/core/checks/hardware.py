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

The stage also runs one rule that can hand the owner a *choice* (F12, S-130),
:func:`spacer_bolt_checks`: where a joint puts a bolt into each end of a spacer, the two bolt
ends must not meet inside it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from napkin2factory.core.build_units import BuildUnits
from napkin2factory.core.checks.choices import Option, offer
from napkin2factory.core.checks.results import CheckResult
from napkin2factory.core.loader import Product


def _part_name(product: Product, uri: str) -> str:
    """A party by its name: a part's, or an assembly's (a ``build: external`` stub, B-0082)."""
    if uri.startswith("asm://"):
        asm = product.assemblies.get(uri.removeprefix("asm://"))
        return asm.name if asm is not None else uri
    part = product.parts.get(uri.removeprefix("part://"))
    return part.name if part is not None else uri


def joint_words(product: Product, iface_id: str) -> str:
    """A joint in plain words: its ``name``, else the two parties by name ("Guard to Stand").

    The ``name`` tells apart joints between the same two parts (four standoff walls, two
    hinges), which the part names alone cannot (gate D, S-118).
    """
    iface = product.interfaces[iface_id]
    if iface.name:
        return iface.name
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
    """One ``hardware://<unit>`` row per build unit that has joint hardware (P9).

    The stage then adds the ``fastening://`` rows of :func:`spacer_bolt_checks`.
    """
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
                # gate D: the owner reads what to do, not only what is wrong
                short.append(
                    f"{name}: {need - have} missing, {have} listed where its joints need "
                    f"{need} ({joints}). Add {need - have} to its line in the parts of "
                    f"{asm.name}, or correct the joint's hardware if fewer are needed"
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


# ---- bolts into both ends of a spacer (F12: the first rule that offers a choice) -----------

# Standard sizes the rule's options are made of (S-130). Not invented: each from its standard,
# to be confirmed against the standard's table by a person [verify].
#: ISO 4762 (hexagon socket head cap screws), preferred nominal lengths l, mm.
SCREW_LENGTHS_MM: tuple[float, ...] = (
    3,
    4,
    5,
    6,
    8,
    10,
    12,
    16,
    20,
    25,
    30,
    35,
    40,
    45,
    50,
    55,
    60,
    65,
    70,
    80,
    90,
    100,
    110,
    120,
)
#: Metric coarse pitch P (ISO 261) and hexagon nut height m max (ISO 4032), mm, by thread size.
METRIC_THREADS_MM: dict[float, tuple[float, float]] = {
    3: (0.5, 2.4),
    4: (0.7, 3.2),
    5: (0.8, 4.7),
    6: (1.0, 5.2),
    8: (1.25, 6.8),
    10: (1.5, 8.4),
    12: (1.75, 10.8),
}
#: The least thread a bolt end must engage in a steel internal thread: one nominal diameter
#: (Machinery's Handbook, "length of engagement"; S-130).
MIN_ENGAGEMENT_DIAMETERS = 1.0
#: Thread left past a nut: at least two pitches (common practice; S-130).
NUT_PROTRUSION_PITCHES = 2

# "M6 x 16" (ISO designation: thread size x length) and a spacer's "M6 … 25 mm".
_SCREW = re.compile(r"\bM(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)
_THREAD = re.compile(r"\bM(\d+(?:\.\d+)?)\b")
_LENGTH = re.compile(r"\b(\d+(?:\.\d+)?)\s*mm\b")
_NUT = re.compile(r"\bnut\b", re.IGNORECASE)


def screw_size(name: str) -> tuple[float, float] | None:
    """``(thread, length)`` in mm from a bolt's name in ISO form ("M6 x 16 …"), else ``None``."""
    m = _SCREW.search(name)
    return (float(m.group(1)), float(m.group(2))) if m else None


def spacer_size(name: str) -> tuple[float, float] | None:
    """``(thread, length)`` in mm of a threaded spacer ("M6 … standoff, 25 mm"), else ``None``.

    A name in bolt form ("M6 x 16") is a bolt, not a spacer.
    """
    if _SCREW.search(name):
        return None
    t, n = _THREAD.search(name), _LENGTH.search(name)
    return (float(t.group(1)), float(n.group(1))) if t and n else None


def _num(x: float) -> str:
    """A length in mm as the owner reads it: 16, 14.8."""
    return f"{x:.1f}".removesuffix(".0") if not float(x).is_integer() else str(int(x))


def _mm(x: float) -> str:
    """A computed length in mm to one decimal, as DEC-style sums read: 14.8, 15.0."""
    return f"{x:.1f}"


def sheet_thickness(product: Product, uri: str) -> tuple[float, str] | None:
    """``(thickness mm, evidence URI)`` of a party built from sheet (a kit's ``thickness``).

    The evidence is the ``param://`` the thickness names, or the part itself for a number.
    """
    from napkin2factory.core.model.parts import KitGeometry
    from napkin2factory.core.units import mm, parse_quantity

    part = product.parts.get(uri.removeprefix("part://")) if uri.startswith("part://") else None
    if part is None or not isinstance(part.geometry, KitGeometry):
        return None
    raw = part.geometry.args.get("thickness")
    try:
        if isinstance(raw, str) and raw.startswith("param://"):
            slug = raw.removeprefix("param://")
            return mm(product.parameter_value(slug)), raw
        if isinstance(raw, (int, float, str)):
            return mm(parse_quantity(raw, "mm")), part.uri
    except Exception:  # an unreadable thickness: the rule does not apply to this joint
        return None
    return None


@dataclass
class _Joint:
    iface: str
    words: str
    sheets: tuple[float, float]  # the two parties' sheet thicknesses, in parties order
    far: str  # the second party's name: where a through bolt's nut sits
    holes: int  # spacers in this joint, all its occurrences
    evidence: list[str] = field(default_factory=list)


@dataclass
class _Group:
    bolt: str
    spacer: str
    thread: float
    bolt_len: float
    spacer_len: float
    joints: list[_Joint] = field(default_factory=list)


def _groups(product: Product, units: BuildUnits) -> list[_Group]:
    """The joints that put a bolt into each end of a spacer, grouped by (bolt, spacer)."""
    groups: dict[tuple[str, str], _Group] = {}
    seen: set[str] = set()
    for uid in units.order():
        for j in units.joints(uid):
            if j.iface in seen:
                continue
            seen.add(j.iface)
            bolts = [h for h in j.hardware if h.per_hole == 2]
            spacers = [h for h in j.hardware if h.per_hole == 1]
            for b in bolts:
                for sp in spacers:
                    bpart, spart = product.parts.get(b.part[7:]), product.parts.get(sp.part[7:])
                    if bpart is None or spart is None:
                        continue
                    bs, ss = screw_size(bpart.name), spacer_size(spart.name)
                    if bs is None or ss is None or bs[0] != ss[0]:
                        continue
                    sheets = [sheet_thickness(product, p) for p in j.parties]
                    if sheets[0] is None or sheets[1] is None:
                        continue
                    g = groups.setdefault(
                        (b.part, sp.part), _Group(b.part, sp.part, bs[0], bs[1], ss[1])
                    )
                    g.joints.append(
                        _Joint(
                            j.iface,
                            joint_words(product, j.iface),
                            (sheets[0][0], sheets[1][0]),
                            _part_name(product, j.parties[1]),
                            sp.qty,
                            [f"iface://{j.iface}", sheets[0][1], sheets[1][1]],
                        )
                    )
    return list(groups.values())


def _listed(g: _Group) -> str:
    """The listed bolts by their size: "M6 x 16 bolts"."""
    return f"M{_num(g.thread)} x {_num(g.bolt_len)} bolts"


def _cost(product: Product, uri: str) -> tuple[float, str] | None:
    part = product.parts.get(uri.removeprefix("part://"))
    if part is None or part.cost is None:
        return None
    q = part.cost.unit
    return float(q.magnitude), str(q.units)


def _money(x: float, unit: str) -> str:
    if abs(x) < 0.005:
        return "about the same"
    return f"about {abs(x):.2f} {unit} {'more' if x > 0 else 'less'}"


def spacer_bolt_checks(product: Product, units: BuildUnits | None = None) -> list[CheckResult]:
    """One ``fastening://<spacer>/<bolt>`` row per bolt-and-spacer pair that joints use (F12).

    Where a bolt-pattern joint lists a spacer per hole (``per_hole: 1``, its name giving its
    thread and length, "M6 … 25 mm") and two bolts per hole (``per_hole: 2``, "M6 x 16"), a bolt
    goes into each end of the spacer through one party's sheet (a kit's ``thickness``). Each
    end reaches ``bolt length - sheet`` into the spacer; the two ends must not meet.

    - they stay apart in every such joint → ``pass``;
    - they meet → the fixes, each checked the same way: shorter bolts at both ends (the
      longest standard length whose ends stay apart and still engage one diameter of thread),
      or one bolt right through each spacer with a nut.  Two valid fixes → a ``choice`` that
      holds the release (F12); one → ``fail`` naming it; none → ``fail``. A choice is never
      offered with an option that is not a valid design (FOUNDATION §7).

    The rule does not apply (no row) where a name gives no size or a party has no sheet
    thickness. Lengths come from the parts' names, the only place v0.5's schema holds them
    (S-130).
    """
    units = units or BuildUnits(product)
    out: list[CheckResult] = []
    for g in _groups(product, units):
        bolt_name = _part_name(product, g.bolt)
        spacer_name = _part_name(product, g.spacer)
        lb, ls = g.bolt_len, g.spacer_len
        reach = [(lb - a, lb - b) for a, b in (j.sheets for j in g.joints)]
        joints = "; ".join(j.words for j in g.joints)
        evidence = [g.bolt, g.spacer] + [u for j in g.joints for u in j.evidence]
        evidence = list(dict.fromkeys(evidence))
        holes = sum(j.holes for j in g.joints)
        res = CheckResult(
            id=f"fastening://{g.spacer[7:]}/{g.bolt[7:]}",
            subject=g.spacer,
            status="pass",
            kind="fastening",
            # one name for the part (gate F, concern 11): "the spacer", defined once here
            title=f"Bolts into both ends of each spacer ({spacer_name})",
            message="",
            detail={
                "bolt": g.bolt,
                "spacer": g.spacer,
                "spacer_length_mm": ls,
                "joints": [
                    {"interface": f"iface://{j.iface}", "reach_mm": list(r), "spacers": j.holes}
                    for j, r in zip(g.joints, reach, strict=True)
                ],
                "evidence": evidence,
            },
        )
        worst = max(a + b for a, b in reach)
        bolts = _listed(g)
        if worst < ls:
            res.message = (
                f"the two {bolts} stay {_mm(ls - worst)} mm or more apart inside each "
                f"{_num(ls)} mm spacer ({joints})"
            )
            out.append(res)
            continue
        same: dict[tuple[float, float], list[str]] = {}
        for j, r in zip(g.joints, reach, strict=True):
            same.setdefault(r, []).append(j.words)
        # the sums explained (gate F, concern 11): each bolt's length less the sheet it passes
        sums = " ".join(
            f"At {'; '.join(where)}, the two bolts reach {_mm(a)} and {_mm(b)} mm into the "
            f"spacer: {_mm(a)} + {_mm(b)} = {_mm(a + b)} mm of bolt in {_num(ls)} mm."
            for (a, b), where in same.items()
        )
        problem = (
            f"As listed, the {bolts}, one into each end of each {_num(ls)} mm spacer, meet "
            f"inside it: each bolt reaches into the spacer its {_num(lb)} mm less the sheet it "
            f"passes through. {sums}"
        )
        cost = _cost(product, g.bolt)
        options = [
            _shorter_bolts(g, holes, bolt_name, cost, _thread_through(product, g.spacer)),
            _through_bolt(product, g, holes, bolt_name, cost),
        ]
        out.append(offer(res, options, blocks="release", problem=problem))
    return out


#: A spacer's name or notes saying it is threaded end to end ("threaded through").
_THROUGH = re.compile(
    r"thread(?:ed)?\s+(?:all\s+the\s+way\s+)?through|through[- ]thread|fully\s+threaded"
    r"|tapped\s+(?:right\s+)?through",
    re.IGNORECASE,
)


def _thread_through(product: Product, uri: str) -> bool:
    """Whether the listed spacer says it is threaded all the way through (its name or notes)."""
    part = product.parts.get(uri.removeprefix("part://"))
    return part is not None and bool(_THROUGH.search(f"{part.name} {part.notes or ''}"))


def _shorter_bolts(
    g: _Group,
    holes: int,
    bolt_name: str,
    cost: tuple[float, str] | None,
    through: bool = False,
) -> Option:
    """Option: a shorter standard bolt at both ends of every spacer.

    ``through``: the listed spacer says it is threaded all the way through, so it qualifies.
    """
    d, ls = g.thread, g.spacer_len
    least = MIN_ENGAGEMENT_DIAMETERS * d
    sheets = [j.sheets for j in g.joints]
    fits = [
        n
        for n in SCREW_LENGTHS_MM
        if n < g.bolt_len
        and all((n - a) + (n - b) < ls and min(n - a, n - b) >= least for a, b in sheets)
    ]
    summary = "shorter bolts at both ends"
    if not fits:
        return Option(
            "shorter-bolts",
            summary,
            "",
            invalid=f"no standard length keeps the ends apart and engages {_num(least)} mm",
        )
    n = max(fits)
    ends = [e for a, b in sheets for e in (n - a, n - b)]
    gap = min(ls - ((n - a) + (n - b)) for a, b in sheets)
    # plain words for thread engagement, and whether the listed spacer qualifies (gate F, 11)
    listed = (
        "the listed spacer says it is threaded all the way through, so it qualifies"
        if through
        else "the parts list does not say how deep the listed spacer's thread goes: check it "
        "with the supplier, or list one threaded all the way through"
    )
    take = (
        f"{2 * holes} M{_num(d)} x {_num(n)} bolts in place of the {2 * holes} {_listed(g)} "
        f"(a new line on the parts list); each bolt goes {_mm(min(ends))} to "
        f"{_mm(max(ends))} mm into the spacer and the two ends stay {_mm(gap)} mm apart, so the "
        f"spacer's thread must reach {_mm(max(ends))} mm in from each end (a spacer threaded "
        f"all the way through does; {listed})"
    )
    delta = f"{_money(0, cost[1])} (estimate: priced like the {bolt_name})" if cost else None
    return Option("shorter-bolts", f"{summary}: M{_num(d)} x {_num(n)}", take, delta)


def _through_bolt(
    product: Product, g: _Group, holes: int, bolt_name: str, cost: tuple[float, str] | None
) -> Option:
    """Option: one bolt right through each spacer, with a nut on the far side."""
    d, ls = g.thread, g.spacer_len
    summary = "one bolt right through each spacer, with a nut"
    thread = METRIC_THREADS_MM.get(d)
    if thread is None:
        return Option("through-bolt", summary, "", invalid=f"no nut height known for M{_num(d)}")
    pitch, nut = thread
    need = max(a + ls + b for a, b in (j.sheets for j in g.joints))
    need += nut + NUT_PROTRUSION_PITCHES * pitch
    longer = [n for n in SCREW_LENGTHS_MM if n >= need]
    if not longer:
        return Option(
            "through-bolt", summary, "", invalid=f"no standard length reaches {_num(need)} mm"
        )
    n = min(longer)
    far = sorted({j.far for j in g.joints})
    take = (
        f"{holes} M{_num(d)} x {_num(n)} bolts and {holes} M{_num(d)} nuts in place of the "
        f"{2 * holes} {_listed(g)}; each bolt passes right through, so the spacer must be "
        f"threaded all the way through or have no thread at all, and both ends must be "
        f"reachable when it is fitted; the nut sits on the far side ({'; '.join(far)})"
    )
    nut_part = next(
        (
            p
            for p in product.parts.values()
            if _NUT.search(p.name) and (t := _THREAD.search(p.name)) and float(t.group(1)) == d
        ),
        None,
    )
    nut_cost = _cost(product, nut_part.uri) if nut_part is not None else None
    delta = None
    if cost and nut_cost and cost[1] == nut_cost[1]:
        x = holes * nut_cost[0] - holes * cost[0]
        delta = (
            f"{_money(x, cost[1])} (estimate: bolts priced like the {bolt_name}, nuts "
            f"like the {nut_part.name if nut_part else 'nut'})"
        )
    return Option("through-bolt", f"{summary}: M{_num(d)} x {_num(n)}", take, delta)
