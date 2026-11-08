"""``n2f build --asm <id>``: one assembly and what it needs, through the DAG (P6, M4).

The option lives here (one verb or option per module, S-103 §4); ``cli/build.py`` hands over.
"""

from __future__ import annotations

from pathlib import Path

from napkin2factory.core.errors import N2FError
from napkin2factory.core.loader import Product


def assembly_id(product: Product, given: str) -> str:
    """The assembly id from ``door`` or ``asm://door``; an unknown id names the known ones."""
    aid = given.removeprefix("asm://")
    if aid not in product.assemblies:
        where = f" --dir {product.root}" if product.root != Path.cwd() else ""
        raise N2FError(
            f"no assembly {aid!r}; known: {', '.join(sorted(product.assemblies)) or 'none'}",
            next=f"n2f status{where}",
        )
    return aid


def check_target(target: str) -> None:
    """``--asm`` builds parts, assemblies and drawings; the rest is the whole product's."""
    allowed = ("geometry", "drawings", "all")
    if target not in allowed:
        raise N2FError(
            f"--asm builds one assembly's parts and placement (--target geometry or drawings); "
            f"--target {target} is the whole product's: run `n2f build --target {target}` "
            "without --asm",
            next=f"choose one of: {', '.join(allowed)}",
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
