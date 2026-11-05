"""v0.6 follow-up: the wiring diagram readable at a real product's size (S-174).

Pure tests of ``circuit_svg`` on hand-written records shaped like a wired product's: an earth
bar holding many conductors never overprints a label; a device reached through a cable entry
from the box is drawn outside it, whatever the circuit's purpose; the title says the supply's
voltage only for a circuit the supply feeds and "Protected by" only where the checks require
a protective device; a long wire is labelled at both ends, once per end.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

# the core first: imported before it, the domain's package registers nothing (B-0156)
from napkin2factory.core.loader import load_product  # noqa: F401
from napkin2factory.domains.electrical.outputs.diagram import carries, circuit_svg, title_inputs
from napkin2factory.drawings.svg import text_width

NS = "{http://www.w3.org/2000/svg}"


def _device(uri: str, name: str, terminals: list[str], role: str = "") -> dict[str, Any]:
    return {"uri": uri, "name": name, "instance": None, "role": role, "terminals": terminals}


def _wire(wid: str, a: str, b: str, via: str | None = None) -> dict[str, Any]:
    return {"id": wid, "from": a, "to": b, "csa_mm2": 2.5, "colour": "green-and-yellow", "via": via}


def _record(
    purpose: str,
    devices: list[dict[str, Any]],
    wires: list[dict[str, Any]],
    entries: list[dict[str, Any]] | None = None,
    **kw: Any,
) -> dict[str, Any]:
    return {
        "circuit": purpose,
        "name": purpose.capitalize(),
        "purpose": purpose,
        "voltage_v": kw.get("voltage_v", 230.0),
        "dc": kw.get("dc", False),
        "protection": kw.get("protection", {"ref": None, "words": "not given"}),
        "devices": devices,
        "wires": wires,
        "entries": entries or [],
        "boundary": [],
    }


def _groups(svg: str) -> dict[str, ET.Element]:
    tree = ET.fromstring(svg)
    return {g.get("id", ""): g for g in tree.iter(f"{NS}g")}


def _labels(svg: str) -> list[tuple[str, float, float, float, float]]:
    """Every wire label: its text and its box (x0, y0, x1, y1) on the sheet."""
    out = []
    for el in ET.fromstring(svg).iter(f"{NS}text"):
        if el.get("class") != "wire-label":
            continue
        text, size = el.text or "", float(el.get("font-size", 0))
        x, y, w = float(el.get("x", 0)), float(el.get("y", 0)), text_width(text, size)
        x0 = x - w if el.get("text-anchor") == "end" else x
        out.append((text, x0, y - size * 0.8, x0 + w, y + size * 0.2))
    return out


def _x(svg: str, gid: str) -> float:
    rect = _groups(svg)[gid].find(f"{NS}rect")
    assert rect is not None
    return float(rect.get("x", 0))


def _earth() -> dict[str, Any]:
    """A supply's earth to a bar in the box, six bonds from the bar, four out through an entry."""
    studs = ["box", "lid", "guard", "shell", "stand", "door"]
    devices = [_device("device://bar", "Earth bar", ["PE"], "earth")]
    devices += [_device(f"device://{s}", f"{s.capitalize()} stud", ["PE"], "earth") for s in studs]
    wires = [_wire("earth-1", "supply://supply#PE", "device://bar#PE", via="iface://mains")]
    for n, s in enumerate(studs, start=2):
        via = "iface://leads" if n > 3 else None
        wires.append(_wire(f"earth-{n}", "device://bar#PE", f"device://{s}#PE", via=via))
    entries = [
        {"uri": "iface://mains", "name": "Mains in", "external": False},
        {"uri": "iface://leads", "name": "Leads out", "external": False},
    ]
    return _record("earth", devices, wires, entries)


def test_a_shared_earth_terminal_never_overprints_and_each_wire_is_said_once_per_end() -> None:
    svg = circuit_svg(_earth())
    labels = _labels(svg)
    for i, (ta, *a) in enumerate(labels):
        for tb, *b in labels[i + 1 :]:
            apart = a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]
            assert apart, f"{ta!r} overprints {tb!r}"
    for n in range(1, 8):
        texts = [t for t, *_ in labels if t.split(" · ")[0] == f"earth-{n}"]
        assert sum(" · " in t for t in texts) == 1, texts  # the full label once
        assert len(texts) <= 2, texts  # and its id at most once more, at its other end
    # the bar's terminal holds six conductors on its outgoing side: no full label there
    bar = _groups(svg)["device-bar"].find(f"{NS}rect")
    assert bar is not None
    right = float(bar.get("x", 0)) + float(bar.get("width", 0))
    beside = [t for t, x0, *_ in labels if abs(x0 - right - 1.5) < 0.01]
    assert not [t for t in beside if " · " in t], beside


def test_a_wire_through_an_entry_is_labelled_at_both_ends() -> None:
    labels = [t for t, *_ in _labels(circuit_svg(_earth()))]
    assert "earth-1 · 2.5 mm² · green-and-yellow" in labels and "earth-1" in labels


