"""M8: the kiln builds clean, every artifact parses, golden assembly props hold, and (under
N2F_TIMING=1) a clean build finishes within the 10-minute budget (D30).

v0.2 M6: the kiln's napkin stage — four concept cards rebuilt on a copy screen exactly as
shipped (C-001 red on the alcove with the door swing, C-003 green), the board is
self-contained and matches its golden, and the promoted direction's requirements (the
alcove, the supply, the form rows) pass on the kiln as built.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product
from tests.conftest import EXAMPLES, copy_product, n2f
from tests.golden.test_build_examples import check_kiln_board_golden, kiln_board_fingerprint
from tests.validate_outputs import validate_outputs

pytestmark = pytest.mark.full  # make check-full (D27)

os.environ.setdefault("N2F_OFFLINE", "1")
TIMING = os.environ.get("N2F_TIMING") == "1"
GOLDEN = Path(__file__).parent.parent / "golden" / "goldens" / "kiln.json"


@pytest.fixture(scope="module")
def kiln(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, float]:
    root = copy_product(EXAMPLES / "kiln", tmp_path_factory.mktemp("kiln") / "kiln", git=True)
    t0 = time.perf_counter()
    run_build(load_product(root), quiet=True, render=True)
    return root, time.perf_counter() - t0


def test_kiln_artifacts_complete(kiln: tuple[Path, float]) -> None:
    root, _ = kiln
    assert validate_outputs(root) == []


def test_kiln_checks_green_with_example_signoffs(kiln: tuple[Path, float]) -> None:
    root, _ = kiln
    data = json.loads((root / "build/checks/checks.json").read_text())
    assert data["summary"]["fail"] == 0, [r["id"] for r in data["results"] if r["status"] == "fail"]
    assert data["summary"]["needs-human"] == 0
    # six safety requirements carry EXAMPLE sign-offs; they are counted apart from real ones (S-047)
    assert data["summary"]["example"] == 6 and data["summary"]["signed"] == 0
    signed = [r for r in data["results"] if r["status"] == "signed"]
    assert len(signed) == 6 and all("EXAMPLE" in r["message"] for r in signed)
    inter = next(r for r in data["results"] if r["id"] == "interference://kiln")
    assert inter["detail"]["interferences"] == []
    counts = next(r for r in data["results"] if r["id"] == "count://kiln")
    assert counts["status"] == "pass"
    # M3b: every unit's joint hardware is listed exactly (S-105 option A)
    hardware = {r["id"]: r["status"] for r in data["results"] if r["kind"] == "hardware"}
    assert hardware == dict.fromkeys(
        ("hardware://controls", "hardware://door", "hardware://kiln"), "pass"
    )


def test_kiln_promoted_direction_holds_on_the_kiln_as_built(kiln: tuple[Path, float]) -> None:
    """DoD 4: C-003's requirements pass on the as-built kiln; the form rows are real rows."""
    root, _ = kiln
    data = json.loads((root / "build/checks/checks.json").read_text())
    by_id = {r["id"]: r for r in data["results"]}
    reqs = load_product(root).requirements
    from_card = {rid: r for rid, r in reqs.items() if (r.source or "").startswith("concept C-003")}
    assert len(from_card) >= 4
    for rid in from_card:
        assert by_id[f"req://{rid}"]["status"] == "pass", by_id[f"req://{rid}"]
    alcove = next(r for r in from_card.values() if r.title == "Fits the alcove with the door open")
    assert alcove.verify.kind == "geometry_prop"
    assert "995.4 mm" in by_id[f"req://{alcove.id}"]["message"]
    # the door is a parameter on the designed door, not a number frozen in the bound (B-0023)
    assert "1509.7 mm" in by_id[f"req://{alcove.id}"]["message"]
    door = next(r for r in from_card.values() if r.title.startswith("The open door keeps"))
    assert door.verify.kind == "param_bound" and door.id == "REQ-027"
    assert by_id[f"req://{door.id}"]["message"] == "240.235 mm <= 240.3 mm"
    assert load_product(root).parameters["door-leaf-width"].expr == "door-guard-width"
    form = [r for r in from_card.values() if r.verify.kind == "rule"]
    assert len(form) >= 2
    rows = [r for r in data["results"] if r["id"].startswith("rule://form-v0/")]
    assert any(r["status"] == "pass" for r in rows) and not any(r["status"] == "fail" for r in rows)


