"""Top assembly: the console, the portal frame on it and the guard around the test zone.

The three sub-assemblies are modelled in the one world frame (x across, y back to front, z up
from the bench), so each is placed at the origin.
"""


def build(P, I, parts):  # noqa: N803
    """Place the three sub-assemblies."""
    from napkin2factory.geometry.assembly import AssemblyResult, place

    res = AssemblyResult()
    for name in ("base-console", "portal-gantry", "guard-shield"):
        res.add(place(f"asm://{name}", parts[name], translate=(0, 0, 0), label=name))
    return res
