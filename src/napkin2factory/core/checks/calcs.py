"""The calc runner: ``calc://module.fn`` → a pint quantity, with recorded reads.

A calc function takes the parameter accessor ``P`` (and may take ``I``) and returns a
quantity.  Its evidence key hashes the module source, the parameter values it read, and
the result, so a sign-off citing ``calc://thermal.skin_temperature`` is invalidated by a
formula change, an input change, or a different outcome.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.core.graph.hashing import sha256_file, sha256_json
from napkin2factory.core.loader import Product
from napkin2factory.core.units import format_quantity, is_quantity
from napkin2factory.geometry.accessors import make_accessors


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


__all__ = ["CalcError", "CalcRecord", "Path", "load_calc_module", "run_calc"]
