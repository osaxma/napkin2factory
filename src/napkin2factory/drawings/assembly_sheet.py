"""``asmsheet:<id>`` run: one A3 assembly sheet per build unit (P8).

Outputs in ``build/drawings/assemblies/``:

* ``<id>.svg`` — the unit assembled (the assembly's iso render) and pulled apart (its
  ``exploded.png``, the viewer's full explode), an item table keyed to the BOM lines of the
  build step, the joints the step closes with their hardware by item number, and a title
  block.  The pictures are embedded as PNG data, so the sheet is self-contained (D13) and the
  report can inline it.  No hidden-line views or balloons (a v0.4 non-goal), so the footer
  does not promise numbered pictures (gate D).  Owner words throughout (N5): a cell that
  would need text below 2.2 mm wraps to two lines instead (gate D, S-118).
* ``<id>.json`` — step, item and joint counts, which pictures were found, rows left out.

Phantoms get no sheet: their lines are on the sheet of the unit they fold into.  The output
hash leaves out the date, as part drawings do (D14).
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.sax.saxutils import quoteattr

from napkin2factory import __version__
from napkin2factory.core.graph.hashing import sha256_text
from napkin2factory.drawings.sheet import PAGE_H, PAGE_W, SHEET, date_words
from napkin2factory.drawings.svg import FONT, Line, Prim, Rect, Text, f, fit_size, group

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext, RunResult

SHEET_DIR = Path("drawings") / "assemblies"
FRAME = 10.0
LEFT = (15.0, 213.0)  # picture column, x range
RIGHT = (221.0, 405.0)  # tables column, x range
TOP, BOTTOM = 15.0, 282.0
TB_W, TB_H = 184.0, 40.0
TB_X, TB_Y = PAGE_W - FRAME - TB_W - 1.0, PAGE_H - FRAME - TB_H - 1.0
ROW_MAX, ROW_MIN = 5.0, 2.8
#: The smallest table text before a cell wraps to two lines: the floor the title block's
#: note keeps (gate D found hinge rows shrunk to 1.59 mm on A3, about 1.1 mm on A4).
MIN_TEXT = 2.2
#: How much taller a wrapped row is, in rows, for the room estimate (≈ 1.2 × 0.55).
WRAP_EXTRA = 0.7

ITEM_COLS = (("ITEM", 12.0), ("PART NO.", 44.0), ("NAME", 92.0), ("QTY", 14.0), ("NOTE", 22.0))
JOINT_COLS = (("JOINT", 82.0), ("×", 10.0), ("HOLES", 14.0), ("HARDWARE (QTY × ITEM)", 78.0))


def _split(val: str, n: int) -> list[str]:
    """``val`` in ``n`` lines of about equal length, broken at spaces (greedy)."""
    words, lines, budget = val.split(" "), [""], len(val) / n
    for word in words:
        if lines[-1] and len(lines[-1]) + 1 + len(word) > budget and len(lines) < n:
            lines.append(word)
        else:
            lines[-1] = f"{lines[-1]} {word}" if lines[-1] else word
    return lines


def _wrap(val: str, width: float, size: float) -> tuple[list[str], float]:
    """A cell's lines and size: one line at ≥ ``MIN_TEXT``, else two or three lines."""
    lines = [val]
    fit = fit_size(val, width, size, minimum=0.0)
    for n in (2, 3):
        if fit >= MIN_TEXT or " " not in val:
            break
        lines = _split(val, n)
        fit = min(fit_size(ln, width, size, minimum=0.0) for ln in lines)
    return lines, max(fit, 1.4)


def wrapped_rows(cols: tuple[tuple[str, float], ...], rows: list[list[str]], size: float) -> int:
    """How many of ``rows`` need two lines at ``size``."""
    return sum(
        1
        for cells in rows
        if any(len(_wrap(v, cw - 2.0, size)[0]) > 1 for (_, cw), v in zip(cols, cells, strict=True))
    )


@dataclass
class _Picture:
    label: str
    path: Path


def sheet_path(build_dir: Path, unit_id: str) -> Path:
    """Where the unit's sheet is written."""
    return build_dir / SHEET_DIR / f"{unit_id}.svg"


