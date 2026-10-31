"""The massing composer: a card's ``massing:`` kit calls → placed silhouettes (N1, N3).

Each call runs the kit generator at ``fidelity="massing"`` (the same validation as a full
build, so an impossible composition fails for real), is placed with a declarative ``at``
(``{x, y, z, rz}``, quantities) and becomes one node ``concept://C-xxx/<as>`` of the
concept's GLB. Artifacts go under ``build/concepts/C-xxx/``: ``massing.glb``, ``props.json``,
``features.json`` and z-buffer ``renders/`` (the agent-eye correctness path, D12).

Concepts sit outside the model: ``param://`` and ``iface://`` references are refused on
cards, and nothing here touches the build graph or its manifest (N1).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from napkin2factory.concepts import CONCEPTS_BUILD_DIR
from napkin2factory.core.errors import N2FError
from napkin2factory.core.model.concepts import ConceptCard, MassingCall
from napkin2factory.core.units import UnitError, parse_quantity

#: Placement keys a card's ``at:`` may use, with the unit a bare number is read in.
AT_KEYS: dict[str, str] = {"x": "mm", "y": "mm", "z": "mm", "rz": "degree"}
#: References that point into a product model; a concept card cannot use them (N1).
MODEL_SCHEMES: tuple[str, ...] = ("param://", "iface://", "part://", "req://")


def concept_build_dir(root: Path, concept_id: str) -> Path:
    """``<product>/build/concepts/<id>/`` (outside the build manifest, N1)."""
    return Path(root) / "build" / CONCEPTS_BUILD_DIR / concept_id


def concept_uri(concept_id: str, name: str) -> str:
    """``concept://C-xxx/<as>``: the GLB node name of one massing call."""
    return f"concept://{concept_id}/{name}"


@dataclass
class Silhouette:
    """A built massing call, shaped like a built part for the assembly exporters."""

    result: Any  # geometry.features.PartResult
    props: dict[str, Any]
    _tess: tuple[NDArray[np.float64], NDArray[np.int64]] | None = field(default=None, repr=False)

    @property
    def tess(self) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
        """Cached tessellation of the silhouette."""
        if self._tess is None:
            from napkin2factory.geometry.exporters import tessellate

            self._tess = tessellate(self.result.shape)
        return self._tess


@dataclass
class MassingPiece:
    """One placed massing call and what screening needs to know about it."""

    name: str
    kit: str
    uri: str
    call: MassingCall
    args: Any  # the generator's validated arguments (lengths in mm)
    built: Silhouette
    location: Any  # build123d Location
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]
    volume: float  # mm³
    process_class: str
    material: str | None = None
    density: float | None = None  # kg/m³
    density_source: str | None = None

    @property
    def size(self) -> tuple[float, float, float]:
        """World bounding-box size (x, y, z) in mm."""
        lo, hi = self.bbox_min, self.bbox_max
        return (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])

    @property
    def mass(self) -> float | None:
        """Silhouette mass in kg (volume × density), ``None`` without a material."""
        return None if self.density is None else self.volume * 1e-9 * self.density


@dataclass
class MassingResult:
    """A composed concept: its pieces, world leaves, props and written artifacts."""

    card_id: str
    pieces: list[MassingPiece]
    leaves: list[Any]  # geometry.assembly.FlatInstance
    props: dict[str, Any]
    out_dir: Path | None = None
    paths: dict[str, Path] = field(default_factory=dict)

    def piece(self, name: str) -> MassingPiece | None:
        """The piece whose ``as`` is ``name``, if any."""
        return next((p for p in self.pieces if p.name == name), None)

    @property
    def bbox_min(self) -> tuple[float, float, float]:
        """World bounding-box minimum over every piece (mm)."""
        return (
            min(p.bbox_min[0] for p in self.pieces),
            min(p.bbox_min[1] for p in self.pieces),
            min(p.bbox_min[2] for p in self.pieces),
        )

    @property
    def bbox_max(self) -> tuple[float, float, float]:
        """World bounding-box maximum over every piece (mm)."""
        return (
            max(p.bbox_max[0] for p in self.pieces),
            max(p.bbox_max[1] for p in self.pieces),
            max(p.bbox_max[2] for p in self.pieces),
        )

    @property
    def size(self) -> tuple[float, float, float]:
        """Overall width (x), depth (y), height (z) in mm."""
        lo, hi = self.bbox_min, self.bbox_max
        return (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])

    @property
    def volume(self) -> float:
        """Sum of the silhouette volumes (mm³)."""
        return sum(p.volume for p in self.pieces)

    @property
    def without_material(self) -> list[str]:
        """Names of the calls that declare no ``material`` (so carry no mass)."""
        return [p.name for p in self.pieces if p.density is None]

    @property
    def mass(self) -> float | None:
        """Total silhouette mass (kg) when every call declares a material, else ``None``."""
        if not self.pieces or self.without_material:
            return None
        return sum(p.mass or 0.0 for p in self.pieces)


