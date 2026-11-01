"""The assembly tree: what contains what, a part's home, and the ports a joint needs (P4, P5).

Two notions of "the lowest assembly containing both parties" live here, on purpose:

- :meth:`AssemblyTree.lowest_containing` (P3, the alignment stage): the assemblies whose
  parts include both, with no sub-assembly that also includes both.  Alignment is checked
  where the two parts actually meet.
- :meth:`AssemblyTree.port_crossings` (P4): starts from each part's *home* (P5), the lowest
  assembly containing all its occurrences.  A bolt used in the door and in the top assembly
  has its home at the top, so a joint naming it is a port of the door.

Both take the assembly YAML only (no build), so the loader can use them.  M4 reuses
:meth:`AssemblyTree.home` for parameter reach (P5).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from napkin2factory.core.model.assemblies import Assembly


class AssemblyTree:
    """Containment over ``assemblies/*.yaml`` (cycle-safe: the loader reports cycles)."""

    def __init__(self, assemblies: Mapping[str, Assembly]) -> None:
        """Index the assemblies by id; nothing is computed until asked."""
        self._asms = assemblies
        self._below: dict[str, frozenset[str]] = {}
        self._parts: dict[str, frozenset[str]] = {}

    def below(self, aid: str) -> frozenset[str]:
        """``aid`` and every assembly under it, through all levels."""
        if aid not in self._below:
            self._below[aid] = frozenset({aid})  # cycle guard
            out = {aid}
            for c in self._asms[aid].children:
                if c.asm is not None and c.asm.id in self._asms:
                    out |= self.below(c.asm.id)
            self._below[aid] = frozenset(out)
        return self._below[aid]

    def parts_under(self, aid: str) -> frozenset[str]:
        """Every part URI under assembly ``aid``, through its sub-assemblies."""
        if aid not in self._parts:
            self._parts[aid] = frozenset(
                f"part://{c.part.id}"
                for sub in self.below(aid)
                for c in self._asms[sub].children
                if c.part is not None
            )
        return self._parts[aid]

    def tops(self) -> list[str]:
        """Assemblies no other assembly contains, sorted."""
        used = {c.asm.id for a in self._asms.values() for c in a.children if c.asm is not None}
        return sorted(a for a in self._asms if a not in used)

    def order(self) -> list[str]:
        """Every assembly, children before parents (depth first, ids sorted at each level)."""
        out: list[str] = []
        seen: set[str] = set()

        def visit(aid: str) -> None:
            if aid in seen:
                return
            seen.add(aid)
            for c in self._asms[aid].children:
                if c.asm is not None and c.asm.id in self._asms:
                    visit(c.asm.id)
            out.append(aid)

        for aid in sorted(self._asms):
            visit(aid)
        return out

    def count_under(self, aid: str, part_uri: str) -> int:
        """Occurrences of ``part_uri`` in one ``aid``, quantities multiplied through every level."""
        pid = part_uri.removeprefix("part://")
        total = 0
        for c in self._asms[aid].children:
            if c.part is not None and c.part.id == pid:
                total += c.qty
            elif c.asm is not None and c.asm.id in self._asms and c.asm.id != aid:
                total += c.qty * self.count_under(c.asm.id, part_uri)
        return total

    def listers(self, part_uri: str) -> list[str]:
        """Assemblies that list ``part_uri`` as a direct child line, sorted."""
        pid = part_uri.removeprefix("part://")
        return sorted(
            aid
            for aid, asm in self._asms.items()
            if any(c.part is not None and c.part.id == pid for c in asm.children)
        )

    def lowest_common(self, aids: Iterable[str]) -> list[str]:
        """The lowest assemblies that contain every one of ``aids`` (itself included), sorted.

        One answer in a tree; several only when sub-assemblies are shared in a diamond, none
        when no single assembly holds them all.
        """
        want = set(aids)
        if not want:
            return []
        common = [a for a in self._asms if want <= self.below(a)]
        return sorted(a for a in common if not any(b != a and b in self.below(a) for b in common))

    def home(self, part_uri: str) -> str | None:
        """The lowest assembly containing all occurrences of ``part_uri`` (P5).

        A part listed in one assembly lives there; one listed in two sibling sub-assemblies
        lives in their parent.  ``None`` when no assembly lists it, or no single assembly
        holds all its occurrences.
        """
        lowest = self.lowest_common(self.listers(part_uri))
        return lowest[0] if len(lowest) == 1 else None

    def lowest_containing(self, a: str, b: str) -> list[str]:
        """Assemblies containing both parts with no sub-assembly that also contains both (P3)."""
        both = {aid for aid in self._asms if {a, b} <= self.parts_under(aid)}
        return sorted(
            aid
            for aid in both
            if not any(c.asm is not None and c.asm.id in both for c in self._asms[aid].children)
        )

    def port_crossings(self, a: str, b: str) -> list[str]:
        """Assemblies that must list a joint between parts ``a`` and ``b`` as a port (P4).

        Every assembly from each part's home up to, not including, the lowest assembly that
        contains both homes: exactly those with one home inside and the other outside.
        Empty when the homes coincide or one is unknown.
        """
        ha, hb = self.home(a), self.home(b)
        if ha is None or hb is None or ha == hb:
            return []
        out: set[str] = set()
        for top in self.lowest_common([ha, hb]):
            for aid in self.below(top) - {top}:
                inside = self.below(aid)
                if (ha in inside) != (hb in inside):
                    out.add(aid)
        return sorted(out)
