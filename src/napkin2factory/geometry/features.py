"""What a generator knows about what it built: features, dimension callouts, flat patterns.

Rule packs (M4) evaluate ``features.json``; drawings (M5) place ``dims`` as callouts and
``flat_pattern`` as the DXF.  Everything here is plain data, serialisable with
:func:`to_json`.  Coordinates are millimetres in the part's own frame.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]


@dataclass
class Hole:
    """A round through-hole (or blind if ``depth`` is set)."""

    center: Vec3
    diameter: float
    axis: Vec3 = (0.0, 0.0, 1.0)
    depth: float | None = None
    edge_distance: float | None = None  # nearest sheet edge, if known
    bend_distance: float | None = None  # nearest bend line, if known
    interface: str | None = None  # iface://… when placed from an interface
    label: str | None = None


@dataclass
class HolePattern:
    """A group of holes placed together (an interface's bolt pattern, or a user pattern)."""

    centers: list[Vec3]
    diameter: float
    frame_origin: Vec3 = (0.0, 0.0, 0.0)
    frame_normal: Vec3 = (0.0, 0.0, 1.0)
    interface: str | None = None
    label: str | None = None


@dataclass
class Bend:
    """A sheet-metal bend: a line in the flat with radius and angle."""

    start: Vec3
    end: Vec3
    radius: float
    angle: float = 90.0
    direction: Literal["up", "down"] = "up"
    k_factor: float = 0.44
    label: str | None = None

    @property
    def length(self) -> float:
        """Bend line length."""
        dx, dy, dz = (self.end[i] - self.start[i] for i in range(3))
        return float((dx * dx + dy * dy + dz * dz) ** 0.5)


@dataclass
class Flange:
    """A bent-up wall or lip; ``height`` is the flat length after the bend."""

    height: float
    length: float
    bend: str | None = None  # label of the bend it hangs on
    label: str | None = None


@dataclass
class Relief:
    """A corner relief cut so adjacent flanges can bend."""

    at: Vec3
    width: float
    depth: float


@dataclass
class Cutout:
    """A rectangular or polygonal opening in a face."""

    face: str  # base | front | back | left | right | top
    center: Vec2
    width: float
    height: float
    corner_radius: float = 0.0
    label: str | None = None


@dataclass
class Member:
    """A frame member (tube or angle) with its cut length."""

    profile: str  # e.g. "square-tube 25x25x2" or "angle 30x30x3"
    length: float
    start: Vec3
    end: Vec3
    label: str | None = None


@dataclass
class Dim:
    """A dimension callout for drawings."""

    label: str
    value: float
    p1: Vec3
    p2: Vec3
    view: Literal["front", "top", "right", "flat", "iso"] = "front"
    kind: Literal["linear", "diameter", "radius"] = "linear"


@dataclass
class FlatPattern:
    """A developed sheet: outline polygon(s), inner contours, and bend lines, all 2D."""

    outline: list[Vec2]
    holes: list[tuple[Vec2, float]] = field(default_factory=list)  # (center, diameter)
    cutouts: list[list[Vec2]] = field(default_factory=list)
    bend_lines: list[tuple[Vec2, Vec2, float, str]] = field(
        default_factory=list
    )  # p1,p2,angle,label
    thickness: float = 1.0
    area: float = 0.0  # developed area (outline minus holes/cutouts), mm²

    def size(self) -> tuple[float, float]:
        """Bounding size of the outline."""
        xs = [p[0] for p in self.outline]
        ys = [p[1] for p in self.outline]
        return (max(xs) - min(xs), max(ys) - min(ys))


@dataclass
class CutItem:
    """One line of a cut list (frames, brick layers)."""

    description: str
    length: float
    qty: int
    profile: str | None = None
    width: float | None = None
    thickness: float | None = None


@dataclass
class Features:
    """Everything a generator declares about its output."""

    process: str = "none"
    thickness: float | None = None  # sheet thickness, mm
    holes: list[Hole] = field(default_factory=list)
    patterns: list[HolePattern] = field(default_factory=list)
    bends: list[Bend] = field(default_factory=list)
    flanges: list[Flange] = field(default_factory=list)
    reliefs: list[Relief] = field(default_factory=list)
    cutouts: list[Cutout] = field(default_factory=list)
    members: list[Member] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, int]:
        """Counts per feature type (for goldens)."""
        return {
            "holes": len(self.holes),
            "patterns": len(self.patterns),
            "bends": len(self.bends),
            "flanges": len(self.flanges),
            "reliefs": len(self.reliefs),
            "cutouts": len(self.cutouts),
            "members": len(self.members),
        }


@dataclass
class PartResult:
    """What ``build(P, I, kit)`` and every kit generator return."""

    shape: Any  # build123d Solid/Part/Compound
    features: Features = field(default_factory=Features)
    dims: list[Dim] = field(default_factory=list)
    flat_pattern: FlatPattern | None = None
    cut_list: list[CutItem] = field(default_factory=list)
    props: dict[str, Any] = field(default_factory=dict)  # generator-declared extras
    notes: list[str] = field(default_factory=list)


def to_json(obj: Any) -> Any:
    """Dataclasses → plain JSON-able structures (tuples become lists)."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_json(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): to_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_json(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 6)
    return obj


def polygon_area(points: list[Vec2]) -> float:
    """Shoelace area of a simple polygon (absolute)."""
    n = len(points)
    s = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0
