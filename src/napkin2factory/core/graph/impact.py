"""``n2f impact`` (GRAND_PLAN §6.3): what a hypothetical edit would touch, before anything changes.

Given edits (from a change request or ``--set``), compute: rules whose recorded reads
intersect the edited keys, transitively through the DAG; requirements whose verify targets
are affected, with hypothetical verdicts where they can be evaluated from declared values;
parts touched (revision bumps implied); docs with affected reads; interfaces whose parties
are affected, and which of them are ports (a joint between modules, P4, P12); sign-offs that
would be invalidated; and a cost delta from declared costs.  Nothing in the model changes.

A design change request's patch (D7) is part of the change: :func:`compute_impact` applies it
to a scratch copy of the product (:func:`dry_run_patch`), lists the files, model objects and
scope states it changes, and takes the rebuild set from the build's own dry run of the copy
against this build (S-180).  A patch that does not apply says so plainly.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from napkin2factory.core.errors import N2FError
from napkin2factory.core.expr import referenced_names
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.graph.rules import Rule, build_rules
from napkin2factory.core.loader import Product
from napkin2factory.core.model import Edit
from napkin2factory.core.units import UnitError, compare, format_quantity, parse_quantity
from napkin2factory.core.uris import Uri, display_uri


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


def _edit_keys(product: Product, edits: list[Edit]) -> tuple[list[str], dict[str, Any]]:
    """Keys touched by the edits and value overrides for hypothetical evaluation."""
    keys: list[str] = []
    overrides: dict[str, Any] = {}
    for e in edits:
        u = e.set
        added = _membership_if_new(product, u)
        if added is not None:
            keys.append(added)
        if u.scheme == "param" and not u.selector:
            keys.append(f"param://{u.id}")
            try:
                overrides[f"param://{u.id}"] = (
                    parse_quantity(e.to, product.parameters[u.id].unit or None)
                    if u.id in product.parameters
                    else e.to
                )
            except UnitError:
                overrides[f"param://{u.id}"] = e.to
            for dep in dependent_params(product, u.id):
                keys.append(f"param://{dep}")
        else:
            keys.append(str(u))
            if u.scheme == "part" and u.selector[:1] == ("cost",):
                keys.append(f"part://{u.id}#cost")
            overrides[str(u)] = e.to
            # rules record the fields they read (part://x#material, asm://y#children, …), so a
            # selector edit touches exactly the rules that read that field (gate-1 B3)
            if u.selector:
                keys.append(f"{u.base}#{u.selector[0]}")
    seen: dict[str, None] = {}
    for k in keys:
        seen.setdefault(k, None)
    return list(seen), overrides


def _families_added_to(edited_keys: list[str]) -> dict[str, str]:
    """Rule family → the ``set://<family>`` key it answers to, for each family a file is added to.

    The domain that registers a family makes its rules from it at every build and declares
    their dependence itself (inputs; its rules record no listing, S-165), so impact names
    all of that domain's rules: conservative, a superset of what the build reruns.
    """
    from napkin2factory.core.graph.recording import membership_key
    from napkin2factory.core.registry import registry

    out: dict[str, str] = {}
    for d in registry().domains:
        if d.in_place:  # the system's own rules record the listing (S-165)
            continue
        for fam in d.families:
            key = membership_key(fam.name)
            if key in edited_keys:
                for rf in d.rule_families:
                    out.setdefault(rf.name, key)
    return out


def _membership_if_new(product: Product, u: Uri) -> str | None:
    """The membership key an edit touches when it names an object that does not exist yet.

    ``--set tally://b#count=2`` with no ``model/tally/b.yaml`` is that file added: every rule
    that listed the family reads ``set://tally`` and reruns when the file arrives (S-165).
    """
    from napkin2factory.core.graph.recording import MEMBERSHIP, membership_key
    from napkin2factory.core.graph.values import MEMBERSHIP_BY_SCHEME
    from napkin2factory.core.registry import registry

    if u.scheme in MEMBERSHIP_BY_SCHEME:
        key = MEMBERSHIP_BY_SCHEME[u.scheme]
        return None if u.id in getattr(product, MEMBERSHIP[key]) else key
    for fam in registry().model_families():
        if fam.uri_scheme == u.scheme:
            objects = product.families.get(fam.name, {})
            return None if dict.__contains__(objects, u.id) else membership_key(fam.name)
    return None


def _hypothetical_params(product: Product, overrides: dict[str, Any]) -> dict[str, Any]:
    """Parameter values with overrides applied and expressions re-evaluated."""
    from napkin2factory.core.expr import evaluate

    values: dict[str, Any] = {}

    def get(slug: str, stack: tuple[str, ...] = ()) -> Any:
        if slug in values:
            return values[slug]
        key = f"param://{slug}"
        p = product.parameters[slug]
        if key in overrides:
            v = overrides[key]
            v = parse_quantity(v, p.unit or None) if isinstance(v, (str, int, float)) else v
        elif p.expr is None:
            v = product.parameter_value(slug)
        else:
            v = evaluate(p.expr, {}, lookup=lambda s: get(s, (*stack, slug)))
            if p.unit and hasattr(v, "to"):
                v = v.to(p.unit)
        values[slug] = v
        return v

    for slug in product.parameters:
        try:
            get(slug)
        except Exception as exc:  # report, don't crash an impact run
            values[slug] = f"invalid: {exc}"
    return values


def compute_impact(
    product: Product,
    edits: list[Edit],
    build_dir: Path | None = None,
    kind: str = "parametric",
    tasks: list[str] | None = None,
    patch: Path | None = None,
) -> ImpactReport:
    """The impact of ``edits`` (and of a design change request's ``patch``) on this build.

    Nothing is modified.  With ``patch``, the patch is applied to a scratch copy
    (:func:`dry_run_patch`) and the impact is computed on the patched model against this
    build: what it adds, changes and removes, and what the build would run for it.
    """
    build_dir = build_dir or product.paths.build
    if patch is None:
        return _impact(product, edits, build_dir, kind, tasks)
    with dry_run_patch(product, patch, build_dir) as (found, after):
        if after is None:
            report = _impact(product, edits, build_dir, kind, tasks)
        else:
            keys = _patch_keys(product, after, found)
            report = _impact(after, edits, build_dir, kind, tasks, keys, found.rebuilds)
        report.patch = found
        return report


def _impact(
    product: Product,
    edits: list[Edit],
    build_dir: Path,
    kind: str,
    tasks: list[str] | None,
    extra_keys: list[str] | None = None,
    seeded: dict[str, str] | None = None,
) -> ImpactReport:
    """:func:`compute_impact` on one model; ``seeded``: rules known to rerun, with why."""
    manifest = Manifest.load(build_dir)
    rules = build_rules(product)
    edited_keys, overrides = _edit_keys(product, edits)
    for k in extra_keys or []:
        if k not in edited_keys:
            edited_keys.append(k)
    edited = set(edited_keys)
    firm = bool(manifest.entries)
    affected: dict[str, str] = {}
    produced_affected: set[str] = set()
    notes: list[str] = []
    if not firm:
        notes.append(
            "the product has never been built here, so the rebuild set is the full build; "
            "run `n2f build` once for an exact list"
        )
    touches = _edit_matcher(edited_keys, {p for r in rules for p in r.produced})
    added_to = _families_added_to(edited_keys)
    for rule in rules:
        entry = manifest.entries.get(rule.id)
        if rule.kind == "validate":
            affected[rule.id] = "always re-validates"
            continue
        if seeded and rule.id in seeded:  # the build's own dry run of the patched copy
            affected[rule.id] = seeded[rule.id]
            for produced in rule.produced:
                produced_affected.add(produced)
                produced_affected.add(produced.split("#")[0])
            continue
        if rule.kind in added_to:
            # its domain makes its rules from the family and records no listing (S-165)
            affected[rule.id] = added_to[rule.kind]
            for produced in rule.produced:
                produced_affected.add(produced)
                produced_affected.add(produced.split("#")[0])
            continue
        reads = entry.reads if entry is not None else _static_reads(product, rule)
        hits = [
            k
            for k in reads
            if touches(k) or k in produced_affected or Uri_base(k) in produced_affected
        ]
        if hits:
            shown = _most_specific(hits)
            affected[rule.id] = ", ".join(shown[:4]) + (" …" if len(shown) > 4 else "")
            for produced in rule.produced:
                produced_affected.add(produced)
                produced_affected.add(produced.split("#")[0])
    parts = sorted(r.split(":", 1)[1] for r in affected if r.startswith("part:"))
    asms = sorted(r.split(":", 1)[1] for r in affected if r.startswith("asm:"))
    drawings = sorted(r.split(":", 1)[1] for r in affected if r.startswith("drawing:"))
    docs = sorted(r.split(":", 1)[1] for r in affected if r.startswith("doc:"))
    affected_part_uris = {f"part://{p}" for p in parts} | {f"asm://{a}" for a in asms}
    affected_params = {k for k in edited if k.startswith("param://")}
    interfaces = sorted(
        i.id
        for i in product.interfaces.values()
        if any(str(p) in affected_part_uris for p in i.parties)
        or any(f"param://{u.id}" in affected_params for u in Uri_refs(i))
        or any(f"param://{s}" in affected_params for s in i.expression_slugs())
    )
    ports = crossed_ports(product, interfaces)
    hyp = _hypothetical_params(product, overrides) if affected_params else {}
    reqs: list[ReqImpact] = []
    for r in product.requirements.values():
        why = []
        if any(
            str(a) in affected_part_uris or str(a) in affected_params
            for a in (r.allocation if isinstance(r.allocation, list) else [])
        ):
            why.append("allocated to something that changes")
        if r.verify is not None and r.verify.target is not None:
            t = r.verify.target
            if (
                str(t.base) in affected_part_uris
                or str(t.base) in affected_params
                or (t.scheme == "bom" and "bom" in affected)
                or (t.scheme == "iface" and t.id in interfaces)
                or (t.scheme == "calc" and affected_params)
            ):
                why.append(f"verified against {t.base}")
        if f"req://{r.id}" in edited or any(k.startswith(f"req://{r.id}#") for k in edited):
            why.append("the change request edits this requirement")
        if not why:
            continue
        verdict, detail = _hypothetical_verdict(product, r, overrides, hyp, affected, build_dir)
        reqs.append(ReqImpact(r.id, r.title, "; ".join(why), verdict, detail, r.safety))
    signoffs = sorted(
        s.requirement.id
        for s in product.signoffs.values()
        if any(_evidence_affected(str(e), affected, affected_params) for e in s.evidence)
        or s.requirement.id in {q.id for q in reqs}
    )
    cost_delta, cost_note = _cost_delta(product, edits, build_dir)
    return ImpactReport(
        edits=[{"set": str(e.set), "to": e.to} for e in edits],
        edited_keys=edited_keys,
        rules=[r.id for r in rules if r.id in affected],
        rule_reasons=affected,
        parts=parts,
        assemblies=asms,
        drawings=drawings,
        docs=docs,
        interfaces=interfaces,
        requirements=reqs,
        signoffs_invalidated=signoffs,
        cost_delta=cost_delta,
        cost_note=cost_note,
        firm=firm,
        kind=kind,
        tasks=list(tasks or []),
        notes=notes,
        ports=ports,
    )


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
        yield found, after


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


def _edit_matcher(edited_keys: list[str], outputs: set[str]) -> Any:
    """``touches(read)``: does a recorded read see one of the edited keys (gate E B1, S-138)?

    A read and an edit of the same object touch when one's field path starts with the
    other's: an edit of ``iface://x#spec.depth`` touches the reads ``iface://x#spec.depth``,
    ``iface://x#spec`` and ``iface://x`` (the object read whole, as the parts read their
    interfaces and the checks a decided choice's ``dec://``), never ``iface://x#name``.  A
    bare key that a rule produces (``part://x``, a domain family's ``<scheme>://x``) is that
    rule's output hash, not the object: it is reached through the rules the edit reruns, not
    matched here.
    """
    by_base: dict[str, list[tuple[str, ...]]] = {}
    for key in edited_keys:
        base, _, sel = key.partition("#")
        by_base.setdefault(base, []).append(tuple(sel.split(".")) if sel else ())

    def touches(read: str) -> bool:
        base, _, sel = read.partition("#")
        edits = by_base.get(base)
        if not edits:
            return False
        path = tuple(sel.split(".")) if sel else ()
        for edit in edits:
            if not path and edit and base in outputs:
                continue
            n = min(len(path), len(edit))
            if path[:n] == edit[:n]:
                return True
        return False

    return touches


def _most_specific(hits: list[str]) -> list[str]:
    """The reason's keys: a whole-object hit is left out when a field of it hit too.

    ``manifest://scope`` and ``manifest://scope#electrical`` both see an edit of
    ``manifest://scope#electrical.note``; the field says which entry it is.
    """
    return [
        k
        for k in hits
        if not any(o != k and o.startswith(k + ("." if "#" in k else "#")) for o in hits)
    ]


def Uri_base(key: str) -> str:  # noqa: N802 - reads like the Uri API
    """``part://x#props.mass`` → ``part://x``; non-URI keys unchanged."""
    return key.split("#", 1)[0]


def Uri_refs(obj: Any) -> list[Uri]:  # noqa: N802
    """Every Uri object inside a pydantic model (for interface spec param refs)."""
    out: list[Uri] = []

    def walk(v: Any) -> None:
        if isinstance(v, Uri):
            out.append(v)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif hasattr(v, "model_fields"):
            for name in type(v).model_fields:
                walk(getattr(v, name))

    walk(obj)
    return out


def _static_reads(product: Product, rule: Rule) -> list[str]:
    """Conservative read set for a rule that has never run (before the first build).

    Each rule family declares its own (``RuleFamily.static_reads``); a family that declares
    none (checks, report, site) reads every artifact a rule produces.
    """
    from napkin2factory.core.registry import registry

    reg = registry()
    family = next((f for f in reg.rule_families() if f.name == rule.kind), None)
    if family is not None and family.static_reads is not None:
        return list(family.static_reads(product, rule))
    # every rule that produces a model artifact (a URI; not validate's or a sheet's rule key)
    from napkin2factory.core.graph.recording import membership_key

    produced = [r.produces for r in build_rules(product) if r.produces and "://" in r.produces]
    return (
        produced
        + [
            "bom://rollups",
            "bom://build-plan",
            "rule:checks",
            "rule:report",
        ]
        # what a check stage or a report section may list (S-165)
        + [membership_key(f.name) for f in reg.model_families()]
    )


# ---- the mechanical families' static read sets (registered in place, F2) -----------------


def part_static_reads(product: Product, rule: Rule) -> list[str]:
    """A part reads its parameters, its interfaces and theirs, and frame-expression slugs."""
    pid = rule.id.split(":", 1)[1]
    part = product.parts[pid]
    reads = [f"param://{u.id}" for u in Uri_refs(part) if u.scheme == "param"]
    reads += [f"iface://{u.id}" for u in part.interfaces]
    reads += [
        f"param://{u.id}"
        for i in part.interfaces
        for u in Uri_refs(product.interfaces[i.id])
        if u.scheme == "param"
    ]
    # P2: slugs named inside frame expressions are reads too (S-106)
    reads += [
        f"param://{s}" for i in part.interfaces for s in product.interfaces[i.id].expression_slugs()
    ]
    return reads


def asm_static_reads(product: Product, rule: Rule) -> list[str]:
    """An assembly reads its children and every parameter."""
    aid = rule.id.split(":", 1)[1]
    return [c.uri for c in product.assemblies[aid].children] + [
        f"param://{p}" for p in product.parameters
    ]


def drawing_static_reads(product: Product, rule: Rule) -> list[str]:
    """A drawing reads its part."""
    return [f"part://{rule.id.split(':', 1)[1]}"]


def bom_static_reads(product: Product, rule: Rule) -> list[str]:
    """The BOM reads every part, its cost, every assembly's children and every interface."""
    return (
        [f"{p.uri}#cost" for p in product.parts.values()]
        + [p.uri for p in product.parts.values()]
        + [f"{a.uri}#children" for a in product.assemblies.values()]
        + [f"iface://{i}" for i in product.interfaces]  # the build plan's hardware (P9)
    )


def asmsheet_static_reads(product: Product, rule: Rule) -> list[str]:
    """An assembly sheet reads its unit's assembly and its step of the plan."""
    aid = rule.id.split(":", 1)[1]
    return [f"asm://{aid}", f"bom://build-plan#units.{aid}"]


def doc_static_reads(product: Product, rule: Rule) -> list[str]:
    """A manual page reads what it declares and every parameter."""
    did = rule.id.split(":", 1)[1]
    return [str(d) for d in product.docs[did].meta.depends_on] + [
        f"param://{p}" for p in product.parameters
    ]


def _hypothetical_verdict(
    product: Product,
    r: Any,
    overrides: dict[str, Any],
    hyp: dict[str, Any],
    affected: dict[str, str],
    build_dir: Path,
) -> tuple[str, str]:
    """Would ``r`` pass after the edit? Its verify kind answers (``VerifyKind.hypothetical``)."""
    from napkin2factory.core.registry import UnknownName, registry

    v = r.verify
    if v is None:
        return "re-check", "no verify method"
    try:
        kind = registry().verify_kind(v.kind)
    except UnknownName:
        return "re-check", ""
    if kind.hypothetical is None:
        return "estimate", "known after the rebuild"
    return kind.hypothetical(product, r, overrides, hyp, affected, build_dir)


# ---- the mechanical verify kinds' answers (registered in place, F2) ----------------------


def hyp_manual(*_: Any) -> tuple[str, str]:
    """A person signs it off again."""
    return "re-check", "a person must sign this off (again, if it was signed)"


def hyp_after_rebuild(*_: Any) -> tuple[str, str]:
    """Geometry decides; known after the rebuild."""
    return "estimate", "depends on geometry; known after the rebuild"


def hyp_calc(*_: Any) -> tuple[str, str]:
    """The calculation re-runs at ``n2f check``."""
    return "estimate", "the calculation re-runs with the new values at `n2f check`"


def hyp_param_bound(
    product: Product,
    r: Any,
    overrides: dict[str, Any],
    hyp: dict[str, Any],
    affected: dict[str, str],
    build_dir: Path,
) -> tuple[str, str]:
    """Compare the hypothetical parameter value with the (possibly edited) limit."""
    v = r.verify
    if v.target is None or not v.op or v.value is None:
        return "re-check", ""
    slug = v.target.id
    value = hyp.get(slug, product.parameter_value(slug) if slug in product.parameters else None)
    limit = overrides.get(f"req://{r.id}#verify.value", v.value)
    if isinstance(limit, str):
        try:
            limit = parse_quantity(limit)
        except UnitError:
            return "re-check", f"cannot read the new limit {limit!r}"
    if value is None or isinstance(value, str):
        return "re-check", "parameter could not be evaluated"
    try:
        ok = compare(value, v.op, limit)
    except UnitError as exc:
        return "re-check", str(exc)
    return (
        "would-pass" if ok else "would-fail"
    ), f"{format_quantity(value)} {v.op} {format_quantity(limit)}"


def hyp_bom_rollup(
    product: Product,
    r: Any,
    overrides: dict[str, Any],
    hyp: dict[str, Any],
    affected: dict[str, str],
    build_dir: Path,
) -> tuple[str, str]:
    """The declared total cost plus the declared cost delta of the edit."""
    v = r.verify
    if v.target is None or not v.op or v.value is None or v.target.selector != ("total_cost",):
        return "re-check", ""
    delta, _ = _cost_delta(
        product,
        [
            Edit(set=Uri.parse(k), to=val)
            for k, val in overrides.items()
            if k.startswith("part://") and "#cost" in k
        ],
        build_dir,
    )
    rollups_path = build_dir / "bom" / "rollups.json"
    if not rollups_path.is_file():
        return "estimate", "BOM not built yet"
    import json

    total = (
        float(json.loads(rollups_path.read_text(encoding="utf-8")).get("total_cost", 0.0)) + delta
    )
    limit = v.value
    ok = compare(parse_quantity(total, "USD"), v.op, limit)
    return (
        "would-pass" if ok else "would-fail"
    ), f"{total:.2f} USD {v.op} {format_quantity(limit)} (declared costs)"


def _evidence_affected(evidence: str, affected: dict[str, str], affected_params: set[str]) -> bool:
    base = Uri_base(evidence)
    scheme, ident = base.split("://", 1)
    if scheme in ("part", "asm", "doc", "drawing"):
        return f"{scheme}:{ident}" in affected
    if scheme == "bom":
        return "bom" in affected
    if scheme == "calc":
        return bool(affected_params)
    from napkin2factory.core.registry import registry

    family = registry().produced_scheme(scheme)  # a domain's rule output (F1)
    return family is not None and f"{family.name}:{ident}" in affected


def _cost_delta(product: Product, edits: list[Edit], build_dir: Path) -> tuple[float, str]:
    """Delta from declared unit costs × quantities; geometry-driven costs are not estimated."""
    import json

    rollups_path = build_dir / "bom" / "rollups.json"
    qty: dict[str, int] = {}
    if rollups_path.is_file():
        data = json.loads(rollups_path.read_text(encoding="utf-8"))
        qty = {k: int(v["total_qty"]) for k, v in data.get("parts", {}).items()}
    delta = 0.0
    touched = False
    for e in edits:
        u = e.set
        if u.scheme == "part" and u.selector == ("cost", "unit") and u.id in product.parts:
            part = product.parts[u.id]
            old = float(part.cost.unit.to("USD").magnitude) if part.cost else 0.0
            try:
                new = float(parse_quantity(e.to, "USD").to("USD").magnitude)
            except UnitError:
                continue
            delta += (new - old) * qty.get(part.uri, 1)
            touched = True
    if touched:
        return round(delta, 2), "from declared unit costs × quantities"
    return (
        0.0,
        "no declared costs change; cost effects of geometry changes are not estimated "
        "(re-quote after rebuild)",
    )


def summarize(report: ImpactReport, product: Product) -> str:
    """Markdown summary in persona vocabulary (owner by default).

    The owner reads edited URIs without their ``scheme://`` prefix (``display_uri``); the
    stored impact (``to_dict``) keeps them whole.
    """
    persona = product.operator.persona
    patch = report.patch
    lines = [f"# Impact of {report.change_count} change(s)", ""]
    for e in report.edits:
        lines.append(f"- set `{display_uri(e['set'], persona)}` to **{e['to']}**")
    if report.edits:
        lines.append("")
    if patch is not None:
        lines += _patch_lines(patch, persona)
    if not report.firm:
        lines.append(
            "> Not built yet here: this is the full list, not the exact one. "
            "Run `n2f build` once and re-run impact for the exact set."
        )
        lines.append("")
    if report.cost_delta:
        sign = "+" if report.cost_delta > 0 else ""
        lines.append(f"**Cost:** {sign}{report.cost_delta:.2f} USD per unit ({report.cost_note}).")
    elif patch is not None and patch.applies:
        parts = [u for k in ("added", "changed") for u in patch.objects.get(k, [])]
        parts = [u for u in parts if u.startswith("part://")]
        lines.append(
            "**Cost:** known after the rebuild: the patch "
            + (f"touches {len(parts)} part(s)" if parts else "changes no part")
            + "; re-quote after `n2f build`."
        )
    else:
        lines.append(f"**Cost:** no change from declared costs ({report.cost_note}).")
    lines.append("")
    lines.append("## What gets rebuilt" if persona == "engineer" else "## What changes")
    added = set(patch.objects.get("added", [])) if patch is not None else set()
    if report.parts:
        lines.append(
            f"- {len(report.parts)} part(s): "
            + ", ".join(_part_words(p, product, patch, added) for p in report.parts)
        )
    if report.assemblies:
        lines.append(
            f"- {len(report.assemblies)} assembly(ies): "
            + ", ".join(f"`{a}`" for a in report.assemblies)
        )
    if report.drawings:
        lines.append(
            f"- {len(report.drawings)} drawing(s): " + ", ".join(f"`{d}`" for d in report.drawings)
        )
    if report.docs:
        lines.append(
            f"- {len(report.docs)} manual page(s): " + ", ".join(f"`{d}`" for d in report.docs)
        )
    if report.interfaces:
        lines.append(
            f"- {len(report.interfaces)} interface(s) to re-verify: "
            + ", ".join(f"`{i}`" for i in report.interfaces)
        )
    between = [p for p in report.ports if p["between_units"]]
    if between:
        lines.append(
            f"- {len(between)} joint(s) between units, so both sides are checked again: "
            + "; ".join(
                f"`{display_uri(p['interface'], persona)}` ("
                + " and ".join(s["unit_name"] or "no unit" for s in p["sides"])
                + ")"
                for p in between
            )
        )
    outputs = _domain_outputs(report.rules)
    for word, ids in outputs.items():
        lines.append(f"- {word}: {len(ids)} output(s): " + ", ".join(f"`{i}`" for i in ids))
    if "bom" in report.rules:
        lines.append("- the bill of materials")
    if not (report.parts or report.assemblies or report.docs or outputs or "bom" in report.rules):
        lines.append("- nothing is rebuilt: no artifact reads what you are changing")
    if patch is not None and patch.applies and patch.stale:
        lines.append(
            f"- {len(patch.stale)} more output(s) were out of date before this change and "
            "rebuild anyway"
        )
    lines.append("")
    if report.requirements:
        lines.append("## Requirements")
        lines.append(
            "_✓ would pass · ✗ would fail · ? needs a person to re-check · "
            "~ known only after the rebuild_"
        )
        for r in report.requirements:
            badge = {
                "would-pass": "✓ would pass",
                "would-fail": "✗ WOULD FAIL",
                "re-check": "? re-check",
                "estimate": "~ after rebuild",
            }[r.verdict]
            safety = " **(safety)**" if r.safety else ""
            lines.append(
                f"- {r.id} {r.title}{safety}: {badge}" + (f" — {r.detail}" if r.detail else "")
            )
        lines.append("")
    if report.signoffs_invalidated:
        lines.append("## Sign-offs that must be redone")
        for s in report.signoffs_invalidated:
            lines.append(f"- {s}: the evidence it was signed against changes")
        lines.append("")
    if report.kind == "design":
        lines.append("## Designer tasks")
        for t in report.tasks:
            lines.append(f"- [ ] {t}")
        lines.append("")
        lines.append(
            "Geometry-dependent verdicts above are estimates until the designer's work is "
            "rebuilt and checked."
        )
        lines.append("")
    if persona == "engineer":
        lines.append("## Rules")
        for rid in report.rules:
            lines.append(f"- `{rid}` ← {report.rule_reasons.get(rid, '')}")
        lines.append("")
    for n in report.notes:
        lines.append(f"_{n}_")
    return "\n".join(lines).rstrip() + "\n"


def _part_words(pid: str, product: Product, patch: PatchImpact | None, added: set[str]) -> str:
    """A part in the rebuild list: its revision step, or "added (rev A)" for a new one."""
    if f"part://{pid}" in added and patch is not None:
        return f"`{pid}` (added, rev {patch.revs.get(pid, 'A')})"
    if pid in product.parts:
        rev = product.parts[pid].rev
        return f"`{pid}` (rev {rev} → {next_rev(rev)})"
    return f"`{pid}`"


def _patch_lines(patch: PatchImpact, persona: str) -> list[str]:
    """The impact page's account of a patch: what it carries, or why it does not apply."""
    if not patch.applies:
        return [
            f"> The patch (`{patch.path}`) does not apply to the model as it is now, so "
            f"nothing below counts its changes: {patch.problem}",
            "",
        ]
    files = patch.files
    counts = [
        f"{len(files.get(k, []))} file(s) {k}"
        for k in ("added", "changed", "removed")
        if files.get(k)
    ]
    out = [
        f"This change request carries the designer's work as a patch (`{patch.path}`): "
        + (", ".join(counts) if counts else "no file changes")
        + ". The rebuild list and the verdicts below are firm only after `n2f build`.",
        "",
        "## What the patch changes",
    ]
    out += [f"- {s['words']}" for s in patch.scope]
    for state in ("added", "changed", "removed"):
        groups = _grouped(patch.objects.get(state, []), persona)
        if groups:
            out.append(f"- {state}: " + "; ".join(groups))
    if not patch.count:
        out.append("- no model object changes (the files it touches hold no design)")
    out.append("")
    return out


def _grouped(uris: list[str], persona: str, shown: int = 8) -> list[str]:
    """URIs grouped by kind in owner words: "5 part(s): `a`, `b` …" (at most ``shown`` each)."""
    from napkin2factory.core.registry import registry

    nouns = dict(_NOUNS)
    for d in registry().domains:
        words = d.vocabulary.get("owner", {})
        for fam in d.families:
            word = words.get(fam.name, fam.name)
            nouns.setdefault(fam.uri_scheme, (word, f"{word}(s)"))
    by: dict[str, list[str]] = {}
    for u in uris:
        by.setdefault(u.split("://", 1)[0], []).append(u.split("://", 1)[1])
    out = []
    for scheme, ids in by.items():
        one, many = nouns.get(scheme, (scheme, scheme))
        names = ", ".join(f"`{i}`" for i in ids[:shown])
        more = f" and {len(ids) - shown} more" if len(ids) > shown else ""
        out.append(f"{len(ids)} {one if len(ids) == 1 else many}: {names}{more}")
    return out


def _domain_outputs(rule_ids: list[str]) -> dict[str, list[str]]:
    """A domain's rules among ``rule_ids``, by the domain's owner word ("Wiring": ids)."""
    from napkin2factory.core.checks.stage import domain_word
    from napkin2factory.core.registry import registry

    owner = {
        rf.name: d.name for d in registry().domains if not d.in_place for rf in d.rule_families
    }
    out: dict[str, list[str]] = {}
    for rid in rule_ids:
        kind, _, ident = rid.partition(":")
        if kind in owner:
            out.setdefault(domain_word(owner[kind]), []).append(ident or rid)
    return out
