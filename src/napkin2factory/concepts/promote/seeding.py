"""Step 3c: the card's rough shapes become the model: parts, layout, driving sizes (B-0316, S-336).

The card's massing calls are kit calls with arguments, a material and a placement, and the board
already drew them right, so promotion turns them into the model mechanically:

1. **Parts.** One part per group of identical calls (same kit, arguments, material, process
   class, role, rotation, module and stretch); ``qty`` is the group's size.
2. **The three overall sizes.** One driving parameter per axis: an envelope parameter promotion
   already seeded whose value equals that axis's extent, else ``overall-length`` (x),
   ``overall-width`` (y) or ``overall-height`` (z). ``x`` and ``y`` grow about the box's centre,
   ``z`` grows upward (the floor stays).
3. **The stretch rule**, per piece and per axis in the world frame: a piece longer than half the
   box's extent *spans* it: it keeps its gaps to both faces, so its length is an expression of the
   overall size (a parameter ``<part>-<argument>``). Any other piece keeps its size and its
   distance to the face it was drawn nearest (centred within 1 mm of the centre: stays centred).
4. **Placement.** One geometry module per seeded assembly, with a table of one row per placed
   instance (:mod:`napkin2factory.geometry.seeded` holds the logic).

All of it is computed in memory from the card as it is now; nothing is written here. A product
that already has parts or assemblies is never seeded: the plan says so and holds nothing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from napkin2factory.concepts.promote.common import (
    SeededParam,
    _and,
    _num,
    _q_text,
    _rel,
    _slug,
    _yaml_scalar,
)
from napkin2factory.concepts.promote.modules import ModulePlan, SeededAssembly
from napkin2factory.concepts.promote.parameters import SEED_OWNER, param_line
from napkin2factory.core.errors import GateBlocked
from napkin2factory.core.model.concepts import ConceptCard

#: The overall size parameters promotion adds when no envelope number is that axis's extent.
OVERALL = {"x": "overall-length", "y": "overall-width", "z": "overall-height"}
#: Two lengths this close (mm) are the same length.
SAME_MM = 0.01
#: A piece whose centre is this close (mm) to the box's centre stays centred.
CENTRED_MM = 1.0
AXES = ("x", "y", "z")

#: A seeded part's finish: the general rule wants one, the card gives none (S-336).
NO_FINISH = "none chosen yet (ask the owner)"

_ENV_SOURCE = re.compile(r"^envelope\.([^\[.]+)(?:\[(\d+)\])?$")


@dataclass
class _Instance:
    """One massing call, measured: where its extent sits and what keeps it there."""

    name: str
    piece: Any  # concepts.massing.MassingPiece
    rz: float
    #: per axis: (anchor, offset mm); ``low`` / ``high`` / ``mid`` of the overall box
    anchors: dict[str, tuple[str, float]] = field(default_factory=dict)
    #: world axis -> (argument name, mm the gaps take from the overall size)
    stretch: dict[str, tuple[str, float]] = field(default_factory=dict)
    #: the call's place in the card's massing: the table keeps the card's order (S-336)
    index: int = 0


@dataclass
class SeededPart:
    """One part promotion wrote."""

    id: str
    name: str
    qty: int
    kit: str
    file: str
    calls: list[str]
    module: str | None = None
    #: the parameters that stretch it (``joist-length``)
    stretched: list[str] = field(default_factory=list)


@dataclass
class SeedPlan:
    """What promotion does with the card's rough shapes (nothing, when ``skipped`` says why)."""

    skipped: str | None = None
    parts: list[SeededPart] = field(default_factory=list)
    #: the three overall sizes: axis -> parameter name
    sizes: dict[str, str] = field(default_factory=dict)
    #: parameters added (their lines for ``parameters.yaml``), as ``SeededParam`` for the result
    new_params: list[SeededParam] = field(default_factory=list)
    param_lines: list[str] = field(default_factory=list)
    texts: dict[str, str] = field(default_factory=dict)  # file (relative) -> text
    assemblies: list[SeededAssembly] = field(default_factory=list)
    top: str | None = None
    geometry_files: list[str] = field(default_factory=list)

    @property
    def seeded(self) -> bool:
        """Whether the model gets parts, a layout and structure checks."""
        return bool(self.parts)


