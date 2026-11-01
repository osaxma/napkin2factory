"""Parameter reach (P5): which module may read which parameter.

A parameter with ``scope: asm://X`` belongs to the module X (a build unit, never a phantom:
the loader refuses that).  A reader sits in a module too: a part rule where the part's home
is (:meth:`AssemblyTree.home`), an assembly rule at its assembly, a phantom folded into the
unit it is built in (P7), a scoped parameter's expression at its scope, and an unscoped one at
the level of the whole product.  From there:

- unscoped parameters are everyone's (P14: a product without scopes behaves as before);
- the reader's own module's parameters and its ancestors' are within reach;
- a descendant's parameter is within reach only when it is exported (``export: true``);
- a sibling's (or cousin's) never is.

What is looked at: the reads recorded by the last build for part and assembly rules (the
manifest), minus the reads made only while resolving an interface (``Entry.iface_reads``:
the other party's frame is the joint's business), and, statically, the parameters named in
each parameter's ``expr``.  An interface's own expressions may name what either party may
read.  Doc, BOM, drawing, assembly-sheet, calc and check rules are exempt.  A finding is a
``warn`` row (v0.4); the rule id and the facts stay in ``--json``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from napkin2factory.core.build_units import BuildUnits
from napkin2factory.core.checks.results import CheckResult
from napkin2factory.core.expr import ExprError, referenced_names
from napkin2factory.core.graph.hashing import sha256_json
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.loader import Product

#: The read key the ``checks`` rule records so a scope, an export or a recorded read that
#: changes re-runs the reach check (D5); :func:`reach_fingerprint` is its value.
REACH_KEY = "reach:inputs"

#: Rule kinds whose recorded reads are checked (P5); every other kind is exempt.
CHECKED_KINDS = ("part", "asm")

#: Why a read is out of reach (``detail.why`` in ``--json``).
WHY_SIBLING = "sibling"
WHY_UNEXPORTED = "unexported"


@dataclass(frozen=True)
class Finding:
    """One read out of reach."""

    reader: str  # part://x, asm://x (its placement code), param://x (its expr), iface://x
    position: str | None  # the module the reader sits in (a unit id), None: the whole product
    param: str  # the slug read
    owner: str  # the assembly the parameter is scoped to
    why: str  # WHY_SIBLING | WHY_UNEXPORTED
    how: str  # "build" (a recorded read) | "expr" (named in an expression)


class Reach:
    """The reach rules over one loaded product (no build needed except for recorded reads)."""

    def __init__(self, product: Product, units: BuildUnits | None = None) -> None:
        """Index the tree and the scoped parameters."""
        self.product = product
        self.units = units or BuildUnits(product)
        self.tree = self.units.tree
        self.scoped: dict[str, str] = {
            slug: p.scope.id
            for slug, p in product.parameters.items()
            if p.scope is not None and p.scope.id in product.assemblies
        }

    @property
    def active(self) -> bool:
        """True when some parameter is scoped: otherwise nothing is checked (P14)."""
        return bool(self.scoped)

    # ---- positions -------------------------------------------------------------------

    def part_position(self, part_uri: str) -> str | None:
        """The module a part's rule sits in: the unit of the part's home (P5)."""
        return self.units.unit_of(self.tree.home(part_uri))

    def asm_position(self, aid: str) -> str | None:
        """The module an assembly's rule sits in (a phantom: the unit it folds into)."""
        return self.units.unit_of(aid)

    def param_position(self, slug: str) -> str | None:
        """Where a parameter's expression sits: its scope, or the whole product (``None``)."""
        return self.scoped.get(slug)

    # ---- the rule -------------------------------------------------------------------

    def why_out_of_reach(self, position: str | None, slug: str) -> str | None:
        """``None`` when a reader at ``position`` may read ``slug``, else the reason."""
        owner = self.scoped.get(slug)
        if owner is None:
            return None  # unscoped: the whole product's
        if position is not None and position in self.tree.below(owner):
            return None  # the owner is the reader's module or one of its ancestors
        if position is None or owner in self.tree.below(position):
            # the owner is below the reader: a parent reads a child's parameter if exported
            return None if self.product.parameters[slug].export else WHY_UNEXPORTED
        return WHY_SIBLING

    # ---- what is checked --------------------------------------------------------------

    def expr_findings(self) -> list[Finding]:
        """Parameters named in parameter and interface expressions, checked statically."""
        out: list[Finding] = []
        if not self.active:
            return out
        for slug, p in sorted(self.product.parameters.items()):
            if not p.expr:
                continue
            pos = self.param_position(slug)
            for name in _names(p.expr):
                if name in self.product.parameters:
                    why = self.why_out_of_reach(pos, name)
                    if why:
                        out.append(
                            Finding(f"param://{slug}", pos, name, self.scoped[name], why, "expr")
                        )
        for iid, iface in sorted(self.product.interfaces.items()):
            parties = [str(x) for x in iface.parties if x.scheme == "part"]
            positions = [self.part_position(x) for x in parties] or [None]
            for name in iface.expression_slugs():
                if name not in self.product.parameters:
                    continue
                whys = [self.why_out_of_reach(pos, name) for pos in positions]
                if all(whys):  # an interface may name what either party may read
                    out.append(
                        Finding(
                            f"iface://{iid}",
                            positions[0],
                            name,
                            self.scoped[name],
                            str(whys[0]),
                            "expr",
                        )
                    )
        return out

    def read_findings(self, manifest: Manifest) -> list[Finding]:
        """Recorded reads of part and assembly rules, minus the reads through an interface."""
        out: list[Finding] = []
        if not self.active:
            return out
        for rid, entry in sorted(manifest.entries.items()):
            reader_pos = self._reader(rid)
            if reader_pos is None:
                continue
            reader, pos = reader_pos
            skip = set(entry.iface_reads)
            for key in entry.reads:
                if not key.startswith("param://") or key in skip:
                    continue
                slug = key.removeprefix("param://").split("#", 1)[0]
                if slug not in self.product.parameters:
                    continue
                why = self.why_out_of_reach(pos, slug)
                if why:
                    out.append(Finding(reader, pos, slug, self.scoped[slug], why, "build"))
        return out

    def _reader(self, rule_id: str) -> tuple[str, str | None] | None:
        kind, _, ident = rule_id.partition(":")
        if kind == "part" and ident in self.product.parts:
            return f"part://{ident}", self.part_position(f"part://{ident}")
        if kind == "asm" and ident in self.product.assemblies:
            return f"asm://{ident}", self.asm_position(ident)
        return None

    def readers_built(self, manifest: Manifest) -> dict[str | None, int]:
        """Module → how many of its part and assembly rules have recorded reads."""
        out: dict[str | None, int] = {}
        for rid in manifest.entries:
            reader_pos = self._reader(rid)
            if reader_pos is not None:
                out[reader_pos[1]] = out.get(reader_pos[1], 0) + 1
        return out


