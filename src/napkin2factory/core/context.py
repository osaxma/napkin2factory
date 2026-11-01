"""A module's working context (P6): what one agent needs to change one assembly alone.

``n2f context asm://<id>`` prints it; files stay where they are.  The module is the assembly
and the phantoms folded into it (P7); a sub-assembly built as a unit of its own is a black
box here, named with its ports and the command that prints its own context.  The context
holds:

- the assembly YAML and its own parts (a part whose home, P5, is in the module), with the
  files an agent may open; parts listed here whose home is higher up (shared hardware) are
  named only;
- its scoped parameters, and the parameters it reads from outside, taken from the last
  build's recorded reads (the reads through an interface left to the joint, as in the reach
  check) and from its parameters' expressions; it says so when nothing is built;
- its ports, each with the other party's frame (resolved, in that part's own coordinates),
  not its geometry; the joints that close inside it;
- the requirements allocated to it or its own parts;
- the two commands that build and check it alone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from napkin2factory.core.build_units import PHANTOM_WORDS, BuildUnits, driver_words, unit_title
from napkin2factory.core.checks.modules import RowModules
from napkin2factory.core.expr import ExprError, referenced_names
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.loader import Product
from napkin2factory.core.units import format_quantity


def _rel(product: Product, path: Path) -> str:
    try:
        return path.resolve().relative_to(product.root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _value(product: Product, slug: str) -> str:
    try:
        return format_quantity(product.parameter_value(slug))
    except Exception as exc:  # an invalid expression is reported by validate; say it here too
        return f"invalid: {exc}"


def _names(expr: str | None) -> list[str]:
    try:
        return referenced_names(expr) if expr else []
    except ExprError:
        return []


def members(units: BuildUnits, aid: str) -> list[str]:
    """``aid`` and the phantoms folded into it, through phantoms only (a unit stops the walk)."""
    out = [aid]
    todo = [aid]
    product = units.product
    while todo:
        cur = todo.pop()
        for c in product.assemblies[cur].children:
            if c.asm is None or c.asm.id not in product.assemblies or c.asm.id in out:
                continue
            if units.is_unit(c.asm.id):
                continue
            out.append(c.asm.id)
            todo.append(c.asm.id)
    return out


def module_context(product: Product, aid: str, build_dir: Path | None = None) -> dict[str, Any]:
    """The context of ``asm://<aid>`` as a JSON-ready dict (see the module docstring)."""
    build_dir = build_dir or product.paths.build
    units = BuildUnits(product)
    tree = units.tree
    rows = RowModules(product, units)
    asm = product.assemblies[aid]
    mine = members(units, aid)
    mine_set = set(mine)
    tops = set(units.tops())
    files: list[str] = []

    def add_file(path: Path | None) -> str | None:
        if path is None:
            return None
        rel = _rel(product, path)
        if rel not in files:
            files.append(rel)
        return rel

    def geometry_file(geometry: Any) -> str | None:
        module = getattr(geometry, "module", None)
        return add_file(product.paths.model / module) if module else None

    assemblies = []
    for a in mine:
        rec = product.assemblies[a]
        assemblies.append(
            {
                "id": a,
                "name": rec.name,
                "file": add_file(product.files[rec.uri]),
                "geometry": geometry_file(rec.geometry),
                "yaml": product.files[rec.uri].read_text(encoding="utf-8"),
            }
        )
    parts: list[dict[str, Any]] = []
    shared: list[dict[str, Any]] = []
    seen: set[str] = set()
    sub_units: list[dict[str, Any]] = []
    for a in mine:
        for c in product.assemblies[a].children:
            if c.asm is not None and c.asm.id in product.assemblies and units.is_unit(c.asm.id):
                sub = product.assemblies[c.asm.id]
                sub_units.append(
                    {
                        "id": sub.id,
                        "name": sub.name,
                        "qty": c.qty,
                        "ports": [str(u) for u in sub.ports],
                        "context": f"n2f context asm://{sub.id}",
                    }
                )
            if c.part is None or c.part.id in seen or c.part.id not in product.parts:
                continue
            seen.add(c.part.id)
            part = product.parts[c.part.id]
            home = tree.home(part.uri)
            qty = sum(
                x.qty
                for m in mine
                for x in product.assemblies[m].children
                if x.part is not None and x.part.id == part.id
            )
            if home in mine_set:
                parts.append(
                    {
                        "id": part.id,
                        "name": part.name,
                        "kind": part.kind,
                        "qty": qty,
                        "file": add_file(product.files[part.uri]),
                        "geometry": geometry_file(part.geometry),
                        "yaml": product.files[part.uri].read_text(encoding="utf-8"),
                    }
                )
            else:
                shared.append(
                    {
                        "id": part.id,
                        "name": part.name,
                        "qty": qty,
                        "home": f"asm://{home}" if home else None,
                    }
                )
    own_params = [
        {
            "param": slug,
            "value": _value(product, slug),
            "expr": p.expr,
            "unit": p.unit,
            "export": p.export,
            "description": p.description or "",
        }
        for slug, p in sorted(product.parameters.items())
        if p.scope is not None and p.scope.id == aid
    ]
    own_slugs = {r["param"] for r in own_params}
    if own_params:
        add_file(product.paths.parameters)
    manifest = Manifest.load(build_dir)
    readers = _module_readers(product, manifest, mine_set)
    built = bool(readers)
    read_by: dict[str, set[str]] = {}
    for reader, entry_reads in readers.items():
        for slug in entry_reads:
            if slug not in own_slugs:
                read_by.setdefault(slug, set()).add(reader)
    for slug, p in sorted(product.parameters.items()):
        if slug not in own_slugs:
            continue
        for name in _names(p.expr):
            if name in product.parameters and name not in own_slugs:
                read_by.setdefault(name, set()).add(f"param://{slug}")
    outside = []
    for slug, who in sorted(read_by.items()):
        p = product.parameters[slug]
        outside.append(
            {
                "param": slug,
                "value": _value(product, slug),
                "scope": str(p.scope) if p.scope is not None else None,
                "export": p.export,
                "read_by": sorted(who),
            }
        )
    from napkin2factory.geometry.accessors import resolve_interface

    ports = []
    for iuri in asm.ports:
        iface = product.interfaces.get(iuri.id)
        if iface is None:
            continue  # a port's file is the joint's, shared with the other side: not listed
        try:
            resolved = resolve_interface(product, iface)
        except Exception:
            resolved = iface
        party_rows = []
        for party in iface.parties:
            puri = str(party)
            home = tree.home(puri)
            frame = resolved.frame_for(puri)
            pname = product.parts[party.id].name if party.id in product.parts else puri
            party_rows.append(
                {
                    "part": puri,
                    "name": pname,
                    "home": f"asm://{home}" if home else None,
                    "inside": home is not None and home in tree.below(aid),
                    "frame": {
                        "origin": [_mm(x) for x in frame.origin],
                        "normal": list(frame.normal),
                        "x_axis": list(frame.x_axis) if frame.x_axis is not None else None,
                    },
                }
            )
        ports.append(
            {
                "iface": iface.uri,
                "kind": iface.kind,
                "description": iface.description or "",
                "file": _rel(product, product.files[iface.uri]),
                "parties": party_rows,
                "offset": _mm(resolved.offset),
                "hardware": [
                    {
                        "part": str(h.part),
                        "per_hole": h.per_hole,
                        "per_joint": h.per_joint,
                    }
                    for h in iface.hardware_items()
                ],
                "closes_in": f"asm://{units.closing().get(iface.id)}"
                if units.closing().get(iface.id)
                else None,
            }
        )
    inside = []
    for iid, where in sorted(units.closing().items()):
        if where in mine_set:
            iface = product.interfaces[iid]
            inside.append(
                {
                    "iface": iface.uri,
                    "kind": iface.kind,
                    "parties": [str(x) for x in iface.parties],
                    "file": add_file(product.files[iface.uri]),
                }
            )
    own_part_uris = {f"part://{p['id']}" for p in parts}
    subjects = own_part_uris | {f"asm://{a}" for a in mine}
    reqs = []
    for rid, req in sorted(product.requirements.items()):
        ruri = f"req://{rid}"
        named = {str(a.base) for a in req.allocation} if isinstance(req.allocation, list) else set()
        named |= {p.uri for p in product.parts.values() if any(str(s) == ruri for s in p.satisfies)}
        named |= {
            a.uri for a in product.assemblies.values() if any(str(s) == ruri for s in a.satisfies)
        }
        if not named & subjects:
            continue
        reqs.append(
            {
                "id": rid,
                "title": req.title,
                "statement": req.statement,
                "safety": req.safety,
                "verify": req.verify.kind if req.verify else None,
                "target": str(req.verify.target)
                if req.verify is not None and req.verify.target is not None
                else None,
                "allocated": sorted(named),
                "checked_here": rows.requirement_in(req, aid),
            }
        )
    is_top = aid in tops
    parents = sorted(
        a.uri
        for a in product.assemblies.values()
        if any(c.asm is not None and c.asm.id == aid for c in a.children)
    )
    return {
        "module": asm.uri,
        "name": asm.name,
        "build": "top" if is_top else asm.build,
        "title": unit_title(asm.name, is_top)
        if units.is_unit(aid)
        else f"{asm.name}, {PHANTOM_WORDS}",
        "why": [driver_words().get(d, d) for d in asm.driver],
        "inside": parents,
        "assemblies": assemblies,
        "parts": parts,
        "shared_parts": shared,
        "sub_assemblies": sub_units,
        "parameters": {
            "own": own_params,
            "outside": outside,
            "built": built,
            "note": ""
            if built
            else (
                "nothing built yet: the parameters its parts and placement read are known "
                f"after `n2f build --asm {aid}`; only those its own expressions name are listed"
            ),
        },
        "ports": ports,
        "joints_inside": inside,
        "requirements": reqs,
        "files": files,
        "commands": {
            "build": f"n2f build --asm {aid}",
            "check": f"n2f check --scope asm://{aid}",
        },
        **_domain_context(product, aid, mine),
    }


