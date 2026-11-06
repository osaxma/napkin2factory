"""Schema 2 and its migration of change requests (v0.8 R8, S-261).

``tests/fixtures/schema/v1`` is a v1 product holding a change request in each v1 state:

* ECR-001 a draft with a parametric edit,
* ECR-002 a draft design request with a patch file,
* ECR-003 in ``impact`` (an impact report stored),
* ECR-004 ``approved``,
* ECR-005 ``applied`` (its edit is already in the model),
* ECR-006 ``closed``,
* ECR-007 ``rejected``.

``n2f init .`` upgrades it; the lowest open id stays open, the others are set aside.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from napkin2factory.cli import init as init_mod
from napkin2factory.cli.app import app
from napkin2factory.ecr.checkpointing import APPROVAL_HASH_EXCLUDE
from napkin2factory.core import checkpoints
from napkin2factory.core.loader import load_product
from napkin2factory.core.model import migrate
from napkin2factory.core.vcs import Vcs
from tests.conftest import copy_product, n2f
from tests.unit.test_migrate import FIXTURES, _files

V1 = FIXTURES / "v1"


@pytest.fixture(autouse=True)
def _no_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(init_mod, "start_kernel_warmup", lambda: False)


def _init(root: Path, *extra: str) -> Any:
    return CliRunner().invoke(app, ["init", str(root), *extra])


def _upgrade(root: Path) -> dict[str, Any]:
    """Upgrade through the CLI; the ``updated`` block of ``--json``."""
    result = _init(root, "--json")
    assert result.exit_code == 0, result.output
    updated: dict[str, Any] = json.loads(result.output)["updated"]
    return updated


def _ecr(root: Path, number: int) -> dict[str, Any]:
    out: dict[str, Any] = yaml.safe_load((root / f"changes/ECR-{number:03d}.yaml").read_text())
    return out


def _fixture_copy(tmp_path: Path, keep: tuple[int, ...] | None = None) -> Path:
    """A tracked copy of the v1 fixture, holding only the change requests numbered ``keep``."""
    root = copy_product(V1, tmp_path / "v1", git=False)
    if keep is not None:
        for path in (root / "changes").glob("ECR-*.yaml"):
            if int(path.stem.split("-")[1]) not in keep:
                path.unlink()
        if 2 not in keep:
            (root / "changes/ECR-002.patch").unlink()
    vcs = Vcs(root)
    vcs.init()
    vcs.snapshot("Start")
    return root


def _value(text: str, slug: str) -> str:
    """The ``value:`` written on a parameter's line in ``parameters.yaml``."""
    found = re.search(rf"^\s*{re.escape(slug)}:\s*\{{value:\s*([^,]+),", text, re.MULTILINE)
    assert found, slug
    return found.group(1)


def _words(text: str) -> str:
    return " ".join(text.split())


@pytest.fixture(scope="module")
def upgraded(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, dict[str, Any], dict[str, str]]:
    """The whole fixture upgraded once: (folder, the init report, its files before)."""
    root = copy_product(V1, tmp_path_factory.mktemp("v1") / "v1", git=True)
    before = _files(root)
    updated = _upgrade(root)
    return root, updated, before


