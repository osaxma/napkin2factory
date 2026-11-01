"""``build_part()``: one part from its kit call or geometry module, exported (M2).

Callable without the build graph: it resolves the part's declarative kit call (or runs its
geometry module) through the recording accessors, cuts its interfaces, exports every
artifact into ``build/parts/<id>/`` and returns what was read so the graph can record
dependencies.  Split from ``geometry/build.py`` (F15, S-131), which re-exports it.
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
from napkin2factory.core.model import KitGeometry, ModuleGeometry, Part
from napkin2factory.core.model.style import STYLED_ROLES
from napkin2factory.core.style import STYLE_GEOMETRY_KEY, load_style
from napkin2factory.core.units import UnitError, parse_quantity
from napkin2factory.geometry import kit as kit_mod
from napkin2factory.geometry.accessors import (
    InterfaceAccessor,
    ParamAccessor,
    make_accessors,
)
from napkin2factory.geometry.exporters import (
    export_part,
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
    iface_reads: list[str] = field(default_factory=list)  # read only through an interface (P5)
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
    built = BuiltPart(
        part=part,
        result=result,
        props=props,
        reads=log.keys,
        out_dir=out_dir,
        iface_reads=log.iface_reads,
    )
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
        elif iface.kind == "mating-face":  # a domain's interface kind cuts nothing (F6)
            result.features.extra.setdefault("mating_faces", []).append(
                {
                    "interface": iface.uri,
                    "origin": list(frame.origin),
                    "normal": list(frame.normal),
                    "width": _mm(iface.spec.width),
                    "depth": _mm(iface.spec.depth),
                }
            )


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
