"""The wiring tables and their typed loader (napkin2factory.calckit.wiring; S-146).

Every row loads with the right units, names its source and is marked ``verify: true``;
unknown ids say what is on file. The spot values are the rows as transcribed from the cited
tables, pinned so an edit to a number is a deliberate one.
"""

from __future__ import annotations

import pytest

from napkin2factory.calckit import load_table, wiring
from napkin2factory.core.units import Quantity as Q

TABLES = ("conductors", "earthing", "wire_colours")


@pytest.mark.parametrize("name", TABLES)
def test_every_row_has_a_source_and_verify(name: str) -> None:
    rows = load_table(name)
    assert rows
    for row in rows:
        assert row["verify"] is True, row
        assert len(row["source"].strip()) > 20, row  # a citation, not a word


def test_every_conductor_loads_with_its_units() -> None:
    rows = wiring.all_conductors()
    assert len(rows) == 25
    assert len({c.id for c in rows}) == len(rows)
    for c in rows:
        assert c.csa.dimensionality == Q(1, "mm**2").dimensionality
        assert c.ampacity.dimensionality == Q(1, "A").dimensionality
        assert str(c.ambient.units) == "degree_Celsius"
        assert str(c.max_temp.units) == "degree_Celsius"
        assert c.csa.magnitude > 0 and c.ampacity.magnitude > 0
        assert c.max_temp > c.ambient
        assert c.kind in {"panel", "cord", "high-temp"}
        assert c.basis and c.insulation and c.label
        assert (c.awg is not None) == (c.region == "US")


def test_regions_and_sizes() -> None:
    eu = wiring.conductors("eu")
    us = wiring.conductors("US")
    assert {c.csa.to("mm**2").magnitude for c in eu} == {0.75, 1.0, 1.5, 2.5, 4.0}
    assert {c.awg for c in us} == {18, 16, 14, 12, 10}
    assert len(eu) == 10 and len(us) == 15
    with pytest.raises(ValueError, match="table 'conductors' has no rows for region 'XX'.*EU, US"):
        wiring.conductors("XX")


def test_ampacity_rises_with_size_within_a_class() -> None:
    by_class: dict[tuple[str, str], list[wiring.Conductor]] = {}
    for c in wiring.all_conductors():
        by_class.setdefault((c.region, c.kind if c.region == "US" else c.insulation), []).append(c)
    for group in by_class.values():
        ordered = sorted(group, key=lambda c: c.csa.magnitude)
        amps = [c.ampacity.magnitude for c in ordered]
        assert amps == sorted(amps), [c.id for c in ordered]


def test_spot_values() -> None:
    c = wiring.conductor("cu-2p5-pvc")
    assert c.ampacity == Q(17.4, "A") and c.csa == Q(2.5, "mm**2") and c.ambient == Q(40, "degC")
    assert "IEC 60204-1" in c.source and "B2" in c.basis
    assert wiring.conductor("awg14-mtw").ampacity == Q(15, "A")
    assert "310.16" in wiring.conductor("awg14-mtw").source
    assert wiring.conductor("awg16-cord").ampacity == Q(13, "A")
    assert "400.5(A)" in wiring.conductor("awg16-cord").source
    # the silicone rows carry the PVC row's value as a floor (the table's header)
    for size in ("0p75", "1p0", "1p5", "2p5", "4p0"):
        assert (
            wiring.conductor(f"cu-{size}-silicone").ampacity
            == wiring.conductor(f"cu-{size}-pvc").ampacity
        )
        assert wiring.conductor(f"cu-{size}-silicone").max_temp == Q(180, "degC")


def test_unknown_conductor_lists_the_known_ids() -> None:
    with pytest.raises(ValueError, match="no conductor 'cu-9-pvc'.*cu-2p5-pvc.*awg10-cord"):
        wiring.conductor("cu-9-pvc")


def test_earthing() -> None:
    rows = wiring.all_earthing()
    assert {e.region for e in rows} == {"AU", "EU", "SA", "UK", "US"}
    assert all(e.verify and len(e.source.strip()) > 20 for e in rows)
    tt = wiring.earthing("tt")
    assert "residual-current device" in tt.class_i and "411.5" in tt.source
    with pytest.raises(ValueError, match="no earthing arrangement 'TN-C' on file"):
        wiring.earthing("TN-C")

    # per-region filtering and US grounding
    eu_rows = wiring.all_earthing("EU")
    assert [e.code for e in eu_rows] == ["TN-S", "TN-C-S", "TT", "IT"]
    assert wiring.earthing("TN-S", region="EU").code == "TN-S"
    assert wiring.earthing("solidly-grounded", region="US").code == "solidly-grounded"
    assert wiring.earthing("grounded", region="US").code == "grounded"

    with pytest.raises(ValueError, match="no earthing arrangement 'TN-C' on file for region 'US'"):
        wiring.earthing("TN-C", region="US")
    with pytest.raises(
        ValueError,
        match="table 'earthing' has no rows for region 'XX'.*known regions: AU, EU, SA, UK, US",
    ):
        wiring.earthing("TN-S", region="XX")


def test_colours() -> None:
    assert wiring.colour("EU", "PE").colour == "green-and-yellow"
    assert wiring.colour("eu", "N").colour == "blue"
    assert wiring.colour("EU", "L").colour == "brown"
    assert wiring.colour("US", "N").colour == "white"
    assert wiring.colour("US", "PE").colour == "green"
    assert "200.6" in wiring.colour("US", "N").source
    pairs = [(c.region, c.role) for c in wiring.all_colours()]
    assert len(pairs) == len(set(pairs)) == 15
    with pytest.raises(
        ValueError, match="table 'wire_colours' has no rows for region 'AU'.*EU, US"
    ):
        wiring.colour("AU", "PE")
    with pytest.raises(
        ValueError, match="table 'wire_colours' has no rows for region 'XX'.*EU, US"
    ):
        wiring.colour("XX", "PE")
    with pytest.raises(ValueError, match="no conductor colour for role 'hot' in region 'US'"):
        wiring.colour("US", "hot")
