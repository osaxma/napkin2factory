"""The product's pages: ``build/site/`` (the ``site`` rule) and ``build/publish/`` (share mode).

``site`` copies the latest report to ``build/site/index.html``; ``n2f release`` adds frozen
Revisions under ``build/site/vX.Y.Z/`` and ``n2f diff`` adds change pages under
``build/site/diff/A..B/`` (S-038).

``n2f publish`` (S-094) gathers what already exists into one folder a web host can serve as
it is: an index page, the latest report, every released Revision with its package, every
change page between released Revisions, and the concept board. It never builds anything:
what is missing is reported with the command that makes it. Every page is self-contained
(D13, N10) and every link is relative, so the folder works from disk and online alike.
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from napkin2factory.core.errors import N2FError
from napkin2factory.core.graph.hashing import sha256_file

if TYPE_CHECKING:
    from napkin2factory.core.graph.rules import RunContext, RunResult

PUBLISH_DIR = "publish"
# The same ceiling as one report or board (D13, N10): the whole folder must fit in it.
MAX_PUBLISH_BYTES = 20 * 1024 * 1024
_REVISION = re.compile(r"^v\d+\.\d+\.\d+$")


def build_site(ctx: RunContext) -> RunResult:
    """Copy the latest report to ``build/site/index.html``."""
    from napkin2factory.core.graph.rules import RunResult

    src = ctx.build_dir / "report" / "index.html"
    out = ctx.build_dir / "site" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, out)
    return RunResult(reads=["rule:report"], outputs=[out], output_hash=sha256_file(out))


# ---- share mode: build/publish/ ---------------------------------------------------------


class PublishError(N2FError):
    """The shared pages could not be assembled; the message says what to do."""

    exit_code = 3


@dataclass(frozen=True)
class SharedPage:
    """One file of the shared folder: where it comes from and where it goes."""

    kind: str  # latest | revision | package | change | board
    label: str
    source: Path
    path: str  # relative to the shared folder, with forward slashes

    @property
    def size(self) -> int:
        """Bytes on disk."""
        return self.source.stat().st_size


@dataclass
class PublishPlan:
    """What the shared folder will hold, and what was left out (with the command to fix it)."""

    pages: list[SharedPage] = field(default_factory=list)
    notes: list[dict[str, str]] = field(default_factory=list)
    latest: str = "latest/index.html"  # where the latest report sits in the shared folder

    def note(self, text: str, command: str = "") -> None:
        """Record something missing or left out; ``command`` makes it, when one exists."""
        self.notes.append({"note": text, "command": command})


def _version_key(name: str) -> tuple[int, ...]:
    return tuple(int(x) for x in name[1:].split("."))


def _safe_key(name: str) -> tuple[int, ...]:
    return _version_key(name) if _REVISION.match(name) else (-1,)


def plan_publish(
    build_dir: Path,
    product_id: str,
    released: list[str],
    has_concepts: bool,
    since: str | None = None,
) -> PublishPlan:
    """Decide what goes into ``build/publish/``; refuse when there is no report at all.

    ``released`` are the Revision names change tracking knows about. Frozen Revision folders
    without one are trial runs (``n2f release --dry-run``) and are left out, as are change
    pages that do not compare two shared Revisions and, with ``since``, Revisions older than
    that one. When the latest report is the newest Revision's page, it is shared once.
    """
    report = build_dir / "report" / "index.html"
    if not report.is_file():
        raise PublishError(
            "there is no report to share yet: run `n2f build` first, then publish again"
        )
    if since is not None and since not in released:
        raise PublishError(
            f"{since} is not a released Revision of this product; the released ones are: "
            + (", ".join(sorted(released, key=_safe_key)) or "none yet")
        )
    plan = PublishPlan()
    site = build_dir / "site"
    frozen = {p.name for p in site.glob("v*") if p.is_dir() and (p / "index.html").is_file()} & {
        v for v in released if _REVISION.match(v)
    }
    if since is not None:
        older = {v for v in frozen if _version_key(v) < _version_key(since)}
        if older:
            plan.note(f"{len(older)} Revision(s) older than {since} left out, as asked")
        frozen -= older
    for name in sorted(
        (p.name for p in site.glob("v*") if p.is_dir() and _REVISION.match(p.name)),
        key=_version_key,
    ):
        if name not in released:
            plan.note(f"{name} was a trial run, not a released Revision, so it is left out")
    revisions = sorted(frozen, key=_version_key)
    for v in sorted((v for v in released if _REVISION.match(v)), key=_version_key):
        if since is not None and _version_key(v) < _version_key(since):
            continue
        if v not in frozen:
            plan.note(
                f"Revision {v} has no saved pages on this computer (it was released "
                "elsewhere), so it is left out"
            )
    newest = site / revisions[-1] / "index.html" if revisions else None
    if newest is not None and sha256_file(newest) == sha256_file(report):
        latest_path = f"{revisions[-1]}/index.html"  # the same page: share it once
    else:
        plan.pages.append(SharedPage("latest", "Latest design", report, "latest/index.html"))
        latest_path = "latest/index.html"
    plan.latest = latest_path
    for v in revisions:
        plan.pages.append(SharedPage("revision", v, site / v / "index.html", f"{v}/index.html"))
        package = site / v / f"{product_id}-{v}.zip"
        if package.is_file():
            plan.pages.append(SharedPage("package", v, package, f"{v}/{package.name}"))
    changes = sorted(p.name for p in (site / "diff").glob("*") if (p / "index.html").is_file())
    for name in changes:
        a, _, b = name.partition("..")
        if a in frozen and b in frozen:
            plan.pages.append(
                SharedPage(
                    "change",
                    f"{a} → {b}",
                    site / "diff" / name / "index.html",
                    f"diff/{name}/index.html",
                )
            )
        else:
            plan.note(
                f"the change page {a} → {b} is left out: it does not compare two shared Revisions"
            )
    for a, b in zip(revisions, revisions[1:], strict=False):
        if f"{a}..{b}" not in changes:
            plan.note(f"no change page for {a} → {b} yet", f"n2f diff {a} {b}")
    board = build_dir / "concepts" / "board.html"
    if board.is_file():
        plan.pages.append(SharedPage("board", "Directions explored", board, "board/index.html"))
    elif has_concepts:
        plan.note("the concept board has not been made yet", "n2f concept board")
    return plan


def _mb(size: int) -> str:
    return f"{size / (1024 * 1024):.1f} MB"


def render_index(product_name: str, plan: PublishPlan, made_on: str) -> str:
    """The index page of the shared folder, in the report's look, with relative links only."""
    import jinja2

    from napkin2factory import __version__
    from napkin2factory.report.brand import favicon_link, footer_mark, footer_wordmark

    env = jinja2.Environment(autoescape=True, undefined=jinja2.StrictUndefined)
    packages = {p.label: p for p in plan.pages if p.kind == "package"}
    return env.from_string(_INDEX).render(
        name=product_name,
        latest=plan.latest,
        revisions=[p for p in reversed(plan.pages) if p.kind == "revision"],
        packages=packages,
        changes=[p for p in reversed(plan.pages) if p.kind == "change"],
        board=next((p for p in plan.pages if p.kind == "board"), None),
        made_on=made_on,
        mb=_mb,
        favicon=favicon_link(),
        mark=footer_mark(),
        wordmark=footer_wordmark(),
        version=__version__,
    )


