"""assemblies/<id>.yaml schema (decision D18)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import (
    BeforeValidator,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from napkin2factory.core.model.base import (
    AsmUri,
    IfaceUri,
    Model,
    PartUri,
    Quantity,
    ReqUri,
    Slug,
    table_check,
)
from napkin2factory.core.model.parts import ModuleGeometry

if TYPE_CHECKING:
    from napkin2factory.core.errors import Problems
    from napkin2factory.core.loader import Product


def _asm_geometry(v: Any) -> Any:
    if v is None or v == "none":
        return "none"
    if isinstance(v, ModuleGeometry):
        return v
    if isinstance(v, dict) and "module" in v:
        return ModuleGeometry.model_validate(v)
    raise ValueError("assembly geometry is {module: geometry/<file>.py} or 'none'")


def _drivers() -> list[str]:
    from napkin2factory.core.registry import registry

    return list(registry().drivers())


#: Why a sub-assembly is built on its own (P7): ``core/data/drivers.yaml`` plus the domains'
#: (F6), each with its owner words (``core.build_units.driver_words``).
Driver = Annotated[str, table_check("build-unit driver", _drivers)]


def __getattr__(name: str) -> Any:
    """``DRIVERS`` (every driver, table order) is read from the registry on each access."""
    if name == "DRIVERS":
        return tuple(_drivers())
    raise AttributeError(name)


def _drop_defaults(data: Any, defaults: dict[str, Any]) -> Any:
    """Leave out fields still at their v0.4 defaults, so a v0.3 file dumps as before (P14)."""
    if isinstance(data, dict):
        for key, default in defaults.items():
            if key in data and data[key] == default:
                data.pop(key)
    return data


class Child(Model):
    """One membership line: a part or a sub-assembly with a quantity.

    ``spare`` says why the line holds more interface hardware than its joints need (P9; the
    hardware check then passes the surplus); ``loose`` marks a line shipped loose for the
    installer instead of fitted in the build step (S-105).
    """

    part: PartUri | None = None
    asm: AsmUri | None = None
    qty: int = 1
    spare: str | None = None
    loose: bool = False

    @field_validator("spare")
    @classmethod
    def _spare_has_reason(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError('spare needs a reason, e.g. spare: "two extra for the installer"')
        return v

    @model_serializer(mode="wrap")
    def _dump(self, handler: SerializerFunctionWrapHandler) -> Any:
        return _drop_defaults(handler(self), {"spare": None, "loose": False})

    @model_validator(mode="after")
    def _one_of(self) -> Child:
        if (self.part is None) == (self.asm is None):
            raise ValueError("a child is exactly one of {part: part://x} or {asm: asm://y}")
        if self.qty < 1:
            raise ValueError("qty must be at least 1")
        return self

    @property
    def uri(self) -> str:
        """The child's URI string."""
        return str(self.part if self.part is not None else self.asm)


class Exploded(Model):
    """Viewer hint for the exploded mode."""

    axis: Literal["x", "y", "z"] = "z"
    spacing: Quantity = "80 mm"


class Assembly(Model):
    """Membership and quantities (the BOM structure); geometry is Python.

    ``build`` and ``driver`` (P7) say how a sub-assembly is built and why: a ``unit`` is a
    step of the build plan of its own, a ``phantom`` only groups lines and folds into its
    parent's step, an ``external`` one is a stub for work done elsewhere (F11): supplied,
    not built here, with its ``ports:`` and no children (:func:`validate_refs`).  The top
    assembly is always built and needs neither.
    """

    id: Slug
    rev: str = "A"
    name: str
    build: Literal["unit", "phantom", "external"] = "unit"
    driver: list[Driver] = Field(default_factory=list)
    geometry: Annotated[ModuleGeometry | Literal["none"], BeforeValidator(_asm_geometry)] = "none"
    children: list[Child] = Field(default_factory=list)
    exploded: Exploded = Field(default_factory=Exploded)
    # P4: the joints that cross this assembly's boundary (one part inside, one outside),
    # each an interface between two parts; the loader requires exactly those (S-107).
    ports: list[IfaceUri] = Field(default_factory=list)
    satisfies: list[ReqUri] = Field(default_factory=list)
    notes: str | None = None

    @model_serializer(mode="wrap")
    def _dump(self, handler: SerializerFunctionWrapHandler) -> Any:
        return _drop_defaults(handler(self), {"build": "unit", "driver": []})

    @property
    def uri(self) -> str:
        """``asm://<id>``."""
        return f"asm://{self.id}"


def _fix(aid: str) -> str:
    return f"model/assemblies/{aid}.yaml"


