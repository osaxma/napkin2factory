"""The ceremony a product runs at, derived from its model (W6, S-205).

Two levels: ``lite`` (an everyday product: one field of work, no hazardous energy) and
``standard`` (everything else).  The level is *derived*, never chosen: it rises when

* a domain with content reports a hazard through :attr:`Domain.hazards` (the wiring does for
  a supply above extra-low voltage),
* more than one domain has content (:attr:`Domain.has_content`),
* a requirement carries a ``hazard:<kind>`` tag whose kind ``core/data/hazards.yaml`` classes
  as raising, or
* ``n2f.yaml`` says ``ceremony: standard`` (it may raise the level, never lower it).

``lite`` relaxes paperwork only: a custom part may leave out ``tolerance_class`` when its
process has a default, one ``build-and-care`` page can stand for the manual set, and the
report leaves out sections that are empty.  Provenance, port alignment and safety sign-offs
are the same at both levels.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from napkin2factory.core.loader import Product
    from napkin2factory.core.model import Part, Requirement

Level = Literal["lite", "standard"]
HAZARD_TAG = "hazard:"
#: ``build/.n2f/ceremony.json``: the level the last ``n2f check`` saw, to say when it rose.
RECORD_REL = Path(".n2f") / "ceremony.json"
#: The read key of a rule whose output depends on the level (``core/graph/values.py``).
CEREMONY_KEY = "manifest://ceremony"


@dataclass(frozen=True)
class Hazard:
    """One row of ``core/data/hazards.yaml``: a kind of hazard and whether it raises the level."""

    id: str
    title: str
    raises: bool
    source: str
    verify: bool = True
    #: The domain whose model answers this hazard (``mains`` -> ``electrical``), or ``None``.
    domain: str | None = None


@dataclass(frozen=True)
class Ceremony:
    """The derived level and, for ``standard``, the plain-words reasons."""

    level: Level
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """``{"ceremony": …, "ceremony_reasons": […]}`` for ``--json``."""
        return {"ceremony": self.level, "ceremony_reasons": list(self.reasons)}


@lru_cache(maxsize=1)
def hazard_table() -> dict[str, Hazard]:
    """The hazard kinds by id (``core/data/hazards.yaml``)."""
    from napkin2factory.core.registry import DATA
    from napkin2factory.core.yamlio import read_yaml

    rows = read_yaml(DATA / "hazards.yaml")
    return {
        r["id"]: Hazard(
            r["id"],
            r["title"],
            bool(r["raises"]),
            r["source"],
            bool(r.get("verify")),
            r.get("domain"),
        )
        for r in rows
    }


def hazard_kinds(req: Requirement) -> list[str]:
    """The kinds a requirement names in its ``hazard:<kind>`` tags, in tag order."""
    return [t[len(HAZARD_TAG) :] for t in req.tags if t.startswith(HAZARD_TAG)]


def hazard_problems(req: Requirement) -> list[tuple[str, str]]:
    """Lint findings for one requirement's hazard tags: ``(message, fix)`` pairs (W6).

    A ``safety: true`` requirement must name its hazard, so the ceremony follows from the
    model; an unknown kind is refused the same way, listing the known ones.
    """
    known = ", ".join(sorted(hazard_table()))
    kinds = hazard_kinds(req)
    out = []
    if req.safety and not kinds:
        out.append(
            (
                "safety requirement without a hazard tag",
                f"add a tag `hazard:<kind>` naming the hazard; kinds: {known}",
            )
        )
    for kind in kinds:
        if kind not in hazard_table():
            out.append((f"unknown hazard kind {kind!r}", f"use one of the known kinds: {known}"))
    return out


def unmodelled_hazard_note(product: Product) -> str | None:
    """One plain sentence when a requirement names a hazard whose domain has no model (S-241).

    A ``hazard:mains`` requirement with nothing under ``model/electrical/`` and no ``scope``
    line for the wiring raises the ceremony but gets no wiring check, so the product passes
    in silence.  ``None`` when every named hazard is modelled, scoped or has no domain.
    """
    from napkin2factory.core.registry import registry

    has = {d.name: d.has_content for d in registry().domains}
    lacking: dict[str, list[str]] = {}  # domain -> titles of the requirements naming its hazard
    for req in product.requirements.values():
        for kind in hazard_kinds(req):
            haz = hazard_table().get(kind)
            if haz is None or haz.domain is None:
                continue
            entry = product.manifest.scope.get(haz.domain)
            if entry is not None and entry.state != "in":
                continue  # left for later or done elsewhere: the scope line says so (F11)
            content = has.get(haz.domain)
            if content is not None and not content(product):
                lacking.setdefault(kind, []).append(req.title)
    if not lacking:
        return None
    parts = []
    for kind, titles in lacking.items():
        shown = ", ".join(f"“{t}”" for t in titles[:2])
        more = f" and {len(titles) - 2} more" if len(titles) > 2 else ""
        parts.append(f"{hazard_table()[kind].title.lower()} is named by {shown}{more}")
    return (
        "; ".join(parts).capitalize()
        + ", but the product models no supply or wiring. Add the wiring under model/electrical/, "
        "or record in n2f.yaml that it is left for later (scope: {electrical: {state: later}})."
    )


def derive_ceremony(product: Product) -> Ceremony:
    """The ceremony the model asks for; ``standard`` carries every reason, in owner words."""
    from napkin2factory.core.registry import registry

    reasons: list[str] = []
    domains = [
        d for d in registry().domains if d.has_content is not None and d.has_content(product)
    ]
    for d in domains:
        if d.hazards is not None:
            reasons += d.hazards(product)
    if len(domains) > 1:
        names = " and ".join(d.name for d in domains)
        reasons.append(f"the product has work in more than one field ({names})")
    named: dict[str, list[str]] = {}  # raising kind -> titles of the requirements naming it
    for req in product.requirements.values():
        for kind in hazard_kinds(req):
            if kind in hazard_table() and hazard_table()[kind].raises:
                named.setdefault(kind, []).append(req.title)
    for kind in hazard_table():  # table order: the reasons read the same every time
        titles = named.get(kind)
        if titles:
            shown = ", ".join(f"“{t}”" for t in titles[:2])
            more = f" and {len(titles) - 2} more" if len(titles) > 2 else ""
            reasons.append(f"{hazard_table()[kind].title.lower()} is named by {shown}{more}")
    if product.manifest.ceremony == "standard":
        reasons.append("n2f.yaml asks for the standard ceremony")
    unique = tuple(dict.fromkeys(reasons))
    return Ceremony("standard" if unique else "lite", unique)


def default_tolerance(product: Product, part: Part, ceremony: Ceremony) -> str | None:
    """The class a ``lite`` product gives a custom part that names none, from its process.

    ``None`` when the part names its own, is bought or supplied, the ceremony is
    ``standard``, or the part's process has no default.
    """
    from napkin2factory.core.registry import registry

    if part.kind != "custom" or part.tolerance_class is not None or ceremony.level != "lite":
        return None
    process = registry().processes().get(part.process)
    return process.default_tolerance_class if process is not None else None


def tolerance_label(part: Part, default: str | None) -> str | None:
    """The class as drawings and the parts list say it; a default is labelled as one."""
    if part.tolerance_class is not None:
        return str(part.tolerance_class)
    return f"{default} (default)" if default else None


def manuals_problem(product: Product, ceremony: Ceremony) -> tuple[str, str] | None:
    """What is missing from the manual set, as ``(message, fix)``, or ``None`` (W6).

    ``standard``: a page with id ``safety`` that carries ``safety: true``.  ``lite``: any page
    that carries it, so one ``build-and-care`` page stands for the whole set.
    """
    flagged = [d for d in product.docs.values() if d.meta.safety]
    if ceremony.level == "lite":
        if flagged:
            return None
        return (
            "no manual page carries the safety notes",
            "add model/docs/build-and-care.md with `safety: true` in its front matter",
        )
    if any(d.meta.id == "safety" for d in flagged):
        return None
    return (
        "no safety manual page",
        "add model/docs/safety.md with `id: safety` and `safety: true` in its front matter",
    )


def what_standard_requires(product: Product) -> list[str]:
    """What a ``standard`` product needs that a ``lite`` one did not, in owner words."""
    out = []
    lacking = sorted(
        p.id for p in product.parts.values() if p.kind == "custom" and p.tolerance_class is None
    )
    if lacking:
        out.append("a tolerance class written on each custom part (" + ", ".join(lacking) + ")")
    out.append("a safety manual page, model/docs/safety.md, not only a build-and-care page")
    out.append("the report keeps its sign-off, sub-assembly and change-request sections when empty")
    return out


def note_level(product: Product) -> dict[str, object] | None:
    """Record the level and, when it rose since the last check, say so once (W6).

    Returns ``{"from": "lite", "to": "standard", "reasons": […], "now_requires": […]}`` the
    first time ``n2f check`` sees ``standard`` after ``lite``; ``None`` otherwise.  The level
    is kept in ``build/.n2f/ceremony.json``.
    """
    ceremony = derive_ceremony(product)
    path = product.paths.build / RECORD_REL
    last: str | None = None
    try:
        last = json.loads(path.read_text(encoding="utf-8")).get("level")
    except (OSError, ValueError, AttributeError):
        last = None
    if last != ceremony.level:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"level": ceremony.level}) + "\n", encoding="utf-8")
    if last == "lite" and ceremony.level == "standard":
        return {
            "from": "lite",
            "to": "standard",
            "reasons": list(ceremony.reasons),
            "now_requires": what_standard_requires(product),
        }
    return None


def ceremony_value(product: Product) -> str:
    """The level as a dependency value (``manifest://ceremony``)."""
    return derive_ceremony(product).level
