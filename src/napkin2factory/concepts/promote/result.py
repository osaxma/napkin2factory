"""What a promotion did, in the owner's words and as JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from napkin2factory.concepts.promote.common import (
    NewRequirement,
    SeededParam,
    _and,
    _count,
)
from napkin2factory.concepts.promote.modules import SeededAssembly


@dataclass
class PromotionResult:
    """What ``n2f concept promote`` did (or, with ``dry_run``, would do)."""

    card_id: str
    title: str
    dec_id: str
    override: bool
    params: list[SeededParam] = field(default_factory=list)
    requirements: list[NewRequirement] = field(default_factory=list)
    style_file: str = "style.yaml"
    style_created: bool = False
    rejected: list[str] = field(default_factory=list)
    already_rejected: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    snapshot: str | None = None
    files: list[str] = field(default_factory=list)
    #: the top assembly and the module stubs written (P10); empty when none were
    assemblies: list[SeededAssembly] = field(default_factory=list)
    #: the card's modules in plain words (``door (built as one unit)``)
    modules: list[str] = field(default_factory=list)
    #: the modules as a suggestion, when the product already had its assemblies
    suggestion: str | None = None

    def summary(self) -> str:
        """The owner's line: what changed, what was kept, what to do next."""
        new = [p for p in self.params if p.status == "new"]
        declared = [p for p in self.params if p.status == "declared"]
        over = [p for p in self.params if p.status == "overwritten"]
        extra = []
        if declared:
            extra.append(f"{len(declared)} already declared")
        if over:
            extra.append(f"{len(over)} overwritten")
        params = f"Seeded {_count(len(new), 'parameter')}" + (
            f" ({', '.join(extra)})" if extra else ""
        )
        abouts: dict[str, int] = {}
        for r in self.requirements:
            abouts[r.about] = abouts.get(r.about, 0) + 1
        order = ("form", "alcove", "supply", "weight", "budget")
        parts = [f"{abouts[a]} about {_ABOUT_WORDS[a]}" for a in order if a in abouts]
        reqs = _count(len(self.requirements), "requirement") + (
            f" ({', '.join(parts)})" if parts else ""
        )
        style = "wrote style.yaml" if self.style_created else "updated style.yaml"
        head = f"{self.card_id} is now the design direction ({self.dec_id})."
        if not self.params and not self.requirements:  # nothing seeded: say so (gate B, B4)
            line = (
                f"{head} The card had no sizes or site limits, so no numbers or requirements "
                "were added; the look is recorded in style.yaml."
            )
        else:
            line = f"{head} {params}, {reqs}, {style}."
        stubs = [a.id.replace("-", " ") for a in self.assemblies if not a.top]
        if stubs:
            line += (
                f" The product's structure starts from its {_count(len(stubs), 'module')}: "
                f"{_and(stubs)}, each still empty, inside the top assembly."
            )
        if self.rejected:
            names = _and(self.rejected)
            verb = "is" if len(self.rejected) == 1 else "are"
            noun = "an alternative" if len(self.rejected) == 1 else "alternatives"
            line += f" {names} {verb} kept as {noun}."
        return line + " Next: `n2f build && n2f check`."

    def to_dict(self) -> dict[str, Any]:
        """JSON form for ``--json``: every id."""
        return {
            "id": self.card_id,
            "title": self.title,
            "dec": self.dec_id,
            "override": self.override,
            "parameters": [
                {
                    "uri": f"param://{p.name}",
                    "value": p.value,
                    "status": p.status,
                    "was": p.was,
                    "from": p.source,
                }
                for p in self.params
            ],
            "requirements": [
                {
                    "uri": f"req://{r.id}",
                    "title": r.title,
                    "about": r.about,
                    "verify": r.data.get("verify"),
                }
                for r in self.requirements
            ],
            "style": {"file": self.style_file, "created": self.style_created},
            "rejected": self.rejected,
            "already_rejected": self.already_rejected,
            "snapshot": self.snapshot,
            "files": self.files,
            "assemblies": [
                {
                    "uri": f"asm://{a.id}",
                    "file": a.file,
                    "top": a.top,
                    "build": a.build,
                    "driver": a.driver,
                    "budget": dict(zip(("x", "y", "z"), a.budget, strict=True))
                    if a.budget is not None
                    else None,
                }
                for a in self.assemblies
            ],
            "modules": self.modules,
            "suggestion": self.suggestion,
            "notes": self.notes,
            "summary": self.summary(),
        }


_ABOUT_WORDS = {
    "form": "form",
    "alcove": "the alcove",
    "supply": "the supply",
    "weight": "the weight",
    "budget": "module sizes",
}
