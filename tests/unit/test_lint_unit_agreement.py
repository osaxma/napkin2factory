"""Lint L5: a verify bound with no unit (a safety factor) is not compared with the statement.

Spec trial 1 (B-0238, S-233): the test stand's factor requirements ("at least 2", whose
statements quote a load in newtons) drew L5 warnings for a unit the bound never had.
"""

from __future__ import annotations

from napkin2factory.core.lint import lint
from napkin2factory.core.loader import load_product
from napkin2factory.core.units import parse_quantity
from tests.conftest import EXAMPLES

RULE = "L5-units-agree"


def test_a_dimensionless_bound_draws_no_unit_warning() -> None:
    product = load_product(EXAMPLES / "test-stand")
    req = product.requirements["REQ-010"]
    assert req.verify is not None and str(req.verify.value.units) == "dimensionless"
    assert "N" in req.statement  # it quotes a load; the bound is a factor
    assert not [p for p in lint(product).items if p.rule == RULE]


def test_a_bound_in_the_wrong_unit_still_warns() -> None:
    product = load_product(EXAMPLES / "test-stand")
    req = product.requirements["REQ-010"]
    assert req.verify is not None
    verify = req.verify.model_copy(update={"value": parse_quantity("5 mm")})
    product.requirements["REQ-010"] = req.model_copy(update={"verify": verify})
    hits = [p for p in lint(product).items if p.rule == RULE]
    assert [p.subject for p in hits] == ["req://REQ-010"]
