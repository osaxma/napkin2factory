"""The calc runner: ``calc://module.fn`` → a pint quantity, with recorded reads.

A calc function takes the parameter accessor ``P`` (and may take ``I``) and returns a
quantity.  Its evidence key hashes the module source, the parameter values it read, and
the result, so a sign-off citing ``calc://heat.skin_temperature`` is invalidated by a
formula change, an input change, or a different outcome.

Reference cases (F17): a product calc proves itself by reproducing cases listed in
``model/calcs/<module>.cases.yaml`` (or a module-level ``CASES`` of the same shape)::

    inputs:                 # parameter values every case below reads, unless it overrides
      plate-thickness: 64 mm
    cases:
      skin_temperature:
        - expect: 78.8 degC
          abs: 0.1          # in the expected unit; or rel: 0.01; default rel 1e-6
          source: "hand computation: …"
          inputs: {plate-thickness: 70 mm}   # optional, overrides the shared value

A case runs the calc on its own inputs, never on the product's current parameters: it checks
the formula, not the design (the requirements do that), and a parameter the calc reads that
the case does not give is a failed case naming it.  :func:`calc_case_stage` turns them into
``calc-case`` rows of ``n2f check``: one per calc (``fail`` naming the calc, the expected and
the computed value; ``warn`` when it has no case), and one per calc-kit pack the product's
calcs use, which runs that pack's own cases (``napkin2factory.calckit._cases``).
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

from napkin2factory.calckit._cases import DEFAULT_REL, Outcome, compare, fmt, pack_cases, run_pack
from napkin2factory.core.checks.results import CheckResult
from napkin2factory.core.graph.hashing import sha256_file, sha256_json
from napkin2factory.core.loader import Product
from napkin2factory.core.units import UnitError, format_quantity, is_quantity, parse_quantity
from napkin2factory.geometry.accessors import make_accessors

if TYPE_CHECKING:
    from napkin2factory.core.domain import StageContext


class CalcError(ValueError):
    """A calc could not be run; the message names the calc and the cause."""


@dataclass
class CalcRecord:
    """Result plus provenance."""

    uri: str
    value: Any
    reads: list[str]
    inputs: dict[str, str]
    key: str
    formatted: str
    doc: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON form."""
        return {
            "uri": self.uri,
            "value": self.formatted,
            "reads": self.reads,
            "inputs": self.inputs,
            "key": self.key,
            "doc": self.doc,
            **self.extra,
        }


_MODULE_CACHE: dict[str, Any] = {}


def load_calc_module(product: Product, module: str) -> Any:
    """Import ``model/calcs/<module>.py`` (fresh each product root)."""
    path = product.paths.calcs / f"{module}.py"
    if not path.is_file():
        raise CalcError(f"calc module {module} not found: expected {path}")
    name = f"n2f_calc_{product.id.replace('-', '_')}_{module}"
    key = f"{path}:{sha256_file(path)}"
    cached = _MODULE_CACHE.get(name)
    if cached is not None and cached[0] == key:
        return cached[1]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise CalcError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    if str(product.paths.calcs) not in sys.path:
        sys.path.insert(0, str(product.paths.calcs))
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        raise CalcError(f"{path.name}: import failed: {type(exc).__name__}: {exc}") from exc
    _MODULE_CACHE[name] = (key, mod)
    return mod


def run_calc(product: Product, uri: str) -> CalcRecord:
    """Run ``calc://module.fn`` and return its record."""
    ident = uri.replace("calc://", "").split("#")[0]
    module, _, fn_name = ident.partition(".")
    if not fn_name:
        raise CalcError(f"{uri}: expected calc://<module>.<function>")
    mod = load_calc_module(product, module)
    fn = getattr(mod, fn_name, None)
    if fn is None or not callable(fn):
        raise CalcError(f"{uri}: no function {fn_name} in model/calcs/{module}.py")
    P, iface_acc, log = make_accessors(product)
    params = inspect.signature(fn).parameters
    kwargs: dict[str, Any] = {}
    if "I" in params:
        kwargs["I"] = iface_acc
    try:
        value = fn(P, **kwargs) if "P" in params or len(params) >= 1 else fn()
    except Exception as exc:
        raise CalcError(f"{uri} raised {type(exc).__name__}: {exc}") from exc
    if not is_quantity(value) and not isinstance(value, (int, float, bool)):
        raise CalcError(
            f"{uri} must return a pint quantity or a number, got {type(value).__name__}"
        )
    inputs = {k: _value_str(product, k) for k in log.keys}
    formatted = format_quantity(value) if is_quantity(value) else str(value)
    key = sha256_json(
        {
            "source": sha256_file(product.paths.calcs / f"{module}.py"),
            "inputs": inputs,
            "result": formatted,
        }
    )
    return CalcRecord(
        uri=f"calc://{ident}",
        value=value,
        reads=log.keys,
        inputs=inputs,
        key=key,
        formatted=formatted,
        doc=(fn.__doc__ or "").strip(),
    )


