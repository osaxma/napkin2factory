"""``n2f init``: write a product skeleton and start change tracking (D23)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import typer

from napkin2factory.cli.common import JsonOption, console, emit_json, handle_errors
from napkin2factory.core.errors import N2FError
from napkin2factory.core.vcs import Vcs
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip
from napkin2factory.templates import TEMPLATE_NAMES, TEMPLATES_DIR


def slugify(name: str) -> str:
    """``My Kiln!`` → ``my-kiln``."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "product"


def write_skeleton(dest: Path, template: str, product_id: str, name: str) -> list[Path]:
    """Copy a template plus the common agent-layer files into ``dest``; return files written."""
    if template not in TEMPLATE_NAMES:
        raise N2FError(f"unknown template {template!r}; choose one of {', '.join(TEMPLATE_NAMES)}")
    src = TEMPLATES_DIR / template
    if not src.is_dir():
        raise N2FError(
            f"template {template!r} is not installed (run `make templates` in the system repo)"
        )
    dest.mkdir(parents=True, exist_ok=True)
    if any(dest.iterdir()):
        raise N2FError(f"{dest} is not empty; choose a new folder")
    shutil.copytree(src, dest, dirs_exist_ok=True)
    shutil.copytree(TEMPLATES_DIR / "_common", dest, dirs_exist_ok=True)
    manifest = dest / "n2f.yaml"
    data = load_roundtrip(manifest)
    data["product"]["id"] = product_id
    data["product"]["name"] = name
    dump_roundtrip(manifest, data)
    return sorted(p for p in dest.rglob("*") if p.is_file())


@handle_errors
def init(
    directory: Path = typer.Argument(
        ".",
        help="Folder to create (its name becomes the product id); an existing product folder "
        "gets change tracking set up.",
    ),
    template: str = typer.Option("blank", "--template", "-t", help="blank | bracket | enclosure"),
    name: str | None = typer.Option(None, "--name", help="Product display name."),
    no_tracking: bool = typer.Option(
        False, "--no-tracking", help="Skip change tracking setup (tests only)."
    ),
    json_out: bool = JsonOption,
) -> None:
    """Start a new product folder from a template."""
    dest = Path(directory).resolve()
    if (dest / "n2f.yaml").is_file():
        # an existing product: only set up change tracking (and add missing agent files)
        added = []
        common = TEMPLATES_DIR / "_common"
        for src in sorted(p for p in common.rglob("*") if p.is_file()):
            target = dest / src.relative_to(common)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(src.read_bytes())
                added.append(str(target.relative_to(dest)))
        vcs = Vcs(dest)
        was_tracked = vcs.is_tracked() and vcs.is_repo_root()
        vcs.init()
        sha = vcs.snapshot("Start change tracking" if not was_tracked else "Add agent files")
        if json_out:
            emit_json({"dir": str(dest), "tracking": True, "snapshot": sha, "added": added})
        elif was_tracked and not added:
            console.print("this product folder already has change tracking; nothing to do")
        else:
            console.print(
                f"[green]✓[/green] change tracking set up for {dest}"
                + (f"; added {len(added)} agent file(s)" if added else "")
            )
        return
    product_id = slugify(dest.name)
    display = name or dest.name.replace("-", " ").replace("_", " ").strip().capitalize()
    files = write_skeleton(dest, template, product_id, display)
    snapshot = None
    if not no_tracking:
        vcs = Vcs(dest)
        vcs.init()
        snapshot = vcs.snapshot(f"Start of {display}")
    if json_out:
        emit_json(
            {
                "dir": str(dest),
                "product": product_id,
                "template": template,
                "files": len(files),
                "snapshot": snapshot,
            }
        )
        return
    console.print(
        f"[green]✓[/green] started [bold]{display}[/bold] in {dest} "
        f"from the {template} template ({len(files)} files)"
    )
    if snapshot:
        console.print(f"  first snapshot saved ({snapshot[:10]})")
    console.print(
        "  next: `n2f build` (the first run loads the CAD kernel; allow a couple of minutes), "
        "then open the folder with your AI client and start intake"
    )
