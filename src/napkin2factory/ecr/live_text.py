"""The owner's reading of a live impact: plain words, numbers labelled (N5, D17)."""

from __future__ import annotations

from typing import Any

from napkin2factory.core.graph.impact import _grouped
from napkin2factory.core.loader import Product
from napkin2factory.core.units import compare, format_quantity, parse_quantity
from napkin2factory.ecr import stale_text

#: How the checks' statuses read to an owner.
_STATUS = {
    "pass": "passes",
    "fail": "FAILS",
    "needs-human": "waits for a person's sign-off",
    "signed": "signed off",
    "warn": "passes with a warning",
    "skip": "not checked",
}


def _status(value: str | None) -> str:
    return _STATUS.get(value or "", "not checked yet" if value is None else value)


def _amount(value: Any, unit: str, places: int) -> str:
    return "not measured" if value is None else f"{value:,.{places}f} {unit}"


def _cost_label(cost: dict[str, Any]) -> str:
    """``Cost (estimate, from the parts' declared unit costs)``: the basis the figure carries."""
    return f"Cost ({cost.get('basis', 'estimate')}, from the parts' declared unit costs)"


def _change(block: dict[str, Any], places: int, label: str, same: str = "no change") -> str:
    """``46.7 kg → 47.1 kg (+0.4 kg)`` with a note when a total leaves parts out."""
    before = _amount(block["before"], block["unit"], places)
    after = _amount(block["after"], block["unit"], places)
    text = f"{label}: {before} → {after}"
    delta = block["delta"]
    if delta is not None:
        text += f" ({delta:+,.{places}f} {block['unit']})" if delta else f" ({same})"
    return text


def _size(dims: list[float] | None) -> str:
    return "not measured" if not dims else " × ".join(f"{d:g}" for d in dims) + " mm"


def summarize_live(impact: dict[str, Any], product: Product, title: str, ecr_id: str) -> str:
    """Markdown for ``n2f ecr impact``: what changed, what it does to the numbers, what follows."""
    persona = product.operator.persona
    lines = [f"# Impact of {ecr_id}: {title}", ""]
    files = impact["files"]
    total = sum(len(v) for v in files.values())
    if not total:
        lines += [
            "Nothing in the model has changed since this request started.",
            "Edit the files under `model/` (or `n2f ecr start --set …`), then run this again.",
            "",
        ]
    else:
        counts = ", ".join(
            f"{len(files[k])} {k}" for k in ("added", "changed", "removed") if files[k]
        )
        lines += [f"Since this request started: {total} file(s): {counts}.", ""]
        lines += _what_changed(impact, persona)
    cost = impact["cost"]
    requoted = cost.get("shape_changed_not_requoted", [])
    lines += ["## The numbers", ""]
    lines.append("- " + _change(impact["mass"], 2, "Mass (computed)"))
    same = "declared prices unchanged" if requoted else "no change"
    lines.append("- " + _change(cost, 0, _cost_label(cost), same=same))
    if requoted:
        names = ", ".join(f"`{p}`" for p in requoted)
        lines.append(f"  - Shape changed, price not re-quoted: {names}")
    if cost["unpriced"]:
        names = ", ".join(f"`{u.removeprefix('part://')}`" for u in cost["unpriced"])
        new = {u for u in cost["newly_unpriced"]}
        lines.append(
            f"  - no price on {len(cost['unpriced'])} part(s), so the cost is at least this: "
            + names
            + (f" ({len(new)} of them new)" if new else "")
        )
    if cost["not_in_an_assembly"]:
        names = ", ".join(f"`{u.removeprefix('part://')}`" for u in cost["not_in_an_assembly"])
        lines.append(f"  - in no assembly yet, so not in the mass or the cost: {names}")
    if cost["note"] and not cost["unpriced"]:
        lines.append(f"  - {cost['note']}")
    for asm, size in impact["envelope"].items():
        was, now = size["before"], size["after"]
        name = asm.removeprefix("asm://")
        if was == now:
            lines.append(f"- Envelope (computed) of `{name}`: {_size(now)} (no change)")
        else:
            lines.append(f"- Envelope (computed) of `{name}`: {_size(was)} → {_size(now)}")
    lines.append("")
    lines += _rebuilt(impact, persona)
    lines += _requirements(impact)
    lines += _signoffs(impact)
    if impact["kind"] == "design" and impact["tasks"]:
        lines += ["## Designer tasks", *(f"- [ ] {t}" for t in impact["tasks"]), ""]
    return "\n".join(lines).rstrip() + "\n"


