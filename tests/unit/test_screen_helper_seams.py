"""v0.5 seams found while the wiring domain moved the supply screen (v0.6 wave 2, E10).

Each test defines its own small domain or screen here; none touches the shipped domains.

* A card field's ``param`` comes from any declaration naming one, not only the first: a
  domain's screens are declared before a product's own (S-160).
* A domain declaring ``CardField``s at import loads when a process imports
  ``napkin2factory.concepts.screens`` first (S-161).
* ``check_rows_state`` says every status it counts, a choice included (S-162).
* ``scope_entry`` gives a domain its scope line (S-163).
* A doc helper reads the build folder from ``h.build_dir`` (S-164).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from napkin2factory.concepts.screens import CardField, card_fields, declared_fields, reads
from napkin2factory.core.checks.stage import check_rows_state, scope_entry
from napkin2factory.core.concepts import param_names
from napkin2factory.core.domain import Domain, HelperContext, Screen
from napkin2factory.core.errors import N2FError
from napkin2factory.core.loader import Doc, load_product
from napkin2factory.core.model.docs import DocMeta
from napkin2factory.core.registry import installed
from napkin2factory.docs.engine import render_doc
from tests.conftest import EXAMPLES, copy_product

# ---- 1. a card field's param (S-160) ----------------------------------------------------

#: The domain's declaration: the same field, no parameter named.
POWER = CardField("envelope", "power", "W", "a power", "2.5 kW", "the power")


@reads(POWER, phase="estimate")
def _supply(card: Any, massing: Any, values: Any) -> list[Any]:
    return []


SUPPLY_DOMAIN = Domain(name="seam-supply", screens=(Screen("seam-supply", _supply),))

PRODUCT_SCREEN = """\
from napkin2factory.concepts.screens import CardField, reads
from napkin2factory.core.domain import Screen

POWER = CardField("envelope", "power", "W", "a power", "2.5 kW", "the heater power",
                  param="{param}")


@reads(POWER, phase="estimate")
def heater(card, massing, values):
    return []


SCREENS = (Screen("seam-heater", heater),)
"""


def _with_screen(tmp_path: Path, param: str) -> Path:
    """A copy of the bracket whose own pack declares ``envelope.power`` seeding ``param``."""
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)
    screens = root / "model" / "screens"
    screens.mkdir(parents=True)
    (screens / "seam_heater.py").write_text(PRODUCT_SCREEN.format(param=param), encoding="utf-8")
    return root


def test_a_domain_declaring_the_field_first_keeps_the_products_param(tmp_path: Path) -> None:
    root = _with_screen(tmp_path, "heater-power")
    with installed(SUPPLY_DOMAIN):
        assert param_names(root) == {"power": "heater-power"}
        power = next(f for f in card_fields(root) if f.name == "envelope.power")
    # the first declaration (the domain's) still gives the words; the param is the product's
    assert (power.words, power.param) == ("the power", "heater-power")


def test_the_same_param_twice_is_no_clash() -> None:
    a = CardField("envelope", "power", "W", "a power", "2.5 kW", "the power", param="p-power")
    b = CardField("envelope", "power", "kW", "a power", "2 kW", "power", param="p-power")
    first = Screen("a", _supply, fields=(a,))
    second = Screen("b", _supply, fields=(b,))
    assert [f.param for f in declared_fields([first, second])] == ["p-power"]


def test_two_different_params_are_an_error_naming_both_files(tmp_path: Path) -> None:
    root = _with_screen(tmp_path, "heater-power")
    named = CardField("envelope", "power", "W", "a power", "2.5 kW", "the power", param="watts")
    domain = Domain(name="seam-named", screens=(Screen("seam-named", _supply, fields=(named,)),))
    with installed(domain), pytest.raises(N2FError) as err:
        param_names(root)
    message = str(err.value)
    assert "envelope.power" in message
    assert "'watts'" in message and "'heater-power'" in message
    assert Path(__file__).name in message and "model/screens/seam_heater.py" in message


# ---- 2. the screens import order (S-161) -------------------------------------------------

CYCLE_DOMAIN = """\
from napkin2factory.concepts.screens import CardField, ScreenValues, reads
from napkin2factory.core.domain import Domain, Screen

CYCLES = CardField("envelope", "seam-cycles", None, "a count", "3", "how many cycles")


@reads(CYCLES)
def cycles(card, massing, values: ScreenValues):
    return []


DOMAIN = Domain(name="seam-cycle", screens=(Screen("seam-cycle", cycles),))
"""

FIRST_IMPORT = """\
import napkin2factory.domains as installed_domains

