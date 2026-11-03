"""The wiring model (ELECTRICAL_STAGE E2, E3): supply, devices, circuits, product conductors.

Four model families under ``model/electrical/`` (S-153, how the folders are laid out;
split into ``schemas.py`` and ``refs.py`` in S-184):

* ``supply`` — ``model/electrical/supply.yaml``, ``supply://supply``: the one supply the
  product plugs into (voltage, phases, frequency, rating, earthing, region, protection).
* ``device`` — ``model/electrical/devices/<id>.yaml``, ``device://<id>``: a powered or
  wired thing, naming the part it is (one part stays one parts-list line, E2).
* ``circuit`` — ``model/electrical/circuits/<id>.yaml``, ``circuit://<id>``: a list of
  connections between terminals (E3), its protection and its earth paths.
* ``conductor`` — ``model/electrical/conductors/<id>.yaml``, ``conductor://<id>``: the
  product's own conductor rows, beside the calc kit's table (E3: a product may add rows).

A connection end is ``device://<id>#<terminal>`` (S-154: connections name devices, not
parts); ``part://<id>#<terminal>`` is a shorthand when exactly one device names the part;
``supply://supply#L`` is a terminal of the supply; ``asm://<module>#<terminal>`` is a
terminal of a module supplied from elsewhere (``build: external``), reached through one of
its ports.  Terminals are free names (``L``, ``PE``, ``A1``, ``13``, ``+``, ``TC-``), so an
end is parsed here, not as a core URI (whose fragment reads ``1`` as an instance number).

:func:`validate_refs` checks every cross-reference and names the file, the thing and the fix.
Everything a wiring code would judge is left to the checks (E6); this module only refuses
what cannot be read: a part that does not exist, a terminal the device does not have, a
conductor nobody has on file, a cable entry the circuit does not pass.
"""

from __future__ import annotations

from napkin2factory.domains.electrical.model.refs import (
    circuits,
    conductor_ids,
    devices,
    devices_of_part,
    has_content,
    placed,
    product_conductors,
    resolve_end,
    supply,
    validate_refs,
    wired_devices,
)
from napkin2factory.domains.electrical.model.schemas import (
    CIRCUIT_FOLDER,
    CONDUCTOR_FOLDER,
    CONTACT_CATEGORIES,
    DEVICE_FOLDER,
    ENTRY_KIND,
    PURPOSES,
    ROLES,
    RULE,
    SUPPLY_FOLDER,
    Amps,
    Circuit,
    CircuitProtection,
    Connection,
    Contact,
    Device,
    DeviceUri,
    EarthPath,
    End,
    EndRef,
    Length,
    ProductConductor,
    ProtectiveUri,
    Rating,
    Supply,
    SupplyProtection,
    UpstreamProtection,
    Volts,
    Watts,
    parse_end,
)

__all__ = [
    "CIRCUIT_FOLDER",
    "CONDUCTOR_FOLDER",
    "CONTACT_CATEGORIES",
    "DEVICE_FOLDER",
    "ENTRY_KIND",
    "PURPOSES",
    "ROLES",
    "RULE",
    "SUPPLY_FOLDER",
    "Amps",
    "Circuit",
    "CircuitProtection",
    "Connection",
    "Contact",
    "Device",
    "DeviceUri",
    "EarthPath",
    "End",
    "EndRef",
    "Length",
    "ProductConductor",
    "ProtectiveUri",
    "Rating",
    "Supply",
    "SupplyProtection",
    "UpstreamProtection",
    "Volts",
    "Watts",
    "circuits",
    "conductor_ids",
    "devices",
    "devices_of_part",
    "has_content",
    "parse_end",
    "placed",
    "product_conductors",
    "resolve_end",
    "supply",
    "validate_refs",
    "wired_devices",
]
