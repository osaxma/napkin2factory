"""The recording accessor a domain's build code reads the model through (D5, gate E B2, S-138).

A build rule, a check stage and a report section's data get ``proxy(obj, uri)`` from their
context (:class:`~napkin2factory.core.graph.rules.RunContext`,
:class:`~napkin2factory.core.domain.StageContext`,
:class:`~napkin2factory.core.domain.SectionContext`).  Reading a field through the proxy
records ``<uri>#<path>`` in the context's ``log``, and the core adds those keys to the rule's
recorded reads, so a change to any field the code used reruns the rule.  Unlike a manual
page's proxy (``docs/engine.py``), a leaf comes back as the plain value (a number, a string, a
URI, a quantity), so the code computes with it as with the object itself.

A nested object (``thing.spec``) comes back as another proxy and records nothing until a
field of it is read, or the object itself is used whole (``str()``, ``==``, iteration,
:func:`unwrap`), which records its own path.  A method or computed property of an object
(``part.uri``, ``spec.model_dump()``) records the whole object: every declared field of it.
"""

from __future__ import annotations

from typing import Any


class Recorded:
    """A model object (or a dict of one) that records each field read as ``<uri>#<path>``."""

    __slots__ = ("_log", "_obj", "_path", "_uri")

    def __init__(self, obj: Any, uri: str, log: Any, path: tuple[str, ...] = ()) -> None:
        """Wrap ``obj``, which ``uri`` names; ``log.add(key)`` receives each read."""
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_uri", uri)
        object.__setattr__(self, "_log", log)
        object.__setattr__(self, "_path", path)

    # ---- reads -------------------------------------------------------------------------

    def _key(self, path: tuple[str, ...]) -> str:
        return f"{self._uri}#{'.'.join(path)}" if path else self._uri

    def _record_whole(self) -> None:
        """Record this object as used whole: its own path, or each field at the top."""
        names = _field_names(self._obj)
        if self._path or not names:
            self._log.add(self._key(self._path))
            return
        for name in names:
            self._log.add(self._key((name,)))

    def _field(self, name: str) -> Any:
        obj = self._obj
        path = (*self._path, name)
        if isinstance(obj, dict):
            if name not in obj:
                raise AttributeError(f"{self._key(path)} does not exist")
            value = obj[name]
        elif name in _field_names(obj):
            value = getattr(obj, name)
        else:
            # a method or a computed property: it may read any field
            value = getattr(obj, name)  # AttributeError: no such field, said by the object
            self._record_whole()
            return value
        if _is_object(value):
            return Recorded(value, self._uri, self._log, path)
        self._log.add(self._key(path))
        return value

    def __getattr__(self, name: str) -> Any:
        """``thing.glow`` records ``<uri>#glow``."""
        if name.startswith("_"):
            raise AttributeError(name)
        return self._field(name)

    def __getitem__(self, key: Any) -> Any:
        """``obj["key"]`` on a dict field records ``<uri>#<path>.key``."""
        if isinstance(self._obj, dict) and isinstance(key, str):
            return self._field(key)
        self._record_whole()
        return self._obj[key]

    def __setattr__(self, name: str, value: Any) -> None:
        """The model is read-only to a build rule."""
        raise AttributeError(f"{self._key(self._path)} is read-only here")

    # ---- the object used whole ---------------------------------------------------------

    def __str__(self) -> str:
        """The object as text (records it whole)."""
        self._record_whole()
        return str(self._obj)

    def __repr__(self) -> str:
        """Names the key without reading (a debugger's view)."""
        return f"<recorded {self._key(self._path)}>"

    def __eq__(self, other: object) -> bool:
        """Compares the object (records it whole)."""
        self._record_whole()
        return bool(self._obj == (other._obj if isinstance(other, Recorded) else other))

    def __hash__(self) -> int:
        """Hashes the object (records it whole)."""
        self._record_whole()
        return hash(self._obj)

    def __bool__(self) -> bool:
        """Truth of the object (records it whole)."""
        self._record_whole()
        return bool(self._obj)

    def __iter__(self) -> Any:
        """Iterates the object (records it whole)."""
        self._record_whole()
        return iter(self._obj)

    def __len__(self) -> int:
        """Length of the object (records it whole)."""
        self._record_whole()
        return len(self._obj)

    def __contains__(self, item: object) -> bool:
        """Membership in the object (records it whole)."""
        self._record_whole()
        return item in self._obj


def unwrap(value: Any) -> Any:
    """The plain object behind a :class:`Recorded` (recorded whole); anything else unchanged."""
    if isinstance(value, Recorded):
        value._record_whole()
        return value._obj
    return value


def _is_object(value: Any) -> bool:
    return hasattr(type(value), "model_fields") or isinstance(value, dict)


def _field_names(obj: Any) -> list[str]:
    if isinstance(obj, dict):
        return [str(k) for k in obj]
    fields = getattr(type(obj), "model_fields", None)
    return list(fields) if fields is not None else []
