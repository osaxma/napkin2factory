---
id: safety
title: Safety
audience: [owner, engineer, manufacturer]
safety: true
order: 1
depends_on: [req://REQ-003, req://REQ-007, req://REQ-008, req://REQ-009, part://guard-shell]
---

# Safety

## Disclaimer

This design was produced with an AI system and has not been reviewed by a licensed
engineer. A kiln is a mains-powered appliance that reaches {{ P["max-temperature"] }}.
Have the design, the wiring and the finished kiln checked by qualified people before use.

## Hazards

- **Burns.** The firing chamber reaches {{ P["max-temperature"] }}. The inner shell behind
  the guard runs at roughly 110 degC (calc://thermal.skin_temperature). Only the ventilated
  {{ part("guard-shell").name | lower }} is meant to be touched; {{ req("REQ-003").statement }}
  Never remove the guard while the kiln is warm.
- **Electricity.** The element runs directly on {{ P["mains-voltage"] }} mains at
  {{ P["element-power"] }}. {{ req("REQ-008").statement }} All wiring is done by the
  electrician; this package contains no electrical design.
- **Opening the door.** {{ req("REQ-009").statement }}
- **Controller.** {{ req("REQ-007").statement }}
- **Fumes.** Firing clay and glazes releases fumes; ventilate the room.
- **Mass.** The complete kiln is heavy (see the report). Lift the body onto the stand with
  two people, bricks and door removed.
- **Sharp edges.** Sheet edges are deburred before coating; check before handling.