def write_publish(build_dir: Path, product_name: str, plan: PublishPlan) -> dict[str, Any]:
    """Write ``build/publish/`` from ``plan``; refuse, writing nothing, above the size limit."""
    index = render_index(product_name, plan, dt.date.today().isoformat()).encode("utf-8")
    total = len(index) + sum(p.size for p in plan.pages)
    if total > MAX_PUBLISH_BYTES:
        biggest = sorted(plan.pages, key=lambda p: p.size, reverse=True)[:3]
        shown = ", ".join(f"{p.path} ({_mb(p.size)})" for p in biggest)
        raise PublishError(
            f"the shared pages would come to {_mb(total)}, over the {_mb(MAX_PUBLISH_BYTES)} "
            f"they may hold, so nothing was written. The largest are {shown}. Share fewer "
            "Revisions: `n2f publish --since <Revision>` leaves out the ones before it"
        )
    out = build_dir / PUBLISH_DIR
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "index.html").write_bytes(index)
    # Served as plain files: no site generator may rename or drop anything.
    (out / ".nojekyll").write_bytes(b"")
    for page in plan.pages:
        dest = out / page.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(page.source, dest)
    return {
        "folder": str(out),
        "index": str(out / "index.html"),
        "latest": plan.latest,
        "bytes": total,
        "pages": [{"kind": p.kind, "label": p.label, "path": p.path} for p in plan.pages],
        "notes": plan.notes,
    }


