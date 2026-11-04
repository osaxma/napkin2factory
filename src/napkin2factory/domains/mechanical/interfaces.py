"""Mechanical domain interface kinds (milestone M2b, W5 amended).

The four mechanical interface kinds:
- ``threaded-insert``: threaded insert (e.g. brass insert) embedded in wood/plastic substrate.
- ``wood-screw-pattern``: wood screws into wood/plastic substrate.
- ``t-slot-joint``: cap screw and T-nut securing a plate or bracket to an extrusion.
- ``hinge-pin``: hinge pin joining two leaves or knuckles.

Each spec subclasses :class:`~napkin2factory.core.model.interfaces.BoltPatternSpec` (S-144).
Holes are cut per-party through :meth:`BoltPatternSpec.hole_for`: the receiving party gets
the installation bore or pilot diameter, the passing party gets the clearance diameter,
and the extrusion in a T-slot joint gets no hole.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from napkin2factory.core.domain import InterfaceKind
from napkin2factory.core.model.base import PartUri, QuantityOrParam
from napkin2factory.core.model.interfaces import BoltPatternSpec, HardwareItem
from napkin2factory.core.units import parse_quantity

#: Path to the shared materials table in the calc kit.
SHARED_MATERIALS_TABLE = Path(__file__).resolve().parents[2] / "calckit" / "data" / "materials.yaml"

_WOOD_KEYWORDS = {
    "wood",
    "oak",
    "maple",
    "walnut",
    "pine",
    "plywood",
    "mdf",
    "timber",
    "hardwood",
    "softwood",
    "birch",
    "cedar",
    "ash",
    "cherry",
    "beech",
    "spruce",
    "fir",
    "lumber",
    "particleboard",
    "chipboard",
}

_PLASTIC_KEYWORDS = {
    "plastic",
    "polycarbonate",
    "acrylic",
    "pmma",
    "acetal",
    "pom",
    "delrin",
    "hdpe",
    "nylon",
    "pa6",
    "pla",
    "petg",
    "abs",
    "polymer",
    "peek",
    "ptfe",
    "polyethylene",
    "polypropylene",
    "pvc",
}


def _default_bore(thread: str) -> str:
    """Default installation bore diameter for a metric threaded insert."""
    t = thread.strip().upper()
    if t.startswith("M"):
        digits = ""
        for ch in t[1:]:
            if ch.isdigit() or ch == ".":
                digits += ch
            else:
                break
        if digits:
            try:
                val = float(digits)
                if val <= 3:
                    return f"{val + 1.5:g} mm"
                return f"{val + 2.0:g} mm"
            except ValueError:
                pass
    return "10 mm"


def _default_clearance(thread: str) -> str:
    """Default clearance hole diameter for a metric machine screw."""
    t = thread.strip().upper()
    if t.startswith("M"):
        digits = ""
        for ch in t[1:]:
            if ch.isdigit() or ch == ".":
                digits += ch
            else:
                break
        if digits:
            try:
                val = float(digits)
                if val == 3:
                    return "3.4 mm"
                if val == 4:
                    return "4.5 mm"
                if val == 5:
                    return "5.5 mm"
                if val == 6:
                    return "6.6 mm"
                if val == 8:
                    return "9 mm"
                return f"{val + 1.0:g} mm"
            except ValueError:
                pass
    return "9 mm"


def _party_words(product: Any, party: Any) -> str:
    """Owner words for a party (part or assembly)."""
    table = product.parts if party.scheme == "part" else product.assemblies
    obj = table.get(party.id)
    return str(getattr(obj, "name", None) or party.id).lower()


def _check_material_is_wood_or_plastic(part: Any) -> tuple[bool, str]:
    """Check if the receiving part's material is a wood or plastic in materials.yaml."""
    mat = getattr(part, "material", None)
    if mat is None:
        return False, "no material declared"
    mat_name = str(getattr(mat, "name", mat) or "").strip()
    if not mat_name:
        return False, "no material declared"
    mat_lower = mat_name.lower()
    mat_spec = str(getattr(mat, "spec", "") or "").lower()

    rows: list[dict[str, Any]] = []
    if SHARED_MATERIALS_TABLE.is_file():
        try:
            from napkin2factory.core.yamlio import read_yaml

            data = read_yaml(SHARED_MATERIALS_TABLE)
            rows = data.get("rows", [])
        except Exception:
            pass

    matched_row: dict[str, Any] | None = None
    for row in rows:
        row_name = str(row.get("name", "")).lower()
        keywords = [str(k).lower() for k in row.get("keywords", [])]
        if (
            mat_lower == row_name
            or mat_lower in keywords
            or any(k in mat_lower for k in keywords if len(k) > 2)
            or any(k in mat_spec for k in keywords if len(k) > 2)
        ):
            matched_row = row
            break

    if matched_row is not None:
        if matched_row.get("moisture_basis") is not None:
            return True, mat_name
        if matched_row.get("process_class") in ("woodworking", "cnc-routing"):
            return True, mat_name
        if matched_row.get("process_class") == "3d-print":
            return True, mat_name
        row_str = (
            str(matched_row.get("name", ""))
            + " "
            + " ".join(str(k) for k in matched_row.get("keywords", []))
        ).lower()
        if any(w in row_str for w in _WOOD_KEYWORDS) or any(
            p in row_str for p in _PLASTIC_KEYWORDS
        ):
            return True, mat_name
        return False, mat_name

    if any(w in mat_lower for w in _WOOD_KEYWORDS) or any(
        p in mat_lower for p in _PLASTIC_KEYWORDS
    ):
        return True, mat_name

    return False, mat_name


