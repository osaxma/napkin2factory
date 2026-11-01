"""Choices (FOUNDATION F12, F13; S-130): trade-offs a check hands to the owner.

A check returns ``choice`` when the facts first show a trade-off and every option it offers
is a valid design (:func:`offer`); a failure stays a failure.  The row carries
``detail.options`` (``id``, ``summary``, ``what_it_takes``, optional ``cost_delta``),
``detail.blocks`` (the gate it holds until decided: ``design``, ``verify``, ``release`` or
``none``) and ``detail.evidence`` (the URIs its facts come from; their keys become the row's
``evidence_keys``).

``n2f decide <check> --pick <option> --by "<name>"`` writes a ``DEC-`` entry
(:func:`record_decision`); ``n2f check`` never decides.  From then on the row reads ``pass``
with its decision while every evidence key is unchanged; when one changes (or the option is
no longer offered) the choice reopens, exactly like a sign-off (D25).

The entry is an ordinary decision: the schema has no field for a choice (F7: no change to it
in v0.5), so the check, the option, the person and the evidence keys are its ``sources``
lines, ``choice <check>: option <id>, chosen by <name>`` and ``evidence <uri> <key>``, which
:func:`decided_choices` reads back [revisit].

``build/checks/choices.json`` lists every row that is or was a choice (open ones with
``decision: null``); ``n2f status`` lists the open ones under "waiting on you".
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from napkin2factory.core.checks.results import CHOICE, CHOICE_BLOCKS, CheckResult
from napkin2factory.core.errors import N2FError
from napkin2factory.core.loader import Product

if TYPE_CHECKING:
    from napkin2factory.core.model.decisions import Decision

#: Where the checks rule writes the choices, under the build folder.
CHOICES_JSON = Path("checks") / "choices.json"
#: The gate a choice holds when its check does not say (the conservative one).
DEFAULT_BLOCKS = "release"
#: What ``n2f status`` and the gates call a gate a choice holds, in owner words.
HOLDS_WORDS = {
    "design": "it holds the Design gate",
    "verify": "it holds the Verify gate",
    "release": "it holds the release",
    "none": "it holds nothing; an agent may decide it and say so",
}

_CHOICE_LINE = re.compile(r"^choice (?P<check>\S+): option (?P<option>\S+), chosen by (?P<by>.+)$")
_EVIDENCE_LINE = re.compile(r"^evidence (?P<uri>\S+) (?P<key>\S+)$")


@dataclass(frozen=True)
class Option:
    """One way to resolve a choice; ``invalid`` says why it is not a valid design."""

    id: str
    summary: str
    what_it_takes: str
    cost_delta: str | None = None
    invalid: str = ""

    def to_dict(self) -> dict[str, Any]:
        """``detail.options[]`` form (F12)."""
        out = {"id": self.id, "summary": self.summary, "what_it_takes": self.what_it_takes}
        if self.cost_delta:
            out["cost_delta"] = self.cost_delta
        return out


def offer(result: CheckResult, options: list[Option], *, blocks: str, problem: str) -> CheckResult:
    """Make ``result`` a choice between ``options``, or a failure (FOUNDATION §7).

    Only valid options are offered.  Two or more → ``choice``; exactly one → ``fail`` naming
    that fix; none → ``fail``.  A choice is never a way to put off a failure.
    """
    if blocks not in CHOICE_BLOCKS:
        raise ValueError(f"blocks must be one of {', '.join(CHOICE_BLOCKS)}")
    valid = [o for o in options if not o.invalid]
    rejected = [{"id": o.id, "why": o.invalid} for o in options if o.invalid]
    if rejected:
        result.detail["not_offered"] = rejected
    if len(valid) >= 2:
        result.status = CHOICE
        result.message = f"{problem} Two ways to fix it: " + "; or ".join(o.summary for o in valid)
        result.detail["options"] = [o.to_dict() for o in valid]
        result.detail["blocks"] = blocks
        return result
    result.status = "fail"
    if valid:
        fix = valid[0]
        result.message = f"{problem} The one fix that works: {fix.summary} — {fix.what_it_takes}"
        result.detail["fix"] = fix.to_dict()
    else:
        result.message = f"{problem} No fix this check knows works: " + "; ".join(
            f"{o.summary} ({o.invalid})" for o in options
        )
    return result


# ---- what was decided --------------------------------------------------------------------


@dataclass(frozen=True)
class Decided:
    """A choice resolved by a ``DEC-`` entry (read back from its ``sources`` lines)."""

    decision: str
    check: str
    option: str
    by: str
    evidence_keys: dict[str, str]


def parse_decision(dec: Decision) -> Decided | None:
    """The choice a decision resolves, or ``None`` for any other decision."""
    found: Decided | None = None
    keys: dict[str, str] = {}
    for line in dec.sources:
        m = _CHOICE_LINE.match(line.strip())
        if m and found is None:
            found = Decided(dec.id, m["check"], m["option"], m["by"].strip(), keys)
            continue
        e = _EVIDENCE_LINE.match(line.strip())
        if e:
            keys[e["uri"]] = e["key"]
    return found


def decided_choices(product: Product) -> dict[str, Decided]:
    """Check id → its latest decision (a later ``DEC-`` id wins after a reopening)."""
    out: dict[str, Decided] = {}
    for dec in sorted(product.decisions.values(), key=lambda d: d.id):
        rec = parse_decision(dec)
        if rec is not None:
            out[rec.check] = rec
    return out


def decision_reads(product: Product) -> list[str]:
    """What the checks read for choices: the set of decisions, and each choice's decision."""
    return ["set://decs"] + [f"dec://{r.decision}" for r in decided_choices(product).values()]


