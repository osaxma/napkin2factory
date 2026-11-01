"""Build units, phantoms folded in, the joints each unit closes and their hardware (P7–P9).

The assembly YAML stays the one tree (D18); this module reads it as a build plan:

- A **build unit** is the top assembly, or a sub-assembly with ``build: unit`` (the default).
  A **phantom** (``build: phantom``) only groups lines: its lines, and the joints that close
  inside it, fold into the step of the unit that contains it, multiplied by its quantity.
- A joint (an interface) **closes** in the lowest assembly containing both parties' homes
  (P5's home, :class:`~napkin2factory.core.tree.AssemblyTree`), i.e. where it stops being a
  port (P4).  It belongs to that assembly's unit, or to the unit a phantom folds into.
- One occurrence of a joint takes ``holes × per_hole + per_joint`` of each hardware item
  (:meth:`~napkin2factory.core.model.Interface.hardware_items`, the ``fastener`` alias
  included).  A joint occurs, per one closing assembly, as often as the more numerous of its
  two parties occurs there: alignment (P3) gives every occurrence of either party a partner.
  Several interfaces joining the same two parts (two hinges on one post) share that number.
- A **hardware part** is a part named in some interface's hardware (P9); lines of any other
  part are not counted, so earth studs or glands need no field (S-105).

Nothing here needs a build: the ``bom`` rule writes the plan from it, the ``checks`` rule
counts hardware with it, and both agree because they call the same code.
"""

from __future__ import annotations

from dataclasses import dataclass

from napkin2factory.core.loader import Product
from napkin2factory.core.tree import AssemblyTree

#: Owner words for each driver (P7): why a sub-assembly is built on its own (docs/vocabulary.md).
#: "built-as-unit" is not "built as one unit", which the step's title already says (gate D).
DRIVER_WORDS: dict[str, str] = {
    "built-as-unit": "put together and fitted as one piece",
    "tested-as-unit": "tested as one unit",
    "serviced-as-unit": "serviced or replaced as one unit",
    "separate-process-or-supplier": "made by another process or supplier",
    "varies": "comes in variants",
    "agent-context": "worked on as one module",
}
#: Owner words for a phantom and for a port (docs/vocabulary.md).
PHANTOM_WORDS = "not put together on its own"
BETWEEN_UNITS_WORDS = "a joint between units"


def and_words(words: list[str]) -> str:
    """Say "a", "a and b", "a, b and c": a list said as a sentence (gate D)."""
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def driver_sentence(driver: list[str]) -> str:
    """Say "Built on its own because it is … and …." (empty without a driver)."""
    words = [DRIVER_WORDS.get(d, d) for d in driver]
    return f"Built on its own because it is {and_words(words)}." if words else ""


def unit_title(name: str, top: bool) -> str:
    """A build step in owner words: "Door, built as one unit" (P8, N5)."""
    return f"{name}, the final assembly" if top else f"{name}, built as one unit"


@dataclass(frozen=True)
class Item:
    """One line of a build step: a part, or a sub-unit built in an earlier step."""

    uri: str
    qty: int  # per one unit, multiplied through the phantoms it was folded from
    via: str  # the assembly whose child line this is (the unit itself or a phantom)
    spare: str | None = None
    loose: bool = False

    @property
    def is_unit(self) -> bool:
        """True for a sub-assembly built as a unit of its own (an earlier step)."""
        return self.uri.startswith("asm://")


@dataclass(frozen=True)
class HardwareNeed:
    """What one joint needs of one hardware part, per one unit."""

    part: str
    per_hole: int | None
    per_joint: int | None
    qty: int


@dataclass(frozen=True)
class Joint:
    """An interface that closes in a build step."""

    iface: str  # interface id
    parties: tuple[str, str]
    closes_in: str  # the assembly where it closes: the unit, or a phantom folded into it
    occurrences: int  # per one unit
    holes: int  # per occurrence
    hardware: tuple[HardwareNeed, ...]
    between_units: bool  # a party's home lies in another unit (the joint is a port, P4)


