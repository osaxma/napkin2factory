"""M6: release gates and the diff page, in a temporary tracked copy of the enclosure (D23)."""

from __future__ import annotations

import json
import os
import re
import zipfile
from pathlib import Path

import pytest
from selectolax.lexbor import LexborHTMLParser

from tests.conftest import EXAMPLES, copy_product, is_swiftshader_flake, n2f

os.environ.setdefault("N2F_OFFLINE", "1")
GIT_WORDS = ("fatal:", "git ", "branch", "commit", "merge", "repository", "tag ")


def _run(*args: str, cwd: Path, ok: bool = True):  # type: ignore[no-untyped-def]
    r = n2f(*args, cwd=cwd)
    if ok:
        assert r.returncode == 0, f"{args}: {r.stdout}\n{r.stderr}"
    low = (r.stdout + r.stderr).lower()
    for w in GIT_WORDS:
        assert w not in low, f"git vocabulary {w!r} leaked: {r.stdout}{r.stderr}"
    return r


@pytest.fixture(scope="module")
def released(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Enclosure released as v1.0.0 after an example sign-off (gate-2 B1/B3 behaviours)."""
    root = copy_product(
        EXAMPLES / "enclosure", tmp_path_factory.mktemp("rel") / "enclosure", git=True
    )
    _run("build", "--no-render", cwd=root)
    # release refused: safety requirement not signed
    r = _run("release", "v1.0.0", cwd=root, ok=False)
    assert r.returncode == 3 and "REQ-004" in r.stderr and "sign-off" in r.stderr
    # a hand edit without a save: the refusal names the owner-level verbs (B1)
    (root / "model/intake.md").write_text((root / "model/intake.md").read_text() + "\nnote\n")
    r = _run("release", "v1.0.0", cwd=root, ok=False)
    assert r.returncode == 4 and "n2f snapshot" in r.stderr and "n2f discard" in r.stderr
    r = _run("snapshot", "-m", "intake note", cwd=root)
    assert "saved as snapshot" in r.stdout
    r = _run("snapshot", cwd=root)
    assert "nothing changed" in r.stdout
    # signing off saves automatically (B1) and refreshes the checks (B5)
    r = _run(
        "signoff",
        "REQ-004",
        "--by",
        "Example Reviewer",
        "--statement",
        "Edges checked.",
        "--example",
        cwd=root,
    )
    assert "saved" in r.stdout and "EXAMPLE" in r.stdout
    st = json.loads(_run("status", "--json", cwd=root).stdout)
    assert st["stage"] == "verify", st
    r = _run("check", cwd=root)
    assert "EXAMPLE" in r.stdout
    # an EXAMPLE sign-off does not release a safety requirement (B3)
    r = _run("release", "v1.0.0", "--no-render", cwd=root, ok=False)
    assert r.returncode == 3 and "EXAMPLE" in r.stderr and "allow-example-signoffs" in r.stderr
    r = _run("release", "v1.0.0", "--no-render", "--allow-example-signoffs", "--json", cwd=root)
    out = json.loads(r.stdout)
    assert out["version"] == "v1.0.0" and Path(out["zip"]).is_file()
    from napkin2factory.core.vcs import Vcs

    assert Vcs(root).tags() == ["v1.0.0"]
    return root


def test_release_package_and_site(released: Path) -> None:
    root = released
    zf = zipfile.ZipFile(root / "build/release/enclosure-v1.0.0.zip")
    names = zf.namelist()
    assert any(n.endswith("step/base-revA.step") for n in names)
    assert any(n.endswith("drawings/base-revA.svg") for n in names)
    assert any(n.endswith("drawings/drawings.pdf") for n in names)
    assert any(n.endswith("flat-patterns/base-revA-flat.dxf") for n in names)
    assert any(n.endswith("bom/bom.xlsx") for n in names)
    assert any(n.endswith("manuals/safety.pdf") for n in names)
    assert any(n.endswith("report.html") for n in names)
    site = root / "build/site"
    assert (site / "v1.0.0/index.html").is_file() and (site / "v1.0.0/data/model.json").is_file()
    assert (site / "index.html").is_file() and (site / "versions.html").is_file()
    assert json.loads((site / "versions.json").read_text())["versions"] == ["v1.0.0"]
    changelog = (root / "CHANGELOG.md").read_text()
    assert "Revision v1.0.0" in changelog
    # the released report says so
    assert "Released v1.0.0" in (site / "v1.0.0/index.html").read_text()
    # second release of the same name refused
    r = _run("release", "v1.0.0", cwd=root, ok=False)
    assert r.returncode == 3 and "already exists" in r.stderr


def test_release_refused_when_evidence_changed(released: Path) -> None:
    root = released
    params = root / "model/parameters.yaml"
    text = params.read_text()
    params.write_text(
        text.replace("box-height:        {value: 80,", "box-height:        {value: 85,")
    )
    from napkin2factory.core.vcs import Vcs

    Vcs(root).snapshot("tweak")
    r = _run("release", "v1.0.1", "--no-render", "--allow-example-signoffs", cwd=root, ok=False)
    assert r.returncode == 3 and "REQ-004" in r.stderr and "evidence changed" in r.stderr
    params.write_text(text)
    Vcs(root).snapshot("revert")


def test_release_refused_when_a_check_fails(released: Path) -> None:
    root = released
    req = root / "model/requirements.yaml"
    text = req.read_text()
    req.write_text(text.replace('op: "<=", value: 100 mm', 'op: "<=", value: 50 mm'))
    from napkin2factory.core.vcs import Vcs

    Vcs(root).snapshot("tighten")
    r = _run("release", "v1.0.1", "--no-render", "--allow-example-signoffs", cwd=root, ok=False)
    assert r.returncode == 3 and "REQ-001" in r.stderr
    req.write_text(text)
    Vcs(root).snapshot("revert")


def test_release_requires_project_root(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=False)
    r = _run("release", "v1.0.0", cwd=root, ok=False)
    assert r.returncode == 4 and "n2f init ." in r.stderr
    r = _run("diff", "v1.0.0", "working", cwd=root, ok=False)
    assert r.returncode == 4 and "n2f init ." in r.stderr
    # and the advice works: init on the existing folder sets up tracking (gate-2 B2)
    r = _run("init", ".", cwd=root)
    assert "change tracking set up" in r.stdout
    r = _run("init", ".", cwd=root)
    assert "already has change tracking" in r.stdout
    # the bracket has no safety requirements, so with tracking set up it releases
    r = _run("release", "v1.0.0", "--no-render", cwd=root)
    assert "Revision" in r.stdout and "released" in r.stdout


def test_ecr_then_release_then_diff(released: Path) -> None:
    root = released
    _run(
        "ecr",
        "new",
        "--title",
        "Taller box",
        "--set",
        "param://box-height=100mm",
        "--set",
        "req://REQ-001#verify.value=120 mm",
        cwd=root,
    )
    _run("ecr", "impact", "ECR-001", cwd=root)
    _run("ecr", "approve", "ECR-001", "--by", "Owner", cwd=root)
    _run("ecr", "apply", "ECR-001", cwd=root)
    _run("build", "--no-render", cwd=root)
    r = _run("check", cwd=root, ok=False)
    # REQ-004's example sign-off cites the base, whose evidence changed → needs-human, not fail
    assert r.returncode == 0, r.stdout
    # re-sign (labelled example step)
    _run(
        "signoff",
        "REQ-004",
        "--by",
        "Example Reviewer",
        "--statement",
        "Re-checked after ECR-001.",
        "--example",
        cwd=root,
    )
    _run("ecr", "close", "ECR-001", cwd=root)
    r = _run("release", "v1.1.0", "--no-render", "--allow-example-signoffs", "--json", cwd=root)
    out = json.loads(r.stdout)
    assert out["closed_ecrs"] == ["ECR-001"]
    import yaml

    assert yaml.safe_load((root / "changes/ECR-001.yaml").read_text())["released_in"] == "v1.1.0"
    r = _run("diff", "v1.0.0", "v9.9.9", cwd=root, ok=False)
    assert r.returncode == 3 and "versions.html" in r.stderr
    r = _run("diff", "v1.0.0", "v1.1.0", "--json", cwd=root)
    d = json.loads(r.stdout)
    page = Path(d["page"])
    assert page.is_file() and page.parent.name == "v1.0.0..v1.1.0"
    states = {p["uri"]: p["state"] for p in d["parts"]}
    assert states.get("part://base") == "changed" and "part://lid" not in states
    assert any(
        p["slug"] == "box-height" and p["a"] == "80 mm" and p["b"] == "100 mm" for p in d["params"]
    )
    assert d["totals"]["mass_delta"] > 0
    html = page.read_text(encoding="utf-8")
    tree = LexborHTMLParser(html)
    assert not tree.css("script[src]") and not tree.css('link:not([href^="data:"])')
    assert 'id="overlay-base"' in html and 'class="old"' in html and 'class="new"' in html
    assert "titleblock" not in html.split('id="overlay-base"', 1)[1].split("</figure>", 1)[0]
    assert 'id="glb-a"' in html and 'id="glb-b"' in html
    assert re.search(r"box-height", html)
    versions = json.loads((root / "build/site/versions.json").read_text())
    assert versions["versions"] == ["v1.0.0", "v1.1.0"] and "v1.0.0..v1.1.0" in versions["diffs"]


def test_diff_page_loads_and_highlights(released: Path) -> None:
    pytest.importorskip("playwright")
    from playwright.sync_api import Error, sync_playwright

    page_path = released / "build/site/diff/v1.0.0..v1.1.0/index.html"
    if not page_path.is_file():
        pytest.skip("diff page not built (earlier test failed)")
    try:
        with sync_playwright() as p:
            p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]).close()
    except Error as exc:
        pytest.skip(f"Playwright Chromium unavailable: {exc}")

    def load() -> tuple[list[str], list[str], list[str]]:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]
            )
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.goto(page_path.as_uri())
            viewers = page.evaluate("window.n2fViewerReady.then(v => Object.keys(v))")
            nodes_b = page.evaluate("window.n2fViewers['viewer-b'].nodes()")
            browser.close()
        return errors, viewers, nodes_b

    errors, viewers, nodes_b = load()
    # SwiftShader sometimes fails to validate a shader under load, with an empty info log; the
    # page is fine on the next load. One retry, then the failure stands (B-0024).
    if errors and all(is_swiftshader_flake(e) for e in errors):
        errors, viewers, nodes_b = load()
    assert errors == [], errors
    assert sorted(viewers) == ["viewer-a", "viewer-b"]
    assert "part://base" in nodes_b
