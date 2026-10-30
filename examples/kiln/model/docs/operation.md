---
id: operation
title: Operation
audience: [owner]
order: 20
depends_on: [req://REQ-009, part://latch, part://pid-controller, param://max-temperature]
---

# Operation

## Before every firing

- Check the vent slots in the guard are clear.
- Check the door closes on its latch and the hinge bolts are tight.
- Keep anything flammable at least 500 mm away.

## Firing

1. Load the chamber ({{ P["chamber-width"] }} × {{ P["chamber-depth"] }} ×
   {{ P["chamber-height"] }}). Keep work 20 mm clear of the element grooves.
2. Close the door and set the latch.
3. Set the programme on the {{ part("pid-controller").name }}. Do not exceed
   {{ P["max-temperature"] }}.
4. Stay in the building while the kiln is on.

## Opening the door

**Switch the element off at the isolator before opening the door.** {{ req("REQ-009").statement }}
Open the door only below 200 degC, standing to the hinge side; the escaping air is hot.

## After firing

Let the kiln cool to room temperature before unloading. The guard may be touched; the
inner shell behind it stays hot for hours.