def _sensing() -> dict[str, Any]:
    """Two probes outside the box, each through one entry to its own controller inside."""
    devices = [
        _device("device://probe-a", "Probe", ["+", "-"], "sensor"),
        _device("device://ctl-a", "Controller", ["5", "6"], "control"),
        _device("device://probe-b", "Second probe", ["+", "-"], "sensor"),
        _device("device://ctl-b", "Limit controller", ["5", "6"], "control"),
    ]
    via = "iface://probes"
    wires = [
        _wire("sensing-1", "device://probe-a#+", "device://ctl-a#6", via),
        _wire("sensing-2", "device://probe-a#-", "device://ctl-a#5", via),
        _wire("sensing-3", "device://probe-b#+", "device://ctl-b#6", via),
        _wire("sensing-4", "device://probe-b#-", "device://ctl-b#5", via),
    ]
    entries = [{"uri": via, "name": "Probe leads in", "external": False}]
    return _record("sensing", devices, wires, entries, voltage_v=0.05, dc=True)


def test_every_device_reached_through_an_entry_is_drawn_outside_it() -> None:
    svg = circuit_svg(_sensing())
    entry = _x(svg, "entry-probes")
    assert _x(svg, "device-probe-a") < entry and _x(svg, "device-probe-b") < entry
    assert _x(svg, "device-ctl-a") > entry and _x(svg, "device-ctl-b") > entry


def test_the_boxs_own_devices_stay_on_the_near_side_of_its_entry() -> None:
    """The studs wired from the bar inside the box sit left of the entry the others leave by."""
    svg = circuit_svg(_earth())
    entry = _x(svg, "entry-leads")
    assert _x(svg, "device-box") < entry and _x(svg, "device-lid") < entry
    assert all(_x(svg, f"device-{s}") > entry for s in ("guard", "shell", "stand", "door"))
    assert _x(svg, "supply-supply") < _x(svg, "entry-mains") < _x(svg, "device-bar")


def test_a_device_beyond_the_box_on_the_far_side_of_the_supply() -> None:
    """A load fed from inside the box through an entry sits right of it, the supply left."""
    devices = [
        _device("device://switch", "Switch", ["1", "2"], "control"),
        _device("device://heater", "Heater", ["A"], "load"),
    ]
    wires = [
        _wire("p-1", "supply://supply#L", "device://switch#1", via="iface://in"),
        _wire("p-2", "device://switch#2", "device://heater#A", via="iface://out"),
    ]
    entries = [
        {"uri": "iface://in", "name": "In", "external": False},
        {"uri": "iface://out", "name": "Out", "external": False},
    ]
    svg = circuit_svg(_record("power", devices, wires, entries))
    xs = [
        _x(svg, g)
        for g in ("supply-supply", "entry-in", "device-switch", "entry-out", "device-heater")
    ]
    assert xs == sorted(xs)


def _title(svg: str) -> list[str]:
    """The title's lines (an empty circuit's "No connections yet." left out)."""
    lines = [t.text or "" for t in _groups(svg)["title"].iter(f"{NS}text")]
    return [t for t in lines if t != "No connections yet."]


def test_each_title_says_what_its_circuit_carries() -> None:
    sensing = _title(circuit_svg(_sensing()))
    assert sensing == ["Sensing circuit (sensing), extra-low-voltage signal"]
    earth = _title(circuit_svg(_earth()))
    assert earth == ["Earth circuit (earth)"]
    power = _record("power", [], [], protection={"ref": "supply", "words": "the site's breaker"})
    assert _title(circuit_svg(power)) == [
        "Power circuit (power), 230 V AC",
        "Protected by: the site's breaker",
    ]
    control = _record("control", [], [])
    assert _title(circuit_svg(control))[1] == "Protected by: not given"  # a gap, said
    # a signal above the band, or of unknown voltage, says so in words
    assert carries(_record("sensing", [], [], voltage_v=230.0)) == "signal at 230 V AC"
    assert carries(_record("sensing", [], [], voltage_v=None)) == "signal, voltage not given"


def test_the_title_reads_the_checks_band_and_protected_purposes() -> None:
    """What the title reads from the checks is an input of every circuit's rule."""
    words = title_inputs()
    assert words.startswith("power,control|") and re.search(r"\d", words)


def test_a_chain_out_through_an_entry_and_back_through_it_draws() -> None:
    """The E-stop and door interlock chain (B-0213, S-233): the door switch sits beyond the
    lid entry and two wires return through it to the drive; an empty column between the
    boxes used to raise an IndexError in the lane search."""
    via = "iface://lid"
    devices = [
        _device("device://estop", "E-stop", ["1", "2"], "control"),
        _device("device://door", "Door switch", ["1", "2"], "control"),
        _device("device://drive", "Drive", ["A", "B"], "load"),
        _device("device://ctl", "Controller", ["24V", "IN"], "control"),
    ]
    wires = [
        _wire("sc-1", "supply://supply#L", "device://estop#1"),
        _wire("sc-2", "device://estop#2", "device://door#1", via),
        _wire("sc-3", "device://door#2", "device://drive#A", via),
        _wire("sc-4", "device://ctl#24V", "device://door#1", via),
        _wire("sc-5", "device://drive#B", "device://ctl#IN"),
    ]
    entries = [{"uri": via, "name": "Lid entry", "external": False}]
    svg = circuit_svg(_record("control", devices, wires, entries, voltage_v=24.0, dc=True))
    entry = _x(svg, "entry-lid")
    assert _x(svg, "device-door") > entry
    assert all(_x(svg, f"device-{d}") < entry for d in ("estop", "drive", "ctl"))
    for wid in ("sc-1", "sc-2", "sc-3", "sc-4", "sc-5"):
        assert f"wire-{wid}" in _groups(svg)
    # no column is left empty: the boxes' x positions fall into as many columns as are used
    xs = sorted({round(_x(svg, g), 3) for g in _groups(svg) if g.startswith(("device-", "entry-"))})
    assert len(xs) >= 4
