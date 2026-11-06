"""A checkpoint's vitals come from a fresh build only (v0.8 R3, S-251)."""

from __future__ import annotations

import re
from pathlib import Path

from napkin2factory.core.checkpoints import Vitals
from napkin2factory.core.loader import load_product
from napkin2factory.core.vitals import current_vitals
from tests.conftest import EXAMPLES, copy_product


def test_vitals_are_read_from_a_fresh_build_and_not_measured_once_stale(tmp_path: Path) -> None:
    table = copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)
    vitals = current_vitals(load_product(table))
    assert vitals.mass is not None and re.fullmatch(r"\d+\.\d kg", vitals.mass)
    assert vitals.cost is not None and re.fullmatch(r"[\d,]+ USD", vitals.cost)

    params = table / "model" / "parameters.yaml"
    changed, n = re.subn(r"(tab-thickness:\s*\{value: )4,", r"\g<1>5,", params.read_text())
    assert n == 1
    params.write_text(changed)
    assert current_vitals(load_product(table)) == Vitals()  # stale: not measured


def test_vitals_without_a_build_are_not_measured(tmp_path: Path) -> None:
    table = copy_product(EXAMPLES / "table", tmp_path / "table", git=False)
    assert current_vitals(load_product(table)) == Vitals()
