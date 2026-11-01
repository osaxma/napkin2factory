"""The screen contract: the fields a screen reads, the values it writes (F8, F10, S-128).

A screen is a :class:`~napkin2factory.core.domain.Screen`: ``run(card, massing, values)``
adds labelled numbers through ``values`` and returns concept rule rows. It declares the card
fields it reads (section, key, the kind of number, an example, the owner's words) and the
phase it runs in, either on the ``Screen`` itself (``fields=``, ``phase=``: the contract,
S-129) or with :func:`reads` on ``run``; ``n2f concept new`` writes the skeleton from those
declarations and ``n2f concept lint`` checks the cards against them. A screen that declares
nothing runs after the system's totals (the ``check`` phase).

Phases, in order (one screening):

* ``measure`` — the system's own: sizes, volume and mass of the rough shapes, the door term.
* ``estimate`` — screens whose numbers the totals read: a mass to add to the rough shapes'
  (:attr:`ScreenValues.mass_items`), something to price (:attr:`ScreenValues.cost_items`).
* ``total`` — the system's own: total mass, cost band, lift class.
* ``check`` — everything else (the default).

The system's generic rule rows come first, then each screen's rows in phase order.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from napkin2factory.core.domain import SCREEN_PHASES
from napkin2factory.core.model.concepts import ConceptCard, LabelledValue
from napkin2factory.core.units import is_quantity

#: The phases a screen may run in, in order (see the module docstring).
PHASES: tuple[str, ...] = SCREEN_PHASES
#: The phase of a screen that declares none.
DEFAULT_PHASE = "check"
#: The card sections a field may sit in.
SECTIONS: tuple[str, ...] = ("envelope", "site", "layout")
#: The owner's words for a ``[verify]`` tag at the end of a "where it comes from" sentence.
TO_CHECK = "to be checked"
#: The system's word for the space a product must fit (F8). A product names it its own way
#: with ``WORDS = {"space": "recess"}`` in a screens module (``core.packs.product_words``);
#: the generic rows, a field's words (``{space}``) and promotion then say that (S-137).
SPACE_WORDS = "space"


@dataclass(frozen=True)
class CardField:
    """One card field a screen reads (F8): where it sits, its kind of number and an example.

    ``unit`` is the unit the screen converts it to (``None``: words, like a region code);
    ``kind`` names that kind of number for the owner (``a length``); ``words`` say what the
    field is (``the {space} width``: ``{space}`` is the product's word for the space it must
    fit, :meth:`said`); ``aliases`` are earlier keys still read for one
    version (F16) — the card's key wins over an alias when both are present. ``param``
    names the parameter an envelope field seeds when its card is promoted, when that is not
    the key itself with hyphens (``None``: the key). ``hint`` false keeps the field out of a
    new card's "screens read" lines unless the card already gives it: a field only some
    products have (the generic door-swing term's door fields), so a shelf's card never
    suggests a door (gate F, S-137).
    """

    section: str
    key: str
    unit: str | None
    kind: str
    example: str
    words: str
    aliases: tuple[str, ...] = ()
    param: str | None = None
    hint: bool = True

    @property
    def name(self) -> str:
        """``site.width``."""
        return f"{self.section}.{self.key}"

    def said(self, space: str = SPACE_WORDS) -> str:
        """The field's words with the product's word for the space (``the space width``)."""
        return self.words.replace("{space}", space)

    def written(self, card: ConceptCard) -> str | None:
        """The key the card uses for this field (the field's own, else an alias), or None."""
        section = getattr(card, self.section)
        for key in (self.key, *self.aliases):
            if key in section:
                return key
        return None

    def raw(self, card: ConceptCard) -> Any:
        """The card's value as written (``None`` when absent)."""
        key = self.written(card)
        return None if key is None else getattr(card, self.section).get(key)

    def wrong_kind(self, value: Any) -> tuple[str, str, str] | None:
        """Why ``value`` is not this field's kind of number, else None.

        Returns ``(the value as written, the kind it should be, an example)``. Words and a
        missing value are never wrong for a field without a unit.
        """
        if self.unit is None or value is None:
            return None
        if is_quantity(value):
            try:
                value.to(self.unit)
            except Exception:  # pint DimensionalityError: another kind of quantity
                return f"{value.magnitude:g} {value.units:~}", self.kind, self.example
            return None
        return str(value), self.kind, self.example

    def quantity(self, card: ConceptCard) -> Any | None:
        """The card's number when it is this field's kind, else None."""
        value = self.raw(card)
        if not is_quantity(value) or self.wrong_kind(value) is not None:
            return None
        return value


def reads(*fields: CardField, phase: str = DEFAULT_PHASE) -> Callable[[Any], Any]:
    """Declare what a screen's ``run`` reads and when it runs (F8).

    ``@reads(CardField("site", "circuit", None, "words", "230V-16A", "the circuit"),
    phase="estimate")`` on the function a :class:`~napkin2factory.core.domain.Screen` runs.
    """
    if phase not in PHASES:
        raise ValueError(f"unknown screen phase {phase!r}; known: {', '.join(PHASES)}")

    def mark(fn: Any) -> Any:
        fn.fields = tuple(fields)
        fn.phase = phase
        return fn

    return mark


def fields_of(screen: Any) -> tuple[CardField, ...]:
    """The fields a screen declares: its own ``fields``, else its ``run``'s :func:`reads`."""
    return tuple(getattr(screen, "fields", ()) or getattr(screen.run, "fields", ()))


def phase_of(screen: Any) -> str:
    """The phase a screen runs in: its own ``phase``, else its ``run``'s, else ``check``."""
    return str(getattr(screen, "phase", "") or getattr(screen.run, "phase", DEFAULT_PHASE))


class Collector:
    """Raw values for the rules plus their labelled, formatted twins for the card."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.raw: dict[str, Any] = {}
        self.out: dict[str, LabelledValue] = {}

    def add(self, name: str, raw: Any, text: str, source: str, ref: str | None = None) -> None:
        """Record one value: ``source`` in the owner's words, ``ref`` for engineers."""
        self.raw[name] = raw
        self.out[name] = LabelledValue(
            value=text,
            label=self.label,  # type: ignore[arg-type]
            source=source,
            ref=ref,
        )


@dataclass
class ScreenValues:
    """What a screen adds to (F8) and what screens hand each other.

    ``computed``, ``estimate`` and ``given`` collect labelled values; ``notes`` holds owner
    sentences. ``shared`` carries raw values from one screen to a later one (a screen of the
    ``estimate`` phase may give ``inner_size`` and ``wall`` for the walls-fit-envelope rule).
    ``mass_items`` (``(kg quantity, words, ref)``) join the rough shapes' mass in the total;
    ``cost_items`` (``(name, process class, kg)``) are priced with the rough shapes.
    """

    computed: Collector = field(default_factory=lambda: Collector("computed"))
    estimate: Collector = field(default_factory=lambda: Collector("estimate"))
    given: Collector = field(default_factory=lambda: Collector("given"))
    notes: list[str] = field(default_factory=list)
    shared: dict[str, Any] = field(default_factory=dict)
    mass_items: list[tuple[Any, str, str]] = field(default_factory=list)
    cost_items: list[tuple[str, str, float | None]] = field(default_factory=list)


# --- formatting ---------------------------------------------------------------------


def sig(x: float, digits: int = 3) -> str:
    """``x`` to ``digits`` significant figures, whole when that is longer."""
    return f"{x:.{digits}g}" if abs(x) < 10**digits else f"{x:.0f}"


def fmt(q: Any, unit: str) -> str:
    """A screening value as text (``995 mm``, ``2.5 kW``, ``7.1 h``, ``1840 USD``)."""
    x = float(q.to(unit).magnitude)
    if unit == "mm":
        return f"{x:.0f} mm"
    if unit == "W":
        return f"{sig(x / 1000)} kW" if abs(x) >= 1000 else f"{x:.0f} W"
    if unit == "degC":
        return f"{x:.0f} degC"
    if unit == "USD":
        return f"{x:.0f} USD"
    if unit == "hour":
        return f"{x:.2g} h" if x < 10 else f"{x:.0f} h"
    if unit == "MJ":
        return f"{sig(x)} MJ"
    if unit == "A":
        return f"{x:.1f} A"
    if unit == "L":
        return f"{sig(x)} L"
    if unit == "kg":
        return f"{sig(x)} kg"
    return f"{sig(x)} {unit}"


def and_(items: list[str]) -> str:
    """``a, b and c``."""
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def the(items: list[str]) -> str:
    """``the body and the door``; three or more: ``the guard, hinge and door``."""
    return "the " + (" and the ".join(items) if len(items) < 3 else and_(items))


def owner_names(names: list[str]) -> list[str]:
    """Call names as words, pieces sharing a prefix grouped: ``guard (5 pieces)``, ``hinge``."""
    words = [n.replace("_", " ").replace("-", " ").strip() for n in names]
    heads = [w.split(" ")[0] for w in words]
    out: list[str] = []
    for w, head in zip(words, heads, strict=True):
        n = heads.count(head)
        item = f"{head} ({n} pieces)" if n > 1 and " " in w else w
        if item not in out:
            out.append(item)
    return out


__all__ = [
    "DEFAULT_PHASE",
    "PHASES",
    "SECTIONS",
    "SPACE_WORDS",
    "TO_CHECK",
    "CardField",
    "Collector",
    "ScreenValues",
    "and_",
    "fields_of",
    "fmt",
    "owner_names",
    "phase_of",
    "reads",
    "sig",
    "the",
]
