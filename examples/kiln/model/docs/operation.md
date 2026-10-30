---
id: operation
title: Operation
audience: [owner]
order: 20
depends_on: [req://REQ-001, req://REQ-009, req://REQ-018, part://latch, part://pid-controller, part://limit-controller, part://door-switch, part://kiln-shelf-set, param://max-temperature]
---

# Operation

## Before every firing

- Check the vent slots in both guards are clear: low on the body's sides, on its top, and
  along the top and bottom of the door guard.
- Check the door closes on its latch and the hinge post bolts are tight.
- Check the limit controller ({{ part("limit-controller").name }}) shows no trip and is set to
  {{ P["over-temperature-limit"] }}.
- Keep anything that can burn at least 500 mm away.

## Loading

The chamber is {{ P["chamber-width"] }} × {{ P["chamber-depth"] }} ×
{{ P["chamber-height"] }}. {{ req("REQ-001").statement }}

- Stand the shelf on its posts ({{ part("kiln-shelf-set").name }}) and put the ware on the
  shelf, not directly on the floor brick.
- Keep every piece 20 mm clear of the element grooves in the side and back walls. Ware that
  touches the element can short it or fuse to it.
- Do not lean anything against the door plug; it must close freely.

## Firing

1. Close the door and set the latch.
2. Set the programme on the {{ part("pid-controller").name }}. Do not exceed
   {{ P["max-temperature"] }}.
3. Stay in the building while the kiln is on.
4. There is no spy hole in this version. Do not open the door to look during a firing; read
   the temperature on the controller.

## Opening the door

**Switch the element off at the controller and the isolator before opening the door.** The
door switch also cuts the element power when the door opens, but it
is a back-up for a mistake, not the way to stop a firing. Open the door only below 200 degC,
standing to the hinge side; the escaping air is hot, and so are the door's inner face and the
chamber.

## If the over-temperature cut-out trips

The kiln stops heating and stays off. Let it cool with the door closed. Do not reset the
limit controller until you know why it tripped (a wrong programme, a stuck relay, a faulty
thermocouple); if you do not know, call the electrician.

## After firing

Let the kiln cool to room temperature before unloading. The guards may be touched; the
inner shell and the door tray behind them stay hot for hours.