def _mm(text: str) -> float | None:
    """A quantity text in millimetres, ``None`` when it is not a length."""
    from napkin2factory.core.units import parse_quantity

    try:
        return float(parse_quantity(text).to("mm").magnitude)
    except Exception:  # noqa: BLE001 — pint's dimensionality errors and parse errors alike
        return None


def _envelope_match(
    card: ConceptCard, seeded: list[SeededParam], extent: tuple[float, float, float]
) -> dict[str, str]:
    """The seeded envelope parameter whose value is each axis's extent, where there is one.

    A three-number entry matches its own axis only (width x, depth y, height z); a single number
    matches the one axis it equals, and none when two axes tie (S-336).
    """
    triples: dict[str, str] = {}
    singles: list[tuple[str, float]] = []
    for p in seeded:
        m = _ENV_SOURCE.match(p.source)
        value = _mm(p.value)
        if m is None or value is None:
            continue
        raw = card.envelope.get(m.group(1))
        if isinstance(raw, list) and len(raw) == 3 and m.group(2) is not None:
            axis = AXES[int(m.group(2))]
            if abs(value - extent[int(m.group(2))]) <= SAME_MM:
                triples.setdefault(axis, p.name)
        elif m.group(2) is None and not isinstance(raw, list):
            singles.append((p.name, value))
    out = dict(triples)
    for i, axis in enumerate(AXES):
        if axis in out:
            continue
        hits = [n for n, v in singles if abs(v - extent[i]) <= SAME_MM]
        tied = [j for j in range(3) if abs(extent[j] - extent[i]) <= SAME_MM]
        if hits and len(tied) == 1:
            out[axis] = hits[0]
    return out


def _unique(name: str, taken: set[str]) -> str:
    """``name``, or ``name-2``, ``name-3`` … when it is taken; the result joins ``taken``."""
    pick, n = name, 2
    while pick in taken:
        pick, n = f"{name}-{n}", n + 1
    taken.add(pick)
    return pick


def _prefix(names: list[str]) -> str:
    """The longest common hyphen prefix of the names, else the first name (S-336)."""
    if len(names) == 1:
        return _slug(names[0]) or "part"
    tokens = [_slug(n).split("-") for n in names]
    common: list[str] = []
    for column in zip(*tokens, strict=False):
        if len(set(column)) != 1:
            break
        common.append(column[0])
    return "-".join(common) if common else (_slug(names[0]) or "part")


def _rot90(rz: float) -> int | None:
    """Quarter turns of ``rz`` degrees, ``None`` when it is not a multiple of 90."""
    q = rz / 90.0
    return int(round(q)) % 4 if abs(q - round(q)) < 1e-9 else None


def _round(x: float) -> float:
    """A millimetre figure to 0.001 mm with no ``-0.0``."""
    r = round(x, 3)
    return 0.0 if r == 0 else r


