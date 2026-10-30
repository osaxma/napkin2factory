"""D19: templates are byte-identical to the examples (and all examples share _common)."""

from napkin2factory.templates.sync import differences


def test_templates_in_sync():
    diffs = differences()
    assert not diffs, "run `make templates`:\n" + "\n".join(diffs)
