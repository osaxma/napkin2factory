"""One registry per kind of thing a domain brings (FOUNDATION F1, F3, F6).

The installed domains are listed, in order, in :data:`napkin2factory.domains.INSTALLED`;
the first lookup imports each and registers its ``DOMAIN``.  Tests (and the toy domain)
add one with :func:`register` and take it away with :func:`unregister`, or for one block
with ``with installed(domain): ...``.

Every view iterates in a stable order: installation order, then the order a domain
declares things in (rule families and check stages in dependency order).  Every lookup of
an unknown name raises :class:`UnknownName`, whose message lists the known values (DoD 7).
The open sets of F6 (processes, finishes, interface kinds, requirement categories,
build-unit drivers, style roles) are the tables in ``core/data/*.yaml`` plus the domains'
additions.

The core never imports a domain by name: it reads these views.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from napkin2factory.core.domain import (
    CheckStage,
    ContextContribution,
    Domain,
    GateRow,
    InterfaceKind,
    ModelFamily,
    Process,
    ReportSection,
    RuleFamily,
    Screen,
    StyleRoleSpec,
    VerifyKind,
)

DATA = Path(__file__).resolve().parent / "data"
SYSTEM_ROOT = Path(__file__).resolve().parents[1]  # src/napkin2factory
#: The gates a domain may add rows to (F4): the ladder itself is the core's.
ROW_GATES: tuple[str, ...] = ("design", "verify")
#: Suffixes hashed as a domain's code (the same set as a system package's, S-031).
CODE_SUFFIXES: tuple[str, ...] = (".py", ".js", ".html", ".css", ".yaml", ".j2")


class UnknownName(ValueError, LookupError):
    """A registry lookup missed; the message names the known values.

    A ``ValueError`` so a schema validator that looks a value up reports it as a validation
    problem of the file, with the known values as the fix.
    """


def unknown(kind: str, name: str, known: list[str] | tuple[str, ...]) -> UnknownName:
    """The error for an unknown ``name`` of ``kind``: "unknown process 'x'; known: a, b"."""
    shown = ", ".join(known) if known else "none installed"
    return UnknownName(f"unknown {kind} {name!r}; known: {shown}")


def _table(name: str) -> list[dict[str, Any]]:
    from napkin2factory.core.yamlio import read_yaml

    data = read_yaml(DATA / f"{name}.yaml")
    return list(data) if isinstance(data, list) else []


def _ordered(items: list[tuple[int, str, tuple[str, ...]]], what: str) -> list[int]:
    """Dependency order over ``(index, name, after)``; ties by index (installation order).

    A name in ``after`` that no item has is ignored (the family it waits for is simply not
    installed); a cycle is an error naming the items in it.
    """
    names = {name for _, name, _ in items}
    waiting = {i: {a for a in after if a in names and a != name} for i, name, after in items}
    by_name: dict[str, list[int]] = {}
    for i, name, _ in items:
        by_name.setdefault(name, []).append(i)
    done: set[str] = set()
    out: list[int] = []
    left = [i for i, _, _ in items]
    name_of = {i: name for i, name, _ in items}
    while left:
        ready = [i for i in left if waiting[i] <= done]
        if not ready:
            raise ValueError(
                f"the {what} wait for each other: " + ", ".join(sorted({name_of[i] for i in left}))
            )
        first = min(ready)
        out.append(first)
        left.remove(first)
        if all(j in out for j in by_name[name_of[first]]):
            done.add(name_of[first])
    return out


#: Registry kind → the names a domain registers in it (for :meth:`Registry.owner`).
_OWNED: dict[str, Callable[[Domain], list[str]]] = {
    "rule family": lambda d: [f.name for f in d.rule_families],
    "verify kind": lambda d: [v.name for v in d.verify_kinds],
    "check stage": lambda d: [s.name for s in d.check_stages],
    "report section": lambda d: [s.id for s in d.report_sections],
    "doc helper": lambda d: list(d.doc_helpers),
    "model family": lambda d: [f.name for f in d.families],
}


@dataclass
class Registry:
    """The registered domains and every view over them (see the module docstring)."""

    domains: list[Domain] = field(default_factory=list)
    _loaded: bool = False

    # ---- installation ------------------------------------------------------------------

    def ensure(self) -> None:
        """Register the installed domains (``domains/__init__.py``) on first use."""
        if self._loaded:
            return
        self._loaded = True
        from napkin2factory.domains import INSTALLED

        for module_name in INSTALLED:
            module = importlib.import_module(module_name)
            self.register(module.DOMAIN)

    def register(self, domain: Domain) -> None:
        """Add ``domain`` after the ones registered; a second domain of a name is an error."""
        self.ensure()
        if any(d.name == domain.name for d in self.domains):
            raise ValueError(f"a domain named {domain.name!r} is already registered")
        self.domains.append(domain)
        self._check_unique()
        _apply_schemes(self)

    def unregister(self, name: str) -> None:
        """Remove the domain called ``name``."""
        self.ensure()
        if not any(d.name == name for d in self.domains):
            raise unknown("domain", name, [d.name for d in self.domains])
        self.domains = [d for d in self.domains if d.name != name]
        _apply_schemes(self)

    def _check_unique(self) -> None:
        """Two domains must not register the same name in one registry (the second would hide)."""
        seen: dict[tuple[str, str], str] = {}
        for d in self.domains:
            pairs = (
                [("rule family", f.name) for f in d.rule_families]
                + [("verify kind", v.name) for v in d.verify_kinds]
                + [("check stage", s.name) for s in d.check_stages]
                + [("report section", s.id) for s in d.report_sections]
                + [("doc helper", h) for h in d.doc_helpers]
                + [("model family", f.name) for f in d.families]
                + [("screen", s.name) for s in d.screens]
            )
            for pair in pairs:
                if pair in seen and seen[pair] != d.name:
                    self.domains.remove(d)
                    raise ValueError(
                        f"domain {d.name!r} registers {pair[0]} {pair[1]!r}, which domain "
                        f"{seen[pair]!r} already registers"
                    )
                seen[pair] = d.name

    def domain(self, name: str) -> Domain:
        """The registered domain called ``name``."""
        self.ensure()
        for d in self.domains:
            if d.name == name:
                return d
        raise unknown("domain", name, [d.name for d in self.domains])

    # ---- code hashes (S-031, F3) ---------------------------------------------------------

    def domain_hash(self, domain: Domain) -> str:
        """Hash of the domain's code: its ``code`` folders (or its whole root)."""
        return _tree_hash(str(domain.root), domain.code)

    def family_hash(self, family: RuleFamily) -> str:
        """Hash of a rule family's code, from the package of the domain that registered it.

        For the mechanical domain (``root`` is the system package) this is exactly the
        subtree hash its rules used before the registry (``package_hash(*code)``), so
        registering in place moves no rule key (F2, FOUNDATION §7 risk 1).
        """
        domain = self.owner("rule family", family.name)
        if domain.in_place:
            return package_hash(*family.code)
        return _tree_hash(str(domain.root), family.code or domain.code)

    def contributors(self, *kinds: str) -> list[Domain]:
        """Domains (not in place) that register any of ``kinds`` (:class:`Domain` field names).

        Their code hash is an input of the rules that read those registries (gate E: every
        registry is hashed into the rules that depend on it).
        """
        self.ensure()
        return [d for d in self.domains if not d.in_place and any(getattr(d, k) for k in kinds)]

    def domain_inputs(self, *kinds: str) -> dict[str, str]:
        """``{"domain:<name>": hash}`` for each contributor of ``kinds`` (empty for mechanical)."""
        return {f"domain:{d.name}": self.domain_hash(d) for d in self.contributors(*kinds)}

    def owner(self, kind: str, name: str) -> Domain:
        """The domain that registered the ``kind`` called ``name``."""
        self.ensure()
        table = _OWNED[kind]
        for d in self.domains:
            if name in table(d):
                return d
        raise unknown(kind, name, [n for d in self.domains for n in table(d)])

    # ---- build rule families (F3) -------------------------------------------------------

    def rule_families(self) -> list[RuleFamily]:
        """Every rule family in build order.

        Producers in dependency order, then the ``reads_all`` families (checks, report,
        site) in theirs.
        """
        self.ensure()
        fams = [f for d in self.domains for f in d.rule_families]
        producers = [f for f in fams if not f.reads_all]
        consumers = [f for f in fams if f.reads_all]
        out: list[RuleFamily] = []
        for group in (producers, consumers):
            order = _ordered([(i, f.name, f.after) for i, f in enumerate(group)], "rule families")
            out += [group[i] for i in order]
        return out

    def rule_family(self, name: str) -> RuleFamily:
        """The rule family called ``name``."""
        for f in self.rule_families():
            if f.name == name:
                return f
        raise unknown("rule family", name, [f.name for f in self.rule_families()])

    def target_kinds(self) -> dict[str, tuple[str, ...]]:
        """``--target`` name → the rule kinds it runs, cumulative in dependency order.

        Each family is a target (itself and everything it waits for, transitively; a
        ``reads_all`` family waits for every producer); a family's ``targets`` are aliases
        of its own (``geometry`` is ``asm``'s, S-031's names kept); ``all`` runs every family.
        """
        fams = self.rule_families()
        by_name = {f.name: f for f in fams}
        order = [f.name for f in fams]
        producers = [f.name for f in fams if not f.reads_all]

        def closure(name: str) -> set[str]:
            need: set[str] = set()
            todo = [name]
            while todo:
                cur = todo.pop()
                if cur in need or cur not in by_name:
                    continue
                need.add(cur)
                todo += list(by_name[cur].after)
                if by_name[cur].reads_all:
                    todo += producers
            return need

        out: dict[str, tuple[str, ...]] = {}
        for f in fams:
            kinds = closure(f.name)
            ordered = tuple(n for n in order if n in kinds)
            for alias in f.targets:
                out[alias] = ordered
            out.setdefault(f.name, ordered)
        out["all"] = tuple(order)
        return out

    def produced_scheme(self, scheme: str) -> RuleFamily | None:
        """The rule family whose rules produce ``<scheme>://<id>`` (rule id ``<family>:<id>``)."""
        for f in self.rule_families():
            if f.produces == f"{scheme}://":
                return f
        return None

    # ---- verify kinds, check stages, gate rows (F3, F4) ------------------------------------

    def verify_kinds(self) -> dict[str, VerifyKind]:
        """Every verify kind by name, in installation order."""
        self.ensure()
        return {v.name: v for d in self.domains for v in d.verify_kinds}

    def verify_kind(self, name: str) -> VerifyKind:
        """The verify kind called ``name``; unknown: an error listing the installed ones."""
        kinds = self.verify_kinds()
        if name not in kinds:
            raise unknown("verify kind", name, list(kinds))
        return kinds[name]

    def check_stages(self) -> list[CheckStage]:
        """Every check stage in run order (dependency order, ties by installation order)."""
        self.ensure()
        stages = [s for d in self.domains for s in d.check_stages]
        order = _ordered([(i, s.name, s.after) for i, s in enumerate(stages)], "check stages")
        return [stages[i] for i in order]

    def check_stage(self, name: str) -> CheckStage:
        """The check stage called ``name``."""
        for s in self.check_stages():
            if s.name == name:
                return s
        raise unknown("check stage", name, [s.name for s in self.check_stages()])

    def gate_rows(self, gate: str | None = None) -> list[GateRow]:
        """The gate rows (of one gate when ``gate`` is given), in installation order."""
        self.ensure()
        if gate is not None and gate not in ROW_GATES:
            raise unknown("gate", gate, ROW_GATES)
        return [r for d in self.domains for r in d.gate_rows if gate is None or r.gate == gate]

    # ---- report sections, doc helpers, vocabulary, context (F5, F1) --------------------------

    def report_sections(self) -> list[ReportSection]:
        """The report's sections in page order.

        The first domain's in its order; a later domain's each go at the end of their group.
        """
        self.ensure()
        out: list[ReportSection] = []
        for d in self.domains:
            if not out:  # the first domain's sections set the page's order
                out += d.report_sections
                continue
            for s in d.report_sections:
                last = max((i for i, x in enumerate(out) if x.group == s.group), default=None)
                if last is None:
                    out.append(s)
                else:
                    out.insert(last + 1, s)
        return out

    def report_section(self, sid: str) -> ReportSection:
        """The report section with anchor ``sid``."""
        for s in self.report_sections():
            if s.id == sid:
                return s
        raise unknown("report section", sid, [s.id for s in self.report_sections()])

    def fragment_path(self, section: ReportSection) -> Path:
        """The template file of a section (relative paths are the owning domain's)."""
        domain = self.owner("report section", section.id)
        return Path(domain.root) / section.fragment

    def doc_helpers(self) -> dict[str, Any]:
        """Doc helper name → factory, in installation order."""
        self.ensure()
        return {name: f for d in self.domains for name, f in d.doc_helpers.items()}

    def doc_helper(self, name: str) -> Any:
        """The doc helper factory called ``name``."""
        helpers = self.doc_helpers()
        if name not in helpers:
            raise unknown("doc helper", name, list(helpers))
        return helpers[name]

    def vocabulary(self, persona: str) -> dict[str, str]:
        """Term → the words ``persona`` reads (later domains do not override earlier ones)."""
        self.ensure()
        out: dict[str, str] = {}
        for d in self.domains:
            for term, words in d.vocabulary.get(persona, {}).items():
                out.setdefault(term, words)
        return out

    def context_contributions(self) -> list[ContextContribution]:
        """What domains add to a module's context, in installation order."""
        self.ensure()
        return [c for d in self.domains for c in d.context]

    def model_families(self) -> list[ModelFamily]:
        """The model families domains add, in installation order."""
        self.ensure()
        return [f for d in self.domains for f in d.families]

    def model_family(self, name: str) -> ModelFamily:
        """The model family called ``name``."""
        for f in self.model_families():
            if f.name == name:
                return f
        raise unknown("model family", name, [f.name for f in self.model_families()])

    def screens(self) -> list[Screen]:
        """Napkin-stage screens domains add, in installation order."""
        self.ensure()
        return [s for d in self.domains for s in d.screens]

    # ---- the open sets of F6: core/data tables plus the domains' additions --------------------

    def interface_kinds(self) -> dict[str, InterfaceKind]:
        """Interface kind → its declaration (the table's, then the domains')."""
        self.ensure()
        out = {
            row["id"]: InterfaceKind(row["id"], row.get("title", ""))
            for row in _table("interface_kinds")
        }
        for d in self.domains:
            for k in d.interface_kinds:
                out.setdefault(k.name, k)
        return out

    def interface_kind(self, name: str) -> InterfaceKind:
        """The interface kind called ``name``."""
        kinds = self.interface_kinds()
        if name not in kinds:
            raise unknown("interface kind", name, list(kinds))
        return kinds[name]

    def processes(self) -> dict[str, Process]:
        """Process id → its declaration."""
        self.ensure()
        out = {
            row["id"]: Process(row["id"], row.get("title", ""), bool(row.get("declared", True)))
            for row in _table("processes")
        }
        for d in self.domains:
            for p in d.processes:
                out.setdefault(p.id, p)
        return out

    def finishes(self) -> dict[str, dict[str, float]]:
        """Finish → its rendering factors (a domain's finish renders with neutral ones)."""
        self.ensure()
        out = {
            row["id"]: {"metallic": float(row["metallic"]), "roughness": float(row["roughness"])}
            for row in _table("finishes")
        }
        for d in self.domains:
            for f in d.finishes:
                out.setdefault(f, {"metallic": 0.0, "roughness": 0.5})
        return out

    def categories(self) -> tuple[str, ...]:
        """Requirement categories."""
        self.ensure()
        out = [row["id"] for row in _table("requirement_categories")]
        for d in self.domains:
            out += [c for c in d.categories if c not in out]
        return tuple(out)

    def style_roles(self) -> dict[str, StyleRoleSpec]:
        """Style role → its declaration: the table's, then the domains' (F6).

        The table is ``core/data/style_roles.yaml``; a later domain never replaces an
        earlier role of the same id.
        """
        self.ensure()
        out = {
            str(row["id"]): StyleRoleSpec(
                str(row["id"]),
                str(row["words"]),
                bool(row.get("styled", False)),
                tuple(str(a) for a in row.get("aliases") or ()),
            )
            for row in _style_roles_table()
        }
        for d in self.domains:
            for r in d.style_roles:
                out.setdefault(r.id, r)
        return out

    def drivers(self) -> dict[str, str]:
        """Build-unit driver → its owner words (v0.4 P7)."""
        self.ensure()
        out = {row["id"]: row["words"] for row in _table("drivers")}
        for d in self.domains:
            for k, words in d.drivers.items():
                out.setdefault(k, words)
        return out


