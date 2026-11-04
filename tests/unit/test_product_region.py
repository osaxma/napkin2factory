"""Tests for product region and display units (W7, W8, S-200).

Covers:
* Manifest region and units fields (W7, W8).
* Supply region defaulting to manifest region when supply file omits it.
* Validation failure when supply region and manifest region differ.
* US product on 120 V / 60 Hz resolving US conductors, colours and earthing.
* Loud failure when a region is unknown (names the table and lists known regions).
* Kiln (no product region today) builds unchanged (W11).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from napkin2factory.calckit import wiring
from napkin2factory.core.errors import ModelError
from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product, validate
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip
from napkin2factory.domains.electrical.model.refs import supply
from napkin2factory.domains.electrical.outputs.rules import _colour
from tests.conftest import EXAMPLES, FIXTURES, copy_product

MINIMAL = FIXTURES / "electrical" / "minimal"


def test_supply_region_defaults_to_manifest_region(tmp_path: Path) -> None:
    """The electrical supply's region defaults to n2f.yaml's when supply.yaml omits it."""
    root = copy_product(MINIMAL, tmp_path / "p", git=False)

    # Put region in n2f.yaml
    manifest_data = load_roundtrip(root / "n2f.yaml")
    manifest_data["region"] = "EU"
    dump_roundtrip(root / "n2f.yaml", manifest_data)

    # Remove region from supply.yaml
    sup_data = load_roundtrip(root / "model" / "electrical" / "supply.yaml")
    del sup_data["region"]
    dump_roundtrip(root / "model" / "electrical" / "supply.yaml", sup_data)

    product = load_product(root)
    sup = supply(product)
    assert sup is not None
    assert sup.region == "EU"
    # Validate succeeds without errors
    _, problems = validate(root)
    assert not problems.errors


def test_supply_and_manifest_region_disagreement_fails(tmp_path: Path) -> None:
    """When both supply and manifest declare region and differ, validation fails naming both."""
    root = copy_product(MINIMAL, tmp_path / "p", git=False)

    # Put region: US in n2f.yaml while supply.yaml has region: EU
    manifest_data = load_roundtrip(root / "n2f.yaml")
    manifest_data["region"] = "US"
    dump_roundtrip(root / "n2f.yaml", manifest_data)

    with pytest.raises(ModelError, match="supply region 'EU' disagrees with product region 'US'"):
        load_product(root)

    _, problems = validate(root)
    assert any(
        "supply region 'EU' disagrees with product region 'US'" in p.message
        for p in problems.errors
    )


def test_us_product_resolves_us_conductors_colours_and_earthing(tmp_path: Path) -> None:
    """A product with region US on 120 V/60 Hz resolves US conductors, colours and earthing."""
    root = copy_product(MINIMAL, tmp_path / "us_product", git=False)

    # Set product region to US
    manifest_data = load_roundtrip(root / "n2f.yaml")
    manifest_data["region"] = "US"
    manifest_data["units"] = "imperial"
    dump_roundtrip(root / "n2f.yaml", manifest_data)

    # Update supply.yaml: US 120 V / 60 Hz solidly-grounded, omitting region: (defaulted)
    sup_data = load_roundtrip(root / "model" / "electrical" / "supply.yaml")
    sup_data["voltage"] = "120 V"
    sup_data["frequency"] = "60 Hz"
    sup_data["earthing"] = "solidly-grounded"
    del sup_data["region"]
    dump_roundtrip(root / "model" / "electrical" / "supply.yaml", sup_data)

    # Update circuit connection conductors to US AWG conductor
    circ_file = root / "model" / "electrical" / "circuits" / "heater.yaml"
    circ_data = load_roundtrip(circ_file)
    for conn in circ_data["connections"]:
        conn["conductor"] = "awg14-mtw"
        if "colour" in conn:
            del conn["colour"]  # let it resolve automatically from region
    dump_roundtrip(circ_file, circ_data)

    product = load_product(root)
    sup = supply(product)
    assert sup is not None
    assert sup.region == "US"
    assert sup.earthing == "solidly-grounded"

    # Validation succeeds without errors
    _, problems = validate(root)
    assert not problems.errors

    # Verify conductor, colour and earthing resolution for US
    us_conductors = wiring.conductors(sup.region)
    assert any(c.id == "awg14-mtw" and c.awg == 14 for c in us_conductors)
    assert wiring.colour(sup.region, "L").colour == "black"
    assert wiring.colour(sup.region, "N").colour == "white"
    assert wiring.colour(sup.region, "PE").colour == "green"
    assert wiring.earthing("solidly-grounded", region=sup.region).code == "solidly-grounded"

    # Terminal roles resolve US colours via _colour
    assert _colour(None, sup.region, ("L", "1"), "power", False) == "black"
    assert _colour(None, sup.region, ("N", "3"), "power", False) == "white"
    assert _colour(None, sup.region, ("PE", "PE"), "earth", False) == "green"


def test_unknown_region_fails_loudly_with_list(tmp_path: Path) -> None:
    """An unknown region like 'XX' fails loudly with the list of known regions."""
    root = copy_product(MINIMAL, tmp_path / "p", git=False)

    manifest_data = load_roundtrip(root / "n2f.yaml")
    manifest_data["region"] = "XX"
    dump_roundtrip(root / "n2f.yaml", manifest_data)

    with pytest.raises(ModelError, match="unknown region 'XX'; known regions: AU, EU, SA, UK, US"):
        load_product(root)

    _, problems = validate(root)
    assert any(
        "unknown region 'XX'; known regions: AU, EU, SA, UK, US" in p.message
        for p in problems.errors
    )


def test_kiln_builds_unchanged(tmp_path: Path) -> None:
    """The kiln (no product region declared today) builds unchanged (W11)."""
    root = copy_product(EXAMPLES / "kiln", tmp_path / "k", prebuilt=True, render=False)
    product = load_product(root)
    # Manifest omits region today
    assert product.manifest.region is None
    # Supply carries EU region today
    sup = supply(product)
    assert sup is not None
    assert sup.region == "EU"
    # Build runs clean
    res = run_build(product, render=False, quiet=True)
    assert isinstance(res["ran"], list)