_INDEX = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ name }} — shared pages</title>
{{ favicon }}
<style>
:root{--bg:#f7f6f2;--fg:#1d1d1b;--muted:#6b6a66;--line:#d9d7d0;--card:#fff;--accent:#1e8449}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
header{background:#fff;border-bottom:1px solid var(--line);padding:.8rem 1.2rem}
h1{font-size:1.25rem;margin:0}main{max-width:52rem;margin:0 auto;padding:1rem 1.2rem 4rem;display:flex;flex-direction:column;gap:1.1rem}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:1rem 1.2rem}h2{font-size:1.05rem;margin:.1rem 0 .6rem}
ul{margin:0;padding-left:1.2rem}li{margin:.25rem 0}a{color:var(--accent)}.muted{color:var(--muted)}
.big{font-size:1.05rem;font-weight:600}
.disclaimer{background:#fff4e5;border:1px solid #f0c27a;border-radius:8px;padding:.6rem .9rem;font-size:.9rem}
</style>
</head>
<body>
<header><h1>{{ name }}</h1><span class="muted">Shared pages, put together on {{ made_on }}</span></header>
<main>
<div class="disclaimer"><strong>Disclaimer.</strong> This design was produced with an AI system and has not been reviewed by a licensed engineer.</div>
<section id="latest"><h2>Latest design</h2>
<p><a class="big" href="{{ latest }}">Open the latest report</a>{% if latest != 'latest/index.html' %} <span class="muted">(Revision {{ latest.split('/')[0] }})</span>{% endif %} <span class="muted">— 3D view, drawings, parts list with what to tell the manufacturer, and the checks</span></p>
</section>
<section id="revisions"><h2>Released Revisions</h2>
{% if revisions %}<ul>{% for r in revisions %}<li><a href="{{ r.path }}">Revision {{ r.label }}</a>{% if r.label in packages %} · <a href="{{ packages[r.label].path }}" download>download the package</a> <span class="muted">(3D files, drawings, parts list, manuals; {{ mb(packages[r.label].size) }})</span>{% endif %}</li>{% endfor %}</ul>
{% else %}<p class="muted">None released yet.</p>{% endif %}
</section>
<section id="changes"><h2>What changed between Revisions</h2>
{% if changes %}<ul>{% for c in changes %}<li><a href="{{ c.path }}">{{ c.label }}</a></li>{% endfor %}</ul>
{% else %}<p class="muted">No change pages yet.</p>{% endif %}
</section>
{% if board %}<section id="board"><h2>Directions explored</h2>
<p><a href="{{ board.path }}">Open the concept board</a> <span class="muted">— the rough directions side by side, before the design</span></p>
</section>{% endif %}
<footer class="muted" style="font-size:.8rem">{{ mark }}generated by {{ wordmark }} {{ version }}</footer>
</main>
</body>
</html>
"""  # noqa: E501 (one page, kept as it is served)
