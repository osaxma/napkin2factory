"""Design change request patch dry runs, diffs and rebuild sets; split from impact.py (S-184)."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from napkin2factory.core.graph.impact_common import PatchImpact, dependent_params
from napkin2factory.core.graph.rules import build_rules
from napkin2factory.core.loader import Product

# ---- a design change request's patch (D7, S-180) ----------------------------------------

#: The core's model collections a patch can touch, by URI scheme (signoffs and change
#: requests are records, not design: a patch over ``model/`` does not carry them).
_COLLECTIONS: tuple[tuple[str, str], ...] = (
    ("part", "parts"),
    ("asm", "assemblies"),
    ("iface", "interfaces"),
    ("req", "requirements"),
    ("param", "parameters"),
    ("dec", "decisions"),
    ("doc", "docs"),
)
#: How the owner says each core kind of object, singular and plural.
_NOUNS: dict[str, tuple[str, str]] = {
    "part": ("part", "parts"),
    "asm": ("assembly", "assemblies"),
    "iface": ("joint", "joints"),
    "req": ("requirement", "requirements"),
    "param": ("size or setting", "sizes and settings"),
    "dec": ("decision", "decisions"),
    "doc": ("manual page", "manual pages"),
}
#: The folders of a product a scratch copy leaves out: its build and its change tracking.
_NOT_COPIED = frozenset({"build", ".git"})


@contextmanager
def dry_run_patch(
    product: Product, patch: Path, build_dir: Path
) -> Iterator[tuple[PatchImpact, Product | None]]:
    """Apply ``patch`` to a scratch copy of ``product``; yield what it changes and the copy.

    The copy is the product folder without ``build/`` and its change tracking; the patch is
    applied there through the vcs wrapper (D31), exactly as ``n2f ecr apply`` applies it, and
    the copy is loaded.  The yielded product is ``None`` when the patch does not apply or the
    patched model does not load (``PatchImpact.problem`` says why).  The copy is removed when
    the block ends, so use the patched product inside it.
    """
    from napkin2factory.core.errors import ModelError
    from napkin2factory.core.loader import load_product
    from napkin2factory.core.vcs import Vcs, VcsError

    shown = _relative(patch, product.root)
    if not patch.is_file():
        yield PatchImpact(shown, False, f"the patch file {shown} is not there"), None
        return
    with tempfile.TemporaryDirectory(prefix="n2f-patch-") as tmp:
        copy = Path(tmp) / product.root.name
        root = product.root.resolve()
        shutil.copytree(
            root,
            copy,
            ignore=lambda d, names: (
                [n for n in names if n in _NOT_COPIED]
                if Path(d).resolve() == root
                else [n for n in names if n == "__pycache__"]
            ),
        )
        vcs = Vcs(copy)
        try:
            vcs.init()  # its own root, so the patch's paths are read from the copy's top
            vcs.apply_patch(patch.resolve())
        except VcsError as exc:
            yield PatchImpact(shown, False, str(exc)), None
            return
        try:
            after = load_product(copy)
        except ModelError as exc:
            problem = f"the model does not load after the patch: {exc}"
            yield PatchImpact(shown, False, problem), None
            return
        found = PatchImpact(shown, True)
        found.files = _file_changes(root, copy)
        found.objects, found.revs = _object_changes(product, after)
        found.scope = _scope_changes(product, after)
        found.rebuilds, found.stale = _patch_rebuilds(product, after, build_dir)
        found.signoffs_removed = signoffs_removed_by(product, found.objects.get("removed", []))
        yield found, after


def signoffs_removed_by(product: Product, removed: list[str]) -> list[dict[str, str]]:
    """Sign-offs that no longer apply once the objects ``removed`` (URIs) are gone (S-215).

    A sign-off of a removed requirement, or citing a removed object as evidence. Used by the
    patch dry run and by a live change request's diff (v0.8 R6).
    """
    removed_objs = set(removed)
    out: list[dict[str, str]] = []
    for so in product.signoffs.values():
        so_file = f"model/signoffs/{so.requirement.id}.yaml"
        if f"req://{so.requirement.id}" in removed_objs:
            reason = f"requirement req://{so.requirement.id} is removed; it will no longer apply"
            out.append({"file": so_file, "id": so.requirement.id, "reason": reason})
            continue
        cites = [str(e.base) for e in so.evidence if str(e.base) in removed_objs]
        if cites:
            reason = f"cites removed {', '.join(cites)}; it will no longer apply"
            out.append({"file": so_file, "id": so.requirement.id, "reason": reason})
    return out


def _relative(path: Path, root: Path) -> str:
    """``path`` relative to ``root`` when it is inside it, else as given."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _files_of(root: Path) -> dict[str, bytes]:
    """Every file of a product folder (no ``build/``, no change tracking) → its bytes."""
    out: dict[str, bytes] = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if rel.parts[0] in _NOT_COPIED or "__pycache__" in rel.parts or not p.is_file():
            continue
        out[rel.as_posix()] = p.read_bytes()
    return out


