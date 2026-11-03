"""Circuit diagram column, track, lane and label layout; split from diagram.py (S-184)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from napkin2factory.drawings.svg import text_width

#: Row pitch, header line height, the gap between boxes in a column (mm on the sheet).
PITCH = 6.0
GAP = 2 * PITCH
#: A wire's vertical track pitch in a gap, and the lane pitch below the boxes.
TRACK = 2.5
LANE = 3.0
#: Text sizes: a box's name, a terminal marking, a wire label, the title.
HEAD_SIZE = 3.0
MARK_SIZE = 2.5
LABEL_SIZE = 2.2
NOT_GIVEN = "not given"
#: A wire whose drawn route is longer than this (mm on the sheet) carries its id at both
#: ends; one through a cable entry always does (S-174).
LONG = 60.0
#: Labels sharing one terminal stack this far apart, alternately above and below its line;
#: a wire's id is fanned so only on a terminal holding at most ``FAN`` conductors on that
#: side, one above its line and one below (a third would sit by the next row and read as
#: its wire; the full label at the far end serves).
LABEL_STEP = 2.6
FAN = 2
#: The device roles a circuit with no supply terminal starts from (its sources).
SOURCE_ROLES = ("supply", "sensor")


@dataclass
class Node:
    """A box: the supply, a device, a cable entry or a module supplied from elsewhere."""

    uri: str
    kind: str  # supply | device | entry | module | other
    head: list[str]
    rows: list[str]
    words: str = ""  # a module's boundary words (above its box)
    role: str = ""  # a device's role
    col: int = 0
    x0: float = 0.0
    y0: float = 0.0
    w: float = 0.0
    used: dict[tuple[str, str], int] = field(default_factory=dict)  # (row, side) → wires

    @property
    def header(self) -> float:
        """Height of the name lines inside the box (a module shows nothing inside)."""
        return 0.0 if self.kind == "module" else PITCH * len(self.head)

    @property
    def h(self) -> float:
        """Box height."""
        return self.header + PITCH * max(1, len(self.rows))

    @property
    def x1(self) -> float:
        """Right edge."""
        return self.x0 + self.w

    def pin_y(self, row: str) -> float:
        """The y of a row's pins."""
        return self.y0 + self.header + (self.rows.index(row) + 0.5) * PITCH


@dataclass
class Leg:
    """One drawn run of a wire: between two nodes' rows (a wire via an entry is two legs)."""

    wire: dict[str, Any]
    a: tuple[str, str]  # (node uri, row): the wire's ``from`` side
    b: tuple[str, str]
    label: str
    part: str = "whole"  # whole | in (from → entry) | out (entry → to)


@dataclass(eq=False)  # compared and hashed by identity: one per drawn leg
class Route:
    """A leg as drawn: its left end ``a``, its right end ``b``, its tracks and points."""

    leg: Leg
    na: Node
    ra: str
    nb: Node
    rb: str
    from_left: bool  # the wire's ``from`` side is the left end
    lane: float = 0.0  # the y of its run across the columns it skips
    tracks: dict[int, float] = field(default_factory=dict)  # gap → its track's x
    pts: list[tuple[float, float]] = field(default_factory=list)

    @property
    def same(self) -> bool:
        """Both ends in one column (the run turns back to the right edge it left)."""
        return self.na.col == self.nb.col

    @property
    def skips(self) -> bool:
        """The run skips a column, so it crosses them on a lane between or below their boxes."""
        return self.nb.col - self.na.col > 1

    def pin(self, side: str) -> tuple[str, str, str]:
        """The terminal an end lands on: ``(node, row, edge)``."""
        if side == "a":
            return self.na.uri, self.ra, "R"
        return self.nb.uri, self.rb, "R" if self.same else "L"


@dataclass
class Seg:
    """A route's vertical run in one gap: from ``y0`` (entering from the left) to ``y1``."""

    route: Route
    y0: float
    y1: float
    back: bool  # the run at ``y1`` turns back left (both ends in one column)


# ---- columns -----------------------------------------------------------------------------


