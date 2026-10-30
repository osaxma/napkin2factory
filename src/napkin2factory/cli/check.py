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
)
from napkin2factory.core.errors import CheckFailed, N2FError
from napkin2factory.core.loader import load_product

STATUS_STYLE = {
    "pass": "green",
    "fail": "red",
    "warn": "yellow",
    "skip": "dim",
    "needs-human": "magenta",
    "signed": "cyan",
}


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
    json_out: bool = JsonOption,
) -> None:
    """Verify every requirement and rule; exit 2 if anything fails."""
    product = load_product(product_root(dir))
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
    """Rich table of the check matrix."""
    t = Table(title="Requirements", show_lines=False)
    t.add_column("id")
    t.add_column("title")
    t.add_column("status")
    t.add_column("what the check found")
    for row in data["matrix"]["requirements"]:
        res = next(r for r in data["results"] if r["id"] == f"req://{row['id']}")
        msg = res["persona_message"] if persona == "owner" else res["message"]
        t.add_row(
            row["id"] + (" ⚠" if row["safety"] else ""),
            escape(row["title"]),
            f"[{STATUS_STYLE[row['status']]}]{row['status']}[/]",
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
        t2.add_column("check")
        t2.add_column("subject")
        t2.add_column("status")
        t2.add_column("detail")
        for r in others:
            t2.add_row(
                escape(r["id"]),
                escape(r["subject"]),
                f"[{STATUS_STYLE[r['status']]}]{r['status']}[/]",
                escape(r["persona_message"] if persona == "owner" else r["message"]),
            )
        console.print(t2)
    s = data["summary"]
    console.print(" · ".join(f"[{STATUS_STYLE[k]}]{v} {k}[/]" for k, v in s.items() if v))


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
    """Where the product is (intake → design → verify → released) and what blocks the next gate."""
    from napkin2factory.core.checks.stage import compute_stage

    product = load_product(product_root(dir))
    rep = compute_stage(product)
    if json_out:
        emit_json(rep.to_dict())
        return
    persona = product.operator.persona
    names = {"intake": "Intake", "design": "Design", "verify": "Verify", "released": "Released"}
    console.print(
        f"[bold]{escape(product.manifest.product.name)}[/bold] — stage: "
        f"[bold]{names[rep.stage]}[/bold]"
    )
    for g in rep.gates:
        mark = "[green]✓[/green]" if g.ok else "[yellow]○[/yellow]"
        console.print(f"  {mark} {names[g.name]}")
        if not g.ok:
            for b in g.blockers[: 6 if persona == "owner" else 20]:
                console.print(f"      [dim]•[/dim] {escape(b)}")
            if len(g.blockers) > 6 and persona == "owner":
                console.print(
                    f"      [dim]… and {len(g.blockers) - 6} more "
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
    """Record a human sign-off for a requirement, bound to the current evidence (D25)."""
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
    if json_out:
        emit_json({"written": str(path), **payload})
    else:
        console.print(
            f"[green]✓[/green] sign-off for {rid} recorded in {path.relative_to(product.root)}"
            + (" [yellow](EXAMPLE)[/yellow]" if example else "")
        )
        console.print(
            "  it stays valid while the evidence it cites is unchanged; "
            "`n2f check` shows it as signed"
        )