def _value_str(product: Product, key: str) -> str:
    if key.startswith("param://"):
        return format_quantity(product.parameter_value(key[len("param://") :]))
    if key.startswith("iface://"):
        from napkin2factory.geometry.accessors import resolve_interface

        return sha256_json(
            resolve_interface(product, product.interfaces[key[len("iface://") :]]).model_dump(
                mode="json"
            )
        )
    return key


# ---- reference cases (F17) -------------------------------------------------------------

#: A product calc module's case file: ``model/calcs/<module>.cases.yaml``.
CASES_SUFFIX = ".cases.yaml"

#: What the owner reads for a calc without a case, and the engineer's hint (F17).
NO_CASE = "no reference case; add one so a change to this formula is caught"


@dataclass
class ProductCase:
    """One reference case of a product calc, as declared (values still as written).

    ``error`` is set when the declaration itself is wrong (no ``expect``, no ``source``, a
    malformed value); such a case fails with that message.
    """

    calc: str
    index: int
    where: str
    inputs: dict[str, Any]
    expect: Any = None
    rel: float | None = None
    abs: float | None = None
    source: str = ""
    error: str = ""


class CaseInputMissing(KeyError):
    """A calc read a parameter its case does not give."""


class CaseParams(Mapping[str, Any]):
    """``P`` for a reference case: the case's own values, nothing from the product."""

    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def __getitem__(self, slug: str) -> Any:
        if slug not in self._values:
            raise CaseInputMissing(slug)
        return self._values[slug]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def mm(self, slug: str) -> float:
        """Read a length parameter as millimetres (as ``P.mm`` does)."""
        return float(self[slug].to("mm").magnitude)

    def get_str(self, slug: str, default: str | None = None) -> str:
        """Read a parameter and format it."""
        return format_quantity(self[slug])


def _case_value(raw: Any) -> Any:
    if is_quantity(raw) or isinstance(raw, bool):
        return raw
    return parse_quantity(raw)


def _declared(product: Product, module: str) -> tuple[dict[str, Any] | None, str]:
    """The case document of one calc module: its ``.cases.yaml``, else its ``CASES``."""
    from napkin2factory.core.yamlio import read_yaml

    path = product.paths.calcs / f"{module}{CASES_SUFFIX}"
    if path.is_file():
        try:
            data = read_yaml(path)
        except Exception as exc:
            return {"error": f"{path.name} does not parse: {exc}"}, path.name
        return (data if isinstance(data, dict) else {"error": f"{path.name}: not a mapping"}), (
            path.name
        )
    try:
        mod = load_calc_module(product, module)
    except CalcError:
        return None, f"{module}.py"
    doc = getattr(mod, "CASES", None)
    if doc is None:
        return None, f"{module}.py"
    return (doc if isinstance(doc, dict) else {"error": "CASES must be a mapping"}), (
        f"{module}.py CASES"
    )


def _float(raw: Any) -> float | None:
    return None if raw is None else float(raw)


def product_cases(product: Product) -> dict[str, list[ProductCase]]:
    """Every declared case of the product's calcs, by ``module.fn`` (declaration order).

    A key whose function does not exist is kept, so the row can say so.
    """
    out: dict[str, list[ProductCase]] = {}
    modules = sorted(set(product.calcs) | _case_files(product))
    for module in modules:
        doc, where = _declared(product, module)
        if doc is None:
            continue
        if "error" in doc and len(doc) == 1:
            out.setdefault(f"{module}.*", []).append(
                ProductCase(f"{module}.*", 1, where, {}, error=str(doc["error"]))
            )
            continue
        shared = doc.get("inputs") or {}
        for fn, cases in (doc.get("cases") or {}).items():
            calc = f"{module}.{fn}"
            for i, raw in enumerate(cases if isinstance(cases, list) else [cases], start=1):
                out.setdefault(calc, []).append(_parse_case(calc, i, where, shared, raw))
    return out