def validate_refs(product: Product, problems: Problems) -> set[str]:
    """Check every external stub and every ``external`` scope entry (F11); return the stubs.

    A stub (``build: external``) is a sub-assembly with no children and at least one port.
    Its ports are checked like any port (P4, S-107), with the stub itself as the party
    inside it, since it holds no parts: each listed interface joins the stub to a part
    outside it, and every interface naming the stub is listed.  A domain whose scope is
    ``external`` needs a stub (the one its ``stub:`` names, else any): the error names
    the file to add or fix.  Interfaces naming a stub are left out of the loader's own
    port rules, which this replaces for them.
    """
    from napkin2factory.core.tree import AssemblyTree

    stubs = {aid for aid, a in product.assemblies.items() if a.build == "external"}
    tops = set(AssemblyTree(product.assemblies).tops()) if product.assemblies else set()
    for aid in sorted(stubs):
        asm = product.assemblies[aid]
        file = product.files.get(asm.uri, product.paths.assemblies / f"{aid}.yaml")
        if aid in tops:
            problems.add(
                file,
                asm.uri,
                "`build: external` marks a module supplied from elsewhere, but nothing uses "
                "this assembly",
                f"list it as a child of the assembly it fits into, e.g. `- {{asm: {asm.uri}}}`",
                rule="external",
            )
        if asm.children:
            problems.add(
                file,
                asm.uri,
                "a module supplied from elsewhere (`build: external`) has no children here: "
                "its parts are not modelled in this product",
                f"remove `children:` from {_fix(aid)}, or set `build: unit` to build it here",
                rule="external",
            )
        if not asm.ports:
            problems.add(
                file,
                asm.uri,
                "a module supplied from elsewhere (`build: external`) needs its ports: the "
                "joints by which it fits this product",
                f"add `ports: [iface://<id>]` to {_fix(aid)}, one interface per joint, each "
                f"naming {asm.uri} and the part it fits to",
                rule="external",
            )
        naming = {
            i.uri for i in product.interfaces.values() if asm.uri in {str(p) for p in i.parties}
        }
        listed = {str(u) for u in asm.ports}
        for iuri in sorted(naming - listed):
            problems.add(
                file,
                asm.uri,
                f"{iuri} joins this module to the product, but is not listed under `ports:`",
                f"add {iuri} to `ports:` in {_fix(aid)}",
                rule="port",
            )
        for iuri in sorted(listed - naming):
            iid = iuri.removeprefix("iface://")
            if iid not in product.interfaces:
                continue  # the unresolved reference is already reported
            problems.add(
                file,
                asm.uri,
                f"lists {iuri} under `ports:`, but that joint does not name this module",
                f"name {asm.uri} as one party of {iuri} (model/interfaces/{iid}.yaml), or "
                f"remove it from `ports:` in {_fix(aid)}",
                rule="port",
            )
    for iface in product.interfaces.values():
        parties = [str(p) for p in iface.parties]
        on_stubs = [p for p in parties if p.removeprefix("asm://") in stubs]
        if len(on_stubs) == 2 or (on_stubs and not any(p.startswith("part://") for p in parties)):
            problems.add(
                product.files.get(iface.uri, product.paths.interfaces / f"{iface.id}.yaml"),
                iface.uri,
                "a joint to a module supplied from elsewhere joins it to a part of this product",
                "name the part it fits to as the other party",
                rule="port",
            )
    _validate_external_scope(product, problems, stubs)
    return stubs


def _validate_external_scope(product: Product, problems: Problems, stubs: set[str]) -> None:
    """Each ``external`` domain has its stub; each scope decision exists (F11)."""
    manifest_file = product.paths.manifest
    for domain, entry in product.manifest.scope.items():
        if entry.decision is not None and entry.decision not in product.decisions:
            if "dec" not in product.broken_schemes:
                problems.add(
                    manifest_file,
                    f"scope.{domain}",
                    f"names decision {entry.decision}, which model/decisions.yaml does not hold",
                    "record the decision in model/decisions.yaml (why this domain is "
                    f"{entry.state}), or fix the id",
                    rule="scope",
                )
        if entry.state != "external":
            continue
        if entry.stub is not None:
            sid = entry.stub.id
            if sid not in product.assemblies:
                if f"asm://{sid}" not in product.broken:
                    problems.add(
                        manifest_file,
                        f"scope.{domain}",
                        f"`stub: {entry.stub}` names no assembly",
                        f"add {_fix(sid)} with `build: external`, its `ports:` and no "
                        "children, or fix the name",
                        rule="external",
                    )
            elif sid not in stubs:
                problems.add(
                    product.files.get(f"asm://{sid}", manifest_file),
                    f"scope.{domain}",
                    f"{entry.stub} stands for {domain} work done elsewhere, but it is "
                    f"`build: {product.assemblies[sid].build}`",
                    f"set `build: external` in {_fix(sid)} (ports, no children)",
                    rule="external",
                )
        elif not stubs and not any(u.startswith("asm://") for u in product.broken):
            problems.add(
                manifest_file,
                f"scope.{domain}",
                f"{domain} is done elsewhere (`state: external`), but no module stands for "
                "it in this product",
                "add model/assemblies/<id>.yaml with `build: external`, its `ports:` (the "
                "joints it fits by) and no children, list it in the assembly it fits into, "
                "and name it here as `stub: asm://<id>`",
                rule="external",
            )
