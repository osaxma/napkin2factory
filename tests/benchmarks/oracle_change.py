"""Judge one ``changes:`` row: find or replay a change request, then its impact and outcome.

A change row is judged on the product as the change leaves it, never on the folder the oracle
was pointed at: the caller hands this module a scratch copy (``oracle.py`` copies the product
with its ``.git`` and ``build/`` into a temporary directory). Two sources give the impact of a
change: an agent's own request found under ``changes/*.yaml``, or a replay of the row's
``sets``/``edits``. The row's figures and facts are then judged by the same finders as the
top-level rows, reading the impact for the ``impact:`` figure and the ``signoffs_lost`` fact.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from tests.benchmarks.oracle_evidence import EvidenceError, run_n2f
from tests.benchmarks.oracle_match import MatchError, convert, requirement_rows
from tests.benchmarks.oracle_schema import Change, ChangeEdit, ChangeSet


class ChangeFailure(ValueError):
    """A change row could not be replayed or its impact could not be read.

    ``whole=True`` (an edit that cannot apply) fails every assertion of the change; otherwise
    the oracle reports one FAIL row for the change as a whole.
    """

    def __init__(self, message: str, *, whole: bool = False) -> None:
        super().__init__(message)
        self.whole = whole


def _json(out: str) -> Any:
    """Parse stdout that ``--json`` promises; an empty or malformed one is a clear error."""
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise ChangeFailure(f"the command printed no JSON: {exc}") from exc


def _last_line(exc: EvidenceError) -> str:
    """The last stderr line of a failed n2f command, for a FAIL row's text."""
    return str(exc).strip().splitlines()[-1]


def resolve_set(row: ChangeSet, parameters: dict[str, Any]) -> str:
    """The one parameter a ``sets`` row names, by its value converted to the row's unit.

    ``parameters`` maps a parameter slug to its evaluated ``{"value", "unit", "description"}``
    (``_evaluated_parameters`` builds it). ``words`` (a case-insensitive regex over the slug
    and description) narrows ties. None or several left: ``MatchError`` naming what it found.
    """
    hits: list[str] = []
    for name, p in parameters.items():
        if not isinstance(p, dict) or "value" not in p:
            continue
        try:
            got = convert(float(p["value"]), str(p.get("unit", "")), row.unit)
        except (MatchError, ValueError, TypeError):
            continue
        if abs(got - row.value) <= 1e-6 * max(abs(row.value), 1.0):
            hits.append(name)
    if row.words:
        hits = [
            h
            for h in hits
            if re.search(row.words, f"{h} {parameters[h].get('description', '')}", re.I)
        ]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise MatchError(
            f"no parameter is {row.value:g} {row.unit}".strip()
            + (f" with the words {row.words!r}" if row.words else "")
        )
    raise MatchError(
        f"{len(hits)} parameters are {row.value:g} {row.unit}: {', '.join(sorted(hits))}"
    )


def _evaluated_parameters(product: Path) -> dict[str, dict[str, Any]]:
    """Every parameter's evaluated value and unit, as ``resolve_set`` reads it.

    Expressions are evaluated (``frame-height = table-height - top-thickness - glide-height``
    is 700 mm, not an ``expr`` string), so a ``sets`` row can find a derived parameter by its
    value; a value is still set through the parameter it depends on (``n2f`` refuses to set an
    expression directly).
    """
    from napkin2factory.core.errors import N2FError
    from napkin2factory.core.loader import load_product

    try:
        prod = load_product(product)
    except (N2FError, ValueError, KeyError, OSError) as exc:
        raise ChangeFailure(f"cannot read the parameters: {exc}") from exc
    out: dict[str, dict[str, Any]] = {}
    for slug, p in prod.parameters.items():
        q = prod.parameter_value(slug)
        out[slug] = {
            "value": float(q.magnitude),
            "unit": "" if q.dimensionless else str(q.units),
            "description": p.description,
        }
    return out


def find_requests(product: Path, change: Change) -> list[Path]:
    """The product's own change requests whose kind, title or reason match the row's ``words``."""
    changes_dir = product / "changes"
    if not changes_dir.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(changes_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict) or data.get("kind") != change.kind:
            continue
        text = f"{data.get('title', '')} {data.get('reason', '')}"
        if re.search(change.words, text, re.I):
            out.append(path)
    return out


def _apply_edit(product: Path, edit: ChangeEdit) -> None:
    """Apply one design edit to the copy; a missing ``find`` fails the whole change."""
    path = product / edit.file
    if edit.remove:
        if not path.exists():
            raise ChangeFailure(
                f"not replayable on this product: {edit.file} is not there to remove", whole=True
            )
        path.unlink()
        return
    if edit.content is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(edit.content, encoding="utf-8")
        return
    assert edit.find is not None and edit.replace is not None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        raise ChangeFailure(
            f"not replayable on this product: {edit.file} has no '{edit.find[:40]}'", whole=True
        )
    if edit.find not in text:
        raise ChangeFailure(
            f"not replayable on this product: {edit.file} has no '{edit.find[:40]}'", whole=True
        )
    path.write_text(text.replace(edit.find, edit.replace, 1), encoding="utf-8")


