"""The wiring diagram of one circuit (ELECTRICAL_STAGE E5), drawn from its record.

A pure function of ``connections.json`` (the wave-2 contract), so the diagram can never
disagree with the schedule.  The layout reads left to right from the supply (S-157):

* every node is a box in a column: the supply, each device (its part's name and instance
  words, a row per terminal with its marking), each cable entry (a dashed box the wires
  pass straight through, one row per wire), and each module supplied from elsewhere (a
  dashed boundary with its words above it and nothing drawn inside, DoD 5);
* a node's column is its distance from the supply along the wires (the longest, so a load
  sits right of the switch that feeds it); a circuit that does not reach the supply starts
  from its first end;
* each wire is an orthogonal line on its own vertical track in the gap right of its
  left end, labelled at that end with its id, cross-section and colour; a wire that skips
  a column runs along its own lane below the boxes.  Columns alternate by half a row, so
  two horizontal runs in one gap never lie on the same line.

Terminals are small circles (IEC 60617's terminal) where a wire lands.  Every coordinate is
rounded by the drawings' serialiser and nothing depends on time, so a golden holds it.  The
SVG is self-contained (its font in a ``<style>``), as the ``file://`` report needs (D13).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from xml.sax.saxutils import quoteattr

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


@dataclass
class Node:
    """A box: the supply, a device, a cable entry or a module supplied from elsewhere."""

    uri: str
    kind: str  # supply | device | entry | module | other
    head: list[str]
    rows: list[str]
    words: str = ""  # a module's boundary words (above its box)
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
    a: tuple[str, str]  # (node uri, row)
    b: tuple[str, str]
    label: str


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
            n = Node(uri, "device", head, list(d.get("terminals") or []))
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
            legs.append(Leg(w, a, through, label))
            legs.append(Leg(w, through, row(b_base, b_term), label))
        else:
            legs.append(Leg(w, a, row(b_base, b_term), label))
    return nodes, legs


def _volts(record: dict[str, Any]) -> str:
    v = record.get("voltage_v")
    kind = "DC" if record.get("dc") else "AC"
    return f"{_num(v)} V {kind}" if v is not None else f"voltage {NOT_GIVEN}"


def _columns(nodes: dict[str, Node], legs: list[Leg]) -> None:
    """Each node's column: its distance from the supply, the longest along the wires."""
    order = list(nodes)
    adj: dict[str, list[str]] = {u: [] for u in order}
    for leg in legs:
        adj[leg.a[0]].append(leg.b[0])
        adj[leg.b[0]].append(leg.a[0])
    depth: dict[str, int] = {}
    roots = [u for u in order if nodes[u].kind == "supply"] + order
    for root in roots:
        if root in depth:
            continue
        depth[root] = 0
        queue = [root]
        while queue:
            u = queue.pop(0)
            for v in adj[u]:
                if v not in depth:
                    depth[v] = depth[u] + 1
                    queue.append(v)
    # orient each leg away from the root (ties: as the wire is written), then push every
    # node right of what feeds it; bounded, so a loop among equals cannot run away
    edges = []
    for leg in legs:
        u, v = leg.a[0], leg.b[0]
        if u == v:
            continue
        edges.append((v, u) if depth[v] < depth[u] else (u, v))
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


def _place(nodes: dict[str, Node], legs: list[Leg]) -> tuple[list[float], list[float]]:
    """Box sizes and positions; returns each column's left x and each gap's left x."""
    ncols = 1 + max((n.col for n in nodes.values()), default=0)
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
    # each gap: a zone for the labels of the wires leaving the column, then one track each
    label_w = [0.0] * ncols
    tracks = [0] * ncols
    for leg in legs:
        ca, cb = nodes[leg.a[0]].col, nodes[leg.b[0]].col
        lo, hi = min(ca, cb), max(ca, cb)
        label_w[lo] = max(label_w[lo], text_width(leg.label, LABEL_SIZE))
        tracks[lo] += 1
        if hi - lo > 1:
            tracks[hi - 1] += 1
    col_x: list[float] = []
    gap_x: list[float] = []
    x = 0.0
    for c in range(ncols):
        col_x.append(x)
        gap_x.append(x + col_w[c])
        x += col_w[c] + label_w[c] + 6 + tracks[c] * TRACK + 6
    ys = [(c % 2) * PITCH / 2 for c in range(ncols)]
    for n in nodes.values():  # in order of first appearance along the wires
        n.x0 = col_x[n.col] + (col_w[n.col] - n.w) / 2
        n.y0 = ys[n.col] + (2 * PITCH if n.kind == "module" else 0.0)
        ys[n.col] = n.y0 + n.h + GAP
    return col_x, [g + lw + 6 for g, lw in zip(gap_x, label_w, strict=True)]


