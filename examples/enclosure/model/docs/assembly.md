---
id: assembly
title: Assembly
audience: [owner, engineer]
order: 10
depends_on: [part://base, part://lid, part://bracket, iface://lid-base-mount]
---

# Assembly

1. Fit the two wall brackets ({{ part("bracket").name }}) to the back wall of the {{ part("base").name | lower }}, {{ P["bracket-spacing"] }} apart, using M6 bolts and wall anchors suited to your wall (not part of this bill of materials).
2. Lay the {{ part("lid").name | lower }} ({{ P["lid-thickness"] }} sheet) on the lip and fasten it with four screws ({{ part("m4x10-screw").name }}).

## Manufacturer note

Tray: {{ part("base").material.spec }}, {{ part("base").finish }}, {{ part("base").tolerance_class }}.
Lid: {{ part("lid").material.spec }}, {{ part("lid").finish }}.
