"""Inspector index entries for the electrical domain (M2).

Builds plain-JSON entries for ``supply://``, ``device://``, ``circuit://`` and
``conductor://`` objects when the product carries electrical content; returns ``{}``
otherwise.  Every model field shown is read through ``sctx.proxy`` (D5) so a change
to a shown field invalidates the ``report`` build rule.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from napkin2factory.core.checks.results import OWNER_WORDS
from napkin2factory.domains.electrical.model import (
    circuits,
    devices,
    has_content,
    parse_end,
    product_conductors,
    supply,
)
from napkin2factory.domains.electrical.owner.common import (
    circuit_title,
    device_name,
    end_words,
    part_name,
    read_connections,
)
from napkin2factory.domains.electrical.owner.vocabulary import PURPOSE_WORDS, ROLE_WORDS
from napkin2factory.report.units import display

if TYPE_CHECKING:
    from napkin2factory.core.domain import SectionContext
    from napkin2factory.core.loader import Product

_STATUS_RANK = {
    "fail": 0,
    "warn": 1,
    "needs-human": 2,
    "choice": 3,
    "pass": 4,
    "signed": 4,
    "skip": 5,
}


def _resolve_param(product: Product, val: Any, log: Any = None) -> Any:
    """Resolve a ``param://<slug>`` reference, recording the read when ``log`` is given."""
    text = str(val)
    if text.startswith("param://"):
        slug = text.removeprefix("param://")
        if log is not None:
            log.add(f"param://{slug}")
        return product.parameter_value(slug)
    return val


def _quantity(val: Any, units: str) -> str:
    """Plain string for a pint quantity or resolved value in manifest display units."""
    if hasattr(val, "magnitude") and hasattr(val, "units"):
        mag = val.magnitude
        num = int(mag) if isinstance(mag, float) and mag.is_integer() else mag
        return display(f"{num} {val.units:~P}", units)
    return display(str(val), units)


def _protection_summary(
    product: Product, record: dict[str, Any] | None, prot: Any, log: Any
) -> str:
    """Summary string for a circuit's upstream protection, recording reads via ``log``."""
    if record and isinstance(record.get("protection"), dict) and record["protection"].get("words"):
        return str(record["protection"]["words"])
    if prot is None:
        return "not declared"
    if prot == "supply":
        raw_sup = supply(product)
        if raw_sup is not None:
            sup_p = log and product
            _ = sup_p
            sp = raw_sup.protection
            if sp is not None and hasattr(sp, "upstream"):
                if log is not None:
                    log.add("supply://supply#protection.upstream")
                return str(sp.upstream)
            if sp is not None:
                if log is not None:
                    log.add("supply://supply#protection")
                return part_name(product, getattr(sp, "id", str(sp)), log)
        return "supply protection"
    scheme = getattr(prot, "scheme", "")
    pid = getattr(prot, "id", str(prot))
    if scheme == "device":
        return device_name(product, pid, log)
    if scheme == "part":
        return part_name(product, pid, log)
    return str(prot)


def _supply_protection_str(product: Product, sup: Any, log: Any) -> str | None:
    """Read ``sup.protection`` through the recording proxy and return plain words."""
    prot = sup.protection
    if prot is None:
        return None
    if hasattr(prot, "upstream"):
        up = str(prot.upstream)
        r = prot.rating
        if r is not None:
            r_val = _resolve_param(product, r, log)
            return f"{up} ({_quantity(r_val, product.manifest.units)})"
        return up
    return str(prot)


def _checks_for(
    uri: str,
    check_rows: list[dict[str, Any]],
    words: dict[str, str],
    units: str,
    *,
    has_built: bool,
) -> tuple[str, str, list[dict[str, Any]]]:
    """Status, status words, and check rows touching ``uri``."""
    matched: list[dict[str, Any]] = []
    suffix = f"@{uri}"
    for r in check_rows:
        rid = str(r.get("id", ""))
        subj = str(r.get("subject", ""))
        ev = r.get("evidence_keys") or {}
        if subj == uri or rid.endswith(suffix) or uri in ev:
            st = str(r.get("status", "skip"))
            msg = str(r.get("persona_message") or r.get("message", ""))
            matched.append(
                {
                    "uri": rid.partition("@")[0] if "@" in rid else rid,
                    "id": rid,
                    "title": display(str(r.get("title", "")), units),
                    "status": st,
                    "status_words": words.get(st, st),
                    "message": display(msg, units),
                }
            )
    if matched:
        worst = min(matched, key=lambda x: _STATUS_RANK.get(x["status"], 9))["status"]
    else:
        worst = "pass" if has_built else "skip"
    return worst, words.get(worst, worst), matched


