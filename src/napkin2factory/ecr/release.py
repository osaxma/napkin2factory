"""``n2f release vX.Y.Z`` (D22, D23, M6): gates, Revision tag, ZIP, frozen site version.

Refuses unless the folder is its own tracked project root, the tree has no unsaved
changes, and the gates pass (no failing check, every safety requirement signed).  Then it
marks closed change requests as released, snapshots, tags the Revision, builds the
manufacturer ZIP, and freezes ``build/site/<version>/`` (report plus the data the diff
needs).  ``--dry-run`` does everything except the model edits, the snapshot and the tag;
for a Revision that already exists it re-packages it, but only from that Revision's own
snapshot (what a product's ``release.yml`` does on the Revision's tag in CI).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from napkin2factory.core.errors import GateBlocked, N2FError
from napkin2factory.core.loader import Product, load_product
from napkin2factory.core.vcs import Vcs
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip

VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")


class ReleaseError(N2FError):
    """A release could not be made; the message names the gate."""

    exit_code = 3


def check_version(version: str) -> str:
    """Accept ``vX.Y.Z`` (adding the ``v`` if missing)."""
    v = version if version.startswith("v") else f"v{version}"
    if not VERSION_RE.match(v):
        raise ReleaseError(f"{version!r} is not a Revision name like v1.0.0")
    return v


def export_data(product: Product, build_dir: Path, data_dir: Path) -> None:
    """Copy what ``n2f diff`` needs from a build into ``data_dir``.

    That is drawings, part props, assembly props/instances/GLB, rollups, checks and a
    snapshot of the model's declared values.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "drawings").mkdir(exist_ok=True)
    for svg in (build_dir / "drawings").glob("*.svg"):
        shutil.copyfile(svg, data_dir / "drawings" / svg.name)
    (data_dir / "parts").mkdir(exist_ok=True)
    for pdir in (build_dir / "parts").glob("*"):
        if (pdir / "props.json").is_file():
            shutil.copyfile(pdir / "props.json", data_dir / "parts" / f"{pdir.name}.json")
    (data_dir / "assemblies").mkdir(exist_ok=True)
    for adir in (build_dir / "assemblies").glob("*"):
        for name in ("props.json", "instances.json", "model.glb"):
            if (adir / name).is_file():
                shutil.copyfile(adir / name, data_dir / "assemblies" / f"{adir.name}.{name}")
    for name in ("bom/rollups.json", "checks/checks.json"):
        src = build_dir / name
        if src.is_file():
            shutil.copyfile(src, data_dir / Path(name).name)
    from napkin2factory.core.units import format_quantity

    model = {
        "product": product.manifest.product.model_dump(),
        "parameters": {k: format_quantity(product.parameter_value(k)) for k in product.parameters},
        "parts": {
            p.id: {
                "rev": p.rev,
                "name": p.name,
                "kind": p.kind,
                "cost": format_quantity(p.cost.unit) if p.cost else None,
                "process": p.process,
                "material": p.material.model_dump(mode="json") if p.material else None,
            }
            for p in product.parts.values()
        },
        "assemblies": {
            a.id: {"rev": a.rev, "children": [{"uri": c.uri, "qty": c.qty} for c in a.children]}
            for a in product.assemblies.values()
        },
        "requirements": {
            r.id: {
                "title": r.title,
                "statement": r.statement,
                "value": str(r.verify.value) if r.verify and r.verify.value is not None else None,
            }
            for r in product.requirements.values()
        },
    }
    (data_dir / "model.json").write_text(
        json.dumps(model, indent=2, default=str) + "\n", encoding="utf-8"
    )


