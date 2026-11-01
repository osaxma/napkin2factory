"""Recording accessors (decisions D5, D21).

``P["sheet-thickness"]`` returns a pint quantity and logs ``param://sheet-thickness``;
``I["lid-base-mount"]`` returns the :class:`Interface` model and logs
``iface://lid-base-mount``.  Every kit generator and geometry module reads through
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
    """Ordered set of dependency keys read during one rule run.

    A key read while resolving an interface is added with ``via`` (the interface's URI).  It is
    one read like any other for invalidation (``keys``), but when it was read *only* that way it
    is listed in :attr:`iface_reads` too: the reach check (P5) leaves those to the joint.
    """

    def __init__(self) -> None:
        self._keys: dict[str, None] = {}
        self._direct: set[str] = set()

    def add(self, key: str, via: str | None = None) -> None:
        """Record a key (idempotent, order-preserving); ``via`` names the interface read through."""
        self._keys.setdefault(key, None)
        if via is None:
            self._direct.add(key)

    @property
    def keys(self) -> list[str]:
        """Keys in first-read order."""
        return list(self._keys)

    @property
    def iface_reads(self) -> list[str]:
        """Keys read only while resolving an interface (frames, offset, spec), never directly."""
        return [k for k in self._keys if k not in self._direct]

    def __len__(self) -> int:
        return len(self._keys)

    def __contains__(self, key: object) -> bool:
        return key in self._keys

    def clear(self) -> None:
        """Forget everything (a new run)."""
        self._keys.clear()
        self._direct.clear()


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
    """Return a copy of ``iface`` with every reference resolved to a value.

    ``param://`` in the spec become quantities; frame coordinates and the ``offset``
    (numbers, quantities, ``param://`` or ``{expr, unit}``, P2) become millimetres.  Each
    parameter read, including every slug an expression names, is recorded in ``log`` (D5), so
    a frame that depends on a parameter invalidates both parties when that parameter changes.
    Those reads are tagged with the interface (``via``): the other party's frame is the joint's
    business, so the reach check (P5) exempts them.
    """
    from napkin2factory.core.model import FrameExpr
    from napkin2factory.core.uris import Uri

    def read(slug: str) -> Any:
        if slug not in product.parameters:
            raise KeyError(f"param://{slug} does not exist (named in {iface.uri})")
        if log is not None:
            log.add(f"param://{slug}", via=iface.uri)
        return product.parameter_value(slug)

    def sub(v: Any) -> Any:
        if isinstance(v, Uri) and v.scheme == "param":
            return read(v.id)
        if isinstance(v, FrameExpr):
            return product.expr_value(v.expr, v.unit, lookup=read, where=iface.uri)
        if isinstance(v, list):
            return [sub(x) for x in v]
        return v

    from napkin2factory.core.units import mm as _mm_

    def to_mm(c: Any) -> float:
        c = sub(c)
        return float(c) if isinstance(c, (int, float)) else float(_mm_(c))

    def frame_mm(frame: Any) -> Any:
        return frame.model_copy(update={"origin": [to_mm(c) for c in frame.origin]})

    spec = iface.spec
    data = {name: sub(getattr(spec, name)) for name in type(spec).model_fields}
    return iface.model_copy(
        update={
            "spec": type(spec).model_validate(data),
            "frame": frame_mm(iface.frame),
            "frames": {k: frame_mm(f) for k, f in iface.frames.items()},
            "offset": to_mm(iface.offset),
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