def _circuit_cables(
    product: Product,
    c: Any,
    cid: str,
    record: dict[str, Any] | None,
    units: str,
    log: Any,
) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    """Record reads on ``c.connections`` and return ``(cables, terminals, devices, entries)``."""
    terminals: list[str] = []
    dev_uris: list[str] = []
    entry_uris: list[str] = []
    model_cables: list[dict[str, Any]] = []
    for idx, conn in enumerate(c.connections, start=1):
        wid = f"{cid}-{idx}"
        frm_raw = str(conn.from_)
        to_raw = str(conn.to)
        terminals.extend([frm_raw, to_raw])
        frm_ref = parse_end(frm_raw)
        to_ref = parse_end(to_raw)
        for ref in (frm_ref, to_ref):
            if ref.scheme == "device":
                du = f"device://{ref.id}"
                if du not in dev_uris:
                    dev_uris.append(du)
        frm_label = display(end_words(product, frm_raw, log), units)
        to_label = display(end_words(product, to_raw, log), units)
        len_val = _resolve_param(product, conn.length, log) if conn.length is not None else None
        via_uri = str(conn.via) if conn.via is not None else ""
        if via_uri and via_uri not in entry_uris:
            entry_uris.append(via_uri)
        model_cables.append(
            {
                "id": wid,
                "circuit": f"circuit://{cid}",
                "from": frm_raw,
                "to": to_raw,
                "from_label": frm_label,
                "to_label": to_label,
                "from_device": frm_ref.base,
                "to_device": to_ref.base,
                "conductor": str(conn.conductor or ""),
                "csa": "",
                "length": _quantity(len_val, units) if len_val is not None else "",
                "colour": str(conn.colour or ""),
                "via": via_uri,
            }
        )
    if record and record.get("wires"):
        by_id = {str(w.get("id", "")): w for w in record["wires"]}
        for mc in model_cables:
            built = by_id.get(mc["id"])
            if built:
                if built.get("csa_mm2") is not None:
                    mc["csa"] = display(f"{built['csa_mm2']:g} mm²", units)
                if not mc["length"] and built.get("length_m") is not None:
                    mc["length"] = display(f"{built['length_m']:g} m", units)
                if not mc["conductor"] and built.get("conductor"):
                    mc["conductor"] = str(built["conductor"])
    seen_terms: dict[str, None] = {}
    for t in terminals:
        seen_terms.setdefault(t, None)
    return model_cables, list(seen_terms), dev_uris, entry_uris