def test_kiln_interfaces_meet_and_a_moved_box_fails(kiln: tuple[Path, float]) -> None:
    """DoD 2 (P3, S-106): every interface meets as built; the box moved 10 mm fails."""
    import shutil

    from napkin2factory.core.checks.interface import check_interface

    root, _ = kiln
    data = json.loads((root / "build/checks/checks.json").read_text())
    rows = [r for r in data["results"] if r["id"].startswith("iface://")]
    # nine joints, the door's two hinges and latch and the controls' lid since M3b (S-113)
    assert len(rows) == 13 and all(r["status"] == "pass" for r in rows), rows
    assert all("meet in asm://" in r["message"] for r in rows)
    assert not [r for r in data["results"] if r["id"].startswith("placement://")]
    moved = root.parent / "moved-build"
    shutil.copytree(root / "build", moved)
    inst_path = moved / "assemblies/kiln/instances.json"
    inst = json.loads(inst_path.read_text())
    box = next(i for i in inst if i["uri"] == "part://controller-box")
    box["translation"][1] += 10.0  # along the guard wall, in the frame plane
    inst_path.write_text(json.dumps(inst))
    product = load_product(root)
    rep = check_interface(product, product.interfaces["controller-mount"], moved)
    assert rep.status == "fail"
    assert "part://guard-shell#1 and part://controller-box#1" in rep.message
    assert "10.0 mm apart" in rep.message


#: The door's working context (P6, S-114): the key set an agent's tools may rely on.
DOOR_CONTEXT_KEYS = {
    "": [
        "assemblies", "build", "commands", "files", "inside", "joints_inside", "module",
        "name", "parameters", "parts", "ports", "requirements", "shared_parts",
        "sub_assemblies", "title", "why",
    ],
    "parameters": ["built", "note", "outside", "own"],
    "parameters.own": ["description", "export", "expr", "param", "unit", "value"],
    "parameters.outside": ["export", "param", "read_by", "scope", "value"],
    "parts": ["file", "geometry", "id", "kind", "name", "qty", "yaml"],
    "ports": [
        "closes_in", "description", "file", "hardware", "iface", "kind", "offset", "parties",
    ],
    "ports.parties": ["frame", "home", "inside", "name", "part"],
    "requirements": [
        "allocated", "checked_here", "id", "safety", "statement", "target", "title", "verify",
    ],
    "commands": ["build", "check"],
}  # fmt: skip


def _keys(data: dict[str, Any]) -> dict[str, list[str]]:
    out = {"": sorted(data)}
    for path in DOOR_CONTEXT_KEYS:
        if not path:
            continue
        cur: Any = data
        for part in path.split("."):
            cur = cur[part] if isinstance(cur, dict) else cur[0][part]
        out[path] = sorted(cur if isinstance(cur, dict) else cur[0])
    return out