def _measure(
    card: ConceptCard,
    pieces: list[Any],
    box: dict[str, tuple[float, float]],
    notes: list[str],
) -> list[_Instance]:
    """Each piece's anchors and stretch against the overall box (the rule in the docstring)."""
    from napkin2factory.geometry import kit as kit_mod

    out: list[_Instance] = []
    literal: set[str] = set()
    for piece in pieces:
        at = piece.call.at or {}
        rz = float(_degrees(at.get("rz", 0)))
        inst = _Instance(piece.name, piece, rz, index=len(out))
        turns = _rot90(rz)
        axes_of: dict[str, str] = {}
        size_axes = getattr(kit_mod.get_module(piece.kit), "size_axes", None)
        if size_axes is None:
            literal.add(f"{piece.kit} (its kit declares no axes)")
        elif turns is None:
            literal.add(f"{piece.name} (turned {rz:g} degrees, not a multiple of 90)")
        else:
            for arg, axis in size_axes(piece.args).items():
                if turns % 2 == 1 and axis in ("x", "y"):
                    axis = "y" if axis == "x" else "x"
                axes_of[axis] = arg
        for i, axis in enumerate(AXES):
            lo, hi = piece.bbox_min[i], piece.bbox_max[i]
            blo, bhi = box[axis]
            extent = bhi - blo
            size = hi - lo
            arg = axes_of.get(axis)
            value = None if arg is None else getattr(piece.args, arg, None)
            stretchable = (
                arg is not None
                and arg in piece.call.args
                and value is not None
                and abs(float(value) - size) <= SAME_MM
            )
            if size > extent / 2 + SAME_MM and stretchable:
                assert arg is not None
                inst.anchors[axis] = ("low", _round(lo - blo))
                inst.stretch[axis] = (arg, _round(extent - size))
                continue
            mid = (lo + hi) / 2 - (blo + bhi) / 2
            if abs(mid) <= CENTRED_MM:
                inst.anchors[axis] = ("mid", _round(mid))
            elif lo - blo <= bhi - hi:
                inst.anchors[axis] = ("low", _round(lo - blo))
            else:
                inst.anchors[axis] = ("high", _round(bhi - hi))
        out.append(inst)
    if literal:
        notes.append(
            "kept at their drawn size, whatever the overall size becomes: " + _and(sorted(literal))
        )
    return out


def _degrees(raw: Any) -> float:
    """A rotation as degrees (a bare number is degrees, as in a card's ``at:``)."""
    from napkin2factory.core.units import parse_quantity

    return float(parse_quantity(raw, "degree").to("degree").magnitude)


def _group(instances: list[_Instance]) -> list[list[_Instance]]:
    """Identical calls together, in the order they first appear."""
    groups: dict[str, list[_Instance]] = {}
    for inst in instances:
        call = inst.piece.call
        key = json.dumps(
            [
                call.kit,
                call.args,
                call.material,
                inst.piece.process_class,
                call.role,
                round(inst.rz, 6),
                call.module,
                sorted((a, arg, round(g, 2)) for a, (arg, g) in inst.stretch.items()),
            ],
            sort_keys=True,
            default=str,
        )
        groups.setdefault(key, []).append(inst)
    return list(groups.values())


def _overlap_note(pieces: list[Any], notes: list[str]) -> None:
    """Say which rough shapes overlap: the check will list them, and joints are the next step."""
    from napkin2factory.core.checks.interference import THRESHOLD_MM3

    pairs: list[str] = []
    for i, a in enumerate(pieces):
        for b in pieces[i + 1 :]:
            volume = 1.0
            for k in range(3):
                volume *= max(
                    0.0, min(a.bbox_max[k], b.bbox_max[k]) - max(a.bbox_min[k], b.bbox_min[k])
                )
            if volume > THRESHOLD_MM3:
                pairs.append(f"{a.name} and {b.name}")
    if pairs:
        shown = _and(pairs[:3]) + (f" (and {len(pairs) - 3} more)" if len(pairs) > 3 else "")
        notes.append(
            f"{len(pairs)} pair(s) of the card's rough shapes overlap, e.g. {shown}: the built "
            "model keeps them as drawn, so `n2f check` lists them under 'parts do not overlap'. "
            "Joints are the next design step: notch or move one of each pair"
        )


def _words(slug: str) -> str:
    return slug.replace("-", " ").capitalize()


def _part_text(
    card: ConceptCard,
    pid: str,
    members: list[_Instance],
    args: dict[str, Any],
    process: str,
) -> str:
    first = members[0].piece
    call = first.call
    data: dict[str, Any] = {
        "id": pid,
        "rev": "A",
        "name": _words(pid),
        "kind": "custom",
        "process": process,
    }
    if call.material:
        data["material"] = {"name": call.material}
    # the general rule asks every custom part for a finish; the card has none per part, so say so
    data["finish"] = NO_FINISH
    if call.role:
        data["role"] = call.role
    data["geometry"] = {"kit": call.kit, "args": args}
    body = yaml.safe_dump(
        data, sort_keys=False, default_flow_style=None, allow_unicode=True, width=100
    )
    header = (
        f"# Seeded from concept {card.id} by `n2f concept promote`, from the rough shapes "
        f"{_and([m.name for m in members])}.\n"
        "# Size it through its parameters and place it in the assembly's geometry module;\n"
        "# change the numbers, do not rewrite the part.\n"
    )
    return header + body


