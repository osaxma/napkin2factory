"""``n2f concept board``: every direction side by side, read-only (NAPKIN_STAGE N10).

One self-contained page, ``build/concepts/board.html``, on the report's machinery (D13):
three.js and the viewer as one inline module script, each card's massing GLB embedded as
base64 and booted in its own viewer with the style's materials and the studio rig, the
styled screenshots and the cards' reference images as ``data:`` URIs, zero external
references, so it opens from ``file://``. Cards appear in id order; a red card keeps its
place, with a red header and its reasons (red is information, N5). Every number on the page
comes from the card's screening with its ``computed`` or ``estimate`` label taken from the
data, never inferred by the template.

The page never exceeds :data:`MAX_REPORT_BYTES`: when it would, the reference images are
dropped first, then the front screenshots, then the 3D viewers, then the iso screenshots,
and the page says what was left out. Choosing happens in conversation or with ``n2f concept
promote``: the board has no control that writes.

The board is built by this verb only, never by the build graph (N1): nothing here imports
``core.graph``.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import json
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.concepts.massing import concept_build_dir
from napkin2factory.core import concepts as cm
from napkin2factory.core.model.concepts import ConceptCard, LabelledValue, RuleRow

#: The page budget: the report's (``report.builder.MAX_REPORT_BYTES``, D13).
MAX_REPORT_BYTES = 20 * 1024 * 1024
#: Where the board is written, relative to the product folder.
BOARD_PATH = Path("build") / "concepts" / "board.html"
#: What is dropped, in order, when the page would exceed the budget.
DROP_ORDER: tuple[str, ...] = ("refs", "front", "viewers", "hero")
DROP_WORDS: dict[str, str] = {
    "refs": "reference images",
    "front": "front screenshots",
    "viewers": "3D viewers",
    "hero": "iso screenshots",
}
#: Key dimensions, in display order (the computed block).
KEY_DIMS: tuple[str, ...] = (
    "width",
    "depth",
    "height",
    "footprint_with_door_swing",
    "mass",
    "total_mass",
)
#: The estimate strip, in display order.
STRIP: tuple[str, ...] = (
    "cost_low",
    "cost_high",
    "heat_up_time",
    "required_power",
    "current",
    "circuit_class",
    "lift_class",
)
#: Owner words for value names; anything else shows its name with spaces.
NAMES: dict[str, str] = {
    "width": "width",
    "depth": "depth",
    "height": "height",
    "footprint_with_door_swing": "width with the door open",
    "mass": "mass of the shapes",
    "total_mass": "total mass",
    "volume": "volume of the shapes",
    "cost_low": "cost, low",
    "cost_high": "cost, high",
    "heat_up_time": "heat-up",
    "required_power": "power needed",
    "current": "current",
    "circuit_class": "supply",
    "power": "power",
    "lift_class": "lifting",
    "heat_loss": "heat loss",
    "skin_temperature": "outside skin",
    "stored_heat": "stored heat",
    "insulation_mass": "insulation mass",
}
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
HEADLINE = "Compare directions, then choose in conversation or with"
CHOOSE_COMMAND = "n2f concept promote C-00x"


@dataclass
class BoardResult:
    """What ``n2f concept board`` wrote."""

    path: Path
    bytes: int
    cards: list[dict[str, Any]]
    dropped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def dropped_notes(self) -> list[str]:
        """One line per thing left out to stay within the page budget."""
        if not self.dropped:
            return []
        what = ", ".join(DROP_WORDS[d] for d in self.dropped)
        return [f"left out to stay under {_mb()} MB: {what}"]

    def line(self) -> str:
        """The owner's one line about the board."""
        n = len(self.cards)
        red = sum(1 for c in self.cards if c["verdict"] == "red")
        unbuilt = sum(1 for c in self.cards if not c["built"])
        extra = []
        if red:
            extra.append(f"{red} with problems")
        if unbuilt:
            extra.append(f"{unbuilt} not built yet")
        tail = f" ({', '.join(extra)})" if extra else ""
        noun = "direction" if n == 1 else "directions"
        return f"board: {BOARD_PATH.as_posix()} — {n} {noun} side by side{tail}"

    def to_dict(self, root: Path) -> dict[str, Any]:
        """JSON form: the gathered data without the embedded bytes."""
        return {
            "board": _rel(root, self.path),
            "bytes": self.bytes,
            "max_bytes": MAX_REPORT_BYTES,
            "dropped": self.dropped,
            "notes": self.notes,
            "cards": self.cards,
        }


def _mb() -> str:
    """The page budget in MB, for the owner's words."""
    return f"{MAX_REPORT_BYTES / (1024 * 1024):.3g}"


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if path.suffix.lower() == ".svg":
        mime = "image/svg+xml"
    return f"data:{mime};base64,{_b64(path)}"


