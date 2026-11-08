"""``n2f docs`` and the docs the wheel carries (S-231); ``n2f init`` beside the owner's files."""

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
import zipfile
from pathlib import Path

import pytest

from napkin2factory.cli.docs import PAGE_TOPICS, TOPICS, docs_dir, read_topic
from napkin2factory.core.errors import N2FError
from tests.conftest import n2f

REPO = Path(__file__).resolve().parents[2]


def test_every_topic_is_a_page_in_the_repo() -> None:
    assert docs_dir() == REPO / "docs"  # a checkout reads its own docs/
    for topic in PAGE_TOPICS:
        assert (REPO / "docs" / f"{topic}.md").is_file(), topic


def test_list_topics_one_line_each() -> None:
    result = n2f("docs")
    assert result.returncode == 0, result.stderr
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    rows = {ln.split()[0]: ln for ln in lines if ln.split()[0] in TOPICS}
    assert set(rows) == set(TOPICS)
    assert "Kit of parts" in rows["kit"]  # the page's first heading
    assert "n2f docs <topic>" in result.stdout


def test_topic_prints_the_page() -> None:
    result = n2f("docs", "kit")
    assert result.returncode == 0, result.stderr
    assert result.stdout == (REPO / "docs" / "kit.md").read_text(encoding="utf-8")


