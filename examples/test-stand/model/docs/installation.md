---
id: installation
title: Installation
audience: [owner]
order: 10
depends_on: [req://REQ-006, req://REQ-007, req://REQ-015, req://REQ-016, req://REQ-019, part://console-tray, part://inlet, param://bench-width-limit, param://bench-depth-limit, param://mains-voltage]
---

# Installation

## The bench

Choose a level, sturdy bench at least {{ P["bench-width-limit"] }} wide and
{{ P["bench-depth-limit"] }} deep. The stand weighs about {{ bom.total_mass }}, which one
person can lift; lift it by the console, not by the frame.

## Bolt it down

{{ req("REQ-015").statement }}

1. Set the stand on the bench where it will stay.
2. Mark the four anchor holes in the tray floor, and drill the bench top to match.
3. Fix the tray with four M6 bolts with washers and nuts, from the tray side.

## Power

Plug the supplied cord into a grounded 120 V, 60 Hz wall socket (NEMA 5-15). {{ req("REQ-016").statement }}
Do not share the circuit with a heater or a kettle.
