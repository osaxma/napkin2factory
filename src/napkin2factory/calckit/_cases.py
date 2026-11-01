"""Reference cases: the inputs, the expected result and where the expectation comes from (F17).

A calc proves itself by reproducing cases its author did not get from the formula itself: a
hand computation written out in the case, or better a worked example from a handbook or a
datasheet (``external=True``).  Each calc-kit pack lists its cases in a module-level
``CASES``; a product calc lists them in ``model/calcs/<module>.cases.yaml`` or a module-level
``CASES`` (``core/checks/calcs.py``).  Both are compared here, so a tolerance means the same
everywhere:

    passes when |actual − expected| ≤ max(abs, rel · |expected|)

in the expected value's unit (``abs`` is a plain number in that unit); with neither given,
``rel`` is :data:`DEFAULT_REL`.  A result that is not a number (a label, a flag) must equal
the expected value.  ``pick`` selects a field of a structured result (``"loss"``,
``"guard_temperature"``, ``"0"`` for the first item of a tuple, dotted for deeper).
"""

from __future__ import annotations

import inspect
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

from napkin2factory.core.units import Quantity, is_quantity

#: Tolerance when a case gives none: six significant figures.
DEFAULT_REL = 1e-6


@dataclass(frozen=True)
class Case:
    """One reference case of a calc-kit function.

    Attributes:
        fn: the function's name in its pack.
        expect: the expected result (a quantity, a number, a string or a flag).
        source: where ``expect`` comes from, precisely ("Kanthal, Design of wire elements,
            p. 51, direct-calculation example", "hand computation: …").
        args: positional arguments.
        kwargs: keyword arguments.
        pick: the field of a structured result to compare (see the module docstring).
        rel: relative tolerance.
        abs: absolute tolerance, in ``expect``'s unit.
        external: ``expect`` comes from a published source, not the author's arithmetic.
        verify: the number could not be confirmed from the source itself; a person still
            has to (``make verify-list`` prints the decision entry that names it).
        note: how the case's inputs were derived from the source, when they were.
    """

    fn: str
    expect: Any
    source: str
    args: tuple[Any, ...] = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)
    pick: str | None = None
    rel: float | None = None
    abs: float | None = None
    external: bool = False
    verify: bool = False
    note: str = ""


@dataclass(frozen=True)
class Outcome:
    """The verdict of one case: passed, and both values as text."""

    ok: bool
    expected: str
    actual: str
    message: str = ""


def fmt(value: Any) -> str:
    """A value as text with enough digits to see a miss (six significant figures)."""
    if is_quantity(value):
        unit = f"{value.units:~P}"
        return f"{float(value.magnitude):.6g} {unit}".strip()
    if isinstance(value, float):
        return f"{value:.6g}"
    return repr(value) if isinstance(value, str) else str(value)


def tolerance_text(rel: float | None, abs_tol: float | None, unit: str = "") -> str:
    """``± 1 %`` / ``± 0.1 degC`` / ``± 0.0001 %`` for messages."""
    parts = []
    if abs_tol is not None:
        parts.append(f"± {abs_tol:g}{(' ' + unit) if unit else ''}")
    if rel is not None or abs_tol is None:
        r = DEFAULT_REL if rel is None and abs_tol is None else rel
        assert r is not None
        parts.append(f"± {r * 100:g} %")
    return " or ".join(parts)


def pick(result: Any, path: str | None) -> Any:
    """The field ``path`` (dotted; a number indexes a sequence) of ``result``."""
    if not path:
        return result
    out = result
    for step in path.split("."):
        if step.lstrip("-").isdigit() and isinstance(out, Sequence) and not isinstance(out, str):
            out = out[int(step)]
        elif isinstance(out, Mapping):
            out = out[step]
        else:
            out = getattr(out, step)
    return out