def _domain_context(product: Product, aid: str, mine: list[str]) -> dict[str, Any]:
    """What registered domains add to the module's context (F1), only when they add any.

    ``{"domains": [{"name", "title", "lines"}]}``; a product no domain has content in gets
    no key, so its context reads exactly as before.
    """
    from napkin2factory.core.registry import registry

    out = []
    for c in registry().context_contributions():
        lines = c.collect(product, aid, mine)
        if lines:
            out.append({"name": c.name, "title": c.title, "lines": list(lines)})
    return {"domains": out} if out else {}


def _mm(v: Any) -> Any:
    if isinstance(v, (int, float)):
        return round(float(v), 4)
    return str(v)  # unresolved (an invalid expression): shown as written


def _module_readers(product: Product, manifest: Manifest, mine: set[str]) -> dict[str, list[str]]:
    """Reader URI → parameter slugs it read directly in the last build (interface reads left out).

    The module's readers: the part rules of its own parts (home in ``mine``) and the assembly
    rules of ``mine``.
    """
    tree = BuildUnits(product).tree
    out: dict[str, list[str]] = {}
    for rid, entry in sorted(manifest.entries.items()):
        kind, _, ident = rid.partition(":")
        if kind == "part" and ident in product.parts and tree.home(f"part://{ident}") in mine:
            reader = f"part://{ident}"
        elif kind == "asm" and ident in mine:
            reader = f"asm://{ident}"
        else:
            continue
        skip = set(entry.iface_reads)
        out[reader] = [
            k.removeprefix("param://").split("#", 1)[0]
            for k in entry.reads
            if k.startswith("param://") and k not in skip
        ]
    return out