def _row(inst: _Instance, pid: str) -> str:
    """One row of a geometry module's table."""
    cells = ", ".join(
        f'"{axis}": ("{inst.anchors[axis][0]}", {_num_row(inst.anchors[axis][1])})' for axis in AXES
    )
    return (
        f'    {{"part": "{pid}", "label": "{inst.name}", "rz": {_num_row(inst.rz)},\n'
        f"     {cells}}},\n"
    )


def _num_row(x: float) -> str:
    return _num(x) if abs(x - round(x)) < 1e-9 else f"{x:.3f}".rstrip("0").rstrip(".")


GEOMETRY_DOC = '''"""Layout of {name}: every part where concept {cid}'s rough shapes drew it.

Seeded by `n2f concept promote`. The three overall sizes drive it ({sizes}):
x and y grow about the centre of the product, z grows upward from the floor. A part that
spans an overall size is as long as the size less its gaps to both faces (its own parameter
says how much); any other part keeps its size and its distance to the face it was drawn
nearest. Change the sizes in `parameters.yaml`, never the table; to move one part, edit its
row in `ROWS`: per axis the face it keeps to (`low`, `high`, or `mid` for the centre) and
the distance from that face in mm. No joints are modelled yet: the parts meet where the
card drew them.
"""
'''


def _geometry_text(
    card: ConceptCard,
    name: str,
    sizes: dict[str, str],
    centre: tuple[float, float],
    floor: float,
    rows: list[str],
) -> str:
    said = _and([f"`{sizes[a]}`" for a in AXES])
    return (
        GEOMETRY_DOC.format(name=name, cid=card.id, sizes=said)
        + "\nfrom __future__ import annotations\n\n"
        + "#: The parameters that hold the overall size along x, y and z.\n"
        + f"SIZES = {{{', '.join(f'{a!r}: {sizes[a]!r}' for a in AXES)}}}\n"
        + "#: The centre of the product in plan (mm) and its floor along z.\n"
        + f"CENTRE = ({_num_row(centre[0])}, {_num_row(centre[1])})\n"
        + f"FLOOR = {_num_row(floor)}\n"
        + "#: One row per placed instance, measured on the rough shapes of "
        + f"{card.id}.\nROWS = [\n"
        + "".join(rows)
        + "]\n\n\n"
        + "def build(P, I, parts):  # noqa: N803 — P and I are the recording accessors\n"
        + f'    """Place every row of the table ({name})."""\n'
        + "    from napkin2factory.geometry.seeded import place_rows\n\n"
        + "    return place_rows(P, parts, ROWS, sizes=SIZES, centre=CENTRE, floor=FLOOR)\n"
    )


