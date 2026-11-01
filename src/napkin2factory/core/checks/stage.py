"""Stage computation (D10, §4.3): derived from repo state, never stored.

Intake complete when requirements and operator pass lint; Design complete when every
custom part has geometry and the build succeeded; Verify complete when checks have no
``fail``, every ``needs-human`` has a valid sign-off and no sign-off is an example; Released
when a Revision tag exists for the current tree.  ``warn`` never blocks.

Napkin (NAPKIN_STAGE N11) is an optional first gate, present only when ``concepts/`` holds a
card: complete when one card is ``promoted``.  Products without concepts see exactly the
four v0.1 gates.  Concepts never gate a release; the gate only names where the product is.

Scope (F11, ``n2f.yaml`` ``scope:``): the requirements and gate rows of a domain whose scope
is ``later`` are left out of the Design and Verify gates, each gate saying so in a row of its
own ("Electrical: later (DEC-xxx) — …"), never silently.  A safety requirement is never left
out: it still needs its sign-off and still blocks a release.

Choices (F12): an open choice never blocks by itself; it blocks the gate its ``blocks`` names
(``design``, ``verify`` or ``release``; ``none`` holds nothing) until ``n2f decide`` records
the pick, one blocker per choice in owner words ("a choice is waiting on you: …").  A decided
choice the model does not show yet is a Design caveat ("decided in DEC-x …, not yet in the
design") and, unless it holds nothing, a blocker of the release (S-139).  While the first open
gate has only caveats, "Next:" names the choice that holds a later gate (gate F, concern 14).

Example sign-offs (``example: true``) are *caveats*, not blockers: they keep the Verify gate
open and the stage at ``verify``, but they do not stop a demonstration release
(``n2f release --allow-example-signoffs``), which reads ``Gate.blockers`` only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from napkin2factory.core.checks.results import (
    example_signoff_why,
    example_signoff_words,
    is_example_signoff,
)
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.loader import Product
from napkin2factory.core.model.concepts import CONCEPT_STATUSES as CARD_STATUSES

if TYPE_CHECKING:
    from napkin2factory.core.domain import Domain, GateRowState
    from napkin2factory.core.model.requirements import Requirement

STAGES = ("intake", "design", "verify", "released")
#: The optional stage before Intake (N11); present only when ``concepts/`` holds a card.
NAPKIN = "napkin"
#: What ``StageReport.current`` reads as to an owner, everywhere it is shown (S-090):
#: the ``n2f status`` headline, the report badge and ``n2f ecr close``.
STAGE_WORDS = {
    NAPKIN: "Napkin",
    "intake": "Intake",
    "design": "Design",
    "verify": "Verify",
    "ready": "ready to release",
    "released": "Released",
}


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
    """Where the product stands, every gate, and the next step.

    Two readings of "stage" (S-090).  :attr:`current` is the one every person sees: the
    stage being worked in, i.e. the first gate not complete (review gate B, B5) — the
    ``n2f status`` headline, the report badge and ``n2f ecr close`` all print it, and
    ``--json`` carries it as ``current_stage``.  :attr:`stage` is the last gate passed
    (a gate held open only by example sign-offs counts as passed); it stays in ``--json``
    unchanged for scripts written against v0.1.
    """

    stage: str
    gates: list[Gate]
    next_step: str
    #: The declared scope (F11), one dict per domain: ``domain``, ``state``, ``decision``,
    #: ``note`` and ``line`` (owner words); empty when ``n2f.yaml`` has no ``scope:``.
    scope: list[dict[str, Any]] = field(default_factory=list)

    @property
    def current(self) -> str:
        """The stage being worked in: the first gate not complete (review gate B, B5).

        A ticked Intake reads ``design``; when only Released is open the product is
        ``ready`` (to release); once the current snapshot is a Revision, ``released`` —
        also a demonstration Revision whose Verify gate stays open only for example
        sign-offs (the report and ``n2f status`` still list those).
        """
        if self.gates and self.gates[-1].name == "released" and self.gates[-1].ok:
            return "released"
        first_open = next((g.name for g in self.gates if not g.ok), None)
        if first_open is None:
            return "released"
        return "ready" if first_open == "released" else first_open

    @property
    def headline(self) -> str:
        """Alias of :attr:`current` (the name ``n2f status`` used first)."""
        return self.current

    @property
    def current_words(self) -> str:
        """:attr:`current` in owner words (``STAGE_WORDS``)."""
        return STAGE_WORDS[self.current]

    def to_dict(self) -> dict[str, Any]:
        """JSON form: ``stage`` (last gate passed) and ``current_stage`` (being worked in)."""
        out = {
            "stage": self.stage,
            "current_stage": self.current,
            "gates": [g.__dict__ for g in self.gates],
            "next_step": self.next_step,
        }
        if self.scope:  # only when declared: a product without scope reads as before (F16)
            out["scope"] = self.scope
        return out


# ---- scope (F11) ----------------------------------------------------------------------------


def scope_entries(product: Product) -> list[dict[str, Any]]:
    """The declared scope in ``n2f.yaml`` order, each with its owner line (F11)."""
    from napkin2factory.core.model.manifest import scope_line

    out: list[dict[str, Any]] = []
    for domain, entry in product.manifest.scope.items():
        dec = product.decisions.get(entry.decision) if entry.decision else None
        out.append(
            {
                "domain": domain,
                "state": entry.state,
                "decision": entry.decision,
                "note": entry.note,
                **({"stub": str(entry.stub)} if entry.stub is not None else {}),
                "line": scope_line(domain, entry, dec.title if dec is not None else None),
            }
        )
    return out


def later_domains(product: Product) -> list[str]:
    """Domains whose scope is ``later``, in ``n2f.yaml`` order."""
    return [d for d, e in product.manifest.scope.items() if e.state == "later"]


def _installed(name: str) -> Domain | None:
    from napkin2factory.core.registry import registry

    return next((d for d in registry().domains if d.name == name), None)


def requirement_in_domain(req: Requirement, domain: str) -> bool:
    """True when ``req`` belongs to ``domain`` (F11).

    By any of these, in order: a tag naming the domain (``tags: [electrical]``, which works
    before the domain is installed), a category of that name, and, for an installed domain,
    a category, verify kind or URI scheme (verify target, allocation) the domain registers.
    """
    if domain in req.tags or req.category == domain:
        return True
    d = _installed(domain)
    if d is None:
        return False
    if req.category in d.categories:
        return True
    if req.verify is not None and req.verify.kind in {v.name for v in d.verify_kinds}:
        return True
    schemes = {f.uri_scheme for f in d.families}
    schemes |= {f.produces.removesuffix("://") for f in d.rule_families if f.produces}
    named = [req.verify.target] if req.verify is not None and req.verify.target else []
    named += list(req.allocation) if isinstance(req.allocation, list) else []
    return any(u.scheme in schemes for u in named)


def later_requirements(product: Product) -> dict[str, list[str]]:
    """``later`` domain → the requirement ids that belong to it (safety ones included)."""
    return {
        d: sorted(r.id for r in product.requirements.values() if requirement_in_domain(r, d))
        for d in later_domains(product)
    }


def _scope_note(product: Product, domain: str, waiting: list[str], gate: str) -> dict[str, str]:
    """The row a ``later`` domain leaves under a gate: what is left out, never silently."""
    entry = product.manifest.scope[domain]
    head = "later" + (f" ({entry.decision})" if entry.decision else "")
    safety = [r for r in waiting if product.requirements[r].safety]
    left = [r for r in waiting if r not in safety]
    what = "checked" if gate == "verify" else "designed"
    if gate == "verify" and left:
        noun = "requirement waits" if len(left) == 1 else "requirements wait"
        tail = f"{len(left)} {noun} for it: {', '.join(left)}"
    elif gate == "verify":
        tail = "no requirement waits for it"
    else:
        tail = "its rows wait for it"
    text = f"{head} — not {what} at this stage; {tail}"
    if safety:
        text += (
            f"; {', '.join(safety)} {'is' if len(safety) == 1 else 'are'} about safety and "
            "still need" + ("s" if len(safety) == 1 else "") + " a sign-off"
        )
    return {"title": domain.capitalize(), "summary": text, "scope": "later"}


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


def _domain_rows(
    product: Product, build_dir: Path, gate: str, blockers: list[str]
) -> tuple[list[dict[str, str]], list[str]]:
    """The registered gate rows of ``gate`` that apply (F4): ``(rows, caveats)``.

    A row's blockers are added to ``blockers``; a domain with no content returns no row, so
    an empty domain shows nothing.  Each row is ``{"title", "summary"}`` for ``n2f status``.
    """
    from napkin2factory.core.registry import registry

    rows: list[dict[str, str]] = []
    caveats: list[str] = []
    later = set(later_domains(product))
    owner = {id(r): d.name for d in registry().domains for r in d.gate_rows}
    for gate_row in registry().gate_rows(gate):
        if owner.get(id(gate_row)) in later:
            continue  # F11: left out; the domain's scope row under this gate says so
        state = gate_row.row(product, build_dir)
        if state is None:
            continue
        rows.append({"title": gate_row.title, "summary": state.summary})
        blockers += state.blockers
        caveats += state.caveats
    return rows, caveats


def check_rows_state(build_dir: Path, kind: str, words: dict[str, str]) -> GateRowState | None:
    """A gate row from the ``checks.json`` rows of one ``kind`` (a helper for domains, F4).

    "3 checks OK, 1 needs attention" in ``words`` (status → owner words); ``None`` when no
    row of that kind exists or the checks have not run.  The failing rows block the Verify
    gate on their own already, so the row adds no blocker.
    """
    from napkin2factory.core.domain import GateRowState

    path = build_dir / "checks" / "checks.json"
    if not path.is_file():
        return None
    results = json.loads(path.read_text(encoding="utf-8")).get("results", [])
    rows = [r for r in results if r.get("kind") == kind]
    if not rows:
        return None
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    order = ("pass", "fail", "needs-human", "warn", "skip", "signed")
    parts = [f"{counts[k]} {words.get(k, k)}" for k in order if counts.get(k)]
    noun = "check" if len(rows) == 1 else "checks"
    return GateRowState(f"{len(rows)} {noun}: " + ", ".join(parts))


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
        intake_blockers.append(
            "no requirements yet — run intake (the project manager role, roles/pm.md)"
        )
    gates.append(Gate("intake", not intake_blockers, intake_blockers))
    # Design
    design_blockers: list[str] = []
    # owner words (gate D, N5): parts and assemblies by name, never their ids
    for part in product.custom_parts():
        if not part.has_geometry:
            design_blockers.append(f"{part.name}: no shape yet — the designer draws it")
    manifest = Manifest.load(build_dir)
    for part in product.parts_with_geometry():
        if f"part:{part.id}" not in manifest.entries:
            design_blockers.append(f"{part.name}: not built yet — run `n2f build`")
    for asm in product.assemblies.values():
        if f"asm:{asm.id}" not in manifest.entries:
            design_blockers.append(f"{asm.name}: not built yet — run `n2f build`")
    if not product.parts:
        design_blockers.append("no parts yet — next, the designer gives each module its parts")
    from napkin2factory.core.checks.choices import WAITING, choice_blockers, unapplied_caveats

    held = choice_blockers(build_dir)  # F12: an open choice holds the gate it names
    held_all = {b for bs in held.values() for b in bs}
    design_blockers += held.get("design", [])
    design_rows, design_caveats = _domain_rows(product, build_dir, "design", design_blockers)
    # a decided choice the model does not show yet keeps the gate open (S-133); the release
    # is what it blocks (S-139, in `held["released"]`)
    design_caveats += unapplied_caveats(build_dir)
    waiting = later_requirements(product)
    for domain in waiting:  # F11: a later domain's design rows are left out, and said so
        d = _installed(domain)
        if d is not None and any(r.gate == "design" for r in d.gate_rows):
            design_rows.append(_scope_note(product, domain, [], "design"))
    gates.append(
        Gate(
            "design",
            not design_blockers and not design_caveats and not intake_blockers,
            design_blockers,
            {"rows": design_rows} if design_rows else {},
            design_caveats,
        )
    )
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
        # F11: a later domain's requirements are left out (its row below says which);
        # a safety requirement never is
        excluded = {
            f"req://{rid}"
            for rids in waiting.values()
            for rid in rids
            if not product.requirements[rid].safety
        }
        for r in data.get("results", []):
            if r["id"] in excluded:
                continue
            if r["status"] == "fail":
                # a requirement keeps its REQ id (the owner's table shows it); other rows
                # are said by their message alone for the owner (gate D, N5)
                text = r["persona_message"] or r["message"]
                if product.operator.persona != "owner":
                    text = f"{r['id']}: {text}"
                elif r["id"].startswith("req://"):
                    text = f"{r['id'].removeprefix('req://')}: {text}"
                verify_blockers.append(text)
            elif r["status"] == "needs-human":
                why = r.get("message") or "needs a human sign-off"
                rid = r["id"] if product.operator.persona != "owner" else r["id"].split("://")[-1]
                verify_blockers.append(
                    f"{rid}: needs a human sign-off ({why}) — `n2f signoff "
                    f'{r["id"].split("://")[-1]} --by <name> --statement "…"`'
                )
            elif is_example_signoff(r["status"], r.get("detail") or {}):
                example_ids.append(r["id"].split("://")[-1])
        if data.get("status") == "placeholder":
            verify_blockers.append("checks are placeholders in this build")
        verify_blockers += held.get("verify", [])
    verify_caveats = [example_signoff_hint(example_ids)] if example_ids else []
    verify_rows, row_caveats = _domain_rows(product, build_dir, "verify", verify_blockers)
    verify_rows += [_scope_note(product, d, rids, "verify") for d, rids in waiting.items()]
    verify_caveats += row_caveats
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
                **({"rows": verify_rows} if verify_rows else {}),
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
    released_blockers += held.get("released", [])
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
    open_at = next((i for i, g in enumerate(gates) if not g.ok), None)
    first_open = gates[open_at] if open_at is not None else None
    if first_open is None or open_at is None:
        next_step = "send the Revision to the manufacturer"
    elif first_open.blockers:
        next_step = first_open.blockers[0]
    elif held_later := [b for g in gates[open_at + 1 :] for b in g.blockers if b in held_all]:
        # only caveats here (example sign-offs, a pick to make): the owner's choice that
        # holds a later gate comes first, or the release refuses on it (gate F, concern 14)
        next_step = sorted(held_later, key=lambda b: not b.startswith(WAITING))[0]
    elif first_open.caveats:
        next_step = first_open.caveats[0]
    else:
        next_step = first_open.name
    return StageReport(stage=stage, gates=gates, next_step=next_step, scope=scope_entries(product))
