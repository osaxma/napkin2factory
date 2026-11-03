"""Build plan steps, unit joints, module groupings, choices; split from builder.py (S-184)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from napkin2factory.core.checks.results import SUMMARY_KEYS, is_example_signoff
from napkin2factory.core.loader import Product


def _viewer_options(product: Product) -> str:
    """Viewer options as JSON: the style palette by part role when ``style.yaml`` exists.

    Products without the file keep the viewer's hash colours (and get no options at all).
    """
    from napkin2factory.core.errors import N2FError
    from napkin2factory.core.model.style import role_for
    from napkin2factory.core.style import load_style, style_path

    if not style_path(product.paths.root).is_file():
        return ""
    try:
        style = load_style(product.paths.root)
    except N2FError:
        return ""
    materials = {p.uri: style.material(role_for(p)) for p in product.parts_with_geometry()}
    return json.dumps({"materials": materials}, sort_keys=True)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _doc_html(build_dir: Path, doc_id: str, markdown: str) -> str:
    """Prefer the docs engine's fragment renderer; fall back to a plain markdown-it render.

    The page's own top-level title is dropped: the report shows the title itself.
    """
    try:
        from napkin2factory.docs.html import render_fragment

        html = str(render_fragment(markdown))
    except ImportError:
        from markdown_it import MarkdownIt

        html = str(MarkdownIt("gfm-like").render(markdown))
    return re.sub(r"^\s*<h1[^>]*>.*?</h1>\s*", "", html, count=1, flags=re.DOTALL)


def _flatten_bom(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ln in lines:
        out.append(ln)
        out.extend(_flatten_bom(ln.get("children", [])))
    return out


def _bom_by_uri(flat: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for ln in flat:
        agg = out.setdefault(
            ln["uri"],
            {
                "name": ln["name"],
                "kind": ln["kind"],
                "total_qty": 0,
                "unit_cost": ln.get("unit_cost"),
                "manufacturer": ln.get("manufacturer", ""),
            },
        )
        agg["total_qty"] += int(ln.get("total_qty", 0))
    return out


def _spec_summary(spec: Any) -> str:
    from napkin2factory.core.model import BoltPatternSpec, MatingFaceSpec

    # by the spec's type: a domain kind's spec may subclass the core's (S-144)
    if isinstance(spec, BoltPatternSpec):
        return f"{spec.count} × ⌀{spec.diameter}, {spec.pattern}"
    if isinstance(spec, MatingFaceSpec):
        return f"{spec.width} × {spec.depth}"
    return type(spec).__name__


def _build_steps(
    build_dir: Path, results: dict[str, dict[str, Any]], words: dict[str, str]
) -> list[dict[str, Any]]:
    """The build plan's steps (P8) with each unit's sheet inlined and its checks' verdicts.

    The plan holds static check ids (``bom`` runs before ``checks``); here they meet the
    verdicts of this run.  An id with no row yet reads "not checked".
    """
    from napkin2factory.bom.build_plan import (
        PLAN_FILE,
        folded_sentence,
        hardware_words,
        item_notes,
        joint_status_words,
    )
    from napkin2factory.core.build_units import driver_sentence
    from napkin2factory.drawings.assembly_sheet import sheet_path

    plan = _read_json(build_dir / "bom" / PLAN_FILE) or {"order": [], "units": {}}
    steps = []
    for uid in plan.get("order", []):
        step = dict(plan["units"][uid])
        # owner words for the template (gate D): the same helpers as the manual's steps
        step["why"] = step.get("driver_sentence") or driver_sentence(step.get("driver", []))
        step["folded_words"] = [folded_sentence(f) for f in step.get("folded", [])]
        # a unit's line links its step in the part column already
        step["items"] = [
            {**it, "notes": [n for n in item_notes(it) if not n.startswith("built ")]}
            for it in step.get("items", [])
        ]
        step["joints"] = [
            {**j, "hardware_words": hardware_words(j), "status_words": joint_status_words(j)}
            for j in step.get("joints", [])
        ]
        svg_path = sheet_path(build_dir, uid)
        svg = svg_path.read_text(encoding="utf-8") if svg_path.is_file() else ""
        step["id"] = uid
        step["sheet_svg"] = svg.split("?>", 1)[1] if svg.startswith("<?xml") else svg
        checks = []
        for cid in step.get("checks", []):
            r = results.get(cid)
            checks.append(
                {
                    "id": cid,
                    "status": r["status"] if r else "skip",
                    # an example sign-off is counted apart, never as a review (S-042)
                    "example": bool(r and is_example_signoff(r["status"], r.get("detail", {}))),
                    "title": (r.get("title") or cid) if r else cid,
                    "message": r.get("message", "") if r else "not checked yet",
                }
            )
        step["check_rows"] = checks
        counts = {
            k: sum(1 for c in checks if ("example" if c["example"] else c["status"]) == k)
            for k in SUMMARY_KEYS
        }
        step["check_summary"] = " · ".join(f"{n} {words.get(k, k)}" for k, n in counts.items() if n)
        steps.append(step)
    return steps


def _between_units(
    build_dir: Path, product: Product, results: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Every joint between units (P13) from the build plan, with its check's verdict.

    The verdict is the interface's own row (the hole pattern or mating face, then where the
    parts meet once placed, P3); the review notes are the product's decisions that link the
    joint (a candidate to combine two parts is logged that way, P13).  No verdict is made here
    on whether the two parts should be one: that is the verifier's judgment.
    """
    from napkin2factory.bom.build_plan import PLAN_FILE

    plan = _read_json(build_dir / "bom" / PLAN_FILE) or {}
    out = []
    for j in plan.get("between_units", []):
        from napkin2factory.bom.build_plan import hardware_words

        r = results.get(j["interface"])
        out.append(
            {
                **j,
                "hardware_words": hardware_words(j),
                "status": r["status"] if r else "skip",
                "message": r.get("message", "") if r else "not checked yet",
                "notes": [
                    {"id": d.id, "uri": f"dec://{d.id}", "title": d.title}
                    for d in product.decisions.values()
                    if j["interface"] in {str(x) for x in d.links}
                ],
            }
        )
    return out