def plan_seed(
    card: ConceptCard,
    product: Any,
    seeded: list[SeededParam],
    modules: ModulePlan,
    notes: list[str],
) -> SeedPlan:
    """The parts, sizes, layout and assemblies the card's rough shapes become (see the docstring).

    A product that already has parts or assemblies, a card without rough shapes, or rough shapes
    that do not compose give an empty plan whose ``skipped`` says why (and a note).

    Raises:
        GateBlocked: a file promotion would write already exists.
    """
    from napkin2factory.concepts.massing import compose
    from napkin2factory.core.model.parts import Part
    from napkin2factory.core.registry import registry

    plan = SeedPlan()
    if not card.massing:
        return plan
    if product.parts or product.assemblies:
        plan.skipped = (
            "the product already has parts or assemblies, so the card's rough shapes were not "
            "turned into a model: nothing was changed there"
        )
        notes.append(plan.skipped)
        return plan
    try:
        composed = compose(card, write=False, render=False)
    except Exception as exc:  # noqa: BLE001 — a card that no longer composes is told, not fatal
        plan.skipped = f"the rough shapes could not be composed ({exc}), so no model was seeded"
        notes.append(plan.skipped)
        return plan
    pieces = composed.pieces
    lo, hi = composed.bbox_min, composed.bbox_max
    extent = (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])
    matched = _envelope_match(card, seeded, extent)
    taken_params = set(product.parameters) | {p.name for p in seeded}
    for axis, i in zip(AXES, range(3), strict=True):
        if axis in matched:
            plan.sizes[axis] = matched[axis]
            continue
        name = _unique(OVERALL[axis], taken_params)
        plan.sizes[axis] = name
        value = _round(extent[i])
        text = _q_text(_quantity(value))
        plan.param_lines.append(
            param_line(
                name,
                {
                    "value": int(value) if float(value).is_integer() else value,
                    "unit": "mm",
                    "description": f"from concept {card.id}: measured across the rough shapes "
                    f"of {card.id} (the overall {_AXIS_WORD[axis]})",
                    "owner": SEED_OWNER,
                },
            )
        )
        plan.new_params.append(SeededParam(name, text, "new", source=f"rough shapes of {card.id}"))
    centre = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)
    size = {a: _size_of(plan, seeded, a, extent[i]) for i, a in enumerate(AXES)}
    box = {
        "x": (centre[0] - size["x"] / 2, centre[0] + size["x"] / 2),
        "y": (centre[1] - size["y"] / 2, centre[1] + size["y"] / 2),
        "z": (lo[2], lo[2] + size["z"]),
    }
    instances = _measure(card, pieces, box, notes)
    _overlap_note(pieces, notes)
    taken_parts: set[str] = set()
    processes = set(registry().processes())
    by_asm: dict[str | None, list[tuple[str, list[_Instance]]]] = {}
    for members in _group(instances):
        first = members[0].piece
        pid = _unique(_prefix([m.name for m in members]), taken_parts)
        args = dict(first.call.args)
        stretched: list[str] = []
        for axis, (arg, gap) in members[0].stretch.items():
            word = _AXIS_WORD[axis]
            if not gap:  # no gaps: the part is as long as the overall size itself
                args[arg] = f"param://{plan.sizes[axis]}"
                stretched.append(plan.sizes[axis])
                continue
            pname = _unique(f"{pid}-{arg}", taken_params)
            # the grammar has no length literals (core/expr.py): the gaps are a parameter
            gname = _unique(f"{pid}-{arg}-gap", taken_params)
            expr = f"{plan.sizes[axis]} - {gname}"
            plan.param_lines.append(
                param_line(
                    gname,
                    {
                        "value": float(_num_row(gap)) if not gap.is_integer() else int(gap),
                        "unit": "mm",
                        "description": f"from concept {card.id}: how much shorter the "
                        f"{_words(pid).lower()}'s {arg} is than the overall {word} "
                        "(its gaps to both faces)",
                        "owner": SEED_OWNER,
                    },
                )
            )
            plan.new_params.append(
                SeededParam(
                    gname, f"{_num_row(gap)} mm", "new", source=f"rough shapes of {card.id}"
                )
            )
            plan.param_lines.append(
                param_line(
                    pname,
                    {
                        "expr": expr,
                        "unit": "mm",
                        "description": f"from concept {card.id}: the {_words(pid).lower()}'s "
                        f"{arg}, which follows the overall {word}",
                        "owner": SEED_OWNER,
                    },
                )
            )
            plan.new_params.append(
                SeededParam(
                    pname,
                    f"{_num_row(extent[AXES.index(axis)] - gap)} mm",
                    "new",
                    source=f"rough shapes of {card.id}",
                )
            )
            args[arg] = f"param://{pname}"
            stretched.append(pname)
        process = first.process_class
        if process not in processes:
            # a cost class (``cots-controls``) is not always a process: the kit's own is
            fallback = str(first.built.result.features.process)
            notes.append(
                f"{pid}: {process!r} is a cost class, not a process the model knows, so the part "
                f"takes the kit's own, {fallback!r}"
            )
            process = fallback
        text = _part_text(card, pid, members, args, process)
        file = f"{_rel(product.root, product.paths.parts)}/{pid}.yaml"
        try:
            Part.model_validate(yaml.safe_load(text))
        except Exception as exc:
            raise GateBlocked(
                f"promotion could not seed the part {pid} from {members[0].name} ({exc}); "
                "nothing was written"
            ) from exc
        plan.texts[file] = text
        plan.parts.append(
            SeededPart(
                pid,
                _words(pid),
                len(members),
                first.kit,
                file,
                [m.name for m in members],
                first.call.module,
                stretched,
            )
        )
        by_asm.setdefault(first.call.module, []).append((pid, members))
    _assemblies(card, product, modules, plan, by_asm, centre, lo[2])
    return plan


