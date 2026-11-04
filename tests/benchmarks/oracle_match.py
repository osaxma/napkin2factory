"""How the oracle finds a thing without its id: card selection, number finders, judging.

Nothing here knows a part, requirement or card id of any product. A number is read from the
text n2f prints (``14.3 mm``, ``bbox.x = 995 mm <= 1000 mm``) and converted with the package's
own unit registry, so ``0.0143 m`` and ``14.3 mm`` are the same figure.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from typing import Any

from napkin2factory.core.units import ureg
from tests.benchmarks.oracle_evidence import Card
from tests.benchmarks.oracle_schema import (
    CardSel,
    Category,
    Expect,
    RequirementFind,
    ResultFind,
    ScreenRowFind,
)


class MatchError(ValueError):
    """A matcher found nothing, found several, or could not read what it found."""


NUM = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
_NUM_UNIT = re.compile(rf"^\s*({NUM})\s*(.*?)\s*$")
#: A unit as it starts: a letter, ``%`` or ``°``. A dash, a bracket or a digit starts no unit.
_UNIT = r"(?:[^\W\d_]|[%°])[^\s<>=)]*"
#: ``<value> [unit] <op> <bound> [unit]`` as a requirement's message ends (the last one counts).
#: A safety requirement without a sign-off goes on after its bound: ``>= 2 — passes by
#: computation; ...``. The words after the bound may look like a unit, so ``parse_bound_message``
#: keeps a captured unit only if the unit registry knows it (S-223).
_BOUND = re.compile(rf"({NUM})\s*({_UNIT})?\s*(<=|>=|==|<|>)\s*({NUM})\s*({_UNIT})?")

#: Words that put a failing check into a category, read from its id and title first, then its
#: message. A rule id from the structural screen is structural whatever its words say.
LEXICON: dict[str, str] = {
    "cost": r"cost|budget|price|usd|afford|spend",
    "mass": r"mass|weight|\bkg\b|lift|heav",
    "envelope": r"\bfits?\b|fitting|envelope|alcove|footprint|bounding|\bspace\b|\bsite\b",
    "structural": r"\bsag|deflect|stress|yield|buckl|\btip|stiff|strength|collaps|stand up",
}
_ORDER: tuple[Category, ...] = ("cost", "mass", "envelope", "structural")


def number_and_unit(text: str) -> tuple[float, str]:
    """``'14.3 mm'`` -> ``(14.3, 'mm')``; ``'3.92'`` -> ``(3.92, '')``."""
    m = _NUM_UNIT.match(str(text))
    if m is None:
        raise MatchError(f"no number in {str(text)[:60]!r}")
    return float(m.group(1)), m.group(2).strip()


def convert(value: float, unit: str, want: str | None) -> float:
    """``value`` in ``unit`` as a number of ``want`` (no ``want``: unchanged)."""
    if not want:
        return value
    if not unit:
        raise MatchError(f"{value:g} has no unit, expected {want}")
    try:
        return float(ureg.Quantity(value, unit).to(want).magnitude)
    except Exception as exc:  # pint's errors differ per case: undefined unit, wrong dimension
        raise MatchError(f"cannot read {value:g} {unit} as {want} ({type(exc).__name__})") from exc


def same_bound(found: tuple[float, str], want: tuple[float, str]) -> bool:
    """True when two bounds are the same quantity (same dimension, same size)."""
    (fv, fu), (wv, wu) = found, want
    if bool(fu) != bool(wu):
        return False
    try:
        got = convert(fv, fu, wu) if wu else fv
    except MatchError:
        return False
    return abs(got - wv) <= 1e-6 * max(abs(wv), 1.0)


# --- categories and cards ----------------------------------------------------------------


def categorize(rule: dict[str, Any], extra: dict[str, list[str]] | None = None) -> str | None:
    """The category a failing rule row belongs to, or None when no word places it."""
    rid = str(rule.get("id", ""))
    if rid.startswith("structural-"):
        return "structural"
    extra = extra or {}
    for text in (f"{rid} {rule.get('title', '')}", str(rule.get("message", ""))):
        for cat in _ORDER:
            words = "|".join([LEXICON[cat], *extra.get(cat, [])])
            if re.search(words, text.lower()):
                return cat
    return None


def failing_categories(card: Card, extra: dict[str, list[str]] | None = None) -> set[str]:
    """The categories of the card's failing screening rows."""
    found = (categorize(r, extra) for r in card.rules if r.get("status") == "fail")
    return {c for c in found if c}


