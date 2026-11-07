"""M2s: a report section's lens and a domain's inspector hook (decision V5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from napkin2factory.core.domain import LENSES, Domain, ReportSection, SectionContext
from napkin2factory.core.registry import Registry, UnknownName, registry

EXPECTED_LENSES: dict[str, str] = {
    "overview": "workbench",
    "model": "workbench",
    "interfaces": "workbench",
    "joints": "workbench",
    "drawings": "drawings",
    "wiring": "drawings",
    "parts": "build",
    "build": "build",
    "safety": "verification",
    "requirements": "verification",
    "rules": "verification",
    "signoffs": "verification",
    "manuals": "verification",
    "parameters": "history",
    "decisions": "history",
    "changes": "history",
}


def _dummy_sctx() -> SectionContext:
    """A lightweight SectionContext for testing inspector hooks without loading a product."""
    return SectionContext(product=None, build_dir=Path())  # type: ignore[arg-type]


def test_lenses_constant_and_installed_sections() -> None:
    """Every registered section's lens is in LENSES, and each lens holds at least one section."""
    assert LENSES == ("workbench", "drawings", "build", "verification", "history")
    reg = registry()
    sections = reg.report_sections()
    assert sections
    for section in sections:
        assert section.lens in LENSES
        assert reg.lens_of(section.id) == section.lens
    for lens in LENSES:
        in_lens = reg.lens_sections(lens)
        assert in_lens, f"lens {lens!r} holds no sections"
        assert [s.id for s in in_lens] == [s.id for s in sections if s.lens == lens]


def test_installed_section_lens_mapping() -> None:
    """Mechanical sections and the electrical 'wiring' section map to their declared lenses."""
    reg = registry()
    actual = {s.id: reg.lens_of(s.id) for s in reg.report_sections()}
    assert actual == EXPECTED_LENSES
    assert [s.id for s in reg.lens_sections("drawings")] == ["drawings", "wiring"]


def test_unknown_lens_and_unknown_section_raise_unknown_name() -> None:
    """Looking up an unknown lens or section raises UnknownName naming the known values."""
    reg = registry()
    with pytest.raises(UnknownName, match="unknown lens 'nonesuch'; known: workbench, drawings"):
        reg.lens_sections("nonesuch")
    with pytest.raises(UnknownName, match="unknown report section 'nonesuch'"):
        reg.lens_of("nonesuch")


def test_section_with_no_declared_lens_defaults_to_verification() -> None:
    """A section that declares no lens lands in the 'verification' lens."""
    reg = Registry()
    section = ReportSection("extra-check", "Extra check", "Verification", "extra.html.j2")
    assert section.lens == "verification"
    dom = Domain(name="extra", report_sections=(section,))
    reg.register(dom)
    try:
        assert reg.lens_of("extra-check") == "verification"
        assert "extra-check" in [s.id for s in reg.lens_sections("verification")]
    finally:
        reg.unregister("extra")


def test_bad_lens_is_refused_at_register() -> None:
    """Registering a domain with an unknown section lens raises ValueError naming it."""
    reg = Registry()
    bad = Domain(
        name="bad-lens-domain",
        report_sections=(ReportSection("oops", "Oops", "Product", "oops.html.j2", lens="attic"),),
    )
    with pytest.raises(
        ValueError,
        match=(
            r"domain 'bad-lens-domain' report section 'oops' has unknown lens 'attic'; "
            r"known: workbench, drawings, build, verification, history"
        ),
    ):
        reg.register(bad)
    assert "bad-lens-domain" not in [d.name for d in reg.domains]


def test_inspector_entries_empty_when_no_domain_has_hook() -> None:
    """Domains without an inspector hook contribute nothing (returns {})."""
    reg = Registry()
    assert reg.inspector_entries(_dummy_sctx()) == {}


def test_inspector_entries_merges_two_hooks_in_order() -> None:
    """inspector_entries merges entries from multiple domain hooks in installation order."""
    reg = Registry()
    dom_a = Domain(
        name="alpha",
        inspector=lambda sctx: {"part://alpha-one": {"title": "Alpha One"}},
    )
    dom_b = Domain(
        name="beta",
        inspector=lambda sctx: {"part://beta-two": {"title": "Beta Two"}},
    )
    reg.register(dom_a)
    reg.register(dom_b)
    try:
        entries = reg.inspector_entries(_dummy_sctx())
        assert list(entries.keys()) == ["part://alpha-one", "part://beta-two"]
        assert entries["part://alpha-one"] == {"title": "Alpha One"}
        assert entries["part://beta-two"] == {"title": "Beta Two"}
    finally:
        reg.unregister("beta")
        reg.unregister("alpha")


def test_inspector_entries_refuses_non_uri_key() -> None:
    """An inspector hook returning a key that does not parse as a URI raises ValueError."""
    reg = Registry()
    dom = Domain(
        name="bad-key-domain",
        inspector=lambda sctx: {"not-a-uri": {"title": "Bad"}},
    )
    reg.register(dom)
    try:
        with pytest.raises(
            ValueError, match="domain 'bad-key-domain' inspector entry 'not-a-uri' is not a URI"
        ):
            reg.inspector_entries(_dummy_sctx())
    finally:
        reg.unregister("bad-key-domain")


def test_inspector_entries_refuses_non_dict_value() -> None:
    """An inspector hook returning a non-dict value raises ValueError naming the domain and key."""
    reg = Registry()

    def bad_inspector(sctx: Any) -> Any:
        return {"part://plate": "not-a-dict"}

    dom = Domain(name="bad-val-domain", inspector=bad_inspector)
    reg.register(dom)
    try:
        with pytest.raises(
            ValueError,
            match="domain 'bad-val-domain' inspector entry 'part://plate' must be a dict",
        ):
            reg.inspector_entries(_dummy_sctx())
    finally:
        reg.unregister("bad-val-domain")


def test_inspector_entries_refuses_duplicate_key_across_domains() -> None:
    """Two domains returning the same URI key in inspector_entries raises ValueError."""
    reg = Registry()
    dom_a = Domain(
        name="first-dom",
        inspector=lambda sctx: {"part://shared": {"from": "first"}},
    )
    dom_b = Domain(
        name="second-dom",
        inspector=lambda sctx: {"part://shared": {"from": "second"}},
    )
    reg.register(dom_a)
    reg.register(dom_b)
    try:
        with pytest.raises(
            ValueError,
            match=(
                r"domain 'second-dom' returns inspector entry 'part://shared', "
                r"which domain 'first-dom' already returned"
            ),
        ):
            reg.inspector_entries(_dummy_sctx())
    finally:
        reg.unregister("second-dom")
        reg.unregister("first-dom")