_AXIS_WORD = {"x": "length", "y": "width", "z": "height"}


def _quantity(mm: float) -> Any:
    from napkin2factory.core.units import Quantity

    return Quantity(mm, "mm")


def _size_of(plan: SeedPlan, seeded: list[SeededParam], axis: str, measured: float) -> float:
    """The overall size along ``axis`` as the driving parameter will hold it (mm)."""
    name = plan.sizes[axis]
    for p in [*seeded, *plan.new_params]:
        if p.name == name:
            value = _mm(p.value)
            if value is not None:
                return value
    return measured


def _assemblies(
    card: ConceptCard,
    product: Any,
    modules: ModulePlan,
    plan: SeedPlan,
    by_asm: dict[str | None, list[tuple[str, list[_Instance]]]],
    centre: tuple[float, float],
    floor: float,
) -> None:
    """Write the top assembly, each module's assembly and their geometry modules."""
    rel_dir = _rel(product.root, product.paths.assemblies)
    top_id = modules.top or str(product.id)
    top_file = f"{rel_dir}/{top_id}.yaml"
    if modules.top is None and (product.paths.assemblies / f"{top_id}.yaml").exists():
        raise GateBlocked(
            f"{top_file} already exists; promotion never overwrites a file — move it away, "
            "then promote again"
        )
    geometry_dir = _rel(product.root, product.paths.model / "geometry")
    kids = [a.id for a in modules.seeded if not a.top]
    plan.top = top_id

    def write(
        asm_id: str,
        name: str,
        extra: list[str],
        owned: list[tuple[str, list[_Instance]]],
        modules_in: list[str],
    ) -> None:
        rows: list[str] = [f'    {{"asm": "{k}"}},\n' for k in modules_in]
        children = [f"  - {{asm: asm://{k}}}" for k in modules_in]
        placed: list[tuple[int, str]] = []
        for pid, members in owned:
            children.append(f"  - {{part: part://{pid}, qty: {len(members)}}}")
            placed += [(m.index, _row(m, pid)) for m in members]
        # the card's order, not the groups': a screen that breaks a tie by order sees the same
        # rough shapes in the same order on the built model (S-336)
        rows += [row for _, row in sorted(placed)]
        fname = f"{asm_id.replace('-', '_')}.py"
        plan.texts[f"{geometry_dir}/{fname}"] = _geometry_text(
            card, name, plan.sizes, centre, floor, rows
        )
        plan.geometry_files.append(f"{geometry_dir}/{fname}")
        lines = [f"id: {asm_id}", f"name: {_yaml_scalar(name)}", *extra]
        lines.append(f"geometry: {{module: geometry/{fname}}}")
        lines += ["children:", *children]
        header = (
            f"# Seeded from concept {card.id} by `n2f concept promote`: its parts, from the\n"
            f"# card's rough shapes; where they sit is in geometry/{fname}.\n"
        )
        plan.texts[f"{rel_dir}/{asm_id}.yaml"] = header + "\n".join(lines) + "\n"

    for name in kids:
        if name not in by_asm:
            continue  # a module with no rough shape keeps its empty stub
        stub = next(a for a in modules.seeded if a.id == name)
        extra = []
        if stub.build == "phantom":
            extra.append("build: phantom")
        if stub.driver:
            extra.append(f"driver: [{', '.join(stub.driver)}]")
        write(name, _words(name), extra, by_asm[name], [])
    write(top_id, str(product.manifest.product.name), [], by_asm.get(None, []), kids)
    plan.assemblies = list(modules.seeded) or [
        SeededAssembly(id=top_id, name=str(product.manifest.product.name), file=top_file, top=True)
    ]