def _picture(x: float, y: float, w: float, h: float, pic: _Picture) -> tuple[str, bool]:
    """A captioned picture box; the PNG is embedded (``data:``), or a note when absent."""
    caption = Text(x + 1.5, y + 4.0, pic.label, size=3.0, anchor="start", bold=True, cls="caption")
    frame = Rect(x, y, w, h, cls="thin")
    body = frame.svg() + caption.svg()
    if pic.path.is_file():
        data = base64.b64encode(pic.path.read_bytes()).decode()
        body += (
            f'<image x="{f(x + 1)}" y="{f(y + 6)}" width="{f(w - 2)}" height="{f(h - 7)}" '
            f'preserveAspectRatio="xMidYMid meet" href="data:image/png;base64,{data}"/>'
        )
        return body, True
    note = "no picture: the assembly was built without renders"
    body += Text(x + w / 2, y + h / 2, note, size=3.0, cls="note").svg()
    return body, False


def _table(
    x: float,
    y: float,
    title: str,
    cols: tuple[tuple[str, float], ...],
    rows: list[list[str]],
    rh: float,
) -> tuple[list[Prim], float]:
    """A titled table at ``(x, y)``; returns the primitives and the y below it.

    A row whose cell would need text below ``MIN_TEXT`` gets two lines and a taller row.
    """
    size = min(2.5, rh * 0.55)
    prims: list[Prim] = [
        Text(x, y + rh * 0.75, title, size=min(3.2, rh * 0.7), anchor="start", bold=True)
    ]
    top = y + rh
    w = sum(c[1] for c in cols)
    all_rows = [[c[0] for c in cols], *rows]
    laid = [
        [_wrap(val, cw - 2.0, size) for (_, cw), val in zip(cols, cells, strict=True)]
        for cells in all_rows
    ]
    heights = [rh + (max(len(lines) for lines, _ in row) - 1) * size * 1.2 for row in laid]
    total = sum(heights)
    prims.append(Rect(x, top, w, total))
    cx = x
    for _, cw in cols[:-1]:
        cx += cw
        prims.append(Line(cx, top, cx, top + total, cls="table"))
    ry = top
    for i, row in enumerate(laid):
        if i:
            prims.append(Line(x, ry, x + w, ry, cls="table"))
        cx = x
        for (_, cw), (lines, tsize) in zip(cols, row, strict=True):
            if len(lines) == 1 and heights[i] == rh:
                baselines = [ry + rh * 0.72]
            else:
                pitch = tsize * 1.2
                block = pitch * (len(lines) - 1) + tsize * 0.95
                first = ry + (heights[i] - block) / 2 + tsize * 0.75
                baselines = [first + k * pitch for k in range(len(lines))]
            for ln, by in zip(lines, baselines, strict=True):
                prims.append(
                    Text(
                        cx + 1.0,
                        by,
                        ln,
                        size=tsize,
                        anchor="start",
                        bold=i == 0,
                        cls="tablehead" if i == 0 else "cell",
                    )
                )
            cx += cw
        ry += heights[i]
    return prims, top + total