def drawings_pdf(build_dir: Path, product: Product, out: Path) -> bool:
    """One PDF with every drawing SVG as a page (Typst embeds SVG natively)."""
    try:
        import typst
    except ImportError:
        return False
    pages = []
    for part in product.parts_with_geometry():
        svg = build_dir / "drawings" / f"{part.id}.svg"
        if svg.is_file():
            pages.append(
                '#page(paper: "a3", flipped: true, margin: 0mm)'
                f'[#image("/{svg.name}", width: 100%)]'
            )
    if not pages:
        return False
    src = '#set page(paper: "a3", flipped: true, margin: 0mm)\n' + "\n".join(pages) + "\n"
    try:
        pdf = typst.compile(src.encode(), root=str(build_dir / "drawings"))
    except Exception as exc:  # the bundle still ships without the PDF bundle
        (out.with_suffix(".error.txt")).write_text(str(exc)[:2000], encoding="utf-8")
        return False
    out.write_bytes(pdf)
    return True


def make_bundle(
    product: Product,
    build_dir: Path,
    version: str,
    out_dir: Path,
    example_ids: list[str] | None = None,
) -> Path:
    """Assemble ``<product>-<version>.zip`` with STEP, drawings, DXFs, BOM, manuals, report.

    ``example_ids``: the safety requirements released on EXAMPLE sign-offs (a demonstration,
    ``--allow-example-signoffs``); the cover says so (gate F, concern 17).
    """
    stage = out_dir / version
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "step").mkdir(parents=True)
    (stage / "drawings").mkdir()
    (stage / "flat-patterns").mkdir()
    (stage / "manuals").mkdir()
    (stage / "bom").mkdir()
    for part in product.parts_with_geometry():
        step = build_dir / "parts" / part.id / "model.step"
        if step.is_file():
            shutil.copyfile(step, stage / "step" / f"{part.id}-rev{part.rev}.step")
        svg = build_dir / "drawings" / f"{part.id}.svg"
        if svg.is_file():
            shutil.copyfile(svg, stage / "drawings" / f"{part.id}-rev{part.rev}.svg")
        dxf = build_dir / "drawings" / f"{part.id}-flat.dxf"
        if dxf.is_file():
            shutil.copyfile(dxf, stage / "flat-patterns" / f"{part.id}-rev{part.rev}-flat.dxf")
    drawings_pdf(build_dir, product, stage / "drawings" / "drawings.pdf")
    for name in ("bom.xlsx", "bom.csv", "rollups.json", "validation.json"):
        src = build_dir / "bom" / name
        if src.is_file():
            shutil.copyfile(src, stage / "bom" / name)
    for doc_id in product.docs:
        pdf = build_dir / "docs" / doc_id / "page.pdf"
        if pdf.is_file():
            shutil.copyfile(pdf, stage / "manuals" / f"{doc_id}.pdf")
        html = build_dir / "docs" / doc_id / "page.html"
        if html.is_file():
            shutil.copyfile(html, stage / "manuals" / f"{doc_id}.html")
    report = build_dir / "report" / "index.html"
    if report.is_file():
        shutil.copyfile(report, stage / "report.html")
    checks = build_dir / "checks" / "checks.json"
    if checks.is_file():
        shutil.copyfile(checks, stage / "checks.json")
    if product.paths.changelog.is_file():
        shutil.copyfile(product.paths.changelog, stage / "CHANGELOG.md")
    lines = scope_lines(product)
    (stage / "README.txt").write_text(
        f"{product.manifest.product.name} — Revision {version}\n\n"
        + "".join(f"{para}\n\n" for para in cover_notes(product, example_ids or []))
        + ("".join(f"Scope: {line}\n" for line in lines) + "\n" if lines else "")
        + "Contents: step/ (3D models), drawings/ (SVG + drawings.pdf), flat-patterns/ (DXF for\n"
        "laser or punch), bom/ (bom.xlsx, bom.csv), manuals/ (PDF + HTML), report.html, "
        "checks.json, release.json.\n\nThis design was produced with an AI system and has not "
        "been reviewed by a licensed engineer.\n",
        encoding="utf-8",
    )
    record = release_record(product, version)
    if example_ids:
        record["example_signoffs"] = list(example_ids)
    (stage / "release.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    zip_path = out_dir / f"{product.id}-{version}.zip"
    zip_stage(stage, zip_path)
    return zip_path


def zip_stage(stage: Path, zip_path: Path) -> None:
    """Write ``zip_path`` from the package folder ``stage`` (paths under its version folder)."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(stage.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(stage.parent))


def _req_words(product: Product, rid: str) -> str:
    """A requirement as the owner reads it: its id with its title (gate F, concern 15)."""
    req = product.requirements.get(rid)
    return f"{rid} ({req.title})" if req is not None and req.title else rid


def cover_notes(product: Product, example_ids: list[str]) -> list[str]:
    """The cover's paragraphs before the scope: a demonstration, and the choices made (F12).

    A Revision released on EXAMPLE sign-offs says so first, naming each requirement, so a
    shop never takes a demonstration for a reviewed design (gate F, concern 17).  Each choice
    decided with ``n2f decide`` is listed with its decision, so the package says why the
    design is the way it is where a check offered two.
    """
    from napkin2factory.core.checks.choices import decided_choices, unapplied

    out: list[str] = []
    # only a pick that holds nothing can be released before it is made (S-139); say so
    pending = {c["decided"]["id"] for c in unapplied(product.paths.build)}
    if example_ids:
        named = "; ".join(_req_words(product, r) for r in example_ids)
        out.append(
            "DEMONSTRATION: this Revision was released with EXAMPLE sign-offs, which are not "
            f"reviews, for: {named}. A qualified person must review and sign each of these "
            "before anything is made from this package."
        )
    picks = []
    for rec in decided_choices(product).values():
        dec = product.decisions.get(rec.decision)
        title = dec.title if dec is not None else rec.option
        later = "; not yet in the design" if rec.decision in pending else ""
        picks.append(f"- {title} ({rec.decision}, chosen by {rec.by}{later})")
    if picks:
        out.append("Choices made:\n" + "\n".join(picks))
    return out


def scope_lines(product: Product) -> list[str]:
    """The package cover's scope lines (F11): one per declared domain, owner words."""
    from napkin2factory.core.checks.stage import scope_entries

    return [e["line"] for e in scope_entries(product)]


def release_record(product: Product, version: str) -> dict[str, Any]:
    """``release.json`` in the package: the Revision, the system that made it, its scope (F11).

    ``scope`` lists every declared domain with its state and decision, so what the Revision
    leaves to a later stage or to someone else is recorded with it, never only in the model;
    ``choices`` lists the picks decided with ``n2f decide`` (each made in the model: a pick
    that is not holds the release, S-139).
    """
    from napkin2factory import __version__
    from napkin2factory.core.checks.choices import decided_choices
    from napkin2factory.core.checks.stage import scope_entries

    return {
        "product": product.id,
        "name": product.manifest.product.name,
        "revision": version,
        "system": __version__,
        "scope": [
            {k: e[k] for k in ("domain", "state", "decision", "note", "stub", "line") if k in e}
            for e in scope_entries(product)
        ],
        # F12: every choice decided with `n2f decide`, as the cover lists it (S-139)
        "choices": [
            {"check": r.check, "decision": r.decision, "option": r.option, "by": r.by}
            for r in decided_choices(product).values()
        ],
    }


def gate_blockers(product: Product) -> list[str]:
    """What stops a release, from the stage computation (checks must have run).

    The Intake, Design and Verify gates' blockers, then every choice that holds the release
    (F12, S-133): an open one, or a decided pick the model does not show yet (S-139).  The
    Released gate's other blockers (no Revision yet, unsaved changes) are what the release
    itself resolves, so only its choices are read here.
    """
    from napkin2factory.core.checks.choices import choice_blockers
    from napkin2factory.core.checks.stage import compute_stage

    rep = compute_stage(product)
    out: list[str] = []
    for g in rep.gates:
        if g.name in ("intake", "design", "verify") and not g.ok:
            out.extend(g.blockers)
    out += [b for b in choice_blockers(product.paths.build).get("released", []) if b not in out]
    return out


def example_signoffs(product: Product) -> list[str]:
    """Safety requirements whose sign-off is flagged ``example: true``."""
    return sorted(
        so.requirement.id
        for so in product.signoffs.values()
        if so.example
        and so.requirement.id in product.requirements
        and product.requirements[so.requirement.id].safety
    )


def release(
    product: Product,
    version: str,
    dry_run: bool = False,
    render: bool = True,
    allow_example_signoffs: bool = False,
) -> dict[str, Any]:
    """Run the release; returns paths and the Revision name."""
    from napkin2factory.core.graph.runner import run_build

    version = check_version(version)
    vcs = Vcs(product.root)
    vcs.require_repo_root()
    existing = version in vcs.tags()
    if existing and not dry_run:
        raise ReleaseError(f"Revision {version} already exists; pick the next version number")
    # A product's release workflow dry-runs the tag it was started by, so the Revision exists:
    # re-package it, but only from its own snapshot (S-095).
    if existing and vcs.revision_snapshot(version) != vcs.head():
        raise ReleaseError(
            f"Revision {version} already exists and the model has changed since; a dry run "
            "re-packages a Revision only from its own snapshot. Pick the next version number."
        )
    if not dry_run:
        vcs.require_clean()
    run_build(product, quiet=True, render=render)
    examples = example_signoffs(product)
    # one refusal with every reason (gate F, concern 14): the gates, the choices, the examples
    blockers = gate_blockers(load_product(product.root))
    owners: list[str] = []  # reasons that are a person's to settle, not checks to fix
    if examples and not allow_example_signoffs:
        owners.append(
            "the safety sign-offs for "
            + "; ".join(_req_words(product, r) for r in examples)
            + " are EXAMPLES, not reviews: a real person signs each with `n2f signoff <REQ> "
            "--by <name> --statement …`, or pass --allow-example-signoffs for a demonstration "
            "release (the package and the report say so)"
        )
    blockers += owners
    if blockers:
        shown = "\n  • ".join(blockers[:8])
        # only choices left: they are the owner's to make, not checks to fix
        from napkin2factory.core.checks.choices import UNAPPLIED, WAITING

        waiting = all(b.startswith((WAITING, UNAPPLIED)) or b in owners for b in blockers)
        head = f"cannot release {version}" + (
            " yet" if waiting else ": the checks are not green yet"
        )
        raise GateBlocked(f"{head}:\n  • {shown}" + ("\n  …" if len(blockers) > 8 else ""))
    build_dir = product.paths.build
    today = dt.date.today().isoformat()
    closed = [e.id for e in product.ecrs.values() if e.status == "closed" and not e.released_in]
    if not dry_run:
        for eid in closed:
            path = product.paths.changes / f"{eid}.yaml"
            data = load_roundtrip(path)
            data["released_in"] = version
            dump_roundtrip(path, data)
        _changelog_release(product, version, closed, today)
        product = load_product(product.root)
        run_build(product, quiet=True, render=render)  # the report shows "released in"
    release_dir = build_dir / "release"
    release_dir.mkdir(parents=True, exist_ok=True)
    shown_examples = examples if allow_example_signoffs else []
    # the package is built before the Revision exists, so a failure leaves no Revision behind
    zip_path = make_bundle(product, build_dir, version, release_dir, shown_examples)
    site = build_dir / "site"
    frozen = site / version
    if frozen.exists():
        shutil.rmtree(frozen)
    frozen.mkdir(parents=True)
    shutil.copyfile(build_dir / "report" / "index.html", frozen / "index.html")
    export_data(product, build_dir, frozen / "data")
    snapshot = None
    if not dry_run:
        snapshot = vcs.snapshot(f"Release {version}")
        vcs.tag(version, f"Revision {version}")
        # the report must say "Released vX.Y.Z": re-render now that the Revision exists, into
        # the frozen site, the build and the package (gate F, blocker 2: the zip held the draft)
        from napkin2factory.report.builder import render_report

        html = render_report(load_product(product.root), build_dir, vcs.commit_date())
        (frozen / "index.html").write_text(html, encoding="utf-8")
        (build_dir / "report" / "index.html").write_text(html, encoding="utf-8")
        stage = release_dir / version
        (stage / "report.html").write_text(html, encoding="utf-8")
        zip_stage(stage, zip_path)
    shutil.copyfile(zip_path, frozen / zip_path.name)
    # re-packaging a released Revision is the Revision itself, not a preview
    write_site_index(product, site, latest=version, dry_run=dry_run and not existing)
    return {
        "version": version,
        "repackaged": existing,
        "zip": str(zip_path),
        "site": str(frozen),
        "snapshot": snapshot,
        "closed_ecrs": closed,
        "dry_run": dry_run,
    }


def _changelog_release(product: Product, version: str, closed: list[str], today: str) -> None:
    path = product.paths.changelog
    text = path.read_text(encoding="utf-8") if path.is_file() else "# Changelog\n"
    header = f"\n## Revision {version} ({today})\n"
    body = "".join(f"- includes {eid}\n" for eid in closed) or "- first release\n"
    # newest first: insert after the title and its intro paragraph, before earlier entries
    lines = text.splitlines(keepends=True)
    i = 1 if lines and lines[0].startswith("# ") else 0
    while i < len(lines) and not lines[i].startswith("#"):
        i += 1
    new = "".join(lines[:i]).rstrip("\n") + "\n" + header + body + "".join(lines[i:])
    path.write_text(new, encoding="utf-8")


def write_site_index(
    product: Product, site: Path, latest: str | None = None, dry_run: bool = False
) -> Path:
    """``build/site/index.html``: the latest report, plus ``versions.json`` and a versions page."""
    site.mkdir(parents=True, exist_ok=True)
    versions = sorted(
        (p.name for p in site.iterdir() if p.is_dir() and VERSION_RE.match(p.name)),
        key=lambda v: tuple(int(x) for x in v[1:].split(".")),
    )
    diffs = sorted(p.name for p in (site / "diff").iterdir()) if (site / "diff").is_dir() else []
    (site / "versions.json").write_text(
        json.dumps(
            {
                "latest": latest or (versions[-1] if versions else None),
                "versions": versions,
                "diffs": diffs,
                "dry_run": dry_run,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report = product.paths.build / "report" / "index.html"
    if report.is_file():
        shutil.copyfile(report, site / "index.html")
    rows = "".join(
        f'<li><a href="{v}/index.html">{v}</a> · '
        f'<a href="{v}/{product.id}-{v}.zip">download package</a></li>'
        for v in reversed(versions)
    )
    drows = "".join(f'<li><a href="diff/{d}/index.html">{d}</a></li>' for d in diffs)
    (site / "versions.html").write_text(
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{product.manifest.product.name} — Revisions</title>"
        "<style>body{font:15px/1.5 -apple-system,Helvetica,Arial,sans-serif;max-width:48rem;"
        "margin:2rem auto;padding:0 1rem}</style></head><body>"
        f"<h1>{product.manifest.product.name}</h1><p><a href='index.html'>Latest report</a></p>"
        f"<h2>Released Revisions</h2><ul>{rows or '<li>none yet</li>'}</ul>"
        f"<h2>Change pages</h2><ul>{drows or '<li>none yet</li>'}</ul>"
        "<p><small>This design was produced with an AI system and has not been reviewed "
        "by a licensed engineer.</small></p></body></html>\n",
        encoding="utf-8",
    )
    return site / "index.html"