def test_kiln_modules_stay_within_reach_and_check_alone(kiln: tuple[Path, float]) -> None:
    """DoD 3, 5 (P5, P6, P12, S-114): no read across units; the door checks and reads alone."""
    root, _ = kiln
    data = json.loads((root / "build/checks/checks.json").read_text())
    reach = {r["id"]: r["status"] for r in data["results"] if r["kind"] == "reach"}
    assert reach == dict.fromkeys(("reach://controls", "reach://door", "reach://kiln"), "pass")
    assert [g["id"] for g in data["matrix"]["modules"]] == ["controls", "door", "kiln", None]
    before = (root / "build/checks/checks.json").read_bytes()
    scoped = n2f("check", "--scope", "asm://door", "--json", cwd=root)
    assert scoped.returncode == 0, scoped.stderr
    door = json.loads(scoped.stdout)
    assert door["summary"]["fail"] == 0 and door["scope"] == "asm://door"
    assert {"iface://door-guard-standoff", "hardware://door", "reach://door"} <= {
        r["id"] for r in door["results"]
    }
    assert (root / "build/checks/checks.json").read_bytes() == before
    res = n2f("context", "asm://door", "--json", cwd=root)
    assert res.returncode == 0, res.stderr
    ctx = json.loads(res.stdout)
    assert _keys(ctx) == DOOR_CONTEXT_KEYS
    assert [p["iface"] for p in ctx["ports"]] == [
        "iface://hinge-lower",
        "iface://hinge-upper",
        "iface://latch-catch",
    ]
    exported = {p["param"] for p in ctx["parameters"]["own"] if p["export"]}
    assert exported == {
        "door-guard-width",
        "door-guard-depth",
        "door-guard-offset",
        "hinge-pin-depth",
    }
    assert ctx["parameters"]["built"] and "hinge-spacing" in {
        p["param"] for p in ctx["parameters"]["outside"]
    }


def test_kiln_golden_props(kiln: tuple[Path, float]) -> None:
    """Assembly fingerprint (D14): mass, bbox, instance count; regenerate via `make goldens`."""
    root, _ = kiln
    props = json.loads((root / "build/assemblies/kiln/props.json").read_text())
    fp = {
        "mass": round(props["mass"], 2),
        "bbox": [round(props["bbox"][k], 1) for k in ("x", "y", "z")],
        "instances": props["instances"],
        "parts": sorted(props["instance_counts"]),
    }
    if os.environ.get("N2F_UPDATE_GOLDENS") == "1" or not GOLDEN.is_file():
        GOLDEN.write_text(json.dumps(fp, indent=2) + "\n")
        if os.environ.get("N2F_UPDATE_GOLDENS") != "1":
            pytest.skip("kiln golden recorded for the first time; re-run to compare")
    want = json.loads(GOLDEN.read_text())
    assert abs(fp["mass"] - want["mass"]) <= 0.01 * want["mass"]
    assert all(abs(a - b) <= 0.5 for a, b in zip(fp["bbox"], want["bbox"], strict=True))
    assert fp["instances"] == want["instances"] and fp["parts"] == want["parts"]


def test_kiln_report_budget(kiln: tuple[Path, float]) -> None:
    root, _ = kiln
    size = (root / "build/report/index.html").stat().st_size
    assert size <= 20 * 1024 * 1024, f"report is {size / 1e6:.1f} MB (D13 budget 20 MB)"


def test_kiln_report_lists_the_joints_between_units(kiln: tuple[Path, float]) -> None:
    """P13 (M6): the four ports, each with its units, parts, kind, hardware and verdict."""
    import re

    from selectolax.lexbor import LexborHTMLParser

    root, _ = kiln
    html = (root / "build/report/index.html").read_text(encoding="utf-8")
    assert not re.search(r"\b(?:src|href)\s*=\s*['\"]?(?:https?:)?//", html)  # D13
    section = LexborHTMLParser(html).css_first("#joints")
    assert section is not None
    rows = {r.attributes["id"]: r for r in section.css("tbody tr")}
    assert set(rows) == {
        "joint-controller-mount",
        "joint-hinge-lower",
        "joint-hinge-upper",
        "joint-latch-catch",
    }
    for rid, row in rows.items():
        text = " ".join(row.text().split())
        unit = "Controls" if rid == "joint-controller-mount" else "Door"
        assert f"Mini electric test kiln and {unit}" in text, text
        assert row.css_first(".badge.pass") is not None, text  # placed, the parts meet
        assert "meet in asm://kiln" in text, text
        assert "DEC-019" in text, text  # the decision that made the door and controls units
    mount = " ".join(rows["joint-controller-mount"].text().split())
    assert "bolted, 4 holes" in mount
    assert "4 × M6 female-female hex standoff, 40 mm" in mount and "8 × M6 x 16" in mount
    hinge = " ".join(rows["joint-hinge-lower"].text().split())
    assert "Hinge post (steel angle)" in hinge and "faces that meet (welded" in hinge
    assert "none" in hinge  # no loose hardware on a welded hinge


