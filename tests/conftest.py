"""Shared fixtures: paths to examples and a helper that copies a product to a temp dir."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Never spawn the background CAD-kernel warm-up of `n2f init` from the suite (B-0016); the
# subprocess CLI runs inherit this. Tests of the warm-up itself clear it explicitly.
os.environ.setdefault("N2F_NO_WARMUP", "1")

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def is_swiftshader_flake(message: str) -> bool:
    """True for SwiftShader's shader-validation hiccup (B-0024), which is not a page defect.

    Under load the software GL sometimes reports ``THREE.WebGLProgram: Shader Error …
    VALIDATE_STATUS false`` with an empty info log; the same page loads cleanly the next time.
    """
    return (
        "THREE.WebGLProgram: Shader Error" in message
        and "VALIDATE_STATUS false" in message
        and message.rstrip().endswith("Program Info Log:")
    )


def real_page_errors(errors: list[str]) -> list[str]:
    """The page errors that are not the SwiftShader flake (B-0024)."""
    return [e for e in errors if not is_swiftshader_flake(e)]


def copy_product(src: Path, dst: Path, git: bool = True) -> Path:
    """Copy a product directory (without build/) and optionally start change tracking (D23)."""
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("build", "__pycache__", ".git"))
    if git:
        from napkin2factory.core.vcs import Vcs

        v = Vcs(dst)
        v.init()
        v.snapshot("Start")
    return dst


@pytest.fixture
def bracket(tmp_path: Path) -> Path:
    """A fresh tracked copy of examples/bracket."""
    return copy_product(EXAMPLES / "bracket", tmp_path / "bracket")


@pytest.fixture
def enclosure(tmp_path: Path) -> Path:
    """A fresh tracked copy of examples/enclosure."""
    return copy_product(EXAMPLES / "enclosure", tmp_path / "enclosure")


def n2f(
    *args: str, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the CLI in-process-equivalent via ``python -m`` so coverage and venv apply."""
    full_env = dict(os.environ)
    full_env["PYTHONIOENCODING"] = "utf-8"
    full_env["COLUMNS"] = "200"
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "napkin2factory.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=full_env,
        check=False,
    )
