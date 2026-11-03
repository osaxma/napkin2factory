"""The package never names an example (FOUNDATION F9, S-128, amended by S-185).

The examples (``examples/*``) are users of the package, never its vocabulary. This guard
derives the forbidden set from the examples themselves — every part id, parameter slug,
interface id, assembly id, requirement id, decision id, doc id, calc name and concept-card
field name that an example holds and the shipped templates do not — plus the example
products' own names.

Under S-185, targeted structural checks replace blind full-text scanning so everyday
examples (such as ``examples/table`` with parts like ``base-plate`` or ``top-rail``) do
not flag HTML tags (like ``<table>``), CSS classes, or ordinary English prose in comments
and docstrings:
- Check A (AST, ``.py`` files only): fails on a string constant (including inside f-strings)
  that is not a docstring and equals an example compound identifier exactly. Product names
  are excluded from Check A so ordinary words like ``"table"`` remain legal.
- Check B (all text files): fails on qualified URIs naming an example identifier
  (``<scheme>://<id>`` for any scheme, e.g. ``part://``, ``asm://``, ``ifc://``,
  ``param://``, ``req://``, ``elec://``), on example requirement, decision or change ids
  (``REQ-nnn``, ``DEC-nnn``, ``ECR-nnn`` style ids defined by examples), and on
  ``examples/<product-folder>`` paths.
Comments, docstrings and HTML/CSS prose are otherwise free.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
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
URI_RE = re.compile(r"\b[a-zA-Z][a-zA-Z0-9_-]*://([A-Za-z0-9_./-]+)")

#: Example identifiers a package file may still name (emptied in S-129): keep it empty;
#: a product's noun belongs in its folder (F10), a source cites a handbook or "a product's
#: measured value", never an example's ids.
ALLOWED: dict[str, set[str]] = {}


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


def package_files(package_root: Path = PACKAGE) -> list[Path]:
    """Every text file of the package outside the templates and vendored code."""
    excluded = (package_root / "templates", package_root / "report" / "vendor")
    return sorted(
        p
        for p in package_root.rglob("*")
        if p.is_file()
        and p.suffix in TEXT_SUFFIXES
        and "__pycache__" not in p.parts
        and not any(p.is_relative_to(x) for x in excluded)
    )


def _docstring_node_ids(tree: ast.AST) -> set[int]:
    """Ids of AST nodes that represent module, class, or function docstrings."""
    doc_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                doc_ids.add(id(node.body[0].value))
    return doc_ids


def scan(package_root: Path, forbidden: dict[str, str]) -> dict[str, list[str]]:
    """Scan files under ``package_root`` for forbidden example identifiers.

    Check A (AST, ``.py`` only): fails on string constants that match compound identifiers
    (product names excluded).
    Check B (all text files): fails on qualified URIs, REQ/DEC/ECR style ids, and
    ``examples/<product-folder>`` paths.
    """
    prods = {k for k, v in forbidden.items() if "product" in v.lower()}
    compounds = {k: v for k, v in forbidden.items() if k not in prods and COMPOUND.search(k)}
    req_dec_ecr = {k for k, v in forbidden.items() if re.match(r"^(REQ|DEC|ECR)-\d+", k)}

    req_dec_alts = "|".join(re.escape(k) for k in sorted(req_dec_ecr, key=len, reverse=True))
    req_dec_re = (
        re.compile(rf"(?<![A-Za-z0-9_-])(?:{req_dec_alts})(?![A-Za-z0-9_-])")
        if req_dec_ecr
        else None
    )
    prod_alts = "|".join(re.escape(p) for p in sorted(prods, key=len, reverse=True))
    ex_path_re = (
        re.compile(rf"(?<![A-Za-z0-9_-])examples/(?:{prod_alts})(?![A-Za-z0-9_-])")
        if prods
        else None
    )

    hits_by_file: dict[str, list[str]] = defaultdict(list)

    for path in package_files(package_root):
        rel = path.relative_to(package_root).as_posix()
        allowed_names = ALLOWED.get(rel, set())

        # Check A: AST inspection for Python files
        if path.suffix == ".py":
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError:
                tree = None
            if tree is not None:
                doc_ids = _docstring_node_ids(tree)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        if id(node) in doc_ids:
                            continue
                        val = node.value
                        if val in compounds and val not in allowed_names:
                            msg = f"{node.lineno}: {val} ({forbidden[val]})"
                            if msg not in hits_by_file[rel]:
                                hits_by_file[rel].append(msg)

        # Check B: Qualified URIs, REQ/DEC/ECR ids, and example folder paths
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for m in URI_RE.finditer(line):
                target = m.group(1)
                for seg in target.split("/"):
                    seg_clean = seg.split("#")[0].rstrip(".")
                    hit_key = (
                        seg_clean
                        if seg_clean in forbidden
                        else (seg_clean.lower() if seg_clean.lower() in prods else None)
                    )
                    if hit_key and hit_key not in allowed_names:
                        msg = f"{no}: {m.group(0)} ({forbidden.get(hit_key, 'example URI')})"
                        if msg not in hits_by_file[rel]:
                            hits_by_file[rel].append(msg)

            if req_dec_re:
                for m in req_dec_re.finditer(line):
                    matched_id = m.group(0)
                    if matched_id not in allowed_names:
                        msg = f"{no}: {matched_id} ({forbidden[matched_id]})"
                        if msg not in hits_by_file[rel]:
                            hits_by_file[rel].append(msg)

            if ex_path_re:
                for m in ex_path_re.finditer(line):
                    matched_path = m.group(0)
                    if matched_path not in allowed_names:
                        msg = f"{no}: {matched_path} (example path)"
                        if msg not in hits_by_file[rel]:
                            hits_by_file[rel].append(msg)

    return dict(hits_by_file)


def hits() -> dict[str, list[str]]:
    """``relative file → ["line: identifier (what)", …]`` for every forbidden identifier."""
    return scan(PACKAGE, forbidden())


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


def test_guard_catches_planted_literal_and_uri(tmp_path: Path) -> None:
    """A planted part("<id>") literal and a planted part://<id> are caught."""
    names = forbidden()
    example_id = "door-guard"
    assert example_id in names

    # Planted literal in a Python file
    py_file = tmp_path / "planted.py"
    py_file.write_text(f'def make():\n    return part("{example_id}")\n', encoding="utf-8")

    # Planted qualified URI in a YAML file
    yaml_file = tmp_path / "planted.yaml"
    yaml_file.write_text(f"source: part://{example_id}\n", encoding="utf-8")

    found = scan(tmp_path, names)
    assert "planted.py" in found
    assert any(example_id in h for h in found["planted.py"])
    assert "planted.yaml" in found
    assert any(f"part://{example_id}" in h for h in found["planted.yaml"])


def test_guard_ignores_prose_comments_docstrings_and_html(tmp_path: Path) -> None:
    """The same id in a comment, a docstring and <table> in an HTML file are not caught."""
    names = forbidden()
    example_id = "door-guard"
    assert example_id in names

    # Comment in a Python file
    comment_file = tmp_path / "comment.py"
    comment_file.write_text(f"# Uses {example_id} as an example\nx = 1\n", encoding="utf-8")

    # Docstrings in a Python file (both module and function docstrings)
    doc_file = tmp_path / "documented.py"
    doc_file.write_text(
        f'"""Module docstring referring to {example_id}."""\n\n'
        f"def func():\n"
        f'    """Function docstring for {example_id}."""\n'
        f"    return 42\n",
        encoding="utf-8",
    )

    # <table> in an HTML file
    html_file = tmp_path / "page.html"
    html_file.write_text(
        "<table>\n  <tr><td>Ordinary table content</td></tr>\n</table>\n",
        encoding="utf-8",
    )

    # Even with an example product named "table", <table> in HTML is not caught
    names_with_table = dict(names, table="an example product's name")
    found = scan(tmp_path, names_with_table)
    assert not found, f"unexpected hits on prose/docstring/html: {found}"
