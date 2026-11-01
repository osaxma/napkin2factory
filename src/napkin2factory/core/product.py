"""The loaded product model, its file layout (``Paths``) and its manual pages (``Doc``).

``Product`` resolves URIs and evaluates parameters.

Split out of ``core/loader.py`` so the loader only orchestrates reading and validation
(F15, S-131); ``core.loader`` re-exports every name here, so importers need no change.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.core.expr import ExprError, evaluate
from napkin2factory.core.model import (
    Assembly,
    Decision,
    DocMeta,
    Ecr,
    Interface,
    Manifest,
    Operator,
    Parameter,
    Part,
    Requirement,
    Signoff,
)
from napkin2factory.core.units import Quantity, parse_quantity
from napkin2factory.core.uris import Uri, find_uris

MANIFEST = "n2f.yaml"


@dataclass
class Paths:
    """Where things live inside a product repository."""

    root: Path

    @property
    def manifest(self) -> Path:
        """``n2f.yaml``."""
        return self.root / MANIFEST

    @property
    def operator(self) -> Path:
        """``operator.yaml``."""
        return self.root / "operator.yaml"

    @property
    def model(self) -> Path:
        """``model/``."""
        return self.root / "model"

    @property
    def requirements(self) -> Path:
        """``model/requirements.yaml``."""
        return self.model / "requirements.yaml"

    @property
    def parameters(self) -> Path:
        """``model/parameters.yaml``."""
        return self.model / "parameters.yaml"

    @property
    def decisions(self) -> Path:
        """``model/decisions.yaml``."""
        return self.model / "decisions.yaml"

    @property
    def parts(self) -> Path:
        """``model/parts/``."""
        return self.model / "parts"

    @property
    def assemblies(self) -> Path:
        """``model/assemblies/``."""
        return self.model / "assemblies"

    @property
    def interfaces(self) -> Path:
        """``model/interfaces/``."""
        return self.model / "interfaces"

    @property
    def geometry(self) -> Path:
        """``model/geometry/``."""
        return self.model / "geometry"

    @property
    def calcs(self) -> Path:
        """``model/calcs/``."""
        return self.model / "calcs"

    @property
    def docs(self) -> Path:
        """``model/docs/``."""
        return self.model / "docs"

    @property
    def signoffs(self) -> Path:
        """``model/signoffs/``."""
        return self.model / "signoffs"

    @property
    def changes(self) -> Path:
        """``changes/``."""
        return self.root / "changes"

    @property
    def reports(self) -> Path:
        """``reports/``."""
        return self.root / "reports"

    @property
    def build(self) -> Path:
        """``build/`` (gitignored)."""
        return self.root / "build"

    @property
    def changelog(self) -> Path:
        """``CHANGELOG.md``."""
        return self.root / "CHANGELOG.md"


@dataclass
class Doc:
    """A manual page: front matter plus the templated Markdown body."""

    meta: DocMeta
    body: str
    path: Path

    @property
    def uri(self) -> str:
        """``doc://<id>``."""
        return f"doc://{self.meta.id}"

    @property
    def anchors(self) -> list[str]:
        """Heading slugs usable as ``doc://id#anchor``."""
        out: list[str] = []
        for line in self.body.splitlines():
            m = re.match(r"^#{1,6}\s+(.*)$", line)
            if m:
                out.append(heading_anchor(m.group(1)))
        return out


def heading_anchor(title: str) -> str:
    """Slugify a heading the way the HTML renderer does (``Power & wiring`` → ``power-wiring``)."""
    title = re.sub(r"\{\{.*?\}\}", "", title)
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s or "section"


