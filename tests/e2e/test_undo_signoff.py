"""A restore reports the sign-offs it makes stale and never revives one (v0.8 R5, S-253).

On a prebuilt copy of the enclosure: sign a safety requirement off, change a parameter its
evidence depends on, save that as a checkpoint, then step back (the sign-off holds again) and
forward (it no longer does: the report names it).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from tests.conftest import EXAMPLES, copy_product, n2f

os.environ.setdefault("N2F_OFFLINE", "1")


def test_redo_over_a_changed_parameter_names_the_stale_signoff(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "e", prebuilt=True, render=False)
    r = n2f("signoff", "REQ-004", "--by", "Tester", "--statement", "Edges checked.", cwd=root)
    assert r.returncode == 0, r.stderr
    params = root / "model" / "parameters.yaml"
    params.write_text(
        params.read_text().replace(
            "box-height:        {value: 80,", "box-height:        {value: 85,"
        )
    )
    r = n2f("snapshot", "-m", "Taller box", cwd=root)
    assert r.returncode == 0, r.stderr

    r = n2f("undo", cwd=root)  # back to the signed-off state: the sign-off holds again
    assert r.returncode == 0, r.stderr
    assert 'undid #3 "Taller box"; back to #2 "Signed off REQ-004"' in r.stdout
    assert "changed: model/parameters.yaml" in r.stdout
    assert "sign-off" not in r.stdout.split("changed:")[1]

    r = n2f("redo", cwd=root)  # forward again: the taller box is no longer what was signed
    assert r.returncode == 0, r.stderr
    assert "the sign-off for REQ-004" in r.stdout and "no longer holds" in r.stdout
    assert "evidence changed since signing" in r.stdout and "n2f signoff REQ-004" in r.stdout
    # nothing was revived or rewritten: the sign-off file is as it was signed
    assert (root / "model" / "signoffs" / "REQ-004.yaml").is_file()

    data = json.loads(n2f("undo", "--json", cwd=root).stdout)
    assert data["stale"] == [] and data["checkpoint"]["number"] == 6
    data = json.loads(n2f("redo", "--json", cwd=root).stdout)
    assert len(data["stale"]) == 1 and "REQ-004" in data["stale"][0]
