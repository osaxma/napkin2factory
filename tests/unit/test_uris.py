import pytest

from napkin2factory.core.uris import Uri, UriError, find_uris, is_uri, slug_to_module


@pytest.mark.parametrize(
    "text, scheme, ident, selector, instance",
    [
        ("req://REQ-014", "req", "REQ-014", (), None),
        ("param://wall-thickness", "param", "wall-thickness", (), None),
        ("part://outer-shell#props.bbox.x", "part", "outer-shell", ("props", "bbox", "x"), None),
        ("part://outer-shell#3", "part", "outer-shell", (), 3),
        ("req://REQ-001#verify.value", "req", "REQ-001", ("verify", "value"), None),
        ("calc://thermal.skin_temperature", "calc", "thermal.skin_temperature", (), None),
        ("rule://sheet-metal/min-bend-radius", "rule", "sheet-metal/min-bend-radius", (), None),
        ("bom://rollups#total_cost", "bom", "rollups", ("total_cost",), None),
        ("doc://installation#power", "doc", "installation", ("power",), None),
    ],
)
def test_parse(text, scheme, ident, selector, instance):
    u = Uri.parse(text)
    assert (u.scheme, u.id, u.selector, u.instance) == (scheme, ident, selector, instance)
    assert str(u) == text
    assert u.key() == text


@pytest.mark.parametrize(
    "bad",
    [
        "REQ-014",
        "req://REQ-14",
        "req://req-014",
        "part://Outer-Shell",
        "part://outer--shell",
        "part://-x",
        "foo://bar",
        "part://x#0",
        "part://x#a..b",
        "part://x y",
        "ecr://ECR-1",
    ],
)
def test_reject(bad):
    with pytest.raises(UriError):
        Uri.parse(bad)
    assert not is_uri(bad)


def test_base_and_with_selector():
    u = Uri.parse("part://a#props.mass")
    assert str(u.base) == "part://a"
    assert str(u.with_selector("rev")) == "part://a#rev"


def test_find_uris_in_prose():
    text = "See req://REQ-003 and part://outer-shell#props.mass, also (param://x)."
    assert [str(u) for u in find_uris(text)] == [
        "req://REQ-003",
        "part://outer-shell#props.mass",
        "param://x",
    ]


def test_slug_to_module():
    assert slug_to_module("outer-shell") == "outer_shell"
