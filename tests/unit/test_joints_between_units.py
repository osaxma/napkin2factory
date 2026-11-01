"""v0.4 M6 (P12, P13): joints between units in the plan and the report, the ports a change
crosses, and the one-module simulation's bundle script.

The kiln is only loaded here (no build): the plan, the ports and the bundle need none. The
report section with its verdicts on the built kiln is in ``tests/e2e/test_kiln.py``.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

from napkin2factory.bom.build_plan import derive_build_plan
from napkin2factory.core.graph.impact import crossed_ports
from napkin2factory.core.loader import load_product
from tests.conftest import EXAMPLES, FIXTURES, ROOT, copy_product

KILN = EXAMPLES / "kiln"


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "module_sim_bundle", ROOT / "scripts" / "module_sim_bundle.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["module_sim_bundle"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_kiln_plan_lists_its_four_joints_between_units() -> None:
    plan = derive_build_plan(load_product(KILN))
    rows = {
        j["interface"]: (
            tuple(s["unit_name"] for s in j["sides"]),
            tuple(s["part"] for s in j["sides"]),
            j["kind"],
            tuple((h["part"], h["qty"]) for h in j["hardware"]),
            j["closed_by"],
        )
        for j in plan["between_units"]
    }
    kiln = "Mini electric test kiln"
    assert rows == {
        "iface://controller-mount": (
            (kiln, "Controls"),
            ("part://guard-shell", "part://controller-box"),
            "bolt-pattern",
            (("part://m6-standoff-40", 4), ("part://m6x16-bolt", 8)),
            "asm://kiln",
        ),
        "iface://hinge-lower": (
            (kiln, "Door"),
            ("part://hinge-post", "part://hinge"),
            "mating-face",
            (),
            "asm://kiln",
        ),
        "iface://hinge-upper": (
            (kiln, "Door"),
            ("part://hinge-post", "part://hinge"),
            "mating-face",
            (),
            "asm://kiln",
        ),
        "iface://latch-catch": (
            (kiln, "Door"),
            ("part://latch-keeper", "part://latch"),
            "mating-face",
            (),
            "asm://kiln",
        ),
    }
    how = {j["interface"]: j["how"] for j in plan["between_units"]}
    assert how["iface://controller-mount"] == "bolted, 4 holes"
    assert how["iface://hinge-lower"].startswith("faces that meet (welded")
    # every joint between units is a port of the unit it hangs (P4) and nothing else is
    ports = {str(u) for a in load_product(KILN).assemblies.values() for u in a.ports}
    assert set(rows) <= ports


def test_flat_products_have_no_joint_between_units() -> None:
    for name in ("bracket", "enclosure"):
        assert derive_build_plan(load_product(EXAMPLES / name))["between_units"] == []


def test_a_phantoms_port_is_not_between_units() -> None:
    plan = derive_build_plan(load_product(FIXTURES / "units"))
    assert [j["interface"] for j in plan["between_units"]] == ["iface://pod-mount"]
    (j,) = plan["between_units"]
    assert [s["unit"] for s in j["sides"]] == ["asm://top", "asm://pod"]
    assert j["step"] == 2 and j["closed_by_name"] == "Top"


def test_impact_names_the_ports_a_change_crosses() -> None:
    kiln = load_product(KILN)
    ports = crossed_ports(kiln, ["door-guard-standoff", "guard-hinge-post", "hinge-lower"])
    assert [p["interface"] for p in ports] == ["iface://hinge-lower"]
    assert ports[0]["port_of"] == ["asm://door"] and ports[0]["between_units"]
    assert [s["unit_name"] for s in ports[0]["sides"]] == ["Mini electric test kiln", "Door"]
    # a phantom's port joins two sides built in one unit
    units = load_product(FIXTURES / "units")
    (cover,) = crossed_ports(units, ["cover-base"])
    assert cover["port_of"] == ["asm://frame"] and not cover["between_units"]
    assert crossed_ports(load_product(EXAMPLES / "bracket"), ["anything"]) == []


def test_impact_summary_says_both_sides_are_checked_again() -> None:
    from napkin2factory.core.graph.impact import compute_impact, parse_set, summarize

    kiln = load_product(KILN)
    report = compute_impact(kiln, [parse_set("param://hinge-length=70 mm")], KILN / "build-none")
    assert {p["interface"] for p in report.ports} >= {"iface://hinge-lower", "iface://hinge-upper"}
    assert "ports" in report.to_dict()
    text = summarize(report, kiln)
    assert "joint(s) between units, so both sides are checked again" in text
    assert "(Mini electric test kiln and Door)" in text


# ---- the one-module simulation (DoD 5) -------------------------------------------------------


@pytest.fixture(scope="module")
def kiln_copy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return copy_product(KILN, tmp_path_factory.mktemp("sim") / "kiln", git=False)


def test_bundle_holds_role_context_and_geometry(
    kiln_copy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _script()
    out = kiln_copy.parent / "bundle.md"
    assert mod.main([str(kiln_copy), "asm://door", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    size = out.stat().st_size
    assert printed.strip() == f"{out}: {size} bytes"
    text = out.read_text(encoding="utf-8")
    assert "# Part 1: your role (roles/design.md)" in text and "# Designer" in text
    assert "# Module asm://door: Door" in text and "## Ports: its joints" in text
    for rel in ("model/geometry/door.py", "model/geometry/door_fiber.py"):
        assert f"## {rel}\n```python\n" in text, rel
    assert "model/geometry/kiln.py" not in text  # the kiln's own code is not the door's
    assert 20_000 < size < 60_000, size


def test_verify_tells_edits_inside_the_context_from_edits_outside(
    kiln_copy: Path, tmp_path: Path
) -> None:
    mod = _script()
    work = tmp_path / "work"
    shutil.copytree(kiln_copy, work)
    assert mod.verify(work, KILN, "asm://door")["verdict"] == "no file changed"
    params = work / "model" / "parameters.yaml"
    text = params.read_text(encoding="utf-8")
    old = "door-standoff-inset: {value: 120,"
    assert old in text
    params.write_text(text.replace(old, "door-standoff-inset: {value: 115,"), encoding="utf-8")
    (work / "build").mkdir()
    (work / "build" / "anything.json").write_text("{}")  # build output never counts
    res = mod.verify(work, KILN, "asm://door")
    assert res["ok"] and res["changed"] == [
        {"file": "model/parameters.yaml", "change": "edited", "in_context": True}
    ]
    kiln_py = work / "model" / "geometry" / "kiln.py"
    kiln_py.write_text(kiln_py.read_text(encoding="utf-8") + "\n# touched\n", encoding="utf-8")
    (work / "model" / "notes.md").write_text("new")
    res = mod.verify(work, KILN, "asm://door")
    assert not res["ok"]
    assert res["outside"] == ["model/geometry/kiln.py", "model/notes.md"]
    assert res["verdict"] == "2 changed file(s) outside the context"
    assert mod.main(["--verify", str(work), str(KILN), "asm://door", "--json"]) == 1
    assert mod.main(["--verify", str(kiln_copy), str(KILN), "asm://door"]) == 2
    assert json.loads(json.dumps(res)) == res
