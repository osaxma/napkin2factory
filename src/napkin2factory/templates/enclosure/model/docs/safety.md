---
id: safety
title: Safety
audience: [owner, engineer, manufacturer]
safety: true
order: 1
depends_on: [req://REQ-004]
---

# Safety

## Disclaimer

This design was produced with an AI system and has not been reviewed by a licensed
engineer. Have it checked by a qualified person before building or using it.

## Hazards

- Sheet edges are sharp until deburred. The manufacturer package requires: {{ req("REQ-004").statement | lower }}
- The box is a metal enclosure; if it houses mains-powered electronics it must be earthed by a qualified person.
