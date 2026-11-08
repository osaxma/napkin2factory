"""Unit tests for the M2 report inspector index and multi-assembly GLB embedding."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from napkin2factory.core.domain import SectionContext
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.graph.values import unvalued_reads, value_of
from napkin2factory.core.loader import Product, load_product
from napkin2factory.core.uris import Uri
from napkin2factory.domains.electrical.owner.inspector import electrical_inspector
from napkin2factory.geometry.accessors import ReadLog
from napkin2factory.report.builder import gather, render_report
from napkin2factory.report.inspector import inspector_index, inspector_json
from tests.conftest import EXAMPLES, copy_product

ALLOWED_SCHEMES = frozenset(
    {
        "manifest",
        "part",
        "asm",
        "iface",
        "req",
        "rule",
        "doc",
        "supply",
        "device",
        "circuit",
        "conductor",
    }
)
FORBIDDEN_SCHEMES = frozenset({"ifc", "elec", "product"})
MINIMAL_ELEC = Path(__file__).resolve().parents[1] / "fixtures" / "electrical" / "minimal"


@pytest.fixture(scope="module")
def built_bracket(
    tmp_path_factory: pytest.TempPathFactory, _prebuilt_root: None
) -> Iterator[Product]:
    """Prebuilt bracket copy (no renders, no kiln)."""
    dst = copy_product(
        EXAMPLES / "bracket",
        tmp_path_factory.mktemp("m2_bracket") / "bracket",
        prebuilt=True,
        render=False,
    )
    yield load_product(dst)


@pytest.fixture(scope="module")
def built_enclosure(
    tmp_path_factory: pytest.TempPathFactory, _prebuilt_root: None
) -> Iterator[Product]:
    """Prebuilt enclosure copy (no renders, no kiln)."""
    dst = copy_product(
        EXAMPLES / "enclosure",
        tmp_path_factory.mktemp("m2_enclosure") / "enclosure",
        prebuilt=True,
        render=False,
    )
    yield load_product(dst)


def test_inspector_index_completeness_and_schemes(
    built_bracket: Product, built_enclosure: Product
) -> None:
    """Every product URI has an entry and no key uses a forbidden or unknown scheme (5a)."""
    for prod in (built_bracket, built_enclosure):
        data = gather(prod, prod.paths.build, "2026-10-30")
        idx = data["inspector_index"]

        assert "manifest://product" in idx
        for k in idx:
            uri = Uri.parse(k)
            assert uri.scheme in ALLOWED_SCHEMES, f"disallowed scheme in {k}"
            assert uri.scheme not in FORBIDDEN_SCHEMES

        for pid in prod.parts:
            assert f"part://{pid}" in idx
        for aid in prod.assemblies:
            assert f"asm://{aid}" in idx
        for iid in prod.interfaces:
            assert f"iface://{iid}" in idx
        for rid in prod.requirements:
            assert f"req://{rid}" in idx
        for did in prod.docs:
            assert f"doc://{did}" in idx

        # Vitals on manifest://product carry given/computed/estimate labels.
        prod_entry = idx["manifest://product"]
        assert prod_entry["kind"] == "product"
        assert prod_entry["name"] == prod.manifest.product.name
        for vital_key in ("part_count", "total_mass", "total_cost", "open_choices"):
            vital = prod_entry["vitals"][vital_key]
            assert vital["label"] in ("given", "computed", "estimate")
        assert prod_entry["vitals"]["open_choices"]["label"] == "given"
        assert isinstance(prod_entry["vitals"]["open_choices"]["raw"], int)
        if "envelope" in prod_entry["vitals"]:
            env = prod_entry["vitals"]["envelope"]
            assert env["label"] == "computed"
            assert isinstance(env["raw"], list) and len(env["raw"]) == 3
            assert all(isinstance(v, (int, float)) for v in env["raw"])
            assert " × " in env["value"] and " mm" in env["value"]
        assert prod_entry["unit_uris"]
        assert all(u.startswith("asm://") for u in prod_entry["unit_uris"])
        for param in prod_entry["parameters"]:
            assert param["kind"] in ("given", "computed")

        # Assembly entry shape.
        for aid in prod.assemblies:
            a_entry = idx[f"asm://{aid}"]
            assert a_entry["kind"] == "assembly"
            assert isinstance(a_entry["part_count"], int)
            assert "bom_cost" in a_entry
            assert "children" in a_entry and isinstance(a_entry["children"], list)
            for ch in a_entry["children"]:
                assert "uri" in ch and "qty" in ch
                assert isinstance(ch["qty"], int) and ch["qty"] >= 1
            sheet_svg = prod.paths.build / "drawings" / "assemblies" / f"{aid}.svg"
            assert ("sheet" in a_entry) == sheet_svg.is_file()
            for st in a_entry.get("build_steps", []):
                assert "sheet_svg" not in st  # no duplicate SVG embedded

        # Part entry shape, artifacts, drawings, COTS supplier/MPN, traces.
        for pid, part in prod.parts.items():
            p_entry = idx[f"part://{pid}"]
            assert p_entry["kind"] == "part"
            assert p_entry["process"] == part.process
            # Only existing files in artifacts; never STL.
            for rel_path in p_entry["artifacts"].values():
                assert not rel_path.endswith(".stl")
                assert (prod.paths.root / rel_path).is_file()
            drawn = (prod.paths.build / "drawings" / f"{pid}.svg").is_file()
            assert ("drawing_id" in p_entry) == drawn
            assert ("drawing_anchor" in p_entry) == drawn
            if drawn:
                assert p_entry["drawing_anchor"] == f"drawing-{pid}"
            if part.source is not None:
                assert p_entry["supplier"] == part.source.vendor
                assert p_entry["mpn"] == part.source.mpn
            for chk in p_entry["checks"]:
                assert chk["uri"].startswith("rule://")
                assert chk["status"] in ("pass", "fail", "warn", "skip")

        # Requirements and rules carry status and message.
        for rid in prod.requirements:
            r_entry = idx[f"req://{rid}"]
            assert r_entry["kind"] == "requirement"
            assert "allocation" in r_entry and "satisfied_by" in r_entry
            assert "status" in r_entry and "message" in r_entry
        rule_entries = [v for k, v in idx.items() if k.startswith("rule://")]
        assert rule_entries
        for rl in rule_entries:
            assert rl["kind"] == "rule"
            assert "status" in rl and "message" in rl


def test_embedded_json_matches_inspector_index_and_size_budget(
    built_bracket: Product, built_enclosure: Product
) -> None:
    """Embedded #inspector-index JSON equals inspector_index() and grows report by <5% (5b)."""
    # Verify escaping of </ and <!-- in inspector_json.
    tricky = {"manifest://product": {"kind": "product", "note": "</script><!-- trick -->"}}
    raw_json = inspector_json(tricky)
    assert "</" not in raw_json
    assert "<!--" not in raw_json
    assert json.loads(raw_json) == tricky

    for prod in (built_bracket, built_enclosure):
        sctx = SectionContext(prod, prod.paths.build)
        direct = inspector_index(sctx)
        html = render_report(prod, prod.paths.build, "2026-10-30")
        tree = HTMLParser(html)
        script = tree.css_first("script#inspector-index")
        assert script is not None
        assert script.attributes.get("type") == "application/json"
        embedded = json.loads(script.text())
        assert embedded == direct

        # Size comparison: report with vs without the embedded inspector script tag.
        after_bytes = len(html.encode("utf-8"))
        script_tag_bytes = len(script.html.encode("utf-8")) + 1
        before_bytes = after_bytes - script_tag_bytes
        growth = (after_bytes - before_bytes) / before_bytes
        assert growth < 0.05, f"{prod.manifest.product.id} grew by {growth:.2%}"


