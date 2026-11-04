---
id: maintenance
title: Maintenance and checks
audience: [owner]
order: 30
depends_on: [req://REQ-019, req://REQ-017, req://REQ-020, req://REQ-021, part://inlet, part://e-stop, part://interlock]
---

# Maintenance and checks

## Every month

- **Bond test.** {{ req("REQ-019").statement }} Measure from the inlet's ground pin to the tray,
  the lid, the base beam, the columns and the actuator body. Any reading above the limit means
  a bonding jumper is loose.
- **E-stop test.** Start a jog, press the E-stop: the actuator must stop at once. {{ req("REQ-020").statement }}
- **Door test.** Start a jog, open the door: the actuator must stop at once. {{ req("REQ-021").statement }}
- **Fuse.** {{ req("REQ-017").statement }} Replace a blown fuse with the same T2.5 A time-delay type.

## Every year

- Check every frame bolt is tight and the platen screws are tight.
- Check the shroud and the door for cracks or clouding; replace a cracked one.
