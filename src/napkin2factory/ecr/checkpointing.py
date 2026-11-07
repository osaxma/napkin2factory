"""The checkpoint calls every state-changing command shares (v0.8 R4, R5; S-253).

A command that changes the design follows one pattern:

1. :func:`save_edits_first` before it changes anything, so the owner's loose edits are a
   checkpoint of their own and never folded into the command's step;
2. its change;
3. :func:`checkpoint` with a plain label ("Promoted C-002 (Steel frame)"), which replaces the
   command's old snapshot.

After a restore (``undo``, ``redo``, ``rollback``, a change request's ``abort``),
:func:`stale_after_restore` lists what the restored state no longer matches, and never revives
it (R5). :func:`open_change_request` tells ``undo`` where it must stop (R5) and ``rollback``
that it must refuse.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from pathlib import Path

import yaml

from napkin2factory.core import checkpoints as cps
from napkin2factory.core.checkpoints import Checkpoint, Vitals
from napkin2factory.core.loader import Product, load_product
from napkin2factory.core.vcs import FileChange, Vcs

#: What an approval hash leaves out: the requests' own records (S-252) and sign-offs, which are
#: checked at close, not approved (S-254 widens S-252); impact, approve, close and the
#: staleness report all use it.
APPROVAL_HASH_EXCLUDE = ("changes/", "model/signoffs/")
#: The states in which a change request is still open: edits count towards it (R5, R6).
OPEN_STATUSES = ("draft", "approved")
_PLAIN_SIGNOFF_RE = re.compile(r"^Signed off (?P<id>REQ-[A-Za-z0-9_-]+)(?P<ex>\s+\(EXAMPLE\))?$")


def _product(product: Product | Path) -> Product | None:
    """The loaded product; None when the model does not load (its vitals are then unknown)."""
    if isinstance(product, Product):
        return product
    try:
        return load_product(Path(product))
    except Exception:  # an unloadable model is the command's to report, not the checkpoint's
        return None


def _root(product: Product | Path) -> Path:
    return product.root if isinstance(product, Product) else Path(product)


def _req_title(root: Path, loaded: Product | None, rid: str) -> str | None:
    if loaded is not None and rid in loaded.requirements:
        return loaded.requirements[rid].title or None
    req_file = root / "model" / "requirements.yaml"
    if not req_file.is_file():
        return None
    try:
        data = yaml.safe_load(req_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    reqs = data.get("requirements") if isinstance(data, dict) else None
    if not isinstance(reqs, list):
        return None
    for item in reqs:
        if isinstance(item, dict) and item.get("id") == rid and item.get("title"):
            return str(item["title"])
    return None


def _enrich_signoff_label(root: Path, loaded: Product | None, label: str) -> str:
    m = _PLAIN_SIGNOFF_RE.match(label)
    if not m:
        return label
    rid = m.group("id")
    title = _req_title(root, loaded, rid)
    if not title:
        return label
    return f"Signed off {rid}: {title}{m.group('ex') or ''}"


def checkpoint(
    product: Product | Path,
    label: str,
    *,
    restores: str | None = None,
    undoes: str | None = None,
    redoes: str | None = None,
    vitals: Vitals | None = None,
) -> Checkpoint:
    """Save everything as a checkpoint with ``label`` and the product's current vitals.

    The vitals come from a fresh build only (``core/vitals.py``); pass ``vitals`` to copy
    them from the checkpoint a restore brings back (the folder then equals that state). The
    trailers ``restores`` / ``undoes`` / ``redoes`` make a restore (always recorded). With
    nothing changed and no trailer, no checkpoint is made and the newest is returned. The
    folder must be a tracked product root: callers keep their own guard.
    """
    from napkin2factory.core.vitals import current_vitals, recorded_vitals

    root = _root(product)
    loaded = _product(product)
    label = _enrich_signoff_label(root, loaded, label)
    if not vitals:
        if restores is not None:
            vitals = recorded_vitals(loaded or root, restores=restores)
        else:
            vitals = current_vitals(loaded) if loaded is not None else Vitals()
    vcs = Vcs(root)
    return cps.record(vcs, label, vitals, restores=restores, undoes=undoes, redoes=redoes)


def save_edits_first(product: Product | Path) -> Checkpoint | None:
    """Save unsaved edits as their own checkpoint, labelled from what changed (B-0293).

    None when there is nothing unsaved, or when the folder is not a tracked product root
    (those commands never saved anything). Call it before the command changes anything.
    """
    vcs = Vcs(_root(product))
    if not (vcs.is_tracked() and vcs.is_repo_root()) or vcs.is_clean():
        return None
    newest = vcs.snapshots(limit=1)
    if not newest:  # a folder with no history yet: the first save is the command's own
        return None
    from napkin2factory.core.vitals import current_vitals

    loaded = _product(product)
    vitals = current_vitals(loaded) if loaded is not None else Vitals()
    fallback = f"edits since #{vcs.snapshot_count()} {newest[0].label}"
    described = cps.describe_edits(vcs, newest[0].id)
    return cps.record(vcs, described or fallback, vitals, since=fallback if described else None)


def open_change_request(product: Product | Path) -> tuple[str, str] | None:
    """``(change request id, its start checkpoint id)`` for the open change request, or None.

    Open means status ``draft`` or ``approved`` with a ``baseline`` (M2b keeps at most one;
    the newest id wins). Its start checkpoint is the first checkpoint on the line right after
    ``baseline.checkpoint`` (the "Started ECR-x" step; the baseline itself when nothing
    follows it yet). ``undo`` stops there (R5) and ``rollback`` refuses while it exists.
    """
    loaded = _product(product)
    if loaded is None:
        return None
    open_ones = [
        e for e in loaded.ecrs.values() if e.status in OPEN_STATUSES and e.baseline is not None
    ]
    if not open_ones:
        return None
    ecr = max(open_ones, key=lambda e: e.id)
    assert ecr.baseline is not None
    log = cps.read(Vcs(loaded.root))
    base = next((c for c in log if c.id == ecr.baseline.checkpoint), None)
    if base is None:  # not on this line: undo reports it cannot tell where the request began
        return ecr.id, ecr.baseline.checkpoint
    after = next((c for c in log if c.number == base.number + 1), base)
    return ecr.id, after.id


def _title(text: str) -> str:
    return f" ({text})" if text else ""


def stale_after_restore(
    product: Product | Path, changes: Sequence[FileChange] | None = None
) -> list[str]:
    """Plain-words lines for every sign-off and approval the folder's state no longer matches.

    * a sign-off whose evidence changed since signing (read from the checks, which rebuild
      what the restore touched; the words are the ones ``n2f check`` shows);
    * an approved change request whose recorded model hash differs from the folder's
      (``Vcs.working_hash`` without ``changes/``, S-252).

    Nothing is revived or written (R5). If the checks cannot run, one line says so.
    """
    root = _root(product)
    lines: list[str] = []
    loaded = _product(root)
    if loaded is None:
        return ["the restored model does not load; run `n2f validate` to see why"]
    if loaded.signoffs:
        lines += _stale_signoffs(loaded, changes)
    approved = [
        e
        for e in loaded.ecrs.values()
        if e.status == "approved" and e.approval is not None and e.approval.model_hash
    ]
    if approved:
        now = Vcs(root).working_hash(exclude=APPROVAL_HASH_EXCLUDE)
        for e in sorted(approved, key=lambda e: e.id):
            assert e.approval is not None
            if e.approval.model_hash != now:
                lines.append(
                    f"the approval of {e.id}{_title(e.title)} no longer matches the model; "
                    f"look at its impact again (`n2f ecr impact {e.id}`), then approve it again"
                )
    return lines


def _calc_static_param_reads(product: Product, ident: str) -> set[str] | None:
    """Parameter slugs statically read by ``calc://<ident>``, or None when unsure."""
    mod_name, _, func_name = ident.partition(".")
    calc_file = product.paths.calcs / f"{mod_name}.py"
    if not func_name or not calc_file.is_file():
        return None
    try:
        tree = ast.parse(calc_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    if func_name not in funcs:
        return None
    reads: set[str] = set()
    seen: set[str] = set()
    queue = [func_name]
    while queue:
        cur = queue.pop()
        if cur in seen:
            continue
        seen.add(cur)
        fn = funcs[cur]
        p_names = {a.arg for a in fn.args.args if a.arg in {"P", "params"}}
        if not p_names and fn.args.args:
            p_names = {fn.args.args[0].arg}
        loop_vars: dict[str, set[str]] = {}
        for node in ast.walk(fn):
            if isinstance(node, (ast.For, ast.comprehension)) and isinstance(node.target, ast.Name):
                if isinstance(node.iter, (ast.Tuple, ast.List)) and all(
                    isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.iter.elts
                ):
                    loop_vars[node.target.id] = {
                        str(e.value) for e in node.iter.elts if isinstance(e, ast.Constant)
                    }
        for node in ast.walk(fn):
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
                if node.value.id in p_names:
                    sl = node.slice
                    if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                        reads.add(sl.value)
                    elif isinstance(sl, ast.Name) and sl.id in loop_vars:
                        reads.update(loop_vars[sl.id])
                    else:
                        return None
            elif isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in p_names
                ):
                    if (
                        len(node.args) == 1
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)
                    ):
                        reads.add(node.args[0].value)
                    elif (
                        len(node.args) == 1
                        and isinstance(node.args[0], ast.Name)
                        and node.args[0].id in loop_vars
                    ):
                        reads.update(loop_vars[node.args[0].id])
                    else:
                        return None
                elif any(
                    isinstance(a, ast.Name) and a.id in p_names
                    for a in [*node.args, *(kw.value for kw in node.keywords)]
                ):
                    if isinstance(node.func, ast.Name) and node.func.id in funcs:
                        queue.append(node.func.id)
                    else:
                        return None
    return reads