class BuildUnits:
    """The build plan's structure over a loaded product (no build needed)."""

    def __init__(self, product: Product) -> None:
        """Index the product's assemblies; everything else is computed when asked."""
        self.product = product
        self.tree = AssemblyTree(product.assemblies)
        self._tops = self.tree.tops()
        self._closing: dict[str, str | None] | None = None

    # ---- units ------------------------------------------------------------------------

    def tops(self) -> list[str]:
        """The top assemblies (always built, whatever their ``build`` says)."""
        return list(self._tops)

    def is_unit(self, aid: str) -> bool:
        """True when ``aid`` gets a build step of its own (the top, or ``build: unit``)."""
        return aid in self._tops or self.product.assemblies[aid].build == "unit"

    def order(self) -> list[str]:
        """The build units, children before parents: the order of the build steps."""
        return [a for a in self.tree.order() if self.is_unit(a)]

    def unit_of(self, aid: str | None) -> str | None:
        """The build unit ``aid`` is built in: itself, or the lowest unit a phantom folds into.

        ``None`` for ``None``, an unknown id, or a phantom shared by two units (no single one).
        The module of a check row (P12) and the position of a reader (P5) both use it.
        """
        if aid is None or aid not in self.product.assemblies:
            return None
        if self.is_unit(aid):
            return aid
        cands = [u for u in self.order() if aid in self.tree.below(u)]
        low = [u for u in cands if not any(v != u and v in self.tree.below(u) for v in cands)]
        return low[0] if len(low) == 1 else None

    def folded(self, uid: str) -> list[tuple[str, int]]:
        """``(assembly, how many per one unit)``: the unit itself, then the phantoms in it.

        A phantom inside a phantom folds through both (the quantities multiply); a unit
        inside a phantom is not folded, it is a step of its own.  A phantom reached twice
        appears twice, once per path.
        """
        out: list[tuple[str, int]] = [(uid, 1)]

        def walk(aid: str, mult: int, stack: tuple[str, ...]) -> None:
            for c in self.product.assemblies[aid].children:
                if c.asm is None or c.asm.id not in self.product.assemblies:
                    continue
                sub = c.asm.id
                if self.is_unit(sub) or sub in stack:
                    continue
                out.append((sub, mult * c.qty))
                walk(sub, mult * c.qty, (*stack, sub))

        walk(uid, 1, (uid,))
        return out

    def folded_ids(self, uid: str) -> list[str]:
        """The unit and its phantoms, each once, in folding order."""
        seen: dict[str, None] = {}
        for aid, _ in self.folded(uid):
            seen.setdefault(aid, None)
        return list(seen)

    def items(self, uid: str) -> list[Item]:
        """Every line the step fits: its own, then each folded phantom's (phantoms omitted)."""
        out: list[Item] = []
        for aid, mult in self.folded(uid):
            for c in self.product.assemblies[aid].children:
                if c.part is not None:
                    out.append(Item(c.uri, c.qty * mult, aid, c.spare, c.loose))
                elif c.asm is not None and self.is_unit(c.asm.id):
                    out.append(Item(c.uri, c.qty * mult, aid, c.spare, c.loose))
        return out

    # ---- joints -------------------------------------------------------------------------

    def closing(self) -> dict[str, str | None]:
        """Interface id → the assembly where its joint closes (``None`` when it closes nowhere).

        A party listed by no assembly, or whose occurrences no single assembly holds, has no
        home, and the joint is in no step.
        """
        if self._closing is None:
            out: dict[str, str | None] = {}
            for iid, iface in sorted(self.product.interfaces.items()):
                a, b = (str(p) for p in iface.parties)
                ha, hb = self.tree.home(a), self.tree.home(b)
                lowest = self.tree.lowest_common([ha, hb]) if ha and hb else []
                out[iid] = lowest[0] if len(lowest) == 1 else None
            self._closing = out
        return self._closing

    def closed_later(self, iface_id: str) -> str | None:
        """The unit whose step closes the joint when its ``closed_in`` says a later one.

        ``None`` when the field is absent or does not name a build unit above the unit the
        joint closes in (``n2f lint`` reports that, L14); the joint then closes where its
        parts meet.  The joint and its hardware stay in that earlier step (S-118).
        """
        iface = self.product.interfaces[iface_id]
        target = iface.closed_in.id if iface.closed_in is not None else None
        where = self.closing().get(iface_id)
        if target is None or where is None or target not in self.product.assemblies:
            return None
        here = self.unit_of(where)
        if not self.is_unit(target) or here is None or here == target:
            return None
        return target if here in self.tree.below(target) else None

    def unplaced_joints(self) -> list[str]:
        """Interfaces whose joint closes in no assembly (a party in no assembly, say)."""
        return [iid for iid, aid in self.closing().items() if aid is None]

    def joints(self, uid: str) -> list[Joint]:
        """The joints that close in the unit or in a phantom folded into it."""
        inside = set(self.folded_ids(uid))
        out: list[Joint] = []
        for aid, mult in self.folded(uid):
            here = [iid for iid, where in self.closing().items() if where == aid]
            pairs = [frozenset(str(p) for p in self.product.interfaces[i].parties) for i in here]
            for iid in here:
                iface = self.product.interfaces[iid]
                a, b = (str(p) for p in iface.parties)
                # k interfaces joining the same two parts (two hinges on one post) share the
                # occurrences: each is one of the places they meet (S-113)
                k = pairs.count(frozenset((a, b)))
                most = max(self.tree.count_under(aid, a), self.tree.count_under(aid, b))
                occ = mult * -(-most // k)  # rounded up
                holes = iface.holes
                needs = tuple(
                    HardwareNeed(
                        part=str(h.part),
                        per_hole=h.per_hole,
                        per_joint=h.per_joint,
                        qty=occ * ((h.per_hole or 0) * holes + (h.per_joint or 0)),
                    )
                    for h in iface.hardware_items()
                )
                between = any(self.tree.home(p) not in inside for p in (a, b))
                out.append(Joint(iid, (a, b), aid, occ, holes, needs, between))
        return out

    # ---- hardware -------------------------------------------------------------------------

    def hardware_parts(self) -> set[str]:
        """Every part named in some interface's hardware (P9), ``fastener`` alias included."""
        return {
            str(h.part)
            for iface in self.product.interfaces.values()
            for h in iface.hardware_items()
        }

    def demand(self, uid: str) -> dict[str, tuple[int, list[str]]]:
        """Hardware part → (quantity the step's joints need, the interfaces that need it)."""
        out: dict[str, tuple[int, list[str]]] = {}
        for j in self.joints(uid):
            for need in j.hardware:
                qty, ifaces = out.get(need.part, (0, []))
                if j.iface not in ifaces:
                    ifaces = [*ifaces, j.iface]
                out[need.part] = (qty + need.qty, ifaces)
        return dict(sorted(out.items()))

    def declared(self, uid: str) -> dict[str, int]:
        """Hardware part → quantity listed in the unit's lines and its phantoms' (folded)."""
        hw = self.hardware_parts()
        out: dict[str, int] = {}
        for it in self.items(uid):
            if it.uri in hw:
                out[it.uri] = out.get(it.uri, 0) + it.qty
        return dict(sorted(out.items()))

    def spares(self, uid: str) -> dict[str, list[str]]:
        """Part → the ``spare:`` reasons on its lines in the step."""
        out: dict[str, list[str]] = {}
        for it in self.items(uid):
            if it.spare:
                out.setdefault(it.uri, []).append(it.spare)
        return out

    def has_hardware(self, uid: str) -> bool:
        """True when the step's joints need hardware or its lines list some."""
        return bool(self.demand(uid) or self.declared(uid))

    # ---- checks -------------------------------------------------------------------------

    def check_ids(self, uid: str) -> list[str]:
        """Ids of the check rows that cover the step (static: the report joins the verdicts).

        The step's interfaces (both stages), interference and instance counts of the unit and
        its phantoms, the hardware count, and the requirements the unit, its phantoms or its
        parts satisfy or are allocated.
        """
        ids: list[str] = []
        if self.has_hardware(uid):
            ids.append(f"hardware://{uid}")
        for aid in self.folded_ids(uid):
            ids += [f"count://{aid}", f"interference://{aid}"]
        ids += [f"iface://{j.iface}" for j in self.joints(uid)]
        subjects = {f"asm://{a}" for a in self.folded_ids(uid)}
        subjects |= {it.uri for it in self.items(uid) if not it.is_unit}
        reqs: set[str] = set()
        for aid in self.folded_ids(uid):
            reqs |= {r.id for r in self.product.assemblies[aid].satisfies}
        for uri in subjects:
            part = self.product.parts.get(uri.removeprefix("part://"))
            if part is not None and uri.startswith("part://"):
                reqs |= {r.id for r in part.satisfies}
        for rid, req in self.product.requirements.items():
            if isinstance(req.allocation, list) and any(
                str(a.base) in subjects for a in req.allocation
            ):
                reqs.add(rid)
        ids += [f"req://{r}" for r in sorted(reqs)]
        seen: dict[str, None] = {}
        for i in ids:
            seen.setdefault(i, None)
        return list(seen)
