---
id: installation
title: Installation
audience: [owner, engineer]
order: 10
depends_on: [part://stand, part://outer-shell, part://guard-shell, part://controller-box, param://circuit-rating, param://mains-voltage]
---

# Installation

## Where to put it

Stand the kiln on a non-combustible floor with at least 500 mm of free air on every side
and above; the footprint is {{ P["guard-outer-width"] }} wide by {{ P["guard-outer-depth"] }}
deep on a {{ P["stand-height"] }} stand. Leave {{ P["door-clearance"] }} beside the hinge side
for the door to swing {{ P["door-swing"] }}. The room needs ventilation to the outside.

## Power

**A licensed electrician must install a dedicated {{ P["circuit-rating"] }} circuit at
{{ P["mains-voltage"] }}** with a residual-current device and a local isolator within reach
of the operator. The element draws {{ P["element-power"] }}. The controller box carries the
label: "Dedicated {{ P["circuit-rating"] }} circuit. Installation by a licensed electrician
only." No wiring diagram is part of this package; the electrician wires the PID controller,
the solid-state relay, the thermocouple and the element to local code.

## Optional door switch

A door-operated switch that cuts the element supply when the door opens is recommended.
It is an installer option in this Revision; see the operation manual for the procedure that
applies without it.

## Mounting the body

1. Place the {{ part("stand").name | lower }} and check it stands level.
2. With two people, lift the shell assembly (bricks and door removed) onto the stand and
   bolt it through the four mounting holes with the {{ part("m6x16-bolt").name }} and nuts.
3. Fit the bricks, the door and the controller box as described in the assembly manual.
4. Have the electrician connect the power. Run the first firing to 200 degC with the door
   ajar to drive off moisture from the insulation.
