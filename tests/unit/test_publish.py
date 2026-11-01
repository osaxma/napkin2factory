"""Share mode (B-0037): the shared folder from existing pages, and sending it online."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from selectolax.lexbor import LexborHTMLParser

from napkin2factory.cli.publish import web_address
from napkin2factory.core.vcs import PAGES_LINE, Vcs, VcsError
from napkin2factory.report import site
from napkin2factory.report.site import PublishError, plan_publish, write_publish

EXTERNAL = re.compile(r"\b(?:src|href)\s*=\s*['\"]?(?:https?:)?//", re.IGNORECASE)
GIT_WORDS = ("fatal:", "git ", "branch", "commit", "merge", "head", "repository", "push")


def _page(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"<!doctype html><html><body>{body}</body></html>", encoding="utf-8")


def _build(tmp_path: Path, board: bool = True) -> Path:
    """A build folder as `n2f build`, two releases, a trial run and three diffs leave it."""
    b = tmp_path / "build"
    _page(b / "report" / "index.html", "latest work")
    for v in ("v1.0.0", "v1.1.0", "v1.2.0"):  # v1.2.0: `n2f release --dry-run`, not released
        _page(b / "site" / v / "index.html", f"Revision {v}")
        (b / "site" / v / f"widget-{v}.zip").write_bytes(b"PK" + v.encode())
    for d in ("v1.0.0..v1.1.0", "v1.0.0..working"):
        _page(b / "site" / "diff" / d / "index.html", d)
    if board:
        _page(b / "concepts" / "board.html", "board")
    return b


def _links(html: str) -> list[str]:
    tree = LexborHTMLParser(html)
    return [a.attributes.get("href") or "" for a in tree.css("a")]


def test_folder_holds_every_shared_page(tmp_path: Path) -> None:
    b = _build(tmp_path)
    plan = plan_publish(b, "widget", ["v1.0.0", "v1.1.0"], has_concepts=True)
    out = write_publish(b, "Widget", plan)
    pub = Path(out["folder"])
    files = sorted(p.relative_to(pub).as_posix() for p in pub.rglob("*") if p.is_file())
    assert files == [
        ".nojekyll",
        "board/index.html",
        "diff/v1.0.0..v1.1.0/index.html",
        "index.html",
        "latest/index.html",
        "v1.0.0/index.html",
        "v1.0.0/widget-v1.0.0.zip",
        "v1.1.0/index.html",
        "v1.1.0/widget-v1.1.0.zip",
    ]
    html = (pub / "index.html").read_text(encoding="utf-8")
    links = _links(html)
    assert links and all((pub / href).is_file() for href in links), links
    assert not any(h.startswith(("/", "http", "file:")) for h in links)  # relative only
    assert not EXTERNAL.search(html)
    assert "Widget" in html and "licensed engineer" in html
    assert links.index("v1.1.0/index.html") < links.index("v1.0.0/index.html")  # newest first
    notes = " ".join(n["note"] for n in out["notes"])
    assert "v1.2.0 was a trial run" in notes and "v1.0.0 → working" in notes
    assert out["bytes"] == sum(p.stat().st_size for p in pub.rglob("*") if p.is_file())


def test_missing_pages_name_the_command(tmp_path: Path) -> None:
    b = _build(tmp_path, board=False)
    plan = plan_publish(b, "widget", ["v1.0.0", "v1.1.0", "v1.2.0", "v0.9.0"], has_concepts=True)
    commands = {n["command"] for n in plan.notes}
    assert {"n2f diff v1.1.0 v1.2.0", "n2f concept board"} <= commands
    assert any("v0.9.0 has no saved pages" in n["note"] for n in plan.notes)


def test_latest_equal_to_newest_revision_is_shared_once(tmp_path: Path) -> None:
    b = _build(tmp_path)
    (b / "report" / "index.html").write_bytes((b / "site" / "v1.1.0" / "index.html").read_bytes())
    out = write_publish(b, "Widget", plan_publish(b, "widget", ["v1.0.0", "v1.1.0"], False))
    pub = Path(out["folder"])
    assert out["latest"] == "v1.1.0/index.html" and not (pub / "latest").exists()
    assert 'href="v1.1.0/index.html"' in (pub / "index.html").read_text(encoding="utf-8")


def test_since_leaves_out_older_revisions(tmp_path: Path) -> None:
    b = _build(tmp_path)
    plan = plan_publish(b, "widget", ["v1.0.0", "v1.1.0"], False, since="v1.1.0")
    paths = {p.path for p in plan.pages}
    assert "v1.1.0/index.html" in paths and "v1.0.0/index.html" not in paths
    assert not any(p.startswith("diff/") for p in paths)
    with pytest.raises(PublishError, match="released ones are: v1.0.0, v1.1.0"):
        plan_publish(b, "widget", ["v1.0.0", "v1.1.0"], False, since="v3.0.0")


def test_refuses_without_a_report(tmp_path: Path) -> None:
    with pytest.raises(PublishError, match="run `n2f build` first"):
        plan_publish(tmp_path / "build", "widget", [], False)
    assert not (tmp_path / "build" / "publish").exists()


def test_refuses_above_the_size_limit_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    b = _build(tmp_path)
    _page(b / "publish" / "index.html", "the previous shared folder")
    monkeypatch.setattr(site, "MAX_PUBLISH_BYTES", 1000)
    plan = plan_publish(b, "widget", ["v1.0.0", "v1.1.0"], False)
    with pytest.raises(PublishError) as ei:
        write_publish(b, "Widget", plan)
    msg = str(ei.value)
    assert "nothing was written" in msg and "--since" in msg and "MB" in msg
    assert "previous shared folder" in (b / "publish" / "index.html").read_text()


@pytest.mark.parametrize(
    ("online", "address"),
    [
        ("git@github.com:Acme/widget.git", "https://acme.github.io/widget/"),
        ("https://github.com/acme/widget", "https://acme.github.io/widget/"),
        ("ssh://git@github.com/acme/widget.git", "https://acme.github.io/widget/"),
        ("https://github.com/acme/acme.github.io.git", "https://acme.github.io/"),
        ("/srv/copies/widget.git", None),
    ],
)
def test_web_address(online: str, address: str | None) -> None:
    assert web_address(online) == address


# ---- the online copy, against a local bare project as the remote (no network) ----------


def _assert_persona(message: str) -> None:
    low = message.lower()
    for w in GIT_WORDS:
        assert w not in low, f"git vocabulary {w!r} leaked into: {message}"


def _product(tmp_path: Path) -> tuple[Vcs, Path]:
    root = tmp_path / "widget"
    root.mkdir()
    (root / "n2f.yaml").write_text("product: {name: Widget}\n")
    v = Vcs(root)
    v.init()
    v.snapshot("Start")
    v.tag("v1.0.0", "Revision v1.0.0")
    remote = tmp_path / "online.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    return v, remote


def _git(where: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=where, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_no_online_copy(tmp_path: Path) -> None:
    v, _ = _product(tmp_path)
    assert v.online_copy() is None
    assert v.current_line() == "main"


def test_send_online_to_a_bare_copy(tmp_path: Path) -> None:
    v, remote = _product(tmp_path)
    _git(v.root, "remote", "add", "origin", str(remote))
    pages = tmp_path / "pages"
    _page(pages / "index.html", "shared")
    (pages / ".nojekyll").write_bytes(b"")
    sha = v.snapshot_of_folder(pages, "Shared pages")
    assert v.is_clean() and _git(v.root, "branch", "--list") == "* main"  # nothing local moved
    v.send_online("origin", "main", sha)
    assert _git(remote, "rev-parse", "main") == v.head()
    assert _git(remote, "tag", "--list") == "v1.0.0"
    assert _git(remote, "ls-tree", "--name-only", PAGES_LINE).split() == [".nojekyll", "index.html"]
    # A second send replaces the pages line, with no history behind it.
    _page(pages / "index.html", "shared again")
    v.send_online("origin", "main", v.snapshot_of_folder(pages, "Shared pages"))
    assert _git(remote, "rev-list", "--count", PAGES_LINE) == "1"
    assert "shared again" in _git(remote, "show", f"{PAGES_LINE}:index.html")


def test_online_copy_with_newer_snapshots_refuses(tmp_path: Path) -> None:
    v, remote = _product(tmp_path)
    _git(v.root, "remote", "add", "origin", str(remote))
    v.send_online("origin", "main")
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(remote), str(other))
    (other / "note.txt").write_text("from another computer")
    _git(other, "add", "note.txt")
    _git(other, "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-qm", "elsewhere")
    _git(other, "push", "-q", "origin", "main")
    (v.root / "here.txt").write_text("here")
    v.snapshot("here")
    with pytest.raises(VcsError) as ei:
        v.send_online("origin", "main")
    assert ei.value.code == "online-newer" and "nothing was sent" in str(ei.value)
    _assert_persona(str(ei.value))


def test_unreachable_online_copy_refuses(tmp_path: Path) -> None:
    v, _ = _product(tmp_path)
    _git(v.root, "remote", "add", "origin", str(tmp_path / "missing.git"))
    with pytest.raises(VcsError) as ei:
        v.send_online("origin", "main")
    assert ei.value.code == "online-unreachable" and ei.value.detail
    _assert_persona(str(ei.value))