def _case_files(product: Product) -> set[str]:
    folder = product.paths.calcs
    if not folder.is_dir():
        return set()
    return {p.name[: -len(CASES_SUFFIX)] for p in folder.glob(f"*{CASES_SUFFIX}")}


def _parse_case(calc: str, i: int, where: str, shared: Any, raw: Any) -> ProductCase:
    case = ProductCase(calc, i, where, {})
    if not isinstance(raw, dict):
        case.error = f"case {i} is not a mapping (expect:, source:, inputs:)"
        return case
    try:
        values = {**(shared if isinstance(shared, dict) else {}), **(raw.get("inputs") or {})}
        case.inputs = {str(k): _case_value(v) for k, v in values.items()}
        if "expect" not in raw:
            raise ValueError("no expect: (the expected result with its unit)")
        case.expect = _case_value(raw["expect"])
        case.rel, case.abs = _float(raw.get("rel")), _float(raw.get("abs"))
    except (UnitError, ValueError, TypeError) as exc:
        case.error = f"case {i} in {where}: {exc}"
        return case
    case.source = str(raw.get("source") or "").strip()
    if not case.source:
        case.error = f"case {i} in {where} has no source: say where the expected value comes from"
    return case


def run_product_case(product: Product, case: ProductCase) -> Outcome:
    """Run one product calc on its case's inputs and compare with the expected value."""
    if case.error:
        return Outcome(False, fmt(case.expect), "—", case.error)
    module, _, fn_name = case.calc.partition(".")
    try:
        mod = load_calc_module(product, module)
    except CalcError as exc:
        return Outcome(False, fmt(case.expect), "—", str(exc))
    fn = getattr(mod, fn_name, None)
    if fn is None or not callable(fn):
        return Outcome(False, fmt(case.expect), "—", f"no function {fn_name} in {module}.py")
    params = inspect.signature(fn).parameters
    kwargs: dict[str, Any] = {}
    if "I" in params:
        kwargs["I"] = make_accessors(product)[1]  # interfaces are the product's own
    try:
        value = fn(CaseParams(case.inputs), **kwargs) if params else fn()
    except CaseInputMissing as exc:
        return Outcome(
            False,
            fmt(case.expect),
            "—",
            f"case {case.index} does not give {exc.args[0]!r}; add it to the case's inputs "
            f"(or the shared inputs of {case.where})",
        )
    except Exception as exc:
        return Outcome(False, fmt(case.expect), "—", f"raised {type(exc).__name__}: {exc}")
    return compare(value, case.expect, case.rel, case.abs)


def kit_packs(product: Product) -> list[ModuleType]:
    """The calc-kit packs the product's calc modules use (imported as modules or functions)."""
    found: dict[str, ModuleType] = {}
    for module in sorted(product.calcs):
        try:
            mod = load_calc_module(product, module)
        except CalcError:
            continue
        for value in vars(mod).values():
            name = getattr(value, "__name__", "") if isinstance(value, ModuleType) else ""
            if not name:
                name = getattr(value, "__module__", "") or ""
            leaf = name.rsplit(".", 1)[-1]
            if name.startswith("napkin2factory.calckit.") and not leaf.startswith("_"):
                pack = sys.modules.get(name)
                if pack is not None and pack_cases(pack):
                    found[name] = pack
    return [found[k] for k in sorted(found)]


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def calc_case_rows(product: Product) -> list[CheckResult]:
    """The ``calc-case`` rows: one per product calc, then one per calc-kit pack it uses."""
    declared = product_cases(product)
    rows: list[CheckResult] = []
    calcs = [f"{m}.{f}" for m in sorted(product.calcs) for f in product.calcs[m]]
    for calc in calcs + sorted(k for k in declared if k not in calcs):
        rows.append(_calc_row(product, calc, declared.get(calc, [])))
    for pack in kit_packs(product):
        rows.append(_pack_row(pack))
    return rows


