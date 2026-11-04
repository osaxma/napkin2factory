"""Human-readable change request impact summaries; split from impact.py (S-184)."""

from __future__ import annotations

from napkin2factory.core.graph.impact_common import ImpactReport, PatchImpact, next_rev
from napkin2factory.core.graph.impact_patch import _NOUNS
from napkin2factory.core.loader import Product
from napkin2factory.core.uris import display_uri


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
    if not report.cost_complete:
        sign = "+" if report.cost_delta >= 0 else "−"
        amt = abs(report.cost_delta)
        lines.append(f"**Cost:** at least {sign}{amt:.2f} USD per unit ({report.cost_note}).")
    elif report.cost_delta:
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
    removed_signoffs = report.patch.signoffs_removed if report.patch else []
    removed_ids = {entry["id"] for entry in removed_signoffs}
    if removed_signoffs:
        lines.append("## Sign-offs that will no longer apply")
        for entry in removed_signoffs:
            lines.append(f"- {entry['file']}: {entry['reason']}")
        lines.append("")
    redo_signoffs = [sid for sid in report.signoffs_invalidated if sid not in removed_ids]
    if redo_signoffs:
        lines.append("## Sign-offs that must be redone")
        for sid in redo_signoffs:
            lines.append(f"- {sid}: the evidence it was signed against changes")
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
