"""``build_part()`` and ``build_assembly()``: the API the DAG rules call (M2 → M3).

Both are callable without the build graph.  They resolve a part's declarative kit call
(or run its geometry module) through the recording accessors, export every artifact
into ``build/parts/<id>/`` or ``build/assemblies/<id>/``, and return what was read so
the graph can record dependencies.
"""

from __future__ import annotations

import importlib.util
import json
import math
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from napkin2factory.core.errors import N2FError
from napkin2factory.core.loader import Product
from napkin2factory.core.model import Assembly, KitGeometry, ModuleGeometry, Part
from napkin2factory.core.model.style import STYLED_ROLES
from napkin2factory.core.style import STYLE_GEOMETRY_KEY, load_style
from napkin2factory.core.units import UnitError, parse_quantity
from napkin2factory.geometry import kit as kit_mod
from napkin2factory.geometry.accessors import (
    InterfaceAccessor,
    ParamAccessor,
    ReadLog,
    make_accessors,
)
from napkin2factory.geometry.assembly import (
    AssemblyResult,
    FlatInstance,
    assembly_props,
    export_assembly_glb,
    flatten,
    scene_for_assembly,
)
from napkin2factory.geometry.exporters import (
    export_part,
    read_render_notes,
    render_views,
    tessellate,
    write_json,
)
from napkin2factory.geometry.features import PartResult


class GeometryError(N2FError):
    """A part or assembly could not be built; the message names the part and the cause."""

    exit_code = 1


@dataclass
class BuiltPart:
    """A built part plus everything downstream needs."""

    part: Part
    result: PartResult
    props: dict[str, Any]
    reads: list[str]
    out_dir: Path
    duration: float = 0.0
    _tess: tuple[NDArray[np.float64], NDArray[np.int64]] | None = field(default=None, repr=False)

    @property
    def uri(self) -> str:
        """``part://<id>``."""
        return self.part.uri

    @property
    def shape(self) -> Any:
        """The build123d shape."""
        return self.result.shape

    @property
    def tess(self) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
        """Cached tessellation (one mesh per part URI, D13)."""
        if self._tess is None:
            self._tess = tessellate(self.result.shape)
        return self._tess


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

    @property
    def uri(self) -> str:
        """``asm://<id>``."""
        return self.assembly.uri


def resolve_args(args: Any, P: ParamAccessor, I: InterfaceAccessor) -> Any:  # noqa: N803
    """Turn declarative kit args into values: URIs are read through the accessors."""
    if isinstance(args, dict):
        return {k: resolve_args(v, P, I) for k, v in args.items()}
    if isinstance(args, list):
        return [resolve_args(v, P, I) for v in args]
    if isinstance(args, str):
        s = args.strip()
        if s.startswith("param://"):
            return P[s[len("param://") :]]
        if s.startswith("iface://"):
            return I[s[len("iface://") :]]
        try:
            return parse_quantity(s)
        except UnitError:
            return args
    return args


