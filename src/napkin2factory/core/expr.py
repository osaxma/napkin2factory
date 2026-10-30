"""Safe expression evaluator for parameter ``expr`` fields.

Grammar: Python arithmetic over parameter names (hyphenated slugs allowed, so write
subtraction with spaces: ``a - b``), numbers, parentheses, and the functions ``min``,
``max``, ``abs``, ``sqrt``, ``ceil``, ``floor``, ``round``.  Values are pint quantities,
so unit errors surface at evaluation.  No attribute access, no calls beyond the list,
no names other than parameters.
"""

from __future__ import annotations

import ast
import math
import re
from collections.abc import Callable, Mapping
from typing import Any

from napkin2factory.core.uris import SLUG

_SLUG_RE = re.compile(rf"(?<![\w.])({SLUG})(?![\w(])")
_FUNCS: dict[str, Callable[..., Any]] = {
    "min": min,
    "max": max,
    "abs": abs,
    "sqrt": lambda x: x**0.5,
    "ceil": lambda x: _apply(math.ceil, x),
    "floor": lambda x: _apply(math.floor, x),
    "round": lambda x, n=0: _apply(lambda m: round(m, n), x),
}


def _apply(fn: Callable[[float], float], x: Any) -> Any:
    if hasattr(x, "magnitude"):
        return x.__class__(fn(x.magnitude), x.units)
    return fn(x)


class ExprError(ValueError):
    """An expression is malformed or references something it may not."""


def referenced_names(expr: str) -> list[str]:
    """Parameter slugs an expression reads, in order of first appearance."""
    seen: list[str] = []
    for m in _SLUG_RE.finditer(expr):
        name = m.group(1)
        if name in _FUNCS or name in seen:
            continue
        # a bare number like 2e3 is not a slug reference
        if re.fullmatch(r"\d+(?:e\d+)?", name):
            continue
        seen.append(name)
    return seen


def _rewrite(expr: str) -> str:
    """Replace hyphenated slugs with underscore identifiers so Python can parse them."""

    def sub(m: re.Match[str]) -> str:
        name = m.group(1)
        if name in _FUNCS or re.fullmatch(r"\d+(?:e\d+)?", name):
            return name
        return "p_" + name.replace("-", "_")

    return _SLUG_RE.sub(sub, expr)


_ALLOWED_NODES: tuple[type[ast.AST], ...] = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Name,
    ast.Call,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Mod,
    ast.FloorDiv,
)


def check_syntax(expr: str) -> None:
    """Parse ``expr`` and reject disallowed syntax without evaluating anything."""
    _parse(expr)


def _parse(expr: str) -> ast.Expression:
    try:
        tree = ast.parse(_rewrite(expr), mode="eval")
    except SyntaxError as exc:
        raise ExprError(f"cannot parse expression {expr!r}: {exc.msg}") from exc
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ExprError(
                f"expression {expr!r} uses {type(node).__name__}, which is not allowed; "
                "only arithmetic, parameter names and min/max/abs/sqrt/ceil/floor/round"
            )
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
                raise ExprError(f"expression {expr!r} calls something other than {sorted(_FUNCS)}")
            if node.keywords:
                raise ExprError(f"expression {expr!r}: keyword arguments are not allowed")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ExprError(f"expression {expr!r}: only numeric constants are allowed")
        if isinstance(node, ast.Name) and node.id not in _FUNCS and not node.id.startswith("p_"):
            raise ExprError(f"expression {expr!r}: {node.id!r} is not allowed")
    return tree


def evaluate(
    expr: str, values: Mapping[str, Any], lookup: Callable[[str], Any] | None = None
) -> Any:
    """Evaluate ``expr`` against parameter ``values`` (slug → quantity).

    Args:
        expr: the expression text.
        values: mapping of slug to value; used when ``lookup`` is None.
        lookup: optional accessor called with the slug (so reads can be recorded).

    Raises:
        ExprError: on disallowed syntax or an unknown name.
    """
    tree = _parse(expr)

    def get(name: str) -> Any:
        if name in _FUNCS:
            return _FUNCS[name]
        if not name.startswith("p_"):
            raise ExprError(f"expression {expr!r}: unknown name {name!r}")
        slug = name[2:].replace("_", "-")
        if lookup is not None:
            return lookup(slug)
        if slug not in values:
            raise ExprError(
                f"expression {expr!r} references unknown parameter {slug!r}; "
                "add it to parameters.yaml"
            )
        return values[slug]

    def ev(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return get(node.id)
        if isinstance(node, ast.UnaryOp):
            v = ev(node.operand)
            return -v if isinstance(node.op, ast.USub) else +v
        if isinstance(node, ast.BinOp):
            left, right = ev(node.left), ev(node.right)
            op = node.op
            if isinstance(op, ast.Add):
                return left + right
            if isinstance(op, ast.Sub):
                return left - right
            if isinstance(op, ast.Mult):
                return left * right
            if isinstance(op, ast.Div):
                return left / right
            if isinstance(op, ast.Pow):
                return left**right
            if isinstance(op, ast.Mod):
                return left % right
            if isinstance(op, ast.FloorDiv):
                return left // right
        if isinstance(node, ast.Call):
            fn = get(node.func.id)  # type: ignore[attr-defined]
            return fn(*[ev(a) for a in node.args])
        raise ExprError(f"unsupported node {type(node).__name__}")  # pragma: no cover

    try:
        return ev(tree)
    except ExprError:
        raise
    except Exception as exc:
        raise ExprError(f"evaluating {expr!r} failed: {exc}") from exc