def _word(s: str) -> str:
    return re.sub(r"[\s_-]+", " ", s.lower()).strip()


def matches(card: Card, sel: CardSel, extra: dict[str, list[str]] | None = None) -> bool:
    """True when the card has every property the selector names."""
    if sel.status is not None and card.status != sel.status:
        return False
    cats = failing_categories(card, extra)
    if not set(sel.by) <= cats or set(sel.not_by) & cats:
        return False
    if sel.material is not None and not any(
        _word(sel.material) in _word(m) for m in card.materials
    ):
        return False
    if sel.kit is not None and sel.kit not in card.kits:
        return False
    return sel.pieces is None or card.pieces == sel.pieces


def describe(sel: CardSel) -> str:
    """A selector in words, for a row's text."""
    bits = [sel.status or "a card"]
    if sel.by:
        bits.append("failing " + " and ".join(sel.by))
    if sel.not_by:
        bits.append("not failing " + " or ".join(sel.not_by))
    if sel.material:
        bits.append(f"with {sel.material}")
    if sel.kit:
        bits.append(f"using a {sel.kit}")
    if sel.pieces is not None:
        bits.append(f"of {sel.pieces} rough shapes")
    return " ".join(bits)


def pick_card(cards: list[Card], sel: CardSel, extra: dict[str, list[str]] | None = None) -> Card:
    """The one card the selector means; none or several raise ``MatchError`` saying so."""
    hits = [c for c in cards if matches(c, sel, extra)]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        seen = ", ".join(
            f"{c.status}/{sorted(failing_categories(c, extra)) or 'no failure'}" for c in cards
        )
        raise MatchError(f"no card is {describe(sel)} (cards: {seen or 'none'})")
    raise MatchError(f"{len(hits)} cards are {describe(sel)}; add a property that tells them apart")


def assign(
    cards: list[Card], sels: list[CardSel], extra: dict[str, list[str]] | None = None
) -> list[Card] | None:
    """Give each selector its own card (every card used once), or None if that cannot be done."""
    if len(cards) != len(sels):
        return None
    for order in itertools.permutations(cards):
        if all(matches(c, s, extra) for c, s in zip(order, sels, strict=True)):
            return list(order)
    return None


# --- finders -----------------------------------------------------------------------------


@dataclass
class Found:
    """What a finder read: numbers in the figure's unit, where, and if several are fine."""

    values: list[float]
    where: str
    unit: str = ""
    several_ok: bool = False
    labels: list[str] = field(default_factory=list)


def screen_values(card: Card, names: list[str], unit: str | None) -> Found:
    """A named value of the card's screening (computed, then estimates, then given)."""
    s = card.screening
    if not s:
        raise MatchError("the card was never screened")
    entries: dict[str, Any] = {}
    for group in ("given", "estimates", "computed"):
        entries.update(s.get(group, {}))
    for name in names:
        if name in entries:
            v, u = number_and_unit(entries[name]["value"])
            return Found([convert(v, u, unit)], f"the card's screened {name}", unit or u)
    have = ", ".join(sorted(entries)) or "nothing"
    raise MatchError(
        f"the card's screening has no value named {' or '.join(names)} (it has: {have})"
    )