def test_recorded_reads_track_shown_part_fields(built_bracket: Product, tmp_path: Path) -> None:
    """Every shown field is read through sctx.proxy and changing a field changes reads (2)."""
    log = ReadLog()
    render_report(built_bracket, built_bracket.paths.build, "2026-10-30", log=log)
    recorded = set(log.keys)
    pid = next(iter(built_bracket.parts))
    puri = f"part://{pid}"
    assert {
        "manifest://product#name",
        f"{puri}#name",
        f"{puri}#process",
        f"{puri}#finish",
        f"{puri}#material.name",
        f"{puri}#interfaces",
        f"{puri}#satisfies",
    } <= recorded
    assert unvalued_reads(built_bracket, built_bracket.paths.build) == {}

    # Mutate a shown part field (finish / source) on a copy and verify the recorded read
    # set and valued read change accordingly.
    dst = copy_product(built_bracket.paths.root, tmp_path / "mutated", git=False)
    shutil.copytree(built_bracket.paths.build, dst / "build")
    part_yaml = dst / "model" / "parts" / f"{pid}.yaml"
    text = part_yaml.read_text(encoding="utf-8")
    part_yaml.write_text(
        text + "\nfinish: powder-coat-black\nsource:\n  vendor: McMaster-Carr\n  mpn: 91292A115\n",
        encoding="utf-8",
    )
    mutated = load_product(dst)
    manifest = Manifest.load(mutated.paths.build)
    log2 = ReadLog()
    sctx2 = SectionContext(mutated, mutated.paths.build)
    sctx2.log = log2
    idx2 = inspector_index(sctx2)
    assert idx2[puri]["finish"] == "powder-coat-black"
    assert idx2[puri]["supplier"] == "McMaster-Carr"
    assert f"{puri}#source.vendor" in log2.keys
    assert f"{puri}#source.mpn" in log2.keys
    assert value_of(
        built_bracket, manifest, built_bracket.paths.build, f"{puri}#finish"
    ) != value_of(mutated, manifest, mutated.paths.build, f"{puri}#finish")