def _sources(nodes: dict[str, Node]) -> list[str]:
    """Where the circuit starts: the supply, else its sensors, else a module, else its first end."""
    tests = (
        lambda n: n.kind == "supply",
        lambda n: n.kind == "device" and n.role in SOURCE_ROLES,
        lambda n: n.kind == "module",
    )
    for test in tests:
        found = [u for u, n in nodes.items() if test(n)]
        if found:
            return found
    return list(nodes)[:1]


def _inside(nodes: dict[str, Node], legs: list[Leg]) -> set[str]:
    """The box's nodes: the side of its cable entries the circuit's sources are not on.

    The circuit, cut at its entries, falls into pieces; the two pieces a wire through an
    entry joins lie on opposite sides of it, so each group of pieces linked through entries
    splits in two.  The box is the side without a source (the supply, a sensor, a module
    supplied from elsewhere), else the side with more nodes; one wire through one entry
    never puts both its ends in the box (S-174).  Empty with no entry.
    """
    parent = {u: u for u in nodes}

    def find(u: str) -> str:
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u

    for leg in legs:
        u, v = leg.a[0], leg.b[0]
        if nodes[u].kind != "entry" and nodes[v].kind != "entry":
            parent[find(u)] = find(v)
    # the pieces a wire through an entry joins: its two legs' far ends
    apart: dict[str, set[str]] = {}
    by_wire: dict[str, list[Leg]] = {}
    for leg in legs:
        by_wire.setdefault(leg.wire["id"], []).append(leg)
    for parts in by_wire.values():
        ends = [find(e[0]) for leg in parts for e in (leg.a, leg.b) if nodes[e[0]].kind != "entry"]
        if len(parts) == 2 and len(ends) == 2 and ends[0] != ends[1]:
            apart.setdefault(ends[0], set()).add(ends[1])
            apart.setdefault(ends[1], set()).add(ends[0])
    if not apart:
        return set()
    sources = (
        set(_sources(nodes))
        if any(n.kind in ("supply", "module") or n.role in SOURCE_ROLES for n in nodes.values())
        else set()
    )
    members: dict[str, list[str]] = {}
    for u, n in nodes.items():
        if n.kind != "entry":
            members.setdefault(find(u), []).append(u)
    side: dict[str, int] = {}
    inside: set[str] = set()
    for root in [r for r in members if r in apart]:
        if root in side:
            continue
        side[root], group, queue = 0, [root], [root]
        while queue:  # two-colour the group; a conflict (an odd loop) keeps the first colour
            r = queue.pop(0)
            for o in sorted(apart[r]):
                if o not in side:
                    side[o] = 1 - side[r]
                    group.append(o)
                    queue.append(o)
        halves = [[m for r in group if side[r] == k for m in members[r]] for k in (0, 1)]

        def rank(half: list[str]) -> tuple[int, int]:
            return (-sum(u in sources for u in half), len(half))

        inside |= set(max(halves, key=rank))
    return inside


def _columns(nodes: dict[str, Node], legs: list[Leg]) -> None:
    """Each node's column: its distance from the sources, the longest along the wires."""
    order = list(nodes)
    adj: dict[str, list[str]] = {u: [] for u in order}
    for leg in legs:
        adj[leg.a[0]].append(leg.b[0])
        adj[leg.b[0]].append(leg.a[0])
    depth: dict[str, int] = {}
    for roots in [_sources(nodes)] + [[u] for u in order]:
        roots = [u for u in roots if u not in depth]
        if not roots:
            continue
        queue = list(roots)
        for u in roots:
            depth[u] = 0
        while queue:
            u = queue.pop(0)
            for v in adj[u]:
                if v not in depth:
                    depth[v] = depth[u] + 1
                    queue.append(v)
    # which side of each entry the box is on: the side its box neighbours reached first
    inside = _inside(nodes, legs)
    box_left: dict[str, bool] = {}
    for u, n in nodes.items():
        if n.kind == "entry":
            near = [depth[v] for v in adj[u] if v in inside]
            if near:
                box_left[u] = min(near) <= depth[u]
    # orient each leg (a box node towards its entry's near side, a device beyond an entry
    # from the box to its far side, the rest away from the sources; ties as written), then
    # push every node right of what feeds it; bounded, so a loop among equals cannot run away
    edges = []
    for leg in legs:
        u, v = leg.a[0], leg.b[0]
        if u == v:
            continue
        e, x = (u, v) if u in box_left else (v, u) if v in box_left else ("", "")
        if e and nodes[x].kind != "entry":
            near_left = box_left[e] if x in inside else not box_left[e]
            edges.append((x, e) if near_left else (e, x))
        else:
            edges.append((v, u) if depth[v] < depth[u] else (u, v))
    # and every box device on its entries' near side, never in an entry's column or past it
    # (a stud wired from the earth bar inside the box would otherwise sit beside the entry)
    for e, left in box_left.items():
        edges += [(x, e) if left else (e, x) for x in order if x in inside]
    col = dict(depth)
    for _ in range(len(order)):
        moved = False
        for u, v in edges:
            if col[v] < col[u] + 1 <= len(order):
                col[v] = col[u] + 1
                moved = True
        if not moved:
            break
    for u in order:
        nodes[u].col = col[u]


