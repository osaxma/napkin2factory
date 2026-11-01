"""``n2f concept new|list|show|build|board|promote|reject|lint`` (NAPKIN_STAGE §4).

Concepts sit outside the build graph (N1): these verbs need a product folder, and all but
``promote`` never load the product model, so a half-written model never blocks exploring
ideas.  ``build`` runs the massing and screening in-process (no build graph); ``board``
writes the read-only comparison page ``build/concepts/board.html``; ``promote`` turns the
chosen card into model content (parameters, requirements, style, a decision) and takes a
snapshot.
"""

from __future__ import annotations

import datetime as dt
import textwrap
from pathlib import Path
from typing import Any

import typer
import yaml
from rich.markup import escape
from rich.table import Table

from napkin2factory.cli.common import (
    DirOption,
    JsonOption,
    console,
    emit_json,
    err_console,
    handle_errors,
    print_problems,
    product_root,
)
from napkin2factory.cli.kernel import warm_kernel_in_background
from napkin2factory.core import concepts as concepts_mod
from napkin2factory.core.errors import GateBlocked, Problems
from napkin2factory.core.model import ConceptCard, Screening

concept_app = typer.Typer(
    help="Concepts: cheap, disposable directions for the product, before the design.",
    no_args_is_help=True,
)

NO_VERDICT = "—"
#: The owner's words for a screening verdict (JSON keeps ``verdict: green|red``; gate B, C7).
VERDICT_WORDS = {"green": "holds up", "red": "has problems"}


def _warm() -> None:
    """Start warming the CAD kernel for the next concept build (N12); never waits."""
    warm_kernel_in_background()


def _row(card: ConceptCard) -> dict[str, str | None]:
    return {
        "id": card.id,
        "status": card.status,
        "title": card.title,
        "based_on": card.based_on,
        "verdict": card.verdict,
    }


def screening_line(card: ConceptCard) -> str:
    """One line on the card's screening, or how to get one."""
    if not card.screening:
        if card.status == "rejected":
            return "never built"
        return f"not built yet — `n2f concept build {card.id}`"
    verdict = card.verdict or "unknown"
    reasons = [r.message or r.title or r.id for r in card.screening.failing]
    if verdict == "red" and reasons:
        return f"screening: this direction has problems: {'; '.join(reasons)}"
    if verdict == "red":
        return "screening: this direction has problems"
    if verdict == "green":
        return "screening: this direction holds up"
    return "screening: not judged yet"


RULE_MARKS = {"pass": "✓", "fail": "✗", "warn": "!", "skip": "·"}


def screening_block(screening: Screening) -> list[str]:
    """The screening as plain lines: given, computed and estimate numbers labelled, then rules.

    The owner's words only: value names as on the board, each value's ``source`` sentence,
    each rule's title (ids, field paths and calc references stay in ``--json``; gate B).
    """
    from napkin2factory.concepts.board import NAMES

    at = f" ({screening.at.date().isoformat()})" if screening.at else ""
    verdict = VERDICT_WORDS.get(screening.verdict or "", "not judged yet")
    lines = [f"screening{at}: {verdict}"]
    for section, values, what in (
        ("given", screening.given, "from the card, your own inputs"),
        ("computed", screening.computed, "measured from the rough shapes"),
        ("estimate", screening.estimates, "a rough engineering formula, before any design"),
    ):
        if not values:
            continue
        lines.append(f"  {section} — {what}:")
        names = {k: NAMES.get(k, k.replace("_", " ")) for k in values}
        width = max(len(n) for n in names.values())
        for key, lv in values.items():
            lines.append(f"    {names[key]:<{width}}  {lv.value:<22} {lv.label} · {lv.source}")
    if screening.rules:
        lines.append("  rules:")
        for row in screening.rules:
            relied = f" [{', '.join(row.relies_on)}]" if row.relies_on else ""
            name = (row.title or row.id).rstrip(".")
            name = name[:1].lower() + name[1:]
            lines.append(f"    {RULE_MARKS.get(row.status, '?')} {name}{relied}: {row.message}")
    for note in screening.notes:
        lines.append(f"  note: {note}")
    return lines