def _wire_prims(
    nodes: dict[str, Node], legs: list[Leg], track_x: list[float]
) -> dict[str, list[Prim]]:
    """Each wire's lines and labels, and the pins they land on."""
    bottom = max(n.y0 + n.h for n in nodes.values())
    used_tracks = [0] * len(track_x)
    lanes = 0
    stacked: dict[tuple[str, str], int] = {}
    out: dict[str, list[Prim]] = {}

    def track(c: int) -> float:
        x = track_x[c] + used_tracks[c] * TRACK
        used_tracks[c] += 1
        return x

    for leg in legs:
        (ua, ra), (ub, rb) = leg.a, leg.b
        na, nb = nodes[ua], nodes[ub]
        if nb.col < na.col:
            (na, ra), (nb, rb) = (nb, rb), (na, ra)
        ya, yb = na.pin_y(ra), nb.pin_y(rb)
        xa = na.x1
        na.used[(ra, "R")] = na.used.get((ra, "R"), 0) + 1
        if nb.col == na.col:
            t = track(na.col)
            xb = nb.x1
            nb.used[(rb, "R")] = nb.used.get((rb, "R"), 0) + 1
            pts = [(xa, ya), (t, ya), (t, yb), (xb, yb)]
        else:
            xb = nb.x0
            nb.used[(rb, "L")] = nb.used.get((rb, "L"), 0) + 1
            if nb.col == na.col + 1:
                t = track(na.col)
                pts = [(xa, ya), (t, ya), (t, yb), (xb, yb)]
            else:
                t1, t2 = track(na.col), track(nb.col - 1)
                lane = bottom + GAP / 2 + lanes * LANE
                lanes += 1
                pts = [(xa, ya), (t1, ya), (t1, lane), (t2, lane), (t2, yb), (xb, yb)]
        # the label sits on the run leaving the left end; a second wire on one terminal
        # writes below the line, a third above the first
        k = stacked.get((na.uri, ra), 0)
        stacked[(na.uri, ra)] = k + 1
        dy = (-0.9, 2.6, -3.4, 5.1)[min(k, 3)]
        prims = out.setdefault(leg.wire["id"], [])
        prims.append(Path([_clean(pts)], cls="visible"))
        prims.append(
            Text(xa + 1.5, ya + dy, leg.label, size=LABEL_SIZE, anchor="start", cls="wire-label")
        )
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


def _title(record: dict[str, Any]) -> list[Prim]:
    name = record.get("name") or record.get("circuit", "")
    purpose = record.get("purpose", "")
    prot = (record.get("protection") or {}).get("words") or NOT_GIVEN
    return [
        Text(
            0,
            -12.0,
            f"{name} circuit ({purpose}), {_volts(record)}",
            size=TITLE_SIZE,
            anchor="start",
            bold=True,
        ),
        Text(0, -6.0, f"Protected by: {prot}", size=MARK_SIZE, anchor="start"),
    ]


def _gid(uri: str) -> str:
    """``device://switch`` → ``switch``: the node's id within its kind."""
    return uri.split("://", 1)[-1].replace("#", "-").replace("/", "-")


def circuit_svg(record: dict[str, Any]) -> str:
    """The circuit's wiring diagram as SVG text, from its record (``connections.json``)."""
    nodes, legs = _nodes_and_legs(record)
    title = _title(record)
    groups: list[tuple[str, list[Prim], dict[str, str]]] = []
    if nodes:
        _columns(nodes, legs)
        _, track_x = _place(nodes, legs)
        wires = _wire_prims(nodes, legs, track_x)
        for uri, n in nodes.items():
            kind = "boundary" if n.kind == "module" else n.kind
            groups.append((f"{kind}-{_gid(uri)}", _node_prims(n), {"data_uri": uri}))
        for wid, prims in wires.items():
            groups.append((f"wire-{wid}", prims, {"data_wire": wid}))
    else:
        title.append(Text(0, 4.0, "No connections yet.", size=MARK_SIZE, anchor="start"))
    every: list[Prim] = title + [p for _, prims, _ in groups for p in prims]
    box = bbox_of(every)
    assert box is not None  # the title is always there
    dx, dy = MARGIN - box.x0, MARGIN - box.y0
    width, height = box.w + 2 * MARGIN, box.h + 2 * MARGIN
    body = [group("title", title, dx, dy)]
    body += [group(gid, prims, dx, dy, **attrs) for gid, prims, attrs in groups]
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
