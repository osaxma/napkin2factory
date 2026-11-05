"""The format of ``SPEC.oracle.yaml``: what a benchmark product must show, said without ids.

An oracle judges outcomes (road-to-v1.0 section 4.2, W9): which concept card was promoted and
what rejected each other card, the figures within a stated tolerance, the product's facts. It
never names a part, a requirement or a card by its id, because a cold agent names things
differently and must still pass. Every row is found by what it *is*: a card by its status, the
category of check that failed it and a distinguishing property; a figure by the kind of surface
n2f writes it to (``tests/benchmarks/README.md`` lists them).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

Category = Literal["structural", "mass", "cost", "envelope"]
CardStatus = Literal["promoted", "rejected", "exploring"]


class Strict(BaseModel):
    """Every oracle model rejects fields it does not know, so a typo is an error, not a pass."""

    model_config = ConfigDict(extra="forbid")


class CardSel(Strict):
    """Which concept card is meant: by outcome and property, never by id.

    ``by`` lists the categories of failing check the card must show, ``not_by`` the ones it
    must not (``not_by: [structural]`` says the rejection is not about strength). ``material``
    is a word that one of the card's rough shapes carries, ``kit`` a shape generator it uses,
    ``pieces`` its number of rough shapes. ``why`` is words for the report only.
    """

    status: CardStatus | None = None
    by: list[Category] = []
    not_by: list[Category] = []
    material: str | None = None
    kit: str | None = None
    pieces: int | None = None
    why: str = ""


class Concepts(Strict):
    """What the napkin stage must have decided."""

    count: int | None = None
    promoted: CardSel = CardSel()
    rejected: list[CardSel] = []
    #: the promoted card must show no failing check (a warning is allowed)
    promoted_has_no_failure: bool = True


class Expect(Strict):
    """A number to judge: within a relative tolerance of ``expect``, or inside a bound.

    ``expect`` may be a list: any one of them satisfies it (the spec states a figure both
    ways, factored and not). ``tol`` is relative; ``abs_tol`` is added for values near zero.
    """

    expect: float | list[float] | None = None
    tol: float | None = None
    abs_tol: float = 0.0
    at_least: float | None = None
    at_most: float | None = None
    range: tuple[float, float] | None = None

    @property
    def judges_a_number(self) -> bool:
        """True when any of expect, at_least, at_most or range is given."""
        return any(g is not None for g in (self.expect, self.at_least, self.at_most, self.range))


class ScreenRowFind(Strict):
    """A row of the card's screening, found by its check kind (``rule``) or its category."""

    rule: str | None = None
    category: Category | None = None
    regex: str


class RequirementFind(Strict):
    """A requirement found by what it bounds: the bound, the direction, its flags, its words.

    Two requirements may bound alike (the footprint and a clear width both at 400 mm); ``words``
    and ``not_words`` (case-insensitive regexes, searched in the requirement's title and
    message) tell them apart. ``aggregate`` reduces what is found to one number: ``min`` is the
    governing factor when one product covers two checks by one requirement and another by two
    (S-230).
    """

    bound: str
    op: Literal["<", "<=", ">", ">=", "=="] | None = None
    safety: bool | None = None
    category: str | None = None
    kind: str | None = None
    words: str | None = None
    not_words: str | None = None
    aggregate: Literal["min", "max"] | None = None


class ResultFind(Strict):
    """A row of ``n2f check --json`` ``results``: its kind, the rule that wrote it, a number in it.

    The number is at ``path`` (dotted, into the row) or captured by ``regex`` from the message.
    """

    kind: str
    rule: str | None = None
    path: str | None = None
    regex: str | None = None

    @model_validator(mode="after")
    def _where_is_the_number(self) -> ResultFind:
        if (self.path is None) == (self.regex is None):
            raise ValueError("give exactly one of path or regex")
        return self


class Find(Strict):
    """Where a figure's number comes from: exactly one of these surfaces."""

    screen_value: str | list[str] | None = None
    screen_row: ScreenRowFind | None = None
    requirement: RequirementFind | None = None
    rollup: str | None = None
    result: ResultFind | None = None

    @model_validator(mode="after")
    def _one_surface(self) -> Find:
        n = sum(v is not None for v in (self.screen_value, self.screen_row, self.requirement))
        n += sum(v is not None for v in (self.rollup, self.result))
        if n != 1:
            raise ValueError("a figure is found in exactly one surface")
        return self

    @property
    def on_card(self) -> bool:
        """True when the number is read from a concept card's screening."""
        return self.screen_value is not None or self.screen_row is not None


class Figure(Expect):
    """A number the product must show: ``what`` in plain words, found by ``find``."""

    name: str
    what: str
    find: Find
    card: CardSel | None = None
    unit: str | None = None

    @field_validator("card", mode="before")
    @classmethod
    def _card_word(cls, v: Any) -> Any:
        return {"status": v} if isinstance(v, str) else v

    @model_validator(mode="after")
    def _consistent(self) -> Figure:
        if self.find.on_card != (self.card is not None):
            raise ValueError("a screen_* figure needs a card, and any other figure has none")
        if not self.judges_a_number:
            raise ValueError("say what to expect: expect, at_least, at_most or range")
        return self


FactKind = Literal[
    "ceremony",
    "region",
    "supply",
    "supply_voltage",
    "supply_frequency",
    "assemblies",
    "count_requirements",
    "gate_blockers",
]


class Fact(Expect):
    """A fact about the product. The word kinds use ``equals``; the numeric ones ``Expect``."""

    name: str
    what: str
    fact: FactKind
    equals: str | None = None
    unit: str | None = None
    safety: bool | None = None
    status: str | None = None
    status_in: list[str] | None = None
    category: str | None = None
    #: count_requirements only: a case-insensitive regex searched in the requirement's title
    #: and message, to name the one wanted ("the tip-over requirement") without its id (S-236)
    words: str | None = None
    gate: str | None = None
    matching: str | None = None
    invert: bool = False

    @field_validator("equals", mode="before")
    @classmethod
    def _as_word(cls, v: Any) -> Any:
        return None if v is None else str(v)

    @model_validator(mode="after")
    def _consistent(self) -> Fact:
        words = {"ceremony", "region", "supply"}
        if self.fact in words and self.equals is None:
            raise ValueError(f"the {self.fact} fact needs equals")
        if self.fact not in words and not self.judges_a_number:
            raise ValueError("say what to expect: expect, at_least, at_most or range")
        if self.fact == "gate_blockers" and self.gate is None:
            raise ValueError("gate_blockers needs the gate's name")
        return self


class Pending(Strict):
    """A figure the spec states that n2f cannot show yet; it becomes a row when it can."""

    what: str
    reason: str


class Oracle(Strict):
    """A whole ``SPEC.oracle.yaml``."""

    oracle: Literal[1] = 1
    title: str = ""
    spec: str = ""
    lexicon: dict[Category, list[str]] = {}
    concepts: Concepts | None = None
    figures: list[Figure] = []
    facts: list[Fact] = []
    pending: list[Pending] = []


def load_oracle(path: Path) -> Oracle:
    """Read and validate an oracle file; a bad one raises ``ValueError`` naming the problem."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Oracle.model_validate(data)
