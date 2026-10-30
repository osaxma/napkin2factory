from pathlib import Path

from napkin2factory.core.graph.export import graph_data, to_dot, to_json
from napkin2factory.core.graph.hashing import combine, sha256_json, sha256_text, sha256_tree
from napkin2factory.core.graph.impact import next_rev, parse_set
from napkin2factory.core.graph.manifest import Entry, Manifest
from napkin2factory.core.graph.rules import TARGET_KINDS, build_rules, rules_for_target
from napkin2factory.core.loader import load_product
from tests.conftest import EXAMPLES


def test_rule_order_and_targets():
    product = load_product(EXAMPLES / "enclosure")
    rules = build_rules(product)
    ids = [r.id for r in rules]
    assert ids[0] == "validate" and ids[-3:] == ["checks", "report", "site"]
    assert (
        ids.index("part:lid")
        < ids.index("asm:enclosure")
        < ids.index("drawing:lid")
        < ids.index("bom")
        < ids.index("doc:assembly")
    )
    geo = [r.id for r in rules_for_target(rules, "geometry")]
    assert geo == ["validate", "part:base", "part:bracket", "part:lid", "asm:enclosure"]
    only = [r.id for r in rules_for_target(rules, "drawings", only_part="lid")]
    assert only == ["validate", "part:lid", "drawing:lid"]
    assert set(TARGET_KINDS["all"]) == {
        "validate",
        "part",
        "asm",
        "drawing",
        "bom",
        "doc",
        "checks",
        "report",
        "site",
    }


def test_declared_inputs_change_with_source(tmp_path: Path):
    product = load_product(EXAMPLES / "enclosure")
    before = {r.id: r.inputs for r in build_rules(product)}
    assert before["part:base"]["code"] != before["part:lid"]["code"]  # different kits
    assert before["part:base"]["code"] == build_rules(product)[1].inputs["code"]  # deterministic


def test_manifest_roundtrip_and_corruption(tmp_path: Path):
    m = Manifest()
    m.entries["x"] = Entry(
        key="k", reads=["param://a"], outputs={"a.txt": "sha256:1"}, output_hash="h", duration=0.1
    )
    m.save(tmp_path)
    back = Manifest.load(tmp_path)
    assert back.entries["x"].reads == ["param://a"]
    (tmp_path / ".n2f" / "manifest.json").write_text("{not json")
    assert Manifest.load(tmp_path).entries == {}
    assert Manifest.load(tmp_path / "nope").entries == {}


def test_hashing_helpers(tmp_path: Path):
    (tmp_path / "a.yaml").write_text("a: 1")
    (tmp_path / "b.py").write_text("x = 1")
    (tmp_path / "c.bin").write_bytes(b"\x00")
    h1 = sha256_tree(tmp_path)
    (tmp_path / "c.bin").write_bytes(b"\x01")  # not a tracked suffix
    assert sha256_tree(tmp_path) == h1
    (tmp_path / "a.yaml").write_text("a: 2")
    assert sha256_tree(tmp_path) != h1
    assert combine({"b": "2", "a": "1"}) == combine({"a": "1", "b": "2"})
    assert sha256_json({"a": [1, 2]}) == sha256_json({"a": [1, 2]})
    assert sha256_text("x").startswith("sha256:")


def test_next_rev_and_parse_set():
    assert (
        next_rev("A") == "B"
        and next_rev("Z") == "AA"
        and next_rev("AZ") == "BA"
        and next_rev("3") == "4"
    )
    e = parse_set("param://x=50 mm")
    assert str(e.set) == "param://x" and e.to == "50 mm"
    e2 = parse_set("req://REQ-001#verify.value=250mm")
    assert e2.set.selector == ("verify", "value")


def test_graph_export_static(tmp_path: Path):
    product = load_product(EXAMPLES / "enclosure")
    data = graph_data(product, build_dir=tmp_path)  # no manifest → static edges only
    ids = {n["id"] for n in data["nodes"]}
    assert "asm:enclosure" in ids and all(not n["built"] for n in data["nodes"])
    assert {"from": "part:lid", "to": "asm:enclosure"} in data["edges"]
    dot = to_dot(data)
    assert dot.startswith("digraph n2f") and '"part:lid" -> "asm:enclosure"' in dot
    around = graph_data(product, build_dir=tmp_path, around="part://lid")
    assert {n["id"] for n in around["nodes"]} >= {"part:lid", "asm:enclosure", "drawing:lid"}
    assert "part:base" not in {n["id"] for n in around["nodes"]}
    assert '"nodes"' in to_json(data)
