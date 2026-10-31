"""``n2f concept new|list|show|build|reject|lint``: the napkin stage's cards (NAPKIN_STAGE §4).

Concepts sit outside the build graph (N1): these verbs need a product folder but never load
the product model, so a half-written model never blocks exploring ideas.  ``build`` runs the
massing and screening in-process (no build graph); ``board`` and ``promote`` arrive in later
milestones.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

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
    reasons = [r.message or r.id for r in card.screening.failing]
    if verdict == "red" and reasons:
        return f"screening: red — this direction has problems: {'; '.join(reasons)}"
    if verdict == "green":
        return "screening: green — this direction holds up"
    return f"screening: {verdict}"


RULE_MARKS = {"pass": "✓", "fail": "✗", "warn": "!", "skip": "·"}


def screening_block(screening: Screening) -> list[str]:
    """The screening as plain lines: computed and estimate numbers labelled, then rules."""
    at = f" ({screening.at.isoformat(sep=' ')})" if screening.at else ""
    lines = [f"screening{at}: {screening.verdict or 'not judged'}"]
    for section, values, what in (
        ("computed", screening.computed, "measured from the massing shapes"),
        ("estimate", screening.estimates, "rough, from the calc kit"),
    ):
        if not values:
            continue
        lines.append(f"  {section} — {what}:")
        width = max(len(k) for k in values)
        for name, lv in values.items():
            lines.append(f"    {name:<{width}}  {lv.value:<22} {lv.label} · {lv.source}")
    if screening.rules:
        lines.append("  rules:")
        for row in screening.rules:
            relied = f" [{', '.join(row.relies_on)}]" if row.relies_on else ""
            lines.append(f"    {RULE_MARKS.get(row.status, '?')} {row.id}{relied}: {row.message}")
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
    for c in ("id", "status", "title", "based on", "verdict"):
        t.add_column(c)
    for r in rows:
        t.add_row(
            str(r["id"]),
            str(r["status"]),
            escape(str(r["title"])),
            r["based_on"] or "",
            r["verdict"] or NO_VERDICT,
        )
    console.print(t)
    print_problems(problems, root)
    if not rows and not problems:
        console.print('  none yet · `n2f concept new "<title>"` starts one')


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
    shown = {k: v for k, v in data.items() if k != "screening"}
    console.print(
        yaml.safe_dump(shown, sort_keys=False, allow_unicode=True, default_flow_style=None),
        markup=False,
        end="",
    )
    if card.screening is not None:
        for line in screening_block(card.screening):
            console.print(line, markup=False, highlight=False, soft_wrap=True)
    if card.status == "rejected":
        reason = (card.decision or {}).get("reason")
        console.print(f"{card.id} is rejected" + (f": {escape(str(reason))}" if reason else ""))
    elif card.status == "promoted":
        console.print(f"{card.id} is the chosen direction (promoted)")
    console.print(escape(screening_line(card)))


@concept_app.command("build")
@handle_errors
def build(
    concept_id: str | None = typer.Argument(None, help="Concept id, e.g. C-002."),
    all_: bool = typer.Option(False, "--all", help="Build every card that is not rejected."),
    no_render: bool = typer.Option(
        False, "--no-render", help="Skip the pictures (silhouettes and styled screenshots)."
    ),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Build the rough shapes of a concept and screen it (red is information, exit 0)."""
    from napkin2factory.cli.kernel import load_cad_kernel
    from napkin2factory.concepts.build import build_concepts, select_cards, summary_line

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
            summary = summary_line(b.card, sc)
            if sc.verdict == "red":
                console.print(f"[red]✗[/red] {cid} — this direction has problems:")
                for row in sc.failing:
                    console.print(f"    • {escape(row.message)}", soft_wrap=True)
                console.print(f"  {escape(summary)}", soft_wrap=True)
            else:
                console.print(f"[green]✓[/green] {cid} holds up: {escape(summary)}", soft_wrap=True)
            for row in sc.rules:
                if row.status == "warn":
                    console.print(
                        f"  [yellow]![/yellow] worth a look: {escape(row.message)}", soft_wrap=True
                    )
            if b.picture is not None:
                console.print(f"  see {b.rel(root, b.picture)}", soft_wrap=True)
        for e in errors:
            if not any(p.subject == e["id"] for p in problems.errors):
                err_console.print(f"[red]✗[/red] {escape(e['error'])}", soft_wrap=True)
    if errors:
        raise typer.Exit(code=1)


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
    if card.status == "promoted":
        raise GateBlocked(
            f"{card.id} is the chosen direction (promoted), so it cannot be rejected; "
            "changing direction after promotion is a change request"
        )
    at = dt.datetime.now().replace(microsecond=0).isoformat()
    card = concepts_mod.update_card_status(root, card.id, "rejected", {"reason": reason, "at": at})
    if json_out:
        emit_json({"id": card.id, "status": card.status, "decision": card.decision})
    else:
        console.print(f"[yellow]•[/yellow] {card.id} rejected: {escape(reason)}")
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