class ThreadedInsertSpec(BoltPatternSpec):
    """A threaded insert joint: machine screw into an insert embedded in wood or plastic.

    The receiving party (``insert_part``) receives the installation bore diameter,
    while the passing party receives the clearance hole ``diameter``.
    """

    thread: str = Field(description="Internal machine thread size, e.g. 'M8', 'M6'")
    insert_length: QuantityOrParam = Field(
        description="Overall length of the threaded insert (e.g. '12 mm')"
    )
    insert_part: PartUri = Field(description="The part URI receiving the threaded insert")
    bore_diameter: QuantityOrParam | None = Field(
        default=None,
        description="Installation bore diameter for the insert (e.g. '10 mm'); derived if omitted",
    )
    diameter: QuantityOrParam = Field(
        default="9 mm",
        description="Fastener clearance hole diameter in the passing party (e.g. '9 mm')",
    )

    @model_validator(mode="before")
    @classmethod
    def _default_clearance(cls, data: Any) -> Any:
        if isinstance(data, dict) and "diameter" not in data and "thread" in data:
            data["diameter"] = parse_quantity(_default_clearance(str(data["thread"])))
        return data

    def hole_for(self, party_uri: str) -> QuantityOrParam | None:
        """Clearance hole on the passing party; installation bore on the receiving insert_part."""
        uri = str(party_uri)
        insert_uri = str(self.insert_part)
        if uri == insert_uri or uri.removeprefix("part://") == insert_uri.removeprefix("part://"):
            return (
                self.bore_diameter
                if self.bore_diameter is not None
                else parse_quantity(_default_bore(self.thread))
            )
        return self.diameter


class WoodScrewSpec(BoltPatternSpec):
    """A wood screw pattern: wood screws fastening through one party into a wood/plastic part.

    The receiving party (``wood_part``) receives the pilot hole diameter,
    while the passing party receives the clearance hole ``diameter``.
    """

    screw_size: str = Field(description="Wood screw size, e.g. '#8', 'No. 8', '4 mm', '5 mm'")
    pilot_diameter: QuantityOrParam = Field(
        description="Pilot hole diameter in the wood substrate (e.g. '2.5 mm')"
    )
    wood_part: PartUri = Field(description="The part URI receiving the screw pilot holes")
    diameter: QuantityOrParam = Field(
        default="5 mm",
        description="Fastener shank/clearance hole diameter in the passing party (e.g. '5 mm')",
    )

    def hole_for(self, party_uri: str) -> QuantityOrParam | None:
        """Clearance hole on the passing party; pilot hole on the receiving wood_part."""
        uri = str(party_uri)
        wood_uri = str(self.wood_part)
        if uri == wood_uri or uri.removeprefix("part://") == wood_uri.removeprefix("part://"):
            return self.pilot_diameter
        return self.diameter


