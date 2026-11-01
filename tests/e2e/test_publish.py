"""Share mode end to end (B-0037): two Revisions and a change page of the bracket, shared."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest
from selectolax.lexbor import LexborHTMLParser

from tests.conftest import EXAMPLES, copy_product, n2f

os.environ.setdefault("N2F_OFFLINE", "1")
EXTERNAL = re.compile(r"\b(?:src|href)\s*=\s*['\"]?(?:https?:)?//", re.IGNORECASE)
GIT_WORDS = ("fatal:", "git ", "branch", "commit", "merge", "repository", "push")


def _run(*args: str, cwd: Path, ok: bool = True) -> subprocess.CompletedProcess[str]:
    r = n2f(*args, cwd=cwd)
    if ok:
        assert r.returncode == 0, f"{args}: {r.stdout}\n{r.stderr}"
    low = (r.stdout + r.stderr).lower()
    for w in GIT_WORDS:
        assert w not in low, f"git vocabulary {w!r} leaked: {r.stdout}{r.stderr}"
    return r


@pytest.fixture(scope="module")
def shared(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The bracket released as v1.0.0 and v1.1.0 (a longer leg), with the change page."""
    root = copy_product(EXAMPLES / "bracket", tmp_path_factory.mktemp("pub") / "bracket")
    r = _run("publish", cwd=root, ok=False)  # nothing built yet
    assert r.returncode == 3 and "n2f build" in r.stderr
    assert not (root / "build" / "publish").exists()
    _run("build", "--no-render", cwd=root)
    _run("release", "v1.0.0", "--no-render", cwd=root)
    params = root / "model" / "parameters.yaml"
    text = params.read_text(encoding="utf-8")
    params.write_text(text.replace("{value: 120, unit: mm", "{value: 130, unit: mm"), "utf-8")
    _run("snapshot", "-m", "Longer shelf leg", cwd=root)
    _run("build", "--no-render", cwd=root)
    _run("release", "v1.1.0", "--no-render", cwd=root)
    r = _run("publish", cwd=root)
    assert "n2f diff v1.0.0 v1.1.0" in r.stdout  # the missing change page is named
    _run("diff", "v1.0.0", "v1.1.0", cwd=root)
    return root


def test_folder_contents_and_links(shared: Path) -> None:
    out = json.loads(_run("publish", "--json", cwd=shared).stdout)
    pub = Path(out["folder"])
    assert pub == shared / "build" / "publish" and out["notes"] == [] and out["online"] is None
    files = sorted(p.relative_to(pub).as_posix() for p in pub.rglob("*") if p.is_file())
    assert files == [
        ".nojekyll",
        "diff/v1.0.0..v1.1.0/index.html",
        "index.html",
        "v1.0.0/bracket-v1.0.0.zip",
        "v1.0.0/index.html",
        "v1.1.0/bracket-v1.1.0.zip",
        "v1.1.0/index.html",
    ]  # the latest report is Revision v1.1.0's page, shared once
    assert out["latest"] == "v1.1.0/index.html"
    assert out["bytes"] <= 20 * 1024 * 1024
    index = (pub / "index.html").read_text(encoding="utf-8")
    hrefs = [a.attributes.get("href") or "" for a in LexborHTMLParser(index).css("a")]
    assert set(hrefs) == {f for f in files if f not in (".nojekyll", "index.html")}
    for f in files:
        if f.endswith(".html"):  # every page self-contained: no external reference
            assert not EXTERNAL.search((pub / f).read_text(encoding="utf-8")), f


def test_online_needs_an_online_copy(shared: Path) -> None:
    r = _run("publish", "--online", "--yes", cwd=shared, ok=False)
    assert r.returncode == 4 and "online copy" in r.stderr and "GitHub" in r.stderr


def test_online_sends_to_the_online_copy(shared: Path, tmp_path: Path) -> None:
    remote = tmp_path / "online.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=shared, check=True)
    try:
        out = json.loads(_run("publish", "--online", "--json", cwd=shared).stdout)
        assert out["online"] == {"sent": True, "web_address": None}

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", *args], cwd=remote, capture_output=True, text=True, check=True
            ).stdout

        assert git("tag", "--list").split() == ["v1.0.0", "v1.1.0"]
        assert "Longer shelf leg" in git("log", "--format=%s", "main")
        online = sorted(git("ls-tree", "-r", "--name-only", "gh-pages").split())
        local = Path(out["folder"])
        assert online == sorted(
            p.relative_to(local).as_posix() for p in local.rglob("*") if p.is_file()
        )
        # Unsaved changes are never sent.
        (shared / "model" / "intake.md").write_text("changed\n", encoding="utf-8")
        r = _run("publish", "--online", "--yes", cwd=shared, ok=False)
        assert r.returncode == 4 and "n2f snapshot" in r.stderr
    finally:
        subprocess.run(["git", "checkout", "--", "."], cwd=shared, check=True)
        subprocess.run(["git", "remote", "remove", "origin"], cwd=shared, check=True)