@lru_cache(maxsize=1)
def _style_roles_table() -> tuple[dict[str, Any], ...]:
    """``core/data/style_roles.yaml``, read once: every part's role is looked up in it."""
    return tuple(_table("style_roles"))


@lru_cache(maxsize=64)
def _tree_hash(root: str, subdirs: tuple[str, ...]) -> str:
    from napkin2factory.core.graph.hashing import sha256_text, sha256_tree

    folders = subdirs or (".",)
    parts = {d: sha256_tree(Path(root) / d, CODE_SUFFIXES) for d in folders}
    return sha256_text("\n".join(f"{k}={v}" for k, v in sorted(parts.items())))


@lru_cache(maxsize=32)
def package_hash(*subdirs: str) -> str:
    """Hash of the system package trees a rule's code lives in (gate-1 B6, S-031)."""
    from napkin2factory import __version__
    from napkin2factory.core.graph.hashing import sha256_text, sha256_tree

    parts = {d: sha256_tree(SYSTEM_ROOT / d, CODE_SUFFIXES) for d in subdirs}
    parts["version"] = __version__
    return sha256_text("\n".join(f"{k}={v}" for k, v in sorted(parts.items())))


def _apply_schemes(reg: Registry) -> None:
    """Tell the URI grammar about the domains' model-family schemes and owner words."""
    from napkin2factory.core import uris

    schemes = {f.uri_scheme: f.id_pattern for f in reg.model_families()}
    uris.set_domain_schemes(schemes, reg.vocabulary("owner"))


#: The process-wide registry.
REGISTRY = Registry()


def registry() -> Registry:
    """The registry with the installed domains registered."""
    REGISTRY.ensure()
    return REGISTRY


def register(domain: Domain) -> None:
    """Register ``domain`` after the installed ones (see :meth:`Registry.register`)."""
    REGISTRY.register(domain)


def unregister(name: str) -> None:
    """Remove the domain called ``name``."""
    REGISTRY.unregister(name)


@contextmanager
def installed(domain: Domain) -> Iterator[Domain]:
    """Register ``domain`` for the length of a ``with`` block (tests, simulations)."""
    register(domain)
    try:
        yield domain
    finally:
        unregister(domain.name)


def check_known(kind: str, value: str, known: list[str] | tuple[str, ...]) -> str:
    """Return ``value`` when it is in ``known``; else the error listing them (F6 tables)."""
    if value not in known:
        raise unknown(kind, value, list(known))
    return value
