"""``n2f concept build``: compose → write artifacts → screen → update the card (N1, N5).

In-process orchestration with no build graph: concepts are outside it, so nothing here is
hashed, recorded in the manifest or read by a build rule. One warm process screens every
card in seconds, and one headless browser page takes every card's styled screenshots (N6).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from napkin2factory.concepts.massing import MassingResult, compose, concept_build_dir
from napkin2factory.concepts.screening import (
    screen,
    write_screening_json,
    write_screening_to_card,
)
from napkin2factory.concepts.screenshot import (
    ScreenshotResult,
    ScreenshotSession,
    styled_screenshots,
)
from napkin2factory.core import concepts as cm
from napkin2factory.core.errors import N2FError, Problems
from napkin2factory.core.model.concepts import ConceptCard, Screening
from napkin2factory.core.model.style import StyleFile


@dataclass
class ConceptBuild:
    """One built and screened card."""

    card: ConceptCard
    massing: MassingResult
    screening: Screening
    out_dir: Path
    seconds: float
    screenshots: ScreenshotResult | None = None

    @property
    def picture(self) -> Path | None:
        """The image to show for this card: the styled iso, else the z-buffer iso."""
        if self.screenshots is not None and "iso" in self.screenshots.paths:
            return self.screenshots.paths["iso"]
        return self.massing.paths.get("render_iso")

    def rel(self, root: Path, path: Path) -> str:
        """``path`` relative to the product folder, with forward slashes."""
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return str(path)

    def to_dict(self, root: Path) -> dict[str, Any]:
        """JSON form for ``n2f concept build --json``."""
        return {
            "id": self.card.id,
            "title": self.card.title,
            "verdict": self.screening.verdict,
            "summary": summary_line(self.card, self.screening),
            "dir": self.rel(root, self.out_dir),
            "renders": {
                k.removeprefix("render_"): self.rel(root, v)
                for k, v in self.massing.paths.items()
                if k.startswith("render_")
            },
            "screenshots": (
                self.screenshots.to_dict(root) if self.screenshots is not None else None
            ),
            "seconds": round(self.seconds, 3),
            "screening": self.screening.model_dump(mode="json"),
        }


def product_style(root: Path) -> tuple[StyleFile, list[str]]:
    """The product's resolved style; ``industrial`` defaults plus a note if the file is bad.

    A broken ``style.yaml`` never stops a concept picture (ideas are never blocked).
    """
    from napkin2factory.core.style import load_style

    try:
        return load_style(root), []
    except N2FError as exc:
        return StyleFile().resolved(), [f"{exc}; pictures use the industrial look"]


def build_concept(
    root: Path,
    card: ConceptCard,
    render: bool = True,
    session: ScreenshotSession | None = None,
    style: StyleFile | None = None,
) -> ConceptBuild:
    """Compose, screen, picture and record one card; the card file gains its ``screening:``.

    Args:
        root: the product folder.
        card: the card to build.
        render: write pictures (z-buffer renders and styled screenshots).
        session: a browser session to reuse across cards (one is opened if needed).
        style: the product's resolved style (read from ``style.yaml`` when omitted).
    """
    from napkin2factory.core.style import merge_card_style

    t0 = time.perf_counter()
    massing = compose(card, root, render=render)
    screening = screen(card, massing, root)
    out_dir = concept_build_dir(root, card.id)
    shots: ScreenshotResult | None = None
    if render:
        notes: list[str] = []
        if style is None:
            style, notes = product_style(root)
        card_style, card_notes = merge_card_style(style, card.style)
        shots = styled_screenshots(
            card, massing.paths["glb"], card_style, out_dir / "renders", session
        )
        for note in [*notes, *card_notes, *shots.notes]:
            if note not in screening.notes:
                screening.notes.append(note)
    write_screening_json(out_dir, card, screening)
    write_screening_to_card(root, card.id, screening)
    updated = cm.load_card(root, card.id)
    return ConceptBuild(
        updated, massing, screening, out_dir, time.perf_counter() - t0, screenshots=shots
    )


def build_concepts(
    root: Path, cards: list[ConceptCard], render: bool = True
) -> tuple[list[ConceptBuild], list[dict[str, str]]]:
    """Build every card through one browser page; returns (built, errors by card id)."""
    built: list[ConceptBuild] = []
    errors: list[dict[str, str]] = []
    style, notes = product_style(root)
    with ScreenshotSession() as session:
        for note in notes:
            session.warn(note)
        for card in cards:
            try:
                built.append(build_concept(root, card, render, session, style))
            except N2FError as exc:
                errors.append({"id": card.id, "error": str(exc)})
    return built, errors


def select_cards(
    root: Path, concept_id: str | None, all_: bool, problems: Problems
) -> list[ConceptCard]:
    """The cards to build: one by id, or every card not rejected (``--all``)."""
    if concept_id is not None and all_:
        raise N2FError("name one card (e.g. C-002) or pass --all, not both")
    if concept_id is None and not all_:
        raise N2FError("name a card to build (e.g. `n2f concept build C-002`) or pass --all")
    if concept_id is not None:
        return [cm.load_card(root, concept_id)]
    cards = cm.load_concepts(root, problems)
    if not cards and not problems.items:
        raise N2FError('there are no concepts yet — `n2f concept new "<title>"` starts one')
    return [c for c in cards.values() if c.status != "rejected"]


def _value(screening: Screening, section: str, name: str) -> str | None:
    values = {
        "given": screening.given,
        "computed": screening.computed,
        "estimates": screening.estimates,
    }[section]
    lv = values.get(name)
    return lv.value if lv is not None else None


def _supply_phrase(screening: Screening) -> str | None:
    """``2.5 kW (on the card) on the 240V-13A circuit — fits with 1.2 headroom (estimate)``.

    The card's own power and circuit are given; only the fit is an estimate (gate A, C1).
    """
    from napkin2factory.rulepacks.concept_checks import circuit_headroom

    given_power = _value(screening, "given", "power")
    power = (
        f"{given_power} (on the card)"
        if given_power
        else (
            f"{_value(screening, 'estimates', 'required_power')} (estimate)"
            if _value(screening, "estimates", "required_power")
            else None
        )
    )
    if power is None:
        return None
    on_card = _value(screening, "given", "circuit_class")
    if on_card:
        row = screening.rule("circuit-available")
        h = f"{circuit_headroom():g}"
        if row is not None and row.status == "pass":
            fit = f"fits with {h} headroom (estimate)"
        elif row is not None and row.status == "fail":
            fit = f"does not fit with {h} headroom (estimate)"
        else:
            fit = "fit not checked"
        return f"{power} on {on_card} — {fit}"
    table = _value(screening, "estimates", "circuit_class")
    if table:
        return f"{power} on a {table} (estimate)"
    return f"{power}, supply not checked"


def summary_line(card: ConceptCard, screening: Screening) -> str:
    """One owner line: size (computed), mass, power on its circuit, heat-up, cost.

    Every number says which label it carries.
    """
    from napkin2factory.core.units import is_quantity

    parts: list[str] = []
    dims = [_value(screening, "computed", k) for k in ("width", "depth", "height")]
    if all(dims):
        nums = [str(d).removesuffix(" mm") for d in dims]
        parts.append(f"{' × '.join(nums)} mm (computed)")
    mass = _value(screening, "estimates", "total_mass")
    if mass:
        parts.append(f"about {mass} (estimate)")
    elif _value(screening, "computed", "mass"):
        parts.append(f"about {_value(screening, 'computed', 'mass')} (computed)")
    supply = _supply_phrase(screening)
    if supply:
        parts.append(supply)
    heat = _value(screening, "estimates", "heat_up_time")
    if heat:
        parts.append(f"{heat} to temperature (estimate)")
    elif _value(screening, "estimates", "required_power") and is_quantity(
        card.envelope.get("heat_up_time")
    ):
        parts.append(
            f"{_value(screening, 'estimates', 'required_power')} for the planned heat-up (estimate)"
        )
    lo, hi = _value(screening, "estimates", "cost_low"), _value(screening, "estimates", "cost_high")
    if lo and hi and lo == hi:
        parts.append(f"{hi} (estimate, one source)")  # a single-source band (C9, B-0022)
    elif lo and hi:
        parts.append(f"{lo.removesuffix(' USD')}–{hi} (estimate)")
    return ", ".join(parts) if parts else "nothing measured yet"


__all__ = [
    "ConceptBuild",
    "build_concept",
    "build_concepts",
    "product_style",
    "select_cards",
    "summary_line",
]
