"""Assembly layout for the wall bracket: one part at the origin."""


def build(P, I, parts):  # noqa: N803 — P and I are the recording accessors
    """Place the single L-bracket at the origin.

    Args:
        P: parameter accessor (records every read).
        I: interface accessor.
        parts: built parts by id, each with ``.shape``.
    """
    from napkin2factory.geometry.assembly import AssemblyResult, place

    return AssemblyResult(instances=[place("part://l-bracket", parts["l-bracket"])])
