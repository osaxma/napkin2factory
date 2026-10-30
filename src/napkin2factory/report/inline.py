"""Bundle the vendored three.js modules and the viewer into one inline module script.

External ES-module files do not load from ``file://`` (opaque-origin CORS), but an
inline ``<script type="module">`` does.  So the report concatenates the pinned
three.js core, the addon modules it needs, and ``viewer.js`` into a single block
(decision D13).  Addons are wrapped in block scopes so their top-level names
cannot collide with the core; their exports are re-bound at top level through a
holder object.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

VENDOR_DIR = Path(__file__).parent / "vendor" / "three"
VIEWER_JS = Path(__file__).parent / "viewer.js"
THREE_VERSION = "0.170.0"

#: Addon modules, in dependency order.  Each is wrapped and its exports re-bound.
ADDONS: tuple[str, ...] = ("BufferGeometryUtils.js", "GLTFLoader.js", "OrbitControls.js")

_IMPORT_RE = re.compile(
    r"^import\s+(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)\s+from\s+['\"][^'\"]+['\"];?\s*$"
    r"|^import\s+['\"][^'\"]+['\"];?\s*$",
    re.MULTILINE,
)
_EXPORT_BLOCK_RE = re.compile(r"^export\s*\{([^}]*)\};?\s*$", re.MULTILINE)
_EXPORT_DECL_RE = re.compile(
    r"^export\s+(?=(?:const|let|var|class|function|async)\b)", re.MULTILINE
)


def _strip_imports(src: str) -> str:
    return _IMPORT_RE.sub("", src)


def _export_names(src: str) -> list[str]:
    names: list[str] = []
    for m in _EXPORT_BLOCK_RE.finditer(src):
        for item in m.group(1).split(","):
            item = item.strip()
            if not item:
                continue
            # "Foo as Bar" exports Bar
            names.append(item.split(" as ")[-1].strip())
    for m in re.finditer(
        r"^export\s+(?:const|let|var|class|function\*?|async function)\s+(\w+)", src, re.MULTILINE
    ):
        names.append(m.group(1))
    return sorted(set(names))


def _strip_exports(src: str) -> str:
    src = _EXPORT_BLOCK_RE.sub("", src)
    return _EXPORT_DECL_RE.sub("", src)


def _wrap_addon(name: str, src: str, index: int) -> str:
    exports = _export_names(src)
    body = _strip_exports(_strip_imports(src))
    holder = f"__n2f_mod{index}"
    assigns = "\n".join(f"{holder}.{n} = {n};" for n in exports)
    rebind = f"const {{ {', '.join(exports)} }} = {holder};" if exports else ""
    header = f"// ---- {name} (three.js r{THREE_VERSION}) ----"
    return f"{header}\nconst {holder} = {{}};\n{{\n{body}\n{assigns}\n}}\n{rebind}\n"


@lru_cache(maxsize=1)
def bundle_three() -> str:
    """Return the three.js core plus addons as one import-free script body."""
    core = (VENDOR_DIR / "three.module.js").read_text(encoding="utf-8")
    parts = [f"// ---- three.module.js (three.js r{THREE_VERSION}) ----\n" + _strip_exports(core)]
    for i, addon in enumerate(ADDONS, start=1):
        parts.append(_wrap_addon(addon, (VENDOR_DIR / addon).read_text(encoding="utf-8"), i))
    return "\n".join(parts)


def bundle_viewer() -> str:
    """Return three.js plus ``viewer.js`` ready to be placed in one inline module script."""
    viewer = VIEWER_JS.read_text(encoding="utf-8") if VIEWER_JS.exists() else ""
    return bundle_three() + "\n// ---- viewer.js ----\n" + _strip_imports(_strip_exports(viewer))


def inline_module_script(body: str) -> str:
    """Wrap a script body in an inline ES-module tag, escaping any closing script tag."""
    safe = body.replace("</script", "<\\/script")
    return f'<script type="module">\n{safe}\n</script>'
