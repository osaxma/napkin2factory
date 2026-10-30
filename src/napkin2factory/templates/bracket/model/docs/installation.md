---
id: installation
title: Installation
audience: [owner]
order: 10
depends_on: [part://l-bracket, param://shelf-load, param://hole-diameter]
---

# Installation

The {{ part("l-bracket").name }} carries a shelf load of up to {{ P["shelf-load"] }}.

## Fixing to the wall

1. Mark two holes {{ P["hole-spacing"] }} apart on the wall.
2. Drill for M8 anchors suited to the wall material; the bracket holes are {{ P["hole-diameter"] }}.
3. Bolt the vertical leg to the wall, then the shelf to the horizontal leg.

## Manufacturer note

Order the bracket as: {{ part("l-bracket").material.spec }}, {{ part("l-bracket").finish }},
tolerance class {{ part("l-bracket").tolerance_class }}.