def test_each_state_is_mapped(upgraded: tuple[Path, dict[str, Any], dict[str, str]]) -> None:
    root, updated, before = upgraded
    assert (updated["from"], updated["to"]) == (1, 2) and migrate.schema_of(root) == 2
    # the lowest open id stays open: a draft with the edit applied and where it started
    live = _ecr(root, 1)
    assert live["status"] == "draft" and live["baseline"]["checkpoint"]
    for gone in ("patch", "impact", "approval", "applied"):
        assert gone not in live
    assert _value((root / "model/parameters.yaml").read_text(), "shelf-load") == "12"
    # every other unfinished request is set aside with its edit kept
    for number in (2, 3, 4, 5):
        aside = _ecr(root, number)
        assert aside["status"] == "aborted", number
        assert aside["aborted_reason"].startswith(
            "set aside when upgrading: one change request is open at a time. "
        )
        if number != 5:
            assert aside["aborted_reason"].endswith("start it again with `n2f ecr start`.")
        for gone in ("patch", "impact", "approval", "applied"):
            assert gone not in aside, (number, gone)
    assert "changes/ECR-002.patch" in _ecr(root, 2)["aborted_reason"]
    assert (root / "changes/ECR-002.patch").read_text() == (
        V1 / "changes/ECR-002.patch"
    ).read_text()
    assert "the edits listed above" in _ecr(root, 3)["aborted_reason"]
    assert "already part of the model" in _ecr(root, 5)["aborted_reason"]
    # finished requests are untouched, byte for byte
    for number in (6, 7):
        name = f"changes/ECR-{number:03d}.yaml"
        assert (root / name).read_text() == before[name]
    assert _ecr(root, 7)["rejected_reason"]
    # exactly one is open
    statuses = {n: _ecr(root, n)["status"] for n in range(1, 8)}
    assert [n for n, s in statuses.items() if s in ("draft", "approved")] == [1]
    # the model loads as schema 2
    product = load_product(root)
    assert product.ecrs["ECR-001"].baseline is not None


def test_the_report_is_in_plain_words(
    upgraded: tuple[Path, dict[str, Any], dict[str, str]],
) -> None:
    root, updated, _ = upgraded
    changes = updated["changes"]
    text = _words("\n".join(changes))
    assert any(
        c.startswith("ECR-001 (Carry a heavier shelf): stays open") and "12 kg" in c
        for c in changes
    )
    for number, title in (
        (2, "Add a levelling step to the installation page"),
        (3, "Wider holes for M10 anchors"),
        (4, "Longer horizontal leg"),
        (5, "Holes a little further from the leg ends"),
    ):
        assert any(c.startswith(f"ECR-00{number} ({title}): set aside") for c in changes), number
    assert "one change request is open at a time" in text
    assert "ECR-002 (Add a levelling step to the installation page): set aside" in text
    assert "its patch stays in changes/ECR-002.patch; start it again with `n2f ecr start`" in text
    assert "so there is nothing to start again" in text  # ECR-005 was applied: its edit is in
    assert "2 finished change request(s) kept as they were" in text
    assert "`n2f ecr abort ECR-001`" in text and "`n2f rollback #" in text
    for word in ("commit", "git ", "branch", "baseline", "schema"):
        assert word not in text.lower(), word
    assert updated["steps"] and "edited in place" in updated["steps"][0]


def test_the_open_request_started_from_a_checkpoint(
    upgraded: tuple[Path, dict[str, Any], dict[str, str]],
) -> None:
    root, _, _ = upgraded
    vcs = Vcs(root)
    log = sorted(checkpoints.read(vcs), key=lambda c: c.number)
    labels = [c.label for c in log]
    assert labels[-4:] == [
        "Before upgrading the format",
        "Upgraded the file format to 2",
        "Started ECR-001: Carry a heavier shelf",
        "ECR-001: carried over from the old format",
    ]
    base = _ecr(root, 1)["baseline"]["checkpoint"]
    upgraded_cp = next(c for c in log if c.label == "Upgraded the file format to 2")
    assert base == upgraded_cp.id and vcs.read_ref("ecr/ECR-001/baseline") == base
    # the start checkpoint follows the baseline at once, as `ecr start` leaves it
    assert log[upgraded_cp.number].label.startswith("Started ECR-001")
    # the baseline is the model before the edit; the working folder is the model after it
    assert b"shelf-load:        {value: 10," in (
        vcs.read_file(base, "model/parameters.yaml") or b""
    )


def test_the_upgraded_product_builds_and_checks_and_shows_its_impact(
    upgraded: tuple[Path, dict[str, Any], dict[str, str]],
) -> None:
    root, _, _ = upgraded
    built = n2f("build", "--no-render", cwd=root)
    assert built.returncode == 0, built.stdout + built.stderr
    checked = n2f("check", cwd=root)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    listed = json.loads(n2f("ecr", "list", "--json", cwd=root).stdout)["ecrs"]
    assert {r["id"]: r["status"] for r in listed} == {
        "ECR-001": "draft",
        "ECR-002": "aborted",
        "ECR-003": "aborted",
        "ECR-004": "aborted",
        "ECR-005": "aborted",
        "ECR-006": "closed",
        "ECR-007": "rejected",
    }
    impact = n2f("ecr", "impact", "--json", cwd=root)
    assert impact.returncode == 0, impact.stdout + impact.stderr
    out = json.loads(impact.stdout)
    assert out["objects"]["changed"] == ["param://shelf-load"]
    assert out["files"]["changed"] == ["model/parameters.yaml"]  # not n2f.yaml: the upgrade
    # a second `init .` has nothing to do
    assert _init(root, "--json").exit_code == 0


