"""The domain contract (FOUNDATION F1): the types a domain fills in to register what it brings.

A domain is a Python package exposing one object, ``DOMAIN = Domain(...)``.  Everything it
adds to the system is declared there: model families, build rule families, verify kinds,
check stages, gate rows, report sections, doc helpers, vocabulary, interface kinds,
processes, finishes, requirement categories, build-unit drivers, style roles, napkin screens
and context contributions.  :mod:`napkin2factory.core.registry` holds one registry per
kind; the core reads the registries and never imports a domain by name.  ``docs/domains.md`` is the
contract's documentation, with the toy domain (``tests/fixtures/domains/toy/``) as its
worked example.

This module imports nothing from the rest of the core at run time, so a domain package (and
the registry, which the schemas consult) can be imported from anywhere without a cycle; the
signatures name core types under ``TYPE_CHECKING`` only.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from napkin2factory.core.checks.evaluators import EvalContext
    from napkin2factory.core.checks.results import CheckResult
    from napkin2factory.core.errors import Problems
    from napkin2factory.core.graph.rules import Rule, RuleBuild
    from napkin2factory.core.loader import Product
    from napkin2factory.core.model.requirements import Requirement


def lazy(target: str) -> Callable[..., Any]:
    """A callable that imports ``"package.module:function"`` on its first call.

    The mechanical domain registers functions that live in the core and the geometry,
    drawing and report packages (F2: in place); importing them when the domain is declared
    would import the whole system before the schemas are ready.  ``lazy`` defers it.
    """
    module_name, _, attr = target.partition(":")
    cache: list[Callable[..., Any]] = []

    def call(*args: Any, **kwargs: Any) -> Any:
        if not cache:
            cache.append(getattr(importlib.import_module(module_name), attr))
        return cache[0](*args, **kwargs)

    call.__name__ = attr
    call.__qualname__ = attr
    call.__doc__ = f"Deferred {target} (core.domain.lazy)."
    return call


@dataclass(frozen=True)
class ModelFamily:
    """A kind of model file the domain adds: ``<folder>/*.yaml``, one object per file.

    Each file is validated with ``schema`` (a pydantic model with an ``id`` field matching
    the file name) and stored in ``product.families[name]``; the objects are addressable as
    ``<scheme>://<id>`` (``scheme`` defaults to the family name).  ``validate_refs(product,
    problems)`` runs after the core's own cross-checks and adds a problem for each broken
    reference it finds.
    """

    name: str
    schema: type[Any]
    folder: str
    validate_refs: Callable[[Product, Problems], None] | None = None
    scheme: str = ""
    id_pattern: str = r"[a-z0-9]+(?:-[a-z0-9]+)*"

    @property
    def uri_scheme(self) -> str:
        """The URI scheme its objects answer to."""
        return self.scheme or self.name


@dataclass(frozen=True)
class RuleFamily:
    """A kind of build rule (F3): ``make_rules`` returns this family's rules for a product.

    ``after`` names the families whose rules must run first; the build walks the families in
    dependency order (ties by installation order).  ``produces`` is the URI scheme (``<scheme>://``)
    or rule key its rules produce, so a downstream read resolves to their output hash, and
    ``also_produces`` lists further keys (S-117).  A ``reads_all`` family (checks, report,
    site) runs after every family that is not itself ``reads_all``.

    ``code`` lists the folders of the domain's package (relative to :attr:`Domain.root`)
    whose files are the family's code: :meth:`Registry.family_hash` hashes them, and a rule
    whose ``inputs`` carry no ``code`` gets that hash, so a change to the domain's code
    rebuilds its rules and nothing else.  Empty: the whole package.

    ``targets`` are ``n2f build --target`` names that end at this family (the family's own
    name is always one); ``output_dir`` is the folder under ``build/`` its rules write one
    subfolder per id into (removed when the rule disappears).  ``static_reads(product, rule)``
    is the conservative read set ``n2f impact`` assumes before the first build.
    """

    name: str
    make_rules: Callable[[RuleBuild], list[Rule]]
    after: tuple[str, ...] = ()
    produces: str = ""
    also_produces: tuple[str, ...] = ()
    code: tuple[str, ...] = ()
    reads_all: bool = False
    targets: tuple[str, ...] = ()
    output_dir: str | None = None
    static_reads: Callable[[Product, Rule], list[str]] | None = None


@dataclass(frozen=True)
class VerifyKind:
    """A ``verify.kind`` a requirement may name (F3, F14).

    ``evaluate(ctx, req, res, evidence)`` returns the computed verdict (``pass``, ``fail``,
    ``warn``, ``skip``, or ``None`` when a person must decide), sets ``res.message`` (and
    ``res.detail`` if it has more to say) and fills ``evidence`` with the keys a sign-off
    is held against.  The schema reads the rest: ``target_schemes`` (empty: the kind takes
    no target), ``compares`` (it needs ``op`` and ``value``), ``binary`` (a requirement's
    statement need not carry a number, lint L1) and ``check`` (extra rules on the
    ``verify`` block; raise ``ValueError`` with the fix).  ``hypothetical`` answers
    ``n2f impact``'s "would it pass" when it can (``(verdict, detail)``), else impact says
    the verdict is known after the rebuild.
    """

    name: str
    evaluate: Callable[[EvalContext, Requirement, CheckResult, dict[str, str]], str | None]
    target_schemes: tuple[str, ...] = ()
    compares: bool = False
    binary: bool = False
    title: str = ""
    check: Callable[[Any], None] | None = None
    hypothetical: Callable[..., tuple[str, str]] | None = None


@dataclass
class StageContext:
    """What a check stage sees: the product, the build folder and this check run's state.

    ``ectx`` is the requirement evaluators' context (stages that requirements read leave
    their reports there, e.g. ``ectx.interfaces``); ``keep(home)`` says whether a row whose
    module is ``home`` belongs to this run (``n2f check --scope``); ``within`` is the scoped
    assembly id or ``None`` for the whole product; ``modules`` is the row-to-module mapper.
    ``proxy(obj, uri)`` reads a model object so that each field used is recorded in ``log``.
    """

    product: Product
    build_dir: Path
    ectx: EvalContext
    keep: Callable[[str | None], bool]
    within: str | None
    modules: Any
    log: Any = field(default_factory=lambda: _read_log())

    def proxy(self, obj: Any, uri: str) -> Any:
        """``obj`` (named ``uri``) through the recording accessor: each field read is a read.

        The reads join the ``checks`` rule's, so a change to a field a stage used reruns the
        checks (D5, gate E B2).
        """
        return _recorded(obj, uri, self.log)


def _read_log() -> Any:
    from napkin2factory.geometry.accessors import ReadLog

    return ReadLog()


def _recorded(obj: Any, uri: str, log: Any) -> Any:
    from napkin2factory.core.graph.recording import Recorded

    return Recorded(obj, uri, log)


@dataclass(frozen=True)
class CheckStage:
    """A step of ``n2f check`` that returns rows (F3).

    ``run(sctx)`` returns :class:`~napkin2factory.core.checks.results.CheckResult` rows.
    Stages run in dependency order (``after``), ties by installation order.
    ``whole_product`` stages (documents, sourcing) are left out of a module's checks.
    Read the model through ``sctx.proxy`` and each field used is a recorded read of the
    ``checks`` rule; ``reads(product)`` names further keys the rows depend on (a rule's
    output, say), added to the same reads, so a change behind them re-runs the checks.
    """

    name: str
    run: Callable[[StageContext], list[CheckResult]]
    after: tuple[str, ...] = ()
    whole_product: bool = False
    reads: Callable[[Product], list[str]] | None = None


@dataclass
class GateRowState:
    """One domain row under a gate: a one-line summary plus what blocks or holds the gate."""

    summary: str
    blockers: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GateRow:
    """A domain's row under the Design or Verify gate (F4): the ladder stays the core's.

    ``row(product, build_dir)`` returns a :class:`GateRowState`, or ``None`` when the domain
    has no content in the product (an empty domain shows nothing).  Its blockers join the
    gate's; ``n2f status`` prints ``<title>: <summary>`` under the gate.
    """

    gate: str
    title: str
    row: Callable[[Product, Path], GateRowState | None]


@dataclass
class SectionContext:
    """What a report section's ``data`` sees: the product, the build folder and a read log.

    ``proxy(obj, uri)`` reads a model object so that each field used is recorded in ``log``;
    the reads join the ``report`` rule's, so a change to a field the section shows reruns
    the report (D5, gate E B2).
    """

    product: Product
    build_dir: Path
    log: Any = field(default_factory=lambda: _read_log())

    def proxy(self, obj: Any, uri: str) -> Any:
        """``obj`` (named ``uri``) through the recording accessor."""
        return _recorded(obj, uri, self.log)


@dataclass(frozen=True)
class ReportSection:
    """A section of the report page (F5): a Jinja fragment plus the data it renders.

    ``fragment`` is the template file, relative to :attr:`Domain.root`.  It renders inside
    the page with the page's context (``badge``, ``h2``, ``w``, ``ref`` …) plus ``data``,
    the dict ``data(sctx)`` returns (``sctx``: a :class:`SectionContext`; read the model
    through ``sctx.proxy`` and each field shown is a recorded read).  A section goes at the
    end of its ``group`` in the side index.  ``reads(product)`` names further keys it shows
    (a rule's output, say), added to the report rule's recorded reads.  ``show(product)``
    false leaves it off the page.
    """

    id: str
    label: str
    group: str
    fragment: str
    data: Callable[[SectionContext], dict[str, Any]] | None = None
    reads: Callable[[Product], list[str]] | None = None
    show: Callable[[Product], bool] | None = None


@dataclass
class HelperContext:
    """What a doc helper factory sees while one manual page renders (D5, F5).

    ``log`` records reads (``log.add(key)``); ``proxy(obj, uri)`` wraps a model object so
    every attribute read is recorded as ``<uri>#<path>``; ``error(msg)`` builds the page's
    render error; ``rollups`` and ``plan`` are the bom rule's outputs when built.
    """

    product: Product
    doc: Any
    log: Any
    rollups: dict[str, Any] | None
    plan: dict[str, Any] | None
    proxy: Callable[[Any, str], Any]
    error: Callable[[str], Exception]
    state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InterfaceKind:
    """An interface ``kind`` (F6) a domain adds.

    ``spec`` validates its ``spec:`` block (a pydantic model);
    ``check(product, iface, build_dir)`` returns its interface check report (a dict with
    ``status`` and ``message``) or the joint is reported as not checked.
    """

    name: str
    title: str = ""
    spec: type[Any] | None = None
    check: Callable[[Product, Any, Path], dict[str, Any]] | None = None


@dataclass(frozen=True)
class Process:
    """A manufacturing process (F6); ``declared`` false means "not decided yet" (``none``)."""

    id: str
    title: str
    declared: bool = True


#: The napkin-stage phases a screen may run in, in order (``concepts/screens/base.py`` says
#: what each is for): ``measure`` and ``total`` are the system's own steps, a domain's or a
#: product's screen takes ``estimate`` (its numbers feed the totals) or ``check``.
SCREEN_PHASES: tuple[str, ...] = ("measure", "estimate", "total", "check")


@dataclass(frozen=True)
class Screen:
    """A napkin-stage screen (F8, F10).

    ``run(card, massing, values)`` adds labelled numbers through ``values``
    (``values.computed.add(...)``, ``values.estimate``, ``values.given``, ``values.notes``)
    and returns concept rule rows.  ``fields`` are the card fields it reads
    (:class:`~napkin2factory.concepts.screens.CardField`: section, key, kind of number,
    example, the owner's words), from which ``n2f concept new`` writes a card's skeleton
    and ``n2f concept lint`` checks a card; ``phase`` is when it runs (one of
    :data:`SCREEN_PHASES`).  Left empty, both come from a ``reads`` decorator on ``run``
    when it has one, else the screen reads no declared field and runs in ``check``.
    """

    name: str
    run: Callable[..., list[Any]]
    title: str = ""
    fields: tuple[Any, ...] = ()
    phase: str = ""

    def __post_init__(self) -> None:
        """An unknown phase is an error naming the known ones."""
        if self.phase and self.phase not in SCREEN_PHASES:
            raise ValueError(
                f"screen {self.name!r}: unknown phase {self.phase!r}; "
                f"known: {', '.join(SCREEN_PHASES)}"
            )


@dataclass(frozen=True)
class StyleRoleSpec:
    """A styling role a domain adds to ``core/data/style_roles.yaml`` (F6).

    ``id`` is the word a part's or a rough shape's ``role:`` and ``style.yaml``'s
    ``palette``/``finish`` keys use; ``words`` say it for the owner; ``styled`` roles take
    the style's shape cues when a part names one (the opt-in rule, N7); ``aliases`` are
    other words read as this role.  A role without a colour in the style's preset takes the
    ``default`` role's.
    """

    id: str
    words: str
    styled: bool = False
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextContribution:
    """What a domain adds to ``n2f context asm://<id>`` (F1, v0.4 P6).

    ``collect(product, aid, members)`` returns Markdown lines for the module ``aid`` (its
    members are the assembly and the phantoms folded into it), or an empty list when the
    domain has nothing there; the context prints them under ``## <title>``.
    """

    name: str
    title: str
    collect: Callable[[Product, str, list[str]], list[str]]


@dataclass(frozen=True)
class Domain:
    """Everything one domain brings (F1). Only ``name`` is required.

    ``root`` is the package folder (``Path(__file__).parent`` in the domain's
    ``__init__.py``); every relative path the domain gives (``code``, ``fragment``) is
    relative to it.  ``code`` lists the folders hashed as the domain's code (empty: all of
    ``root``).  ``in_place`` is for the mechanical domain only (F2): its code lives in the
    system package and each of its families already hashes its own folders, so its
    registrations add no ``domain:`` input to the rules that read them.
    """

    name: str
    root: Path = field(default_factory=Path)
    title: str = ""
    families: tuple[ModelFamily, ...] = ()
    rule_families: tuple[RuleFamily, ...] = ()
    verify_kinds: tuple[VerifyKind, ...] = ()
    check_stages: tuple[CheckStage, ...] = ()
    gate_rows: tuple[GateRow, ...] = ()
    report_sections: tuple[ReportSection, ...] = ()
    doc_helpers: dict[str, Callable[[HelperContext], Any]] = field(default_factory=dict)
    vocabulary: dict[str, dict[str, str]] = field(default_factory=dict)
    interface_kinds: tuple[InterfaceKind, ...] = ()
    processes: tuple[Process, ...] = ()
    finishes: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    drivers: dict[str, str] = field(default_factory=dict)
    style_roles: tuple[StyleRoleSpec, ...] = ()
    screens: tuple[Screen, ...] = ()
    context: tuple[ContextContribution, ...] = ()
    code: tuple[str, ...] = ()
    in_place: bool = False
