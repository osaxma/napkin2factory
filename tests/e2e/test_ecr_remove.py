"""Tests for ECRs that remove parts, parameters or joints (B-0197, S-215)."""

from __future__ import annotations

from pathlib import Path

from napkin2factory.core.vcs import Vcs
from tests.conftest import EXAMPLES, copy_product, n2f
from tests.e2e.test_ecr import _no_git_words


def _run(*args: str, cwd: Path, ok: bool = True):  # type: ignore[no-untyped-def]
    r = n2f(*args, cwd=cwd)
    if ok:
        assert r.returncode == 0, f"{args}: {r.stdout}\n{r.stderr}"
    _no_git_words(r.stdout + r.stderr)
    return r


def test_ecr_remove_part_and_parameter(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", prebuilt=True, render=False)

    # 1. Setup: add an extra part (shim) and an extra parameter (shim-offset) to the bracket
    part_path = root / "model/parts/shim.yaml"
    part_path.write_text(
        "id: shim\n"
        "name: Mounting shim\n"
        "rev: A\n"
        "kind: cots\n"
        "cost: {unit: 0.50 USD}\n"
        "source: {vendor: Acme, mpn: '123', url: 'https://example.com', verified: false}\n"
        "satisfies: [req://REQ-001]\n"
    )

    asm_path = root / "model/assemblies/bracket.yaml"
    asm_orig = asm_path.read_text()
    asm_path.write_text(
        asm_orig.replace(
            "children:\n  - {part: part://l-bracket, qty: 1}",
            "children:\n  - {part: part://l-bracket, qty: 1}\n  - {part: part://shim, qty: 1}",
        )
    )

    params_path = root / "model/parameters.yaml"
    params_orig = params_path.read_text()
    params_path.write_text(
        params_orig + "  shim-offset: {value: 5, unit: mm, description: Shim offset}\n"
    )

    # Sign off REQ-001 citing the shim
    _run(
        "signoff",
        "REQ-001",
        "--by",
        "Tester",
        "--statement",
        "Shim verified",
        "--evidence",
        "part://shim",
        cwd=root,
    )

    vcs = Vcs(root)
    vcs.snapshot("Add shim part, parameter, and sign-off")

    # Verify everything builds and passes before filing the removal ECR
    _run("build", "--no-render", cwd=root)
    _run("validate", cwd=root)
    _run("lint", cwd=root)
    _run("check", cwd=root)

    # 2. Open the design ECR, then remove part://shim, its place in the assembly and the parameter
    _run(
        "ecr",
        "start",
        "--title",
        "Remove shim and offset parameter",
        "--kind",
        "design",
        "--task",
        "Remove the mounting shim part and unused offset parameter",
        cwd=root,
    )
    part_path.unlink()
    asm_path.write_text(asm_orig)
    params_path.write_text(params_orig)

    # The impact report must name the sign-off file and say it will no longer apply
    impact_res = _run("ecr", "impact", "ECR-001", cwd=root)
    assert "model/signoffs/REQ-001.yaml" in impact_res.stdout or "REQ-001" in impact_res.stdout
    assert "will no longer apply" in impact_res.stdout or "no longer apply" in impact_res.stdout
    _run("ecr", "approve", "ECR-001", "--by", "Owner", cwd=root)

    # Part must be gone; the sign-off that cited it stays as a record and the product loads
    assert not (root / "model/parts/shim.yaml").exists()
    assert (root / "model/signoffs/REQ-001.yaml").exists()

    # Commands must succeed afterwards
    _run("validate", cwd=root)
    _run("lint", cwd=root)
    _run("build", "--no-render", cwd=root)
    _run("check", cwd=root)
