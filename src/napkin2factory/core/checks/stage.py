"""Stage computation (D10, §4.3): derived from repo state, never stored.

Intake complete when requirements and operator pass lint; Design complete when every
custom part has geometry and the build succeeded; Verify complete when checks have no
``fail``, every ``needs-human`` has a valid sign-off and no sign-off is an example; Released
when a Revision tag exists for the current tree.  ``warn`` never blocks.

Napkin (NAPKIN_STAGE N11) is an optional first gate, present only when ``concepts/`` holds a
card: complete when one card is ``promoted``.  Products without concepts see exactly the
four v0.1 gates.  Concepts never gate a release; the gate only names where the product is.

Example sign-offs (``example: true``) are *caveats*, not blockers: they keep the Verify gate
open and the stage at ``verify``, but they do not stop a demonstration release
(``n2f release --allow-example-signoffs``), which reads ``Gate.blockers`` only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.core.checks.results import (
    example_signoff_why,
    example_signoff_words,
    is_example_signoff,
)
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.loader import Product
from napkin2factory.core.model.concepts import CONCEPT_STATUSES as CARD_STATUSES

STAGES = ("intake", "design", "verify", "released")
#: The optional stage before Intake (N11); present only when ``concepts/`` holds a card.
NAPKIN = "napkin"


@dataclass
class Gate:
    """One gate's state, what blocks it, and what keeps it open without blocking a release."""

    name: str
    ok: bool
    blockers: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)
    #: Reasons the gate is not done that a demonstration release may pass over
    #: (today: example sign-offs).  Owner-friendly, each a complete next step.
    caveats: list[str] = field(default_factory=list)

    @property
    def open_only_by_caveats(self) -> bool:
        """Not done, yet nothing blocks: the product is *in* this stage."""
        return not self.ok and not self.blockers and bool(self.caveats)


@dataclass
class StageReport:
    """Current stage plus every gate."""

    stage: str
    gates: list[Gate]
    next_step: str

    @property
    def headline(self) -> str:
        """The stage ``n2f status`` names: the first gate not complete (review gate B, B5).

        ``stage`` is the last gate passed (kept for ``--json`` and the report); the owner
        reads the stage they are working in, so a ticked Intake reads "Design".  When only
        Released is open the product is ``ready``; when every gate is done, ``released``.
        """
        first_open = next((g.name for g in self.gates if not g.ok), None)
        if first_open is None:
            return "released"
        return "ready" if first_open == "released" else first_open

    def to_dict(self) -> dict[str, Any]:
        """JSON form."""
        return {
            "stage": self.stage,
            "gates": [g.__dict__ for g in self.gates],
            "next_step": self.next_step,
        }


def example_signoff_hint(requirement_ids: list[str]) -> str:
    """The next step when example sign-offs stand in for reviews (owner wording)."""
    n = len(requirement_ids)
    real = "a real one" if n == 1 else "real ones"
    return (
        f"replace the {example_signoff_words(n)} with {real} — "
        f'`n2f signoff {requirement_ids[0]} --by <name> --statement "…"` — '
        "or release with --allow-example-signoffs for a demonstration"
    )


def _checks_stale(product: Product, build_dir: Path, manifest: Manifest) -> bool:
    """True when the ``checks`` rule would rerun (something it read changed)."""
    try:
        from napkin2factory.core.graph.rules import build_rules
        from napkin2factory.core.graph.runner import needs_run

        rule = next(r for r in build_rules(product) if r.id == "checks")
        return needs_run(rule, product, manifest, build_dir)[0]
    except Exception:
        return False


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def napkin_gate(root: Path) -> Gate | None:
    """The Napkin gate, or None when ``concepts/`` holds no card (the stage is then hidden).

    Done when one card is promoted *by* ``n2f concept promote`` (a screening and a
    ``decision.dec`` on record).  A ``promoted`` status typed by hand is a blocker, not a
    pass (review gate A, B2).  Otherwise one owner-worded blocker naming the next command:
    build the cards first when none has been screened, else compare and choose.
    """
    from napkin2factory.core.concepts import (
        card_files,
        decision_ids,
        load_concepts,
        promotion_problem,
    )
    from napkin2factory.core.errors import Problems

    files = card_files(root)
    if not files:
        return None
    problems = Problems()
    cards = load_concepts(root, problems)
    by_status = {s: [cid for cid, c in cards.items() if c.status == s] for s in CARD_STATUSES}
    promoted = by_status["promoted"]
    detail: dict[str, Any] = {
        "cards": len(files),
        "exploring": len(by_status["exploring"]),
        "rejected": len(by_status["rejected"]),
        "promoted": promoted[0] if promoted else None,
        "unreadable": len(files) - len(cards),
    }
    blockers: list[str] = []
    if promoted:
        dec_ids = decision_ids(root)
        unrecorded = [w for cid in promoted if (w := promotion_problem(cards[cid], dec_ids))]
        if not unrecorded:
            return Gate(NAPKIN, True, [], detail)
        detail["promoted"] = None
        blockers.extend(f"{why} — `n2f concept lint`" for why in unrecorded)
        if problems.errors:
            bad = sorted({Path(p.file).name for p in problems.errors})
            blockers.append(f"{', '.join(bad)} cannot be read — `n2f concept lint` says why")
        return Gate(NAPKIN, False, blockers, detail)
    exploring = by_status["exploring"]
    if not exploring:
        blockers.append(
            "every concept so far is rejected — "
            '`n2f concept new "<title>"` to start another direction'
        )
    elif not any(cards[cid].screening for cid in exploring):
        blockers.append(
            f"{_plural(len(exploring), 'concept')} exploring, none chosen yet — "
            "`n2f concept build --all` first"
        )
    else:
        blockers.append(
            f"{_plural(len(exploring), 'concept')} exploring, none chosen yet — "
            "`n2f concept board` to compare them, then `n2f concept promote C-00x`"
        )
    if problems.errors:
        bad = sorted({Path(p.file).name for p in problems.errors})
        blockers.append(f"{', '.join(bad)} cannot be read — `n2f concept lint` says why")
    return Gate(NAPKIN, False, blockers, detail)


