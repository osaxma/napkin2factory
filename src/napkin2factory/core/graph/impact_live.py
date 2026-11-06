"""A live change request's diff: what the working folder adds, changes and removes (v0.8 R6).

The patch dry run (:mod:`impact_patch`) applies a ``.patch`` to a scratch copy to learn what a
design change would do. A live change request has no patch: the agent edited ``model/`` files
in place, so the change is the working folder against the model as it stood at the baseline.
:func:`live_diff` takes that model (loaded from a scratch copy of the baseline), the model as
it is now and the files that differ, and answers in the shape the impact report already
speaks (:class:`PatchImpact`): files, objects added, changed and removed, scope states moved,
the revision of each added part and the sign-offs that no longer apply. It adds what a patch
cannot say, a parameter's value before and after, which is the one number an owner reads first.
"""

from __future__ import annotations

from typing import Any

from napkin2factory.core.graph.impact_common import PatchImpact
from napkin2factory.core.graph.impact_patch import (
    _object_changes,
    _scope_changes,
    signoffs_removed_by,
)
from napkin2factory.core.loader import Product
from napkin2factory.core.units import format_quantity

#: What the live diff calls itself where a patch impact names its patch file.
WORKING_FOLDER = "the working folder"


def _declared(product: Product, slug: str) -> str:
    """A parameter as declared: ``4 mm``, or ``= expression`` for a computed one."""
    p = product.parameters[slug]
    if p.expr is not None:
        return f"= {p.expr}"
    return f"{p.value} {p.unit}".strip()


def _computed(product: Product, slug: str) -> str | None:
    """A parameter's value after evaluating it, or None when it cannot be evaluated."""
    try:
        return format_quantity(product.parameter_value(slug))
    except Exception:  # an invalid model reports itself elsewhere; a diff is not the place
        return None


def parameter_changes(before: Product, after: Product) -> list[dict[str, Any]]:
    """Each parameter whose declared value or unit changed, with its value before and after.

    ``declared`` is what the file says (``4 mm`` or ``= expr``); ``computed`` rows are
    parameters whose expression is unchanged but whose value moved because a parameter it
    reads changed. Added and removed parameters have ``before`` or ``after`` None.
    """
    rows: list[dict[str, Any]] = []
    for slug in sorted(set(before.parameters) | set(after.parameters)):
        old = _declared(before, slug) if slug in before.parameters else None
        new = _declared(after, slug) if slug in after.parameters else None
        if old != new:
            rows.append(
                {
                    "id": slug,
                    "before": old,
                    "after": new,
                    "kind": "declared",
                    "computed_before": _computed(before, slug) if old is not None else None,
                    "computed_after": _computed(after, slug) if new is not None else None,
                }
            )
    declared = {r["id"] for r in rows}
    for slug in sorted((set(before.parameters) & set(after.parameters)) - declared):
        if after.parameters[slug].expr is None:
            continue
        was, now = _computed(before, slug), _computed(after, slug)
        if was != now:
            rows.append(
                {
                    "id": slug,
                    "before": was,
                    "after": now,
                    "kind": "computed",
                    "computed_before": was,
                    "computed_after": now,
                }
            )
    return rows


def live_diff(
    before: Product, after: Product, files: dict[str, list[str]]
) -> tuple[PatchImpact, list[dict[str, Any]]]:
    """What the working folder changed against the baseline model.

    ``before`` is the model loaded from a scratch copy of the baseline, ``after`` the model as
    it is now, ``files`` the product-relative files that differ (``added`` / ``changed`` /
    ``removed``, without ``changes/``). Returns the diff in the patch impact's shape (so the
    impact report and its owner text are shared) and the parameter changes.
    """
    found = PatchImpact(WORKING_FOLDER, True)
    found.files = files
    found.objects, found.revs = _object_changes(before, after)
    found.scope = _scope_changes(before, after)
    found.signoffs_removed = signoffs_removed_by(before, found.objects.get("removed", []))
    return found, parameter_changes(before, after)