def render_text(ctx: dict[str, Any]) -> str:
    """The context as Markdown for an agent to read (``--json`` is the same, for tools)."""
    out: list[str] = []
    add = out.append
    add(f"# Module {ctx['module']}: {ctx['name']}")
    add("")
    why = f" ({'; '.join(ctx['why'])})" if ctx["why"] else ""
    inside = f" Inside {', '.join(ctx['inside'])}." if ctx["inside"] else ""
    add(f"{ctx['title']}{why}.{inside}")
    add("")
    add("## Work on it alone")
    add(f"- build it and what it needs: `{ctx['commands']['build']}`")
    add(f"- check it (its own checks only): `{ctx['commands']['check']}`")
    add("")
    add("## Its files (a port's file is shared with the other side: see Ports)")
    out += [f"- {f}" for f in ctx["files"]]
    for a in ctx["assemblies"]:
        add("")
        add(f"## Assembly {a['id']} ({a['file']})")
        add("```yaml")
        add(a["yaml"].rstrip())
        add("```")
    add("")
    add("## Its own parts")
    if not ctx["parts"]:
        add("none")
    for p in ctx["parts"]:
        add("")
        geo = f", geometry {p['geometry']}" if p["geometry"] else ""
        add(f"### {p['id']} × {p['qty']}: {p['name']} ({p['file']}{geo})")
        add("```yaml")
        add(p["yaml"].rstrip())
        add("```")
    if ctx["shared_parts"]:
        add("")
        add("## Parts listed here but defined higher up (shared hardware)")
        out += [
            f"- {p['id']} × {p['qty']}: {p['name']} (home {p['home'] or 'none'})"
            for p in ctx["shared_parts"]
        ]
    if ctx["sub_assemblies"]:
        add("")
        add("## Units inside it (black boxes: each has its own context)")
        out += [
            f"- asm://{s['id']} × {s['qty']}: {s['name']}; ports "
            f"{', '.join(s['ports']) or 'none'}; `{s['context']}`"
            for s in ctx["sub_assemblies"]
        ]
    params = ctx["parameters"]
    add("")
    add(f"## Its parameters (scope {ctx['module']})")
    if not params["own"]:
        add("none scoped to it (unscoped parameters are the whole product's)")
    for r in params["own"]:
        expr = f" = {r['expr']}" if r["expr"] else ""
        shared_word = " (exported: its parent may read it)" if r["export"] else ""
        add(f"- {r['param']}: {r['value']}{expr}{shared_word}. {r['description']}".rstrip())
    add("")
    add("## Parameters it reads from outside")
    if params["note"]:
        add(params["note"])
    if not params["outside"] and not params["note"]:
        add("none")
    for r in params["outside"]:
        where = r["scope"] or "the whole product"
        add(f"- {r['param']}: {r['value']} ({where}); read by {', '.join(r['read_by'])}")
    add("")
    add("## Ports: its joints with the rest of the product")
    if not ctx["ports"]:
        add("none")
    for port in ctx["ports"]:
        add("")
        add(f"### {port['iface']} ({port['kind']}, {port['file']})")
        if port["description"]:
            add(port["description"])
        for party in port["parties"]:
            side = "inside" if party["inside"] else "outside"
            f = party["frame"]
            add(
                f"- {side}: {party['part']} ({party['name']}, home {party['home']}); frame in "
                f"its own coordinates (mm): origin {f['origin']}, normal {f['normal']}, "
                f"x_axis {f['x_axis']}"
            )
        add(f"- offset: {port['offset']} mm; closes in {port['closes_in']}")
        hw = ", ".join(
            f"{h['part']} ({h['per_hole']} per hole)"
            if h["per_hole"]
            else f"{h['part']} ({h['per_joint']} per joint)"
            for h in port["hardware"]
        )
        add(f"- hardware: {hw or 'none'}")
    add("")
    add("## Joints inside it")
    if not ctx["joints_inside"]:
        add("none")
    out += [
        f"- {j['iface']} ({j['kind']}): {' + '.join(j['parties'])} ({j['file']})"
        for j in ctx["joints_inside"]
    ]
    add("")
    add("## Requirements allocated to it or its parts")
    if not ctx["requirements"]:
        add("none")
    for r in ctx["requirements"]:
        safety = " (safety)" if r["safety"] else ""
        here = "" if r["checked_here"] else "; checked with the assembly above it"
        target = f" {r['target']}" if r["target"] else ""
        add(f"- {r['id']}{safety}: {r['title']}. Verified by {r['verify']}{target}{here}")
    for d in ctx.get("domains", []):  # a domain's contribution (F1)
        add("")
        add(f"## {d['title']}")
        out += d["lines"]
    return "\n".join(out) + "\n"