@concept_app.command("new")
@handle_errors
def new(
    title: str = typer.Argument(..., help="A short name for the direction."),
    from_: str | None = typer.Option(
        None, "--from", help="Start from an existing card (copies its content)."
    ),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Start a new concept card (status: exploring)."""
    _warm()
    root = product_root(dir)
    card = concepts_mod.new_card(root, title, from_)
    rel = f"concepts/{card.id}.yaml"
    if json_out:
        emit_json({"id": card.id, "status": card.status, "based_on": card.based_on, "file": rel})
        return
    started = f"started concept {card.id}" + (f" from {card.based_on}" if card.based_on else "")
    console.print(
        f"[green]✓[/green] {started} — edit {rel}, then `n2f concept build {card.id}`",
        soft_wrap=True,
    )
    chosen = [
        c.id
        for c in concepts_mod.load_concepts(root, Problems()).values()
        if c.id != card.id and concepts_mod.recorded_promotion(c, root)
    ]
    if chosen:  # gate B, C9: a card made after promotion can be compared, not chosen
        console.print(
            f"  [dim]{chosen[0]} is already the design direction; this card can be compared "
            "on the board, but choosing it instead is a change request.[/dim]",
            soft_wrap=True,
        )


@concept_app.command("list")
@handle_errors
def list_(dir: Path | None = DirOption, json_out: bool = JsonOption) -> None:
    """List the concept cards."""
    _warm()
    root = product_root(dir)
    problems = Problems()
    cards = concepts_mod.load_concepts(root, problems)
    rows = [_row(c) for c in cards.values()]
    if json_out:
        emit_json({"concepts": rows, "problems": [p.to_dict() for p in problems.items]})
        return
    t = Table(title="Concepts")
    for c in ("id", "status", "title", "based on", "screening"):
        t.add_column(c)
    for r in rows:
        t.add_row(
            str(r["id"]),
            str(r["status"]),
            escape(str(r["title"])),
            r["based_on"] or "",
            VERDICT_WORDS.get(r["verdict"] or "", NO_VERDICT),
        )
    console.print(t)
    print_problems(problems, root)
    if not rows and not problems:
        console.print('  none yet · `n2f concept new "<title>"` starts one')


def _without_nulls(value: Any) -> Any:
    """The card as shown: fields left empty (``null``) are dropped (gate B, C8)."""
    if isinstance(value, dict):
        return {k: _without_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_without_nulls(v) for v in value]
    return value


@concept_app.command("show")
@handle_errors
def show(
    concept_id: str = typer.Argument(..., help="Concept id, e.g. C-002."),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Show one concept card and where its screening stands."""
    _warm()
    root = product_root(dir)
    card = concepts_mod.load_card(root, concept_id)
    data = card.model_dump(mode="json", by_alias=True)
    if json_out:
        emit_json({**data, "summary": screening_line(card)})
        return
    console.print(f"file: {concepts_mod.card_path(root, card.id).relative_to(root).as_posix()}")
    shown = _without_nulls({k: v for k, v in data.items() if k not in ("screening", "notes")})
    console.print(
        yaml.safe_dump(
            shown, sort_keys=False, allow_unicode=True, default_flow_style=None, width=10**6
        ),
        markup=False,
        highlight=False,
        soft_wrap=True,
        end="",
    )
    if card.notes:
        width = max(40, min(console.width, 100) - 2)
        console.print("notes:", highlight=False)
        for para in str(card.notes).split("\n"):
            wrapped = textwrap.fill(
                para, width, initial_indent="  ", subsequent_indent="  ", break_long_words=False
            )
            console.print(wrapped, markup=False, highlight=False, soft_wrap=True)
    if card.screening is not None:
        for line in screening_block(card.screening):
            console.print(line, markup=False, highlight=False, soft_wrap=True)
    if card.status == "rejected":
        reason = card.decision.reason if card.decision is not None else None
        words = concepts_mod.set_aside_words(reason)
        console.print(f"{card.id} is {escape(words)}", soft_wrap=True)
    elif card.status == "promoted":
        dec = card.decision.dec if card.decision is not None else None
        console.print(
            f"{card.id} is the chosen direction (promoted" + (f", {dec})" if dec else ")")
        )
    console.print(escape(screening_line(card)), soft_wrap=True)


@concept_app.command("build")
@handle_errors
def build(
    concept_id: str | None = typer.Argument(None, help="Concept id, e.g. C-002."),
    all_: bool = typer.Option(False, "--all", help="Build every card, set-aside ones too."),
    no_render: bool = typer.Option(
        False, "--no-render", help="Skip the pictures (silhouettes and styled screenshots)."
    ),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Build the rough shapes of a concept and screen it (red is information, exit 0)."""
    from napkin2factory.cli.kernel import load_cad_kernel
    from napkin2factory.concepts.build import (
        build_concepts,
        select_cards,
        status_tail,
        summary_line,
    )

    root = product_root(dir)
    problems = Problems()
    cards = select_cards(root, concept_id, all_, problems)
    load_cad_kernel()
    built, errors = build_concepts(root, cards, render=not no_render)
    errors += [{"id": p.subject, "error": p.message} for p in problems.errors]
    if json_out:
        emit_json({"concepts": [b.to_dict(root) for b in built], "errors": errors})
    else:
        print_problems(problems, root)
        for b in built:
            sc, cid = b.screening, b.card.id
            summary = summary_line(b.card, sc, root)
            tail = escape(status_tail(b.card))
            if sc.verdict == "red":
                console.print(f"[red]✗[/red] {cid} — this direction has problems:")
                for row in sc.failing:
                    console.print(f"    • {escape(row.message)}", soft_wrap=True)
                console.print(f"  {escape(summary)}{tail}", soft_wrap=True)
            else:
                console.print(
                    f"[green]✓[/green] {cid} holds up: {escape(summary)}{tail}", soft_wrap=True
                )
            for row in sc.rules:
                if row.status == "warn":
                    console.print(
                        f"  [yellow]![/yellow] worth a look: {escape(row.message)}", soft_wrap=True
                    )
            if b.picture is not None:
                shots = b.screenshots
                plain = shots is None or shots.method == "zbuffer-fallback"
                tail = " (correctness render — styled picture unavailable)" if plain else ""
                console.print(f"  see {b.rel(root, b.picture)}{tail}", soft_wrap=True)
        for e in errors:
            if not any(p.subject == e["id"] for p in problems.errors):
                err_console.print(f"[red]✗[/red] {escape(e['error'])}", soft_wrap=True)
    if errors:
        raise typer.Exit(code=1)


@concept_app.command("board")
@handle_errors
def board(dir: Path | None = DirOption, json_out: bool = JsonOption) -> None:
    """Write the concept board: every direction side by side (build/concepts/board.html)."""
    from napkin2factory.concepts.board import write_board

    root = product_root(dir)
    result = write_board(root)
    if json_out:
        emit_json(result.to_dict(root))
        return
    console.print(f"[green]✓[/green] {escape(result.line())}", soft_wrap=True)
    for note in result.dropped_notes:
        console.print(f"  [yellow]![/yellow] {escape(note)}", soft_wrap=True)
    console.print(
        "  open it in a browser to compare; choose in conversation or with "
        "`n2f concept promote C-00x`",
        soft_wrap=True,
    )


@concept_app.command("promote")
@handle_errors
def promote(
    concept_id: str = typer.Argument(..., help="Concept id, e.g. C-003."),
    override: bool = typer.Option(
        False,
        "--override",
        help="Promote a direction screening marked red, or overwrite parameters that differ "
        "(needs --reason).",
    ),
    reason: str | None = typer.Option(
        None, "--reason", help="Why (recorded in the decision); required with --override."
    ),
    by: str | None = typer.Option(
        None, "--by", help="Who chose this direction (recorded as a human decision)."
    ),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Make a concept the design direction: parameters, requirements, style and a decision."""
    from napkin2factory.concepts.promote import promote as do_promote

    root = product_root(dir)
    result = do_promote(root, concept_id, override=override, reason=reason, by=by)
    if json_out:
        emit_json(result.to_dict())
        return
    console.print(f"[green]✓[/green] {escape(result.summary())}", soft_wrap=True)
    for a in result.assemblies:  # P10: the structure seeded from the card's modules
        console.print(f"  + {escape(a.file)}", soft_wrap=True, highlight=False)
    for r in result.requirements:
        console.print(f"  + {r.id} {escape(r.title)}", soft_wrap=True, highlight=False)
    if result.suggestion:
        console.print(f"  suggestion: {escape(result.suggestion)}", soft_wrap=True)
    for note in result.notes:
        console.print(f"  [dim]note: {escape(note)}[/dim]", soft_wrap=True)
    if result.snapshot:
        console.print("  snapshot saved")


@concept_app.command("reject")
@handle_errors
def reject(
    concept_id: str = typer.Argument(..., help="Concept id, e.g. C-002."),
    reason: str = typer.Option(..., "--reason", help="Why this direction is set aside."),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Set a concept aside (status: rejected); the card is kept as a record."""
    _warm()
    root = product_root(dir)
    card = concepts_mod.load_card(root, concept_id)
    if concepts_mod.recorded_promotion(card, root):  # a status typed by hand may be undone
        raise GateBlocked(
            f"{card.id} is the chosen direction (promoted), so it cannot be rejected; "
            "changing direction after promotion is a change request"
        )
    at = dt.datetime.now().replace(microsecond=0).isoformat()
    card = concepts_mod.update_card_status(root, card.id, "rejected", {"reason": reason, "at": at})
    if json_out:
        emit_json({"id": card.id, "status": card.status, "decision": card.decision})
    else:
        console.print(f"[yellow]•[/yellow] {card.id} set aside: {escape(reason)}")
        console.print("  the card stays in concepts/ as a record of what was tried")


@concept_app.command("lint")
@handle_errors
def lint(dir: Path | None = DirOption, json_out: bool = JsonOption) -> None:
    """Check the concept cards (light on purpose: warnings never fail)."""
    _warm()
    root = product_root(dir)
    problems = concepts_mod.lint_concepts(root)
    n = len(concepts_mod.card_files(root))
    if json_out:
        emit_json(
            {
                "ok": not problems.errors,
                "cards": n,
                "problems": [p.to_dict() for p in problems.items],
            }
        )
    else:
        print_problems(problems, root)
        if problems.errors:
            console.print(f"[red]{len(problems.errors)} problem(s)[/red] in the concept cards")
        else:
            console.print(
                f"[green]✓[/green] {n} concept card(s) look fine"
                + (f" ({len(problems.warnings)} warning(s))" if problems.warnings else "")
            )
    if problems.errors:
        raise typer.Exit(code=1)
