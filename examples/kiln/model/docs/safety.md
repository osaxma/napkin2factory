---
id: safety
title: Safety
audience: [owner, engineer, manufacturer]
safety: true
order: 1
depends_on: [req://REQ-003, req://REQ-007, req://REQ-008, req://REQ-009, req://REQ-018, req://REQ-019, part://guard-shell, part://door-guard, part://limit-controller, part://door-switch]
---

# Safety

## Disclaimer

This design was produced with an AI system and has not been reviewed by a licensed
engineer. A kiln is a mains-powered appliance that reaches {{ P["max-temperature"] }}.
Have the design, the wiring and the finished kiln checked by qualified people before use.

## Hazards

- **Burns.** The firing chamber reaches {{ P["max-temperature"] }}. The inner shell and the
  door's steel tray sit behind two ventilated guards and run much hotter than the guards; the
  report gives their computed temperatures (calc://thermal.shell_temperature and
  calc://thermal.door_skin_temperature). Only the {{ part("guard-shell").name | lower }}
  around the body and the {{ part("door-guard").name | lower }} in front of the door are meant
  to be touched. {{ req("REQ-003").statement }} The computed guard temperatures are an
  estimate; they are confirmed by measuring the guards and the latch on the finished kiln.
  Never run the kiln with either guard off, never block their vent slots, and never remove a
  guard while the kiln is warm. When the door is open, its inner face and the chamber are
  hot for hours after a firing.
- **Electricity.** The element is bare wire in the brick grooves, running directly on
  {{ P["mains-voltage"] }} mains at {{ P["element-power"] }}. {{ req("REQ-008").statement }}
  All wiring is done by the electrician; this package contains no wiring diagram.
- **Earth.** {{ req("REQ-019").statement }} A broken element touching the case must trip the
  circuit protection instead of making the case live. Do not paint over or remove the earth
  studs.
- **Over-temperature.** {{ req("REQ-018").statement }} The
  limit controller ({{ part("limit-controller").name }}) is set to {{ P["over-temperature-limit"] }}.
  If it trips, the kiln stops; find out why before resetting it, and call the electrician if
  you cannot.
- **Opening the door.** {{ req("REQ-009").statement }} Switch the element off before you
  open the door anyway; the door switch is a back-up, not the way
  to stop a firing. Never tape, wedge or bridge the door switch.
- **Controller.** {{ req("REQ-007").statement }} Keep the lid on; mains terminals are inside.
- **Fumes and fire.** Firing clay and glazes releases fumes; ventilate the room to the
  outside. Keep anything that can burn at least 500 mm from the kiln.
- **Dust.** Cutting or handling ceramic fiber board and insulating brick makes fine dust.
  Wear gloves and a dust mask, and clean up with a vacuum, not a brush.
- **Mass.** The complete kiln is heavy (see the report). Lift the body onto the stand with
  two people, with the bricks and the door out.
- **Pinch points.** Keep fingers clear of the hinge side and the latch when closing the door.
- **Sharp edges.** Sheet edges are deburred before coating; check before handling.
