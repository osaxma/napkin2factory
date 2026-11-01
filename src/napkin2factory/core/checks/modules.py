"""Which module a check row belongs to (P12): the matrix groups by it, ``--scope`` selects by it.

A row's *home* is an assembly: an interface's is where its joint closes (a port is checked
by the parent, where both sides meet), an interference, count, layout, hardware or placement
row's is its assembly, a part's row's is the part's home (P5), a requirement's is the lowest
assembly holding everything it is allocated to or satisfied by, a reach row's is its
reader's module.  A row's *module* is the build unit its home is built in (a phantom folds
into its parent, P7); ``None`` is the whole product (documents, sourcing, requirements with
nothing allocated).
"""

from __future__ import annotations

from napkin2factory.core.build_units import BuildUnits
from napkin2factory.core.checks.results import CheckResult
from napkin2factory.core.loader import Product
from napkin2factory.core.model import Requirement

#: Row id schemes whose part after ``://`` (up to an ``@``) is an assembly id.
_ASM_ROWS = ("interference://", "count://", "layout://", "hardware://", "placement://")


class RowModules:
    """Homes and modules of check rows over one loaded product (no build needed)."""

    def __init__(self, product: Product, units: BuildUnits | None = None) -> None:
        """Index the tree, the build units and where each joint closes."""
        self.product = product
        self.units = units or BuildUnits(product)
        self.tree = self.units.tree
        self.closing = self.units.closing()

    def part_home(self, uri: str) -> str | None:
        """A part's home (P5), ``None`` when no single assembly holds it."""
        return self.tree.home(uri)

    def requirement_home(self, req: Requirement) -> str | None:
        """The lowest assembly holding every assembly, part or joint the requirement names."""
        homes: set[str] = set()
        subjects = [str(a.base) for a in req.allocation] if isinstance(req.allocation, list) else []
        subjects += [p.uri for p in self.product.parts.values() if req.id in _ids(p.satisfies)]
        subjects += [a.uri for a in self.product.assemblies.values() if req.id in _ids(a.satisfies)]
        for uri in subjects:
            home = self._uri_home(uri)
            if home is not None:
                homes.add(home)
        if not homes:
            return None
        low = self.tree.lowest_common(homes)
        return low[0] if len(low) == 1 else None

    def requirement_in(self, req: Requirement, aid: str) -> bool:
        """True when ``n2f check --scope asm://<aid>`` checks the requirement (P12).

        It is allocated to (or satisfied by) the assembly, one below it or one of their own
        parts, and its verdict does not read another module's build: a target on a part,
        assembly or joint must be inside too, and a BOM total is the whole product's.  It may
        still be grouped under a higher module in the full matrix, where all it names meets.
        """
        below = self.tree.below(aid)
        subjects = [str(a.base) for a in req.allocation] if isinstance(req.allocation, list) else []
        subjects += [p.uri for p in self.product.parts.values() if req.id in _ids(p.satisfies)]
        subjects += [a.uri for a in self.product.assemblies.values() if req.id in _ids(a.satisfies)]
        if not any(self._uri_home(u) in below for u in subjects if not u.startswith("param://")):
            return False
        target = req.verify.target if req.verify is not None else None
        if target is None:
            return True
        if target.scheme == "bom":
            return False
        if target.scheme in ("part", "asm", "iface"):
            return self._uri_home(str(target.base)) in below
        return True

    def _uri_home(self, uri: str) -> str | None:
        scheme, _, ident = uri.partition("://")
        if scheme == "part":
            return self.part_home(uri)
        if scheme == "asm":
            return ident if ident in self.product.assemblies else None
        if scheme == "iface":
            return self.closing.get(ident)
        if scheme == "param":
            p = self.product.parameters.get(ident)
            return p.scope.id if p is not None and p.scope is not None else None
        return None

    def home(self, row: CheckResult) -> str | None:
        """The assembly a row belongs to (any assembly, a phantom included)."""
        rid = row.id
        if row.kind == "reach":
            return row.module
        if rid.startswith("iface://"):
            return self.closing.get(rid.removeprefix("iface://"))
        for prefix in _ASM_ROWS:
            if rid.startswith(prefix):
                aid = rid.removeprefix(prefix).split("@", 1)[0]
                return aid if aid in self.product.assemblies else None
        if rid.startswith("req://"):
            req = self.product.requirements.get(rid.removeprefix("req://"))
            return self.requirement_home(req) if req is not None else None
        if rid.startswith("doc://"):
            return None
        return self._uri_home(row.subject)

    def module(self, row: CheckResult) -> str | None:
        """The build unit a row belongs to; ``None`` is the whole product."""
        return self.units.unit_of(self.home(row))

    def annotate(self, rows: list[CheckResult]) -> None:
        """Set each row's ``module`` (P12)."""
        for r in rows:
            r.module = self.module(r)

    def inside(self, row: CheckResult, aid: str) -> bool:
        """True when ``--scope asm://<aid>`` keeps the row: its home is ``aid`` or below it.

        A requirement is kept by :meth:`requirement_in` instead.
        """
        if row.id.startswith("req://"):
            req = self.product.requirements.get(row.id.removeprefix("req://"))
            return req is not None and self.requirement_in(req, aid)
        home = self.home(row)
        return home is not None and home in self.tree.below(aid)


def _ids(uris: list[object]) -> set[str]:
    return {str(u).removeprefix("req://") for u in uris}


def module_groups(product: Product, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """The matrix by module: one group per build unit (build order), the whole product last.

    Each group: ``id`` (unit id or ``None``), ``title`` in owner words, the row ``ids`` and a
    ``summary`` (status → count).  Units without rows are left out.
    """
    from napkin2factory.core.build_units import unit_title

    units = BuildUnits(product)
    tops = set(units.tops())
    order: list[str | None] = [*units.order(), None]
    groups: list[dict[str, object]] = []
    for uid in order:
        ids = [str(r["id"]) for r in rows if r.get("module") == uid]
        if not ids:
            continue
        summary: dict[str, int] = {}
        for r in rows:
            if r.get("module") == uid:
                summary[str(r["status"])] = summary.get(str(r["status"]), 0) + 1
        title = (
            unit_title(product.assemblies[uid].name, uid in tops)
            if uid is not None
            else "The whole product"
        )
        groups.append({"id": uid, "title": title, "ids": ids, "summary": summary})
    return groups