def screen_row(card: Card, find: ScreenRowFind, unit: str | None, extra: Any = None) -> Found:
    """A number captured by ``regex`` from the one screening row of a check kind or category."""
    rows = [
        r
        for r in card.rules
        if (find.rule is not None and r.get("id") == find.rule)
        or (find.category is not None and categorize(r, extra) == find.category)
    ]
    what = find.rule or find.category
    if not rows:
        raise MatchError(f"the card's screening has no row for {what}")
    if len(rows) > 1:
        raise MatchError(f"{len(rows)} screening rows match {what}")
    m = re.search(find.regex, str(rows[0].get("message", "")))
    if m is None:
        raise MatchError(f"the {what} row's message does not match {find.regex!r}")
    v = float(m.groupdict().get("value", m.group(1)))
    u = m.groupdict().get("unit") or ""
    return Found([convert(v, u, unit)], f"the card's {what} row", unit or u)


def requirement_rows(check: dict[str, Any]) -> list[dict[str, Any]]:
    """The requirement results of ``n2f check --json``, with the matrix's category and kind."""
    meta = {f"req://{r['id']}": r for r in (check.get("matrix", {}).get("requirements", []))}
    rows = [r for r in check.get("results", []) if r.get("kind") == "requirement"]
    return [{**meta.get(r.get("id", ""), {}), **r} for r in rows]


def parse_bound_message(message: str) -> tuple[tuple[float, str], str, tuple[float, str]]:
    """``(value, unit), op, (bound, unit)`` from the end of a requirement's message."""
    hits = list(_BOUND.finditer(message))
    if not hits:
        raise MatchError(f"no `value <= bound` in {message[:70]!r}")
    m = hits[-1]
    return (
        (float(m.group(1)), _known_unit(m.group(2))),
        m.group(3),
        (float(m.group(4)), _known_unit(m.group(5))),
    )


def _known_unit(token: str | None) -> str:
    """``token`` if the unit registry reads it as a unit, else nothing (words after a bound)."""
    if not token:
        return ""
    try:
        ureg.Quantity(1, token)
    except Exception:  # pint's errors differ per case: undefined unit, bad syntax
        return ""
    return token


def requirement_values(check: dict[str, Any], find: RequirementFind, unit: str | None) -> Found:
    """The measured values of every requirement with this bound (and flags)."""
    want = number_and_unit(find.bound)
    vals: list[float] = []
    labels: list[str] = []
    for row in requirement_rows(check):
        if find.safety is not None and bool(row.get("safety")) != find.safety:
            continue
        if find.category is not None and row.get("category") != find.category:
            continue
        if find.kind is not None and row.get("kind") != find.kind:
            continue
        try:
            (v, vu), op, bound = parse_bound_message(str(row.get("message", "")))
        except MatchError:
            continue
        if (find.op is not None and op != find.op) or not same_bound(bound, want):
            continue
        vals.append(convert(v, vu, unit))
        labels.append(str(row.get("title", "")))
    if not vals:
        raise MatchError(
            f"no requirement is bounded at {find.bound}" + (f" ({find.op})" if find.op else "")
        )
    return Found(
        vals, f"requirements bounded at {find.bound}", unit or "", several_ok=True, labels=labels
    )


def rollup_value(rollups: dict[str, Any], key: str, unit: str | None) -> Found:
    """A BOM roll-up number, in its own unit (``total_mass`` is in kg)."""
    if key not in rollups or not isinstance(rollups[key], int | float):
        have = ", ".join(sorted(k for k, v in rollups.items() if isinstance(v, int | float)))
        raise MatchError(f"the BOM roll-up has no number {key} (it has: {have})")
    own = str(rollups.get(f"{key}_unit", ""))
    return Found([convert(float(rollups[key]), own, unit)], f"the BOM roll-up {key}", unit or own)


