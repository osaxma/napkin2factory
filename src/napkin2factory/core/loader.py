"""YAML → model, with cross-reference validation and actionable errors.

``load_product`` reads every file of a product repository (§3.2), validates each
against its schema, then runs each model family's ``validate_refs`` in a fixed order
(F15): every URI anywhere resolves, parts and interfaces agree about each other,
geometry modules exist, assemblies form a tree with the right ports, expressions
reference known parameters without cycles.  All problems are collected and reported
together; nothing stops at the first one.  The loaded ``Product`` lives in
``core/product.py``; this module re-exports it.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from napkin2factory.core.errors import ModelError, Problems
from napkin2factory.core.model import (
    DecisionsFile,
    DocMeta,
    Ecr,
    Manifest,
    Operator,
    ParametersFile,
    Part,
    RequirementsFile,
    Signoff,
)
from napkin2factory.core.model import assemblies as _assemblies
from napkin2factory.core.model import interfaces as _interfaces
from napkin2factory.core.model import parameters as _parameters
from napkin2factory.core.model import parts as _parts
from napkin2factory.core.model import signoff as _signoff
from napkin2factory.core.product import MANIFEST, Doc, Paths, Product, heading_anchor
from napkin2factory.core.uris import Uri
from napkin2factory.core.yamlio import read_yaml, split_front_matter

__all__ = [
    "MANIFEST",
    "Doc",
    "Paths",
    "Product",
    "find_product_root",
    "heading_anchor",
    "load_product",
    "validate",
]

#: Each core family's cross-reference check, in the order the loader runs them (F15).  The
#: order is the one the checks had inside the loader before the split, so ``n2f validate``
#: lists problems as before (S-131); domain families run after these, in registry order.
REF_CHECKS: tuple[Callable[[Product, Problems], None], ...] = (
    _interfaces.validate_refs,
    _parts.validate_refs,
    _assemblies.validate_refs,
    _parameters.validate_refs,
    _signoff.validate_refs,
)


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
    _load_list(product, problems, paths.requirements, RequirementsFile, "req", "requirement")
    _load_parameters(product, problems)
    _load_list(product, problems, paths.decisions, DecisionsFile, "dec", "decision")
    for files, model, scheme, table in (
        (paths.parts.glob("*.yaml"), Part, "part", product.parts),
        (paths.assemblies.glob("*.yaml"), _assemblies.Assembly, "asm", product.assemblies),
        (paths.interfaces.glob("*.yaml"), _interfaces.Interface, "iface", product.interfaces),
        (paths.changes.glob("ECR-*.yaml"), Ecr, "ecr", product.ecrs),
    ):
        _load_folder(product, problems, files, model, scheme, table)
    _load_signoffs(product, problems)
    _load_docs(product, problems)
    _load_calcs(product, problems)
    for fam in _domain_families():  # model families a domain registers (F1)
        objects: dict[str, Any] = {}
        _load_folder(
            product,
            problems,
            (product.root / fam.folder).glob("*.yaml"),
            fam.schema,
            fam.uri_scheme,
            objects,
        )
        product.families[fam.name] = objects
    _validate_uris(product, problems)
    for check in REF_CHECKS:
        check(product, problems)
    for fam in _domain_families():  # each family checks its own references (F15)
        if fam.validate_refs is not None:
            fam.validate_refs(product, problems)
    return product, problems


def _load_list(
    product: Product, problems: Problems, file: Path, model: type[Any], scheme: str, noun: str
) -> None:
    """``requirements.yaml`` or ``decisions.yaml``: a list of objects with unique ids."""
    if not file.is_file():
        return
    before = len(problems.errors)
    raw = _safe_read(problems, file)
    if len(problems.errors) > before:
        product.broken_schemes.add(scheme)
    key = f"{noun}s"
    loaded = _load_one(problems, file, file.name, model, raw)
    table: dict[str, Any] = product.requirements if scheme == "req" else product.decisions
    if loaded is None:
        for item in raw.get(key, []) or []:
            if isinstance(item, dict) and "id" in item:
                product.broken.add(f"{scheme}://{item['id']}")
        return
    for obj in getattr(loaded, key):
        if obj.id in table:
            problems.add(file, obj.id, f"duplicate {noun} id", "ids must be unique")
        table[obj.id] = obj


def _load_parameters(product: Product, problems: Problems) -> None:
    file = product.paths.parameters
    if not file.is_file():
        return
    before = len(problems.errors)
    raw = _safe_read(problems, file)
    if len(problems.errors) > before:
        product.broken_schemes.add("param")
    pf = _load_one(problems, file, "parameters.yaml", ParametersFile, raw)
    if pf is not None:
        product.parameters = dict(pf.parameters)
    else:
        for k in raw.get("parameters", {}) or {}:
            product.broken.add(f"param://{k}")


def _load_folder(
    product: Product,
    problems: Problems,
    files: Iterable[Path],
    model: type[Any],
    scheme: str,
    table: dict[str, Any],
) -> None:
    """One object per ``<id>.yaml``; the file name must be the id."""
    for f in sorted(files):
        obj = _load_one(problems, f, f.stem, model, _safe_read(problems, f), product, scheme)
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
        table[ident] = obj
        product.files[f"{scheme}://{ident}"] = f


def _load_signoffs(product: Product, problems: Problems) -> None:
    for f in sorted(product.paths.signoffs.glob("REQ-*.yaml")):
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


def _load_docs(product: Product, problems: Problems) -> None:
    for f in sorted(product.paths.docs.glob("*.md")):
        meta_raw, body = split_front_matter(f.read_text(encoding="utf-8"))
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


def _load_calcs(product: Product, problems: Problems) -> None:
    for f in sorted(product.paths.calcs.glob("*.py")):
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


def _domain_families() -> list[Any]:
    from napkin2factory.core.registry import registry

    return registry().model_families()


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


def _validate_uris(product: Product, problems: Problems) -> None:
    """Every URI anywhere resolves, with its selector and its doc anchor."""
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