def test_topic_json() -> None:
    result = n2f("docs", "napkin", "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert set(data) == {"topic", "title", "text"}
    assert data["topic"] == "napkin"
    assert data["title"].startswith("The napkin stage")
    assert data["text"].startswith("# ")


def test_list_json() -> None:
    data = json.loads(n2f("docs", "--json").stdout)
    assert [row["topic"] for row in data["topics"]] == list(TOPICS)
    assert all(row["title"] for row in data["topics"])


def test_unknown_topic_lists_the_known_ones() -> None:
    result = n2f("docs", "nope")
    assert result.returncode == 1
    assert "no docs topic 'nope'" in result.stderr + result.stdout
    flat = " ".join((result.stderr + result.stdout).split())
    assert all(topic in flat for topic in TOPICS)
    with pytest.raises(N2FError):
        read_topic("nope")


def test_missing_page_is_a_plain_error(tmp_path: Path) -> None:
    with pytest.raises(N2FError, match="missing from this install"):
        read_topic("kit", root=tmp_path)


def test_build_config_includes_every_topic() -> None:
    config = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    targets = config["tool"]["hatch"]["build"]["targets"]
    wheel = targets["wheel"]["force-include"]
    assert wheel == {f"docs/{t}.md": f"napkin2factory/_docs/{t}.md" for t in PAGE_TOPICS}
    # `uv build` makes the wheel from the sdist, so the sdist must hold the pages too.
    assert {f"docs/{t}.md" for t in PAGE_TOPICS} <= set(targets["sdist"]["include"])


def test_wheel_carries_the_docs(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not installed; the build configuration is checked above")
    out = tmp_path / "dist"
    build = subprocess.run(
        [uv, "build", "--out-dir", str(out)], cwd=REPO, capture_output=True, text=True
    )
    assert build.returncode == 0, build.stderr
    (wheel,) = out.glob("*.whl")
    with zipfile.ZipFile(wheel) as z:
        names = set(z.namelist())
        z.extractall(tmp_path / "unpacked")
    for topic in PAGE_TOPICS:
        assert f"napkin2factory/_docs/{topic}.md" in names, topic
    title, text = read_topic("kit", root=tmp_path / "unpacked" / "napkin2factory" / "_docs")
    assert title == "Kit of parts" and text.startswith("# Kit of parts")


# materials topic (B-0318) -----------------------------------------------------------------


def test_materials_prints_one_line_per_row_without_sources() -> None:
    from napkin2factory.calckit import load_table

    rows = load_table("materials")
    result = n2f("docs", "materials")
    assert result.returncode == 0, result.stderr
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == len(rows)

    for r, line in zip(rows, lines, strict=True):
        assert r["name"] in line
        for kw in r.get("keywords", []):
            assert str(kw) in line
        assert f"{r['density']} kg/m³" in line
        if r.get("youngs_modulus") is not None:
            gpa = float(r["youngs_modulus"]) / 1e9
            assert f"{gpa:g} GPa" in line
        else:
            assert "not on file" in line
        if r.get("yield_strength") is not None:
            mpa = float(r["yield_strength"]) / 1e6
            assert f"{mpa:g} MPa" in line
        else:
            assert "not on file" in line
        pclass = r.get("process_class") or "no process class"
        assert pclass in line
        if r.get("verify"):
            assert "[verify]" in line
        # No sources in any line
        assert "source" not in line.lower()
        if r.get("source"):
            assert r["source"] not in line


def test_materials_json_gives_rows_as_objects() -> None:
    from napkin2factory.calckit import load_table

    rows = load_table("materials")
    result = n2f("docs", "materials", "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["topic"] == "materials"
    assert "Every material a card may name" in data["title"]
    objects = data["materials"]
    assert len(objects) == len(rows)

    # Each object has fields without sources
    for obj in objects:
        assert "name" in obj
        assert "keywords" in obj
        assert "density" in obj
        assert "process_class" in obj
        assert "verify" in obj
        assert "source" not in obj

    # mild steel
    ms = next(o for o in objects if o["name"] == "mild steel")
    assert ms["density"] == 7850
    assert ms["youngs_modulus"] == 200.0e9
    assert ms["yield_strength"] == 250.0e6
    assert ms["process_class"] is None
    assert ms["verify"] is True

    # K-23
    k23 = next(o for o in objects if o["name"] == "K-23 insulating firebrick")
    assert k23["youngs_modulus"] is None
    assert k23["yield_strength"] is None
    assert k23["process_class"] == "cut-block"

    # n2f docs (no topic) lists materials
    no_topic = json.loads(n2f("docs", "--json").stdout)
    assert "materials" in [t["topic"] for t in no_topic["topics"]]


def test_materials_name_argument_returns_one_row_whole() -> None:
    # 1. Plain text with name argument
    res = n2f("docs", "materials", "mild-steel")
    assert res.returncode == 0, res.stderr
    assert "name: mild steel" in res.stdout
    assert "density: 7850" in res.stdout
    assert "source:" in res.stdout
    assert "carbon steel" in res.stdout

    # 2. Quoted name with spaces
    res_sp = n2f("docs", "materials", "mild steel")
    assert res_sp.returncode == 0, res_sp.stderr
    assert "name: mild steel" in res_sp.stdout

    # 3. Via --section option
    res_opt = n2f("docs", "materials", "--section", "mild steel")
    assert res_opt.returncode == 0, res_opt.stderr
    assert "name: mild steel" in res_opt.stdout

    # 4. JSON with name argument
    res_json = n2f("docs", "materials", "mild-steel", "--json")
    assert res_json.returncode == 0, res_json.stderr
    d = json.loads(res_json.stdout)
    assert d["topic"] == "materials"
    assert d["name"] == "mild steel"
    assert d["density"] == 7850
    assert "carbon steel" in d["source"]
    assert d["material"]["name"] == "mild steel"

    # 5. Unknown name says which names exist
    res_err = n2f("docs", "materials", "unobtainium")
    assert res_err.returncode != 0
    msg = res_err.stderr + res_err.stdout
    assert "no material 'unobtainium'" in msg
    assert "mild steel" in msg
    assert "stainless-316" in msg


def test_materials_stays_under_page_limit() -> None:
    from napkin2factory.cli.docs import materials_topic_text
    from napkin2factory.mcp.combined import PAGE_LIMIT

    text = materials_topic_text()
    assert len(text) <= PAGE_LIMIT, f"length {len(text)} exceeds PAGE_LIMIT {PAGE_LIMIT}"


# n2f init beside the owner's own files (S-231) ---------------------------------------------


def test_init_keeps_the_owners_files(tmp_path: Path) -> None:
    folder = tmp_path / "lamp"
    folder.mkdir()
    (folder / "SPEC.md").write_text("my brief\n", encoding="utf-8")
    (folder / "notes").mkdir()
    (folder / "notes" / "a.txt").write_text("x\n", encoding="utf-8")
    result = n2f("init", str(folder), "--no-tracking")
    assert result.returncode == 0, result.stderr
    assert (folder / "SPEC.md").read_text(encoding="utf-8") == "my brief\n"
    assert (folder / "notes" / "a.txt").is_file()
    assert (folder / "n2f.yaml").is_file() and (folder / "AGENTS.md").is_file()


def test_init_refuses_only_a_file_it_would_overwrite(tmp_path: Path) -> None:
    folder = tmp_path / "lamp"
    folder.mkdir()
    (folder / "AGENTS.md").write_text("mine\n", encoding="utf-8")
    (folder / "SPEC.md").write_text("my brief\n", encoding="utf-8")
    result = n2f("init", str(folder), "--no-tracking")
    assert result.returncode != 0
    assert "AGENTS.md" in result.stderr + result.stdout
    assert "SPEC.md" not in result.stderr + result.stdout
    assert (folder / "AGENTS.md").read_text(encoding="utf-8") == "mine\n"
    assert not (folder / "n2f.yaml").exists()  # nothing was written
