"""The wiring's words for the owner (F1 §3.8; M4 refines them).

A term named like a URI scheme is said before the id (``circuit://power`` reads "circuit
power"); ``electrical`` is the domain's own word ("Wiring: done here").
"""

from __future__ import annotations

VOCABULARY = {
    "owner": {
        "electrical": "wiring",
        "supply": "supply",
        "device": "electrical device",
        "circuit": "circuit",
        "conductor": "conductor",
    }
}
