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


def start_kernel_warmup(root: Path | None = None) -> bool:
    """Warm the CAD kernel in the background (B-0016); True when a warm-up was started.

    With the engine on (no ``N2F_NO_ENGINE``), the product's engine is started: it loads the
    package and the kernel before it listens, so the first ``n2f build`` after ``init`` may be
    served warm. Otherwise a detached process imports the kernel, unless it is already loaded
    here.
    """
    from napkin2factory.cli import engine

    if root is not None and not engine.engine_disabled():
        return engine.spawn(root) is not None
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


def check_place(region: str | None, units: str | None) -> tuple[str | None, str | None]:
    """Validate ``--region`` and ``--units`` the way ``n2f.yaml`` does; return them cleaned.

    A region code is matched without regard to case (``us`` is ``US``); an unknown one lists
    the known codes, as ``n2f validate`` does (S-236, W7, W8).

    Raises:
        N2FError: the region is not a known code, or the units are not metric or imperial.
    """
    from pydantic import ValidationError

    from napkin2factory.core.model import Manifest

    code = region.strip().upper() if region and region.strip() else None
    try:
        Manifest.model_validate(
            {
                "product": {"id": "x", "name": "x"},
                **({"region": code} if code else {}),
                **({"units": units} if units else {}),
            }
        )
    except ValidationError as exc:
        err = exc.errors()[0]
        field = str(err["loc"][0]) if err["loc"] else "value"
        message = str(err["msg"]).removeprefix("Value error, ")
        if field == "units":
            message = f"unknown units {units!r}; choose metric or imperial"
        raise N2FError(f"--{field}: {message}") from exc
    return code, units or None


def write_skeleton(
    dest: Path,
    template: str,
    product_id: str,
    name: str,
    style: str = "industrial",
    region: str | None = None,
    units: str | None = None,
) -> list[Path]:
    """Copy a template plus the common agent-layer files into ``dest``; return files written.

    A new product also gets ``style.yaml`` (written here, not shipped in ``_common``, which
    is copied onto existing products too). ``region`` and ``units``, when given, are written
    into ``n2f.yaml`` (S-236).
    """
    region, units = check_place(region, units)
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
    # A folder may already hold the owner's own files (a brief, notes): refuse only when a
    # file we write is there, naming it (S-231).
    common = TEMPLATES_DIR / "_common"
    planned = sorted(
        {
            *(p.relative_to(src) for p in src.rglob("*") if p.is_file()),
            *(p.relative_to(common) for p in common.rglob("*") if p.is_file()),
            Path("style.yaml"),
        }
    )
    clashes = [str(rel) for rel in planned if (dest / rel).exists()]
    if clashes:
        raise N2FError(
            f"{dest} already has {', '.join(clashes[:5])}"
            + (f" and {len(clashes) - 5} more" if len(clashes) > 5 else "")
            + ", which `n2f init` would overwrite; choose a new folder or move "
            + ("it" if len(clashes) == 1 else "them")
            + " aside"
        )
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, dirs_exist_ok=True)
    shutil.copytree(TEMPLATES_DIR / "_common", dest, dirs_exist_ok=True)
    manifest = dest / "n2f.yaml"
    data = load_roundtrip(manifest)
    data["product"]["id"] = product_id
    data["product"]["name"] = name
    if region:
        data["region"] = region
    if units:
        data["units"] = units
    dump_roundtrip(manifest, data)
    write_style(dest, style)
    return [dest / rel for rel in planned]


def upgrade_existing(dest: Path, json_out: bool = False) -> None:
    """``n2f init .`` on an existing product: tracking, file updates, missing agent files.

    The upgrade path (S-057, F7): a folder from a newer system stops before anything is
    touched (:class:`~napkin2factory.core.model.migrate.NewerSchema`, a plain message); a
    folder with migrations pending is checked first (a step that cannot be done refuses with
    the folder untouched), gets a snapshot of how it is, then the migrations, and the owner
    reads what changed in plain words.  Nothing else in the folder changes.
    """
    from napkin2factory.core.model import migrate

    steps = migrate.pending(dest)  # raises NewerSchema before anything is touched
    migrate.check(dest)  # a step that cannot be done refuses here, before anything is touched
    vcs = Vcs(dest)
    was_tracked = vcs.is_tracked() and vcs.is_repo_root()
    vcs.init()
    before = None
    upgrade = None
    # The missing agent files go in first, so a change request carried over by an upgrade does
    # not count them as part of its change (S-261).
    added = []
    common = TEMPLATES_DIR / "_common"
    for src in sorted(p for p in common.rglob("*") if p.is_file()):
        target = dest / src.relative_to(common)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(src.read_bytes())
            added.append(str(target.relative_to(dest)))
    if steps:
        before = vcs.snapshot("Before upgrading the format")
        upgrade = migrate.apply(dest)
    if upgrade is not None:
        message = f"Update the files to format {upgrade.to_version}"
    else:
        message = "Start change tracking" if not was_tracked else "Add agent files"
    sha = vcs.snapshot(message)
    warming = start_kernel_warmup(dest)
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
    region: str | None = typer.Option(
        None,
        "--region",
        help="Where it will be built and bought, a region code (US, UK, EU, AU or SA): "
        "costs and electrics are read for it. Written to n2f.yaml; ask the owner.",
    ),
    units: str | None = typer.Option(
        None,
        "--units",
        help="metric | imperial: the units the owner thinks in, for reports and the board "
        "(drawings stay in mm). Written to n2f.yaml; ask the owner.",
    ),
    no_tracking: bool = typer.Option(
        False, "--no-tracking", help="Skip change tracking setup (tests only)."
    ),
    json_out: bool = JsonOption,
) -> None:
    """Start a new product folder from a template."""
    dest = Path(directory).resolve()
    region, units = check_place(region, units)  # before anything is written
    if (dest / "n2f.yaml").is_file():
        if region or units:
            raise N2FError(
                f"{dest} is already a product: set region and units in its n2f.yaml "
                "(`region:` and `units:`), not with `n2f init`"
            )
        upgrade_existing(dest, json_out)
        return
    product_id = slugify(dest.name)
    display = name or dest.name.replace("-", " ").replace("_", " ").strip().capitalize()
    files = write_skeleton(dest, template, product_id, display, style, region, units)
    snapshot = None
    if not no_tracking:
        vcs = Vcs(dest)
        vcs.init()
        snapshot = vcs.snapshot(f"Start of {display}")
    warming = start_kernel_warmup(dest)
    if json_out:
        emit_json(
            {
                "dir": str(dest),
                "product": product_id,
                "template": template,
                "region": region,
                "units": units or "metric",
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
    if not region or not units:
        console.print(
            "  ask the owner where it will be built and bought and which units they think in, "
            "then set `region:` and `units:` in n2f.yaml",
            soft_wrap=True,
        )
    console.print(NEXT_WARMING if warming else NEXT_COLD, soft_wrap=True)