class TSlotSpec(BoltPatternSpec):
    """A T-slot joint: cap screw and T-nut fixing a plate or bracket to an extrusion.

    The extrusion party (``slot_part``) gets no hole; the bracket or plate party gets
    the clearance hole ``diameter``.  Hardware per hole includes both the fastener and the T-nut.
    """

    slot_part: PartUri = Field(description="The extrusion member part URI, which gets no hole")
    tnut: PartUri | None = Field(default=None, description="T-nut hardware part URI")
    diameter: QuantityOrParam = Field(
        default="5.5 mm",
        description="Clearance hole diameter in the bracket or plate (e.g. '5.5 mm')",
    )

    def hardware_items(self) -> list[HardwareItem]:
        """Hardware one joint takes: explicit hardware, else fastener and tnut per hole."""
        if self.hardware is not None:
            return list(self.hardware)
        items: list[HardwareItem] = []
        if self.fastener is not None:
            items.append(HardwareItem(part=self.fastener, per_hole=1))
        if self.tnut is not None:
            items.append(HardwareItem(part=self.tnut, per_hole=1))
        return items

    def hole_for(self, party_uri: str) -> QuantityOrParam | None:
        """Clearance hole on the bracket/plate; slot_part gets no hole."""
        uri = str(party_uri)
        slot_uri = str(self.slot_part)
        if uri == slot_uri or uri.removeprefix("part://") == slot_uri.removeprefix("part://"):
            return None
        return self.diameter


