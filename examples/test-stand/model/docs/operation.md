---
id: operation
title: Operation
audience: [owner]
order: 20
depends_on: [req://REQ-001, req://REQ-002, req://REQ-004, req://REQ-005, req://REQ-020, req://REQ-021, req://REQ-023, part://actuator, part://load-cell, part://guard-door, param://rated-load, param://stroke, param://daylight-min, param://clear-width-min]
---

# Operation

## Before a test

1. Switch on at the inlet on the back of the console and check the red E-stop is pulled out.
2. Open the door. The interlock cuts the motor power, so the actuator cannot move.
3. Put the specimen on the lower platen, at the centre. The daylight under the upper platen is
   at least {{ P["daylight-min"] }} with the rod retracted and the clear width between the
   columns at least {{ P["clear-width-min"] }}.
4. Close the door until the interlock engages.
5. Zero the load cell.

## A test

The stand pushes up to {{ P["rated-load"] }} over a stroke of {{ P["stroke"] }}.
{{ req("REQ-023").statement }}

- Press the red E-stop or open the door at any time: the motor power is cut at once.
- To restart after the E-stop, twist it to release, then close the door.

## After a test

Open the door only when the actuator has stopped. Remove the specimen and keep the door closed
when the stand is idle.
