"""Impact report data structures, revisions and parameter parsing; split from impact.py (S-184)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from napkin2factory.core.errors import N2FError
from napkin2factory.core.expr import referenced_names
from napkin2factory.core.loader import Product
from napkin2factory.core.model import Edit
from napkin2factory.core.uris import Uri


@dataclass
class ReqImpact:
    """A requirement's predicted state after the edit."""

    id: str
    title: str
    why: str
    verdict: str  # would-pass | would-fail | re-check | estimate
    detail: str = ""
    safety: bool = False


@dataclass
class ImpactReport:
    """Structured impact (stored in the ECR) plus a persona summary."""

    edits: list[dict[str, Any]]
    edited_keys: list[str]
    rules: list[str]
    rule_reasons: dict[str, str]
    parts: list[str]
    assemblies: list[str]
    drawings: list[str]
    docs: list[str]
    interfaces: list[str]
    requirements: list[ReqImpact]
    signoffs_invalidated: list[str]
    cost_delta: float
    cost_note: str
    firm: bool  # True when the graph has been built at least once (otherwise estimates)
    kind: str = "parametric"
    cost_complete: bool = True
    tasks: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    ports: list[dict[str, Any]] = field(default_factory=list)  # P12: the ports it crosses
    patch: PatchImpact | None = None  # a design change request's patch (D7, S-180)

    @property
    def change_count(self) -> int:
        """The changes the heading counts: the edits, plus what the patch changes."""
        return len(self.edits) + (self.patch.count if self.patch is not None else 0)

    def to_dict(self) -> dict[str, Any]:
        """JSON form (stored in the change request; ``patch`` only when there is one)."""
        d = dict(self.__dict__)
        d["requirements"] = [r.__dict__ for r in self.requirements]
        # an impact without a patch keeps the stored form it had before S-180
        if self.patch is None:
            d.pop("patch")
        else:
            d["patch"] = self.patch.to_dict()
        return d


@dataclass
class PatchImpact:
    """What a design change request's patch changes, from a dry run on a scratch copy.

    ``files`` and ``objects`` map ``added`` / ``changed`` / ``removed`` to product-relative
    paths and model URIs; ``scope`` lists each domain whose scope state moves (``words`` in
    owner words); ``revs`` an added part's revision; ``rebuilds`` the rules the build would
    run after the patch and not before it (rule id → why); ``stale`` the rules already out
    of date before it.  ``applies`` is false when the patch does not fit the model or the
    patched model does not load; ``problem`` then says why.
    """

    path: str
    applies: bool
    problem: str = ""
    files: dict[str, list[str]] = field(default_factory=dict)
    objects: dict[str, list[str]] = field(default_factory=dict)
    scope: list[dict[str, str]] = field(default_factory=list)
    revs: dict[str, str] = field(default_factory=dict)
    rebuilds: dict[str, str] = field(default_factory=dict)
    stale: list[str] = field(default_factory=list)
    signoffs_removed: list[dict[str, str]] = field(default_factory=list)

    @property
    def count(self) -> int:
        """Model objects added, changed or removed, plus scope states moved."""
        return sum(len(v) for v in self.objects.values()) + len(self.scope)

    def to_dict(self) -> dict[str, Any]:
        """JSON form."""
        return dict(self.__dict__)


def next_rev(rev: str) -> str:
    """``A`` → ``B``, ``Z`` → ``AA``, ``3`` → ``4``."""
    if rev.isdigit():
        return str(int(rev) + 1)
    if not rev:
        return "A"
    chars = list(rev.upper())
    i = len(chars) - 1
    while i >= 0:
        if chars[i] != "Z":
            chars[i] = chr(ord(chars[i]) + 1)
            return "".join(chars)
        chars[i] = "A"
        i -= 1
    return "A" + "".join(chars)


class EditError(N2FError, ValueError):
    """A ``--set`` that is not an edit; the message names it and says what is wrong (C7)."""


def parse_set(text: str) -> Edit:
    """``param://x=50mm`` or ``req://REQ-001#verify.value=250 mm`` → Edit.

    Anything else raises :class:`EditError` with the reason in plain words (gate E C7): the
    command prints it instead of a traceback.
    """
    if "=" not in text:
        raise EditError(f"--set expects <uri>=<value>, e.g. param://x=50mm; got {text!r}")
    target, value = text.split("=", 1)
    try:
        return Edit(set=Uri.parse(target.strip()), to=value.strip())
    except ValidationError as exc:
        reasons = "; ".join(str(e["msg"]).removeprefix("Value error, ") for e in exc.errors())
        raise EditError(f"--set {text!r}: {reasons}") from exc
    except ValueError as exc:  # UriError: not a URI the model knows
        raise EditError(f"--set {text!r}: {exc}") from exc


def dependent_params(product: Product, slug: str) -> list[str]:
    """Parameters whose expressions depend on ``slug`` (transitively)."""
    out: list[str] = []
    changed = True
    seen = {slug}
    while changed:
        changed = False
        for name, p in product.parameters.items():
            if name in seen or not p.expr:
                continue
            if set(referenced_names(p.expr)) & seen:
                seen.add(name)
                out.append(name)
                changed = True
    return out
