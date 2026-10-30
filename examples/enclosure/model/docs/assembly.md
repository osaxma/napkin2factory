---
id: assembly
title: Assembly
audience: [owner, engineer]
order: 10
depends_on: [part://base, part://lid, part://bracket, iface://lid-base-mount]
---

# Assembly

1. Fit the two {{ part("bracket").name }} brackets to the back wall of the {{ part("base").name }} with the supplied M6 hardware, {{ P["bracket-spacing"] }} apart.
2. Lay the {{ part("lid").name }} ({{ P["lid-thickness"] }} sheet) on the lip and fasten it with four {{ part("m4x10-screw").name }}.

## Manufacturer note

Tray: {{ part("base").material.spec }}, {{ part("base").finish }}, {{ part("base").tolerance_class }}.
Lid: {{ part("lid").material.spec }}, {{ part("lid").finish }}.
