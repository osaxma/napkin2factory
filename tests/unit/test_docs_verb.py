"""``n2f docs`` and the docs the wheel carries (S-231); ``n2f init`` beside the owner's files."""

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
import zipfile
from pathlib import Path

import pytest

from napkin2factory.cli.docs import TOPICS, docs_dir, read_topic
from napkin2factory.core.errors import N2FError
from tests.conftest import n2f

REPO = Path(__file__).resolve().parents[2]


def test_every_topic_is_a_page_in_the_repo() -> None:
    assert docs_dir() == REPO / "docs"  # a checkout reads its own docs/
    for topic in TOPICS:
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
    assert wheel == {f"docs/{t}.md": f"napkin2factory/_docs/{t}.md" for t in TOPICS}
    # `uv build` makes the wheel from the sdist, so the sdist must hold the pages too.
    assert {f"docs/{t}.md" for t in TOPICS} <= set(targets["sdist"]["include"])


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
    for topic in TOPICS:
        assert f"napkin2factory/_docs/{topic}.md" in names, topic
    title, text = read_topic("kit", root=tmp_path / "unpacked" / "napkin2factory" / "_docs")
    assert title == "Kit of parts" and text.startswith("# Kit of parts")


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
