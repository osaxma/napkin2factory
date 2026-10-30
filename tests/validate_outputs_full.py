"""Artifact assertions beyond geometry (M5+): drawings, DXF, BOM files, docs, report."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

EXTERNAL = re.compile(r"\b(?:src|href)\s*=\s*['\"]?(?:https?:)?//", re.IGNORECASE)
MAX_REPORT = 20 * 1024 * 1024


def validate_full(root: Path, product, problems: list[str]) -> None:  # type: ignore[no-untyped-def]
    """Drawings for every custom part, DXF for sheet metal, BOM CSV/XLSX, docs HTML/PDF, report."""
    import ezdxf
    import openpyxl
    from lxml import etree
    from selectolax.lexbor import LexborHTMLParser

    build = root / "build"
    # drawings
    for part in product.parts_with_geometry():
        svg = build / "drawings" / f"{part.id}.svg"
        if not svg.is_file():
            problems.append(f"{part.uri}: missing drawing {svg.name}")
            continue
        try:
            tree = etree.parse(str(svg))
        except etree.XMLSyntaxError as exc:
            problems.append(f"{part.uri}: drawing SVG does not parse: {exc}")
            continue
        ids = {el.get("id") for el in tree.getroot().iter() if el.get("id")}
        for g in ("view-front", "view-top", "view-right", "view-iso", "titleblock"):
            if g not in ids:
                problems.append(f"{part.uri}: drawing lacks <g id='{g}'>")
        if part.process == "sheet-metal":
            dxf = build / "drawings" / f"{part.id}-flat.dxf"
            if not dxf.is_file():
                problems.append(f"{part.uri}: sheet-metal part has no flat-pattern DXF")
            else:
                doc = ezdxf.readfile(str(dxf))
                layers = {ln.dxf.name for ln in doc.layers}
                if "BEND" not in layers:
                    problems.append(f"{part.uri}: DXF has no BEND layer")
            if "view-flat" not in ids:
                problems.append(f"{part.uri}: sheet-metal drawing has no flat-pattern view")
    # bom
    for name in ("rollups.json", "validation.json", "bom.csv", "bom.xlsx"):
        if not (build / "bom" / name).is_file():
            problems.append(f"bom: missing {name}")
    rollups = (
        json.loads((build / "bom" / "rollups.json").read_text())
        if (build / "bom" / "rollups.json").is_file()
        else {}
    )
    if (build / "bom" / "bom.xlsx").is_file():
        wb = openpyxl.load_workbook(str(build / "bom" / "bom.xlsx"), data_only=True)
        if "BOM" not in wb.sheetnames:
            problems.append("bom.xlsx has no BOM sheet")
        else:
            cells = [
                str(c.value) for row in wb["BOM"].iter_rows() for c in row if c.value is not None
            ]
            if (
                rollups
                and f"{rollups['total_cost']:.2f}" not in " ".join(cells)
                and str(rollups["total_cost"]) not in cells
            ):
                problems.append("bom.xlsx totals do not include rollups total_cost")
    if (build / "bom" / "bom.csv").is_file():
        with (build / "bom" / "bom.csv").open(newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        if not rows or "uri" not in rows[0]:
            problems.append("bom.csv has no header with 'uri'")
    # docs
    for doc in product.docs.values():
        d = build / "docs" / doc.meta.id
        for name in ("page.md", "page.html", "reads.json"):
            if not (d / name).is_file():
                problems.append(f"{doc.uri}: missing {name}")
        pdf = d / "page.pdf"
        if not pdf.is_file():
            problems.append(
                f"{doc.uri}: missing page.pdf"
                + (
                    f" ({(d / 'page.pdf.error.txt').read_text()[:120]})"
                    if (d / "page.pdf.error.txt").is_file()
                    else ""
                )
            )
        elif pdf.read_bytes()[:5] != b"%PDF-" or pdf.read_bytes().count(b"/Type /Page") < 1:
            problems.append(f"{doc.uri}: page.pdf is not a PDF with pages")
        if (d / "page.html").is_file():
            tree = LexborHTMLParser((d / "page.html").read_text(encoding="utf-8"))
            if tree.css_first("h1") is None and tree.css_first("h2") is None:
                problems.append(f"{doc.uri}: page.html has no headings")
    safety_pages = [d for d in product.docs.values() if d.meta.safety]
    if not safety_pages:
        problems.append("docs: no page with safety: true (a Safety section is mandatory)")
    # checks
    checks = build / "checks" / "checks.json"
    if not checks.is_file():
        problems.append("checks: missing checks.json")
    else:
        data = json.loads(checks.read_text())
        fails = [r["id"] for r in data.get("results", []) if r["status"] == "fail"]
        if fails:
            problems.append(f"checks: failing rows: {', '.join(fails[:8])}")
    # report
    report = build / "report" / "index.html"
    if not report.is_file():
        problems.append("report: missing build/report/index.html")
    else:
        html = report.read_text(encoding="utf-8")
        size = report.stat().st_size
        if size > MAX_REPORT:
            problems.append(f"report: {size / 1e6:.1f} MB exceeds the 20 MB budget (D13)")
        tree = LexborHTMLParser(html)
        if tree.css("script[src]") or tree.css("link") or EXTERNAL.search(html):
            problems.append("report: has external script/link/asset references (D13)")
        modules = [s for s in tree.css("script") if s.attributes.get("type") == "module"]
        if len(modules) != 1 and any(p.has_geometry for p in product.parts.values()):
            problems.append(f"report: expected one inline module script, found {len(modules)}")
        for part in product.parts.values():
            if part.uri not in html:
                problems.append(f"report: {part.uri} not mentioned")
        for rid in product.requirements:
            if f'id="req-{rid}"' not in html:
                problems.append(f"report: requirement {rid} row missing")
        if "not been reviewed by a licensed engineer" not in html:
            problems.append("report: disclaimer missing")
        for s in product.signoffs.values():
            if s.example and "EXAMPLE SIGN-OFF, NOT A REVIEW" not in html:
                problems.append(f"report: example sign-off {s.requirement} is not labelled")
    site = build / "site" / "index.html"
    if not site.is_file():
        problems.append("site: missing build/site/index.html")
