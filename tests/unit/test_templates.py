"""D19: templates are byte-identical to the examples (and all examples share _common)."""

from napkin2factory.templates.sync import differences


def test_templates_in_sync():
    diffs = differences()
    assert not diffs, "run `make templates`:\n" + "\n".join(diffs)


def test_templates_do_not_send_the_agent_to_the_system_repo():
    # The installed tool has no docs/ folder: `n2f docs <topic>` is the way (S-231).
    from napkin2factory.templates import TEMPLATES_DIR

    hits = [
        str(p.relative_to(TEMPLATES_DIR))
        for p in TEMPLATES_DIR.rglob("*.md")
        if "system repo" in p.read_text(encoding="utf-8")
    ]
    assert not hits, hits
