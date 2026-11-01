"""``n2f init``: write a product skeleton and start change tracking (D23)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import typer
from rich.markup import escape

from napkin2factory.cli.common import JsonOption, console, emit_json, handle_errors
from napkin2factory.cli.kernel import kernel_loaded, warm_kernel_in_background
from napkin2factory.core.errors import N2FError
from napkin2factory.core.vcs import Vcs
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip
from napkin2factory.templates import TEMPLATE_NAMES, TEMPLATES_DIR


def slugify(name: str) -> str:
    """``My Lamp!`` → ``my-lamp``."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "product"


NEXT_WARMING = (
    '  next: sketch two directions — `n2f concept new "<title>"` — or go straight to '
    "`n2f build`; then open the folder with your AI client. The CAD kernel is warming up in "
    "the background (one to two minutes the first time on a machine)"
)
NEXT_COLD = (
    '  next: sketch two directions — `n2f concept new "<title>"` — or go straight to '
    "`n2f build` (the first run loads the CAD kernel; allow a couple of minutes); then open "
    "the folder with your AI client"
)


def start_kernel_warmup() -> bool:
    """Warm the CAD kernel in a detached process unless it is already loaded here (B-0016).

    Returns True when a background warm-up was started.
    """
    if kernel_loaded():
        return False
    return warm_kernel_in_background() is not None


STYLE_HEADER = """\
# style.yaml: how the product looks (preset, colours and finishes by part role, shape cues).
# These are the starting defaults. `n2f concept promote` fills it from the chosen concept;
# you may also edit it by hand. Presets: industrial | appliance | lab.
"""


def write_style(dest: Path, preset: str = "industrial") -> Path:
    """Seed ``style.yaml`` with the chosen preset's values under a short header (N7).

    Raises:
        N2FError: ``preset`` is not one of the presets.
    """
    import yaml

    from napkin2factory.core.model import StyleFile
    from napkin2factory.core.model.style import PRESETS

    if preset not in PRESETS:
        raise N2FError(f"unknown style {preset!r}; choose one of {' | '.join(PRESETS)}")
    path = dest / "style.yaml"
    data = StyleFile.model_validate({"preset": preset}).resolved().model_dump(mode="json")
    body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    path.write_text(STYLE_HEADER + body, encoding="utf-8")
    return path


def write_skeleton(
    dest: Path, template: str, product_id: str, name: str, style: str = "industrial"
) -> list[Path]:
    """Copy a template plus the common agent-layer files into ``dest``; return files written.

    A new product also gets ``style.yaml`` (written here, not shipped in ``_common``, which
    is copied onto existing products too).
    """
    from napkin2factory.core.model.style import PRESETS

    if style not in PRESETS:
        raise N2FError(f"unknown style {style!r}; choose one of {' | '.join(PRESETS)}")
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
    write_style(dest, style)
    return sorted(p for p in dest.rglob("*") if p.is_file())


def upgrade_existing(dest: Path, json_out: bool = False) -> None:
    """``n2f init .`` on an existing product: tracking, file updates, missing agent files.

    The upgrade path (S-057, F7): a folder from a newer system stops before anything is
    touched (:class:`~napkin2factory.core.model.migrate.NewerSchema`, a plain message); a
    folder with migrations pending gets a snapshot of how it is, then the migrations, and the
    owner reads what changed in plain words.  Nothing else in the folder changes.
    """
    from napkin2factory.core.model import migrate

    steps = migrate.pending(dest)  # raises NewerSchema before anything is touched
    vcs = Vcs(dest)
    was_tracked = vcs.is_tracked() and vcs.is_repo_root()
    vcs.init()
    before = None
    upgrade = None
    if steps:
        before = vcs.snapshot(f"Before updating the files to format {steps[-1].to_version}")
        upgrade = migrate.apply(dest)
    added = []
    common = TEMPLATES_DIR / "_common"
    for src in sorted(p for p in common.rglob("*") if p.is_file()):
        target = dest / src.relative_to(common)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(src.read_bytes())
            added.append(str(target.relative_to(dest)))
    if upgrade is not None:
        message = f"Update the files to format {upgrade.to_version}"
    else:
        message = "Start change tracking" if not was_tracked else "Add agent files"
    sha = vcs.snapshot(message)
    warming = start_kernel_warmup()
    if json_out:
        emit_json(
            {
                "dir": str(dest),
                "tracking": True,
                "snapshot": sha,
                "added": added,
                "kernel_warmup": warming,
                "updated": None
                if upgrade is None
                else {**upgrade.to_dict(), "snapshot_before": before},
            }
        )
        return
    if upgrade is not None:
        console.print(
            f"[green]✓[/green] brought this product's files up to date (file format "
            f"{upgrade.from_version} → {upgrade.to_version}); a snapshot of how they were was "
            "saved first, so nothing is lost"
        )
        for step in upgrade.steps:
            console.print(f"  {escape(step.title)}")
        for line in upgrade.changes:
            console.print(f"  - {escape(line)}")
        if added:
            console.print(f"  added {len(added)} agent file(s)")
    elif was_tracked and not added:
        console.print("this product folder already has change tracking; nothing to do")
    else:
        console.print(
            f"[green]✓[/green] change tracking set up for {dest}"
            + (f"; added {len(added)} agent file(s)" if added else "")
        )
    if warming:
        console.print("  the CAD kernel is warming up in the background for your next `n2f build`")


@handle_errors
def init(
    directory: Path = typer.Argument(
        ".",
        help="Folder to create (its name becomes the product id); an existing product folder "
        "gets change tracking set up.",
    ),
    template: str = typer.Option("blank", "--template", "-t", help="blank | bracket | enclosure"),
    name: str | None = typer.Option(None, "--name", help="Product display name."),
    style: str = typer.Option(
        "industrial", "--style", help="Starting look for style.yaml: industrial | appliance | lab."
    ),
    no_tracking: bool = typer.Option(
        False, "--no-tracking", help="Skip change tracking setup (tests only)."
    ),
    json_out: bool = JsonOption,
) -> None:
    """Start a new product folder from a template."""
    dest = Path(directory).resolve()
    if (dest / "n2f.yaml").is_file():
        upgrade_existing(dest, json_out)
        return
    product_id = slugify(dest.name)
    display = name or dest.name.replace("-", " ").replace("_", " ").strip().capitalize()
    files = write_skeleton(dest, template, product_id, display, style)
    snapshot = None
    if not no_tracking:
        vcs = Vcs(dest)
        vcs.init()
        snapshot = vcs.snapshot(f"Start of {display}")
    warming = start_kernel_warmup()
    if json_out:
        emit_json(
            {
                "dir": str(dest),
                "product": product_id,
                "template": template,
                "files": len(files),
                "snapshot": snapshot,
                "kernel_warmup": warming,
            }
        )
        return
    console.print(
        f"[green]✓[/green] started [bold]{display}[/bold] in {dest} "
        f"from the {template} template ({len(files)} files)"
    )
    if snapshot:
        console.print("  first snapshot saved")
    console.print(NEXT_WARMING if warming else NEXT_COLD, soft_wrap=True)
