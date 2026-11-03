"""The wiring diagram of one circuit (ELECTRICAL_STAGE E5), drawn from its record.

A pure function of ``connections.json`` (the wave-2 contract), so the diagram can never
disagree with the schedule.  The layout reads left to right (S-157, S-174; layout primitives
split to ``diagram_layout.py`` in S-184):

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
  half a row, so two horizontal runs in one gap never lie on the same line.

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
from typing import Any
from xml.sax.saxutils import quoteattr

from napkin2factory.core.units import magnitude_in
from napkin2factory.domains.electrical.checks.pack import rule as pack_rule
from napkin2factory.domains.electrical.checks.stage import PROTECTED
from napkin2factory.domains.electrical.outputs.diagram_layout import (
    FAN,
    GAP,
    HEAD_SIZE,
    LABEL_SIZE,
    LABEL_STEP,
    LANE,
    LONG,
    MARK_SIZE,
    NOT_GIVEN,
    PITCH,
    SOURCE_ROLES,
    TRACK,
    Label,
    Leg,
    Node,
    Route,
    Seg,
    _between,
    _channels,
    _clean,
    _columns,
    _cross,
    _gaps,
    _inside,
    _label_at,
    _lanes,
    _length,
    _level,
    _order_tracks,
    _place,
    _plan_labels,
    _points,
    _routes,
    _sources,
    _stack,
)
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

MARGIN = 10.0
TITLE_SIZE = 4.0
PIN_R = 0.8
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


__all__ = [
    "DISCLAIMER",
    "DRAFT",
    "FAN",
    "FOOTER_GAP",
    "FOOTER_LABEL",
    "FOOTER_ROW",
    "GAP",
    "HEAD_SIZE",
    "LABEL_SIZE",
    "LABEL_STEP",
    "LANE",
    "LONG",
    "MARGIN",
    "MARK_SIZE",
    "NOT_GIVEN",
    "PIN_R",
    "PITCH",
    "SOURCE_ROLES",
    "TITLE_SIZE",
    "TRACK",
    "Label",
    "Leg",
    "Node",
    "Route",
    "Seg",
    "_between",
    "_channels",
    "_clean",
    "_columns",
    "_cross",
    "_gaps",
    "_inside",
    "_label_at",
    "_lanes",
    "_length",
    "_level",
    "_order_tracks",
    "_place",
    "_plan_labels",
    "_points",
    "_routes",
    "_sources",
    "_stack",
    "carries",
    "circuit_svg",
    "title_inputs",
]
