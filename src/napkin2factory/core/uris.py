"""The URI scheme and selector grammar (GRAND_PLAN §4.1, decision D24).

``req://REQ-014``, ``param://wall-thickness``, ``part://outer-shell``, ``asm://kiln``,
``iface://shell-frame-mount``, ``dec://DEC-031``, ``ecr://ECR-019``, ``doc://installation``,
``calc://thermal.skin_temperature``, ``rule://sheet-metal/min-bend-radius``, ``bom://rollups``.

Selector: ``<uri>#dotted.path`` selects a field or computed property.  For parts inside an
assembly, ``part://outer-shell#3`` selects the third instance; the grammar distinguishes
the two by whether the fragment is all digits.
"""

from __future__ import annotations

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
    "bom": r"rollups|validation",
}
SCHEMES: tuple[str, ...] = tuple(_ID_PATTERNS)
_URI_RE = re.compile(r"^(?P<scheme>[a-z]+)://(?P<id>[^#\s]+)(?:#(?P<fragment>[A-Za-z0-9_.\-]+))?$")
_DOTTED_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*(?:\.[A-Za-z_][A-Za-z0-9_\-]*)*$")


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
                f"{text!r} is not a URI; expected something like part://outer-shell "
                f"or req://REQ-001#verify.value"
            )
        scheme, ident, fragment = m.group("scheme"), m.group("id"), m.group("fragment")
        if scheme not in _ID_PATTERNS:
            raise UriError(f"unknown scheme {scheme!r} in {text!r}; known: {', '.join(SCHEMES)}")
        if not re.fullmatch(_ID_PATTERNS[scheme], ident):
            raise UriError(
                f"{ident!r} is not a valid {scheme} id in {text!r} "
                f"(expected pattern {_ID_PATTERNS[scheme]})"
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


_FIND_RE = re.compile(r"\b(?:" + "|".join(SCHEMES) + r")://[^\s\"'`,;)\]}>]+")


def find_uris(text: str) -> list[Uri]:
    """Every parseable URI mentioned in free text (used by lint and docs)."""
    out: list[Uri] = []
    for m in _FIND_RE.finditer(text):
        candidate = m.group(0).rstrip(".:")
        try:
            out.append(Uri.parse(candidate))
        except UriError:
            continue
    return out


def uri(scheme: str, ident: str) -> Uri:
    """Build a URI from parts, validating the id."""
    return Uri.parse(f"{scheme}://{ident}")


def slug_to_module(slug: str) -> str:
    """``outer-shell`` → ``outer_shell`` (geometry file naming rule, §3.2)."""
    return slug.replace("-", "_")
