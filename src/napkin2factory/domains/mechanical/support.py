"""Support check on an assembly: every part connects down to the floor (B-0328).

An assembly's placed parts must form a continuous chain of support down to the
lowest parts standing on the floor. Two parts connect when their bounding boxes
touch on a face patch of at least 1 mm² (within 0.5 mm), or when a declared
interface names both parts and their bounding boxes are within 30 mm (bridged by
hardware such as standoffs).
"""

from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from napkin2factory.core.checks.results import CheckResult
    from napkin2factory.core.domain import StageContext
    from napkin2factory.core.loader import Product


@dataclass
class SupportReport:
    """Outcome of the support check for an assembly."""

    asm_id: str
    built: bool = True
    ground: list[str] = field(default_factory=list)
    supported: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    unsupported_titles: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when every placed part is supported."""
        return not self.unsupported

    def to_dict(self) -> dict[str, Any]:
        """JSON form."""
        return dict(self.__dict__)


def _location(tr: list[float], q: list[float]) -> Any:
    """Construct a build123d Location from translation and quaternion."""
    from build123d import Location
    from OCP.gp import gp_Quaternion, gp_Trsf, gp_Vec

    trsf = gp_Trsf()
    trsf.SetRotation(gp_Quaternion(q[0], q[1], q[2], q[3]))
    trsf.SetTranslationPart(gp_Vec(tr[0], tr[1], tr[2]))
    return Location(trsf)


def _boxes_connected(
    box_a: tuple[tuple[float, float, float], tuple[float, float, float]],
    box_b: tuple[tuple[float, float, float], tuple[float, float, float]],
    has_interface: bool = False,
) -> bool:
    """True when two bounding boxes connect by face touch or a bridging interface."""
    min_a, max_a = box_a
    min_b, max_b = box_b

    gaps: list[float] = []
    overlaps: list[float] = []
    for k in range(3):
        ov = min(max_a[k], max_b[k]) - max(min_a[k], min_b[k])
        if ov >= 0.0:
            gaps.append(0.0)
            overlaps.append(ov)
        else:
            gaps.append(-ov)
            overlaps.append(0.0)

    # (a) Touch on a face patch: gap <= 0.5 mm along one axis,
    # and overlap area >= 1 mm² on the other two axes.
    for axis in range(3):
        if gaps[axis] <= 0.5:
            other = [ax for ax in range(3) if ax != axis]
            area = overlaps[other[0]] * overlaps[other[1]]
            if area >= 1.0:
                return True

    # (b) Declared interface names both parts and gap between boxes > 0.5 mm and <= 30 mm
    if has_interface:
        box_gap = math.hypot(gaps[0], gaps[1], gaps[2])
        if 0.5 < box_gap <= 30.0:
            return True

    return False


def check_support(product: Product, asm_id: str, build_dir: Path) -> SupportReport:
    """Run the support check against placed instances of an assembly."""
    from build123d import import_step

    report = SupportReport(asm_id=asm_id)
    inst_path = build_dir / "assemblies" / asm_id / "instances.json"
    if not inst_path.is_file():
        report.built = False
        report.notes.append(f"asm://{asm_id} has not been built")
        return report

    instances = json.loads(inst_path.read_text(encoding="utf-8"))
    shapes: dict[str, Any] = {}
    # node, uri, box ((min_x, min_y, min_z), (max_x, max_y, max_z))
    placed: list[
        tuple[
            str,
            str,
            tuple[tuple[float, float, float], tuple[float, float, float]],
        ]
    ] = []

    for inst in instances:
        uri = inst["uri"]
        pid = uri.replace("part://", "")
        if uri not in shapes:
            step = build_dir / "parts" / pid / "model.step"
            if not step.is_file():
                report.notes.append(f"{uri} has no STEP; skipped")
                continue
            shapes[uri] = import_step(str(step))
        moved = shapes[uri].moved(_location(inst["translation"], inst["rotation"]))
        bb = moved.bounding_box()
        box = ((bb.min.X, bb.min.Y, bb.min.Z), (bb.max.X, bb.max.Y, bb.max.Z))
        placed.append((inst["node"], uri, box))

    if not placed:
        return report

    # Ground: instances whose box bottom (min Z) is within 0.5 mm of lowest min Z
    min_z_all = min(p[2][0][2] for p in placed)
    ground_nodes = {p[0] for p in placed if p[2][0][2] <= min_z_all + 0.5}
    report.ground = sorted(ground_nodes)

    # Build adjacency graph
    nodes = [p[0] for p in placed]
    adj: dict[str, set[str]] = {n: set() for n in nodes}

    for i in range(len(placed)):
        node_a, _, box_a = placed[i]
        for j in range(i + 1, len(placed)):
            node_b, _, box_b = placed[j]
            # Two parts connect by face contact or hardware bridging across gaps <= 30 mm
            if _boxes_connected(box_a, box_b, has_interface=True):
                adj[node_a].add(node_b)
                adj[node_b].add(node_a)

    # Walk from ground
    visited: set[str] = set(ground_nodes)
    queue: deque[str] = deque(ground_nodes)
    while queue:
        curr = queue.popleft()
        for neighbor in adj[curr]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    report.supported = sorted(visited)
    report.unsupported = [n for n in nodes if n not in visited]

    # Map unsupported node to part title
    for node in report.unsupported:
        # find placed instance uri
        matching = [p[1] for p in placed if p[0] == node]
        uri = matching[0] if matching else node
        pid = uri.replace("part://", "")
        part = product.parts.get(pid)
        title = part.name if part and part.name else pid
        if title not in report.unsupported_titles:
            report.unsupported_titles.append(title)

    return report


def support_stage(sctx: StageContext) -> list[CheckResult]:
    """Check that every placed part of an assembly is held up down to the floor."""
    from napkin2factory.core.checks.results import CheckResult

    product, build_dir = sctx.product, sctx.build_dir
    results: list[CheckResult] = []

    for aid in product.assemblies:
        if not sctx.keep(aid):
            continue
        srep = check_support(product, aid, build_dir)
        if not srep.built:
            status = "skip"
            msg = f"asm://{aid} has not been built"
        elif srep.ok:
            status = "pass"
            msg = "every part touches the floor or something that leads to it"
        else:
            status = "fail"
            msg = "; ".join(
                f"{t} is not held up: it touches nothing that leads to the floor"
                for t in srep.unsupported_titles
            )

        results.append(
            CheckResult(
                id=f"support://{aid}",
                subject=f"asm://{aid}",
                status=status,
                kind="support",
                title="every part is held up",
                message=msg,
                detail=srep.to_dict(),
                evidence={
                    "unsupported": srep.unsupported,
                    "ground": srep.ground,
                },
            )
        )

    return results