def _can_skip_signoff_build(product: Product, changes: Sequence[FileChange] | None) -> bool:
    """True when no sign-off's evidence can read any file ``changes`` touched (B-0269).

    Reuses ``ecr impact``'s static read sets (:func:`_static_reads`, :func:`_edit_matcher`,
    :func:`_evidence_affected`). Returns False whenever unsure so the build is never skipped
    wrongly.
    """
    from napkin2factory.core.graph.impact import (
        Uri_base,
        Uri_refs,
        _edit_matcher,
        _evidence_affected,
        _static_reads,
        dependent_params,
    )
    from napkin2factory.core.graph.rules import build_rules

    vcs = Vcs(product.root)
    prev_ref: str | None = None
    if vcs.is_tracked() and vcs.is_repo_root():
        log = cps.read(vcs, limit=2)
        if len(log) >= 2:
            prev_ref = log[1].id
            if changes is None and (
                log[0].restores is not None or log[0].label.startswith("Switched to ")
            ):
                changes = vcs._diff_trees(vcs.tree_of(log[1].id), vcs.tree_of(log[0].id))
    if changes is None:
        return False
    if not changes:
        return True
    edited_keys: list[str] = []
    for ch in changes:
        if ch.path.startswith(("changes/", "concepts/")):
            continue
        if ch.path.startswith("model/signoffs/"):
            return False
        if ch.path == "model/parameters.yaml":
            if prev_ref is None:
                return False
            old_doc, new_doc = cps._read_pair(vcs, prev_ref, "model/parameters.yaml")
            old_p, new_p = old_doc.get("parameters"), new_doc.get("parameters")
            if not isinstance(old_p, dict) or not isinstance(new_p, dict):
                return False
            slugs = [str(s) for s in set(old_p) | set(new_p) if old_p.get(s) != new_p.get(s)]
            for slug in slugs:
                edited_keys.append(f"param://{slug}")
                edited_keys.extend(f"param://{d}" for d in dependent_params(product, slug))
        elif ch.path == "model/requirements.yaml":
            if prev_ref is None:
                return False
            for rid in cps._list_id_edits(vcs, prev_ref, ch.path, "requirements"):
                edited_keys.append(f"req://{rid}")
        elif ch.path == "model/decisions.yaml":
            if prev_ref is None:
                return False
            for did in cps._list_id_edits(vcs, prev_ref, ch.path, "decisions"):
                edited_keys.append(f"dec://{did}")
        else:
            p = Path(ch.path)
            if len(p.parts) == 3 and p.parts[0] == "model":
                sub, stem, suf = p.parts[1], p.stem, p.suffix
                if sub == "parts" and suf in {".yaml", ".yml"}:
                    edited_keys.append(f"part://{stem}")
                elif sub == "assemblies" and suf in {".yaml", ".yml"}:
                    edited_keys.append(f"asm://{stem}")
                elif sub == "interfaces" and suf in {".yaml", ".yml"}:
                    edited_keys.append(f"iface://{stem}")
                elif sub == "docs" and suf == ".md":
                    edited_keys.append(f"doc://{stem}")
                else:
                    return False
            elif ch.path.startswith("model/") or ch.path in {"n2f.yaml", "style.yaml"}:
                return False
    if not edited_keys:
        return True
    edited_bases = {Uri_base(k) for k in edited_keys}
    affected_params = {k for k in edited_bases if k.startswith("param://")}
    rules = build_rules(product)
    touches = _edit_matcher(edited_keys, {p for r in rules for p in r.produced})
    affected: dict[str, str] = {}
    produced_affected: set[str] = set()
    for rule in rules:
        if rule.kind == "validate":
            continue
        if rule.id.startswith("part:") and affected_params:
            pid = rule.id.split(":", 1)[1]
            part = product.parts.get(pid)
            if part is not None and getattr(part.geometry, "module", None) is not None:
                affected[rule.id] = "module"
                for produced in rule.produced:
                    produced_affected.add(produced)
                    produced_affected.add(produced.split("#")[0])
                continue
        reads = _static_reads(product, rule)
        if any(
            touches(k) or k in produced_affected or Uri_base(k) in produced_affected for k in reads
        ):
            affected[rule.id] = "static"
            for produced in rule.produced:
                produced_affected.add(produced)
                produced_affected.add(produced.split("#")[0])
    for so in product.signoffs.values():
        if f"req://{so.requirement.id}" in edited_bases:
            return False
        for ev in so.evidence:
            base = Uri_base(str(ev))
            if "://" not in base:
                return False
            scheme, ident = base.split("://", 1)
            if base in edited_bases:
                return False
            if scheme == "calc":
                if affected_params:
                    calc_params = _calc_static_param_reads(product, ident)
                    if calc_params is None or any(
                        f"param://{s}" in affected_params for s in calc_params
                    ):
                        return False
            elif scheme in {"part", "asm", "doc", "drawing", "bom"}:
                if _evidence_affected(str(ev), affected, affected_params):
                    return False
            elif scheme == "iface":
                iface = product.interfaces.get(ident)
                if iface is None or any(
                    str(p) in produced_affected or str(p) in edited_bases for p in iface.parties
                ):
                    return False
                if any(f"param://{u.id}" in affected_params for u in Uri_refs(iface)) or any(
                    f"param://{s}" in affected_params for s in iface.expression_slugs()
                ):
                    return False
            elif scheme not in {"param", "req", "dec"}:
                return False
    return True