# ---- the engine's status handling --------------------------------------------------------


def _normalize(row: CheckResult) -> None:
    """A ``choice`` row of any origin carries two well-formed options and its gate, or fails.

    A rule-pack check (``severity: choice``) says its options in its violation:
    ``{"options": [...], "blocks": "verify", "evidence": [...]}``.
    """
    d = row.detail
    if not d.get("options"):
        for v in d.get("violations") or []:
            if isinstance(v, dict) and v.get("options"):
                d["options"] = v["options"]
                for key in ("blocks", "evidence"):
                    if key in v:
                        d.setdefault(key, v[key])
                break
    options: list[dict[str, Any]] = []
    for o in d.get("options") or []:
        if (
            isinstance(o, dict)
            and all(isinstance(o.get(k), str) and o.get(k) for k in ("id", "summary"))
            and isinstance(o.get("what_it_takes"), str)
            and o["id"] not in {x["id"] for x in options}
        ):
            options.append(dict(o))
    if len(options) < 2:
        row.status = "fail"
        row.message = (
            "offered as a choice without two designs to choose from (a choice needs two "
            f"valid options): {row.message}"
        )
        return
    d["options"] = options
    if d.get("blocks") not in CHOICE_BLOCKS:
        d["blocks"] = DEFAULT_BLOCKS
    if not isinstance(d.get("evidence"), list):
        d["evidence"] = [row.subject]


def _changed(
    product: Product,
    build_dir: Path,
    recorded: dict[str, str],
    now: dict[str, str],
    calc_records: dict[str, Any],
) -> list[str]:
    """The evidence URIs whose key moved since the decision, or that are new facts."""
    from napkin2factory.core.checks.evidence import evidence_key, keys_match, legacy_keys

    out: list[str] = []
    for uri, key in recorded.items():
        cur = now.get(uri) or evidence_key(product, build_dir, uri, calc_records)
        if not keys_match(key, cur) and key not in legacy_keys(product, build_dir, uri):
            out.append(uri)
    out += [u for u in now if u not in recorded]
    return out


