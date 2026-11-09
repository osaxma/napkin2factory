"""Wave 8: promotion reports a limit the card already breaks instead of seeding it (B-0324)."""

from __future__ import annotations

from pathlib import Path

import yaml

from napkin2factory.concepts.promote import promote
from napkin2factory.core.loader import load_product
from tests.conftest import n2f


def test_promote_skips_broken_limit_and_reports_conflict(tmp_path: Path) -> None:
    """A card with a 33 kg lift limit screened at 76.5 kg is promoted; requirement is absent."""
    root = tmp_path / "bench"
    r = n2f("init", str(root), "--name", "Bench", "--no-tracking")
    assert r.returncode == 0, r.stderr

    card_data = {
        "id": "C-001",
        "title": "Timber bench",
        "status": "exploring",
        "site": {
            "width": "1000 mm",
            "mass_limit": "33 kg",
            "lift_class": "one-person",
        },
        "screening": {
            "computed": {
                "width": {
                    "value": "800 mm",
                    "label": "computed",
                    "source": "measured across rough shapes",
                },
                "mass": {
                    "value": "76.5 kg",
                    "label": "computed",
                    "source": "from rough shapes",
                },
            },
            "verdict": "green",
        },
    }
    card_path = root / "concepts" / "C-001.yaml"
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(yaml.safe_dump(card_data, sort_keys=False), encoding="utf-8")

    result = promote(root, "C-001", snapshot=False)

    # 1. Requirement is absent from the model
    product = load_product(root)
    assert "Light enough to move as planned" not in [r.title for r in product.requirements.values()]
    assert all(r.category != "mass" for r in product.requirements.values())
    assert all(r.about != "weight" for r in result.requirements)

    req_yaml = (root / "model/requirements.yaml").read_text(encoding="utf-8")
    assert "Light enough to move as planned" not in req_yaml
    assert "33 kg" not in req_yaml

    # 2. conflicts has it with both figures
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict["title"] == "Light enough to move as planned"
    assert conflict["limit"] == "33 kg"
    assert conflict["figure"] == "76.5 kg"
    expected_say = (
        "The design weighs 76.5 kg on the napkin, over the 33 kg one-person lift limit. "
        "Ask the owner: drop the limit, or change the design."
    )
    assert conflict["say"] == expected_say
    assert result.to_dict()["conflicts"] == [conflict]

    # 3. Passing limit is still seeded
    space_req = next((r for r in result.requirements if r.about == "space"), None)
    assert space_req is not None
    assert "Fits the space width" in space_req.title
    assert any("Fits the space width" in r.title for r in product.requirements.values())

    # 4. result.next advises asking the owner before building
    assert "ask the owner" in result.next.lower()
    assert "before building" in result.next.lower()
    assert result.to_dict()["next"] == result.next

    # 5. CLI plain output shows the conflict and next step
    summary = result.summary()
    assert f"conflict: {expected_say}" in summary
    assert result.next in summary


def test_cli_promote_shows_conflict_in_plain_output(tmp_path: Path) -> None:
    """CLI promotion prints conflicts on their own line and actionable next step."""
    root = tmp_path / "bench-cli"
    r = n2f("init", str(root), "--name", "Bench CLI", "--no-tracking")
    assert r.returncode == 0, r.stderr

    card_data = {
        "id": "C-001",
        "title": "Timber bench",
        "status": "exploring",
        "site": {
            "width": "1000 mm",
            "mass_limit": "33 kg",
            "lift_class": "one-person",
        },
        "screening": {
            "computed": {
                "width": {
                    "value": "800 mm",
                    "label": "computed",
                    "source": "measured across rough shapes",
                },
                "mass": {
                    "value": "76.5 kg",
                    "label": "computed",
                    "source": "from rough shapes",
                },
            },
            "verdict": "green",
        },
    }
    card_path = root / "concepts" / "C-001.yaml"
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(yaml.safe_dump(card_data, sort_keys=False), encoding="utf-8")

    r = n2f("concept", "promote", "C-001", cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (
        "conflict: The design weighs 76.5 kg on the napkin, over the 33 kg one-person lift limit."
        in r.stdout
    )
    assert "Ask the owner: drop the limit, or change the design." in r.stdout
    assert "Ask the owner about each conflict before building" in r.stdout