@dataclass
class Product:
    """The fully loaded product model."""

    paths: Paths
    manifest: Manifest
    operator: Operator
    requirements: dict[str, Requirement] = field(default_factory=dict)
    parameters: dict[str, Parameter] = field(default_factory=dict)
    decisions: dict[str, Decision] = field(default_factory=dict)
    parts: dict[str, Part] = field(default_factory=dict)
    assemblies: dict[str, Assembly] = field(default_factory=dict)
    interfaces: dict[str, Interface] = field(default_factory=dict)
    ecrs: dict[str, Ecr] = field(default_factory=dict)
    signoffs: dict[str, Signoff] = field(default_factory=dict)
    docs: dict[str, Doc] = field(default_factory=dict)
    calcs: dict[str, list[str]] = field(default_factory=dict)  # module → functions
    files: dict[str, Path] = field(default_factory=dict)  # uri string → source file
    broken: set[str] = field(default_factory=set)  # base URIs whose file failed schema validation
    broken_schemes: set[str] = field(default_factory=set)  # whole files that did not parse
    #: Objects of the model families domains register (F1): family name → id → object.
    families: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def root(self) -> Path:
        """Repository root."""
        return self.paths.root

    @property
    def id(self) -> str:
        """Product id from the manifest."""
        return self.manifest.product.id

    # ---- resolution -------------------------------------------------------

    def exists(self, u: Uri | str) -> bool:
        """True if the base URI names something in the model."""
        try:
            self.resolve(u)
        except KeyError:
            return False
        return True

    def resolve(self, u: Uri | str) -> Any:
        """Return the object a base URI names; ``KeyError`` with a hint otherwise."""
        uri = Uri.parse(u) if isinstance(u, str) else u
        table: dict[str, dict[str, Any]] = {
            "req": self.requirements,
            "param": self.parameters,
            "part": self.parts,
            "asm": self.assemblies,
            "iface": self.interfaces,
            "dec": self.decisions,
            "ecr": self.ecrs,
            "doc": self.docs,
            # n2f.yaml's own fields (S-133, B-0091): a decision may link the scope it set
            "manifest": {"product": self.manifest.product, "scope": self.manifest.scope},
        }
        from napkin2factory.core.registry import registry

        for fam in registry().model_families():  # a domain's family answers to its scheme (F1)
            table.setdefault(fam.uri_scheme, self.families.get(fam.name, {}))
        if str(uri.base) in self.broken or uri.scheme in self.broken_schemes:
            return None  # the file exists but did not load; its own error is already reported
        if uri.scheme == "calc":
            mod, fn = uri.id.split(".", 1)
            if fn not in self.calcs.get(mod, []):
                raise KeyError(f"{uri} does not exist: no function {fn} in model/calcs/{mod}.py")
            return (mod, fn)
        if uri.scheme == "bom":
            return f"bom://{uri.id}"  # rollups, validation, build-plan (core/uris.py, S-117)
        if uri.scheme == "rule":
            return uri.id  # rule packs are validated by the rule runner
        if uri.id not in table[uri.scheme]:
            raise KeyError(
                f"{uri.base} does not exist; known {uri.scheme} ids: "
                f"{sorted(table[uri.scheme]) or 'none'}"
            )
        return table[uri.scheme][uri.id]

    def select(self, u: Uri | str) -> Any:
        """Resolve a URI with a selector against *declared* fields (not build props).

        Returns the field value, or raises ``KeyError`` if the path does not exist.
        Computed selectors (``#props.*``, ``bom://…#…``) are not available here; the
        checks layer resolves those against build artifacts.
        """
        uri = Uri.parse(u) if isinstance(u, str) else u
        obj = self.resolve(uri)
        if not uri.selector or obj is None:
            return obj
        cur: Any = obj
        for i, key in enumerate(uri.selector):
            if key == "props" and i == 0:
                raise KeyError(f"{uri}: #props.* is computed by the build, not declared")
            if isinstance(cur, dict):
                if key not in cur:
                    raise KeyError(f"{uri}: no key {key!r}")
                cur = cur[key]
            elif hasattr(cur, key):
                cur = getattr(cur, key)
            else:
                raise KeyError(f"{uri}: {type(cur).__name__} has no field {key!r}")
            if cur is None and i < len(uri.selector) - 1:
                raise KeyError(f"{uri}: {key!r} is empty")
        return cur

    # ---- parameters -------------------------------------------------------

    def parameter_value(self, slug: str, _stack: tuple[str, ...] = ()) -> Any:
        """Quantity for a parameter, evaluating expressions (cycle-safe)."""
        if slug in _stack:
            raise ExprError(f"parameter cycle: {' -> '.join((*_stack, slug))}")
        p = self.parameters[slug]
        if p.expr is None:
            return parse_quantity(p.value if p.value is not None else 0, p.unit or None)
        return self.expr_value(
            p.expr,
            p.unit,
            lookup=lambda s: self.parameter_value(s, (*_stack, slug)),
            where=f"param://{slug}",
        )

    def expr_value(
        self,
        expr: str,
        unit: str,
        lookup: Callable[[str], Any] | None = None,
        where: str = "expression",
    ) -> Any:
        """Evaluate ``expr`` over parameter slugs and express it in ``unit``.

        The one evaluation path for parameter ``expr`` fields and interface frame
        expressions (P2), so both share the grammar and the unit handling.  ``lookup`` (slug →
        value) lets the caller record each read; by default parameters are read directly.

        Raises:
            ExprError: on bad syntax, an unknown slug or a result not expressible in ``unit``.
        """
        val = evaluate(expr, {}, lookup=lookup or self._lookup_known)
        if unit:
            try:
                return val.to(unit) if hasattr(val, "to") else Quantity(val, unit)
            except Exception as exc:
                raise ExprError(
                    f"{where}: expression result cannot be expressed in {unit}: {exc}"
                ) from exc
        return val

    def _lookup_known(self, slug: str) -> Any:
        if slug not in self.parameters:
            raise ExprError(f"unknown parameter {slug!r}; add it to parameters.yaml")
        return self.parameter_value(slug)

    def resolved_parameters(self) -> dict[str, Any]:
        """Every parameter as a quantity."""
        return {k: self.parameter_value(k) for k in self.parameters}

    # ---- iteration helpers ------------------------------------------------

    def custom_parts(self) -> Iterator[Part]:
        """Parts with ``kind: custom``."""
        return (p for p in self.parts.values() if p.kind == "custom")

    def parts_with_geometry(self) -> Iterator[Part]:
        """Parts that produce 3D output."""
        return (p for p in self.parts.values() if p.has_geometry)

    def safety_requirements(self) -> Iterator[Requirement]:
        """Requirements flagged ``safety: true``."""
        return (r for r in self.requirements.values() if r.safety)

    def all_uris(self) -> list[tuple[Uri, Path, str]]:
        """Every URI referenced anywhere, with the file and subject it appears in."""
        out: list[tuple[Uri, Path, str]] = []

        def walk(obj: Any, file: Path, subject: str) -> None:
            if isinstance(obj, Uri):
                out.append((obj, file, subject))
            elif isinstance(obj, str):
                for u in find_uris(obj):
                    out.append((u, file, subject))
            elif isinstance(obj, dict):
                for v in obj.values():
                    walk(v, file, subject)
            elif isinstance(obj, (list, tuple)):
                for v in obj:
                    walk(v, file, subject)
            elif hasattr(obj, "model_fields"):
                for name in type(obj).model_fields:
                    walk(getattr(obj, name), file, subject)

        for r in self.requirements.values():
            walk(r, self.paths.requirements, r.id)
        for d in self.decisions.values():
            walk(d, self.paths.decisions, d.id)
        for p in self.parts.values():
            walk(p, self.files[p.uri], p.uri)
        for a in self.assemblies.values():
            walk(a, self.files[a.uri], a.uri)
        for i in self.interfaces.values():
            walk(i, self.files[i.uri], i.uri)
        for e in self.ecrs.values():
            walk(e, self.files[e.uri], e.uri)
        for s in self.signoffs.values():
            walk(s, self.files[f"signoff:{s.requirement.id}"], f"signoff {s.requirement.id}")
        for doc in self.docs.values():
            walk(doc.meta, doc.path, doc.uri)
        return out
