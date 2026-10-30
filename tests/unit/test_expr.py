import pytest

from napkin2factory.core.expr import ExprError, evaluate, referenced_names
from napkin2factory.core.units import parse_quantity as q


def test_hyphenated_names_and_spaces_for_minus():
    vals = {"brick-thickness": q("65 mm"), "fiber-thickness": q("50 mm")}
    assert evaluate("brick-thickness + fiber-thickness", vals).to("mm").magnitude == 115
    assert evaluate("brick-thickness - fiber-thickness", vals).to("mm").magnitude == 15
    assert referenced_names("brick-thickness + 2 * fiber-thickness") == [
        "brick-thickness",
        "fiber-thickness",
    ]


def test_functions_and_numbers():
    vals = {"a": q("3 mm"), "b": q("4 mm")}
    assert evaluate("sqrt(a*a + b*b)", vals).to("mm").magnitude == pytest.approx(5)
    assert evaluate("max(a, b) * 2", vals).to("mm").magnitude == 8
    assert evaluate("ceil(a / 2)", vals).magnitude == 2


def test_unknown_name():
    with pytest.raises(ExprError, match="unknown parameter 'zz'"):
        evaluate("zz + 1", {})


@pytest.mark.parametrize(
    "bad", ["__import__('os')", "a.b", "a[0]", "lambda: 1", "open('x')", "a if a else b"]
)
def test_disallowed(bad):
    with pytest.raises(ExprError):
        evaluate(bad, {"a": q("1 mm"), "b": q("1 mm")})


def test_lookup_records_reads():
    seen = []

    def lookup(name):
        seen.append(name)
        return q("1 mm")

    evaluate("a + b + a", {}, lookup=lookup)
    assert seen == ["a", "b", "a"]
