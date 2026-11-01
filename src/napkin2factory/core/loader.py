"""YAML → model, with cross-reference validation and actionable errors.

``load_product`` reads every file of a product repository (§3.2), validates each
against its schema, then checks that every URI anywhere resolves, that parts and
interfaces agree about each other, that assembly children exist, that geometry
modules exist, that expressions reference known parameters without cycles, and
that calc targets name a function that exists.  All problems are collected and
reported together; nothing stops at the first one.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from napkin2factory.core.errors import ModelError, Problems
from napkin2factory.core.expr import ExprError, check_syntax, evaluate, referenced_names
from napkin2factory.core.model import (
    Assembly,
    Decision,
    DecisionsFile,
    DocMeta,
    Ecr,
    Interface,
    KitGeometry,
    Manifest,
    ModuleGeometry,
    Operator,
    Parameter,
    ParametersFile,
    Part,
    Requirement,
    RequirementsFile,
    Signoff,
)
from napkin2factory.core.tree import AssemblyTree
from napkin2factory.core.units import Quantity, UnitError, parse_quantity
from napkin2factory.core.uris import Uri, find_uris, slug_to_module
from napkin2factory.core.yamlio import read_yaml, split_front_matter

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


# ---------------------------------------------------------------------------


def find_product_root(start: Path | None = None) -> Path | None:
    """Walk up from ``start`` (cwd) to the nearest directory holding ``n2f.yaml``."""
    cur = (start or Path.cwd()).resolve()
    for p in (cur, *cur.parents):
        if (p / MANIFEST).is_file():
            return p
    return None


def _validation_problems(
    problems: Problems, file: Path, subject: str, exc: ValidationError
) -> None:
    for err in exc.errors():
        loc = ".".join(str(x) for x in err["loc"]) or "(top level)"
        msg = err["msg"]
        hint = ""
        if err["type"] == "extra_forbidden":
            hint = f"remove or rename the key {loc!r}; see docs/product-model.md for the schema"
        elif err["type"] == "missing":
            hint = f"add the required key {loc!r}"
        problems.add(file, subject, f"{loc}: {msg}", hint, rule="schema")


def _load_one(
    problems: Problems,
    file: Path,
    subject: str,
    model: type[Any],
    data: Any,
    product: Product | None = None,
    scheme: str | None = None,
) -> Any | None:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        _validation_problems(problems, file, subject, exc)
        if product is not None and scheme is not None:
            ident = data.get("id", file.stem) if isinstance(data, dict) else file.stem
            product.broken.add(f"{scheme}://{ident}")
        return None


def load_product(root: Path, strict: bool = True) -> Product:
    """Load and validate a product repository.

    Args:
        root: directory holding ``n2f.yaml``.
        strict: raise :class:`ModelError` on problems (otherwise return what loaded
            and leave problems on ``product.problems``... callers use :func:`validate`).
    """
    product, problems = _load(root)
    if strict:
        problems.raise_if_any()
    return product


def validate(root: Path) -> tuple[Product | None, Problems]:
    """Load without raising; returns the product (possibly partial) and all problems."""
    try:
        product, problems = _load(root)
    except ModelError as exc:
        return None, exc.problems
    return product, problems


def _load(root: Path) -> tuple[Product, Problems]:
    paths = Paths(Path(root).resolve())
    problems = Problems()
    if not paths.manifest.is_file():
        problems.add(
            paths.manifest,
            "n2f.yaml",
            "this folder is not a napkin2factory product",
            "run `n2f init <dir>` to start one, or cd into a product folder",
        )
        raise ModelError(problems, "not a product folder")
    from napkin2factory.core.model.migrate import refuse_unreadable

    refuse_unreadable(paths.manifest, problems)  # F7: a newer or not-yet-updated schema stops
    manifest = _load_one(
        problems, paths.manifest, "n2f.yaml", Manifest, _safe_read(problems, paths.manifest)
    )
    operator = (
        _load_one(
            problems,
            paths.operator,
            "operator.yaml",
            Operator,
            _safe_read(problems, paths.operator),
        )
        if paths.operator.is_file()
        else Operator()
    )
    if manifest is None:
        raise ModelError(problems, "n2f.yaml is invalid")
    product = Product(paths=paths, manifest=manifest, operator=operator or Operator())

    # requirements
    if paths.requirements.is_file():
        before = len(problems.errors)
        raw = _safe_read(problems, paths.requirements)
        if len(problems.errors) > before:
            product.broken_schemes.add("req")
        rf = _load_one(problems, paths.requirements, "requirements.yaml", RequirementsFile, raw)
        if rf is None:
            for item in raw.get("requirements", []) or []:
                if isinstance(item, dict) and "id" in item:
                    product.broken.add(f"req://{item['id']}")
        else:
            for r in rf.requirements:
                if r.id in product.requirements:
                    problems.add(
                        paths.requirements, r.id, "duplicate requirement id", "ids must be unique"
                    )
                product.requirements[r.id] = r
    # parameters
    if paths.parameters.is_file():
        before = len(problems.errors)
        raw = _safe_read(problems, paths.parameters)
        if len(problems.errors) > before:
            product.broken_schemes.add("param")
        pf = _load_one(problems, paths.parameters, "parameters.yaml", ParametersFile, raw)
        if pf is not None:
            product.parameters = dict(pf.parameters)
        else:
            for k in raw.get("parameters", {}) or {}:
                product.broken.add(f"param://{k}")
    # decisions
    if paths.decisions.is_file():
        before = len(problems.errors)
        raw = _safe_read(problems, paths.decisions)
        if len(problems.errors) > before:
            product.broken_schemes.add("dec")
        df = _load_one(problems, paths.decisions, "decisions.yaml", DecisionsFile, raw)
        if df is None:
            for item in raw.get("decisions", []) or []:
                if isinstance(item, dict) and "id" in item:
                    product.broken.add(f"dec://{item['id']}")
        else:
            for d in df.decisions:
                if d.id in product.decisions:
                    problems.add(
                        paths.decisions, d.id, "duplicate decision id", "ids must be unique"
                    )
                product.decisions[d.id] = d
    # parts / assemblies / interfaces / changes / signoffs
    for f in sorted(paths.parts.glob("*.yaml")):
        part = _load_one(problems, f, f.stem, Part, _safe_read(problems, f), product, "part")
        if part is None:
            continue
        if part.id != f.stem:
            problems.add(
                f,
                part.id,
                f"file name {f.name} does not match id {part.id!r}",
                f"rename the file to {part.id}.yaml",
            )
        product.parts[part.id] = part
        product.files[part.uri] = f
    for f in sorted(paths.assemblies.glob("*.yaml")):
        asm = _load_one(problems, f, f.stem, Assembly, _safe_read(problems, f), product, "asm")
        if asm is None:
            continue
        if asm.id != f.stem:
            problems.add(
                f,
                asm.id,
                f"file name {f.name} does not match id {asm.id!r}",
                f"rename the file to {asm.id}.yaml",
            )
        product.assemblies[asm.id] = asm
        product.files[asm.uri] = f
    for f in sorted(paths.interfaces.glob("*.yaml")):
        iface = _load_one(problems, f, f.stem, Interface, _safe_read(problems, f), product, "iface")
        if iface is None:
            continue
        if iface.id != f.stem:
            problems.add(
                f,
                iface.id,
                f"file name {f.name} does not match id {iface.id!r}",
                f"rename the file to {iface.id}.yaml",
            )
        product.interfaces[iface.id] = iface
        product.files[iface.uri] = f
    for f in sorted(paths.changes.glob("ECR-*.yaml")):
        ecr = _load_one(problems, f, f.stem, Ecr, _safe_read(problems, f), product, "ecr")
        if ecr is None:
            continue
        if ecr.id != f.stem:
            problems.add(
                f,
                ecr.id,
                f"file name {f.name} does not match id {ecr.id!r}",
                f"rename the file to {ecr.id}.yaml",
            )
        product.ecrs[ecr.id] = ecr
        product.files[ecr.uri] = f
    for f in sorted(paths.signoffs.glob("REQ-*.yaml")):
        so = _load_one(problems, f, f.stem, Signoff, _safe_read(problems, f))
        if so is None:
            continue
        if so.requirement.id != f.stem:
            problems.add(
                f,
                f.stem,
                f"file name {f.name} does not match requirement {so.requirement}",
                f"rename the file to {so.requirement.id}.yaml",
            )
        product.signoffs[so.requirement.id] = so
        product.files[f"signoff:{so.requirement.id}"] = f
    for f in sorted(paths.docs.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        meta_raw, body = split_front_matter(text)
        if not meta_raw:
            problems.add(
                f,
                f.stem,
                "manual page has no front matter",
                "start the file with ---\\nid: …\\ntitle: …\\n---",
            )
            continue
        meta = _load_one(problems, f, f.stem, DocMeta, meta_raw)
        if meta is None:
            continue
        if meta.id != f.stem:
            problems.add(
                f,
                meta.id,
                f"file name {f.name} does not match id {meta.id!r}",
                f"rename the file to {meta.id}.md",
            )
        product.docs[meta.id] = Doc(meta=meta, body=body, path=f)
    for f in sorted(paths.calcs.glob("*.py")):
        if f.name.startswith("test_") or f.name == "__init__.py":
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            problems.add(
                f,
                f.stem,
                f"calc module does not parse: {exc.msg} (line {exc.lineno})",
                "fix the Python syntax",
            )
            continue
        product.calcs[f.stem] = [
            n.name
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
        ]

    _load_domain_families(product, problems)
    _cross_validate(product, problems)
    for fam in _domain_families():  # each family checks its own references (F15)
        if fam.validate_refs is not None:
            fam.validate_refs(product, problems)
    return product, problems


def _domain_families() -> list[Any]:
    from napkin2factory.core.registry import registry

    return registry().model_families()


def _load_domain_families(product: Product, problems: Problems) -> None:
    """Load ``<folder>/*.yaml`` of every model family a domain registers (F1)."""
    for fam in _domain_families():
        objects: dict[str, Any] = {}
        for f in sorted((product.root / fam.folder).glob("*.yaml")):
            obj = _load_one(
                problems, f, f.stem, fam.schema, _safe_read(problems, f), product, fam.uri_scheme
            )
            if obj is None:
                continue
            ident = getattr(obj, "id", f.stem)
            if ident != f.stem:
                problems.add(
                    f,
                    ident,
                    f"file name {f.name} does not match id {ident!r}",
                    f"rename the file to {ident}.yaml",
                )
            objects[ident] = obj
            product.files[f"{fam.uri_scheme}://{ident}"] = f
        product.families[fam.name] = objects


def _safe_read(problems: Problems, file: Path) -> Any:
    try:
        data = read_yaml(file)
    except Exception as exc:
        problems.add(
            file,
            file.name,
            f"YAML does not parse: {exc}",
            "fix the YAML syntax (indentation, quotes)",
        )
        return {}
    if not isinstance(data, dict):
        problems.add(
            file,
            file.name,
            "expected a mapping at the top level",
            "the file should start with keys like `id:`",
        )
        return {}
    return data


def _cross_validate(product: Product, problems: Problems) -> None:  # noqa: C901
    paths = product.paths
    # Every URI resolves.
    for uri, file, subject in product.all_uris():
        try:
            product.resolve(uri)
        except KeyError as exc:
            problems.add(file, subject, str(exc), _hint_for(uri), rule="uri")
            continue
        if uri.selector and uri.selector[0] != "props" and uri.scheme not in ("bom", "doc"):
            try:
                product.select(uri)
            except KeyError as exc:
                problems.add(file, subject, str(exc), "check the field path after '#'", rule="uri")
        if uri.scheme == "doc" and uri.selector:
            doc = product.docs[uri.id]
            anchor = ".".join(uri.selector)
            if anchor not in doc.anchors:
                problems.add(
                    file,
                    subject,
                    f"{uri}: no heading with anchor {anchor!r} in {doc.path.name}",
                    f"available anchors: {', '.join(doc.anchors) or 'none'}",
                    rule="uri",
                )
    # Parts ↔ interfaces agree.
    for part in product.parts.values():
        for iu in part.interfaces:
            iface = product.interfaces.get(iu.id)
            if iface and all(pp.id != part.id for pp in iface.parties):
                problems.add(
                    product.files[part.uri],
                    part.uri,
                    f"lists {iu} but that interface's parties are "
                    f"{[str(p) for p in iface.parties]}",
                    f"add part://{part.id} to the interface's parties or remove it here",
                    rule="interface",
                )
    for iface in product.interfaces.values():
        for party in iface.parties:
            if party.scheme == "part":
                party_part = product.parts.get(party.id)
                if party_part and all(i.id != iface.id for i in party_part.interfaces):
                    problems.add(
                        product.files[iface.uri],
                        iface.uri,
                        f"names {party} as a party but that part does not list iface://{iface.id}",
                        f"add iface://{iface.id} to the part's `interfaces:`",
                        rule="interface",
                    )
        if iface.kind == "bolt-pattern":
            spec = iface.spec
            fastener = getattr(spec, "fastener", None)
            if fastener is not None and fastener.id not in product.parts:
                problems.add(
                    product.files[iface.uri],
                    iface.uri,
                    f"fastener {fastener} is not a part",
                    "add the fastener as a COTS part",
                    rule="interface",
                )
    # Geometry modules exist; kit names are known.
    from napkin2factory.geometry.kit import GENERATORS

    for part in product.parts.values():
        g = part.geometry
        if isinstance(g, KitGeometry) and g.kit not in GENERATORS:
            problems.add(
                product.files[part.uri],
                part.uri,
                f"unknown kit generator {g.kit!r}",
                f"use one of: {', '.join(GENERATORS)}",
                rule="geometry",
            )
        if isinstance(g, ModuleGeometry):
            mod = paths.model / g.module
            if not mod.is_file():
                problems.add(
                    product.files[part.uri],
                    part.uri,
                    f"geometry module {g.module} not found",
                    f"create model/{g.module} exposing build(P, I, kit), or use a kit generator",
                    rule="geometry",
                )
        elif part.kind == "custom" and g == "none":
            problems.add(
                product.files[part.uri],
                part.uri,
                "custom part has no geometry",
                "add geometry: {kit: …} or {module: geometry/<id>.py}",
                severity="warn",
                rule="geometry",
            )
    for asm in product.assemblies.values():
        ag = asm.geometry
        if isinstance(ag, ModuleGeometry):
            mod = paths.model / ag.module
            if not mod.is_file():
                problems.add(
                    product.files[asm.uri],
                    asm.uri,
                    f"geometry module {ag.module} not found",
                    f"create model/{ag.module} exposing build(P, I, parts)",
                    rule="geometry",
                )
        expected = paths.geometry / f"{slug_to_module(asm.id)}.py"
        if ag == "none" and expected.is_file():
            problems.add(
                product.files[asm.uri],
                asm.uri,
                f"{expected.name} exists but geometry is 'none'",
                "set geometry: {module: geometry/%s}" % expected.name,
                severity="warn",
                rule="geometry",
            )
    # Assembly graph is acyclic.
    for asm in product.assemblies.values():
        _check_asm_cycle(product, asm, (), problems)
    _validate_ports(product, problems)
    _validate_parameter_scopes(product, problems)
    # Parameter expressions. Static faults (unsafe syntax, unknown names, bad units) mark
    # the parameter as bad; evaluation then runs whenever parameters.yaml parsed, whatever
    # errors other files have (S-012 keeps hiding only what depends on a broken target).
    bad: set[str] = set()
    for slug, p in product.parameters.items():
        if p.expr:
            try:
                check_syntax(p.expr)
            except ExprError as exc:
                bad.add(slug)
                problems.add(
                    paths.parameters,
                    f"param://{slug}",
                    str(exc),
                    "only arithmetic over parameter names is allowed",
                    rule="expr",
                )
                continue
            for name in referenced_names(p.expr):
                if name not in product.parameters:
                    bad.add(slug)
                    problems.add(
                        paths.parameters,
                        f"param://{slug}",
                        f"expression references unknown parameter {name!r}",
                        "add it to parameters.yaml or fix the spelling",
                        rule="expr",
                    )
        if p.unit:
            try:
                parse_quantity(1, p.unit)
            except UnitError as exc:
                bad.add(slug)
                problems.add(
                    paths.parameters,
                    f"param://{slug}",
                    str(exc),
                    "use a pint unit like mm, kg, degC, USD, d",
                    rule="units",
                )
    if "param" not in product.broken_schemes:
        for slug in product.parameters:
            if _reaches_bad_parameter(product, slug, bad):
                continue
            try:
                product.parameter_value(slug)
            except (ExprError, UnitError) as exc:
                problems.add(
                    paths.parameters,
                    f"param://{slug}",
                    str(exc),
                    "fix the expression or its unit",
                    rule="expr",
                )
    _validate_interface_expressions(product, problems, bad)
    # Signoffs point at requirements that exist (already via URI) and keys match evidence.
    for so in product.signoffs.values():
        missing = [str(e) for e in so.evidence if str(e) not in so.evidence_keys]
        if missing and so.evidence_keys:
            problems.add(
                product.files[f"signoff:{so.requirement.id}"],
                f"signoff {so.requirement.id}",
                f"evidence without a recorded key: {missing}",
                "re-run `n2f signoff` so keys are recorded",
                severity="warn",
                rule="signoff",
            )
    # Product id vs directory is informational only.


def _validate_interface_expressions(product: Product, problems: Problems, bad: set[str]) -> None:
    """Frame coordinates and offsets written as ``{expr, unit}`` name known parameters (P2).

    An unknown slug is an error naming the interface file and the slug; an expression whose
    result does not fit its unit is reported like a parameter's.  Expressions that read a
    parameter already reported as bad are not evaluated (cascade suppression, S-009).
    """
    for iface in product.interfaces.values():
        file = product.files[iface.uri]
        for e in iface.expressions():
            unknown = [s for s in e.slugs if s not in product.parameters]
            for name in unknown:
                problems.add(
                    file,
                    iface.uri,
                    f"expression {e.expr!r} references unknown parameter {name!r}",
                    "add it to parameters.yaml or fix the spelling",
                    rule="expr",
                )
            if unknown or "param" in product.broken_schemes:
                continue
            if any(_reaches_bad_parameter(product, s, bad) for s in e.slugs):
                continue
            try:
                product.expr_value(e.expr, e.unit, where=iface.uri)
            except (ExprError, UnitError) as exc:
                problems.add(
                    file, iface.uri, str(exc), "fix the expression or its unit", rule="expr"
                )


def _reaches_bad_parameter(product: Product, slug: str, bad: set[str]) -> bool:
    """True when ``slug`` is, or transitively reads, a parameter already reported as bad.

    Evaluating such a parameter would only repeat the first error in other words, so it is
    skipped (cascade suppression). Cycles among good parameters are left for evaluation to
    report.
    """
    seen: set[str] = set()
    todo = [slug]
    while todo:
        cur = todo.pop()
        if cur in seen:
            continue
        seen.add(cur)
        if cur in bad or cur not in product.parameters:
            return True
        expr = product.parameters[cur].expr
        if expr:
            todo.extend(referenced_names(expr))
    return False


def _validate_ports(product: Product, problems: Problems) -> None:
    """Interfaces join parts; a joint crossing a sub-assembly is one of its ports (P4).

    An ``asm://`` party is refused (closes B-0005): the holes live on the part that carries
    them, and the assembly lists the joint under ``ports:``.  For a joint between two parts
    with different homes (P5), every assembly from each home up to, not including, the
    lowest assembly containing both must list it; listing a joint that does not cross the
    assembly's boundary is an error too.  Skipped when an assembly file did not load, since
    the tree would be incomplete (cascade suppression, S-009).
    """
    from napkin2factory.core.model import assemblies

    # F11, S-124: a stub for work done elsewhere has ports, no parts; its own rules check it
    stubs = assemblies.validate_refs(product, problems)
    refused: set[str] = set()  # interfaces with an asm:// party: their port rules wait (C1)
    for iface in product.interfaces.values():
        for party in iface.parties:
            if party.scheme == "asm" and party.id not in stubs:
                refused.add(iface.uri)
                problems.add(
                    product.files[iface.uri],
                    iface.uri,
                    f"names {party} as a party, but an interface joins two parts",
                    f"name the part inside {party} that carries the joint, and list "
                    f"{iface.uri} under `ports:` in model/assemblies/{party.id}.yaml",
                    rule="port",
                )
    if any(u.startswith("asm://") for u in product.broken):
        return
    tree = AssemblyTree(product.assemblies)
    needed: dict[str, dict[str, tuple[str, str]]] = {}  # asm id -> iface uri -> (in, out)
    for iface in product.interfaces.values():
        a, b = (str(p) for p in iface.parties)
        if not (a.startswith("part://") and b.startswith("part://")):
            continue
        for aid in tree.port_crossings(a, b):
            a_in = tree.home(a) in tree.below(aid)
            needed.setdefault(aid, {})[iface.uri] = (a, b) if a_in else (b, a)
    for aid, asm in sorted(product.assemblies.items()):
        if aid in stubs:
            continue
        file = product.files[asm.uri]
        listed = {str(u) for u in asm.ports}
        for iuri, (inside, outside) in sorted(needed.get(aid, {}).items()):
            if iuri not in listed:
                problems.add(
                    file,
                    asm.uri,
                    f"{iuri} joins {inside}, inside this assembly, to {outside}, outside it, "
                    "but is not listed under `ports:`",
                    f"add {iuri} to `ports:` in model/assemblies/{aid}.yaml: a joint that "
                    "crosses an assembly's boundary is one of its ports",
                    rule="port",
                )
        for iuri in sorted(listed - set(needed.get(aid, {}))):
            iid = iuri.removeprefix("iface://")
            if iid not in product.interfaces:
                continue  # the unresolved reference is already reported
            if iuri in refused:
                # gate C, C1: the party error already says to list it here; "remove it"
                # would contradict it in the same run (S-117)
                continue
            problems.add(
                file,
                asm.uri,
                f"lists {iuri} under `ports:`, but that joint does not cross this assembly's "
                f"boundary ({_port_where(tree, aid, product.interfaces[iid])})",
                f"remove {iuri} from `ports:` in model/assemblies/{aid}.yaml",
                rule="port",
            )


def _validate_parameter_scopes(product: Product, problems: Problems) -> None:
    """A parameter's ``scope`` names an existing assembly that is built as a unit (P5, M4).

    A phantom only groups lines and folds into its parent's build step (P7), so it is not a
    module of its own and owns no parameters: the hint names the unit it folds into.
    ``export`` on an unscoped parameter changes nothing and is a warning.  Whether rules and
    expressions stay within reach is a check, not a validation error (``core/reach.py``).
    """
    if not product.parameters or any(u.startswith("asm://") for u in product.broken):
        return
    tree = AssemblyTree(product.assemblies)
    tops = set(tree.tops())
    for slug, p in sorted(product.parameters.items()):
        subject = f"param://{slug}"
        if p.scope is None:
            if p.export:
                problems.add(
                    product.paths.parameters,
                    subject,
                    "is marked `export: true` but has no `scope:`; an unscoped parameter is "
                    "the whole product's already",
                    "add `scope: asm://<id>` or remove `export`",
                    severity="warn",
                    rule="scope",
                )
            continue
        aid = p.scope.id
        if aid not in product.assemblies:
            problems.add(
                product.paths.parameters,
                subject,
                f"`scope: {p.scope}` names no assembly; known: "
                f"{', '.join(sorted(product.assemblies)) or 'none'}",
                "scope it to an assembly in model/assemblies/, or remove `scope:`",
                rule="scope",
            )
            continue
        if aid not in tops and product.assemblies[aid].build == "phantom":
            parents = sorted(
                a.id
                for a in product.assemblies.values()
                if any(c.asm is not None and c.asm.id == aid for c in a.children)
            )
            problems.add(
                product.paths.parameters,
                subject,
                f"`scope: {p.scope}` names a phantom, a grouping that is not built on its own "
                "and owns no parameters",
                f"scope it to {', '.join(f'asm://{x}' for x in parents) or 'its parent'}, the "
                "unit it is built in, or remove `scope:`",
                rule="scope",
            )


def _port_where(tree: AssemblyTree, aid: str, iface: Interface) -> str:
    """Why a listed port is not one: in plain words, where its parties are."""
    a, b = (str(p) for p in iface.parties)
    if not (a.startswith("part://") and b.startswith("part://")):
        return "it does not join two parts"
    inside = [p for p in (a, b) if p in tree.parts_under(aid)]
    if len(inside) == 2:
        return "both parts are inside it"
    if not inside:
        return "neither part is inside it"
    return f"{inside[0]} is also used outside it"


def _check_asm_cycle(
    product: Product, asm: Assembly, stack: tuple[str, ...], problems: Problems
) -> None:
    if asm.id in stack:
        problems.add(
            product.files[asm.uri],
            asm.uri,
            f"assembly cycle: {' -> '.join((*stack, asm.id))}",
            "an assembly cannot contain itself",
            rule="assembly",
        )
        return
    for child in asm.children:
        if child.asm is not None and child.asm.id in product.assemblies:
            _check_asm_cycle(product, product.assemblies[child.asm.id], (*stack, asm.id), problems)


def _hint_for(uri: Uri) -> str:
    where = {
        "req": "model/requirements.yaml",
        "param": "model/parameters.yaml",
        "part": f"model/parts/{uri.id}.yaml",
        "asm": f"model/assemblies/{uri.id}.yaml",
        "iface": f"model/interfaces/{uri.id}.yaml",
        "dec": "model/decisions.yaml",
        "ecr": f"changes/{uri.id}.yaml",
        "doc": f"model/docs/{uri.id}.md",
        "calc": f"model/calcs/{uri.id.split('.')[0]}.py",
    }.get(uri.scheme, "the model")
    return f"define it in {where} or fix the reference"
