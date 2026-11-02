"""The wiring's words for the owner (F1 §3.8, docs/domains.md §3.8).

A term named like one of the domain's URI schemes is said before the id, so ``n2f check
--all`` says "circuit power" for ``circuit://power`` and "electrical device heater" for
``device://heater``.  ``electrical`` is the domain's own word ("Wiring: done here", S-150).

Two choices, both in S-159:

* ``supply`` has no owner word.  Its one id is ``supply`` (``supply://supply``), and a word
  is said *before* the id, so any word would read twice ("supply supply"); without one the
  owner reads "supply".
* No ``engineer`` words: the contract reads the vocabulary for the ``owner`` persona only
  (docs/domains.md §9), and the engineer sees the URI itself.

The non-scheme terms (``cable-entry``, ``terminal``, ``earth``, ``interlock``) are the words
the owner's view itself says, kept here so every surface of the domain says them one way.
"""

from __future__ import annotations

#: The owner's words, by term.  Read by the core for URI schemes and the domain's own name;
#: :func:`owner_word` reads them for the rest.
VOCABULARY: dict[str, dict[str, str]] = {
    "owner": {
        "electrical": "wiring",
        "device": "electrical device",
        "circuit": "circuit",
        "conductor": "conductor",
        "cable-entry": "cable entry",
        "terminal": "terminal",
        "earth": "earth",
        "interlock": "interlock",
    }
}

#: What each circuit purpose is, said to the owner (``Circuit.purpose``).
PURPOSE_WORDS = {
    "power": "power",
    "control": "control",
    "sensing": "sensing",
    "earth": "earth",
}

#: What each device role is, said to the owner (``Device.role``).
ROLE_WORDS = {
    "supply": "supply point",
    "load": "load",
    "control": "switching device",
    "protection": "protective device",
    "sensor": "sensor",
    "earth": "earth point",
    "passthrough": "terminal or connector",
}


def owner_word(term: str) -> str:
    """The owner's word for ``term`` (the term itself when the table has none)."""
    return VOCABULARY["owner"].get(term, term)
