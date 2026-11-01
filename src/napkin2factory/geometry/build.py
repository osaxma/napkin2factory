"""``build_part()`` and ``build_assembly()``: the API the DAG rules call (M2 → M3).

Both are callable without the build graph.  They resolve a part's declarative kit call
(or run its geometry module) through the recording accessors, export every artifact
into ``build/parts/<id>/`` or ``build/assemblies/<id>/``, and return what was read so
the graph can record dependencies.

Parts live in :mod:`~napkin2factory.geometry.build_part`, assemblies in
:mod:`~napkin2factory.geometry.build_asm` (F15, S-131); this module keeps every name
importable from here, so callers need no change.
"""

from __future__ import annotations

from napkin2factory.geometry.build_asm import (
    BuiltAssembly,
    PartsView,
    assembly_order,
    build_assembly,
    build_geometry,
    declared_counts,
    instance_records,
    load_built_assembly,
    render_note_lines,
    render_notes,
)
from napkin2factory.geometry.build_part import (
    BuiltPart,
    GeometryError,
    _load_module,
    apply_interfaces,
    build_part,
    load_built_part,
    load_props,
    resolve_args,
)

__all__ = [
    "BuiltAssembly",
    "BuiltPart",
    "GeometryError",
    "PartsView",
    "_load_module",
    "apply_interfaces",
    "assembly_order",
    "build_assembly",
    "build_geometry",
    "build_part",
    "declared_counts",
    "instance_records",
    "load_built_assembly",
    "load_built_part",
    "load_props",
    "render_note_lines",
    "render_notes",
    "resolve_args",
]