def compare(
    actual: Any, expect: Any, rel: float | None = None, abs_tol: float | None = None
) -> Outcome:
    """Compare a result with its expected value under the case tolerance."""
    if rel is None and abs_tol is None:
        rel = DEFAULT_REL
    if is_quantity(expect) or (
        isinstance(expect, (int, float)) and not isinstance(expect, bool) and is_quantity(actual)
    ):
        exp_q = expect if is_quantity(expect) else Quantity(float(expect), "")
        if not is_quantity(actual):
            if isinstance(actual, (int, float)) and not isinstance(actual, bool):
                actual = Quantity(float(actual), "")
            else:
                return Outcome(False, fmt(expect), fmt(actual), "not a quantity")
        try:
            got = actual.to(exp_q.units)
        except Exception as exc:  # pint.DimensionalityError: the unit kind differs
            return Outcome(False, fmt(expect), fmt(actual), f"wrong kind of unit ({exc})")
        a, e = float(got.magnitude), float(exp_q.magnitude)
        unit = f"{exp_q.units:~P}"
        ok = _close(a, e, rel, abs_tol)
        return Outcome(ok, f"{fmt(expect)} {tolerance_text(rel, abs_tol, unit)}", fmt(got))
    if isinstance(expect, float) or (
        isinstance(expect, int) and not isinstance(expect, bool) and isinstance(actual, float)
    ):
        if isinstance(actual, bool) or not isinstance(actual, (int, float)):
            return Outcome(False, fmt(expect), fmt(actual), "not a number")
        ok = _close(float(actual), float(expect), rel, abs_tol)
        return Outcome(ok, f"{fmt(expect)} {tolerance_text(rel, abs_tol)}", fmt(actual))
    return Outcome(actual == expect, fmt(expect), fmt(actual))


def _close(a: float, e: float, rel: float | None, abs_tol: float | None) -> bool:
    if math.isnan(a):
        return False
    limit = max(abs_tol or 0.0, (rel or 0.0) * abs(e))
    return abs(a - e) <= limit


def run_case(fn: Callable[..., Any], case: Case) -> Outcome:
    """Call ``fn`` with the case's arguments and compare the (picked) result."""
    try:
        result = fn(*case.args, **dict(case.kwargs))
        value = pick(result, case.pick)
    except Exception as exc:
        return Outcome(False, fmt(case.expect), "—", f"raised {type(exc).__name__}: {exc}")
    return compare(value, case.expect, case.rel, case.abs)


def public_functions(module: ModuleType) -> list[str]:
    """The calc functions a pack exports (``__all__`` entries that are plain functions)."""
    names = getattr(module, "__all__", None) or [n for n in vars(module) if not n.startswith("_")]
    return [
        n
        for n in names
        if inspect.isfunction(getattr(module, n, None))
        and getattr(module, n).__module__ == module.__name__
    ]


def pack_cases(module: ModuleType) -> list[Case]:
    """A pack's ``CASES`` (empty when it declares none)."""
    return list(getattr(module, "CASES", ()) or ())


def uncovered(module: ModuleType) -> list[str]:
    """Public functions of a pack without a reference case."""
    covered = {c.fn for c in pack_cases(module)}
    return [n for n in public_functions(module) if n not in covered]


def run_pack(module: ModuleType) -> list[tuple[Case, Outcome]]:
    """Run every case of a pack; an unknown ``fn`` is a failed case naming it."""
    out = []
    for case in pack_cases(module):
        fn = getattr(module, case.fn, None)
        if not callable(fn):
            out.append((case, Outcome(False, fmt(case.expect), "—", f"no function {case.fn}")))
            continue
        out.append((case, run_case(fn, case)))
    return out


__all__ = [
    "DEFAULT_REL",
    "Case",
    "Outcome",
    "compare",
    "fmt",
    "pack_cases",
    "pick",
    "public_functions",
    "run_case",
    "run_pack",
    "tolerance_text",
    "uncovered",
]