def _what_changed(impact: dict[str, Any], persona: str) -> list[str]:
    out = ["## What changed", ""]
    for p in impact["parameters"]:
        if p["kind"] != "declared":
            continue
        was = p["before"] if p["before"] is not None else "(new)"
        now = p["after"] if p["after"] is not None else "(removed)"
        out.append(f"- size or setting `{p['id']}`: {was} → {now}")
    for state in ("added", "changed", "removed"):
        uris = [u for u in impact["objects"].get(state, []) if not u.startswith("param://")]
        for group in _grouped(uris, persona):
            out.append(f"- {state}: {group}")
    for s in impact["scope"]:
        out.append(f"- {s['words']}")
    computed = [p for p in impact["parameters"] if p["kind"] == "computed"]
    if computed:
        shown = ", ".join(f"`{p['id']}` {p['before']} → {p['after']}" for p in computed[:6])
        out.append(f"- computed from them: {shown}" + (" …" if len(computed) > 6 else ""))
    other = [
        f
        for k in ("added", "changed", "removed")
        for f in impact["files"][k]
        if f.startswith("model/geometry/")
    ]
    if other:
        out.append(
            "- shape scripts touched: " + ", ".join(f"`{f.rsplit('/', 1)[-1]}`" for f in other)
        )
    out.append("")
    return out


def _rebuilt(impact: dict[str, Any], persona: str) -> list[str]:
    rebuilt = impact["rebuilt"]
    out = ["## What was rebuilt" if persona == "engineer" else "## What was redone", ""]
    if not rebuilt:
        return [*out, "- nothing: no output reads what changed", ""]
    kinds: dict[str, list[str]] = {}
    for rid in rebuilt:
        kind, _, ident = rid.partition(":")
        if kind != "validate":
            kinds.setdefault(kind, []).append(ident or rid)
    words = {
        "part": "part(s)",
        "asm": "assembly(ies)",
        "drawing": "drawing(s)",
        "doc": "manual page(s)",
        "asmsheet": "assembly sheet(s)",
    }
    alone = {"bom": "the bill of materials", "checks": "the checks", "report": "the report"}
    for kind, ids in kinds.items():
        if kind in alone:
            out.append(f"- {alone[kind]}")
            continue
        names = ", ".join(f"`{i}`" for i in ids[:8]) + (" …" if len(ids) > 8 else "")
        out.append(f"- {len(ids)} {words.get(kind, kind)}: {names}")
    if impact["interfaces"]:
        out.append(f"- {len(impact['interfaces'])} joint(s) to check again")
    out.append("")
    return out


def is_structure_req(req: Any) -> bool:
    """Whether a requirement is checked by a structure.* calc or is of kind structure."""
    if req is None or getattr(req, "verify", None) is None:
        return False
    v = req.verify
    if getattr(v, "kind", None) == "structure":
        return True
    if getattr(v, "kind", None) == "calc":
        target = str(getattr(v, "target", None) or "")
        return target.startswith(("calc://structure.", "structure."))
    return False


def parse_figure(msg: str, op: str | None = None) -> tuple[str, str]:
    """Extract (value_str, limit_str) from a check message."""
    clean = msg.split(" — ")[0].split(" -- ")[0].strip()
    if "=" in clean:
        clean = clean.partition("=")[2].strip()
    ops = [op] if op else []
    ops += ["<=", ">=", "==", "!=", "<", ">"]
    for candidate in ops:
        if candidate and candidate in clean:
            val_part, _, limit_part = clean.partition(candidate)
            return val_part.strip(), limit_part.strip()
    return clean, ""


def figure_verdict(
    val_str: str, op: str | None, limit_str: str, after_status: str | None = None
) -> str:
    """Verdict as 'passes' or 'fails' in plain words."""
    if after_status == "fail":
        return "fails"
    if op and val_str and limit_str and val_str != "not measured":
        try:
            q_val = parse_quantity(val_str)
            q_lim = parse_quantity(limit_str)
            return "passes" if compare(q_val, op, q_lim) else "fails"
        except Exception:
            pass
    if after_status in ("pass", "signed"):
        return "passes"
    return "fails" if after_status == "fail" else "passes"


def format_structure_line(
    req: Any,
    before_msg: str,
    after_msg: str,
    after_status: str | None,
) -> str:
    """Format one structure line: '<title>: <before> → <after> against <limit> (<passes|fails>)'."""
    v = getattr(req, "verify", None)
    op = v.op if v else None
    before_val, _ = parse_figure(before_msg, op)
    after_val, limit_val = parse_figure(after_msg, op)
    if not before_val:
        before_val = "not measured"
    if not after_val:
        after_val = "not measured"
    if not limit_val and v and getattr(v, "value", None) is not None:
        limit_val = format_quantity(v.value)
    verdict = figure_verdict(after_val, op, limit_val, after_status)
    title = req.title if req is not None else ""
    return f"{title}: {before_val} → {after_val} against {limit_val} ({verdict})"


