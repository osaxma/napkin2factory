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


def test_build_plan_steps_parse_even_for_a_unit_named_with_a_digit() -> None:
    """Gate C, B1: ``bom://build-plan`` parses; a later selector segment may start with a digit."""
    u = Uri.parse("bom://build-plan#units.2-stage")
    assert (u.id, u.selector) == ("build-plan", ("units", "2-stage"))
    assert Uri.parse("part://x#3").instance == 3  # an all-digit fragment is still an instance


def test_find_uris_finds_a_registered_domains_scheme() -> None:
    """B-0075 (S-129): prose naming a domain's object is found, so the lint checks it."""
    from napkin2factory.core.registry import installed
    from tests.fixtures.domains import toy

    text = "The glow of toy://widget#glow sits on part://plate, not on glim://x."
    with installed(toy.DOMAIN):
        assert [str(u) for u in find_uris(text)] == ["toy://widget#glow", "part://plate"]


def test_the_manifest_is_a_uri_but_not_a_reference_in_prose() -> None:
    """B-0083 (S-129): ``n2f impact --set manifest://scope#…`` parses; prose never cites it."""
    u = Uri.parse("manifest://scope#electrical.state")
    assert (u.scheme, u.id, u.selector) == ("manifest", "scope", ("electrical", "state"))
    assert str(Uri.parse("manifest://product#name")) == "manifest://product#name"
    with pytest.raises(UriError, match="not a valid manifest id"):
        Uri.parse("manifest://parts")
    assert find_uris("its scope is manifest://scope#electrical") == []