def _by_module(
    checks: dict[str, Any], other_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """The check matrix grouped by module (P12), when the product has two units or more.

    Returns the module overview (title and counts per module, build order, the whole product
    last), the findings in groups (one untitled group when there is a single module), and the
    rules × parts matrix with its parts ordered by module plus ``groups`` for a header row.
    """
    matrix = checks.get("matrix", {})
    rules = dict(matrix.get("rules", {"parts": [], "rules": {}, "cells": {}}))
    groups = list(matrix.get("modules", []))
    if sum(1 for g in groups if g["id"] is not None) < 2:  # one unit: the matrix as before
        return [], [{"title": "", "rows": other_rows}], {**rules, "groups": []}
    order = {g["id"]: i for i, g in enumerate(groups)}
    other_groups = [
        {"title": g["title"], "rows": [r for r in other_rows if r.get("module") == g["id"]]}
        for g in groups
    ]
    part_module: dict[str, Any] = {}
    for r in checks.get("results", []):
        if r.get("kind") == "rule" and str(r.get("subject", "")).startswith("part://"):
            part_module[str(r["subject"]).removeprefix("part://")] = r.get("module")
    parts = sorted(rules.get("parts", []), key=lambda p: (order.get(part_module.get(p), 99), p))
    header: list[dict[str, Any]] = []
    for p in parts:
        title = next((g["title"] for g in groups if g["id"] == part_module.get(p)), "")
        if header and header[-1]["title"] == title:
            header[-1]["span"] += 1
        else:
            header.append({"title": title, "span": 1})
    return (
        groups,
        [g for g in other_groups if g["rows"]],
        {**rules, "parts": parts, "groups": header},
    )


def waiting_on_you(build_dir: Path) -> list[dict[str, Any]]:
    """The open choices (F12) for the overview's "waiting on you" list (B-0093, S-133).

    From ``choices.json``, which the ``checks`` rule writes (the report reads ``rule:checks``):
    each with what the check found, its options, the gate it holds and the command that
    records the pick, in the words ``n2f status`` uses.
    """
    from napkin2factory.core.checks.choices import HOLDS_WORDS, decide_command, open_choices

    out: list[dict[str, Any]] = []
    for c in open_choices(build_dir):
        found = str(c.get("message", "")).split(" Two ways to fix it:")[0]
        out.append(
            {
                "id": c["id"],
                "title": c.get("title") or c["id"],
                "found": found,
                "options": c.get("options", []),
                "holds": HOLDS_WORDS.get(c.get("blocks", ""), ""),
                "command": decide_command(c).strip("`"),
            }
        )
    return out


__all__ = [
    "_between_units",
    "_bom_by_uri",
    "_build_steps",
    "_by_module",
    "_doc_html",
    "_flatten_bom",
    "_read_json",
    "_spec_summary",
    "_viewer_options",
    "waiting_on_you",
]