def _calc_row(product: Product, calc: str, cases: list[ProductCase]) -> CheckResult:
    row = CheckResult(
        id=f"calc-case://{calc}",
        subject=f"calc://{calc}",
        status="pass",
        message="",
        kind="calc-case",
        title=f"Reference cases of {calc}",
    )
    module, _, fn = calc.partition(".")
    if module not in product.calcs or fn not in product.calcs[module]:
        where = cases[0].where if cases else f"{module}{CASES_SUFFIX}"
        row.status = "fail"
        row.message = (
            f"{where} lists cases for {calc}, which is not a calc in model/calcs/{module}.py; "
            "fix the name or remove the cases"
        )
        if cases and cases[0].error:
            row.message = cases[0].error
        row.persona_message = row.message
        return row
    if not cases:
        row.status = "warn"
        row.message = f"{calc}: {NO_CASE} (model/calcs/{module}{CASES_SUFFIX})"
        row.persona_message = NO_CASE
        return row
    outcomes = [(c, run_product_case(product, c)) for c in cases]
    row.detail = {
        "calc": calc,
        "cases": [
            {
                "case": c.index,
                "source": c.source,
                "expected": o.expected,
                "actual": o.actual,
                "ok": o.ok,
                "message": o.message,
            }
            for c, o in outcomes
        ],
    }
    bad = [(c, o) for c, o in outcomes if not o.ok]
    if bad:
        c, o = bad[0]
        why = f" ({o.message})" if o.message else ""
        row.status = "fail"
        row.message = (
            f"{calc}: case {c.index} of {len(cases)} expected {o.expected}, computed "
            f"{o.actual}{why}; source: {c.source or 'none given'}"
        )
        row.persona_message = (
            f"the formula misses its reference case: expected {o.expected}, computed "
            f"{o.actual}{why}" + (f"; {len(bad) - 1} more case(s) miss" if len(bad) > 1 else "")
        )
        return row
    row.message = f"{calc}: {_plural(len(cases), 'reference case')} reproduced"
    row.persona_message = (
        f"the formula reproduces its {_plural(len(cases), 'reference case')} ({cases[0].source})"
    )
    return row


def _pack_row(pack: ModuleType) -> CheckResult:
    name = pack.__name__.rsplit(".", 1)[-1]
    results = run_pack(pack)
    external = [c for c, _ in results if c.external]
    sources = sorted({c.source.split(":")[0].split(",")[0] for c in external})
    bad = [(c, o) for c, o in results if not o.ok]
    row = CheckResult(
        id=f"calc-case://calckit.{name}",
        subject=f"calckit.{name}",
        status="fail" if bad else "pass",
        message="",
        kind="calc-case",
        title=f"Reference cases of the calc kit's {name.replace('_', ' ')} formulas",
        detail={
            "pack": name,
            "cases": [
                {
                    "fn": c.fn,
                    "source": c.source,
                    "external": c.external,
                    "verify": c.verify,
                    "expected": o.expected,
                    "actual": o.actual,
                    "ok": o.ok,
                    "message": o.message,
                }
                for c, o in results
            ],
        },
    )
    if bad:
        c, o = bad[0]
        why = f" ({o.message})" if o.message else ""
        row.message = (
            f"calckit.{name}.{c.fn}: expected {o.expected}, computed {o.actual}{why}; "
            f"source: {c.source}"
        )
        row.persona_message = (
            f"a shared formula ({c.fn}) misses its reference case: expected {o.expected}, "
            f"computed {o.actual}"
        )
        return row
    row.message = (
        f"calckit.{name}: {_plural(len(results), 'reference case')} reproduced, "
        f"{len(external)} from published sources ({'; '.join(sources) or 'none'})"
    )
    row.persona_message = (
        f"the shared {name.replace('_', ' ')} formulas reproduce "
        f"{_plural(len(results), 'reference case')}, {len(external)} of them from published "
        "sources"
    )
    return row


def calc_case_stage(sctx: StageContext) -> list[CheckResult]:
    """The ``calc-case`` check stage (F17): every case of every calc the product uses."""
    return calc_case_rows(sctx.product)


def calc_case_reads(product: Product) -> list[str]:
    """What the rows depend on: each calc's module source (its cases sit beside it)."""
    return [f"calc://{m}.{f}" for m in sorted(product.calcs) for f in product.calcs[m]]


def calcs_without_cases(product: Product) -> list[str]:
    """``module.fn`` of each product calc that declares no reference case (the lint, F17)."""
    declared = product_cases(product)
    return [
        f"{m}.{f}"
        for m in sorted(product.calcs)
        for f in product.calcs[m]
        if not declared.get(f"{m}.{f}")
    ]


__all__ = [
    "CASES_SUFFIX",
    "DEFAULT_REL",
    "NO_CASE",
    "CalcError",
    "CalcRecord",
    "CaseParams",
    "Path",
    "ProductCase",
    "calc_case_reads",
    "calc_case_rows",
    "calc_case_stage",
    "calcs_without_cases",
    "kit_packs",
    "load_calc_module",
    "product_cases",
    "run_calc",
    "run_product_case",
]