def _title_block(step: dict[str, Any], total: int, date: str) -> list[Prim]:
    x, y = TB_X, TB_Y
    title = step["title"]
    note = (
        f"Generated by napkin2factory {__version__}. Pictures not to scale and not numbered; "
        "the item numbers in the tables match the build plan. Produced with an AI system; not "
        "reviewed by a licensed engineer."
    )
    cells = [
        (x, y + 14, 46.0, "STEP", f"{step['step']} of {total}"),
        (x + 46, y + 14, 46.0, "SHEET", SHEET),
        (x + 92, y + 14, 46.0, "DATE", date_words(date) if date else date),
        (x + 138, y + 14, 46.0, "BUILT PER PRODUCT", str(step["built_per_product"])),
    ]
    prims: list[Prim] = [
        Rect(x, y, TB_W, TB_H, cls="frame"),
        Rect(x, y, 150, 14),
        Text(x + 1.2, y + 2.6, "ASSEMBLY", size=1.8, anchor="start", cls="tblabel"),
        Text(x + 1.2, y + 8.0, title, size=fit_size(title, 147, 5.0), anchor="start", bold=True),
        Text(
            x + 1.2,
            y + 12.4,
            step["unit"].removeprefix("asm://"),
            size=2.6,
            anchor="start",
            cls="uri",
        ),
        Rect(x + 150, y, 34, 14),
        Text(x + 151.2, y + 2.6, "REV", size=1.8, anchor="start", cls="tblabel"),
        Text(x + 167, y + 11.5, step["rev"], size=7.0, bold=True, cls="rev"),
    ]
    for cx, cy, cw, label, value in cells:
        prims += [
            Rect(cx, cy, cw, 10),
            Text(cx + 1.2, cy + 2.6, label, size=1.8, anchor="start", cls="tblabel"),
            Text(cx + 1.2, cy + 8.0, value, size=fit_size(value, cw - 2.4, 3.2), anchor="start"),
        ]
    cut = note.rfind(" ", 0, len(note) // 2 + 10)
    lines = (note[:cut], note[cut + 1 :])
    size = min(fit_size(ln, 181, 2.2) for ln in lines)
    prims.append(Rect(x, y + 24, TB_W, TB_H - 24))
    for i, ln in enumerate(lines):
        prims.append(Text(x + 1.2, y + 29.0 + 4.0 * i, ln, size=size, anchor="start"))
    return prims


def _rows(step: dict[str, Any]) -> tuple[list[list[str]], list[list[str]]]:
    from napkin2factory.bom.build_plan import NO_FIXINGS

    item_of = {it["uri"]: it["item"] for it in step["items"]}
    items = []
    for it in step["items"]:
        note = []
        if it["kind"] == "unit":
            note.append(f"step {it.get('step')}")
        elif it["kind"] == "cots":
            note.append("bought")
        if it.get("group"):
            note.append(it["group"])
        if it.get("loose"):
            note.append("loose")
        if it.get("spare"):
            note.append("spare")
        items.append([str(it["item"]), it["id"], it["name"], str(it["qty"]), ", ".join(note)])
    joints = []
    for j in step["joints"]:
        hw = " + ".join(
            f"{h['qty']} × "
            + (
                f"item {item_of[h['part']]}"
                if h["part"] in item_of
                else f"{h['name']}" + (f" (step {j['from_step']})" if "from_step" in j else "")
            )
            for h in j["hardware"]
        )
        marks = []
        if j.get("closed_later_step"):
            marks.append(f"closed in step {j['closed_later_step']}")
        if "from_step" in j:
            marks.append(f"left open in step {j['from_step']}")
        if j["between_units"]:
            marks.append("between units")
        words = j["words"] + (f" ({'; '.join(marks)})" if marks else "")
        joints.append([words, str(j["occurrences"]), str(j["holes"] or "none"), hw or NO_FIXINGS])
    return items, joints


def compose_sheet(
    step: dict[str, Any], total: int, pictures: list[_Picture], date: str
) -> tuple[str, str, dict[str, Any]]:
    """The sheet's SVG text, the text hashed (no date), and its summary."""
    items, joints = _rows(step)
    avail = TB_Y - 6.0 - TOP
    head_rows = 2.0  # the step heading
    fixed = head_rows + 2 + (2 if joints else 0)  # table titles and header rows
    rows_wanted = len(items) + len(joints)
    rows_wanted += WRAP_EXTRA * (
        wrapped_rows(ITEM_COLS, items, 2.5) + wrapped_rows(JOINT_COLS, joints, 2.5)
    )
    rh = max(ROW_MIN, min(ROW_MAX, avail / (fixed + rows_wanted)))
    room = int(avail / rh - fixed)
    left_out = 0
    if rows_wanted > room:
        keep = max(1, room - len(joints) - 1)
        left_out = len(items) - keep
        items = items[:keep] + [["…", "", f"{left_out} more lines: see the BOM", "", ""]]
    x0 = RIGHT[0]
    heading = f"Step {step['step']}: {step['title']}"
    from napkin2factory.bom.build_plan import item_range, lower_name
    from napkin2factory.core.build_units import and_words

    why = and_words(step["driver_words"])
    prims: list[Prim] = [
        Text(x0, TOP + 5.0, heading, size=fit_size(heading, 184, 5.0), anchor="start", bold=True)
    ]
    if why or step["folded"]:
        sub = (f"on its own because it is {why}" if why else "") + "".join(
            f"{'; ' if why or i else ''}the {lower_name(fo['name'])}"
            + (f" ({item_range(fo.get('items', []))})" if fo.get("items") else "")
            + " is laid in place in this step"
            for i, fo in enumerate(step["folded"])
        )
        sub = sub[:1].upper() + sub[1:]
        prims.append(Text(x0, TOP + 9.5, sub, size=fit_size(sub, 184, 2.8), anchor="start"))
    y = TOP + head_rows * 5.5
    tprims, y = _table(x0, y, "PARTS FOR THIS STEP", ITEM_COLS, items, rh)
    prims += tprims
    if joints:
        tprims, y = _table(x0, y + rh * 0.5, "JOINTS CLOSED IN THIS STEP", JOINT_COLS, joints, rh)
        prims += tprims
    pic_h = (BOTTOM - TOP - 6.0) / 2
    pics_svg = []
    found = []
    for i, pic in enumerate(pictures):
        svg, ok = _picture(LEFT[0], TOP + i * (pic_h + 6.0), LEFT[1] - LEFT[0], pic_h, pic)
        pics_svg.append(svg)
        if ok:
            found.append(pic.path.stem)
    frame = Rect(FRAME, FRAME, PAGE_W - 2 * FRAME, PAGE_H - 2 * FRAME, cls="frame")
    head = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{f(PAGE_W)}mm" height="{f(PAGE_H)}mm" viewBox="0 0 {f(PAGE_W)} {f(PAGE_H)}" '
        f'data-assembly={quoteattr(step["unit"])} data-step="{step["step"]}">'
        f"<style>text{{font-family:{FONT};fill:#000}}</style>"
        f'<rect id="sheet" x="0" y="0" width="{f(PAGE_W)}" height="{f(PAGE_H)}" fill="#fff"/>'
        + group("frame", [frame])
    )
    body = f'<g id="pictures">{"".join(pics_svg)}</g>' + group("tables", prims)
    svg = head + body + group("titleblock", _title_block(step, total, date)) + "</svg>\n"
    stable = head + body + group("titleblock", _title_block(step, total, "")) + "</svg>\n"
    meta = {
        "unit": step["unit"],
        "step": step["step"],
        "sheet": SHEET,
        "items": len(step["items"]),
        "joints": len(step["joints"]),
        "pictures": found,
        "rows_left_out": left_out,
    }
    return svg, stable, meta


