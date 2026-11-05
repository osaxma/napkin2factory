"""``n2f init`` → ``n2f validate`` → ``n2f lint`` for every template, through the real CLI."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from napkin2factory.templates import TEMPLATE_NAMES, TEMPLATES_DIR
from tests.conftest import n2f

INSTALLED = [t for t in TEMPLATE_NAMES if (TEMPLATES_DIR / t).is_dir()]


@pytest.mark.parametrize("template", INSTALLED)
def test_init_then_validate_and_lint(tmp_path: Path, template: str):
    dest = tmp_path / "my-thing"
    r = n2f("init", str(dest), "--template", template, "--json", process=True)  # the entry point
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["product"] == "my-thing" and payload["snapshot"]
    assert (dest / ".git").is_dir(), "init starts change tracking (D23)"
    assert (dest / "AGENTS.md").is_file() and not (dest / "CLAUDE.md").exists()  # S-076
    assert not (dest / ".claude").exists(), "roles live in roles/, for any client (S-077)"
    for rel in (
        "roles/pm.md",
        "roles/design.md",
        "roles/verifier.md",
        "roles/impact-analyst.md",
        ".github/workflows/build.yml",
    ):
        assert (dest / rel).is_file(), rel
    assert "id: my-thing" in (dest / "n2f.yaml").read_text()
    v = n2f("validate", cwd=dest, process=True)
    assert v.returncode == 0, v.stderr + v.stdout
    lint = n2f("lint", cwd=dest, process=True)
    assert lint.returncode == 0, lint.stderr + lint.stdout
    # vocabulary: user-facing output has no git words
    for out in (r.stdout, r.stderr, v.stdout, v.stderr, lint.stdout, lint.stderr):
        assert "commit" not in out and "branch" not in out, out


def test_init_hint_points_to_build_and_warns_about_the_kernel(tmp_path: Path):
    r = n2f("init", str(tmp_path / "hinted"), "--template", "blank")
    assert r.returncode == 0, r.stderr
    assert "next: sketch two directions — `n2f concept new" in r.stdout, r.stdout
    assert "or go straight to `n2f build`" in r.stdout and "CAD kernel" in r.stdout, r.stdout
    assert "AI client" in r.stdout
    # gate B, B6: no ten-character snapshot id for the owner
    assert re.search(r"first snapshot saved\s*$", r.stdout, re.MULTILINE), r.stdout


def test_init_refuses_to_overwrite_but_keeps_the_owners_files(tmp_path: Path):
    # The owner's brief may already sit in the folder; init refuses only a file it would write.
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "f").write_text("1")
    assert n2f("init", str(tmp_path / "x")).returncode == 0
    assert (tmp_path / "x" / "f").read_text() == "1"
    (tmp_path / "y").mkdir()
    (tmp_path / "y" / "AGENTS.md").write_text("mine")
    r = n2f("init", str(tmp_path / "y"))
    assert r.returncode == 1 and "AGENTS.md" in r.stderr
    assert (tmp_path / "y" / "AGENTS.md").read_text() == "mine"


def test_validate_outside_a_product_is_actionable(tmp_path: Path):
    r = n2f("validate", cwd=tmp_path)
    assert r.returncode == 1
    assert "n2f init" in r.stderr and "fatal" not in r.stderr.lower()


def test_validate_json_reports_problems(tmp_path: Path):
    from tests.conftest import FIXTURES

    r = n2f("validate", "--json", cwd=FIXTURES / "invalid" / "bad-uri-target")
    assert r.returncode == 1
    payload = json.loads(r.stdout)
    assert payload["ok"] is False and payload["problems"][0]["file"]


def test_init_writes_the_region_and_units_it_is_given(tmp_path: Path):
    """S-236: `--region` and `--units` land in n2f.yaml, validated like the file is."""
    dest = tmp_path / "placed"
    r = n2f("init", str(dest), "--region", "us", "--units", "imperial", "--json")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["region"] == "US" and payload["units"] == "imperial"
    manifest = (dest / "n2f.yaml").read_text()
    assert "region: US" in manifest and "units: imperial" in manifest
    assert n2f("validate", cwd=dest).returncode == 0


def test_init_refuses_an_unknown_region_or_units_before_writing_anything(tmp_path: Path):
    for flag, value, word in (
        ("--region", "ZZ", "unknown region"),
        ("--units", "cubits", "metric"),
    ):
        dest = tmp_path / f"bad{value}"
        r = n2f("init", str(dest), flag, value)
        assert r.returncode != 0 and word in r.stdout + r.stderr, (r.stdout, r.stderr)
        assert "known regions: " in r.stdout + r.stderr or flag == "--units"
        assert not dest.exists(), "nothing is written for a bad value"


def test_init_without_them_asks_nothing_but_tells_the_agent_to_ask_the_owner(tmp_path: Path):
    dest = tmp_path / "unplaced"
    r = n2f("init", str(dest))
    assert r.returncode == 0, r.stderr
    assert "ask the owner where it will be built and bought" in r.stdout.replace("\n", " ")
    assert "region:" not in (dest / "n2f.yaml").read_text()
    # both given: no reminder
    done = n2f("init", str(tmp_path / "placed2"), "--region", "UK", "--units", "metric")
    assert "ask the owner" not in done.stdout.replace("\n", " ")


def test_init_flags_are_refused_on_an_existing_product(tmp_path: Path):
    dest = tmp_path / "there"
    assert n2f("init", str(dest)).returncode == 0
    r = n2f("init", str(dest), "--region", "US")
    assert r.returncode != 0 and "already a product" in r.stdout + r.stderr


def test_the_product_files_tell_the_agent_to_ask_for_region_and_units(tmp_path: Path):
    dest = tmp_path / "words"
    assert n2f("init", str(dest)).returncode == 0
    pm = (dest / "roles" / "pm.md").read_text()
    assert "Region and units" in pm and "built and bought" in pm and "imperial" in pm
    agents = (dest / "AGENTS.md").read_text()
    assert "`region:`" in agents and "`units:`" in agents


def test_check_says_the_us_bands_were_read_while_no_region_is_declared(tmp_path: Path):
    from tests.conftest import copy_product

    EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
    work = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", prebuilt=True)
    data = json.loads(n2f("check", "--json", cwd=work).stdout)
    assert "US cost bands" in data["region_note"]
    table = n2f("check", cwd=work).stdout.replace("\n", " ")
    assert table.count("Costs use the US cost bands") == 1
    (work / "n2f.yaml").write_text(
        (work / "n2f.yaml").read_text().rstrip() + "\nregion: US\n", encoding="utf-8"
    )
    again = json.loads(n2f("check", "--json", cwd=work).stdout)
    assert "region_note" not in again
