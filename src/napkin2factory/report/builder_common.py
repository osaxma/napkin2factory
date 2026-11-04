"""Report vocabulary, section registry, anchors and read sets; split from builder.py (S-184)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from markupsafe import Markup

from napkin2factory.core.ceremony import CEREMONY_KEY
from napkin2factory.core.loader import Product
from napkin2factory.core.style import STYLE_LOOK_KEY
from napkin2factory.core.uris import display_uri

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext

TEMPLATES = Path(__file__).parent / "templates"
MAX_REPORT_BYTES = 20 * 1024 * 1024


def __getattr__(name: str) -> Any:
    """``SECTIONS`` is the report-section registry's view (F5), read on each access."""
    if name == "SECTIONS":
        return sections()
    raise AttributeError(name)


def sections(product: Product | None = None) -> tuple[tuple[str, str, str], ...]:
    """Page sections in reading order: (anchor, nav label, group); the nav groups them.

    The registered report sections (F5); with ``product``, those whose ``show`` says no are
    left out.
    """
    from napkin2factory.core.registry import registry

    return tuple(
        (sec.id, sec.label, sec.group)
        for sec in registry().report_sections()
        if product is None or sec.show is None or sec.show(product)
    )


VOCAB: dict[str, dict[str, str]] = {
    "owner": {
        "pass": "OK",
        "fail": "needs attention",
        "warn": "worth a look",
        "skip": "not checked",
        "needs-human": "needs your sign-off",
        "signed": "signed off",
        "choice": "a choice waiting on you",
        "later": "left for later",
        "example": "example sign-offs — not reviews",
        "example_one": "example sign-off — not a review",
        "changes": "Change requests",
    },
    "engineer": {
        "pass": "pass",
        "fail": "fail",
        "warn": "warn",
        "skip": "skip",
        "needs-human": "needs-human",
        "signed": "signed",
        "choice": "choice",
        "later": "later",
        "example": "example sign-offs — not reviews",
        "example_one": "example sign-off — not a review",
        "changes": "Change requests (ECRs)",
    },
}


def anchor_for(uri: str, anchors: dict[str, str]) -> str | None:
    """The in-page anchor a model URI points at, ignoring any ``#selector`` suffix."""
    base = uri.split("#", 1)[0]
    if base in anchors:
        return anchors[base]
    scheme = base.split("://", 1)[0] if "://" in base else ""
    return {
        "bom": "parts",
        "rule": "rules",
        "manifest": "overview",
        "param": "parameters",
        "req": "requirements",
        "dec": "decisions",
        "ecr": "changes",
        "doc": "manuals",
        "iface": "interfaces",
        "asm": "model",
    }.get(scheme)


def ref_html(uri: Any, anchors: dict[str, str], persona: str = "engineer") -> Markup:
    """Render a URI as a hyperlink to its row when the page has one, else as plain text.

    The link target always uses the full URI; the visible text follows the persona's
    display rule (:func:`~napkin2factory.core.uris.display_uri`).
    """
    text = str(uri)
    anchor = anchor_for(text, anchors)
    shown = display_uri(text, persona)
    if anchor is None:
        return Markup('<span class="mono">{}</span>').format(shown)
    return Markup('<a class="ref mono" href="#{}">{}</a>').format(anchor, shown)


def scope_reads(product: Product) -> list[str]:
    """The scope the overview line and the gate notes say (F11), as recorded reads.

    The whole block is always read, declared or not, so a product's first ``scope:`` reruns
    the report by itself (S-133, closing B-0081; every product's report key moved once with
    it, at the v0.5 upgrade).  Each declared domain is read too, so an edit to one entry
    names the report in ``n2f impact``.
    """
    from napkin2factory.core.graph.values import SCOPE_KEY

    return [SCOPE_KEY, *(f"{SCOPE_KEY}#{d}" for d in product.manifest.scope)]


def report_reads(ctx: RunContext) -> list[str]:
    """The report depends on every artifact: checks, parts, assemblies, drawings, docs, BOM."""
    product = ctx.product
    reads = ["rule:checks", "bom://rollups"]
    reads += [p.uri for p in product.parts_with_geometry()]
    reads += [f"drawing://{p.id}" for p in product.parts_with_geometry()]
    reads += [a.uri for a in product.assemblies.values()]
    reads += [f"doc://{d}" for d in product.docs]
    reads += [f"req://{r}#title" for r in product.requirements]
    reads += [f"req://{r}#statement" for r in product.requirements]
    reads += [f"dec://{d}#title" for d in product.decisions]
    reads += [f"ecr://{e}#status" for e in product.ecrs]
    reads += [f"param://{p}" for p in product.parameters]
    reads += [f"signoff:{s}" for s in product.signoffs]
    reads += [f"{p.uri}#role" for p in product.parts_with_geometry()]
    reads.append(STYLE_LOOK_KEY)  # the palette the viewer paints parts with
    # P8: the build plan section and each unit's assembly sheet
    reads += ["bom://build-plan#order", "bom://build-plan#units"]
    # P13: the joints between units, and the decisions that note them (a merge candidate)
    reads.append("bom://build-plan#between_units")
    reads += [f"dec://{d}#links" for d in product.decisions]
    from napkin2factory.core.build_units import BuildUnits

    reads += [f"rule:asmsheet:{a}" for a in BuildUnits(product).order()]
    reads += [
        "set://parts",
        "set://asms",
        "set://docs",
        "set://reqs",
        "set://decs",
        "set://ecrs",
        "set://signoffs",
        "set://params",
        "set://ifaces",
        "manifest://product#name",
        CEREMONY_KEY,  # W6: a lite report leaves out its empty sections
    ]
    reads += scope_reads(product)
    from napkin2factory.core.registry import registry

    for sec in registry().report_sections():  # what a domain's section shows (F5)
        if sec.reads is not None:
            reads += sec.reads(product)
    return reads


__all__ = [
    "MAX_REPORT_BYTES",
    "TEMPLATES",
    "VOCAB",
    "anchor_for",
    "ref_html",
    "report_reads",
    "scope_reads",
    "sections",
]