def result_value(check: dict[str, Any], find: ResultFind, unit: str | None) -> Found:
    """One check result row of a kind (and rule), and a number in it."""
    rows = [
        r
        for r in check.get("results", [])
        if r.get("kind") == find.kind
        and (
            find.rule is None or find.rule in str(r.get("detail", {}).get("rule", r.get("id", "")))
        )
    ]
    what = f"{find.kind} result" + (f" {find.rule}" if find.rule else "")
    if not rows:
        raise MatchError(f"check printed no {what}")
    if len(rows) > 1:
        raise MatchError(f"{len(rows)} {what} rows; name the rule that wrote it")
    row = rows[0]
    if find.path is not None:
        cur: Any = row
        for part in find.path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                raise MatchError(f"the {what} row has no {find.path}")
            cur = cur[part]
        if isinstance(cur, int | float):  # a bare JSON number is in the figure's own unit
            return Found([float(cur)], f"the {what}", unit or "")
        v, u = number_and_unit(str(cur))
    else:
        assert find.regex is not None
        m = re.search(find.regex, str(row.get("message", "")))
        if m is None:
            raise MatchError(f"the {what} message does not match {find.regex!r}")
        v, u = float(m.groupdict().get("value", m.group(1))), m.groupdict().get("unit") or ""
    return Found([convert(v, u, unit)], f"the {what}", unit or u)


# --- judging -----------------------------------------------------------------------------


def within(got: float, want: float, tol: float, abs_tol: float) -> bool:
    """``got`` is within ``tol`` (relative) of ``want``, plus ``abs_tol``."""
    return abs(got - want) <= tol * abs(want) + abs_tol


def expectation(e: Expect, default_tol: float) -> str:
    """The expectation in words."""
    tol = default_tol if e.tol is None else e.tol
    if e.expect is not None:
        wants = e.expect if isinstance(e.expect, list) else [e.expect]
        return " or ".join(f"{w:g}" for w in wants) + (f" (±{tol * 100:g} %)" if tol else "")
    parts = []
    if e.at_least is not None:
        parts.append(f"at least {e.at_least:g}")
    if e.at_most is not None:
        parts.append(f"at most {e.at_most:g}")
    if e.range is not None:
        parts.append(f"between {e.range[0]:g} and {e.range[1]:g}")
    return " and ".join(parts)


def number_ok(got: float, e: Expect, default_tol: float) -> bool:
    """True when ``got`` satisfies every part of the expectation."""
    tol = default_tol if e.tol is None else e.tol
    if e.expect is not None:
        wants = e.expect if isinstance(e.expect, list) else [e.expect]
        if not any(within(got, w, tol, e.abs_tol) for w in wants):
            return False
    if e.at_least is not None and got < e.at_least:
        return False
    if e.at_most is not None and got > e.at_most:
        return False
    return e.range is None or e.range[0] <= got <= e.range[1]


def judge(found: Found, e: Expect, default_tol: float) -> tuple[bool, str]:
    """Judge a finder's numbers against an expectation: ``(passed, found text)``.

    Several numbers are allowed only where the finder says so (requirements bounded alike);
    then the figure passes if one is in tolerance, and is ambiguous if two that differ are.
    """
    shown = ", ".join(f"{v:.4g}" for v in found.values)
    unit = f" {found.unit}" if found.unit else ""
    if len(found.values) > 1 and not found.several_ok:
        raise MatchError(f"{len(found.values)} candidates ({shown}) at {found.where}")
    good = [v for v in found.values if number_ok(v, e, default_tol)]
    if len(found.values) == 1:
        return bool(good), f"{shown}{unit}"
    if not good:
        return False, f"none of {shown}{unit} ({len(found.values)} {found.where})"
    tol = default_tol if e.tol is None else e.tol
    if len(good) > 1 and not all(within(g, good[0], max(tol, 1e-9), e.abs_tol) for g in good):
        raise MatchError(
            f"{len(good)} candidates in tolerance but differing ({shown}) at {found.where}"
        )
    return True, f"{good[0]:.4g}{unit} (of {shown}, {found.where})"
