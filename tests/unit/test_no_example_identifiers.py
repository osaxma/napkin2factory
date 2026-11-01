"""The package never names an example (FOUNDATION F9, S-128).

The examples (``examples/*``) are users of the package, never its vocabulary. This guard
derives the forbidden set from the examples themselves — every part id, parameter slug,
interface id, assembly id, requirement id, decision id, doc id, calc name and concept-card
field name that an example holds and the shipped templates do not — and fails on any of them
appearing in ``src/napkin2factory/`` (code, strings, docstrings and comments alike;
``templates/`` and ``report/vendor/`` excluded), plus the example products' own names.

Not an English word list (F9): a single plain word (``door``, ``hinge``, ``latch``) is a
generic noun a grep for would cry wolf on, so only *compound* identifiers count (with a
hyphen, an underscore or a digit: ``door-guard``, ``max_temperature``, ``DEC-021``), exact
and whole (``door-swing`` does not match inside ``door-swing-clearance``). The product names
are matched whole as well, in any case (``Kiln``); identifiers match case for case. The card
fields the system's own generic screens declare (``concepts/screens/generic.py``), the
parameters those fields seed at promotion (the key with hyphens) and the parameters the
fits-the-space screen names for its door term are the system's vocabulary, which an example
then uses, so they are not forbidden; everything else a screen reads that only an example
needs lives in that example's folder (F10). A reviewer's question in
``docs/reviews/TEMPLATE.md`` catches what a grep cannot.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / "src" / "napkin2factory"
EXAMPLES = REPO / "examples"
TEMPLATES = PACKAGE / "templates"
#: Folders of the package that are not its own words: the templates (examples the package
#: ships on purpose) and third-party code.
EXCLUDED = (TEMPLATES, PACKAGE / "report" / "vendor")
TEXT_SUFFIXES = {".py", ".yaml", ".yml", ".j2", ".md", ".html", ".txt", ".json", ".css", ".js"}
COMPOUND = re.compile(r"[-_0-9]")

#: Example identifiers still in package files another v0.5 task owned in wave 2 (the calc
#: kit, M2; ``n2f init``, M4), where the v0.5 M3 task could not edit them. B-0084 clears this
#: list (v0.5 M7); nothing else may be added here.
_KILN_PARTS = {
    "controller-box", "controller-lid", "door-brick", "door-fiber", "door-guard",
    "door-switch", "door-tray", "fiber-back", "fiber-side", "fiber-slab", "guard-shell",
    "hinge-post", "latch-keeper", "limit-controller", "liner-back", "liner-side", "liner-slab",
    "outer-shell", "pid-controller",
}  # fmt: skip
ALLOWED: dict[str, set[str]] = {
    "calckit/__init__.py": {"kiln"},
    "calckit/data/cost_bands.yaml": {"DEC-012", "kiln", *_KILN_PARTS},
    "calckit/data/materials.yaml": {
        "brick-conductivity",
        "brick-density",
        "brick-specific-heat",
        "fiber-conductivity",
        "kiln",
    },  # fmt: skip
    "calckit/data/touch_limits.yaml": {"touch_limit"},
    "calckit/mass_cost.py": {"DEC-012", "kiln"},
    "calckit/power.py": {"DEC-004", "DEC-005", "kiln"},
    "calckit/thermal_enclosure.py": {"DEC-004", "DEC-015", "kiln"},
    "cli/init.py": {"kiln"},
}


def _stems(folder: Path, pattern: str) -> set[str]:
    return {p.stem for p in folder.glob(pattern)} if folder.is_dir() else set()


def _yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
    except yaml.YAMLError:
        return None


def _ids(path: Path, key: str) -> set[str]:
    data = _yaml(path)
    rows = data.get(key) if isinstance(data, dict) else None
    return {str(r["id"]) for r in rows or [] if isinstance(r, dict) and "id" in r}


def _calc_names(folder: Path) -> set[str]:
    """``<module>.<function>`` of every public calc (how ``calc://`` names one)."""
    out: set[str] = set()
    for path in folder.glob("*.py") if folder.is_dir() else []:
        if path.stem.startswith("_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        out |= {
            f"{path.stem}.{node.name}"
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        }
    return out


def _card_fields(product: Path) -> set[str]:
    out: set[str] = set()
    for path in sorted((product / "concepts").glob("*.yaml")):
        card = _yaml(path)
        if isinstance(card, dict):
            for section in ("envelope", "site"):
                value = card.get(section)
                if isinstance(value, dict):
                    out |= {str(k) for k in value}
    return out


def identifiers(product: Path) -> dict[str, str]:
    """Every identifier a product folder defines, with what it is."""
    model = product / "model"
    params = _yaml(model / "parameters.yaml")
    found: dict[str, str] = {}
    sources = {
        "part id": _stems(model / "parts", "*.yaml"),
        "parameter": set((params or {}).get("parameters") or {})
        if isinstance(params, dict)
        else set(),
        "interface id": _stems(model / "interfaces", "*.yaml"),
        "assembly id": _stems(model / "assemblies", "*.yaml"),
        "requirement id": _ids(model / "requirements.yaml", "requirements"),
        "decision id": _ids(model / "decisions.yaml", "decisions"),
        "doc id": _stems(model / "docs", "*.md"),
        "calc name": _calc_names(model / "calcs"),
        "card field": _card_fields(product),
    }
    for what, names in sources.items():
        for name in names:
            found.setdefault(str(name), what)
    return found


def product_names() -> set[str]:
    """Each example product's id and folder name (``kiln``), those the templates lack."""
    names: set[str] = set()
    for product in sorted(EXAMPLES.iterdir()):
        data = _yaml(product / "n2f.yaml")
        pid = data.get("product", {}).get("id") if isinstance(data, dict) else None
        names |= {product.name, *([str(pid)] if pid else [])}
    return names - {p.name for p in TEMPLATES.iterdir() if p.is_dir()}


def system_words() -> set[str]:
    """The card fields the generic screens declare and the parameters they seed (F8)."""
    from napkin2factory.concepts.screens import generic, generic_fields

    keys = {f.key for f in generic_fields()}
    return (
        keys
        | {k.replace("_", "-") for k in keys}
        | {
            generic.DOOR_LEAF_PARAM,
            generic.DOOR_ROOM_PARAM,
        }
    )


def forbidden() -> dict[str, str]:
    """Identifier → what it is in which example, for every example-only identifier."""
    allowed: set[str] = set()
    for template in TEMPLATES.iterdir():
        if template.is_dir():
            allowed |= set(identifiers(template))
    allowed |= system_words()
    out: dict[str, str] = {}
    for product in sorted(p for p in EXAMPLES.iterdir() if p.is_dir()):
        for name, what in identifiers(product).items():
            if name not in allowed and COMPOUND.search(name):
                out.setdefault(name, f"{what} in examples/{product.name}")
    for name in product_names():
        out.setdefault(name, "an example product's name")
    return out


def package_files() -> list[Path]:
    """Every text file of the package outside the templates and vendored code."""
    return sorted(
        p
        for p in PACKAGE.rglob("*")
        if p.is_file()
        and p.suffix in TEXT_SUFFIXES
        and "__pycache__" not in p.parts
        and not any(p.is_relative_to(x) for x in EXCLUDED)
    )


def hits() -> dict[str, list[str]]:
    """``relative file → ["line: identifier (what)", …]`` for every forbidden identifier."""
    names = forbidden()
    products = product_names()
    out: dict[str, list[str]] = defaultdict(list)
    for path in package_files():
        rel = path.relative_to(PACKAGE).as_posix()
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for m in _pattern(names).finditer(line):
                name = m.group(1)
                if name not in names and name.lower() in products:
                    name = name.lower()
                if name not in names or name in ALLOWED.get(rel, set()):
                    continue  # another case of an identifier, or allowed this wave
                out[rel].append(f"{no}: {m.group(1)} ({names[name]})")
    return dict(out)


@lru_cache(maxsize=4)
def _compiled(alternation: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9_-])({alternation})(?![A-Za-z0-9_-])", re.IGNORECASE)


