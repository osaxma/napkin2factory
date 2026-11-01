"""``build_assembly()``: one assembly from its built children, exported (M3).

Callable without the build graph: it runs the assembly's geometry module (or lays the
children out in a row), exports ``build/assemblies/<id>/`` and returns what was read.
``build_geometry`` builds every part, then every assembly in dependency order.  Split from
``geometry/build.py`` (F15, S-131), which re-exports it.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.core.loader import Product
from napkin2factory.core.model import Assembly, ModuleGeometry
from napkin2factory.geometry.accessors import (
    ReadLog,
    make_accessors,
)
from napkin2factory.geometry.assembly import (
    AssemblyResult,
    FlatInstance,
    assembly_props,
    exploded_scene,
    export_assembly_glb,
    flatten,
    scene_for_assembly,
)
from napkin2factory.geometry.build_part import (
    BuiltPart,
    GeometryError,
    _load_module,
    build_part,
    load_built_part,
)
from napkin2factory.geometry.exporters import (
    read_render_notes,
    render_views,
    write_json,
)
from napkin2factory.geometry.render import rasterize, write_png


@dataclass
class BuiltAssembly:
    """A built assembly: placements, flattened instances, props."""

    assembly: Assembly
    result: AssemblyResult
    leaves: list[FlatInstance]
    props: dict[str, Any]
    reads: list[str]
    out_dir: Path
    duration: float = 0.0
    iface_reads: list[str] = field(default_factory=list)  # read only through an interface (P5)

    @property
    def uri(self) -> str:
        """``asm://<id>``."""
        return self.assembly.uri


class PartsView:
    """``parts["l-bracket"]`` inside an assembly module: built parts and sub-assemblies by id."""

    def __init__(
        self, parts: dict[str, BuiltPart], asms: dict[str, BuiltAssembly], log: ReadLog
    ) -> None:
        self._parts = parts
        self._asms = asms
        self._log = log

    def __getitem__(self, key: str) -> Any:
        key = key.replace("part://", "").replace("asm://", "")
        if key in self._parts:
            self._log.add(f"part://{key}")
            return self._parts[key]
        if key in self._asms:
            self._log.add(f"asm://{key}")
            return self._asms[key]
        raise KeyError(
            f"{key!r} is not a built part or sub-assembly of this assembly; "
            f"children: {sorted(self._parts) + sorted(self._asms)}"
        )

    def __contains__(self, key: str) -> bool:
        key = key.replace("part://", "").replace("asm://", "")
        return key in self._parts or key in self._asms


def _auto_layout(
    asm: Assembly, parts: dict[str, BuiltPart], asms: dict[str, BuiltAssembly]
) -> AssemblyResult:
    """Assemblies without a module: lay children out in a row along X (a placeholder, flagged)."""
    from napkin2factory.geometry.assembly import place

    # an empty module stub has nothing to lay out: the "module has parts" rule speaks for
    # it instead of a layout warning (P10, S-112)
    notes = ["auto-layout: no geometry module; children placed in a row"] if asm.children else []
    res = AssemblyResult(notes=notes)
    x = 0.0
    for child in asm.children:
        key = child.part.id if child.part is not None else (child.asm.id if child.asm else "")
        built = parts.get(key) or asms.get(key)
        if built is None:
            continue
        width = float(built.props["bbox"]["x"]) + 20.0
        for _ in range(child.qty):
            res.add(place(child.uri, built, translate=(x, 0.0, 0.0)))
            x += width
    return res


