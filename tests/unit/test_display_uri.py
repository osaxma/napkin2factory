"""B-0008: the persona display rule for model URIs in human-facing tables and captions."""

from __future__ import annotations

import pytest

from napkin2factory.core.uris import display_uri


@pytest.mark.parametrize(
    ("uri", "owner"),
    [
        ("part://outer-shell", "outer-shell"),
        ("req://REQ-003", "REQ-003"),
        ("req://REQ-003#verify.value", "REQ-003#verify.value"),
        ("asm://kiln", "kiln"),
        ("param://wall-thickness", "wall-thickness"),
        ("dec://DEC-001", "DEC-001"),
        ("ecr://ECR-002", "ECR-002"),
        ("iface://shell-frame-mount", "shell-frame-mount"),
        ("doc://installation", "installation"),
        ("calc://thermal.skin_temperature", "thermal.skin_temperature"),
        ("part://outer-shell#3", "outer-shell#3"),
        ("asm://kiln · iso", "kiln · iso"),
        ("operator.yaml", "operator.yaml"),
        ("interference://kiln", "interference://kiln"),  # a check id, not a model URI
        ("", ""),
    ],
)
def test_owner_drops_prefix_engineer_keeps_it(uri: str, owner: str) -> None:
    assert display_uri(uri, "owner") == owner
    assert display_uri(uri, "engineer") == uri


def test_only_the_leading_scheme_is_dropped() -> None:
    sel = "rule://sheet-metal/min-flange#part://lid"
    assert display_uri(sel, "owner") == "sheet-metal/min-flange#part://lid"