def _pattern(names: dict[str, str]) -> re.Pattern[str]:
    """Every name whole; case is checked after the match (only product names ignore it)."""
    return _compiled("|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)))


def test_the_forbidden_set_is_derived_from_the_examples() -> None:
    names = forbidden()
    assert "kiln" in names  # the product name
    assert "door-guard" in names and names["door-guard"].startswith("part id")
    assert not any(n in names for n in ("door", "hinge", "REQ-001"))  # generic or templated
    assert "door_swing" not in names and "door-leaf-width" not in names  # the system's words


def test_the_package_names_no_example() -> None:
    found = hits()
    listing = "\n".join(f"  {f}: {h}" for f, rows in found.items() for h in rows)
    assert not found, (
        f"the package names an example's identifiers ({sum(map(len, found.values()))}):\n"
        f"{listing}\nmove what only the example needs into its folder (F10), or rename it"
    )


def test_the_allow_list_only_holds_live_entries() -> None:
    """An allow-list entry that no longer matches is stale: remove it."""
    names = forbidden()
    for rel, allowed in ALLOWED.items():
        text = (PACKAGE / rel).read_text(encoding="utf-8")
        for name in allowed:
            assert name in names, f"{rel}: {name} is not an example identifier"
            assert re.search(
                rf"(?<![A-Za-z0-9_-]){re.escape(name)}(?![A-Za-z0-9_-])", text, re.IGNORECASE
            ), f"{rel} no longer names {name}: drop it from ALLOWED"
