"""A part's home and the ports a joint needs (P4, P5; S-107)."""

from __future__ import annotations

from napkin2factory.core.loader import load_product
from napkin2factory.core.model import Assembly
from napkin2factory.core.tree import AssemblyTree
from tests.conftest import EXAMPLES


def _tree(spec: dict[str, list[str]]) -> AssemblyTree:
    """``{"top": ["part://a", "asm://door"], ...}`` → a tree of assemblies."""
    asms = {}
    for aid, children in spec.items():
        lines = [{"asm": c} if c.startswith("asm://") else {"part": c, "qty": 1} for c in children]
        asms[aid] = Assembly.model_validate({"id": aid, "name": aid, "children": lines})
    return AssemblyTree(asms)


KILN_LIKE = {
    "kiln": ["part://guard", "part://bolt", "asm://door", "asm://controls"],
    "door": ["part://tray", "part://bolt", "asm://handle"],
    "handle": ["part://grip"],
    "controls": ["part://box", "part://bolt"],
}


def test_home_of_a_part_in_one_assembly() -> None:
    tree = _tree(KILN_LIKE)
    assert tree.home("part://tray") == "door"
    assert tree.home("part://grip") == "handle"
    assert tree.home("part://guard") == "kiln"


def test_home_of_a_part_in_two_sibling_sub_assemblies_is_their_parent() -> None:
    tree = _tree({"top": ["asm://a", "asm://b"], "a": ["part://bolt"], "b": ["part://bolt"]})
    assert tree.home("part://bolt") == "top"


def test_home_of_a_part_used_at_the_top_and_below_is_the_top() -> None:
    tree = _tree(KILN_LIKE)
    assert tree.home("part://bolt") == "kiln"
    assert tree.home("part://nowhere") is None


def test_no_home_when_no_assembly_holds_every_occurrence() -> None:
    tree = _tree({"one": ["part://x"], "two": ["part://x"]})
    assert tree.home("part://x") is None


def test_port_crossings_run_from_each_home_up_to_the_lowest_common() -> None:
    tree = _tree(KILN_LIKE)
    # a grip in the handle (in the door) joins the guard at the top: the handle and the door
    assert tree.port_crossings("part://grip", "part://guard") == ["door", "handle"]
    # two siblings: each side's module lists the joint, the parent does not
    assert tree.port_crossings("part://tray", "part://box") == ["controls", "door"]
    # the door's own part joins its handle's: only the handle lists it
    assert tree.port_crossings("part://tray", "part://grip") == ["handle"]
    # both parts at home in one assembly: no port
    assert tree.port_crossings("part://guard", "part://bolt") == []
    # the bolt lives at the top (P5), so a joint from the tray to a bolt is the door's port
    assert tree.port_crossings("part://tray", "part://bolt") == ["door"]


def test_lowest_containing_is_where_the_parts_meet() -> None:
    tree = _tree(KILN_LIKE)
    assert tree.lowest_containing("part://tray", "part://bolt") == ["door"]
    assert tree.lowest_containing("part://grip", "part://guard") == ["kiln"]
    assert tree.lowest_common(["door", "controls"]) == ["kiln"]
    assert tree.lowest_common([]) == []


def test_kiln_joints_cross_no_boundary_yet() -> None:
    """M2 leaves the kiln's tree alone (M3): its nine joints each stay inside one assembly."""
    product = load_product(EXAMPLES / "kiln")
    tree = AssemblyTree(product.assemblies)
    for iface in product.interfaces.values():
        a, b = (str(p) for p in iface.parties)
        assert tree.port_crossings(a, b) == [], iface.id
    assert tree.home("part://door-tray") == "door"
    assert tree.home("part://m6x16-bolt") == "kiln"