def electrical_inspector(sctx: SectionContext) -> dict[str, dict[str, Any]]:
    """Inspector entries for ``supply://``, ``device://``, ``circuit://``, ``conductor://``."""
    product, build_dir = sctx.product, sctx.build_dir
    if product is None or not hasattr(product, "families") or not has_content(product):
        return {}
    units = product.manifest.units
    words = dict(OWNER_WORDS)

    by_circuit: dict[str, dict[str, Any]] = {}
    for cid in circuits(product):
        rec_data = read_connections(build_dir, cid)
        if rec_data is not None:
            by_circuit[cid] = rec_data
            sctx.log.add(f"circuit://{cid}")
    has_built = bool(by_circuit)

    checks_path = build_dir / "checks" / "checks.json"
    check_rows: list[dict[str, Any]] = (
        json.loads(checks_path.read_text(encoding="utf-8")).get("results", [])
        if checks_path.is_file()
        else []
    )

    entries: dict[str, dict[str, Any]] = {}

    # 1. Circuits first so cables can be cross-linked to supply, devices, and conductors.
    cables_by_end: dict[str, list[dict[str, Any]]] = {}
    circuits_by_dev: dict[str, list[str]] = {}
    cables_by_conductor: dict[str, list[dict[str, Any]]] = {}

    for cid, raw_circ in sorted(circuits(product).items()):
        uri = f"circuit://{cid}"
        c = sctx.proxy(raw_circ, uri)
        rec = by_circuit.get(cid)
        title = display(circuit_title(c), units)
        purpose = str(c.purpose)
        dc = bool(c.dc)
        v_raw = _resolve_param(product, c.voltage, sctx.log) if c.voltage is not None else None
        voltage = (
            _quantity(v_raw, units)
            if v_raw is not None
            else (
                display(f"{rec['voltage_v']:g} V", units)
                if rec and rec.get("voltage_v") is not None
                else None
            )
        )
        prot = c.protection
        prot_words = _protection_summary(product, rec, prot, sctx.log)

        cables, term_list, dev_uris, entry_uris = _circuit_cables(
            product, c, cid, rec, units, sctx.log
        )
        for du in dev_uris:
            circuits_by_dev.setdefault(du, []).append(uri)
        for cb in cables:
            cables_by_end.setdefault(cb["from_device"], []).append(cb)
            if cb["to_device"] != cb["from_device"]:
                cables_by_end.setdefault(cb["to_device"], []).append(cb)
            if cb["conductor"]:
                cables_by_conductor.setdefault(cb["conductor"], []).append(cb)

        ratings: dict[str, Any] = {"dc": dc, "protection": prot_words}
        if voltage is not None:
            ratings["voltage"] = voltage

        diag_svg = build_dir / "electrical" / cid / "diagram.svg"
        status, status_words, checks_list = _checks_for(
            uri, check_rows, words, units, has_built=has_built
        )
        circ_entry: dict[str, Any] = {
            "kind": "circuit",
            "id": cid,
            "uri": uri,
            "name": title,
            "title": title,
            "purpose": purpose,
            "purpose_words": PURPOSE_WORDS.get(purpose, purpose),
            "voltage": voltage,
            "dc": dc,
            "protection": prot_words,
            "ratings": ratings,
            "devices": dev_uris,
            "terminals": term_list,
            "cables": cables,
            "entries": entry_uris,
            "status": status,
            "status_words": status_words,
            "checks": checks_list,
        }
        if diag_svg.is_file():
            circ_entry["diagram_anchor"] = f"wiring-{cid}"
        if c.notes:
            circ_entry["notes"] = display(str(c.notes), units)
        entries[uri] = circ_entry

    # 2. Supply
    raw_sup = supply(product)
    if raw_sup is not None:
        sup_uri = "supply://supply"
        sup = sctx.proxy(raw_sup, sup_uri)
        v_val = _resolve_param(product, sup.voltage, sctx.log)
        v_str = _quantity(v_val, units)
        phases = sup.phases
        freq_str = _quantity(sup.frequency, units) if sup.frequency is not None else None
        dc = bool(sup.dc)
        r_val = _resolve_param(product, sup.rating, sctx.log) if sup.rating is not None else None
        r_str = _quantity(r_val, units) if r_val is not None else None
        earthing = str(sup.earthing) if sup.earthing is not None else None
        region = str(sup.region) if sup.region is not None else None
        dedicated = bool(sup.dedicated)
        prot_str = _supply_protection_str(product, sup, sctx.log)
        raw_terms = sup.terminals
        sup_terms = list(raw_terms) if raw_terms is not None else raw_sup.terminal_names()
        sup_ratings: dict[str, Any] = {
            "voltage": v_str,
            "phases": phases,
            "dc": dc,
            "dedicated": dedicated,
        }
        if freq_str is not None:
            sup_ratings["frequency"] = freq_str
        if r_str is not None:
            sup_ratings["current"] = r_str
        if earthing is not None:
            sup_ratings["earthing"] = earthing
        if region is not None:
            sup_ratings["region"] = region
        if prot_str is not None:
            sup_ratings["protection"] = prot_str

        status, status_words, checks_list = _checks_for(
            sup_uri, check_rows, words, units, has_built=has_built
        )
        sup_entry: dict[str, Any] = {
            "kind": "supply",
            "id": "supply",
            "uri": sup_uri,
            "name": "Supply",
            "title": "Supply",
            "voltage": v_str,
            "phases": phases,
            "frequency": freq_str,
            "dc": dc,
            "rating": r_str,
            "earthing": earthing,
            "region": region,
            "dedicated": dedicated,
            "protection": prot_str,
            "ratings": sup_ratings,
            "terminals": sup_terms,
            "cables": cables_by_end.get(sup_uri, []),
            "status": status,
            "status_words": status_words,
            "checks": checks_list,
        }
        if sup.notes:
            sup_entry["notes"] = display(str(sup.notes), units)
        entries[sup_uri] = sup_entry

    # 3. Devices
    for did, raw_dev in sorted(devices(product).items()):
        dev_uri = f"device://{did}"
        dev = sctx.proxy(raw_dev, dev_uri)
        part_uri = str(dev.part)
        dname = display(device_name(product, did, sctx.log), units)
        role = str(dev.role)
        terms = list(dev.terminals)
        dev_ratings: dict[str, Any] = {}
        dr = dev.rating
        if dr is not None:
            for rf in ("voltage", "current", "power"):
                rv = getattr(dr, rf)
                if rv is not None:
                    dev_ratings[rf] = _quantity(_resolve_param(product, rv, sctx.log), units)
        dc_contact = dev.contact
        if dc_contact is not None:
            if dc_contact.current is not None:
                dev_ratings["contact_current"] = _quantity(dc_contact.current, units)
            if dc_contact.category is not None:
                dev_ratings["contact_category"] = str(dc_contact.category)

        status, status_words, checks_list = _checks_for(
            dev_uri, check_rows, words, units, has_built=has_built
        )
        dev_entry: dict[str, Any] = {
            "kind": "device",
            "id": did,
            "uri": dev_uri,
            "name": dname,
            "title": dname,
            "part": part_uri,
            "role": role,
            "role_words": ROLE_WORDS.get(role, role),
            "ratings": dev_ratings,
            "terminals": terms,
            "cables": cables_by_end.get(dev_uri, []),
            "circuits": sorted(circuits_by_dev.get(dev_uri, [])),
            "status": status,
            "status_words": status_words,
            "checks": checks_list,
        }
        if dev.instance is not None:
            dev_entry["instance"] = str(dev.instance)
        if dev.class_ is not None:
            dev_entry["class"] = str(dev.class_)
        if dev.safety is not None:
            dev_entry["safety"] = str(dev.safety)
        if dev.notes:
            dev_entry["notes"] = display(str(dev.notes), units)
        entries[dev_uri] = dev_entry

    # 4. Product conductors
    for cond_id, raw_cond in sorted(product_conductors(product).items()):
        cond_uri = f"conductor://{cond_id}"
        cond = sctx.proxy(raw_cond, cond_uri)
        label = display(str(cond.label), units)
        cond_kind = str(cond.kind)
        csa_str = _quantity(cond.csa, units) if cond.csa is not None else None
        amp_str = _quantity(cond.ampacity, units) if cond.ampacity is not None else None
        amb_str = _quantity(cond.ambient, units) if cond.ambient is not None else None
        max_t_str = _quantity(cond.max_temp, units) if cond.max_temp is not None else None
        insulation = cond.insulation
        region = str(cond.region) if cond.region is not None else None
        source = str(cond.source)
        verify = bool(cond.verify)
        cond_ratings: dict[str, Any] = {}
        if csa_str is not None:
            cond_ratings["csa"] = csa_str
        if amp_str is not None:
            cond_ratings["ampacity"] = amp_str
        if amb_str is not None:
            cond_ratings["ambient"] = amb_str
        if max_t_str is not None:
            cond_ratings["max_temp"] = max_t_str
        if insulation is not None:
            cond_ratings["insulation"] = str(insulation)
        if region is not None:
            cond_ratings["region"] = region

        status, status_words, checks_list = _checks_for(
            cond_uri, check_rows, words, units, has_built=has_built
        )
        cond_entry: dict[str, Any] = {
            "kind": "conductor",
            "id": cond_id,
            "uri": cond_uri,
            "name": label,
            "title": label,
            "conductor_kind": cond_kind,
            "csa": csa_str,
            "ampacity": amp_str,
            "ambient": amb_str,
            "max_temp": max_t_str,
            "insulation": insulation,
            "region": region,
            "source": source,
            "verify": verify,
            "ratings": cond_ratings,
            "cables": cables_by_conductor.get(cond_id, []),
            "status": status,
            "status_words": status_words,
            "checks": checks_list,
        }
        if cond.basis:
            cond_entry["basis"] = display(str(cond.basis), units)
        entries[cond_uri] = cond_entry

    return entries
