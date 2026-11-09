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
from napkin2factory.concepts.promote.seeding import SeedPlan


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
    parked: list[str] = field(default_factory=list)
    already_rejected: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    snapshot: str | None = None
    checkpoint: int | None = None
    files: list[str] = field(default_factory=list)
    #: the top assembly and the module stubs written (P10); empty when none were
    assemblies: list[SeededAssembly] = field(default_factory=list)
    #: the card's modules in plain words (``door (built as one unit)``)
    modules: list[str] = field(default_factory=list)
    #: the modules as a suggestion, when the product already had its assemblies
    suggestion: str | None = None
    #: the product's word for the space it must fit (its screens' ``WORDS``; S-137)
    space: str = "space"
    #: what the card's rough shapes became: parts, sizes, layout (B-0316, S-336)
    seed: SeedPlan = field(default_factory=SeedPlan)
    #: limits the card's screening already fails, reported for the owner instead of seeded (B-0324)
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    #: the command that builds what promotion seeded (the MCP tool ``n2f_sync`` runs it)
    NEXT = "n2f build"

    @property
    def next(self) -> str:
        """The command or next action: ask about conflicts, else build."""
        if self.conflicts:
            return (
                "Ask the owner about each conflict before building: "
                "drop the limit, or change the design."
            )
        return self.NEXT

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
        order = (
            "form",
            "space",
            "supply",
            "sag",
            "yield",
            "buckling",
            "tip-over",
            "cost",
            "weight",
            "budget",
        )
        words = {**_ABOUT_WORDS, "space": f"the {self.space}"}
        parts = [f"{abouts[a]} about {words[a]}" for a in order if a in abouts]
        reqs = _count(len(self.requirements), "requirement") + (
            f" ({', '.join(parts)})" if parts else ""
        )
        style = "wrote style.yaml" if self.style_created else "updated style.yaml"
        head = f"{self.card_id} is now the design direction ({self.dec_id})."
        if not self.params and not self.requirements and not self.conflicts:
            # nothing seeded: say so (gate B, B4)
            line = (
                f"{head} The card had no sizes or site limits, so no numbers or requirements "
                "were added; the look is recorded in style.yaml."
            )
        else:
            line = f"{head} {params}, {reqs}, {style}."
        stubs = [a.id.replace("-", " ") for a in self.assemblies if not a.top]
        if self.seed.seeded:
            pieces = sum(p.qty for p in self.seed.parts)
            line += (
                f" Its rough shapes became {_count(len(self.seed.parts), 'part')} "
                f"({_count(pieces, 'piece')}), placed where the card drew them and driven by "
                "the overall sizes, with the sag and strength checks on the built model: "
                "build next, and change the sizes, never the seeded parts or layout by hand."
            )
        if stubs:
            line += (
                f" The product's structure starts from its {_count(len(stubs), 'module')}: "
                f"{_and(stubs)}, "
                + ("each with its parts" if self.seed.seeded else "each still empty")
                + ", inside the top assembly."
            )
        if self.rejected or self.parked:
            n = len(self.rejected) + len(self.parked)
            names = _and([*self.rejected, *self.parked])
            verb = "is" if n == 1 else "are"
            noun = "an alternative" if n == 1 else "alternatives"
            line += f" {names} {verb} kept as {noun}."
        if self.conflicts:
            conflict_lines = "\n".join(f"  conflict: {c['say']}" for c in self.conflicts)
            return f"{line}\n{conflict_lines}\nNext: {self.next}"
        return line + " Next: `n2f build && n2f check`."

    def _seeded_dict(self) -> dict[str, Any]:
        """What the rough shapes became, for ``--json`` (empty lists when nothing was seeded)."""
        seed = self.seed
        return {
            "model": seed.seeded,
            "skipped": seed.skipped,
            "parts": [
                {
                    "uri": f"part://{p.id}",
                    "qty": p.qty,
                    "kit": p.kit,
                    "file": p.file,
                    "from": p.calls,
                    "module": p.module,
                    "stretched_by": [f"param://{n}" for n in p.stretched],
                }
                for p in seed.parts
            ],
            "overall_sizes": {a: f"param://{n}" for a, n in seed.sizes.items()},
            "layout": seed.geometry_files,
            "structure_checks": [
                f"req://{r.id}"
                for r in self.requirements
                if (r.data.get("verify") or {}).get("kind") == "structure"
            ],
        }

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
            "conflicts": self.conflicts,
            "style": {"file": self.style_file, "created": self.style_created},
            "rejected": self.rejected,
            "parked": self.parked,
            "already_rejected": self.already_rejected,
            "snapshot": self.snapshot,
            "checkpoint": self.checkpoint,
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
            "seeded": self._seeded_dict(),
            "next": self.next,
            "suggestion": self.suggestion,
            "notes": self.notes,
            "summary": self.summary(),
        }


#: What each ``about`` is in the owner's words; ``space`` says the product's own word for
#: the space it must fit (``PromotionResult.space``; gate E, C13).
_ABOUT_WORDS = {
    "form": "form",
    "space": "the space",
    "supply": "the supply",
    "weight": "the weight",
    "budget": "module sizes",
    "sag": "the sag limit",  # B-0230: what the card's loads and limits become
    "cost": "the cost budget",
    "yield": "strength",  # S-336: the structural factors the built model re-checks
    "buckling": "buckling",
    "tip-over": "tipping over",
}