def _names(expr: str) -> list[str]:
    try:
        return referenced_names(expr)
    except ExprError:
        return []  # the loader reports the bad expression


def reach_fingerprint(product: Product, manifest: Manifest) -> str:
    """Everything the reach rows depend on, hashed: the checks rule records it (D5)."""
    params = {
        slug: [str(p.scope) if p.scope else None, p.export, sorted(_names(p.expr or ""))]
        for slug, p in sorted(product.parameters.items())
    }
    tree = {
        aid: [a.build, [c.uri for c in a.children]] for aid, a in sorted(product.assemblies.items())
    }
    ifaces = {
        iid: [[str(x) for x in i.parties], sorted(i.expression_slugs())]
        for iid, i in sorted(product.interfaces.items())
    }
    reads = {
        rid: [sorted(k for k in e.reads if k.startswith("param://")), sorted(e.iface_reads)]
        for rid, e in sorted(manifest.entries.items())
        if rid.partition(":")[0] in CHECKED_KINDS
    }
    return sha256_json({"params": params, "tree": tree, "ifaces": ifaces, "reads": reads})


# ---- check rows ---------------------------------------------------------------------------


def _module_words(product: Product, position: str | None) -> str:
    if position is None:
        return "the whole product"
    return f"the {product.assemblies[position].name}"