def _stale_signoffs(product: Product, changes: Sequence[FileChange] | None = None) -> list[str]:
    import json

    from napkin2factory.core.graph.runner import run_build

    if _can_skip_signoff_build(product, changes):
        return []
    try:
        # No renders: a sign-off is held against what the build measured, not against pictures,
        # and a restore should not wait for them (R12).
        run_build(product, target="checks", quiet=True, render=False)
        path = product.paths.build / "checks" / "checks.json"
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # a restored model that does not build: say so, do not hide it
        return [
            "could not check the sign-offs against the restored model "
            f"({str(exc).splitlines()[0] if str(exc) else type(exc).__name__}); "
            "run `n2f check` to see which are still valid"
        ]
    lines: list[str] = []
    for row in data.get("results", []):
        so = (row.get("detail") or {}).get("signoff") or {}
        if so.get("present") and not so.get("valid"):
            rid = str(row["id"]).removeprefix("req://")
            lines.append(
                f"the sign-off for {rid}{_title(row.get('title') or '')} no longer holds: "
                f"{so.get('why', 'the evidence changed')}; sign it again with `n2f signoff {rid}`"
            )
    return lines


def approved_checkpoint(vcs: Vcs, ecr_id: str) -> cps.Checkpoint | None:
    """The newest ``Approved <id> …`` checkpoint of the history, or None."""
    from napkin2factory.ecr.upgrade import carried_approval_label

    carried = carried_approval_label(ecr_id)
    for cp in cps.read(vcs):  # newest first
        if cp.label.startswith(f"Approved {ecr_id} ") or cp.label == carried:
            return cp
    return None


def matches_approval(vcs: Vcs, ecr_id: str) -> bool:
    """Whether the model is the one in the approval's checkpoint (same files left out as the hash).

    The hash in the request file can be typed by anyone; the checkpoint cannot (S-273).
    """
    cp = approved_checkpoint(vcs, ecr_id)
    if cp is None:
        return False
    return not [c for c in vcs.diff_working(cp.id) if not c.path.startswith(APPROVAL_HASH_EXCLUDE)]
