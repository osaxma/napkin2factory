"""Lint L17: an earlier style-role word is read for one version, and lint says so.

Gate E, C8 (S-137): ``role: door`` and a ``stand:`` palette key were read as ``opening`` and
``support`` with no notice, against ``docs/schema-policy.md``. The kiln still writes them.
"""

from __future__ import annotations

from napkin2factory.core.lint import ROLE_ALIAS_RULE, lint
from napkin2factory.core.loader import load_product
from napkin2factory.core.model.style import alias_uses
from tests.conftest import EXAMPLES


def test_the_role_aliases_are_named_by_lint() -> None:
    found = {
        (p.subject, p.message)
        for p in lint(load_product(EXAMPLES / "kiln")).items
        if p.rule == ROLE_ALIAS_RULE
    }
    assert (
        "part://door-guard",
        "role: door is read as role: opening for this version only",
    ) in found
    assert (
        "palette.stand",
        "palette.stand is read as palette.support for this version only",
    ) in found
    assert ("finish.door", "finish.door is read as finish.opening for this version only") in found
    every = [p for p in lint(load_product(EXAMPLES / "kiln")).items if p.rule == ROLE_ALIAS_RULE]
    assert all(p.severity == "warn" for p in every)


def test_a_product_with_the_table_words_gets_no_notice() -> None:
    assert not [
        p for p in lint(load_product(EXAMPLES / "bracket")).items if p.rule == ROLE_ALIAS_RULE
    ]


def test_alias_uses_reads_the_raw_file() -> None:
    raw = {"palette": {"door": "#fff", "body": "#000"}, "finish": {"stand": "painted"}}
    assert alias_uses(raw) == [
        ("palette.door", "door", "opening"),
        ("finish.stand", "stand", "support"),
    ]
    assert alias_uses(None) == [] and alias_uses({"palette": "x"}) == []