def _load_module(path: Path, name: str) -> Any:
    """Import a product geometry module fresh; sibling helpers in its folder reload too."""
    folder = str(path.parent.resolve())
    if folder not in sys.path:
        sys.path.insert(0, folder)
    # Drop cached product-local modules so a helper edit is seen in the same process (gate-1 B6).
    for mod_name, mod in list(sys.modules.items()):
        mod_file = getattr(mod, "__file__", None)
        if mod_file and str(Path(mod_file).resolve()).startswith(folder):
            del sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise GeometryError(f"cannot import geometry module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise GeometryError(f"{path.name}: import failed: {type(exc).__name__}: {exc}") from exc
    return module


def build_part(
    product: Product, part_id: str, build_dir: Path | None = None, render: bool = True
) -> BuiltPart:
    """Build one part: run its generator or module, export artifacts, return the result.

    Raises:
        GeometryError: naming the part, the generator, and the underlying cause.
    """
    t0 = time.perf_counter()
    if part_id not in product.parts:
        raise GeometryError(
            f"part://{part_id} does not exist; known parts: {', '.join(sorted(product.parts))}"
        )
    part = product.parts[part_id]
    if not part.has_geometry:
        raise GeometryError(f"part://{part_id} has no geometry (it is BOM-only)")
    P, I, log = make_accessors(product)
    # Declared fields the geometry depends on are recorded as selector reads (gate-1 B3), so
    # an edit to an unrelated field (cost, notes) does not rebuild the part.
    for field_name in (
        "geometry",
        "material",
        "mass",
        "process",
        "kind",
        "interfaces",
        "rev",
        "role",
    ):
        log.add(f"{part.uri}#{field_name}")
    # Style geometry defaults reach only parts that opt in with a styling role (N7); for
    # them the geometry-relevant part of style.yaml is a recorded read.
    style = None
    if part.role in STYLED_ROLES:
        style = load_style(product.paths.root)
        log.add(STYLE_GEOMETRY_KEY)
    ctx = kit_mod.KitContext(
        part_id=part_id,
        material_name=part.material.name if part.material else "",
        style=style,
        role=part.role,
    )
    ctx.interfaces = {iu.id: I[iu.id] for iu in part.interfaces}
    g = part.geometry
    try:
        if isinstance(g, KitGeometry):
            args = resolve_args(g.args, P, I)
            result = kit_mod.run(g.kit, args, ctx)
        elif isinstance(g, ModuleGeometry):
            module = _load_module(
                product.paths.model / g.module, f"n2f_geometry_{part_id.replace('-', '_')}"
            )
            if not hasattr(module, "build"):
                raise GeometryError(f"{g.module} must define build(P, I, kit)")
            result = module.build(P, I, kit_mod.Kit(ctx))
            if not isinstance(result, PartResult):
                raise GeometryError(
                    f"{g.module}: build() must return a PartResult, got {type(result).__name__}"
                )
            result.shape.label = part.uri
        else:  # pragma: no cover - guarded by has_geometry
            raise GeometryError(f"part://{part_id}: unsupported geometry {g!r}")
    except GeometryError:
        raise
    except Exception as exc:
        raise GeometryError(
            f"part://{part_id}: geometry failed: {type(exc).__name__}: {exc}"
        ) from exc
    if not result.features.process or result.features.process == "none":
        result.features.process = part.process
    try:
        apply_interfaces(part, result, ctx)
    except Exception as exc:
        raise GeometryError(
            f"part://{part_id}: applying interfaces failed: {type(exc).__name__}: {exc}"
        ) from exc
    out_dir = (build_dir or product.paths.build) / "parts" / part_id
    if out_dir.exists():
        shutil.rmtree(out_dir)  # never leave stale renders/flat patterns behind (gate-1 B4)
    props = export_part(part.uri, result, out_dir, part.material, part.mass, render=render)
    props["rev"] = part.rev
    props["reads"] = log.keys
    write_json(out_dir / "props.json", props)
    built = BuiltPart(part=part, result=result, props=props, reads=log.keys, out_dir=out_dir)
    built.duration = time.perf_counter() - t0
    return built


def apply_interfaces(part: Part, result: PartResult, ctx: kit_mod.KitContext) -> None:
    """Cut every declared bolt-pattern interface into the part and record it (D16, S-013).

    Generators need not know about interfaces: the contract is applied here, identically for
    both parties, in each party's own frame (``Interface.frame_for``).  Mating-face interfaces
    only record the face frame; the checker verifies contact (D29).
    """
    from napkin2factory.core.model import BoltPatternSpec
    from napkin2factory.core.units import mm as _mm
    from napkin2factory.geometry.features import Hole, HolePattern
    from napkin2factory.geometry.kit.hole_pattern import centers_from_spec, cut_pattern

    for iface_id, iface in ctx.interfaces.items():
        already = any(p.interface == iface.uri for p in result.features.patterns)
        frame = iface.frame_for(part.uri)
        if isinstance(iface.spec, BoltPatternSpec):
            if already:
                continue
            all_centers = centers_from_spec(iface.spec, frame)
            diameter = _mm(iface.spec.diameter)
            depth = _mm(iface.spec.depth)
            # A bolt shared by two interfaces (shell → standoff → guard → stand) is one hole:
            # skip centres already cut at the same spot with the same diameter (S-051).
            centers = [
                c
                for c in all_centers
                if not any(
                    abs(h.diameter - diameter) < 1e-6
                    and math.dist(tuple(h.center), tuple(c)) < 0.05
                    for h in result.features.holes
                )
            ]
            result.shape = cut_pattern(result.shape, centers, diameter, tuple(frame.normal), depth)
            if result.flat_pattern is not None:
                unmapped = 0
                for c in centers:
                    xy = result.flat_map(tuple(c)) if result.flat_map is not None else None
                    if xy is None:
                        unmapped += 1
                        continue
                    result.flat_pattern.holes.append(((float(xy[0]), float(xy[1])), diameter))
                    result.flat_pattern.area -= math.pi * (diameter / 2) ** 2
                if unmapped:
                    result.notes.append(
                        f"{unmapped} hole(s) from {iface.uri} are not in the flat pattern "
                        "(the generator cannot map them); add them by hand before cutting"
                    )
            result.features.patterns.append(
                HolePattern(
                    centers=[tuple(c) for c in all_centers],
                    diameter=diameter,
                    frame_origin=tuple(frame.origin),
                    frame_normal=tuple(frame.normal),
                    interface=iface.uri,
                    label=iface_id,
                )
            )
            for i, c in enumerate(centers):
                result.features.holes.append(
                    Hole(
                        center=tuple(c),
                        diameter=diameter,
                        axis=tuple(frame.normal),
                        interface=iface.uri,
                        label=f"{iface_id}-{i + 1}",
                    )
                )
        else:
            result.features.extra.setdefault("mating_faces", []).append(
                {
                    "interface": iface.uri,
                    "origin": list(frame.origin),
                    "normal": list(frame.normal),
                    "width": _mm(iface.spec.width),
                    "depth": _mm(iface.spec.depth),
                }
            )


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

    res = AssemblyResult(notes=["auto-layout: no geometry module; children placed in a row"])
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
    built = BuiltAssembly(
        assembly=asm, result=result, leaves=leaves, props=props, reads=log.keys, out_dir=out_dir
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


def load_built_part(product: Product, part_id: str, build_dir: Path | None = None) -> BuiltPart:
    """Reconstruct a BuiltPart from ``build/parts/<id>/`` (STEP + props) without rebuilding."""
    from build123d import import_step

    build_dir = build_dir or product.paths.build
    out_dir = build_dir / "parts" / part_id
    props_path = out_dir / "props.json"
    if not props_path.is_file() or not (out_dir / "model.step").is_file():
        raise GeometryError(
            f"part://{part_id} has not been built yet; run `n2f build --target geometry`"
        )
    try:
        props: dict[str, Any] = json.loads(props_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise GeometryError(
            f"part://{part_id}: {props_path} is unreadable ({exc}); run `n2f build --clean`"
        ) from exc
    shape = import_step(str(out_dir / "model.step"))
    volume = float(shape.volume) if shape is not None and shape.solids() else 0.0
    if volume <= 0 or abs(volume - float(props.get("volume", 0))) > 0.005 * max(volume, 1.0):
        raise GeometryError(
            f"part://{part_id}: build/parts/{part_id}/model.step does not match props.json "
            f"(volume {volume:.1f} vs {props.get('volume')}); run `n2f build --clean`"
        )
    shape.label = f"part://{part_id}"
    result = PartResult(shape=shape)
    built = BuiltPart(
        part=product.parts[part_id],
        result=result,
        props=props,
        reads=list(props.get("reads", [])),
        out_dir=out_dir,
    )
    mesh = out_dir / "mesh.npz"
    if mesh.is_file():
        data = np.load(mesh)
        built._tess = (data["vertices"], data["triangles"])  # identical bytes for --jobs N
    return built


def load_props(build_dir: Path, uri: str) -> dict[str, Any]:
    """Read ``props.json`` for a part or assembly URI from a build directory."""
    scheme, ident = uri.split("://", 1)
    sub = "parts" if scheme == "part" else "assemblies"
    path = build_dir / sub / ident.split("#")[0] / "props.json"
    if not path.is_file():
        raise FileNotFoundError(f"{uri} has not been built (missing {path})")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


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
