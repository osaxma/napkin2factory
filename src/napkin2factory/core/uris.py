"""The URI scheme and selector grammar (GRAND_PLAN §4.1, decision D24).

``req://REQ-001``, ``param://sheet-thickness``, ``part://lid``, ``asm://enclosure``,
``iface://lid-base-mount``, ``dec://DEC-031``, ``ecr://ECR-019``, ``doc://installation``,
``calc://strength.max_stress``, ``rule://sheet-metal/min-bend-radius``, ``bom://rollups``,
``manifest://scope#electrical.state`` (a field of ``n2f.yaml``).

Selector: ``<uri>#dotted.path`` selects a field or computed property.  For parts inside an
assembly, ``part://m4x10-screw#3`` selects the third instance; the grammar distinguishes
the two by whether the fragment is all digits.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from typing import ClassVar

SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_ID_PATTERNS: dict[str, str] = {
    "req": r"REQ-\d{3}",
    "dec": r"DEC-\d{3}",
    "ecr": r"ECR-\d{3}",
    "param": SLUG,
    "part": SLUG,
    "asm": SLUG,
    "iface": SLUG,
    "doc": SLUG,
    "calc": r"[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*",
    "rule": rf"{SLUG}/{SLUG}",
    # build-plan: the plan the bom rule writes (P8); pages and sheets read its steps (B1, S-117)
    "bom": r"rollups|validation|build-plan",
    # the product's n2f.yaml: its name and its scope (F11), recorded reads of the report, so
    # `n2f impact --set manifest://scope#<domain>.state=later` can ask what a scope edit
    # reruns (S-127, S-129)
    "manifest": r"product|scope",
}
SCHEMES: tuple[str, ...] = tuple(_ID_PATTERNS)
#: Schemes a model's prose never cites: ``manifest://`` names the product file, not a model
#: object, so free text that mentions one is no reference for the lint to check (S-129).
_NOT_IN_PROSE: frozenset[str] = frozenset({"manifest"})
#: Schemes of the model families domains register (F1), set by ``core.registry``, and the
#: owner's word for each (a domain's vocabulary), which :func:`display_uri` puts first.
_DOMAIN_PATTERNS: dict[str, str] = {}
_DOMAIN_WORDS: dict[str, str] = {}


def set_domain_schemes(patterns: dict[str, str], owner_words: dict[str, str]) -> None:
    """Replace the domains' schemes (``core.registry`` calls this on every registration)."""
    _DOMAIN_PATTERNS.clear()
    _DOMAIN_PATTERNS.update({k: v for k, v in patterns.items() if k not in _ID_PATTERNS})
    _DOMAIN_WORDS.clear()
    _DOMAIN_WORDS.update({k: v for k, v in owner_words.items() if k in _DOMAIN_PATTERNS})


def _pattern(scheme: str) -> str | None:
    """The id pattern of ``scheme``: the core's, or a registered domain's."""
    if scheme in _ID_PATTERNS:
        return _ID_PATTERNS[scheme]
    if scheme not in _DOMAIN_PATTERNS:
        # the installed domains' schemes are registered on first use; imported by name so the
        # URI grammar, which every schema imports, stays out of the registry's import cycle
        importlib.import_module("napkin2factory.core.registry").REGISTRY.ensure()
    return _DOMAIN_PATTERNS.get(scheme)


_URI_RE = re.compile(r"^(?P<scheme>[a-z]+)://(?P<id>[^#\s]+)(?:#(?P<fragment>[A-Za-z0-9_.\-]+))?$")
# Only the first segment must start with a letter (an all-digit fragment is an instance); later
# segments may be slugs that start with a digit, e.g. ``bom://build-plan#units.2-stage`` (S-117).
_DOTTED_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*(?:\.[A-Za-z0-9_][A-Za-z0-9_\-]*)*$")


class UriError(ValueError):
    """A string is not a valid napkin2factory URI."""


