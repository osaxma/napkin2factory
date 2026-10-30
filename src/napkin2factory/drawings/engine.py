"""``drawing:<id>`` run: one A3 SVG per part, plus the flat-pattern DXF for sheet metal (D11).

Outputs in ``build/drawings/``:

* ``<id>.svg`` — third-angle front/top/right views with hidden lines, an iso view, the
  flat pattern (sheet metal), overall and generator dimensions, a hole table and the
  title block.  See :mod:`napkin2factory.drawings.sheet` for the layout.
* ``<id>-flat.dxf`` — every part with a flat pattern (:mod:`napkin2factory.drawings.dxf`).
* ``<id>.json`` — scale, views, dimension and hole counts (for tests and the report).

The output hash covers the SVG without the title-block date (D14), so re-building the
same geometry from a different snapshot does not invalidate anything downstream.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from napkin2factory import __version__
from napkin2factory.core.graph.hashing import sha256_json, sha256_text
from napkin2factory.drawings.sheet import SheetInput, TitleFields, compose
from napkin2factory.drawings.views import ALL_VIEWS, ORTHO_VIEWS, ortho_extents, project_shape

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext, RunResult

#: Title-block fields read from the part YAML (recorded as dependency keys).
TITLE_FIELDS = ("rev", "name", "material", "process", "finish", "tolerance_class")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _part_data(
    ctx: RunContext, part_id: str
) -> tuple[Any, dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """Return ``(shape, props, features, flat_pattern)`` for a part built now or earlier."""
    from napkin2factory.geometry.build import load_built_part
    from napkin2factory.geometry.features import to_json

    part_dir = ctx.build_dir / "parts" / part_id
    built = ctx.built_parts.get(part_id)
    if built is not None:
        feats: dict[str, Any] = to_json(built.result.features)
        feats["dims"] = to_json(built.result.dims)
        fp = built.result.flat_pattern
        flat = to_json(fp) if fp is not None else None
    else:
        built = load_built_part(ctx.product, part_id, ctx.build_dir)
        feats = _read_json(part_dir / "features.json") or {}
        flat = _read_json(part_dir / "flat_pattern.json")
    return built.shape, dict(built.props), feats, flat


def _material_text(part: Any) -> str:
    m = part.material
    if m is None:
        return "—"
    return f"{m.name} — {m.spec}" if m.spec else m.name


def _write_atomic(path: Path, data: str | bytes) -> Path:
    tmp = path.with_name(f".{path.name}.tmp")
    if isinstance(data, str):
        tmp.write_text(data, encoding="utf-8")
    else:
        tmp.write_bytes(data)
    return tmp


def make_drawing(ctx: RunContext, part_id: str) -> RunResult:
    """Project, dimension and write the drawing (and DXF) for ``part://<part_id>``.

    Args:
        ctx: the build context (product, build dir, parts built in this run, snapshot date).
        part_id: the part to draw.

    Returns:
        The run result: reads (part outputs and title-block fields), outputs, output hash.

    Raises:
        RuntimeError: naming the part when a projection fails or the sheet cannot be laid out.
    """
    from napkin2factory.core.graph.rules import RunResult
    from napkin2factory.drawings.dxf import write_flat_dxf

    part = ctx.product.parts[part_id]
    uri = part.uri
    shape, props, feats, flat = _part_data(ctx, part_id)
    bb = props["bbox"]
    lo = tuple(float(v) for v in bb["min"])
    hi = tuple(float(v) for v in bb["max"])
    size = (float(bb["x"]), float(bb["y"]), float(bb["z"]))
    center = tuple((a + b) / 2 for a, b in zip(lo, hi, strict=True))
    tol = max(0.05, max(size) / 400)
    views = {}
    for name in ALL_VIEWS:
        try:
            views[name] = project_shape(shape, name, center, tol)  # type: ignore[arg-type]
        except Exception as exc:
            raise RuntimeError(
                f"{uri}: drawing failed — hidden-line projection of the {name} view raised "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        if name in ORTHO_VIEWS:
            ortho_extents(views[name], lo, hi)  # type: ignore[arg-type]
    has_flat = bool(flat and flat.get("outline"))  # any flat part gets a DXF (cut-sheet too)
    thickness = feats.get("thickness") or (flat or {}).get("thickness")
    inp = SheetInput(
        title=TitleFields(
            uri=uri,
            name=part.name,
            rev=part.rev,
            material=_material_text(part),
            process=part.process,
            finish=part.finish or "—",
            tolerance=part.tolerance_class or "—",
            version=__version__,
            date=ctx.snapshot_date,
        ),
        views=views,
        bbox_min=lo,  # type: ignore[arg-type]
        bbox_max=hi,  # type: ignore[arg-type]
        bbox_size=size,
        dims=list(feats.get("dims", [])),
        holes=list(feats.get("holes", [])),
        flat=flat if has_flat else None,
        bends=list(feats.get("bends", [])),
        thickness=float(thickness) if thickness else None,
    )
    sheet = compose(inp)

    out_dir = ctx.build_dir / "drawings"
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_path = out_dir / f"{part_id}.svg"
    dxf_path = out_dir / f"{part_id}-flat.dxf"
    json_path = out_dir / f"{part_id}.json"
    # Everything is produced into temporary siblings first; renames happen last so a
    # failure never leaves a half-written drawing behind.
    staged: list[tuple[Path, Path]] = []
    try:
        staged.append((_write_atomic(svg_path, sheet.svg), svg_path))
        if has_flat and flat is not None:
            tmp_dxf = dxf_path.with_name(f".{dxf_path.name}.tmp")
            write_flat_dxf(tmp_dxf, flat, uri, inp.bends, inp.thickness)
            staged.append((tmp_dxf, dxf_path))
        meta = dict(sheet.meta, uri=uri, dxf=dxf_path.name if has_flat else None)
        staged.append(
            (
                _write_atomic(json_path, json.dumps(meta, indent=2, sort_keys=True) + "\n"),
                json_path,
            )
        )
    except Exception:
        for tmp, _ in staged:
            tmp.unlink(missing_ok=True)
        raise
    for tmp, final in staged:
        os.replace(tmp, final)
    if not has_flat:
        dxf_path.unlink(missing_ok=True)  # the part stopped being sheet metal
    outputs = [final for _, final in staged]
    output_hash = sha256_text(
        sheet.hash_text + (sha256_json(flat) if has_flat and flat is not None else "")
    )
    reads = [uri] + [f"{uri}#{k}" for k in TITLE_FIELDS]
    return RunResult(reads=reads, outputs=outputs, output_hash=output_hash)
