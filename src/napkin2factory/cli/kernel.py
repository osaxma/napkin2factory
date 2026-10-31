"""The CAD kernel (build123d/OCP): announce its slow first import, or warm it up early.

The first ``import build123d`` on a machine loads a ~140 MB native library and can take one
to two minutes with no output; later imports take seconds (B-0016). ``n2f build`` announces
the stall before importing; ``n2f init`` starts the import in a detached background process
so the cost is paid while the owner reads the next-step hint.
"""

from __future__ import annotations

import os
import subprocess
import sys

from napkin2factory.cli.common import err_console

KERNEL_NOTE = (
    "loading the CAD kernel (the first run on a machine can take a couple of minutes; "
    "later runs take seconds)…"
)

NO_WARMUP_ENV = "N2F_NO_WARMUP"


def kernel_loaded() -> bool:
    """True when build123d is already imported in this process."""
    return "build123d" in sys.modules


def load_cad_kernel() -> None:
    """Import build123d/OCP eagerly, announcing the first-import stall on stderr.

    The first ``import build123d`` in a fresh environment loads a ~140 MB native library
    and can take one to two minutes with no output; later imports take seconds. Printing
    the note *before* the import (to stderr, so ``--json`` output stays clean) tells the
    operator the command has not hung.
    """
    if kernel_loaded():
        return
    err_console.print(f"[dim]{KERNEL_NOTE}[/dim]")
    import build123d  # noqa: F401


def warm_kernel_in_background() -> subprocess.Popen[bytes] | None:
    """Start ``import build123d`` in a detached process and return without waiting.

    The child runs in its own session with no inherited streams, so the calling command
    exits at once and the child survives it; the operating system's file cache is then warm
    for the next command that needs the kernel. Returns ``None`` without spawning when
    ``N2F_NO_WARMUP=1`` is set (the test suite sets it) or the spawn itself fails.
    """
    if os.environ.get(NO_WARMUP_ENV) == "1":
        return None
    try:
        return subprocess.Popen(
            [sys.executable, "-c", "import build123d"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return None