def test_undoing_the_upgrade_with_no_open_request(tmp_path: Path) -> None:
    """With nothing open the upgrade is one step: `n2f undo` brings the old files back."""
    root = _fixture_copy(tmp_path, keep=(6, 7))
    before = _files(root)
    updated = _upgrade(root)
    assert updated["changes"] == ["2 finished change request(s) kept as they were"]
    assert migrate.schema_of(root) == 2
    undone = n2f("undo", cwd=root)
    assert undone.returncode == 0, undone.stdout + undone.stderr
    after = _files(root)
    assert {k: v for k, v in after.items() if k in before} == before
    assert migrate.schema_of(root) == 1
    # and `redo` brings the upgrade back
    assert n2f("redo", cwd=root).returncode == 0 and migrate.schema_of(root) == 2


def test_going_back_with_an_open_request_is_abort_then_rollback(tmp_path: Path) -> None:
    root = _fixture_copy(tmp_path)
    before = _files(root)
    updated = _upgrade(root)
    hint = updated["changes"][-1]
    number = re.search(r"`n2f rollback #(\d+)`", hint)
    assert number and "`n2f ecr abort ECR-001`" in hint
    # undo stops where the request started: nothing more to undo inside it
    assert n2f("undo", cwd=root).returncode == 0
    r = n2f("undo", cwd=root)
    assert "nothing more to undo inside the change request ECR-001" in _words(r.stdout)
    assert n2f("rollback", f"#{number.group(1)}", cwd=root).returncode != 0  # still open
    assert n2f("ecr", "abort", cwd=root).returncode == 0
    r = n2f("rollback", f"#{number.group(1)}", cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    after = _files(root)
    assert {k: v for k, v in after.items() if k in before} == before
    assert migrate.schema_of(root) == 1


def test_a_design_request_carries_its_patch_over(tmp_path: Path) -> None:
    root = _fixture_copy(tmp_path, keep=(2, 6, 7))
    updated = _upgrade(root)
    assert any("ECR-002" in c and "its patch was applied" in c for c in updated["changes"])
    live = _ecr(root, 2)
    assert live["status"] == "draft" and "patch" not in live and live["tasks"]
    assert "4. Check with a spirit level" in (root / "model/docs/installation.md").read_text()
    assert (root / "changes/ECR-002.patch").is_file()  # the file stays as a record
    assert load_product(root).ecrs["ECR-002"].baseline is not None


def test_an_approved_request_loses_its_approval(tmp_path: Path) -> None:
    root = _fixture_copy(tmp_path, keep=(4, 6, 7))
    updated = _upgrade(root)
    text = _words("\n".join(updated["changes"]))
    assert "ECR-004 (Longer horizontal leg): stays open" in text
    assert "approve it again after reviewing the impact" in text
    live = _ecr(root, 4)
    assert live["status"] == "draft" and "approval" not in live and "impact" not in live
    assert _value((root / "model/parameters.yaml").read_text(), "bracket-length") == "130"


def test_an_applied_request_becomes_approved_for_the_model_as_it_is(tmp_path: Path) -> None:
    root = _fixture_copy(tmp_path, keep=(5, 6, 7))
    updated = _upgrade(root)
    text = _words("\n".join(updated["changes"]))
    assert "ECR-005 (Holes a little further from the leg ends): was applied but not closed" in text
    assert "the last saved state before upgrading" in text  # its recorded snapshot is not here
    live = _ecr(root, 5)
    assert live["status"] == "approved" and "applied" not in live
    vcs = Vcs(root)
    assert live["approval"]["model_hash"] == vcs.working_hash(exclude=APPROVAL_HASH_EXCLUDE)
    assert live["approval"]["by"] == "Sam"
    assert vcs.read_ref("ecr/ECR-005/baseline") == live["baseline"]["checkpoint"]
    assert load_product(root).ecrs["ECR-005"].status == "approved"


def test_an_applied_request_starts_from_the_state_before_it_was_applied(tmp_path: Path) -> None:
    root = _fixture_copy(tmp_path, keep=(5, 6, 7))
    vcs = Vcs(root)
    params = root / "model/parameters.yaml"
    params.write_text(
        params.read_text().replace("hole-inset:        {value: 22", "hole-inset:        {value: 20")
    )
    before_apply = vcs.snapshot("Before ECR-005")
    params.write_text(
        params.read_text().replace("hole-inset:        {value: 20", "hole-inset:        {value: 22")
    )
    applied = vcs.snapshot("Apply ECR-005: Holes a little further from the leg ends")
    ecr = root / "changes/ECR-005.yaml"
    ecr.write_text(ecr.read_text().replace("0000000000000000000000000000000000000000", applied))
    vcs.snapshot("Record ECR-005 as applied")
    updated = _upgrade(root)
    assert "started from the state before it was applied" in _words("\n".join(updated["changes"]))
    assert _ecr(root, 5)["baseline"]["checkpoint"] == before_apply
    # the impact reads the old-format baseline as the current format: only the edit differs
    n2f("build", "--no-render", cwd=root)
    impact = n2f("ecr", "impact", "--json", cwd=root)
    assert impact.returncode == 0, impact.stdout + impact.stderr
    out = json.loads(impact.stdout)
    assert out["objects"]["changed"] == ["param://hole-inset"]
    assert out["files"]["changed"] == ["model/parameters.yaml"]


def test_a_patch_that_no_longer_fits_refuses_the_whole_upgrade(tmp_path: Path) -> None:
    root = _fixture_copy(tmp_path, keep=(2, 3, 6, 7))
    patch = root / "changes/ECR-002.patch"
    patch.write_text(patch.read_text().replace("3. Bolt the vertical leg", "3. Bolt the wrong leg"))
    Vcs(root).snapshot("The patch went stale")
    before = _files(root)
    result = _init(root)
    assert result.exit_code == 3, result.output
    text = _words(result.output)
    assert "nothing was changed" in text
    assert "ECR-002 (Add a levelling step to the installation page)" in text
    assert "changes/ECR-002.yaml" in text and "ECR-002.patch" in text
    assert _files(root) == before  # not even the agent files were added
    assert migrate.schema_of(root) == 1
    assert len(checkpoints.read(Vcs(root))) == 2  # nothing was saved either


def test_an_edit_that_no_longer_fits_refuses_the_whole_upgrade(tmp_path: Path) -> None:
    root = _fixture_copy(tmp_path, keep=(1, 6, 7))
    ecr = root / "changes/ECR-001.yaml"
    ecr.write_text(ecr.read_text().replace("param://shelf-load", "param://no-such-thing"))
    before = _files(root)
    result = _init(root)
    assert result.exit_code == 3, result.output
    assert "ECR-001 (Carry a heavier shelf)" in _words(result.output)
    assert "nothing was changed" in _words(result.output)
    assert _files(root) == before


def test_a_product_with_no_change_requests_just_gets_the_new_number(tmp_path: Path) -> None:
    root = _fixture_copy(tmp_path, keep=())
    updated = _upgrade(root)
    assert updated["changes"] == []
    assert migrate.schema_of(root) == 2 and load_product(root).ecrs == {}


def test_the_fixture_itself_stays_a_schema_1_product() -> None:
    assert migrate.schema_of(V1) == 1
    assert shutil.which("git")
    assert sorted(p.name for p in (V1 / "changes").iterdir()) == [
        "ECR-001.yaml",
        "ECR-002.patch",
        "ECR-002.yaml",
        "ECR-003.yaml",
        "ECR-004.yaml",
        "ECR-005.yaml",
        "ECR-006.yaml",
        "ECR-007.yaml",
    ]
