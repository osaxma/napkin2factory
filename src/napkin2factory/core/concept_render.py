"""Writing a concept card's YAML text; split from core/concepts.py (S-259)."""

from __future__ import annotations

from typing import Any

import yaml

from napkin2factory.concepts.screens import card_fields as screen_fields


def _flow(value: Any) -> str:
    return str(
        yaml.safe_dump(
            value, default_flow_style=True, sort_keys=False, allow_unicode=True, width=4096
        )
    ).strip()


def _scalar(key: str, value: Any) -> str:
    return str(yaml.safe_dump({key: value}, sort_keys=False, allow_unicode=True, width=88)).rstrip(
        "\n"
    )


def _reads_lines(section: str, fields: list[Any], given: Any = None) -> list[str]:
    """``#   screens read: width (a length, like 800 mm), …`` wrapped as comment lines.

    A field declared ``hint=False`` (a door's, read only when the card names one) is listed
    only when ``given`` (the card's section) already holds it (gate F, S-137).
    """
    present = set(given) if isinstance(given, dict) else set()
    items = [
        f"{f.key} ({f.kind}, like {f.example})" if f.unit else f"{f.key} (like {f.example})"
        for f in fields
        if f.section == section
        and (getattr(f, "hint", True) or present & {f.key, *getattr(f, "aliases", ())})
    ]
    if not items:
        return ["#   (no screen asks for anything here yet)"]
    lines, line = [], "#   screens read:"
    for i, item in enumerate(items):
        piece = f" {item}" + ("," if i < len(items) - 1 else "")
        if len(line) + len(piece) > 92:
            lines.append(line)
            line = "#    "
        line += piece
    return [*lines, line]


def _group_lines(section: str, fields: list[Any]) -> list[str]:
    """One comment line per group of optional fields, e.g. the structural ones (B-0253).

    ``#   when it carries a load: point_load, … (also: …)`` names the keys a screen reads only
    when the card gives them, so they are findable without being asked of every card.
    """
    groups: dict[str, list[str]] = {}
    for f in fields:
        group = getattr(f, "group", "")
        if f.section == section and group:
            groups.setdefault(group, []).append(f.key)
    return [f"#   {group}, also: {', '.join(keys)}" for group, keys in groups.items()]


def render_card(data: dict[str, Any], fields: list[Any] | None = None) -> str:
    """A card as commented YAML, every §3 section present, in the canonical order.

    ``data`` holds plain values (strings, lists, dicts) as read from YAML or dumped from a
    :class:`ConceptCard` in JSON mode with aliases. The comments name the fields the
    installed screens read (``fields``, default the system's and the domains'), so the
    skeleton follows the screens (F8).
    """
    fields = fields if fields is not None else screen_fields()
    cid = data["id"]
    lines = [
        f"# Concept card {cid}: one possible direction for the product.",
        "# Concepts sit outside the build: nothing here changes `n2f build`; edit freely.",
        f"# Read it back with `n2f concept show {cid}`; check it with `n2f concept lint`.",
        _scalar("id", cid),
        _scalar("title", data.get("title", "")),
        "# status: exploring | rejected | promoted (reject and promote set it for you)",
        _scalar("status", data.get("status", "exploring")),
    ]
    if data.get("based_on"):
        lines.append(_scalar("based_on", data["based_on"]) + "  # the card this one started from")
    lines += [
        "# refs: images under concepts/refs/ that informed this card (never geometry),",
        "#   e.g. [refs/sketch-01.jpg]",
        f"refs: {_flow(data.get('refs') or [])}",
        "# layout: where things go, in words",
        *_reads_lines("layout", fields, data.get("layout")),
        f"layout: {_flow(data.get('layout') or {})}",
        "# envelope: named rough sizes, any name; they seed parameters when this card is chosen",
        *_reads_lines("envelope", fields, data.get("envelope")),
        f"envelope: {_flow(data.get('envelope') or {})}",
        "# site: the space it must fit and what it plugs into; screening checks what its",
        "#   screens read, and these become requirements when chosen",
        *_reads_lines("site", fields, data.get("site")),
        *_group_lines("site", fields),
        f"site: {_flow(data.get('site') or {})}",
        "# style: look and feel,",
        "#   e.g. {preset: appliance, corner_radius: 8 mm, fastener_visibility: hidden-front}",
        f"style: {_flow(data.get('style') or {})}",
        "# modules: the units it is built from and why, when a reason applies (else leave it",
        "#   empty), e.g. {lid: {driver: [built-as-unit, serviced-as-unit]}};",
        "#   a massing line joins one with `module: lid`",
        f"modules: {_flow(data.get('modules') or {})}",
        "# massing: rough shapes from the kit, one line each, e.g.",
        "#   - {kit: enclosure, as: body, args: {length: 540 mm, width: 540 mm, height: 620 mm}}",
        "#   - {kit: block, as: lid, module: lid, args: {…}, at: {…}}",
    ]
    massing = data.get("massing") or []
    if massing:
        lines.append("massing:")
        lines += [f"  - {_flow(m)}" for m in massing]
    else:
        lines.append("massing: []")
    lines += [
        "# notes: anything worth remembering about this direction",
        _scalar("notes", data.get("notes")),
        "# written for you: screening by `n2f concept build`, decision by reject or promote",
        _scalar("screening", data.get("screening")),
        _scalar("decision", data.get("decision")),
    ]
    built = data.get("built")
    if built is not None:  # a card without built figures reads as before (R11, B-0278)
        flow = yaml.safe_dump(built, default_flow_style=True, sort_keys=False, width=10**6)
        lines += [
            "# measured from the built design by `n2f concept fork-from-model` or `concept switch`",
            f"built: {flow.strip()}",
        ]
    return "\n".join(lines) + "\n"