def resolve(
    product: Product,
    build_dir: Path,
    results: list[CheckResult],
    calc_records: dict[str, Any] | None = None,
) -> None:
    """Every ``choice`` row: checked for form, keyed, and turned to ``pass`` when decided.

    The row's evidence keys are taken now (D25).  A decision whose keys all still match makes
    the row ``pass`` with ``detail.decision``; otherwise the choice is open again and
    ``detail.reopened`` says what changed.
    """
    from napkin2factory.core.checks.evidence import evidence_key

    calc_records = calc_records or {}
    decided: dict[str, Decided] | None = None
    for row in results:
        if row.status != CHOICE:
            continue
        _normalize(row)
        if row.status != CHOICE:
            continue
        if not row.evidence_keys:
            row.evidence_keys = {
                u: evidence_key(product, build_dir, u, calc_records) for u in row.detail["evidence"]
            }
        if decided is None:
            decided = decided_choices(product)
        rec = decided.get(row.id)
        if rec is None:
            continue
        option = next((o for o in row.detail["options"] if o["id"] == rec.option), None)
        changed = _changed(product, build_dir, rec.evidence_keys, row.evidence_keys, calc_records)
        if option is not None and not changed:
            row.status = "pass"
            row.detail["decision"] = {"id": rec.decision, "option": rec.option, "by": rec.by}
            row.message = (
                f"decided in {rec.decision}: {option['summary']} (chosen by {rec.by}); "
                f"the model shows it once this is done: {option['what_it_takes']}"
            )
            continue
        was = option["summary"] if option is not None else rec.option
        what = ", ".join(u.split("://", 1)[-1] for u in changed) or "the options offered"
        row.detail["reopened"] = {
            "decision": rec.decision,
            "option": rec.option,
            "changed": changed,
        }
        row.message = f"reopened: {what} changed since {rec.decision} ({was}); {row.message}"