class HingePinSpec(BoltPatternSpec):
    """A hinge pin joint between two leaves or knuckles.

    Both parties receive the hinge pin hole ``pin_diameter``.
    """

    pin_diameter: QuantityOrParam = Field(
        default="6 mm", description="Hinge pin diameter (e.g. '6 mm')"
    )
    axis_note: str | None = Field(
        default=None, description="Note on hinge rotation axis orientation"
    )
    diameter: QuantityOrParam = Field(
        default="6 mm", description="Hole diameter for the hinge pin (e.g. '6 mm')"
    )
    count: int = Field(default=1, description="Number of hinge pin holes")

    @model_validator(mode="before")
    @classmethod
    def _sync_diameter(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "pin_diameter" in data and "diameter" not in data:
                data["diameter"] = data["pin_diameter"]
            elif "diameter" in data and "pin_diameter" not in data:
                data["pin_diameter"] = data["diameter"]
        return data

    def hole_for(self, party_uri: str) -> QuantityOrParam | None:
        """Both parties get the hinge pin diameter."""
        return self.pin_diameter or self.diameter


def check_threaded_insert(product: Any, iface: Any, build_dir: Path) -> dict[str, Any]:
    """Check that insert_part exists among the parties and its material is wood or plastic."""
    first, second = (_party_words(product, p) for p in iface.parties)
    joint = f"{first} to {second}"
    spec = iface.spec
    parties_uris = {str(p) for p in iface.parties}
    if (
        str(spec.insert_part) not in parties_uris
        and f"part://{spec.insert_part}" not in parties_uris
    ):
        return {
            "status": "fail",
            "message": (
                f"{joint}: receiving part {spec.insert_part} is not among the joint parties; "
                "add it to `parties:`"
            ),
        }
    pid = str(spec.insert_part).removeprefix("part://")
    part = product.parts.get(pid)
    if part is None:
        return {
            "status": "fail",
            "message": f"{joint}: receiving part {spec.insert_part} does not exist",
        }
    ok, mat_name = _check_material_is_wood_or_plastic(part)
    if not ok:
        return {
            "status": "fail",
            "message": (
                f"{joint}: {part.name} material is '{mat_name}', which is not wood or plastic; "
                f"threaded inserts require a wood or plastic receiving part "
                f"(change {part.name}'s material or use a bolt pattern)"
            ),
        }
    return {
        "status": "pass",
        "message": f"{joint}: threaded insert into {part.name} ({mat_name})",
    }


def check_wood_screw(product: Any, iface: Any, build_dir: Path) -> dict[str, Any]:
    """Check that wood_part exists among the parties and its material is wood or plastic."""
    first, second = (_party_words(product, p) for p in iface.parties)
    joint = f"{first} to {second}"
    spec = iface.spec
    parties_uris = {str(p) for p in iface.parties}
    if str(spec.wood_part) not in parties_uris and f"part://{spec.wood_part}" not in parties_uris:
        return {
            "status": "fail",
            "message": (
                f"{joint}: receiving part {spec.wood_part} is not among the joint parties; "
                "add it to `parties:`"
            ),
        }
    pid = str(spec.wood_part).removeprefix("part://")
    part = product.parts.get(pid)
    if part is None:
        return {
            "status": "fail",
            "message": f"{joint}: receiving part {spec.wood_part} does not exist",
        }
    ok, mat_name = _check_material_is_wood_or_plastic(part)
    if not ok:
        return {
            "status": "fail",
            "message": (
                f"{joint}: {part.name} material is '{mat_name}', which is not wood or plastic; "
                f"wood screws require a wood or plastic receiving part "
                f"(change {part.name}'s material or use a bolt pattern)"
            ),
        }
    return {
        "status": "pass",
        "message": f"{joint}: wood screw into {part.name} ({mat_name})",
    }


def check_t_slot(product: Any, iface: Any, build_dir: Path) -> dict[str, Any]:
    """Check that slot_part is an extrusion profile or extrusion-cut process."""
    first, second = (_party_words(product, p) for p in iface.parties)
    joint = f"{first} to {second}"
    spec = iface.spec
    parties_uris = {str(p) for p in iface.parties}
    if str(spec.slot_part) not in parties_uris and f"part://{spec.slot_part}" not in parties_uris:
        return {
            "status": "fail",
            "message": (
                f"{joint}: slot part {spec.slot_part} is not among the joint parties; "
                "add it to `parties:`"
            ),
        }
    pid = str(spec.slot_part).removeprefix("part://")
    part = product.parts.get(pid)
    if part is None:
        return {
            "status": "fail",
            "message": f"{joint}: slot part {spec.slot_part} does not exist",
        }

    profile: Any = None
    if getattr(part, "geometry", None) is not None:
        args = getattr(part.geometry, "args", {})
        if isinstance(args, dict):
            profile = args.get("profile") or (
                args.get("member", {}).get("profile")
                if isinstance(args.get("member"), dict)
                else None
            )

    feats_path = build_dir / "parts" / pid / "features.json"
    if feats_path.is_file():
        try:
            feats = json.loads(feats_path.read_text(encoding="utf-8"))
            profile = profile or feats.get("profile") or feats.get("extra", {}).get("profile")
        except Exception:
            pass

    if profile is None:
        notes = str(getattr(part, "notes", "") or "")
        name = str(getattr(part, "name", "") or "")
        if "t-slot" in notes.lower() or "t-slot" in name.lower():
            profile = "t-slot"

    is_tslot_profile = profile is not None and "t-slot" in str(profile).lower()
    is_extrusion_cut = getattr(part, "process", "") == "extrusion-cut"

    if not (is_tslot_profile or is_extrusion_cut):
        return {
            "status": "warn",
            "message": (
                f"{joint}: {part.name} process is '{part.process}' and profile is not t-slot; "
                "t-slot joints expect an extrusion-cut t-slot member"
            ),
        }
    return {
        "status": "pass",
        "message": f"{joint}: t-slot joint on {part.name}",
    }


def check_hinge_pin(product: Any, iface: Any, build_dir: Path) -> dict[str, Any]:
    """Check that a hinge pin joins exactly two parties."""
    if len(iface.parties) != 2:
        return {
            "status": "fail",
            "message": (
                f"a hinge pin joins exactly two parties, but {len(iface.parties)} were given"
            ),
        }
    first, second = (_party_words(product, p) for p in iface.parties)
    return {
        "status": "pass",
        "message": f"hinge pin joins {first} and {second}",
    }


#: The four mechanical interface kinds (W5 amended).
INTERFACE_KINDS = (
    InterfaceKind(
        "threaded-insert",
        "Threaded insert",
        spec=ThreadedInsertSpec,
        check=check_threaded_insert,
    ),
    InterfaceKind(
        "wood-screw-pattern",
        "Wood screw pattern",
        spec=WoodScrewSpec,
        check=check_wood_screw,
    ),
    InterfaceKind(
        "t-slot-joint",
        "T-slot joint",
        spec=TSlotSpec,
        check=check_t_slot,
    ),
    InterfaceKind(
        "hinge-pin",
        "Hinge pin",
        spec=HingePinSpec,
        check=check_hinge_pin,
    ),
)
