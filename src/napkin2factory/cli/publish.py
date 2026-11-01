"""``n2f publish``: share mode (B-0037).

Puts the pages that already exist into ``build/publish/``, one folder a web host serves as it
is. ``--online`` also sends the snapshots, the Revisions and those pages to the product's
existing online copy on GitHub, which serves the pages at a web address. The tool never
creates accounts or online projects and never changes their settings.
"""

from __future__ import annotations

import re
from pathlib import Path

import typer
from rich.markup import escape

from napkin2factory.cli.common import (
    DirOption,
    JsonOption,
    console,
    emit_json,
    handle_errors,
    product_root,
)
from napkin2factory.core.vcs import NO_ONLINE_COPY, Vcs, VcsError

_GITHUB = re.compile(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$")


def web_address(online: str) -> str | None:
    """The address GitHub serves the pages at, from the online copy's address (else None)."""
    m = _GITHUB.search(online.strip())
    if not m:
        return None
    owner, name = m.group(1).split("@")[-1], m.group(2)
    if name.lower() == f"{owner.lower()}.github.io":
        return f"https://{owner.lower()}.github.io/"
    return f"https://{owner.lower()}.github.io/{name}/"


@handle_errors
def publish(
    online: bool = typer.Option(
        False,
        "--online",
        help="Also send the snapshots, Revisions and these pages to the product's online copy "
        "on GitHub, which shows the pages at a web address anyone can open.",
    ),
    since: str | None = typer.Option(
        None, "--since", help="Leave out Revisions older than this one, e.g. v1.2.0."
    ),
    yes: bool = typer.Option(False, "--yes", help="Send online without asking."),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Put the report, every Revision, change pages and the board into one folder to share."""
    from napkin2factory.core.concepts import concepts_dir
    from napkin2factory.core.loader import load_product
    from napkin2factory.report.site import plan_publish, write_publish

    if since is not None and not since.startswith("v"):
        since = f"v{since}"
    root = product_root(dir)
    product = load_product(root)
    vcs = Vcs(root)
    tracked = vcs.is_tracked()
    remote = line = None
    if online:
        # Every refusal comes before anything is written or sent.
        vcs.require_repo_root()
        vcs.require_clean()
        if vcs.head() is None:
            raise VcsError("there is no snapshot to send yet: run `n2f snapshot` first")
        remote = vcs.online_copy()
        if remote is None:
            raise VcsError(NO_ONLINE_COPY, code="no-online-copy")
        line = vcs.current_line()
        if line is None:
            raise VcsError(
                "this folder is showing an earlier state, not the current draft, so nothing "
                "was sent; return to the current draft and publish again",
                code="no-draft",
            )
    released = vcs.tags() if tracked else []
    has_concepts = any(concepts_dir(root).glob("C-*.yaml"))
    plan = plan_publish(product.paths.build, product.id, released, has_concepts, since)
    result = write_publish(product.paths.build, product.manifest.product.name, plan)
    result["online"] = None
    if online and remote is not None and line is not None:
        if not yes and not json_out:
            typer.confirm(
                "Send the snapshots, Revisions and these pages online? Anyone with the web "
                "address can open the pages",
                abort=True,
            )
        address = vcs.online_address(remote)
        pages = vcs.snapshot_of_folder(Path(result["folder"]), "Shared pages")
        vcs.send_online(remote, line, pages)
        result["online"] = {"sent": True, "web_address": web_address(address)}
    if json_out:
        emit_json(result)
        return
    console.print(
        f"[green]✓[/green] {len(plan.pages)} page(s) and download(s) ready to share "
        f"({result['bytes'] / (1024 * 1024):.1f} MB)"
    )
    console.print(f"  open: {escape(result['index'])}")
    for n in plan.notes:
        hint = f" — `{n['command']}` makes it" if n["command"] else ""
        console.print(f"  [yellow]•[/yellow] {escape(n['note'])}{escape(hint)}")
    if result["online"]:
        where = result["online"]["web_address"]
        console.print("[green]✓[/green] sent to the online copy")
        if where:
            console.print(f"  web address: {where}")
        console.print(
            "  [dim]First time? The pages appear once GitHub serves them: in the online "
            'project\'s Settings, under Pages, choose "gh-pages" as the source (once).[/dim]'
        )