def _routes(nodes: dict[str, Node], legs: list[Leg]) -> list[Route]:
    out = []
    for leg in legs:
        (ua, ra), (ub, rb) = leg.a, leg.b
        na, nb = nodes[ua], nodes[ub]
        if nb.col < na.col:
            out.append(Route(leg, nb, rb, na, ra, from_left=False))
        else:
            out.append(Route(leg, na, ra, nb, rb, from_left=True))
    return out


# ---- heights: stacking each column, level with what feeds it ------------------------------


def _stack(nodes: dict[str, Node], cols: dict[int, list[str]]) -> None:
    for c, members in cols.items():
        y = (c % 2) * PITCH / 2
        for u in members:
            n = nodes[u]
            n.y0 = y + (2 * PITCH if n.kind == "module" else 0.0)
            y = n.y0 + n.h + GAP


def _level(nodes: dict[str, Node], cols: dict[int, list[str]], routes: list[Route]) -> None:
    """Order each column by where its boxes' wires come from.

    The mean height of the other ends in earlier columns; a box fed from nowhere to its left
    keeps its place.
    """
    for c in sorted(cols)[1:]:

        def want(u: str, c: int = c) -> float:
            n = nodes[u]
            ys = []
            for r in routes:
                for me, mine, other, theirs in ((r.na, r.ra, r.nb, r.rb), (r.nb, r.rb, r.na, r.ra)):
                    if me is n and other.col < c:
                        ys.append(other.pin_y(theirs) - (n.pin_y(mine) - n.y0))
            return sum(ys) / len(ys) if ys else n.y0

        cols[c].sort(key=want)
        _stack(nodes, cols)


# ---- labels ---------------------------------------------------------------------------------


@dataclass
class Label:
    """A wire's label at one end of one route: the full words, or the id alone."""

    route: Route
    side: str  # a | b
    text: str
    full: bool


def _plan_labels(routes: list[Route]) -> list[Label]:
    """Each wire's full label at a free end, its id at a free end far from it.

    An end is free when its terminal holds no other conductor on that side; the order tried
    is the wire's start, its finish, then the two sides of its cable entry.  When no end is
    free (both terminals shared), the label stacks at the start; the id, when no other end
    is free, fans on a terminal shared by at most ``FAN`` conductors.
    """
    crowd: Counter[tuple[str, str, str]] = Counter()
    for r in routes:
        for side, node in (("a", r.na), ("b", r.nb)):
            _, row, edge = r.pin(side)
            crowd[r.pin(side)] += 1
            node.used[(row, edge)] = node.used.get((row, edge), 0) + 1
    by_wire: dict[str, list[Route]] = {}
    for r in routes:
        by_wire.setdefault(r.leg.wire["id"], []).append(r)
    out: list[Label] = []
    for wid, rs in by_wire.items():

        def end(r: Route, which: str) -> tuple[Route, str]:
            return r, ("a" if (which == "from") == r.from_left else "b")

        if len(rs) == 1:
            start, finish = end(rs[0], "from"), end(rs[0], "to")
            via: list[tuple[Route, str]] = []
        else:
            r_in = next(r for r in rs if r.leg.part == "in")
            r_out = next(r for r in rs if r.leg.part == "out")
            start, finish = end(r_in, "from"), end(r_out, "to")
            via = [end(r_in, "to"), end(r_out, "from")]

        def free(e: tuple[Route, str]) -> bool:
            return crowd[e[0].pin(e[1])] == 1

        tried = [start, finish] + via
        full = next((e for e in tried if free(e)), start)
        out.append(Label(full[0], full[1], rs[0].leg.label, True))
        if full in (start, *via[:1]):
            others = [finish] + via[::-1] + [start]
        else:
            others = [start] + via + [finish]
        pair = {via[0]: via[1], via[1]: via[0]} if via else {}
        rest = [e for e in others if e != full and e != pair.get(full)]
        # the id alone at a free end, else fanned on a terminal shared by a few (S-174)
        other = next((e for e in rest if free(e)), None) or next(
            (e for e in rest if crowd[e[0].pin(e[1])] <= FAN), None
        )
        if other is not None:
            out.append(Label(other[0], other[1], wid, False))
    return out


