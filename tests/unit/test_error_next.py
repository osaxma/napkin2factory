"""Actionable errors under --json for unknown ids, missing files, and bad values (B-0310)."""

from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import EXAMPLES, copy_product, n2f

GENERIC_FALLBACK = "run `n2f --help`"


def test_unknown_part_gives_status_next(tmp_path: Path) -> None:
    """An unknown part id directs the agent to `n2f status`."""
    prod = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=True)
    res = n2f("build", "-p", "nosuch-part", "--json", cwd=prod)
    data = json.loads(res.stdout)
    assert data["next"] != GENERIC_FALLBACK
    assert data["next"] == "n2f status"


def test_unknown_assembly_gives_status_next(tmp_path: Path) -> None:
    """An unknown assembly id directs the agent to `n2f status`."""
    prod = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=True)
    res = n2f("build", "--asm", "nosuch-asm", "--json", cwd=prod)
    data = json.loads(res.stdout)
    assert data["next"] != GENERIC_FALLBACK
    assert data["next"] == "n2f status"


def test_unknown_requirement_gives_status_next(tmp_path: Path) -> None:
    """An unknown requirement id directs the agent to `n2f status`."""
    prod = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=True)
    res = n2f(
        "signoff",
        "req://NONEXISTENT",
        "--by",
        "tester",
        "--statement",
        "verified manually",
        "--json",
        cwd=prod,
    )
    data = json.loads(res.stdout)
    assert data["next"] != GENERIC_FALLBACK
    assert data["next"] == "n2f status"


def test_unknown_docs_topic_gives_docs_next() -> None:
    """An unknown docs topic directs the agent to `n2f docs`."""
    res = n2f("docs", "nosuch-topic", "--json")
    data = json.loads(res.stdout)
    assert data["next"] != GENERIC_FALLBACK
    assert data["next"] == "n2f docs"


def test_unknown_change_request_gives_ecr_list_next(tmp_path: Path) -> None:
    """An unknown change request directs the agent to `n2f ecr list`."""
    prod = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=True)
    res = n2f("impact", "--ecr", "ECR-999", "--json", cwd=prod)
    data = json.loads(res.stdout)
    assert data["next"] != GENERIC_FALLBACK
    assert data["next"] == "n2f ecr list"


def test_unknown_concept_card_gives_concept_list_next(tmp_path: Path) -> None:
    """An unknown concept card directs the agent to `n2f concept list`."""
    prod = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=True)
    res = n2f("concept", "show", "C-999", "--json", cwd=prod)
    data = json.loads(res.stdout)
    assert data["next"] != GENERIC_FALLBACK
    assert data["next"] == "n2f concept list"


def test_unknown_template_gives_init_help_next(tmp_path: Path) -> None:
    """An unknown template directs the agent to `n2f init --help`."""
    dest = tmp_path / "new_prod"
    res = n2f("init", "--template", "nosuch-template", str(dest), "--json")
    data = json.loads(res.stdout)
    assert data["next"] != GENERIC_FALLBACK
    assert data["next"] == "n2f init --help"


def test_unknown_checkpoint_gives_checkpoints_next(tmp_path: Path) -> None:
    """An unknown checkpoint directs the agent to `n2f checkpoints`."""
    prod = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=True)
    res = n2f("rollback", "999", "--json", cwd=prod)
    data = json.loads(res.stdout)
    assert data["next"] != GENERIC_FALLBACK
    assert data["next"] == "n2f checkpoints"


def test_unknown_check_gives_status_next(tmp_path: Path) -> None:
    """An unknown check in decide directs the agent to `n2f status`."""
    prod = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=True)
    res = n2f("decide", "nosuch-check", "--pick", "1", "--by", "tester", "--json", cwd=prod)
    data = json.loads(res.stdout)
    assert data["next"] != GENERIC_FALLBACK
    assert data["next"] == "n2f status"


def test_missing_manifest_gives_init_next(tmp_path: Path) -> None:
    """A missing n2f.yaml directs the agent to `n2f init <dir>`."""
    empty = tmp_path / "empty"
    empty.mkdir()
    res = n2f("status", "--json", cwd=empty)
    data = json.loads(res.stdout)
    assert data["next"] != GENERIC_FALLBACK
    assert "n2f init" in data["next"]


def test_missing_evidence_gives_build_next(tmp_path: Path) -> None:
    """Missing evidence in signoff directs the agent to `n2f build`."""
    prod = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=True)
    res = n2f(
        "signoff",
        "REQ-001",
        "--evidence",
        "drawing://bracket",
        "--by",
        "tester",
        "--statement",
        "ok",
        "--json",
        cwd=prod,
    )
    data = json.loads(res.stdout)
    assert data["next"] != GENERIC_FALLBACK
    assert data["next"] == "n2f build"


def test_bad_value_init_style_gives_choices_next(tmp_path: Path) -> None:
    """A bad style preset lists the allowed values in next, read from PRESETS."""
    from napkin2factory.core.model.style import PRESETS

    dest = tmp_path / "bad_style_prod"
    res = n2f("init", "--style", "nosuch-style", str(dest), "--json")
    data = json.loads(res.stdout)
    assert data["next"] != GENERIC_FALLBACK
    assert data["next"] == f"choose one of: {', '.join(PRESETS)}"


def test_bad_value_init_units_gives_choices_next(tmp_path: Path) -> None:
    """A bad units option lists the allowed values (metric, imperial) in next."""
    dest = tmp_path / "bad_units_prod"
    res = n2f("init", "--units", "cubits", str(dest), "--json")
    data = json.loads(res.stdout)
    assert data["next"] != GENERIC_FALLBACK
    assert data["next"] == "choose one of: metric, imperial"


def test_dir_flag_preserved_in_next(tmp_path: Path) -> None:
    """When --dir is used, the next command includes --dir <folder>."""
    prod = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=True)
    res = n2f("build", "--dir", str(prod), "-p", "nosuch-part", "--json")
    data = json.loads(res.stdout)
    assert data["next"] != GENERIC_FALLBACK
    assert data["next"] == f"n2f status --dir {prod}"