def _refuse_model_refs(card_id: str, call: MassingCall, value: Any, where: str) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            _refuse_model_refs(card_id, call, v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _refuse_model_refs(card_id, call, v, f"{where}[{i}]")
    elif isinstance(value, str) and value.strip().startswith(MODEL_SCHEMES):
        raise N2FError(
            f"{card_id}/{call.as_}: {where} is {value.strip()!r}, but a concept card cannot "
            "refer into the product model (concepts sit outside it) — write the number "
            f"itself, e.g. `540 mm`, in concepts/{card_id}.yaml"
        )


def _location(card_id: str, call: MassingCall) -> Any:
    from napkin2factory.geometry.assembly import _location as make_location

    at = call.at or {}
    unknown = sorted(set(at) - set(AT_KEYS))
    if unknown:
        raise N2FError(
            f"{card_id}/{call.as_}: at: has {', '.join(unknown)}; a placement takes "
            f"{', '.join(AT_KEYS)} (e.g. at: {{x: 300 mm, z: 700 mm, rz: 90 deg}})"
        )
    values: dict[str, float] = {}
    for key, unit in AT_KEYS.items():
        raw = at.get(key, 0)
        try:
            q = parse_quantity(raw, unit)
            values[key] = float(q.to(unit).magnitude)
        except (UnitError, Exception) as exc:  # pint DimensionalityError and friends
            raise N2FError(
                f"{card_id}/{call.as_}: at.{key} = {raw!r} is not a {unit} quantity ({exc})"
            ) from exc
    return make_location(
        translate=(values["x"], values["y"], values["z"]), rotate=(0.0, 0.0, values["rz"])
    )


def _build_piece(card: ConceptCard, call: MassingCall) -> MassingPiece:
    from napkin2factory.geometry import kit
    from napkin2factory.geometry.assembly import transform_points
    from napkin2factory.geometry.materials import density_kg_m3

    prefix = f"{card.id}/{call.as_}"
    _refuse_model_refs(card.id, call, call.args, "args")
    _refuse_model_refs(card.id, call, call.at or {}, "at")
    location = _location(card.id, call)
    ctx = kit.KitContext(part_id=call.as_, material_name=call.material or "", fidelity="massing")
    try:
        result = kit.run(call.kit, call.args, ctx)
        args = kit.get_module(call.kit).ARGS.model_validate(call.args)
    except Exception as exc:
        raise kit.KitError(f"{prefix}: {exc}") from exc
    shape = result.shape
    volume = float(shape.volume)
    density: float | None = None
    density_source: str | None = None
    if call.material:
        density, density_source = density_kg_m3(call.material)
    c = shape.center()
    built = Silhouette(
        result=result,
        props={
            "mass": 0.0 if density is None else volume * 1e-9 * density,
            "volume": volume,
            "centroid": {"x": c.X, "y": c.Y, "z": c.Z},
        },
    )
    pts = transform_points(built.tess[0], location)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    return MassingPiece(
        name=call.as_,
        kit=call.kit,
        uri=concept_uri(card.id, call.as_),
        call=call,
        args=args,
        built=built,
        location=location,
        bbox_min=(float(lo[0]), float(lo[1]), float(lo[2])),
        bbox_max=(float(hi[0]), float(hi[1]), float(hi[2])),
        volume=volume,
        process_class=call.process_class or str(result.features.process),
        material=call.material,
        density=density,
        density_source=density_source,
    )


def _props(card_id: str, pieces: list[MassingPiece], leaves: list[Any]) -> dict[str, Any]:
    from napkin2factory.geometry.assembly import assembly_props

    props = assembly_props(leaves)
    missing = [p.name for p in pieces if p.density is None]
    if missing:
        props.pop("mass", None)
        props["mass_missing"] = missing
        props["mass_source"] = "no mass: these calls declare no material: " + ", ".join(missing)
    else:
        props["mass_source"] = "silhouette volume × density per call"
    props["concept"] = card_id
    props["fidelity"] = "massing"
    props["pieces"] = {
        p.name: {
            "kit": p.kit,
            "uri": p.uri,
            "bbox": {
                "x": round(p.size[0], 4),
                "y": round(p.size[1], 4),
                "z": round(p.size[2], 4),
                "min": [round(v, 4) for v in p.bbox_min],
                "max": [round(v, 4) for v in p.bbox_max],
            },
            "volume": round(p.volume, 3),
            "process_class": p.process_class,
            **(
                {
                    "material": p.material,
                    "mass": round(p.mass or 0.0, 6),
                    "density_source": p.density_source,
                }
                if p.density is not None
                else {}
            ),
        }
        for p in pieces
    }
    return props


def write_artifacts(result: MassingResult, out_dir: Path, render: bool = True) -> dict[str, Path]:
    """Write ``massing.glb``, ``props.json``, ``features.json`` and ``renders/`` to ``out_dir``."""
    from napkin2factory.geometry.assembly import export_assembly_glb, scene_for_assembly
    from napkin2factory.geometry.exporters import render_views, write_json
    from napkin2factory.geometry.features import to_json

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    top = f"concept://{result.card_id}"
    paths = {
        "glb": export_assembly_glb(top, result.leaves, [], out_dir / "massing.glb"),
        "props": write_json(out_dir / "props.json", result.props),
    }
    features = [
        {
            "as": p.name,
            "kit": p.kit,
            "uri": p.uri,
            "fidelity": "massing",
            "process_class": p.process_class,
            "material": p.material,
            "features": to_json(p.built.result.features),
            "dims": to_json(p.built.result.dims),
            "notes": list(p.built.result.notes),
        }
        for p in result.pieces
    ]
    paths["features"] = write_json(out_dir / "features.json", features)
    if render:
        views = render_views(scene_for_assembly(result.leaves), out_dir / "renders")
        paths.update({f"render_{k}": v for k, v in views.items()})
    result.out_dir = out_dir
    result.paths = paths
    return paths


def compose(
    card: ConceptCard, root: Path | None = None, *, write: bool = True, render: bool = True
) -> MassingResult:
    """Run the card's massing calls, place them, and (by default) write the artifacts.

    Args:
        card: the concept card.
        root: the product folder; artifacts go to ``build/concepts/<id>/`` under it.
        write: write the artifacts (needs ``root``).
        render: also write the z-buffer renders.

    Raises:
        N2FError: the card has no massing, repeats an ``as`` name, refers into the model,
            or has a bad placement.
        KitError: a generator refused the call (the message starts ``C-xxx/<as>:``).
    """
    from napkin2factory.geometry.assembly import FlatInstance

    if not card.massing:
        raise N2FError(
            f"{card.id} has no massing yet — add kit calls under `massing:` in "
            f"concepts/{card.id}.yaml, e.g. "
            "- {kit: enclosure, as: body, args: {length: 540 mm, width: 540 mm, "
            "height: 620 mm, thickness: 1.5 mm}}"
        )
    seen: set[str] = set()
    for call in card.massing:
        if call.as_ in seen:
            raise N2FError(
                f"{card.id}: two massing calls are named {call.as_!r}; give each a "
                "different `as:` name"
            )
        seen.add(call.as_)
    pieces = [_build_piece(card, call) for call in card.massing]
    leaves = [FlatInstance(p.uri, p.uri, p.location, None, p.built) for p in pieces]
    result = MassingResult(card.id, pieces, leaves, _props(card.id, pieces, leaves))
    if write:
        if root is None:
            raise N2FError("compose(write=True) needs the product folder")
        write_artifacts(result, concept_build_dir(root, card.id), render=render)
    return result


__all__ = [
    "AT_KEYS",
    "MassingPiece",
    "MassingResult",
    "Silhouette",
    "compose",
    "concept_build_dir",
    "concept_uri",
    "write_artifacts",
]
