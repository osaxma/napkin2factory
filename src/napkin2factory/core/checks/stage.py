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
    CHOICE,
    OWNER_WORDS,
    example_signoff_why,
    example_signoff_words,
    is_example_signoff,
)
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.loader import Product
from napkin2factory.core.model.concepts import CONCEPT_STATUSES as CARD_STATUSES
from napkin2factory.core.model.manifest import SCOPE_WORDS

if TYPE_CHECKING:
    from napkin2factory.core.checks.results import CheckResult
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


def domain_word(name: str) -> str:
    """How the owner says a domain (S-150): "Wiring", never a bare key when it has a word.

    An installed domain says itself by its owner vocabulary term named like the domain
    (``vocabulary={"owner": {"<name>": "wiring"}}``), else by its ``title``; a domain that is
    not installed (a scope key a product names before its domain exists) is its key,
    capitalised.
    """
    d = _installed(name)
    word = ""
    if d is not None:
        word = d.vocabulary.get("owner", {}).get(name, "") or d.title
    word = word or name
    return word[:1].upper() + word[1:]


def requirement_words(product: Product, rid: str) -> str:
    """A requirement as the owner reads it: its id with its title (gate F, concern 15)."""
    req = product.requirements.get(rid)
    return f"{rid} ({req.title})" if req is not None and req.title else rid


def scope_entries(product: Product) -> list[dict[str, Any]]:
    """The declared scope in ``n2f.yaml`` order, each with its owner line (F11).

    A ``later`` domain that leaves requirements out lists them, with their titles, under
    ``left_for_later`` (S-149), so the scope line names what waits; an ``external`` domain
    with no module standing for it carries ``missing_stub``, the owner's next step (S-151).
    """
    from napkin2factory.core.model.manifest import scope_line

    stubless = missing_stubs(product)
    out: list[dict[str, Any]] = []
    for domain, entry in product.manifest.scope.items():
        dec = product.decisions.get(entry.decision) if entry.decision else None
        word = domain_word(domain)
        item: dict[str, Any] = {
            "domain": domain,
            "state": entry.state,
            "decision": entry.decision,
            "note": entry.note,
            **({"stub": str(entry.stub)} if entry.stub is not None else {}),
            "line": scope_line(domain, entry, dec.title if dec is not None else None, word),
        }
        if entry.state == "later":
            left = [
                requirement_words(product, r)
                for r in later_requirements(product)[domain]
                if not product.requirements[r].safety
            ]
            if left:
                item["left_for_later"] = left
        if domain in stubless:
            item["missing_stub"] = stubless[domain]
        out.append(item)
    return out


def scope_entry(product: Product, domain: str) -> dict[str, Any] | None:
    """One domain's scope entry as :func:`scope_entries` gives it, or ``None`` when undeclared.

    The public way for a domain to say its own scope line (S-163): ``entry["line"]`` is
    "Wiring: left for later (not designed here yet) — <note> (DEC-xxx)", in the words every
    other surface uses; ``entry["state"]``, ``"decision"``, ``"note"`` and, for ``later``,
    ``"left_for_later"`` (the requirements it leaves out) come with it.
    """
    return next((e for e in scope_entries(product) if e["domain"] == domain), None)


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


def mark_later(product: Product, results: list[CheckResult]) -> None:
    """A requirement a ``later`` domain leaves out reads ``later`` in the checks (S-149).

    Its own status, counted apart from "needs your sign-off" (gate F, concern 7): the check
    still runs, and what it found stays in ``detail.later`` (``status``, ``message``) for
    the day the scope says ``in``.  A safety requirement is never left for later: its row is
    untouched and still blocks.
    """
    from napkin2factory.core.checks.results import LATER

    owner: dict[str, str] = {}
    for domain, rids in later_requirements(product).items():
        for rid in rids:
            owner.setdefault(rid, domain)  # n2f.yaml order: the first later domain says it
    if not owner:
        return
    for r in results:
        rid = r.id.removeprefix("req://")
        if r.kind != "requirement" or rid not in owner or product.requirements[rid].safety:
            continue
        domain = owner[rid]
        entry = product.manifest.scope[domain]
        dec = f" ({entry.decision})" if entry.decision else ""
        r.detail = {
            **r.detail,
            "later": {
                "domain": domain,
                "decision": entry.decision,
                "status": r.status,
                "message": r.message,
            },
        }
        r.status = LATER
        r.message = (
            f"{domain_word(domain)} is left for later{dec}: not checked until it is designed here"
        )


def scope_check_reads(product: Product) -> list[str]:
    """What :func:`mark_later` depends on, as recorded reads of the ``checks`` rule (S-149).

    The state of every domain a requirement could belong to (declared, installed, or named by
    a tag or category; "missing" until declared), so a first ``later`` reruns the checks; and,
    once a domain is ``later``, its decision and each requirement's tags, category and
    allocation, so a requirement newly tagged moves its row.  A scope note edit reruns nothing.
    """
    from napkin2factory.core.graph.values import SCOPE_KEY
    from napkin2factory.core.registry import registry

    names = set(product.manifest.scope) | {d.name for d in registry().domains}
    for req in product.requirements.values():
        names |= set(req.tags)
        if req.category:
            names.add(req.category)
    reads = [f"{SCOPE_KEY}#{d}.state" for d in sorted(names)]
    later = later_domains(product)
    if later:
        reads += [f"{SCOPE_KEY}#{d}.decision" for d in later]
        for rid in product.requirements:
            reads += [f"req://{rid}#{f}" for f in ("tags", "category", "allocation")]
    return reads