#: A cost band wider than this (high ÷ low) gets one sentence under it (review gate B, C10).
WIDE_BAND = 1.5
WIDE_BAND_WORDS = "a wide band: only the parts screening can price are counted"


def _value(name: str, lv: LabelledValue) -> dict[str, Any]:
    """One row of the board's numbers.

    The owner's ``source`` is printed under estimates and the door row; the engineer's
    ``ref`` travels in ``--json`` only (the template never prints it).
    """
    return {
        "key": name,
        "name": NAMES.get(name, name.replace("_", " ")),
        "value": lv.value,
        "label": lv.label,
        "source": lv.source,
        "ref": lv.ref,
        "show_src": lv.label == "estimate" or name == "footprint_with_door_swing",
        "after": None,
    }


def _amount(text: str) -> float | None:
    try:
        return float(text.split(" ")[0])
    except ValueError:
        return None


def _cost_rows(strip: list[dict[str, Any]]) -> None:
    """The two cost rows share one source line; a wide band says why (C10)."""
    rows = {v["key"]: v for v in strip}
    low, high = rows.get("cost_low"), rows.get("cost_high")
    if low is None or high is None:
        return
    if low["source"] == high["source"]:
        low["show_src"] = False
    lo, hi = _amount(low["value"]), _amount(high["value"])
    if lo is not None and hi is not None and lo > 0 and hi / lo > WIDE_BAND:
        high["after"] = WIDE_BAND_WORDS


def _rule_row(row: RuleRow) -> dict[str, Any]:
    return {"id": row.id, "message": row.message, "relies_on": list(row.relies_on)}


def _status_word(card: ConceptCard) -> str:
    if card.status == "exploring" and card.screening is None:
        return "not built yet"
    return card.status


def _decision_line(card: ConceptCard) -> str | None:
    """``set aside when C-003 was chosen (DEC-018) — 2026-10-31``: the date, never the time."""
    d = card.decision
    if d is None or card.status == "exploring":
        return None
    at = d.at.date().isoformat() if isinstance(d.at, dt.datetime) else str(d.at or "")
    day = at.replace("T", " ").split(" ")[0]
    when = f" — {day}" if day else ""
    if card.status == "promoted":
        return f"the chosen direction ({d.dec}){when}" if d.dec else f"the chosen direction{when}"
    return f"{cm.set_aside_words(d.reason)}{when}"


def gather_card(root: Path, card: ConceptCard, style: Any) -> dict[str, Any]:
    """One card's board data: words, labelled values and the files to embed (as paths)."""
    from napkin2factory.concepts.screenshot import card_materials
    from napkin2factory.core.style import merge_card_style

    out_dir = concept_build_dir(root, card.id)
    sc = card.screening
    values: dict[str, LabelledValue] = {}
    given_values: dict[str, LabelledValue] = {}
    if sc is not None:
        values = {**sc.computed, **sc.estimates}
        given_values = dict(sc.given)
    # the card's own inputs (power, circuit) are shown as given, apart from what was
    # measured or estimated (review gate A, C1)
    given = [_value(k, lv) for k, lv in given_values.items()]
    dims = [_value(k, values[k]) for k in KEY_DIMS if k in values]
    strip = [_value(k, values[k]) for k in STRIP if k in values]
    _cost_rows(strip)
    shown = set(KEY_DIMS) | set(STRIP)
    more = [_value(k, lv) for k, lv in values.items() if k not in shown]
    rules = sc.rules if sc is not None else []
    files: dict[str, str | None] = {}
    for key, rel in (
        ("glb", "massing.glb"),
        ("hero", "renders/styled-iso.png"),
        ("front", "renders/styled-front.png"),
    ):
        p = out_dir / rel
        files[key] = str(p) if sc is not None and p.is_file() else None
    refs = []
    for ref in card.refs:
        p = (cm.concepts_dir(root) / ref).resolve()
        is_image = p.suffix.lower() in IMAGE_TYPES
        refs.append(
            {
                "name": ref,
                "path": str(p) if p.is_file() and is_image else None,
                "missing": not p.is_file(),
            }
        )
    card_style, _ = merge_card_style(style, card.style)
    options = {
        "background": card_style.background,
        "materials": card_materials(card, card_style),
        "lighting": "studio",
        "camera": "iso",
        "transparent": False,
    }
    return {
        "id": card.id,
        "title": card.title,
        "status": card.status,
        "status_word": _status_word(card),
        "built": sc is not None,
        "verdict": card.verdict,
        "based_on": card.based_on,
        "given": given,
        "dims": dims,
        "strip": strip,
        "more": more,
        "problems": [r.message for r in rules if r.status == "fail"],
        "worth_a_look": [r.message for r in rules if r.status == "warn"],
        # the same rows with the labels of the numbers each relied on (gate A, C2)
        "problem_rows": [_rule_row(r) for r in rules if r.status == "fail"],
        "look_rows": [_rule_row(r) for r in rules if r.status == "warn"],
        "screening_notes": list(sc.notes) if sc is not None else [],
        "notes": card.notes,
        "decision": _decision_line(card),
        "refs": refs,
        "files": files,
        "viewer_options": options,
        "build_hint": f"n2f concept build {card.id}",
    }