def build_assembly(
    product: Product,
    asm_id: str,
    parts: dict[str, BuiltPart],
    asms: dict[str, BuiltAssembly] | None = None,
    build_dir: Path | None = None,
    render: bool = True,
) -> BuiltAssembly:
    """Build one assembly from already-built children; export GLB, props, instances, renders."""
    t0 = time.perf_counter()
    if asm_id not in product.assemblies:
        raise GeometryError(f"asm://{asm_id} does not exist")
    asm = product.assemblies[asm_id]
    asms = asms or {}
    P, I, log = make_accessors(product)
    for field_name in ("children", "geometry", "rev", "exploded"):
        log.add(f"{asm.uri}#{field_name}")
    children_parts = {
        c.part.id: parts[c.part.id]
        for c in asm.children
        if c.part is not None and c.part.id in parts
    }
    children_asms = {
        c.asm.id: asms[c.asm.id] for c in asm.children if c.asm is not None and c.asm.id in asms
    }
    for c in asm.children:
        key = c.uri
        if c.part is not None and c.part.id not in parts and product.parts[c.part.id].has_geometry:
            raise GeometryError(f"asm://{asm_id}: child {key} has not been built")
        if c.asm is not None and c.asm.id not in asms:
            raise GeometryError(f"asm://{asm_id}: sub-assembly {key} has not been built")
    view = PartsView(children_parts, children_asms, log)
    try:
        if isinstance(asm.geometry, ModuleGeometry):
            module = _load_module(
                product.paths.model / asm.geometry.module, f"n2f_asm_{asm_id.replace('-', '_')}"
            )
            if not hasattr(module, "build"):
                raise GeometryError(f"{asm.geometry.module} must define build(P, I, parts)")
            result = module.build(P, I, view)
            if not isinstance(result, AssemblyResult):
                raise GeometryError(f"{asm.geometry.module}: build() must return an AssemblyResult")
        else:
            result = _auto_layout(asm, children_parts, children_asms)
            for key in children_parts:
                log.add(f"part://{key}")
            for key in children_asms:
                log.add(f"asm://{key}")
    except GeometryError:
        raise
    except Exception as exc:
        raise GeometryError(
            f"asm://{asm_id}: assembly failed: {type(exc).__name__}: {exc}"
        ) from exc
    for p in result.instances:
        if p.uri.replace("part://", "").replace("asm://", "") not in view:
            raise GeometryError(f"asm://{asm_id}: placed {p.uri} which is not a declared child")
    leaves, groups = flatten(result, asm.uri)
    out_dir = (build_dir or product.paths.build) / "assemblies" / asm_id
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    export_assembly_glb(asm.uri, leaves, groups, out_dir / "model.glb")
    props = assembly_props(leaves)
    props["uri"] = asm.uri
    props["rev"] = asm.rev
    props["reads"] = log.keys
    props["declared_counts"] = declared_counts(product, asm_id)
    props["notes"] = list(result.notes)
    write_json(out_dir / "props.json", props)
    write_json(out_dir / "instances.json", instance_records(leaves))
    if render:
        # section through the mass centroid: a body on a tall stand is cut where the mass is
        render_views(
            scene_for_assembly(leaves), out_dir / "renders", section_z=props["centroid"]["z"]
        )
        # P8: the exploded picture for the unit's assembly sheet (the viewer's full explode)
        spacing = float(asm.exploded.spacing.to("mm").magnitude)
        write_png(
            out_dir / "renders" / "exploded.png",
            rasterize(exploded_scene(leaves, groups, asm.exploded.axis, spacing), "iso"),
        )
    built = BuiltAssembly(
        assembly=asm,
        result=result,
        leaves=leaves,
        props=props,
        reads=log.keys,
        out_dir=out_dir,
        iface_reads=log.iface_reads,
    )
    built.duration = time.perf_counter() - t0
    return built


def instance_records(leaves: list[FlatInstance]) -> list[dict[str, Any]]:
    """The rows of ``instances.json``: one per leaf occurrence, in the assembly's frame."""
    return [
        {
            "node": leaf.node,
            "uri": leaf.uri,
            "parent": leaf.parent,
            "translation": list(_trs(leaf)[0]),
            "rotation": list(_trs(leaf)[1]),
            # how it was placed: the P1 warning and the build marks (parts placed by
            # coordinates) read these; no placement order, so reordering the placement code
            # leaves this file unchanged (S-030, S-106)
            "label": leaf.label,
            "via": leaf.via,
        }
        for leaf in leaves
    ]


def _trs(
    leaf: FlatInstance,
) -> tuple[tuple[float, float, float], tuple[float, float, float, float]]:
    from napkin2factory.geometry.assembly import location_to_trs

    return location_to_trs(leaf.location)


def declared_counts(product: Product, asm_id: str, multiplier: int = 1) -> dict[str, int]:
    """Leaf part counts implied by the assembly YAML, multiplied through sub-assemblies (D18)."""
    out: dict[str, int] = {}
    asm = product.assemblies[asm_id]
    for c in asm.children:
        if c.part is not None:
            if product.parts[c.part.id].has_geometry:
                out[c.uri] = out.get(c.uri, 0) + c.qty * multiplier
        elif c.asm is not None:
            for k, v in declared_counts(product, c.asm.id, multiplier * c.qty).items():
                out[k] = out.get(k, 0) + v
    return dict(sorted(out.items()))


def assembly_order(product: Product) -> list[str]:
    """Assemblies in dependency order (children before parents)."""
    order: list[str] = []
    seen: set[str] = set()

    def visit(aid: str) -> None:
        if aid in seen:
            return
        seen.add(aid)
        for c in product.assemblies[aid].children:
            if c.asm is not None:
                visit(c.asm.id)
        order.append(aid)

    for aid in sorted(product.assemblies):
        visit(aid)
    return order


def build_geometry(
    product: Product,
    only_part: str | None = None,
    build_dir: Path | None = None,
    render: bool = True,
    log: Any = None,
) -> tuple[dict[str, BuiltPart], dict[str, BuiltAssembly]]:
    """Build every part with geometry, then every assembly (the M2 thin path)."""
    parts: dict[str, BuiltPart] = {}
    asms: dict[str, BuiltAssembly] = {}
    ids = [only_part] if only_part else sorted(p.id for p in product.parts_with_geometry())
    for pid in ids:
        parts[pid] = build_part(product, pid, build_dir, render)
        if log:
            log(f"part://{pid}: {parts[pid].duration:.1f}s")
    if only_part:
        return parts, asms
    for aid in assembly_order(product):
        asms[aid] = build_assembly(product, aid, parts, asms, build_dir, render)
        if log:
            log(f"asm://{aid}: {asms[aid].duration:.1f}s, {asms[aid].props['instances']} instances")
    write_json(
        (build_dir or product.paths.build) / "geometry.json",
        {
            "parts": {k: v.props for k, v in parts.items()},
            "assemblies": {k: v.props for k, v in asms.items()},
        },
    )
    return parts, asms


