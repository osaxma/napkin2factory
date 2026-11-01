"""The top: the base by coordinates, the pod onto it by its port, a clip onto each rail."""


def build(P, I, parts):  # noqa: N803
    """Place the base, then the pod and the clips through the pod's ports (P4)."""
    from napkin2factory.geometry.assembly import AssemblyResult, place, place_by

    res = AssemblyResult()
    res.add(place("part://base", parts["base"], translate=(0.0, 0.0, P.mm("base-z"))))
    res.add(place_by(I, res, "pod-mount", "asm://pod", parts["pod"], label="pod"))
    for side in ("left", "right"):
        res.add(place_by(I, res, "clip-rail", "part://clip", parts["clip"], onto=side, label=side))
    return res