def _file_changes(before: Path, after: Path) -> dict[str, list[str]]:
    """The product-relative files the patch adds, changes and removes."""
    a, b = _files_of(before), _files_of(after)
    return {
        "added": sorted(set(b) - set(a)),
        "changed": sorted(k for k in set(a) & set(b) if a[k] != b[k]),
        "removed": sorted(set(a) - set(b)),
    }


def _objects_of(product: Product) -> dict[str, Any]:
    """Every model object of ``product`` by its URI (the core's, then each domain family's)."""
    from napkin2factory.core.registry import registry

    out: dict[str, Any] = {}
    for scheme, name in _COLLECTIONS:
        for oid, obj in getattr(product, name).items():
            out[f"{scheme}://{oid}"] = obj
    for fam in registry().model_families():
        # dict.items: listing a family outside a rule records nothing, and needs not to (S-165)
        for oid, obj in dict.items(product.families.get(fam.name, {})):
            out[f"{fam.uri_scheme}://{oid}"] = obj
    return out


def _dump(obj: Any) -> dict[str, Any]:
    """An object's fields as plain data, to compare two versions of it."""
    from napkin2factory.core.product import Doc

    if isinstance(obj, Doc):
        return {"meta": obj.meta.model_dump(mode="json"), "body": obj.body}
    if hasattr(obj, "model_dump"):
        dumped: dict[str, Any] = obj.model_dump(mode="json")
        return dumped
    return {"value": repr(obj)}