def compute_stage(
    product: Product, build_dir: Path | None = None, *, napkin: bool = True
) -> StageReport:
    """Derive the stage from the model, the build manifest, checks.json and change tracking.

    ``napkin=False`` leaves out the Napkin gate even when concepts exist; build outputs (the
    report) pass it so that concepts never change what ``n2f build`` writes (N1).
    """
    from napkin2factory.core import lint as lint_mod

    build_dir = build_dir or product.paths.build
    gates: list[Gate] = []
    first = napkin_gate(product.root) if napkin else None
    if first is not None:
        gates.append(first)
    names = ((NAPKIN,) if first is not None else ()) + STAGES
    later = len(gates)  # index of the Intake gate
    # Intake
    lint_problems = lint_mod.lint(product)
    req_errors = [
        p
        for p in lint_problems.errors
        if p.subject.startswith("req://") or p.subject == "operator.yaml"
    ]
    intake_blockers = [p.format(product.root) for p in req_errors]
    if not product.requirements:
        intake_blockers.append("no requirements yet — run intake with the n2f-pm skill")
    gates.append(Gate("intake", not intake_blockers, intake_blockers))
    # Design
    design_blockers: list[str] = []
    for part in product.custom_parts():
        if not part.has_geometry:
            design_blockers.append(f"{part.uri} has no geometry yet")
    manifest = Manifest.load(build_dir)
    for part in product.parts_with_geometry():
        if f"part:{part.id}" not in manifest.entries:
            design_blockers.append(f"{part.uri} has not been built — run `n2f build`")
    for asm in product.assemblies.values():
        if f"asm:{asm.id}" not in manifest.entries:
            design_blockers.append(f"{asm.uri} has not been built — run `n2f build`")
    if not product.parts:
        design_blockers.append("no parts yet — the designer role composes the kit")
    gates.append(Gate("design", not design_blockers and not intake_blockers, design_blockers))
    # Verify
    verify_blockers: list[str] = []
    example_ids: list[str] = []
    checks_path = build_dir / "checks" / "checks.json"
    if not checks_path.is_file() or "checks" not in manifest.entries:
        verify_blockers.append("checks have not run — run `n2f check`")
        counts: dict[str, int] = {}
    elif _checks_stale(product, build_dir, manifest):
        verify_blockers.append("the checks are out of date — run `n2f check` to refresh")
        counts = {}
    else:
        data = json.loads(checks_path.read_text(encoding="utf-8"))
        counts = data.get("summary", {})
        for r in data.get("results", []):
            if r["status"] == "fail":
                verify_blockers.append(f"{r['id']}: {r['persona_message'] or r['message']}")
            elif r["status"] == "needs-human":
                why = r.get("message") or "needs a human sign-off"
                verify_blockers.append(
                    f"{r['id']}: needs a human sign-off ({why}) — `n2f signoff "
                    f'{r["id"].split("://")[-1]} --by <name> --statement "…"`'
                )
            elif is_example_signoff(r["status"], r.get("detail") or {}):
                example_ids.append(r["id"].split("://")[-1])
        if data.get("status") == "placeholder":
            verify_blockers.append("checks are placeholders in this build")
    verify_caveats = [example_signoff_hint(example_ids)] if example_ids else []
    gates.append(
        Gate(
            "verify",
            not verify_blockers
            and not verify_caveats
            and not design_blockers
            and not intake_blockers,
            verify_blockers,
            {
                "counts": counts,
                "example_signoffs": example_ids,
                "why": example_signoff_why(len(example_ids)) if example_ids else None,
            },
            verify_caveats,
        )
    )
    # Released
    released_blockers: list[str] = []
    tag = None
    try:
        from napkin2factory.core.vcs import Vcs

        v = Vcs(product.root)
        if not v.is_tracked():
            released_blockers.append("change tracking is not set up — run `n2f init` here")
        else:
            if not v.is_clean():
                released_blockers.append("unsaved changes since the last snapshot")
            tag = v.tag_for_head()
            if tag is None:
                released_blockers.append(
                    "no Revision for the current snapshot — "
                    "`n2f release vX.Y.Z` when the checks are green"
                )
    except Exception as exc:  # never crash status on a tracking problem
        released_blockers.append(f"change tracking unavailable: {exc}")
    # a Revision made with --allow-example-signoffs is still a Revision: caveats do not undo it
    verify_gate = gates[later + 2]
    verified_enough = verify_gate.ok or verify_gate.open_only_by_caveats
    gates.append(
        Gate(
            "released",
            not released_blockers and verified_enough,
            released_blockers,
            {"revision": tag},
        )
    )
    # The stage is the last gate passed; a gate held open only by caveats is passed through
    # (the product is in that stage, not past it) so example sign-offs read as "Verify",
    # never as "Design" and never as verified.
    stage = names[0]
    for g, name in zip(gates, names, strict=True):
        if g.ok or g.open_only_by_caveats:
            stage = name
        else:
            break
    first_open = next((g for g in gates if not g.ok), None)
    if first_open is None:
        next_step = "send the Revision to the manufacturer"
    elif first_open.blockers:
        next_step = first_open.blockers[0]
    elif first_open.caveats:
        next_step = first_open.caveats[0]
    else:
        next_step = first_open.name
    return StageReport(stage=stage, gates=gates, next_step=next_step)
