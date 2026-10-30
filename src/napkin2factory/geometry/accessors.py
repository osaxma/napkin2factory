"""Recording accessors (decisions D5, D21).

``P["wall-thickness"]`` returns a pint quantity and logs ``param://wall-thickness``;
``I["shell-frame-mount"]`` returns the :class:`Interface` model and logs
``iface://shell-frame-mount``.  Every kit generator and geometry module reads through
these, so the build graph learns exactly what each rule depended on.  ``mm()`` is the
boundary helper that turns a quantity into a float millimetre value for build123d.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from napkin2factory.core.loader import Product
from napkin2factory.core.model import Interface
from napkin2factory.core.units import mm as _mm


class ReadLog:
    """Ordered set of dependency keys read during one rule run."""

    def __init__(self) -> None:
        self._keys: dict[str, None] = {}

    def add(self, key: str) -> None:
        """Record a key (idempotent, order-preserving)."""
        self._keys.setdefault(key, None)

    @property
    def keys(self) -> list[str]:
        """Keys in first-read order."""
        return list(self._keys)

    def __len__(self) -> int:
        return len(self._keys)

    def __contains__(self, key: object) -> bool:
        return key in self._keys

    def clear(self) -> None:
        """Forget everything (a new run)."""
        self._keys.clear()


class ParamAccessor(Mapping[str, Any]):
    """``P`` — parameters by slug, each read recorded."""

    def __init__(self, product: Product, log: ReadLog) -> None:
        self._product = product
        self._log = log

    def __getitem__(self, slug: str) -> Any:
        if slug not in self._product.parameters:
            raise KeyError(
                f"param://{slug} does not exist; known parameters: "
                f"{', '.join(sorted(self._product.parameters)) or 'none'}"
            )
        value = self._product.parameter_value(slug)
        self._log.add(f"param://{slug}")
        return value

    def __iter__(self) -> Iterator[str]:
        return iter(self._product.parameters)

    def __len__(self) -> int:
        return len(self._product.parameters)

    def mm(self, slug: str) -> float:
        """Read a length parameter as millimetres."""
        return _mm(self[slug])

    def get_str(self, slug: str, default: str | None = None) -> str:
        """Read a parameter and format it (for docs)."""
        from napkin2factory.core.units import format_quantity

        return format_quantity(self[slug])


def resolve_interface(product: Product, iface: Interface, log: ReadLog | None = None) -> Interface:
    """Return a copy of ``iface`` with every ``param://`` in its spec replaced by the value.

    Each parameter read is recorded in ``log`` so a spec that depends on a parameter
    invalidates both parties when that parameter changes.
    """
    from napkin2factory.core.uris import Uri

    def sub(v: Any) -> Any:
        if isinstance(v, Uri) and v.scheme == "param":
            if log is not None:
                log.add(f"param://{v.id}")
            return product.parameter_value(v.id)
        if isinstance(v, list):
            return [sub(x) for x in v]
        return v

    from napkin2factory.core.units import mm as _mm_

    def frame_mm(frame: Any) -> Any:
        origin = []
        for c in frame.origin:
            c = sub(c)
            origin.append(float(c) if isinstance(c, (int, float)) else float(_mm_(c)))
        return frame.model_copy(update={"origin": origin})

    spec = iface.spec
    data = {name: sub(getattr(spec, name)) for name in type(spec).model_fields}
    return iface.model_copy(
        update={
            "spec": type(spec).model_validate(data),
            "frame": frame_mm(iface.frame),
            "frames": {k: frame_mm(f) for k, f in iface.frames.items()},
        }
    )


class InterfaceAccessor(Mapping[str, Interface]):
    """``I`` — interfaces by id, each read recorded (spec ``param://`` refs resolved)."""

    def __init__(self, product: Product, log: ReadLog) -> None:
        self._product = product
        self._log = log

    def __getitem__(self, iface_id: str) -> Interface:
        if iface_id not in self._product.interfaces:
            raise KeyError(
                f"iface://{iface_id} does not exist; known interfaces: "
                f"{', '.join(sorted(self._product.interfaces)) or 'none'}"
            )
        self._log.add(f"iface://{iface_id}")
        return resolve_interface(self._product, self._product.interfaces[iface_id], self._log)

    def __iter__(self) -> Iterator[str]:
        return iter(self._product.interfaces)

    def __len__(self) -> int:
        return len(self._product.interfaces)


def make_accessors(product: Product) -> tuple[ParamAccessor, InterfaceAccessor, ReadLog]:
    """A fresh ``(P, I, log)`` triple for one rule run."""
    log = ReadLog()
    return ParamAccessor(product, log), InterfaceAccessor(product, log), log


mm = _mm
