"""The row an assembly without a module gets keeps neighbours apart (S-241)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from napkin2factory.geometry.build_asm import _auto_layout


def _built(lo: float, hi: float) -> Any:
    return SimpleNamespace(props={"bbox": {"x": hi - lo, "min": [lo, 0, 0], "max": [hi, 0, 0]}})


def _child(pid: str, qty: int = 1) -> Any:
    return SimpleNamespace(part=SimpleNamespace(id=pid), asm=None, qty=qty, uri=f"part://{pid}")


def _faces(children: list[Any], parts: dict[str, Any]) -> list[tuple[float, float]]:
    """The (near, far) x face of every placed instance, in placement order."""
    res = _auto_layout(SimpleNamespace(children=children), parts, {})  # type: ignore[arg-type]
    out = []
    for inst in res.instances:
        key = inst.uri.removeprefix("part://")
        x = inst.location.position.X
        out.append((x + parts[key].props["bbox"]["min"][0], x + parts[key].props["bbox"]["max"][0]))
    return out


def test_a_wide_part_after_a_narrow_one_does_not_overlap_it() -> None:
    parts = {"narrow": _built(-5, 5), "wide": _built(-100, 100)}  # centred, 10 and 200 wide
    (a0, a1), (b0, b1) = _faces([_child("narrow"), _child("wide")], parts)
    assert b0 - a1 == 20.0  # the gap, whatever the widths


def test_parts_not_centred_and_repeats_keep_the_gap() -> None:
    parts = {"a": _built(0, 40), "b": _built(-30, 10)}
    faces = _faces([_child("a", 2), _child("b")], parts)
    assert [round(n - f, 6) for (_, f), (n, _) in zip(faces, faces[1:], strict=False)] == [20, 20]