def _label_at(lab: Label) -> tuple[Node, str, str]:
    """The node, row and edge a label sits by."""
    r = lab.route
    if lab.side == "a":
        return r.na, r.ra, "R"
    return r.nb, r.rb, "R" if r.same else "L"


# ---- tracks and lanes -------------------------------------------------------------------------


def _between(y: float, a: float, b: float) -> bool:
    lo, hi = (a, b) if a < b else (b, a)
    return lo < y < hi


def _cross(i: Seg, j: Seg) -> int:
    """Crossings between two runs of one gap when ``i`` takes the track left of ``j``."""
    n = 0
    if _between(j.y0, i.y0, i.y1):  # j's run in from the left passes i's track
        n += 1
    if j.back and _between(j.y1, i.y0, i.y1):  # so does j's run back
        n += 1
    if not i.back and _between(i.y1, j.y0, j.y1):  # i's run out to the right passes j's
        n += 1
    return n


def _order_tracks(segs: list[Seg]) -> list[Seg]:
    """The gap's runs, left to right.

    Down runs starting lowest first, then up runs starting highest; then neighbours swap
    while that removes a crossing.
    """
    out = sorted(segs, key=lambda s: (0, -s.y0, -s.y1) if s.y1 > s.y0 else (1, s.y0, s.y1))
    for _ in range(len(out)):
        swapped = False
        for k in range(len(out) - 1):
            if _cross(out[k + 1], out[k]) < _cross(out[k], out[k + 1]):
                out[k], out[k + 1] = out[k + 1], out[k]
                swapped = True
        if not swapped:
            break
    return out


def _channels(nodes: dict[str, Node], cols: range) -> list[tuple[float, float]]:
    """The free bands ``(y from, y to)`` crossing every column in ``cols`` between its boxes.

    The last is the open band below every box.
    """
    bottom = max(n.y0 + n.h for n in nodes.values())
    free = [(-float("inf"), float("inf"))]
    for c in cols:
        boxes = sorted(
            (n.y0 - (PITCH if n.kind == "module" else 0.0), n.y0 + n.h)
            for n in nodes.values()
            if n.col == c
        )
        gaps = [(a[1], b[0]) for a, b in zip(boxes, boxes[1:])] + [(boxes[-1][1], float("inf"))]
        free = [
            (max(lo, glo), min(hi, ghi))
            for lo, hi in free
            for glo, ghi in gaps
            if min(hi, ghi) - max(lo, glo) >= GAP
        ]
    inner = [band for band in free if band[1] != float("inf")]
    return inner + [(bottom, float("inf"))]