def make_assembly_sheet(ctx: RunContext, unit_id: str) -> RunResult:
    """Write the assembly sheet of build unit ``asm://<unit_id>``.

    Args:
        ctx: the build context (product, build dir, the plan the ``bom`` rule just wrote).
        unit_id: the build unit to draw (a key of the plan's ``units``).

    Returns:
        The run result: reads (the assembly and its plan step), outputs, output hash.
    """
    from napkin2factory.bom.build_plan import PLAN_FILE, derive_build_plan, plan_key
    from napkin2factory.core.graph.rules import RunResult

    plan = ctx.payloads.get("build_plan")
    if plan is None:
        path = ctx.build_dir / "bom" / PLAN_FILE
        plan = (
            json.loads(path.read_text(encoding="utf-8"))
            if path.is_file()
            else derive_build_plan(ctx.product)
        )
    step = plan["units"][unit_id]
    renders = ctx.build_dir / "assemblies" / unit_id / "renders"
    pictures = [
        _Picture("ASSEMBLED", renders / "iso.png"),
        _Picture("PULLED APART", renders / "exploded.png"),
    ]
    svg, stable, meta = compose_sheet(step, len(plan["order"]), pictures, ctx.snapshot_date)
    out = sheet_path(ctx.build_dir, unit_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    meta_path = out.with_suffix(".json")
    for target, text in ((out, svg), (meta_path, json.dumps(meta, indent=2) + "\n")):
        tmp = target.with_name(f".{target.name}.tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, target)
    # "STEP n of N": the plan's order is read too, so adding a unit redraws every sheet
    reads = [f"asm://{unit_id}", plan_key(unit_id), "bom://build-plan#order"]
    return RunResult(reads=reads, outputs=[out, meta_path], output_hash=sha256_text(stable))