def _changed_fields(before: Any, after: Any) -> list[str]:
    """The top-level fields that differ between two versions of one object."""
    a, b = _dump(before), _dump(after)
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def _object_changes(
    product: Product, after: Product
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """URIs added, changed and removed by the patch; each added part's revision."""
    a, b = _objects_of(product), _objects_of(after)
    changed = sorted(u for u in set(a) & set(b) if _changed_fields(a[u], b[u]))
    added = sorted(set(b) - set(a))
    revs = {
        u[len("part://") :]: after.parts[u[len("part://") :]].rev
        for u in added
        if u.startswith("part://")
    }
    return (
        {"added": added, "changed": changed, "removed": sorted(set(a) - set(b))},
        revs,
    )


def _scope_changes(product: Product, after: Product) -> list[dict[str, str]]:
    """Each domain whose scope state the patch moves, in owner words (F11).

    "Wiring: left for later → done here"; a domain the model did not declare before reads
    "not declared".
    """
    from napkin2factory.core.checks.stage import domain_word
    from napkin2factory.core.model.manifest import SCOPE_WORDS

    old, new = product.manifest.scope, after.manifest.scope
    out = []
    for domain in [*old, *(d for d in new if d not in old)]:
        was = old[domain].state if domain in old else ""
        now = new[domain].state if domain in new else ""
        if was == now:
            continue
        words = (
            f"{domain_word(domain)}: {SCOPE_WORDS.get(was, 'not declared')} → "
            f"{SCOPE_WORDS.get(now, 'not declared')}"
        )
        out.append({"domain": domain, "before": was, "after": now, "words": words})
    return out


def _patch_keys(product: Product, after: Product, found: PatchImpact) -> list[str]:
    """The dependency keys the patch touches, as edits of the same objects would name them.

    A changed object: each changed field (``part://x#material``), a parameter whole and the
    parameters computed from it; an added or removed one: its URI and its family's
    membership key (``set://parts``, a domain family's ``set://<family>``); a moved scope
    state: ``manifest://scope#<domain>``; the product's name and the like:
    ``manifest://product#<field>``.
    """
    from napkin2factory.core.graph.recording import membership_key
    from napkin2factory.core.graph.values import MEMBERSHIP_BY_SCHEME, SCOPE_KEY
    from napkin2factory.core.registry import registry

    members = dict(MEMBERSHIP_BY_SCHEME)
    for fam in registry().model_families():
        members.setdefault(fam.uri_scheme, membership_key(fam.name))
    a, b = _objects_of(product), _objects_of(after)
    keys: list[str] = []
    for uri in found.objects.get("changed", []):
        scheme, slug = uri.split("://", 1)
        if scheme == "param":
            keys += [uri, *(f"param://{d}" for d in dependent_params(after, slug))]
        elif scheme == "doc":
            keys.append(uri)
        else:
            keys += [f"{uri}#{f}" for f in _changed_fields(a[uri], b[uri])]
    for uri in found.objects.get("added", []) + found.objects.get("removed", []):
        keys.append(uri)
        scheme = uri.split("://", 1)[0]
        if scheme in members:
            keys.append(members[scheme])
    keys += [f"{SCOPE_KEY}#{s['domain']}" for s in found.scope]
    keys += [
        f"manifest://product#{f}"
        for f in _changed_fields(product.manifest.product, after.manifest.product)
    ]
    return list(dict.fromkeys(keys))


def _patch_rebuilds(
    product: Product, after: Product, build_dir: Path
) -> tuple[dict[str, str], list[str]]:
    """The rules the build would run after the patch and not before it; those stale already.

    Both from the build's own dry run (:func:`explain_build`, a superset of what a build
    reruns) against this build, so the list is what ``n2f build`` would do, not a guess.  A
    rule the patch brings is "added with the change"; a rule that would run anyway (the
    model moved since the last build) is left out and listed as stale.
    """
    from napkin2factory.core.graph.runner import explain_build

    def would_run(p: Product) -> dict[str, str]:
        return {rid: why for rid, run, why in explain_build(p, "all", build_dir, False) if run}

    before = would_run(product)
    known = {r.id for r in build_rules(product)}
    rebuilds = {
        rid: ("added with the change" if rid not in known else why)
        for rid, why in would_run(after).items()
        if rid not in before and rid != "validate"
    }
    return rebuilds, sorted(r for r in before if r != "validate")


def crossed_ports(product: Product, iface_ids: list[str]) -> list[dict[str, Any]]:
    """The ports among ``iface_ids`` (P12): joints some assembly lists under ``ports:``.

    Each names the modules listing it and, per party, the build unit it is built into;
    ``between_units`` is true when the two sides are built in different units, so a change
    there is an interface change touching both.
    """
    from napkin2factory.core.build_units import BuildUnits

    listed: dict[str, list[str]] = {}
    for a in product.assemblies.values():
        for u in a.ports:
            listed.setdefault(u.id, []).append(a.uri)
    if not listed:
        return []
    units = BuildUnits(product)
    out = []
    for iid in iface_ids:
        if iid not in listed:
            continue
        sides = []
        for party in product.interfaces[iid].parties:
            uid = units.unit_of(units.tree.home(str(party)))
            sides.append(
                {
                    "part": str(party),
                    "unit": f"asm://{uid}" if uid else None,
                    "unit_name": product.assemblies[uid].name if uid else None,
                }
            )
        out.append(
            {
                "interface": f"iface://{iid}",
                "port_of": sorted(listed[iid]),
                "sides": sides,
                "between_units": len({s["unit"] for s in sides}) > 1,
            }
        )
    return out