installed_domains.INSTALLED = (*installed_domains.INSTALLED, "seam_cycle_domain")
import napkin2factory.concepts.screens  # first, before any core module: the order that cycled

from napkin2factory.concepts.screens import card_fields
from napkin2factory.core.registry import registry

print([d.name for d in registry().domains])
print([f.name for f in card_fields()])
"""


def test_a_domain_declaring_card_fields_loads_when_the_screens_are_imported_first(
    tmp_path: Path,
) -> None:
    package = tmp_path / "seam_cycle_domain"
    package.mkdir()
    (package / "__init__.py").write_text(CYCLE_DOMAIN, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(tmp_path)}
    done = subprocess.run(
        [sys.executable, "-c", FIRST_IMPORT],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    domains, fields = done.stdout.splitlines()[-2:]
    assert "'seam-cycle'" in domains
    assert "'envelope.seam-cycles'" in fields


# ---- 3. every status said in a gate row (S-162) ------------------------------------------


def _checks(build: Path, statuses: list[str], kind: str = "seam") -> Path:
    rows = [{"id": f"r{i}", "kind": kind, "status": s} for i, s in enumerate(statuses)]
    (build / "checks").mkdir(parents=True, exist_ok=True)
    (build / "checks" / "checks.json").write_text(json.dumps({"results": rows}))
    return build


def test_a_choice_and_every_other_status_are_said(tmp_path: Path) -> None:
    build = _checks(
        tmp_path, ["later", "signed", "warn", "needs-human", "choice", "pass", "pass", "skip"]
    )
    state = check_rows_state(build, "seam", {"pass": "OK", "warn": "for a person to judge"})
    assert state is not None
    assert state.summary == (
        "8 checks: 2 OK, 1 choice waiting on you, 1 needs your sign-off, "
        "1 for a person to judge, 1 not checked, 1 signed off, 1 left for later"
    )
    assert state.blockers == [] and state.caveats == []


def test_choices_counted_and_a_domains_own_word_wins(tmp_path: Path) -> None:
    build = _checks(tmp_path, ["choice", "choice", "fail"])
    state = check_rows_state(build, "seam", {"fail": "needs attention"})
    assert state is not None and state.summary == (
        "3 checks: 1 needs attention, 2 choices waiting on you"
    )
    own = check_rows_state(build, "seam", {"choice": "for you to decide"})
    assert own is not None and own.summary == ("3 checks: 1 needs attention, 2 for you to decide")


def test_a_row_without_a_choice_reads_as_before(tmp_path: Path) -> None:
    build = _checks(tmp_path, ["pass", "fail", "pass"])
    state = check_rows_state(build, "seam", {"pass": "OK", "fail": "needs attention"})
    assert state is not None and state.summary == "3 checks: 2 OK, 1 needs attention"
    assert check_rows_state(build, "other", {}) is None


# ---- 4. a domain's scope line (S-163) ----------------------------------------------------


def test_scope_entry_gives_a_domain_its_scope_line(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)
    manifest = yaml.safe_load((root / "n2f.yaml").read_text())
    manifest["scope"] = {"seam": {"state": "later", "note": "comes in the next version"}}
    (root / "n2f.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    product = load_product(root)
    entry = scope_entry(product, "seam")
    assert entry is not None
    assert entry["state"] == "later"
    assert entry["line"] == (
        "Seam: left for later (not designed here yet) — comes in the next version"
    )
    assert scope_entry(product, "mechanical") is None


# ---- 5. a doc helper's build folder (S-164) ----------------------------------------------


def _build_dir_helper(h: HelperContext) -> Any:
    def seam_build_dir() -> str:
        return str(h.build_dir)

    return seam_build_dir


HELPER_DOMAIN = Domain(name="seam-helper", doc_helpers={"seam_build_dir": _build_dir_helper})


def test_a_doc_helper_reads_the_build_folder_it_renders_in(tmp_path: Path) -> None:
    with installed(HELPER_DOMAIN):
        product = load_product(EXAMPLES / "bracket")
        doc = Doc(
            meta=DocMeta(id="seam", title="Seam"),
            body="{{ seam_build_dir() }}",
            path=tmp_path / "seam.md",
        )
        elsewhere = tmp_path / "elsewhere" / "build"
        assert render_doc(product, doc, build_dir=elsewhere).markdown == str(elsewhere)
        assert render_doc(product, doc).markdown == str(product.paths.build)
