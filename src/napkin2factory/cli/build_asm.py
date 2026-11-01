"""``n2f build --asm <id>``: one assembly and what it needs, through the DAG (P6, M4).

The option lives here (one verb or option per module, S-103 §4); ``cli/build.py`` hands over.
"""

from __future__ import annotations

from napkin2factory.core.errors import N2FError
from napkin2factory.core.loader import Product


def assembly_id(product: Product, given: str) -> str:
    """The assembly id from ``door`` or ``asm://door``; an unknown id names the known ones."""
    aid = given.removeprefix("asm://")
    if aid not in product.assemblies:
        raise N2FError(
            f"no assembly {aid!r}; known: {', '.join(sorted(product.assemblies)) or 'none'}"
        )
    return aid


def check_target(target: str) -> None:
    """``--asm`` builds parts, assemblies and drawings; the rest is the whole product's."""
    if target not in ("geometry", "drawings", "all"):
        raise N2FError(
            f"--asm builds one assembly's parts and placement (--target geometry or drawings); "
            f"--target {target} is the whole product's: run `n2f build --target {target}` "
            "without --asm"
        )


def build_assembly_alone(
    product: Product, aid: str, target: str, clean: bool, render: bool, quiet: bool
) -> dict[str, object]:
    """Run the DAG for ``asm:<aid>`` and the part, assembly and drawing rules it needs."""
    from napkin2factory.core.graph.runner import run_build

    return run_build(
        product,
        target="drawings" if target == "all" else target,
        clean=clean,
        render=render,
        quiet=quiet,
        only_asm=aid,
    )