def test_two_top_assemblies_embed_two_glbs(
    built_enclosure: Product, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A product with two top assemblies embeds two GLBs and renders two viewer divs (4, 5c)."""
    from napkin2factory.bom import rollups as rollups_mod
    from napkin2factory.core.model.assemblies import Assembly, Exploded

    first_id = next(iter(built_enclosure.assemblies))
    second_id = "second-top"
    second_glb_dir = built_enclosure.paths.build / "assemblies" / second_id
    second_glb_dir.mkdir(parents=True, exist_ok=True)
    second_glb_dir.joinpath("model.glb").write_bytes(b"glTF-second-unit")

    monkeypatch.setitem(
        built_enclosure.assemblies,
        second_id,
        Assembly(
            id=second_id,
            name="Second Unit",
            exploded=Exploded(axis="x", spacing="120 mm"),
        ),
    )
    monkeypatch.setattr(rollups_mod, "top_assemblies", lambda _p: [first_id, second_id])

    data = gather(built_enclosure, built_enclosure.paths.build, "2026-10-30")
    assert len(data["glbs"]) == 2
    assert [g["id"] for g in data["glbs"]] == [first_id, second_id]
    assert data["glb_b64"] == data["glbs"][0]["b64"]

    html = render_report(built_enclosure, built_enclosure.paths.build, "2026-10-30")
    tree = HTMLParser(html)
    v1 = tree.css_first("#viewer")
    v2 = tree.css_first(f"#viewer-{second_id}")
    d1 = tree.css_first("#glb-data")
    d2 = tree.css_first(f"#glb-data-{second_id}")
    assert v1 is not None and d1 is not None
    assert v2 is not None and d2 is not None
    assert v1.attributes.get("data-n2f-glb") == "glb-data"
    assert v2.attributes.get("data-n2f-glb") == f"glb-data-{second_id}"
    assert v2.attributes.get("data-explode-axis") == "x"
    assert v2.attributes.get("data-explode-spacing") == "120.0"
    assert d2.text() == data["glbs"][1]["b64"]


def test_electrical_inspector_hook(built_bracket: Product, tmp_path: Path) -> None:
    """Electrical hook returns {} on bracket and domain entries on electrical (3, 5d)."""
    assert electrical_inspector(SectionContext(built_bracket, built_bracket.paths.build)) == {}

    dst = copy_product(MINIMAL_ELEC, tmp_path / "elec", git=False)
    cond_yaml = dst / "model" / "electrical" / "conductors" / "custom-ptfe-2p5.yaml"
    cond_yaml.parent.mkdir(parents=True, exist_ok=True)
    cond_yaml.write_text(
        "id: custom-ptfe-2p5\n"
        "label: 2.5 mm² PTFE\n"
        "kind: high-temp\n"
        "csa: 2.5 mm^2\n"
        "ampacity: 24 A\n"
        "ambient: 30 degC\n"
        "max_temp: 200 degC\n"
        "insulation: PTFE\n"
        "source: IEC 60364-5-52 table B.52.2\n"
        "verify: true\n",
        encoding="utf-8",
    )
    prod = load_product(dst)
    log = ReadLog()
    sctx = SectionContext(prod, prod.paths.build)
    sctx.log = log

    entries = electrical_inspector(sctx)
    assert "supply://supply" in entries
    assert "device://switch" in entries
    assert "circuit://heater" in entries
    assert "conductor://custom-ptfe-2p5" in entries

    assert entries["supply://supply"]["kind"] == "supply"
    assert entries["supply://supply"]["terminals"] == ["L", "N", "PE"]
    assert entries["device://switch"]["kind"] == "device"
    assert entries["device://switch"]["part"] == "part://switch"
    assert "voltage" in entries["device://switch"]["ratings"]
    assert entries["circuit://heater"]["kind"] == "circuit"
    assert entries["circuit://heater"]["cables"]
    assert entries["conductor://custom-ptfe-2p5"]["kind"] == "conductor"
    assert "csa" in entries["conductor://custom-ptfe-2p5"]["ratings"]

    # Model reads went through sctx.proxy.
    recorded = set(log.keys)
    assert {
        "supply://supply#voltage",
        "device://switch#part",
        "device://switch#terminals",
        "circuit://heater#purpose",
        "conductor://custom-ptfe-2p5#csa",
    } <= recorded