@pytest.mark.timing
@pytest.mark.skipif(not TIMING, reason="timing assertions run only under N2F_TIMING=1 (D30)")
def test_kiln_clean_build_under_ten_minutes(kiln: tuple[Path, float]) -> None:
    _, seconds = kiln
    assert seconds < 600, f"clean kiln build took {seconds:.0f} s (budget 600 s, DoD item 3)"


# --- the napkin stage (v0.2 M6) ------------------------------------------------------------


@pytest.fixture(scope="module")
def kiln_concepts(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A copy of the kiln with every card rebuilt (rejected ones too) and the board written."""
    from napkin2factory.concepts.build import build_concepts
    from napkin2factory.core import concepts as cm

    root = copy_product(EXAMPLES / "kiln", tmp_path_factory.mktemp("napkin") / "kiln", git=False)
    built, errors = build_concepts(root, list(cm.load_concepts(root).values()))
    assert errors == [] and len(built) == 4
    r = n2f("concept", "board", cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    return root


def test_kiln_cards_rebuild_exactly_as_shipped(kiln_concepts: Path) -> None:
    """DoD 3: one red card with the door-swing reason, three green, every number labelled."""
    from napkin2factory.core import concepts as cm

    shipped = cm.load_concepts(EXAMPLES / "kiln")
    rebuilt = cm.load_concepts(kiln_concepts)
    assert sorted(rebuilt) == ["C-001", "C-002", "C-003", "C-004"]
    for cid, card in rebuilt.items():
        sc, was = card.screening, shipped[cid].screening
        assert sc is not None and was is not None
        assert sc.verdict == was.verdict, cid
        assert {k: v.value for k, v in sc.values.items()} == {
            k: v.value for k, v in was.values.items()
        }, f"{cid}: the shipped screening is stale; rebuild the cards in place"
        assert [(r.id, r.status, r.message) for r in sc.rules] == [
            (r.id, r.status, r.message) for r in was.rules
        ]
        for section, label in (
            ("given", "given"),
            ("computed", "computed"),
            ("estimates", "estimate"),
        ):
            assert all(v.label == label for v in getattr(sc, section).values()), (cid, section)
    c1 = rebuilt["C-001"].screening
    assert c1 is not None and c1.verdict == "red"
    assert [r.id for r in c1.failing] == ["fits-site-width"]
    reason = c1.failing[0].message
    assert "995 mm for the body plus 240 mm for the open door" in reason  # 110° door (B-0029)
    assert "alcove is 800 mm" in reason
    assert c1.estimates["heat_up_time"].value == "4.4 h"  # not DEC-004's planned 7 h
    assert rebuilt["C-003"].verdict == "green"


def test_kiln_board_matches_its_golden(kiln_concepts: Path) -> None:
    from selectolax.lexbor import LexborHTMLParser

    board = kiln_concepts / "build/concepts/board.html"
    assert board.stat().st_size <= 20 * 1024 * 1024
    assert validate_outputs(kiln_concepts, "concepts") == []
    html = board.read_text(encoding="utf-8")
    tree = LexborHTMLParser(html)
    assert [a.attributes.get("data-verdict") for a in tree.css("article.concept")] == [
        "red",
        "green",
        "green",
        "green",
    ]
    fp = kiln_board_fingerprint(kiln_concepts)
    # the page shows exactly the labelled numbers the fingerprint counts
    for label, count in fp["labels"].items():
        assert len(tree.css(f"dd span.lbl.{label}")) == count, label
    assert fp["problems"]["C-001"][0] in tree.css_first("#card-C-001 .limits.bad").text()
    check_kiln_board_golden(fp)
