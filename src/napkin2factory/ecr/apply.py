"""Mechanical application of change requests: in-place YAML editing and sign-off invalidation.

Split from lifecycle.py (S-248).
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

from napkin2factory.core.loader import Product, load_product
from napkin2factory.core.model import Edit
from napkin2factory.core.units import UnitError, format_quantity, parse_quantity
from napkin2factory.core.vcs import Vcs
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip
from napkin2factory.ecr.revisions import _output_hashes
from napkin2factory.ecr.state import EcrError, _require, _transition


def _set_in_yaml(product: Product, edit: Edit) -> str:
    """Apply one edit to the right YAML file in place; return a human line."""
    u = edit.set
    if u.scheme == "param":
        path = product.paths.parameters
        data = load_roundtrip(path)
        params = data.setdefault("parameters", {})
        if u.id not in params:
            raise EcrError(f"param://{u.id} does not exist")
        entry = params[u.id]
        unit = entry.get("unit", "") or None
        try:
            q = parse_quantity(str(edit.to), unit)
            value: Any = q.to(unit).magnitude if unit else q.magnitude
        except Exception as exc:
            raise EcrError(f"cannot set param://{u.id} to {edit.to!r}: {exc}") from exc
        if "expr" in entry:
            raise EcrError(
                f"param://{u.id} is an expression ({entry['expr']}); "
                "set the parameters it depends on instead"
            )
        old = entry.get("value")
        new_value = int(value) if float(value).is_integer() else float(value)
        if not _edit_param_line(path, u.id, new_value):
            entry["value"] = new_value
            dump_roundtrip(path, data)
        return f"param://{u.id}: {old} → {new_value} {unit or ''}".strip()
    # selector edits on requirements, parts, assemblies, interfaces, decisions
    if u.scheme == "req":
        path = product.paths.requirements
        data = load_roundtrip(path)
        target = next((r for r in data.get("requirements", []) if r.get("id") == u.id), None)
    elif u.scheme == "dec":
        path = product.paths.decisions
        data = load_roundtrip(path)
        target = next((d for d in data.get("decisions", []) if d.get("id") == u.id), None)
    elif u.scheme in ("part", "asm", "iface"):
        folder = {
            "part": product.paths.parts,
            "asm": product.paths.assemblies,
            "iface": product.paths.interfaces,
        }[u.scheme]
        path = folder / f"{u.id}.yaml"
        data = load_roundtrip(path)
        target = data
    else:
        raise EcrError(
            f"edits cannot target {u.scheme}:// ({u}); supported: param, req, part, asm, iface, dec"
        )
    if target is None:
        raise EcrError(f"{u.base} does not exist")
    cur: Any = target
    for key in u.selector[:-1]:
        if key not in cur or cur[key] is None:
            cur[key] = {}
        cur = cur[key]
    last = u.selector[-1]
    old = cur.get(last) if isinstance(cur, dict) else None
    cur[last] = _coerce(edit.to, old)
    dump_roundtrip(path, data)
    return f"{u}: {old!r} → {cur[last]!r}"


def _edit_param_line(path: Path, slug: str, value: Any) -> bool:
    """Change ``value:`` on the parameter's own line, touching nothing else (one-line diff).

    Works for the flow-mapping style ``n2f init`` writes (``slug: {value: 1, unit: mm}``);
    returns False when the parameter is written in block style, so the caller falls back
    to a ruamel round-trip.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    pat = re.compile(
        rf"^(\s*{re.escape(slug)}\s*:\s*\{{.*?)(value\s*:\s*)([-+0-9.eE]+)(.*)$", re.DOTALL
    )
    for i, line in enumerate(lines):
        m = pat.match(line)
        if m:
            lines[i] = f"{m.group(1)}{m.group(2)}{value}{m.group(4)}"
            path.write_text("".join(lines), encoding="utf-8")
            return True
    return False


def _coerce(value: Any, old: Any) -> Any:
    """Keep the field's type where obvious: numbers stay numbers, quantities stay strings."""
    if isinstance(old, bool):
        return str(value).lower() in ("true", "yes", "1")
    if isinstance(old, (int, float)) and not isinstance(value, (int, float)):
        try:
            f = float(str(value).split()[0])
            return int(f) if f.is_integer() and isinstance(old, int) else f
        except ValueError:
            return value
    if isinstance(value, str):
        try:
            q = parse_quantity(value)
            return format_quantity(q) if not q.dimensionless else value
        except UnitError:
            return value
    return value