def render_notes(product: Product, build_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """What the renders of every built part and assembly had to remark, by URI (S-088).

    Read from each ``renders/notes.json`` (written by
    :func:`~napkin2factory.geometry.exporters.render_views`), so a part that was up to date
    and not rebuilt still reports its notes. Parts and assemblies without notes are left out.
    """
    build_dir = build_dir or product.paths.build
    out: dict[str, dict[str, Any]] = {}
    for sub, ids, scheme in (
        ("parts", sorted(product.parts), "part"),
        ("assemblies", sorted(product.assemblies), "asm"),
    ):
        for ident in ids:
            notes = read_render_notes(build_dir / sub / ident / "renders")
            if notes["notes"]:
                out[f"{scheme}://{ident}"] = notes
    return out


def _owner_name(product: Product, uri: str) -> str:
    """A part or assembly's name for an owner, from a URI or GLB node (``part://x#2``)."""
    scheme, _, ident = uri.partition("://")
    ident = ident.split("#")[0].split("/")[0]
    if scheme == "part" and ident in product.parts:
        return product.parts[ident].name
    if scheme == "asm" and ident in product.assemblies:
        return product.assemblies[ident].name
    return ident or uri


def render_note_lines(product: Product, notes: dict[str, dict[str, Any]]) -> list[str]:
    """:func:`render_notes` in plain owner words: one line per picture that has a remark."""
    lines: list[str] = []
    for uri, entry in notes.items():
        where = _owner_name(product, uri)
        names = list(dict.fromkeys(_owner_name(product, u) for u in entry.get("uncapped", [])))
        if names == [where]:
            lines.append(
                f"Cut-away picture of {where}: its 3D surface has a gap, so the cut is drawn "
                "open instead of filled in. Check the shape if it should be solid."
            )
        elif names:
            many = len(names) > 1
            lines.append(
                f"Cut-away picture of {where}: {', '.join(names)} {'have' if many else 'has'} "
                f"a gap in {'their' if many else 'its'} 3D surface, so the cut is drawn open "
                "instead of filled in. Check the shape if it should be solid."
            )
        else:  # a remark of a kind this wording does not know yet: point at the file
            lines.append(f"Pictures of {where}: the renderer left a remark in renders/notes.json.")
    return lines


def load_built_assembly(
    product: Product,
    asm_id: str,
    build_dir: Path | None = None,
    parts: dict[str, BuiltPart] | None = None,
) -> BuiltAssembly:
    """Reconstruct a BuiltAssembly from ``build/assemblies/<id>/`` without rebuilding (S-049).

    Used when a parent assembly must rebuild but this sub-assembly's run was skipped as up to
    date.  The leaf instances in ``instances.json`` are in the sub-assembly's own frame, so
    they are placed directly; nested groups inside it are flattened one level (the parent's
    GLB still groups everything under this assembly's node).  Parts are loaded from disk
    through ``parts`` (filled in place) so each part is imported once per build.

    Raises:
        GeometryError: when the assembly has not been built or its files are unreadable.
    """
    from build123d import Location
    from OCP.gp import gp_Quaternion, gp_Trsf, gp_Vec

    from napkin2factory.geometry.assembly import flatten, place

    build_dir = build_dir or product.paths.build
    out_dir = build_dir / "assemblies" / asm_id
    props_path, inst_path = out_dir / "props.json", out_dir / "instances.json"
    if not props_path.is_file() or not inst_path.is_file():
        raise GeometryError(
            f"asm://{asm_id} has not been built yet; run `n2f build --target geometry`"
        )
    try:
        props: dict[str, Any] = json.loads(props_path.read_text(encoding="utf-8"))
        instances = json.loads(inst_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise GeometryError(
            f"asm://{asm_id}: {out_dir} is unreadable ({exc}); run `n2f build --clean`"
        ) from exc
    cache: dict[str, BuiltPart] = parts if parts is not None else {}
    result = AssemblyResult()
    for inst in instances:
        part_id = str(inst["uri"]).replace("part://", "")
        if part_id not in cache:
            cache[part_id] = load_built_part(product, part_id, build_dir)
        x, y, z, w = (float(v) for v in inst["rotation"])
        trsf = gp_Trsf()
        trsf.SetRotation(gp_Quaternion(x, y, z, w))
        trsf.SetTranslationPart(gp_Vec(*(float(v) for v in inst["translation"])))
        placed = place(inst["uri"], cache[part_id], Location(trsf), label=inst.get("label"))
        placed.via = str(inst.get("via", placed.via))
        result.add(placed)
    asm = product.assemblies[asm_id]
    leaves, _groups = flatten(result, asm.uri)
    return BuiltAssembly(
        assembly=asm,
        result=result,
        leaves=leaves,
        props=props,
        reads=list(props.get("reads", [])),
        out_dir=out_dir,
    )