@dataclass(frozen=True, order=True)
class Uri:
    """A parsed URI: scheme, id, optional selector path or instance number."""

    scheme: str
    id: str
    selector: tuple[str, ...] = ()
    instance: int | None = None

    SCHEMES: ClassVar[tuple[str, ...]] = SCHEMES

    @classmethod
    def parse(cls, text: str) -> Uri:
        """Parse ``scheme://id[#selector]``; raise :class:`UriError` with a hint otherwise."""
        if not isinstance(text, str):
            raise UriError(f"expected a URI string, got {type(text).__name__}")
        m = _URI_RE.match(text.strip())
        if not m:
            raise UriError(
                f"{text!r} is not a URI; expected something like part://lid "
                f"or req://REQ-001#verify.value"
            )
        scheme, ident, fragment = m.group("scheme"), m.group("id"), m.group("fragment")
        pattern = _pattern(scheme)
        if pattern is None:
            known = ", ".join((*SCHEMES, *_DOMAIN_PATTERNS))
            raise UriError(f"unknown scheme {scheme!r} in {text!r}; known: {known}")
        if not re.fullmatch(pattern, ident):
            raise UriError(
                f"{ident!r} is not a valid {scheme} id in {text!r} (expected pattern {pattern})"
            )
        selector: tuple[str, ...] = ()
        instance: int | None = None
        if fragment:
            if fragment.isdigit():
                instance = int(fragment)
                if instance < 1:
                    raise UriError(f"instance numbers start at 1 in {text!r}")
            elif _DOTTED_RE.match(fragment):
                selector = tuple(fragment.split("."))
            else:
                raise UriError(f"bad selector {fragment!r} in {text!r}; use dotted.path")
        return cls(scheme, ident, selector, instance)

    @property
    def base(self) -> Uri:
        """The URI without selector or instance."""
        return Uri(self.scheme, self.id)

    @property
    def fragment(self) -> str:
        """The ``#...`` part, or ``""``."""
        if self.instance is not None:
            return str(self.instance)
        return ".".join(self.selector)

    def with_selector(self, *path: str) -> Uri:
        """Return a copy selecting ``path``."""
        return Uri(self.scheme, self.id, tuple(path), None)

    def __str__(self) -> str:
        frag = self.fragment
        return f"{self.scheme}://{self.id}" + (f"#{frag}" if frag else "")

    def key(self) -> str:
        """The canonical string form (the dependency-recording key)."""
        return str(self)


def is_uri(text: object) -> bool:
    """True if ``text`` parses as a URI."""
    if not isinstance(text, str):
        return False
    try:
        Uri.parse(text)
    except UriError:
        return False
    return True


_FIND_TAIL = r")://[^\s\"'`,;)\]}>]+"
_FIND_CACHE: dict[tuple[str, ...], re.Pattern[str]] = {}


def _find_re() -> re.Pattern[str]:
    """The prose pattern over the core's schemes and every registered domain's (S-129)."""
    importlib.import_module("napkin2factory.core.registry").REGISTRY.ensure()
    schemes = tuple(s for s in (*SCHEMES, *_DOMAIN_PATTERNS) if s not in _NOT_IN_PROSE)
    if schemes not in _FIND_CACHE:
        _FIND_CACHE[schemes] = re.compile(r"\b(?:" + "|".join(schemes) + _FIND_TAIL)
    return _FIND_CACHE[schemes]


def find_uris(text: str) -> list[Uri]:
    """Every parseable URI mentioned in free text (used by lint and docs).

    The core's schemes and every registered domain's (``<scheme>://<id>``), so a domain's
    reference in prose is found and checked like a part's.
    """
    out: list[Uri] = []
    for m in _find_re().finditer(text):
        candidate = m.group(0).rstrip(".:")
        try:
            out.append(Uri.parse(candidate))
        except UriError:
            continue
    return out


_DISPLAY_PREFIX_RE = re.compile(r"^(?:" + "|".join(SCHEMES) + r")://")


def display_uri(uri: str, persona: str) -> str:
    """How a model URI reads in a human-facing table cell or caption for ``persona``.

    The owner sees ``lid`` for ``part://lid`` and ``REQ-003#verify.value`` for
    ``req://REQ-003#verify.value`` (the ``scheme://`` prefix dropped, any ``#selector`` kept);
    the engineer sees the full URI.  Only a leading known scheme is dropped, so free text that
    merely starts with a URI (``asm://enclosure · iso``) is shortened the same way and anything else
    passes through.  Machine outputs (JSON, ``data-uri``, anchors, GLB node names) never use this.
    """
    if persona != "owner":
        return uri
    scheme, sep, rest = uri.partition("://")
    if sep and scheme in _DOMAIN_PATTERNS:  # a domain's scheme: its owner word first (F1)
        return f"{_DOMAIN_WORDS[scheme]} {rest}" if scheme in _DOMAIN_WORDS else rest
    return _DISPLAY_PREFIX_RE.sub("", uri, count=1)


def uri(scheme: str, ident: str) -> Uri:
    """Build a URI from parts, validating the id."""
    return Uri.parse(f"{scheme}://{ident}")


def slug_to_module(slug: str) -> str:
    """``m4x10-screw`` → ``m4x10_screw`` (geometry file naming rule, §3.2)."""
    return slug.replace("-", "_")