def format_req_line(req: Any, before_status: str | None, after_status: str | None) -> str:
    """Format a non-structure requirement line in plain words."""
    safety = " **(safety)**" if req and getattr(req, "safety", False) else ""
    was_w = _status(before_status)
    now_w = _status(after_status)
    verdict = now_w if before_status == after_status else f"{was_w} → {now_w}"
    title = req.title if req is not None else ""
    rid = getattr(req, "id", "") if req is not None else ""
    prefix = f"{rid} " if rid else ""
    return f"{prefix}{title}{safety}: {verdict}"


def _requirements(impact: dict[str, Any]) -> list[str]:
    lines = impact.get("requirement_lines")
    out: list[str] = []
    if lines is not None:
        if lines:
            out += ["## Requirements", ""]
            for line in lines:
                out.append(f"- {line}")
                r = None
                for req_item in impact.get("requirements", []):
                    rid = req_item.get("id", "")
                    title = req_item.get("title", "")
                    if (rid and rid in line) or (title and title in line):
                        r = req_item
                        break
                if r and r.get("after") == "fail" and not r.get("structure"):
                    if r.get("after_message") or r.get("before_message"):
                        before = r.get("before_message") or "no figure"
                        after = r.get("after_message") or "none"
                        out.append(f"  - figures: before {before}; after {after}")
            out.append("")
        elif impact.get("has_structure") is False:
            out += [
                "## Requirements",
                "",
                "- No structure requirement: the sag and tipping are not checked.",
                "",
            ]
    else:
        rows = impact.get("requirements", [])
        if rows or impact.get("has_structure") is False:
            out += ["## Requirements", ""]
            if impact.get("has_structure") is False:
                out.append("- No structure requirement: the sag and tipping are not checked.")
            for r in rows:
                if r.get("line"):
                    out.append(f"- {r['line']}")
                else:
                    safety = " **(safety)**" if r.get("safety") else ""
                    was, now = r.get("before"), r.get("after")
                    verdict = _status(now) if was == now else f"{_status(was)} → {_status(now)}"
                    out.append(f"- {r.get('id', '')} {r.get('title', '')}{safety}: {verdict}")
                    if now == "fail" and (r.get("after_message") or r.get("before_message")):
                        before = r.get("before_message") or "no figure"
                        after = r.get("after_message") or "none"
                        out.append(f"  - figures: before {before}; after {after}")
            out.append("")
    broken = [c for c in impact.get("other_checks", []) if c.get("after") == "fail"]
    if broken:
        out += ["## Other checks that now fail", ""]
        out += [f"- {c['message'] or c['id']}" for c in broken]
        out.append("")
    return out


def _signoffs(impact: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if impact["signoffs_removed"]:
        out += ["## Sign-offs that will no longer apply", ""]
        out += [f"- {e['file']}: {e['reason']}" for e in impact["signoffs_removed"]]
        out.append("")
    if impact["signoffs_invalidated"]:
        out += ["## Sign-offs that must be redone", ""]
        out += [
            f"- {sid}: the evidence it was signed against changes"
            for sid in impact["signoffs_invalidated"]
        ]
        out.append("")
    again = set(impact["signoffs_invalidated"])
    waiting = [s for s in impact.get("signoffs_waiting", []) if s not in again]
    if waiting:
        out += ["## Sign-offs `n2f ecr close` will ask for", ""]
        out += [f"- {sid}: waits for a person's sign-off" for sid in waiting]
        out.append("")
    if impact.get("stale_text"):
        out += ["## Words that may still give the old size", ""]
        out += stale_text.lines(impact["stale_text"])
        out.append("")
    return out


def failing(impact: dict[str, Any]) -> list[str]:
    """The requirements and other checks this change leaves failing."""
    ids = [r["id"] for r in impact.get("requirements", []) if r.get("after") == "fail"]
    ids += [c["id"] for c in impact.get("other_checks", []) if c.get("after") == "fail"]
    return ids


def next_step(impact: dict[str, Any], ecr_id: str, approve_first: bool = True) -> str:
    """What to do next: on a failure, drop or fix it; otherwise approve and close."""
    bad = failing(impact)
    if bad:
        names = ", ".join(i.removeprefix("req://") for i in bad[:5])
        return (
            f"this change makes {names} fail, and a failing change cannot close: drop it with "
            f"`n2f ecr abort {ecr_id}`, or edit the files and run `n2f ecr impact {ecr_id}` again"
        )
    if impact.get("has_structure") is False:
        return "ask the owner for the load and add a structure requirement"
    if approve_first:
        return (
            f"`n2f ecr approve {ecr_id} --by <name>`, or keep editing and run "
            f"`n2f ecr impact {ecr_id}` again; `n2f ecr abort {ecr_id}` drops it"
        )
    return (
        f"`n2f ecr approve {ecr_id} --by <name> && n2f ecr close {ecr_id}`, "
        f"or `n2f ecr abort {ecr_id}`"
    )
