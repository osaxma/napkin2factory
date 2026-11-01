"""``n2f check``, ``n2f status``, ``n2f signoff``."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import typer
from rich.markup import escape
from rich.table import Table

from napkin2factory.cli.common import (
    DirOption,
    JsonOption,
    console,
    emit_json,
    handle_errors,
    product_root,
    warn_if_pin_excludes,
)
from napkin2factory.core.checks.results import example_signoff_words
from napkin2factory.core.errors import CheckFailed, N2FError
from napkin2factory.core.loader import load_product
from napkin2factory.core.uris import display_uri

STATUS_STYLE = {
    "pass": "green",
    "fail": "red",
    "warn": "yellow",
    "skip": "dim",
    "needs-human": "magenta",
    "signed": "cyan",
    "example": "yellow",  # summary-only key: example sign-offs are not reviews
}
#: The order of the non-requirement rows: what blocks first (gate D).
STATUS_ORDER = {"fail": 0, "needs-human": 1, "warn": 2, "skip": 3, "signed": 4, "pass": 5}
OWNER_WORDS = {
    "pass": "OK",
    "fail": "needs attention",
    "warn": "worth a look",
    "skip": "not checked",
    "needs-human": "needs your sign-off",
    "signed": "signed off",
}


def _word(status: str, persona: str) -> str:
    return OWNER_WORDS.get(status, status) if persona == "owner" else status


def _ensure_checks(product, offline: bool = False):  # type: ignore[no-untyped-def]
    from napkin2factory.core.graph.runner import run_build

    run_build(product, target="checks", quiet=True)  # renders are part outputs; keep them
    path = product.paths.build / "checks" / "checks.json"
    return json.loads(path.read_text(encoding="utf-8"))


@handle_errors
def check(
    dir: Path | None = DirOption,
    format: str = typer.Option("table", "--format", "-f", help="table | json | md"),
    all_rows: bool = typer.Option(False, "--all", help="Show passing rule-pack rows too."),
    scope: str | None = typer.Option(
        None,
        "--scope",
        help="Check one module only, e.g. asm://door (written to build/checks/scope/<id>/).",
    ),
    json_out: bool = JsonOption,
) -> None:
    """Check every requirement and rule, and show what needs attention."""
    root = product_root(dir)
    warn_if_pin_excludes(root, json_out or format == "json")
    product = load_product(root)
    if scope is not None:
        from napkin2factory.cli.check_scope import scoped_checks

        data = scoped_checks(product, scope)
    else:
        data = _ensure_checks(product)
    if json_out or format == "json":
        emit_json(data)
    elif format == "md":
        typer.echo(render_md(data))
    else:
        render_table(data, product.operator.persona, all_rows)
    if data["summary"].get("fail", 0):
        raise CheckFailed(f"{data['summary']['fail']} check(s) failed")


def render_table(data: dict, persona: str, all_rows: bool) -> None:  # type: ignore[type-arg]
    """Rich table of the check matrix; the owner reads URIs without their ``scheme://``.

    With more than one module (P12) the second table says which module each row belongs to;
    a module's own checks (``--scope``) say which module they are.
    """
    if data.get("scope"):
        where = escape(display_uri(data["scope"], persona))
        console.print(f"[bold]Checks of one module: {where}[/bold]")
        # gate D: say what these rows count, so they are not read against the report's
        console.print(
            "[dim]its parts' rules, its joints, counts and requirements; the documents and "
            "the sourcing are the whole product's and are left out[/dim]"
        )
    groups = data["matrix"].get("modules", [])
    titles = {g["id"]: g["title"] for g in groups}
    by_module = sum(1 for g in groups if g["id"] is not None) > 1  # two units or more
    t = Table(title="Requirements", show_lines=False)
    t.add_column("id")
    t.add_column("title")
    t.add_column("status")
    t.add_column("what the check found")
    for row in data["matrix"]["requirements"]:
        res = next(r for r in data["results"] if r["id"] == f"req://{row['id']}")
        msg = res["message"]
        if row["status"] == "signed" and "EXAMPLE" in msg:
            word = (
                "signed off (EXAMPLE, not a review)" if persona == "owner" else "signed (EXAMPLE)"
            )
        else:
            word = _word(row["status"], persona)
        t.add_row(
            row["id"] + (" ⚠" if row["safety"] else ""),
            escape(row["title"]),
            f"[{STATUS_STYLE[row['status']]}]{word}[/]",
            escape(msg),
        )
    console.print(t)
    others = [
        r
        for r in data["results"]
        if r["kind"] != "requirement" and (all_rows or r["status"] != "pass")
    ]
    if others:
        t2 = Table(
            title="Rules, interfaces, assemblies, documents, sourcing"
            + ("" if all_rows else " (non-passing)")
        )
        # gate D: what needs attention first, then by module in build order
        order = {g["id"]: i for i, g in enumerate(groups)}
        others.sort(
            key=lambda r: (
                STATUS_ORDER.get(r["status"], len(STATUS_ORDER)),
                order.get(r.get("module"), len(order)) if by_module else 0,
            )
        )
        if by_module:
            t2.add_column("module")
        t2.add_column("check")
        t2.add_column("subject")
        t2.add_column("status")
        t2.add_column("detail")
        for r in others:
            t2.add_row(
                *([escape(titles.get(r.get("module"), ""))] if by_module else []),
                escape(display_uri(r["id"], persona)),
                escape(display_uri(r["subject"], persona)),
                f"[{STATUS_STYLE[r['status']]}]{_word(r['status'], persona)}[/]",
                escape(r["message"]),
            )
        console.print(t2)
    console.print(render_summary(data["summary"], persona))


def render_summary(summary: dict[str, int], persona: str) -> str:
    """The one-line footer: counts per status; example sign-offs are named, never "signed off"."""
    parts = []
    for k, v in summary.items():
        if not v:
            continue
        text = example_signoff_words(v) if k == "example" else f"{v} {_word(k, persona)}"
        parts.append(f"[{STATUS_STYLE.get(k, '')}]{text}[/]")
    return " · ".join(parts)


def render_md(data: dict) -> str:  # type: ignore[type-arg]
    """Markdown check matrix."""
    lines = ["| id | title | status | finding |", "|---|---|---|---|"]
    for row in data["matrix"]["requirements"]:
        lines.append(f"| {row['id']} | {row['title']} | {row['status']} | {row['message']} |")
    lines.append("")
    lines.append("| check | subject | status | detail |")
    lines.append("|---|---|---|---|")
    for r in data["results"]:
        if r["kind"] != "requirement":
            lines.append(f"| {r['id']} | {r['subject']} | {r['status']} | {r['message']} |")
    return "\n".join(lines) + "\n"


@handle_errors
def status(dir: Path | None = DirOption, json_out: bool = JsonOption) -> None:
    """Where the product is (napkin → intake → … → released) and what blocks the next gate."""
    from napkin2factory.core.checks.stage import STAGE_WORDS, compute_stage

    root = product_root(dir)
    warn_if_pin_excludes(root, json_out)
    product = load_product(root)
    rep = compute_stage(product)
    if json_out:
        emit_json(rep.to_dict())
        return
    persona = product.operator.persona
    console.print(
        f"[bold]{escape(product.manifest.product.name)}[/bold] — "
        f"stage: [bold]{rep.current_words}[/bold]"
    )
    for g in rep.gates:
        mark = "[green]✓[/green]" if g.ok else "[yellow]○[/yellow]"
        console.print(f"  {mark} {STAGE_WORDS[g.name]}")
        for row in g.detail.get("rows", []):  # a domain's row under its gate (F4)
            console.print(f"      {escape(row['title'])}: {escape(row['summary'])}")
        if not g.ok:
            # blockers first, then caveats (example sign-offs: the gate is open, not blocked)
            reasons = g.blockers + g.caveats
            for b in reasons[: 6 if persona == "owner" else 20]:
                console.print(f"      [dim]•[/dim] {escape(b)}")
            if len(reasons) > 6 and persona == "owner":
                console.print(
                    f"      [dim]… and {len(reasons) - 6} more "
                    "(`n2f status --json` lists all)[/dim]"
                )
            break
    console.print(f"next: {escape(rep.next_step)}")


@handle_errors
def signoff(
    requirement: str = typer.Argument(..., help="Requirement id, e.g. REQ-003"),
    by: str = typer.Option(..., "--by", help="Who is signing."),
    statement: str = typer.Option(..., "--statement", help="What you reviewed."),
    evidence: list[str] = typer.Option(
        [],
        "--evidence",
        help="URIs you reviewed (default: the requirement's verify target and allocation).",
    ),
    example: bool = typer.Option(
        False,
        "--example",
        help="Mark as an example sign-off (shipped with example products; never a real review).",
    ),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Record that a person reviewed a requirement; it stays valid until the evidence changes."""
    from napkin2factory.core.checks.evidence import evidence_key
    from napkin2factory.core.yamlio import write_yaml

    product = load_product(product_root(dir))
    rid = requirement.replace("req://", "")
    if rid not in product.requirements:
        raise N2FError(
            f"requirement {rid} does not exist; known: {', '.join(sorted(product.requirements))}"
        )
    req = product.requirements[rid]
    data = _ensure_checks(product)
    res = next((r for r in data["results"] if r["id"] == f"req://{rid}"), None)
    if res is not None and res["status"] == "fail":
        raise N2FError(f"{rid} currently fails its check ({res['message']}); fix it before signing")
    uris = list(evidence)
    if not uris:
        if req.verify is not None and req.verify.target is not None:
            uris.append(
                str(req.verify.target.base)
                if req.verify.target.scheme != "calc"
                else str(req.verify.target)
            )
        if isinstance(req.allocation, list):
            uris += [str(a) for a in req.allocation]
    calc_records = data.get("calcs", {})
    keys = {u: evidence_key(product, product.paths.build, u, calc_records) for u in uris}
    missing = [u for u, k in keys.items() if k == "missing"]
    if missing:
        raise N2FError(
            f"cannot bind the sign-off: no evidence yet for {', '.join(missing)} "
            "(build first, or pass --evidence)"
        )
    payload = {
        "requirement": f"req://{rid}",
        "by": by,
        "role": "human",
        "date": dt.date.today().isoformat(),
        "statement": statement,
        "evidence": uris,
        "evidence_keys": keys,
        "example": example,
    }
    path = product.paths.signoffs / f"{rid}.yaml"
    write_yaml(path, payload)
    # refresh the checks so `n2f status` agrees, and save: a sign-off is a record
    _ensure_checks(load_product(product.root))
    from napkin2factory.core.vcs import Vcs

    vcs = Vcs(product.root)
    saved = None
    if vcs.is_tracked() and vcs.is_repo_root():
        saved = vcs.snapshot(f"Sign off {rid}" + (" (EXAMPLE)" if example else ""))
    if json_out:
        emit_json({"written": str(path), "snapshot": saved, **payload})
    else:
        console.print(
            f"[green]✓[/green] sign-off for {rid} recorded and saved"
            + (" [yellow](EXAMPLE SIGN-OFF, NOT A REVIEW)[/yellow]" if example else "")
        )
        console.print("  it stays valid while the evidence it cites is unchanged")
