"""The napkin stage's engine: massing composer, screening and ``n2f concept build`` (N1, N5).

Everything here runs in-process, outside the build graph: it reads concept cards, runs the
kit at massing fidelity, calls the calc kit, and writes under ``build/concepts/<id>/`` —
a folder no build rule reads and the build manifest never lists (N1). Nothing here
imports ``core.graph``.

* :mod:`~napkin2factory.concepts.massing` — card ``massing:`` calls → placed silhouettes,
  GLB, props, features, renders.
* :mod:`~napkin2factory.concepts.screening` — labelled numbers (``computed`` from the
  massing, ``estimate`` from the calc kit), the ``concept-v0`` rule pack, a verdict.
* :mod:`~napkin2factory.concepts.build` — the orchestration behind ``n2f concept build``.
"""

from __future__ import annotations

CONCEPTS_BUILD_DIR = "concepts"

__all__ = ["CONCEPTS_BUILD_DIR"]