def gather(root: Path) -> dict[str, Any]:
    """Everything the board shows: product name, cards in id order, notes."""
    import yaml

    from napkin2factory.concepts.build import product_style

    root = Path(root)
    name = root.name
    manifest = root / "n2f.yaml"
    if manifest.is_file():
        try:
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            name = str((data.get("product") or {}).get("name") or name)
        except yaml.YAMLError:
            pass
    style, notes = product_style(root)
    from napkin2factory.core.errors import Problems

    problems = Problems()
    cards = cm.load_concepts(root, problems)
    for p in problems.items:
        notes.append(f"{p.subject}: {p.message} (left off the board; `n2f concept lint`)")
    return {
        "product": name,
        "cards": [gather_card(root, c, style) for c in cards.values()],
        "notes": notes,
    }


def _embed(cards: list[dict[str, Any]], dropped: set[str]) -> list[dict[str, Any]]:
    """Cards with their files read as base64 / data URIs, minus what ``dropped`` names."""
    out = []
    for c in cards:
        files = c["files"]
        e = dict(c)
        e["glb_b64"] = _b64(Path(files["glb"])) if files["glb"] and "viewers" not in dropped else ""
        e["hero_src"] = (
            _data_uri(Path(files["hero"])) if files["hero"] and "hero" not in dropped else ""
        )
        e["front_src"] = (
            _data_uri(Path(files["front"])) if files["front"] and "front" not in dropped else ""
        )
        e["ref_items"] = [
            {
                "name": r["name"],
                "src": _data_uri(Path(r["path"])) if r["path"] and "refs" not in dropped else "",
                "missing": r["missing"],
            }
            for r in c["refs"]
        ]
        e["options_json"] = json.dumps(c["viewer_options"], sort_keys=True)
        out.append(e)
    return out


def render_board(data: dict[str, Any], dropped: set[str] | None = None) -> str:
    """The page HTML (the viewer bundle inlined when any card has a 3D model)."""
    import jinja2

    from napkin2factory import __version__
    from napkin2factory.report.brand import favicon_link, footer_mark, footer_wordmark
    from napkin2factory.report.inline import bundle_viewer, inline_module_script

    dropped = dropped or set()
    cards = _embed(data["cards"], dropped)
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(Path(__file__).parents[1] / "report" / "templates")),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )
    env.globals["n2f_favicon"] = favicon_link()
    env.globals["n2f_mark"] = footer_mark()
    env.globals["n2f_wordmark"] = footer_wordmark()
    any_glb = any(c["glb_b64"] for c in cards)
    dropped_words = [DROP_WORDS[d] for d in DROP_ORDER if d in dropped]
    return env.get_template("board.html.j2").render(
        product=data["product"],
        cards=cards,
        notes=data["notes"],
        dropped=dropped_words,
        max_mb=_mb(),
        headline=HEADLINE,
        choose=CHOOSE_COMMAND,
        version=__version__,
        generated=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        viewer_script=inline_module_script(bundle_viewer()) if any_glb else "",
        esc=html.escape,
    )


def write_board(root: Path) -> BoardResult:
    """Gather, render within the budget and write ``build/concepts/board.html``."""
    root = Path(root)
    data = gather(root)
    if not data["cards"]:
        from napkin2factory.core.errors import N2FError

        raise N2FError('there are no concepts yet — `n2f concept new "<title>"` starts one')
    dropped: set[str] = set()
    page = render_board(data, dropped)
    for what in DROP_ORDER:
        if len(page.encode("utf-8")) <= MAX_REPORT_BYTES:
            break
        dropped.add(what)
        page = render_board(data, dropped)
    size = len(page.encode("utf-8"))
    if size > MAX_REPORT_BYTES:
        from napkin2factory.core.errors import N2FError

        raise N2FError(
            f"the board is {size / 1e6:.1f} MB even without pictures; split the concepts "
            "into fewer cards"
        )
    path = root / BOARD_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    cards = [{k: v for k, v in c.items() if k not in ("viewer_options",)} for c in data["cards"]]
    for c in cards:
        c["files"] = {k: (_rel(root, Path(v)) if v else None) for k, v in c["files"].items()}
        c["refs"] = [
            {**r, "path": _rel(root, Path(r["path"])) if r["path"] else None} for r in c["refs"]
        ]
    order = [d for d in DROP_ORDER if d in dropped]
    return BoardResult(path, size, cards, order, list(data["notes"]))


__all__ = [
    "BOARD_PATH",
    "DROP_ORDER",
    "MAX_REPORT_BYTES",
    "BoardResult",
    "gather",
    "gather_card",
    "render_board",
    "write_board",
]