def choices_payload(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """``choices.json``: every row that is a choice or was decided as one, in check order."""
    out: list[dict[str, Any]] = []
    for r in rows:
        d = r.get("detail") or {}
        if r["status"] != CHOICE and "decision" not in d:
            continue
        out.append(
            {
                "id": r["id"],
                "subject": r["subject"],
                "module": r.get("module"),
                "kind": r.get("kind"),
                "title": r.get("title", ""),
                "status": r["status"],
                "blocks": d.get("blocks", DEFAULT_BLOCKS),
                "message": r["message"],
                "options": d.get("options", []),
                "evidence_keys": r.get("evidence_keys", {}),
                "decision": (d.get("decision") or {}).get("id"),
                **({"decided": d["decision"]} if "decision" in d else {}),
                **({"reopened": d["reopened"]} if "reopened" in d else {}),
            }
        )
    return out


def write_choices(build_dir: Path, rows: list[dict[str, Any]]) -> Path:
    """Write ``build/checks/choices.json`` (always, ``[]`` when there is none)."""
    path = build_dir / CHOICES_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(choices_payload(rows), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def load_choices(build_dir: Path) -> list[dict[str, Any]]:
    """The choices the last ``n2f check`` wrote (empty before the first one)."""
    path = build_dir / CHOICES_JSON
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def open_choices(build_dir: Path) -> list[dict[str, Any]]:
    """The choices waiting on the owner (not decided, or reopened)."""
    return [c for c in load_choices(build_dir) if c.get("status") == CHOICE]


def decide_command(choice: dict[str, Any]) -> str:
    """The command that records a pick for ``choice``."""
    ids = " | ".join(o["id"] for o in choice.get("options", []))
    return f'`n2f decide {choice["id"]} --pick {ids or "<option>"} --by "<name>"`'


def choice_blockers(build_dir: Path) -> dict[str, list[str]]:
    """Gate → the open choices that hold it (F12: ``blocks`` honoured by the gate it names)."""
    out: dict[str, list[str]] = {}
    for c in open_choices(build_dir):
        gate = c.get("blocks", DEFAULT_BLOCKS)
        if gate == "none":
            continue
        out.setdefault("released" if gate == "release" else gate, []).append(
            f"a choice is waiting on you: {c.get('title') or c['id']} — {decide_command(c)}"
        )
    return out


# ---- n2f decide -------------------------------------------------------------------------


class ChoiceError(N2FError):
    """``n2f decide`` cannot record this pick (unknown check, option, or nothing to decide)."""


def find_choice(rows: list[dict[str, Any]], check: str) -> dict[str, Any]:
    """The check row ``check`` names: its full id, or the part after ``://`` when unique."""
    exact = [r for r in rows if r["id"] == check]
    if not exact:
        exact = [r for r in rows if r["id"].split("://", 1)[-1] == check]
    if len(exact) == 1:
        row = exact[0]
        if row["status"] == CHOICE:
            return row
        dec = ((row.get("detail") or {}).get("decision") or {}).get("id")
        if dec:
            raise ChoiceError(
                f"{row['id']} is already decided ({dec}); it opens again by itself if what it "
                "was decided on changes"
            )
        raise ChoiceError(f"{row['id']} is not a choice (it reads {row['status']})")
    open_ = [r["id"] for r in rows if r["status"] == CHOICE]
    known = ", ".join(open_) if open_ else "none is waiting"
    raise ChoiceError(f"no check {check!r}; the open choices: {known}")


def next_decision_id(product: Product) -> str:
    """The next free ``DEC-`` id (``DEC-001`` for the first)."""
    nums = [int(i.split("-", 1)[1]) for i in product.decisions if i.split("-", 1)[1].isdigit()]
    return f"DEC-{(max(nums) + 1 if nums else 1):03d}"


def decision_entry(
    product: Product,
    row: dict[str, Any],
    option_id: str,
    by: str,
    note: str | None = None,
    agent: bool = False,
    today: dt.date | None = None,
) -> dict[str, Any]:
    """The ``DEC-`` entry ``n2f decide`` writes for ``option_id`` of choice ``row``."""
    from napkin2factory.core.uris import Uri, UriError

    options = {o["id"]: o for o in (row.get("detail") or {}).get("options", [])}
    if option_id not in options:
        raise ChoiceError(
            f"{option_id!r} is not an option of {row['id']}; pick one of: {', '.join(options)}"
        )
    blocks = (row.get("detail") or {}).get("blocks", DEFAULT_BLOCKS)
    if agent and blocks != "none":
        raise ChoiceError(
            f"{row['id']} holds the {blocks} gate, so it is the owner's to decide; an agent "
            "decides only a choice that holds nothing (roles/pm.md)"
        )
    o = options[option_id]
    links: list[str] = []
    for u in [row["subject"], *row.get("evidence_keys", {})]:
        try:
            Uri.parse(u)
        except UriError:
            continue
        if u not in links:
            links.append(u)
    decision = f"{o['summary'][:1].upper()}{o['summary'][1:]}. What it takes: {o['what_it_takes']}."
    if o.get("cost_delta"):
        decision += f" Cost: {o['cost_delta']}."
    return {
        "id": next_decision_id(product),
        "date": today or dt.date.today(),
        "title": f"{row.get('title') or row['id']}: {o['summary']}",
        "context": row["message"],
        "decision": decision,
        "rationale": note or f"Chosen by {by} when the check offered it as a choice.",
        "links": links,
        "made_by": "agent" if agent else "human",
        "disclosed": True,
        "verify": False,
        "sources": [
            f"choice {row['id']}: option {option_id}, chosen by {by}",
            *(f"evidence {u} {k}" for u, k in row.get("evidence_keys", {}).items()),
        ],
    }


def append_decision(path: Path, entry: dict[str, Any]) -> None:
    """Append ``entry`` to ``model/decisions.yaml``, keeping the file's comments and order."""
    from ruamel.yaml.comments import CommentedMap, CommentedSeq

    from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip

    data = load_roundtrip(path) if path.is_file() else None
    if not isinstance(data, dict):
        data = CommentedMap()
    if data.get("decisions") is None:
        data["decisions"] = CommentedSeq()
    item = CommentedMap()
    for k, v in entry.items():
        if k == "links":
            seq = CommentedSeq(v)
            seq.fa.set_flow_style()
            item[k] = seq
        else:
            item[k] = v
    data["decisions"].append(item)
    path.parent.mkdir(parents=True, exist_ok=True)
    dump_roundtrip(path, data)
