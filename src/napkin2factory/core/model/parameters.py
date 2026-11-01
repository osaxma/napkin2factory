"""parameters.yaml schema."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field, SerializerFunctionWrapHandler, model_serializer, model_validator

from napkin2factory.core.model.assemblies import _drop_defaults
from napkin2factory.core.model.base import AsmUri, Model, Slug

if TYPE_CHECKING:
    from napkin2factory.core.errors import Problems
    from napkin2factory.core.loader import Product


class Parameter(Model):
    """A named value with a unit, or an expression over other parameters.

    ``scope`` and ``export`` (P5) say which module a parameter belongs to: a parameter scoped to
    ``asm://door`` is the door's; the door, the assemblies inside it, and its ancestors' rules
    may read it only as the reach check allows (``core/reach.py``), and its parent reads it
    only when it is exported.  Unscoped parameters are the whole product's, as before (P14).
    """

    value: float | int | None = None
    expr: str | None = None
    unit: str = ""
    description: str | None = None
    owner: str | None = None
    min: float | int | None = None
    max: float | int | None = None
    scope: AsmUri | None = None
    export: bool = False

    @model_serializer(mode="wrap")
    def _dump(self, handler: SerializerFunctionWrapHandler) -> Any:
        # P14: the v0.4 fields are left out at their defaults, so a v0.3 record dumps as before
        return _drop_defaults(handler(self), {"scope": None, "export": False})

    @model_validator(mode="after")
    def _value_xor_expr(self) -> Parameter:
        if (self.value is None) == (self.expr is None):
            raise ValueError("a parameter has exactly one of 'value' or 'expr'")
        return self


class ParametersFile(Model):
    """Top level of ``model/parameters.yaml``."""

    parameters: dict[Slug, Parameter] = Field(default_factory=dict)

    def raw(self) -> dict[str, Any]:
        """Slug → declared value/expr, for impact tooling."""
        return {k: v.model_dump() for k, v in self.parameters.items()}


def validate_refs(product: Product, problems: Problems) -> None:
    """Scopes name built units; every expression over parameters reads known ones (F15).

    Covers the parameters' own expressions and the interfaces' frame expressions (P2), which
    share one evaluation path.  Static faults (unsafe syntax, unknown names, bad units) mark
    the parameter as bad; evaluation then runs whenever parameters.yaml parsed, whatever
    errors other files have (S-012 keeps hiding only what depends on a broken target).
    """
    from napkin2factory.core.expr import ExprError, check_syntax, referenced_names
    from napkin2factory.core.units import UnitError, parse_quantity

    _validate_scopes(product, problems)
    paths = product.paths
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


def _validate_interface_expressions(product: Product, problems: Problems, bad: set[str]) -> None:
    """Frame coordinates and offsets written as ``{expr, unit}`` name known parameters (P2).

    An unknown slug is an error naming the interface file and the slug; an expression whose
    result does not fit its unit is reported like a parameter's.  Expressions that read a
    parameter already reported as bad are not evaluated (cascade suppression, S-009).
    """
    from napkin2factory.core.expr import ExprError
    from napkin2factory.core.units import UnitError

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
    from napkin2factory.core.expr import referenced_names

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


def _validate_scopes(product: Product, problems: Problems) -> None:
    """A parameter's ``scope`` names an existing assembly that is built as a unit (P5, M4).

    A phantom only groups lines and folds into its parent's build step (P7), so it is not a
    module of its own and owns no parameters: the hint names the unit it folds into.
    ``export`` on an unscoped parameter changes nothing and is a warning.  Whether rules and
    expressions stay within reach is a check, not a validation error (``core/reach.py``).
    """
    from napkin2factory.core.tree import AssemblyTree

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