def missing_stubs(product: Product) -> dict[str, str]:
    """``external`` domain → the owner's next step, for each with no module standing for it.

    The same cases validation refuses (F11); ``n2f status`` still shows the product with this
    as its first bullet (gate F, concern 10, S-151).
    """
    stubs = {aid for aid, a in product.assemblies.items() if a.build == "external"}
    out: dict[str, str] = {}
    for domain, entry in product.manifest.scope.items():
        if entry.state != "external":
            continue
        if entry.stub is not None:
            if entry.stub.id in product.assemblies:
                continue
            file, uri = f"model/assemblies/{entry.stub.id}.yaml", str(entry.stub)
        elif stubs:
            continue
        else:
            file, uri = "model/assemblies/<id>.yaml", "asm://<id>"
        out[domain] = (
            f"{domain_word(domain)} is done elsewhere, but nothing in the product shows where "
            f"it fits yet: your agent adds a stand-in module, {file}, with `build: external`, "
            "its `ports:` (the joints it fits by) and no children, lists it in the assembly "
            f"it fits into and names it in n2f.yaml as `stub: {uri}`"
        )
    return out


def _scope_note(product: Product, domain: str, waiting: list[str], gate: str) -> dict[str, str]:
    """The row a ``later`` domain leaves under a gate: what is left out, never silently."""
    entry = product.manifest.scope[domain]
    head = SCOPE_WORDS["later"] + (f" ({entry.decision})" if entry.decision else "")
    safety = [r for r in waiting if product.requirements[r].safety]
    left = [requirement_words(product, r) for r in waiting if r not in safety]
    what = "checked" if gate == "verify" else "designed"
    if gate == "verify" and left:
        noun = "requirement" if len(left) == 1 else "requirements"
        tail = f"{len(left)} {noun} left for later with it: {', '.join(left)}"
    elif gate == "verify":
        tail = "no requirement is left for later with it"
    else:
        tail = "its rows wait for it"
    text = f"{head} — not {what} at this stage; {tail}"
    if safety:
        named = ", ".join(requirement_words(product, r) for r in safety)
        text += (
            f"; {named} {'is' if len(safety) == 1 else 'are'} about safety and still "
            + ("needs" if len(safety) == 1 else "need")
            + " a sign-off"
        )
    return {"title": domain_word(domain), "summary": text, "scope": "later"}


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


#: The order :func:`check_rows_state` says the statuses in (``choice`` added in S-162; the
#: others keep their v0.5 order, so a summary without a choice reads as before).
ROW_ORDER: tuple[str, ...] = (
    "pass",
    "fail",
    "choice",
    "needs-human",
    "warn",
    "skip",
    "signed",
    "later",
)


def _counted(n: int, status: str, words: dict[str, str]) -> str:
    """``"2 OK"``: a count with the domain's word for the status, else the core's."""
    if status in words:
        return f"{n} {words[status]}"
    if status == CHOICE:  # the core's "a choice waiting on you", counted
        return f"{n} choice{'' if n == 1 else 's'} waiting on you"
    return f"{n} {OWNER_WORDS.get(status, status)}"


def check_rows_state(build_dir: Path, kind: str, words: dict[str, str]) -> GateRowState | None:
    """A gate row from the ``checks.json`` rows of one ``kind`` (a helper for domains, F4).

    "3 checks: 2 OK, 1 needs attention" in ``words`` (status → owner words); ``None`` when no
    row of that kind exists or the checks have not run.  The failing rows block the Verify
    gate on their own already, so the row adds no blocker.  Every status counted is said
    (S-162): one ``words`` leaves out falls back to the core's owner words
    (:data:`~napkin2factory.core.checks.results.OWNER_WORDS`), a choice as "1 choice waiting
    on you", in the order of :data:`ROW_ORDER`, then any other status by name.
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
    order = [*ROW_ORDER, *sorted(k for k in counts if k not in ROW_ORDER)]
    parts = [_counted(counts[k], k, words) for k in order if counts.get(k)]
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
    # F11: work done elsewhere with no module standing for it comes first (S-151)
    design_blockers: list[str] = list(missing_stubs(product).values())
    # owner words (gate D, N5): parts and assemblies by name, never their ids
    for part in product.custom_parts():
        if not part.has_geometry:
            design_blockers.append(f"{part.name}: no shape yet — the designer draws it")
    manifest = Manifest.load(build_dir)
    for part in product.parts_with_geometry():
        if f"part:{part.id}" not in manifest.entries:
            design_blockers.append(f"{part.name}: not built yet — run `n2f build`")
    for asm in product.assemblies.values():
        if asm.build == "external":
            continue  # supplied, not built here (F11): never "not built yet" (S-152)
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
    fail_texts: list[str] = []  # failing rows only: a change request names the first (S-282)
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
            if r["id"] in excluded or r["status"] == "later":
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
                fail_texts.append(text)
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
                released_blockers.append(
                    "unsaved edits: save them as a checkpoint (`n2f snapshot`) "
                    "or undo them (`n2f undo`)"
                )
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
    # S-282: an open change request is what the owner is in the middle of; status names it
    # and its next step comes before any requirement line
    open_ecrs = [e for e in product.ecrs.values() if e.status in ("draft", "approved")]
    if open_ecrs:
        e = open_ecrs[0]
        head = f"{e.id} ({e.title}) is {e.status}: "
        if fail_texts:
            next_step = (
                f"{head}{fail_texts[0]}; fix it, or drop the change with `n2f ecr abort {e.id}`"
            )
        elif e.status == "draft":
            next_step = (
                f"{head}edit the files under `model/`, then `n2f ecr impact {e.id}`; "
                f"`n2f ecr abort {e.id}` drops it"
            )
        else:
            next_step = (
                f"{head}`n2f ecr close {e.id}` when the work is done, or `n2f ecr abort {e.id}`"
            )
    return StageReport(stage=stage, gates=gates, next_step=next_step, scope=scope_entries(product))
