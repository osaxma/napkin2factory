"""The wiring diagram of one circuit (ELECTRICAL_STAGE E5), drawn from its record.

A pure function of ``connections.json`` (the wave-2 contract), so the diagram can never
disagree with the schedule.  The layout reads left to right (S-157, S-174):

* every node is a box in a column: the supply, each device (its part's name and instance
  words, a row per terminal with its marking), each cable entry (a dashed box the wires
  pass straight through, one row per wire), and each module supplied from elsewhere (a
  dashed boundary with its words above it and nothing drawn inside, DoD 5);
* the circuit's sources start on the left: the supply, else its sensors (or a supply
  device), else a module supplied from elsewhere, else its first end; a node's column is
  its distance from them along the wires (the longest, so a load sits right of the switch
  that feeds it);
* the box is the side of its cable entries the sources are not on (see ``_inside``); a
  device reached through an entry from the box is drawn on the far side of that entry,
  whatever the circuit's purpose, and the box's own devices before it;
* within a column, a box sits level with what feeds it (the mean height of its wires'
  other ends); each wire is an orthogonal line on its own vertical track in the gap right
  of its left end, the tracks of a gap ordered so the fewest runs cross; a wire that skips
  a column runs along its own lane through a free band between the skipped columns' boxes
  (the band nearest its ends while one has room), else below the boxes;
* a wire is labelled "id · size · colour" once, at an end whose terminal holds no other
  conductor on that side (never stacked on a shared terminal), and a long one carries its id
  again at its other end so a reader can match the two (fanned above and below the line
  where two conductors share that terminal, left out where more do).  Columns alternate by
  half a row,
  so two horizontal runs in one gap never lie on the same line.

The title says what the circuit carries: the voltage for a circuit the supply feeds, the
words "extra-low-voltage signal" for a sensing circuit within the checks' extra-low-voltage
band, nothing for an earth circuit; "Protected by" only where the checks require a
protective device.  Terminals are small circles (IEC 60617's terminal) where a wire lands.
A footer band closes every diagram, as the title block closes a mechanical sheet
(``drawings/sheet.py``): the product, the circuit, the Revision (or "draft") and
:data:`DISCLAIMER`, so a printed diagram never travels without it (S-179).  Every
coordinate is rounded by the drawings' serialiser and nothing depends on time, so a
golden holds it.  The SVG is self-contained (its font in a ``<style>``), as the
``file://`` report needs (D13).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any
from xml.sax.saxutils import quoteattr

from napkin2factory.core.units import magnitude_in
from napkin2factory.domains.electrical.checks.pack import rule as pack_rule
from napkin2factory.domains.electrical.checks.stage import PROTECTED
from napkin2factory.drawings.svg import (
    FONT,
    Circle,
    Line,
    Path,
    Prim,
    Rect,
    Text,
    bbox_of,
    f,
    fit_size,
    group,
    text_width,
)

#: Row pitch, header line height, the gap between boxes in a column (mm on the sheet).
PITCH = 6.0
GAP = 2 * PITCH
#: A wire's vertical track pitch in a gap, and the lane pitch below the boxes.
TRACK = 2.5
LANE = 3.0
MARGIN = 10.0
#: Text sizes: a box's name, a terminal marking, a wire label, the title.
HEAD_SIZE = 3.0
MARK_SIZE = 2.5
LABEL_SIZE = 2.2
TITLE_SIZE = 4.0
PIN_R = 0.8
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
#: The sentence every wiring output carries (S-179, gate G blocker 3, gate H B2): the
#: diagram's footer, the package folder's README and the manual's wiring pages.
DISCLAIMER = (
    "Produced with an AI system; not reviewed by a licensed electrician: "
    "a licensed electrician wires the product to local code."
)
#: The footer's Revision when the build is not a released Revision's (S-179).
DRAFT = "draft"
#: Footer geometry: the gap above it, a cell's label size, a row's height.
FOOTER_GAP = 6.0
FOOTER_LABEL = 1.8
FOOTER_ROW = 9.0


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


def _split(end: str) -> tuple[str, str]:
    base, _, terminal = end.partition("#")
    return base, terminal


def _label(w: dict[str, Any]) -> str:
    size = f"{_num(w['csa_mm2'])} mm²" if w.get("csa_mm2") is not None else "size " + NOT_GIVEN
    return f"{w['id']} · {size} · {w.get('colour') or NOT_GIVEN}"


def _num(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _nodes_and_legs(record: dict[str, Any]) -> tuple[dict[str, Node], list[Leg]]:
    devices = {d["uri"]: d for d in record.get("devices", [])}
    entries = {e["uri"]: e for e in record.get("entries", [])}
    modules = {m["assembly"]: m for m in record.get("boundary", [])}
    nodes: dict[str, Node] = {}

    def node(uri: str) -> Node:
        if uri in nodes:
            return nodes[uri]
        if uri in devices:
            d = devices[uri]
            head = [d["name"]] + ([d["instance"]] if d.get("instance") else [])
            n = Node(uri, "device", head, list(d.get("terminals") or []), role=d.get("role") or "")
        elif uri in entries:
            n = Node(uri, "entry", [entries[uri]["name"]], [])
        elif uri in modules:
            n = Node(uri, "module", [modules[uri].get("name", uri)], [], modules[uri]["words"])
        elif uri.startswith("supply://"):
            n = Node(uri, "supply", ["Supply", _volts(record)], [])
        else:
            n = Node(uri, "other", [uri], [])
        nodes[uri] = n
        return n

    def row(uri: str, name: str) -> tuple[str, str]:
        n = node(uri)
        if name not in n.rows:
            n.rows.append(name)
        return uri, name

    legs: list[Leg] = []
    for w in record.get("wires", []):
        a = row(*_split(w["from"]))
        b_base, b_term = _split(w["to"])
        label = _label(w)
        if w.get("via"):
            through = row(w["via"], w["id"])
            legs.append(Leg(w, a, through, label, "in"))
            legs.append(Leg(w, through, row(b_base, b_term), label, "out"))
        else:
            legs.append(Leg(w, a, row(b_base, b_term), label))
    return nodes, legs


def _volts(record: dict[str, Any]) -> str:
    v = record.get("voltage_v")
    kind = "DC" if record.get("dc") else "AC"
    if v is None:
        return f"voltage {NOT_GIVEN}"
    if 0 < abs(v) < 1:
        return f"{_num(v * 1000)} mV {kind}"
    return f"{_num(v)} V {kind}"


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


def _wire_prims(
    nodes: dict[str, Node], routes: list[Route], labels: list[Label]
) -> dict[str, list[Prim]]:
    """Each wire's lines and labels."""
    out: dict[str, list[Prim]] = {}
    for r in routes:
        r.pts = _clean(_points(r, nodes))
        out.setdefault(r.leg.wire["id"], []).append(Path([r.pts], cls="visible"))
    long_wires = {
        wid
        for wid in out
        if len([r for r in routes if r.leg.wire["id"] == wid]) > 1
        or _length([p for r in routes if r.leg.wire["id"] == wid for p in r.pts]) > LONG
        or any(r.skips for r in routes if r.leg.wire["id"] == wid)
    }
    stacked: Counter[tuple[str, str, str]] = Counter()
    for lab in labels:
        wid = lab.route.leg.wire["id"]
        if not lab.full and wid not in long_wires:
            continue
        node, row, edge = _label_at(lab)
        k = stacked[(node.uri, row, edge)]
        stacked[(node.uri, row, edge)] = k + 1
        # alone: above the line; stacked (no free end): alternately below and above
        dy = -0.9 - LABEL_STEP * (k // 2) if k % 2 == 0 else 2.6 + LABEL_STEP * (k // 2)
        y = node.pin_y(row) + dy
        if edge == "R":
            text = Text(
                node.x1 + 1.5, y, lab.text, size=LABEL_SIZE, anchor="start", cls="wire-label"
            )
        else:
            text = Text(node.x0 - 1.5, y, lab.text, size=LABEL_SIZE, anchor="end", cls="wire-label")
        out[wid].append(text)
    return out


def _clean(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in pts:
        if not out or p != out[-1]:
            out.append(p)
    return out


def _node_prims(n: Node) -> list[Prim]:
    prims: list[Prim] = []
    if n.kind == "module":
        prims.append(Rect(n.x0, n.y0, n.w, n.h, cls="hidden"))
        prims.append(Text(n.x0, n.y0 - 2.0, n.words, size=MARK_SIZE, anchor="start", bold=True))
        for r in n.rows:
            y = n.pin_y(r)
            left, right = n.used.get((r, "L"), 0), n.used.get((r, "R"), 0)
            if not right:
                prims.append(Text(n.x1 + 1.5, y + 0.9, r, size=MARK_SIZE, anchor="start"))
            elif not left:
                prims.append(Text(n.x0 - 1.5, y + 0.9, r, size=MARK_SIZE, anchor="end"))
            else:
                prims.append(Text(n.x1 + 1.5, y - 1.2, r, size=MARK_SIZE, anchor="start"))
            prims += _pins(n, r, y)
        return prims
    prims.append(Rect(n.x0, n.y0, n.w, n.h, cls="hidden" if n.kind == "entry" else "visible"))
    for i, line in enumerate(n.head):
        size = HEAD_SIZE if n.kind != "entry" else LABEL_SIZE
        prims.append(
            Text(n.x0 + n.w / 2, n.y0 + (i + 0.5) * PITCH + 1.1, line, size=size, bold=i == 0)
        )
    if n.head and n.kind != "entry":
        prims.append(Line(n.x0, n.y0 + n.header, n.x1, n.y0 + n.header, cls="thin"))
    for r in n.rows:
        y = n.pin_y(r)
        if n.kind == "entry":
            if n.used.get((r, "L")) and n.used.get((r, "R")):
                prims.append(Line(n.x0, y, n.x1, y, cls="visible"))
        else:
            prims.append(Text(n.x0 + n.w / 2, y + 0.9, r, size=MARK_SIZE, cls="terminal"))
        prims += _pins(n, r, y)
    return prims


def _pins(n: Node, row: str, y: float) -> list[Prim]:
    out: list[Prim] = []
    if n.used.get((row, "L")):
        out.append(Circle(n.x0, y, PIN_R, cls="thin"))
    if n.used.get((row, "R")):
        out.append(Circle(n.x1, y, PIN_R, cls="thin"))
    return out


# ---- the title ------------------------------------------------------------------------------


def title_inputs() -> str:
    """What the title reads from outside the family's code, as one string.

    The checks' protected purposes and extra-low-voltage band: an input of every ``elec:``
    rule, so a change to either reruns them (the family's code is not ``checks/``).
    """
    elv = pack_rule("entry-voltage")
    return f"{','.join(PROTECTED)}|{elv.param('elv-ac')}|{elv.param('elv-dc')}"


def _band(record: dict[str, Any]) -> str | None:
    """``elv`` or ``mains`` by the circuit's voltage and the checks' band (S-158), or unknown."""
    v = record.get("voltage_v")
    if v is None:
        return None
    limit = pack_rule("entry-voltage").param("elv-dc" if record.get("dc") else "elv-ac")
    return "elv" if abs(v) <= float(magnitude_in(limit, "V")) else "mains"


def carries(record: dict[str, Any]) -> str:
    """What the circuit carries, in the title's words ("" for an earth circuit).

    The voltage for a circuit the supply feeds (power, control); a sensing circuit in words,
    its voltage only when it is above the extra-low-voltage band or not known.
    """
    purpose = record.get("purpose", "")
    if purpose == "earth":
        return ""
    if purpose == "sensing":
        band = _band(record)
        if band == "elv":
            return "extra-low-voltage signal"
        if band is None:
            return f"signal, voltage {NOT_GIVEN}"
        return f"signal at {_volts(record)}"
    return _volts(record)


def _title(record: dict[str, Any]) -> list[Prim]:
    name = record.get("name") or record.get("circuit", "")
    purpose = record.get("purpose", "")
    what = carries(record)
    head = f"{name} circuit ({purpose})" + (f", {what}" if what else "")
    protected = purpose in PROTECTED
    prims: list[Prim] = [
        Text(0, -12.0 if protected else -7.0, head, size=TITLE_SIZE, anchor="start", bold=True)
    ]
    if protected:
        prot = (record.get("protection") or {}).get("words") or NOT_GIVEN
        prims.append(Text(0, -6.0, f"Protected by: {prot}", size=MARK_SIZE, anchor="start"))
    return prims


def _cell(x: float, y: float, w: float, label: str, value: str, bold: bool = False) -> list[Prim]:
    """A footer cell: its label small at the top, its value below (the title block's form)."""
    return [
        Rect(x, y, w, FOOTER_ROW, cls="table"),
        Text(x + 1.2, y + 2.6, label, size=FOOTER_LABEL, anchor="start", cls="tblabel"),
        Text(
            x + 1.2,
            y + FOOTER_ROW - 2.0,
            value,
            size=fit_size(value, w - 2.4, HEAD_SIZE),
            anchor="start",
            bold=bold,
            cls="tbvalue",
        ),
    ]


def _footer(
    record: dict[str, Any], sheet: dict[str, Any], x: float, y: float, w: float
) -> list[Prim]:
    """The footer band under the drawing, at least ``w`` wide: product, circuit, Revision, note.

    ``sheet`` carries ``product`` (the product's name) and ``revision`` (a released
    Revision's name, else "draft"); a missing one reads "not given".
    """
    product = str(sheet.get("product") or NOT_GIVEN)
    circuit = str(record.get("name") or record.get("circuit") or NOT_GIVEN)
    revision = str(sheet.get("revision") or DRAFT)
    widths = [text_width(v, HEAD_SIZE) + 4 for v in (product, circuit)]
    rev_w = max(28.0, text_width(revision, HEAD_SIZE) + 4)
    note_w = text_width(DISCLAIMER, LABEL_SIZE) + 4
    width = max(w, sum(widths) + rev_w, note_w)
    spare = width - sum(widths) - rev_w  # to the product's cell, so the row fills the band
    pw, cw = widths[0] + spare, widths[1]
    prims: list[Prim] = []
    prims += _cell(x, y, pw, "PRODUCT", product, bold=True)
    prims += _cell(x + pw, y, cw, "CIRCUIT", circuit)
    prims += _cell(x + pw + cw, y, rev_w, "REVISION", revision, bold=True)
    yy = y + FOOTER_ROW
    prims += [
        Rect(x, yy, width, 6.0, cls="table"),
        Text(x + 1.2, yy + 4.0, DISCLAIMER, size=LABEL_SIZE, anchor="start", cls="note"),
        Rect(x, y, width, FOOTER_ROW + 6.0, cls="thin"),
    ]
    return prims


def _gid(uri: str) -> str:
    """``device://switch`` → ``switch``: the node's id within its kind."""
    return uri.split("://", 1)[-1].replace("#", "-").replace("/", "-")


def circuit_svg(record: dict[str, Any], sheet: dict[str, Any] | None = None) -> str:
    """The circuit's wiring diagram as SVG text, from its record (``connections.json``).

    ``sheet`` is what the footer says besides the record: ``product`` (the product's name)
    and ``revision`` (a released Revision's name, else "draft"), S-179.
    """
    nodes, legs = _nodes_and_legs(record)
    title = _title(record)
    groups: list[tuple[str, list[Prim], dict[str, str]]] = []
    if nodes:
        _columns(nodes, legs)
        routes = _routes(nodes, legs)
        cols: dict[int, list[str]] = {}
        for u, n in nodes.items():
            cols.setdefault(n.col, []).append(u)
        cols = dict(sorted(cols.items()))
        _stack(nodes, cols)
        _level(nodes, cols, routes)
        labels = _plan_labels(routes)
        gaps = _gaps(nodes, routes)
        _place(nodes, cols, labels, gaps)
        wires = _wire_prims(nodes, routes, labels)
        for uri, n in nodes.items():
            kind = "boundary" if n.kind == "module" else n.kind
            groups.append((f"{kind}-{_gid(uri)}", _node_prims(n), {"data_uri": uri}))
        for wid, prims in wires.items():
            groups.append((f"wire-{wid}", prims, {"data_wire": wid}))
    else:
        title.append(Text(0, 4.0, "No connections yet.", size=MARK_SIZE, anchor="start"))
    every: list[Prim] = title + [p for _, prims, _ in groups for p in prims]
    drawn = bbox_of(every)
    assert drawn is not None  # the title is always there
    footer = _footer(record, sheet or {}, drawn.x0, drawn.y1 + FOOTER_GAP, drawn.w)
    box = bbox_of(every + footer)
    assert box is not None
    dx, dy = MARGIN - box.x0, MARGIN - box.y0
    width, height = box.w + 2 * MARGIN, box.h + 2 * MARGIN
    body = [group("title", title, dx, dy)]
    body += [group(gid, prims, dx, dy, **attrs) for gid, prims, attrs in groups]
    body.append(group("footer", footer, dx, dy))
    circuit = quoteattr(str(record.get("circuit", "")))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{f(width)}mm" height="{f(height)}mm" viewBox="0 0 {f(width)} {f(height)}" '
        f"data-circuit={circuit}>"
        f"<style>text{{font-family:{FONT};fill:#000}}</style>"
        f'<rect x="0" y="0" width="{f(width)}" height="{f(height)}" fill="#fff"/>'
        + "".join(body)
        + "</svg>\n"
    )