def _move_invalidated_signoffs(product: Product, lines: list[str]) -> None:
    """Move sign-off files citing a removed requirement or object to .yaml.invalid (S-215)."""
    from napkin2factory.core.uris import Uri
    from napkin2factory.core.yamlio import read_yaml

    reqs_path = product.paths.requirements
    known_req_ids: set[str] = set()
    if reqs_path.is_file():
        req_data = read_yaml(reqs_path)
        if isinstance(req_data, dict):
            known_req_ids = {
                str(r["id"])
                for r in req_data.get("requirements", [])
                if isinstance(r, dict) and "id" in r
            }

    params_path = product.paths.parameters
    known_param_ids: set[str] = set()
    if params_path.is_file():
        param_data = read_yaml(params_path)
        if isinstance(param_data, dict):
            known_param_ids = set(str(k) for k in param_data.get("parameters", {}).keys())

    for so_path in sorted(product.paths.signoffs.glob("REQ-*.yaml")):
        try:
            data = read_yaml(so_path)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        req_ref = str(data.get("requirement", ""))
        req_id = req_ref.replace("req://", "")
        invalid_reason = ""
        if req_id not in known_req_ids:
            invalid_reason = f"requirement {req_ref} was removed"
        else:
            for ev in data.get("evidence", []):
                try:
                    u = Uri.parse(str(ev))
                except Exception:
                    continue
                if u.scheme == "part" and not (product.paths.parts / f"{u.id}.yaml").is_file():
                    invalid_reason = f"cited part {u.base} was removed"
                    break
                if u.scheme == "asm" and not (product.paths.assemblies / f"{u.id}.yaml").is_file():
                    invalid_reason = f"cited assembly {u.base} was removed"
                    break
                if (
                    u.scheme == "iface"
                    and not (product.paths.interfaces / f"{u.id}.yaml").is_file()
                ):
                    invalid_reason = f"cited interface {u.base} was removed"
                    break
                if u.scheme == "param" and u.id not in known_param_ids:
                    invalid_reason = f"cited parameter {u.base} was removed"
                    break

        if invalid_reason:
            invalid_path = so_path.with_name(f"{so_path.name}.invalid")
            so_path.rename(invalid_path)
            lines.append(f"moved sign-off {so_path.name} → {invalid_path.name} ({invalid_reason})")


def apply(product: Product, ecr_id: str, snapshot: bool = True) -> list[str]:
    """Apply an approved change request to the model and take a snapshot."""
    ecr = _require(product, ecr_id)
    if ecr.status != "approved":
        raise EcrError(
            f"{ecr.id} is {ecr.status}; only approved change requests are applied "
            f"(`n2f ecr approve {ecr.id} --by <name>`)"
        )
    vcs = Vcs(product.root)
    vcs.require_repo_root()
    # S-215: Atomicity (Item 4). Ensure pre-apply state is clean and snapshotted.
    if not vcs.is_clean():
        vcs.snapshot(f"Approve {ecr.id}")

    lines: list[str] = []
    try:
        before = _output_hashes(product)
        for e in ecr.edits:
            lines.append(_set_in_yaml(product, e))
        if ecr.kind == "design":
            if ecr.patch:
                patch_path = product.root / ecr.patch
                if not patch_path.is_file():
                    raise EcrError(f"{ecr.id}: patch file {ecr.patch} not found")
                vcs.apply_patch(patch_path)
                lines.append(f"applied patch {ecr.patch}")
            for t in ecr.tasks:
                lines.append(f"task for the designer: {t}")

        # S-215: Sign-offs citing a removed part/requirement (Item 3)
        # Move such sign-offs to .invalid so the product loads cleanly.
        _move_invalidated_signoffs(product, lines)

        # validate the result before snapshotting
        fresh = load_product(product.root)
        # always a snapshot of its own (empty for a tasks-only design change), so the one before
        # it is the model as it stood before this change request (S-089, `_snapshot_before`)
        sha = (
            vcs.snapshot(f"Apply {ecr.id}: {ecr.title}", allow_empty=True)
            if snapshot
            else (vcs.head() or "")
        )
        _transition(
            fresh,
            fresh.ecrs[ecr.id],
            "applied",
            applied={
                "snapshot": sha,
                "at": dt.datetime.now().isoformat(timespec="seconds"),
                "before": before,
            },
        )
        if snapshot:
            vcs.snapshot(f"Record {ecr.id} as applied")
        return lines
    except Exception as exc:
        vcs.discard()
        raise EcrError(f"could not apply {ecr.id}: {exc}") from exc


__all__ = [
    "_coerce",
    "_edit_param_line",
    "_move_invalidated_signoffs",
    "_set_in_yaml",
    "apply",
]