def _replay(change: Change, product: Path, needs_impact: bool) -> dict[str, Any] | None:
    """Replay the change in the copy: ``ecr start`` with the resolved ``sets``, then ``edits``.

    The start and the edits leave the model the other rows judge; the impact is computed only
    when a row reads it (``needs_impact``), because ``ecr impact`` rebuilds the product and its
    result would otherwise be thrown away.
    """
    if not (product / ".git").exists():
        raise ChangeFailure(f"{product.name} has no history; run `n2f init .` here")
    args = ["ecr", "start", "--title", change.what, "--kind", change.kind, "--json"]
    parameters = _evaluated_parameters(product)
    for row in change.sets:
        args += ["--set", f"param://{resolve_set(row, parameters)}={row.to}"]
    try:
        _json(run_n2f(product, *args))
    except EvidenceError as exc:
        raise ChangeFailure(_last_line(exc)) from exc
    for edit in change.edits:
        _apply_edit(product, edit)
    if not needs_impact:
        return None
    try:
        return _json(run_n2f(product, "ecr", "impact", "--json"))
    except EvidenceError as exc:
        raise ChangeFailure(_last_line(exc)) from exc


def _first(cps: list[dict[str, Any]], label_prefix: str) -> dict[str, Any] | None:
    """The newest checkpoint whose label starts with ``label_prefix``."""
    return next((c for c in cps if str(c.get("label", "")).startswith(label_prefix)), None)


def _needs_impact(change: Change) -> bool:
    """True when a row reads the impact block: an ``impact:`` figure or ``signoffs_lost`` fact."""
    return any(f.find.impact is not None for f in change.figures) or any(
        f.fact == "signoffs_lost" for f in change.facts
    )


def _agent_impact(
    change: Change, product: Path, path: Path, needs_impact: bool
) -> dict[str, Any] | None:
    """The impact of the agent's own request, from the state the request left (or its record).

    None when no row reads the impact (``needs_impact`` is False): a draft's edits are already in
    the copy's model, and a closed or aborted request is still rolled back to the state it left
    so the other rows judge that. None too for a closed or aborted request that kept no stored
    impact (see ``obtain_impact``).
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ChangeFailure(f"{path.name} is not a change request")
    ecr_id = str(data.get("id", path.stem))
    status = str(data.get("status", ""))
    if status in ("draft", "approved"):
        if not needs_impact:
            return None
        try:
            return _json(run_n2f(product, "ecr", "impact", ecr_id, "--json"))
        except EvidenceError as exc:
            raise ChangeFailure(_last_line(exc)) from exc
    try:
        cps = _json(run_n2f(product, "checkpoints", "--json")).get("checkpoints", [])
    except EvidenceError as exc:
        raise ChangeFailure(_last_line(exc)) from exc
    if status == "closed":
        cp = _first(cps, f"Closed {ecr_id}:")
    else:  # aborted: the abort saved the work first, as the checkpoint just before "Aborted"
        aborted = _first(cps, f"Aborted {ecr_id}:")
        cp = (
            next((c for c in cps if c.get("number") == aborted["number"] - 1), None)
            if aborted is not None
            else None
        )
    if cp is None:
        raise ChangeFailure(f"no checkpoint holds {ecr_id} ({status})")
    try:
        run_n2f(product, "rollback", str(cp["number"]), "--json")
    except EvidenceError as exc:
        raise ChangeFailure(_last_line(exc)) from exc
    if not needs_impact:
        return None
    record = yaml.safe_load((product / "changes" / f"{ecr_id}.yaml").read_text(encoding="utf-8"))
    if isinstance(record, dict) and record.get("impact"):
        return record["impact"]
    return None


def obtain_impact(change: Change, product: Path, replay: bool) -> dict[str, Any] | None:
    """The impact block to judge a change row: the agent's request, or a replay of the row.

    The impact is computed only when a row reads it (an ``impact:`` figure or ``signoffs_lost``
    fact); otherwise None, and the outcome and the non-impact figures and facts are judged on the
    state the change left. None too when the request is closed or aborted and kept no stored
    impact: only the ``impact:`` finder and the ``signoffs_lost`` fact fail with "the request
    kept no impact".
    """
    needs_impact = _needs_impact(change)
    if not replay:
        matches = find_requests(product, change)
        if len(matches) == 1:
            return _agent_impact(change, product, matches[0], needs_impact)
        if len(matches) > 1:
            raise ChangeFailure(f"{len(matches)} change requests match")
    return _replay(change, product, needs_impact)


def outcome_failures(change: Change, check: dict[str, Any]) -> tuple[bool, str]:
    """Whether the change's requirement outcomes match its row: ``(passed, found text)``.

    ``accepted``: no requirement fails. ``refused``: every ``fails`` regex matches exactly one
    failing requirement (title or message) and no failing requirement is left unmatched.
    """
    failing = [r for r in requirement_rows(check) if r.get("status") == "fail"]

    def name(r: dict[str, Any]) -> str:
        return str(r.get("title", "") or r.get("id", "a requirement"))

    if change.outcome == "accepted":
        if not failing:
            return True, "no requirement fails"
        return False, f"{len(failing)} requirement(s) fail: " + "; ".join(name(r) for r in failing)
    claimed: set[int] = set()
    problems: list[str] = []
    for regex in change.fails:
        hits = [
            r
            for r in failing
            if re.search(regex, f"{r.get('title', '')} {r.get('message', '')}", re.I)
        ]
        if len(hits) == 1:
            claimed.add(id(hits[0]))
        else:
            problems.append(f"'{regex}' matches {len(hits)} failing requirement(s)")
    unmatched = [r for r in failing if id(r) not in claimed]
    if not problems and not unmatched:
        return True, "; ".join(name(r) for r in failing) or "the named requirement fails"
    bits = list(problems)
    if unmatched:
        bits.append(
            f"{len(unmatched)} failing requirement(s) unmatched: "
            + "; ".join(name(r) for r in unmatched)
        )
    return False, "; ".join(bits)