def _lanes(nodes: dict[str, Node], routes: list[Route]) -> None:
    """Each skipping run's lane (the y it crosses the skipped columns at).

    In the free band between the skipped columns' boxes nearest its two ends while one has
    room, else below every box; the widest spans lowest (S-174).
    """
    used: dict[tuple[float, float], int] = {}
    for r in sorted((r for r in routes if r.skips), key=lambda r: r.nb.col - r.na.col):
        ya, yb = r.na.pin_y(r.ra), r.nb.pin_y(r.rb)
        target = (ya + yb) / 2
        bands = _channels(nodes, range(r.na.col + 1, r.nb.col))
        best, best_d = bands[-1], float("inf")
        for band in bands[:-1]:
            room = int((band[1] - band[0] - GAP / 2) // LANE) + 1
            if used.get(band, 0) >= room:
                continue
            d = 0.0 if band[0] <= target <= band[1] else min(abs(target - b) for b in band)
            if d < best_d:
                best, best_d = band, d
        k = used.get(best, 0)
        used[best] = k + 1
        r.lane = best[0] + (GAP / 2 if best[1] == float("inf") else GAP / 4) + k * LANE


def _gaps(nodes: dict[str, Node], routes: list[Route]) -> dict[int, list[Seg]]:
    """Each gap's vertical runs, lanes assigned."""
    _lanes(nodes, routes)
    gaps: dict[int, list[Seg]] = {}
    for r in routes:
        ya, yb = r.na.pin_y(r.ra), r.nb.pin_y(r.rb)
        if r.skips:
            gaps.setdefault(r.na.col, []).append(Seg(r, ya, r.lane, False))
            gaps.setdefault(r.nb.col - 1, []).append(Seg(r, r.lane, yb, False))
        elif ya != yb or r.same:
            gaps.setdefault(r.na.col, []).append(Seg(r, ya, yb, r.same))
    return {g: _order_tracks(segs) for g, segs in gaps.items()}


# ---- placing --------------------------------------------------------------------------------


def _place(
    nodes: dict[str, Node],
    cols: dict[int, list[str]],
    labels: list[Label],
    gaps: dict[int, list[Seg]],
) -> None:
    """Box widths and x positions; each track's x."""
    ncols = 1 + max(cols)
    for n in nodes.values():
        if n.kind == "module":
            n.w = 24.0
            continue
        widths = [text_width(t, HEAD_SIZE) for t in n.head]
        if n.kind != "entry":
            widths += [text_width(r, MARK_SIZE) * 2 + 4 for r in n.rows]
        n.w = max(14.0 if n.kind == "entry" else 24.0, max(widths, default=0) + 8)
    col_w = [0.0] * ncols
    for n in nodes.values():
        col_w[n.col] = max(col_w[n.col], n.w)
    # each gap: a zone for the labels by the left column's right edges, the tracks, then a
    # zone for the labels by the right column's left edges
    right_zone = [0.0] * ncols
    left_zone = [0.0] * ncols
    for lab in labels:
        node, _, edge = _label_at(lab)
        w = text_width(lab.text, LABEL_SIZE) + 3
        zone = right_zone if edge == "R" else left_zone
        zone[node.col] = max(zone[node.col], w)
    x = 0.0
    col_x: list[float] = []
    for c in range(ncols):
        x += left_zone[c]
        col_x.append(x)
        track0 = x + col_w[c] + right_zone[c] + 6
        for k, seg in enumerate(gaps.get(c, [])):
            seg.route.tracks[c] = track0 + k * TRACK
        x = track0 + len(gaps.get(c, [])) * TRACK + 6
    for n in nodes.values():
        n.x0 = col_x[n.col] + (col_w[n.col] - n.w) / 2


def _points(r: Route, nodes: dict[str, Node]) -> list[tuple[float, float]]:
    xa, ya = r.na.x1, r.na.pin_y(r.ra)
    xb, yb = (r.nb.x1 if r.same else r.nb.x0), r.nb.pin_y(r.rb)
    if r.skips:
        t1, t2 = r.tracks[r.na.col], r.tracks[r.nb.col - 1]
        return [(xa, ya), (t1, ya), (t1, r.lane), (t2, r.lane), (t2, yb), (xb, yb)]
    t = r.tracks.get(r.na.col)
    if t is None:  # level: a straight run
        return [(xa, ya), (xb, yb)]
    return [(xa, ya), (t, ya), (t, yb), (xb, yb)]


def _length(pts: list[tuple[float, float]]) -> float:
    return sum(abs(x1 - x0) + abs(y1 - y0) for (x0, y0), (x1, y1) in zip(pts, pts[1:]))


def _clean(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in pts:
        if not out or p != out[-1]:
            out.append(p)
    return out
