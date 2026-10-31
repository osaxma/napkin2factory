"""D20: a product pinned to another napkin2factory range gets one stderr notice, never a refusal."""

from __future__ import annotations

import json
from pathlib import Path

from napkin2factory import __version__
from napkin2factory.cli.common import pin_warning
from napkin2factory.cli.doctor import _pin_row
from tests.conftest import EXAMPLES, copy_product, n2f


def _repin(root: Path, system: str) -> None:
    manifest = root / "n2f.yaml"
    text = manifest.read_text()
    assert 'system: ">=0.3,<0.4"' in text
    manifest.write_text(text.replace('system: ">=0.3,<0.4"', f'system: "{system}"'))


def test_validate_warns_but_runs_outside_the_pin(tmp_path: Path):
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)
    _repin(root, ">=0.1,<0.2")
    r = n2f("validate", cwd=root)
    assert r.returncode == 0, r.stderr + r.stdout
    want = (
        f"this product was written for napkin2factory >=0.1,<0.2; you are running "
        f"{__version__}. It keeps working; once you are happy with the results, set "
        f"`system:` in n2f.yaml to a range that includes {__version__}."
    )
    assert want in r.stderr, r.stderr
    assert r.stderr.count("written for napkin2factory") == 1
    assert "written for" not in r.stdout
    j = n2f("validate", "--json", cwd=root)
    assert j.returncode == 0 and "written for" not in j.stderr + j.stdout
    assert json.loads(j.stdout)["ok"] is True


def test_validate_is_quiet_inside_the_pin(tmp_path: Path):
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)
    r = n2f("validate", cwd=root)
    assert r.returncode == 0, r.stderr + r.stdout
    assert "napkin2factory" not in r.stderr and "you are running" not in r.stderr


def test_pin_warning_is_none_for_an_unreadable_manifest(tmp_path: Path):
    (tmp_path / "n2f.yaml").write_text("system: [not, a, pin\n")
    assert pin_warning(tmp_path) is None


def test_doctor_pin_row(tmp_path: Path):
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)
    row = _pin_row(root)
    assert row is not None and row["status"] == "ok" and __version__ in row["detail"]
    _repin(root, ">=0.1,<0.2")
    row = _pin_row(root)
    assert row is not None and row["status"] == "warn" and ">=0.1,<0.2" in row["detail"]
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    assert _pin_row(outside) is None
