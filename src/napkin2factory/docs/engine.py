"""Templated Markdown with recorded reads (decision D8).

A manual page's body is a Jinja2 template over the product model.  Every value it
reads is recorded: ``P["x"]`` → ``param://x``; ``part("id").name`` → ``part://id#name``;
``req("REQ-001").statement`` → ``req://REQ-001#statement``; ``bom.total_cost`` →
``bom://rollups#total_cost``; ``asm("id").name`` → ``asm://id#name``.  The ``doc:<id>`` rule
stores those keys as ``reads.json`` so the checks rule can flag a stale page when any
recorded value changed after the page was last rendered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jinja2

from napkin2factory.core.loader import Doc, Product
from napkin2factory.core.units import format_quantity, is_quantity
from napkin2factory.geometry.accessors import ParamAccessor, ReadLog, make_accessors


class _Proxy:
    """Attribute access on a model object that records ``<uri>#<path>``."""

    def __init__(self, obj: Any, uri: str, log: ReadLog, path: tuple[str, ...] = ()) -> None:
        self._obj = obj
        self._uri = uri
        self._log = log
        self._path = path

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        obj = self._obj
        if isinstance(obj, dict):
            if name not in obj:
                raise AttributeError(f"{self._uri}#{'.'.join((*self._path, name))} does not exist")
            value = obj[name]
        else:
            if not hasattr(obj, name):
                raise AttributeError(f"{self._uri}#{'.'.join((*self._path, name))} does not exist")
            value = getattr(obj, name)
        path = (*self._path, name)
        self._log.add(f"{self._uri}#{'.'.join(path)}")
        if hasattr(value, "model_fields") or isinstance(value, dict):
            return _Proxy(value, self._uri, self._log, path)
        return _Value(value)

    def __str__(self) -> str:
        if isinstance(self._obj, dict) or not hasattr(self._obj, "name"):
            self._log.add(f"{self._uri}#{'.'.join(self._path)}" if self._path else self._uri)
            return str(self._obj)
        path = (*self._path, "name")
        self._log.add(f"{self._uri}#{'.'.join(path)}")
        return str(self._obj.name)


class _Value:
    """A leaf value that formats quantities nicely."""

    def __init__(self, value: Any) -> None:
        self.value = value

    def __str__(self) -> str:
        if is_quantity(self.value):
            return format_quantity(self.value)
        if self.value is None:
            return ""
        return str(self.value)

    def __format__(self, spec: str) -> str:
        return format(str(self), spec)

    def __eq__(self, other: object) -> bool:
        return bool(self.value == (other.value if isinstance(other, _Value) else other))

    def __bool__(self) -> bool:
        return bool(self.value)

    def __iter__(self) -> Any:
        return iter(self.value)


class _FormattedParams(ParamAccessor):
    """``P["x"]`` in a doc renders as ``"50 mm"``."""

    def __getitem__(self, slug: str) -> Any:
        try:
            return _Value(super().__getitem__(slug))
        except KeyError as exc:  # keep the accessor's hint instead of Jinja's generic message
            raise DocRenderError(str(exc.args[0])) from exc


class _Bom:
    """``bom.total_cost`` → records ``bom://rollups#total_cost``."""

    def __init__(self, rollups: dict[str, Any] | None, log: ReadLog) -> None:
        self._rollups = rollups or {}
        self._log = log

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        self._log.add(f"bom://rollups#{name}")
        val = self._rollups.get(name)
        if name == "total_cost" and val is not None:
            return _Value(f"{val:.2f} USD")
        if name == "total_mass" and val is not None:
            return _Value(f"{val:.3f} kg")
        if name == "max_lead_time" and val is not None:
            return _Value(f"{val:g} d")
        return _Value(val if val is not None else "(not built)")


@dataclass
class Rendered:
    """A rendered page: Markdown text plus the keys it read."""

    markdown: str
    reads: list[str]
    warnings: list[str]


class DocRenderError(ValueError):
    """A manual page failed to render; the message names the page and the expression."""


def make_env() -> jinja2.Environment:
    """Strict Jinja2: undefined names are errors (a typo must not render as blank)."""
    return jinja2.Environment(
        undefined=jinja2.StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )


def render_doc(product: Product, doc: Doc, rollups: dict[str, Any] | None = None) -> Rendered:
    """Render one page's Markdown body with recording accessors."""
    _, iface_accessor, log = make_accessors(product)
    P = _FormattedParams(product, log)
    warnings: list[str] = []

    def part(pid: str) -> _Proxy:
        pid = pid.replace("part://", "")
        if pid not in product.parts:
            raise DocRenderError(f"doc://{doc.meta.id}: part('{pid}') does not exist")
        return _Proxy(product.parts[pid], f"part://{pid}", log)

    def asm(aid: str) -> _Proxy:
        aid = aid.replace("asm://", "")
        if aid not in product.assemblies:
            raise DocRenderError(f"doc://{doc.meta.id}: asm('{aid}') does not exist")
        return _Proxy(product.assemblies[aid], f"asm://{aid}", log)

    def req(rid: str) -> _Proxy:
        rid = rid.replace("req://", "")
        if rid not in product.requirements:
            raise DocRenderError(f"doc://{doc.meta.id}: req('{rid}') does not exist")
        return _Proxy(product.requirements[rid], f"req://{rid}", log)

    def iface(iid: str) -> _Proxy:
        iid = iid.replace("iface://", "")
        return _Proxy(iface_accessor[iid], f"iface://{iid}", log)

    def dec(did: str) -> _Proxy:
        did = did.replace("dec://", "")
        if did not in product.decisions:
            raise DocRenderError(f"doc://{doc.meta.id}: dec('{did}') does not exist")
        return _Proxy(product.decisions[did], f"dec://{did}", log)

    env = make_env()
    try:
        template = env.from_string(doc.body)
        text = template.render(
            P=P,
            part=part,
            asm=asm,
            req=req,
            iface=iface,
            dec=dec,
            bom=_Bom(rollups, log),
            product=_Proxy(product.manifest.product, "manifest://product", log),
        )
    except (jinja2.TemplateError, DocRenderError, KeyError, AttributeError) as exc:
        line = getattr(exc, "lineno", None)
        if line is None:
            tb = exc.__traceback__
            while tb is not None:
                if tb.tb_frame.f_code.co_filename == "<template>":
                    line = tb.tb_lineno
                tb = tb.tb_next
        where = f" line {line}" if line else ""
        raise DocRenderError(f"doc://{doc.meta.id} ({doc.path.name}{where}): {exc}") from exc
    for dep in doc.meta.depends_on:
        log.add(str(dep))
    return Rendered(markdown=text, reads=log.keys, warnings=warnings)