def _reader_words(product: Product, reach: Reach, f: Finding) -> str:
    scheme, _, ident = f.reader.partition("://")
    where = _module_words(product, f.position)
    if scheme == "part":
        return f"{product.parts[ident].name} (in {where}) reads"
    if scheme == "asm":
        return f"The placement of {product.assemblies[ident].name}'s parts reads"
    if scheme == "iface":
        return f"The joint {ident} names"
    return f"The size {ident} (of {where}) is computed from"


def finding_row(product: Product, reach: Reach, f: Finding) -> CheckResult:
    """One ``warn`` row in plain words; the rule id and the facts stay in ``--json``."""
    owner = product.assemblies[f.owner].name
    reader = _reader_words(product, reach, f)
    if f.why == WHY_SIBLING:
        where = _module_words(product, f.position)
        common = reach.tree.lowest_common([a for a in (f.position, f.owner) if a is not None])
        up = f"the {product.assemblies[common[0]].name}" if common else "the whole product"
        message = (
            f"{reader} {f.param}, a size of the {owner}; {where} and the {owner} sit side by "
            f"side and never read each other's sizes: move it up to {up}, or let a joint "
            "between them carry it"
        )
    else:
        message = (
            f"{reader} {f.param}, a size the {owner} keeps to itself: share it (mark it "
            "exported), or let a joint between them carry it"
        )
    kind, _, ident = f.reader.partition("://")
    return CheckResult(
        id=f"reach://{kind}/{ident}@{f.param}",
        subject=f.reader,
        status="warn",
        kind="reach",
        title=f"{f.param} read from outside its module",
        message=message,
        detail={
            "reader": f.reader,
            "param": f"param://{f.param}",
            "scope": f"asm://{f.owner}",
            "export": product.parameters[f.param].export,
            "why": f.why,
            "how": f.how,
            "reader_module": f"asm://{f.position}" if f.position else None,
        },
        module=f.position,
    )


def reach_checks(product: Product, manifest: Manifest) -> list[CheckResult]:
    """The reach rows: one ``warn`` per read out of reach, one row per module otherwise.

    Nothing at all when no parameter is scoped (P14).  A module none of whose rules has been
    built yet gets a ``skip`` row saying the reach check needs a build.
    """
    reach = Reach(product)
    if not reach.active:
        return []
    findings = _unique(reach.expr_findings() + reach.read_findings(manifest))
    rows = [finding_row(product, reach, f) for f in findings]
    flagged = {f.position for f in findings}
    built = reach.readers_built(manifest)
    for uid in reach.units.order():
        if uid in flagged:
            continue
        name = product.assemblies[uid].name
        n = built.get(uid, 0)
        rows.append(
            CheckResult(
                id=f"reach://{uid}",
                subject=f"asm://{uid}",
                status="pass" if n else "skip",
                kind="reach",
                title=f"{name}: sizes read within reach",
                message=(
                    f"{name}: its parts and their placement read only its own sizes, sizes "
                    f"above it and shared ones ({n} parts and placements checked)"
                    if n
                    else "the reads are recorded by a build: run `n2f build` first"
                ),
                module=uid,
            )
        )
    return rows


def _unique(findings: Iterable[Finding]) -> list[Finding]:
    seen: dict[tuple[str, str], Finding] = {}
    for f in findings:
        seen.setdefault((f.reader, f.param), f)
    return list(seen.values())
