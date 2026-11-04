---
id: safety
title: Safety
audience: [owner]
safety: true
order: 1
depends_on: [req://REQ-010, req://REQ-011, req://REQ-012, req://REQ-014, req://REQ-015, req://REQ-017, req://REQ-018, req://REQ-019, req://REQ-020, req://REQ-021, req://REQ-022, part://e-stop, part://interlock, part://guard-shroud, part://guard-door, part://console-tray, param://rated-load, param://mains-voltage, param://tilt]
---

# Safety

This stand pushes with up to {{ P["rated-load"] }} on a specimen and runs from a
{{ P["mains-voltage"] }} wall socket. Read this page before the first test.

## Moving parts and pinch points

- The actuator moves the upper platen down onto the specimen. Keep hands, loose sleeves and
  hair out of the test zone while it moves.
- {{ req("REQ-020").statement }}
- {{ req("REQ-021").statement }} Never bridge or remove the interlock switch.
- The stand cannot lift a specimen out of the way by itself when the power is cut: a
  compressed specimen relaxes the screw back, which is the safe direction.

## Flying fragments and stored energy

- A spring or a snap-fit can break or spring out of the test zone. {{ req("REQ-022").statement }}
- Never test with the door open or the shroud removed. Wear eye protection.

## Mains power

- {{ req("REQ-019").statement }} Run the bond test of the maintenance page after any repair.
- {{ req("REQ-017").statement }} {{ req("REQ-018").statement }} Replace the fuse only with the
  rating on the label, a time-delay T2.5 A.
- Unplug the stand before opening the console.

## Tipping

- {{ req("REQ-014").statement }}
- {{ req("REQ-015").statement }} Do this before the first test: unanchored, a sideways push
  of about 26 N at the top of the frame tips the stand over.

## Structure

- The frame is sized for the rated load and for {{ P["test-cycles"] }} tests. {{ req("REQ-010").statement }}
  {{ req("REQ-011").statement }} {{ req("REQ-012").statement }}
- Do not exceed the rated load. The load cell reads it; stop the test if it is reached.
