"""Styled concept screenshots: the inline viewer, ``style.yaml`` materials, a studio rig (N6).

One self-contained HTML page per card (the report's inline module machinery, the massing
GLB as base64, zero external references) boots the viewer with per-part materials from the
resolved style (each massing call's role → palette colour and finish), the fixed studio
lighting and a preset camera; headless Chromium snapshots ``iso`` and ``front`` at
1200 × 900 into ``renders/styled-iso.png`` and ``renders/styled-front.png``.

:class:`ScreenshotSession` keeps one browser page for a whole ``n2f concept build --all``.
When Playwright is missing, Chromium will not start, or ``N2F_NO_PLAYWRIGHT=1`` is set, the
z-buffer ``iso.png``/``front.png`` are copied to the styled names instead and the card says
so (``[revisit]``): z-buffer renders are for correctness, viewer screenshots for appearance
(D12 as amended by S-059 and N6).

Layout marks (review gate B, C16): the silhouette has no door, hinge, handle or controls
face, so the card's ``layout`` words would be invisible.  The page draws them as flat, unlit
ink on the shapes' faces (a door outline with a heavy hinge edge and a handle bar opposite
it, a controls panel with a display and two knobs).  They annotate the words; they are not
designed geometry and nothing is measured from them.

A blank capture (headless GL occasionally hands back an empty frame under load, S-093) is
detected and the card is rendered once more; a second blank falls back to the correctness
renders with a note, like any other viewer failure.  A shader that fails to compile under the
same load (``THREE.WebGLProgram: Shader Error``) is retried the same way (S-108).
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from napkin2factory.core.model.concepts import ConceptCard
from napkin2factory.core.model.style import StyleFile, role_for

#: Snapshot size in CSS pixels (device scale 1): at least 1200 px wide (N6).
VIEWPORT: tuple[int, int] = (1200, 900)
#: The views written, in order, as ``styled-<view>.png``.
VIEWS: tuple[str, ...] = ("iso", "front")
#: Software WebGL so the screenshots work on machines without a GPU (as the report test).
CHROMIUM_ARGS: tuple[str, ...] = ("--use-gl=swiftshader", "--enable-unsafe-swiftshader")
#: Set to 1 to force the z-buffer fallback (tests, machines without a browser).
NO_PLAYWRIGHT_ENV = "N2F_NO_PLAYWRIGHT"

Method = Literal["viewer", "zbuffer-fallback"]

Vec = tuple[int, int, int]

#: A face of a box as ``(outward normal, right, up)`` for a person facing it from outside,
#: in model axes (x to the right, y to the back, z up: the front faces -y, as the ``front``
#: camera sees it).  Every triple is right-handed (right × up = normal).
FACES: dict[str, tuple[Vec, Vec, Vec]] = {
    "front": ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
    "back": ((0, 1, 0), (-1, 0, 0), (0, 0, 1)),
    "right": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "left": ((-1, 0, 0), (0, -1, 0), (0, 0, 1)),
    "top": ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
    "bottom": ((0, 0, -1), (1, 0, 0), (0, -1, 0)),
}
#: Layout words → the direction they name.
_DIRECTION_WORDS: dict[str, Vec] = {
    "left": (-1, 0, 0),
    "right": (1, 0, 0),
    "front": (0, -1, 0),
    "back": (0, 1, 0),
    "rear": (0, 1, 0),
    "top": (0, 0, 1),
    "lid": (0, 0, 1),
    "bottom": (0, 0, -1),
}
_BELOW_WORDS = frozenset({"below", "under", "underneath", "bottom", "low", "lower"})
_NONE_WORDS = frozenset({"none", "no", "without"})
#: Mark inks: dark on light faces, light on dark ones; neutral so they read as drawn on.
INK_DARK = "#23272b"
INK_LIGHT = "#f3f2ee"
#: Relative luminance above which a face gets the dark ink (sRGB, 0..1; by eye: industrial's
#: #3f444a door gets light ink, appliance's #e6e3dc and industrial's orange controls dark).
INK_THRESHOLD = 0.18
#: A capture is blank when fewer than this share of pixels differ from its border colour.
BLANK_SHARE = 0.003
#: …by more than this (0..255 on any channel): lighting gradients on the backdrop stay under.
BLANK_TOLERANCE = 12
#: Page errors that headless GL raises under load and a reload clears (S-108).
TRANSIENT_GL_ERRORS = ("THREE.WebGLProgram: Shader Error", "CONTEXT_LOST_WEBGL")


@dataclass
class ScreenshotResult:
    """What :func:`styled_screenshots` wrote and how."""

    paths: dict[str, Path] = field(default_factory=dict)
    method: Method = "viewer"
    notes: list[str] = field(default_factory=list)
    #: The first capture came back blank, or its shader failed under load, and the card was
    #: rendered once more (S-093, S-108).
    retried: bool = False

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        """JSON form (paths relative to ``root`` when given)."""

        def rel(p: Path) -> str:
            if root is not None:
                try:
                    return p.relative_to(root).as_posix()
                except ValueError:
                    pass
            return str(p)

        return {
            "method": self.method,
            "paths": {k: rel(v) for k, v in self.paths.items()},
            "notes": list(self.notes),
        }


def fallback_note(why: str) -> str:
    """The card note for the z-buffer fallback."""
    return f"styled screenshots unavailable ({why}): showing correctness renders [revisit]"


def card_materials(card: ConceptCard, style: StyleFile) -> dict[str, dict[str, Any]]:
    """Viewer materials by GLB node URI: each massing call's role → colour and finish."""
    from napkin2factory.concepts.massing import concept_uri

    return {concept_uri(card.id, c.as_): style.material(role_for(c)) for c in card.massing}


def _words(text: object) -> list[str]:
    return [w for w in re.split(r"[^a-z]+", str(text or "").lower()) if w]


def _direction(words: list[str]) -> Vec | None:
    for w in words:
        if w in _DIRECTION_WORDS:
            return _DIRECTION_WORDS[w]
    return None


def _face_named(direction: Vec | None) -> str:
    for name, (n, _, _) in FACES.items():
        if n == direction:
            return name
    return "front"


def _edge(direction: Vec | None, face: str) -> str | None:
    """The face edge (``u-``, ``u+``, ``v-``, ``v+``) lying toward ``direction``."""
    if direction is None:
        return None
    _, u, v = FACES[face]
    for axis, vec in (("u", u), ("v", v)):
        dot = sum(a * b for a, b in zip(vec, direction, strict=True))
        if dot:
            return f"{axis}{'+' if dot > 0 else '-'}"
    return None  # the hinge word names the face itself or its back: no edge to draw


def ink_for(hex_colour: str) -> str:
    """The mark ink that reads on a face of ``hex_colour``: dark on light, light on dark."""
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        rgb = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    except ValueError:
        return INK_DARK
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return INK_DARK if lum > INK_THRESHOLD else INK_LIGHT


def _face_spec(face: str) -> dict[str, Any]:
    n, u, v = FACES[face]
    return {"name": face, "n": list(n), "u": list(u), "v": list(v)}


def layout_marks(card: ConceptCard, style: StyleFile) -> dict[str, Any]:
    """What the page draws from the card's ``layout`` words (review gate B, C16).

    ``door``: on the face ``layout.load`` names (the front when it names none) of the
    ``door`` shapes, else of the body; ``hinge`` is the edge ``layout.door`` names
    (``hinged-left`` → the left edge), ``None`` for a door with no hinge side (sliding,
    lift-off: outline and a centred handle).  ``controls``: on the face ``layout.controls``
    names, of the ``controls`` shapes when the card has them, else of the body (``below``
    → low on the front).  Either is ``None`` when the layout names none, ``none``, or a
    place the words do not say (nothing is drawn rather than a guess).
    """
    from napkin2factory.concepts.massing import concept_uri

    def uris(role: str) -> list[str]:
        return [concept_uri(card.id, c.as_) for c in card.massing if role_for(c) == role]

    def colour(role: str) -> str:
        return str(style.material(role)["color"])

    body = uris("body") or [concept_uri(card.id, c.as_) for c in card.massing]
    marks: dict[str, Any] = {"body": body, "door": None, "controls": None}
    layout = {str(k).lower(): v for k, v in (card.layout or {}).items()}

    door_words = _words(layout.get("door"))
    if door_words and not _NONE_WORDS.intersection(door_words):
        face = _face_named(_direction(_words(layout.get("load"))))
        doors = uris("door")
        hinge_dir = (
            _direction(door_words) if any(w.startswith("hinge") for w in door_words) else None
        )
        marks["door"] = {
            "nodes": doors,
            "face": _face_spec(face),
            "hinge": _edge(hinge_dir, face),
            "ink": ink_for(colour("door" if doors else "body")),
        }

    ctl_words = _words(layout.get("controls"))
    direction = _direction(ctl_words)
    below = bool(_BELOW_WORDS.intersection(ctl_words))
    if ctl_words and not _NONE_WORDS.intersection(ctl_words) and (direction or below):
        if direction == (0, 0, -1):  # "bottom": the owner reads it as low on the front
            direction = None
        face = _face_named(direction) if direction else "front"
        nodes = uris("controls")
        marks["controls"] = {
            "nodes": nodes,
            "face": _face_spec(face),
            "band": "lower" if below else "upper",
            "ink": ink_for(colour("controls" if nodes else "body")),
        }
    return marks


#: Draws :func:`layout_marks` on the loaded model; appended to the viewer's module script, so
#: the three.js names are in scope.  Sizes are shares of the model's largest dimension so the
#: marks read at board thumbnail size (about 360 px wide) whatever the product's scale.
LAYOUT_MARKS_JS = r"""
// ---- layout marks (concepts/screenshot.py): flat ink on the faces, not designed geometry ----
function n2fLayoutMarks(viewer, spec) {
  const byUri = new Map();
  viewer.scene.traverse((o) => {
    const uri = o.userData && o.userData.n2f_kind === 'instance' && o.userData.n2f_uri;
    if (uri) { if (!byUri.has(uri)) byUri.set(uri, []); byUri.get(uri).push(o); }
  });
  const boxOf = (uris) => {
    const box = new Box3();
    for (const u of uris || []) for (const o of byUri.get(u) || []) box.expandByObject(o);
    return box.isEmpty() ? null : box;
  };
  const model = boxOf(Array.from(byUri.keys()));
  if (!model) return 0;
  const size = model.getSize(new Vector3());
  const big = Math.max(size.x, size.y, size.z);
  const W = 0.011 * big, LIFT = 0.004 * big;
  const group = new Group();
  group.name = 'n2f-layout-marks';
  const vec = (a) => new Vector3(a[0], a[1], a[2]);
  const span = (box, a) => {  // [lo, hi] of dot(a, p) over the box
    let lo = 0, hi = 0;
    for (const [i, k] of [[0, 'x'], [1, 'y'], [2, 'z']]) {
      const p = a[i] * box.min[k], q = a[i] * box.max[k];
      lo += Math.min(p, q); hi += Math.max(p, q);
    }
    return [lo, hi];
  };
  function faceOf(box, face) {
    const [s0, s1] = span(box, face.u), [t0, t1] = span(box, face.v);
    return { s0, s1, t0, t1, d: span(box, face.n)[1], face };
  }
  function rect(f, s0, s1, t0, t1, ink, lift) {
    const m = new Mesh(new PlaneGeometry(Math.abs(s1 - s0), Math.abs(t1 - t0)), inkMat(ink));
    place(m, f, (s0 + s1) / 2, (t0 + t1) / 2, lift);
  }
  function disc(f, s, t, r, ink, lift) {
    place(new Mesh(new CircleGeometry(r, 32), inkMat(ink)), f, s, t, lift);
  }
  function place(m, f, s, t, lift) {
    const u = vec(f.face.u), v = vec(f.face.v), n = vec(f.face.n);
    m.quaternion.setFromRotationMatrix(new Matrix4().makeBasis(u, v, n));
    m.position.copy(u.multiplyScalar(s)).add(v.multiplyScalar(t)).add(n.multiplyScalar(f.d + lift));
    m.renderOrder = 10;
    group.add(m);
  }
  const mats = new Map();
  function inkMat(ink) {
    if (!mats.has(ink)) {
      mats.set(ink, new MeshBasicMaterial({
        color: new Color(ink), side: DoubleSide, toneMapped: false,
        polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
      }));
    }
    return mats.get(ink);
  }
  function outline(f, s0, s1, t0, t1, w, ink, lift) {
    rect(f, s0, s1, t0, t0 + w, ink, lift); rect(f, s0, s1, t1 - w, t1, ink, lift);
    rect(f, s0, s0 + w, t0, t1, ink, lift); rect(f, s1 - w, s1, t0, t1, ink, lift);
  }
  const bodyBox = boxOf(spec.body) || model;
  let doorRect = null;
  if (spec.door) {
    const d = spec.door;
    const box = boxOf(d.nodes);
    let f = faceOf(box || bodyBox, d.face);
    if (!box) {  // no door shape: the door is drawn inset on the body's face
      const iu = 0.1 * (f.s1 - f.s0), iv = 0.1 * (f.t1 - f.t0);
      f = Object.assign(f, { s0: f.s0 + iu, s1: f.s1 - iu, t0: f.t0 + iv, t1: f.t1 - iv });
    }
    const w = Math.min(W, 0.045 * Math.min(f.s1 - f.s0, f.t1 - f.t0));
    // drawn inside the door's edge, so a rim of the door separates the ink from the backdrop
    const ins = 1.2 * w;
    const g = { s0: f.s0 + ins, s1: f.s1 - ins, t0: f.t0 + ins, t1: f.t1 - ins };
    const dw = g.s1 - g.s0, dh = g.t1 - g.t0;
    outline(f, g.s0, g.s1, g.t0, g.t1, w, d.ink, LIFT);
    const bar = 3 * w, knuckle = 5 * w;
    const h = d.hinge;
    if (h === 'u-' || h === 'u+') {
      const at = h === 'u-' ? g.s0 : g.s1, sgn = h === 'u-' ? 1 : -1;
      rect(f, at, at + sgn * bar, g.t0, g.t1, d.ink, LIFT * 1.2);
      for (const k of [0.18, 0.82]) {
        const t = g.t0 + k * dh;
        rect(f, at, at + sgn * knuckle, t - 0.05 * dh, t + 0.05 * dh, d.ink, LIFT * 1.3);
      }
      const hs = (h === 'u-' ? g.s1 : g.s0) - sgn * Math.max(0.1 * dw, 4 * w);
      const len = 0.24 * dh, mt = (g.t0 + g.t1) / 2;
      rect(f, hs - w, hs + w, mt - len / 2, mt + len / 2, d.ink, LIFT * 1.4);
    } else if (h === 'v-' || h === 'v+') {
      const at = h === 'v-' ? g.t0 : g.t1, sgn = h === 'v-' ? 1 : -1;
      rect(f, g.s0, g.s1, at, at + sgn * bar, d.ink, LIFT * 1.2);
      for (const k of [0.18, 0.82]) {
        const s = g.s0 + k * dw;
        rect(f, s - 0.05 * dw, s + 0.05 * dw, at, at + sgn * knuckle, d.ink, LIFT * 1.3);
      }
      const ht = (h === 'v-' ? g.t1 : g.t0) - sgn * Math.max(0.1 * dh, 4 * w);
      const len = 0.24 * dw, ms = (g.s0 + g.s1) / 2;
      rect(f, ms - len / 2, ms + len / 2, ht - w, ht + w, d.ink, LIFT * 1.4);
    } else {  // no hinge side in the words: a centred handle
      const len = 0.24 * dw, mt = (g.t0 + g.t1) / 2, ms = (g.s0 + g.s1) / 2;
      rect(f, ms - len / 2, ms + len / 2, mt - w, mt + w, d.ink, LIFT * 1.4);
    }
    doorRect = f;
  }
  if (spec.controls) {
    const c = spec.controls;
    const box = boxOf(c.nodes);
    const f = faceOf(box || bodyBox, c.face);
    const fw = f.s1 - f.s0, fh = f.t1 - f.t0;
    let s0, s1, t0, t1;
    if (box) {  // the controls shape's own face, inset
      s0 = f.s0 + 0.14 * fw; s1 = f.s1 - 0.14 * fw; t0 = f.t0 + 0.14 * fh; t1 = f.t1 - 0.14 * fh;
    } else {  // a panel on the body: a band clear of a door drawn on the same face
      let lo = f.t0, hi = f.t1;
      const same = doorRect && doorRect.face.name === c.face.name;
      if (same && c.band === 'lower' && doorRect.t0 - f.t0 > 0.08 * fh) hi = doorRect.t0;
      if (same && c.band !== 'lower' && f.t1 - doorRect.t1 > 0.08 * fh) lo = doorRect.t1;
      const ph = Math.min(0.18 * fh, 0.8 * (hi - lo)), pw = Math.min(0.34 * fw, 2.2 * ph);
      const mid = c.band === 'lower' ? lo + 0.1 * fh + ph / 2 : hi - 0.1 * fh - ph / 2;
      const tc = Math.min(Math.max(mid, lo + ph / 2), hi - ph / 2);
      s0 = (f.s0 + f.s1) / 2 - pw / 2; s1 = s0 + pw; t0 = tc - ph / 2; t1 = tc + ph / 2;
    }
    const pw = s1 - s0, ph = t1 - t0;
    const w = Math.min(W, 0.07 * Math.min(pw, ph));
    outline(f, s0, s1, t0, t1, w, c.ink, LIFT);
    rect(f, s0 + 0.16 * pw, s1 - 0.16 * pw, t0 + 0.56 * ph, t1 - 0.14 * ph, c.ink, LIFT * 1.2);
    const r = Math.min(0.11 * pw, 0.13 * ph);
    for (const k of [0.33, 0.67]) disc(f, s0 + k * pw, t0 + 0.3 * ph, r, c.ink, LIFT * 1.2);
  }
  viewer.scene.add(group);
  viewer.render();
  return group.children.length;
}
window.n2fMarksReady = window.n2fViewerReady.then(() => {
  const el = document.getElementById('n2f-layout-marks');
  if (!el || !window.n2fViewer) return 0;
  return n2fLayoutMarks(window.n2fViewer, JSON.parse(el.textContent));
});
"""


def styled_page(
    glb: bytes,
    materials: dict[str, dict[str, Any]],
    style: StyleFile,
    marks: dict[str, Any] | None = None,
) -> str:
    """One self-contained page: the inline viewer bundle, the GLB, studio options.

    ``marks`` (from :func:`layout_marks`) adds the door and controls marks; without it the
    page shows the bare silhouette.
    """
    from napkin2factory.report.inline import bundle_viewer, inline_module_script

    options = {
        "background": style.background,
        "materials": materials,
        "lighting": "studio",
        "camera": "iso",
        "transparent": False,
    }
    w, h = VIEWPORT
    marks_tag = ""
    if marks is not None:
        payload = json.dumps(marks, sort_keys=True).replace("<", "\\u003c")
        marks_tag = f'<script type="application/json" id="n2f-layout-marks">{payload}</script>\n'
    return (
        '<!doctype html>\n<html><head><meta charset="utf-8"><title>styled concept</title>'
        f"<style>html,body{{margin:0;padding:0;overflow:hidden;background:{style.background}}}"
        f"#viewer{{width:{w}px;height:{h}px}}</style></head><body>\n"
        f'<div id="viewer" data-n2f-glb="glb-data" '
        f'data-n2f-options="{html.escape(json.dumps(options, sort_keys=True))}"></div>\n'
        f'<script type="text/plain" id="glb-data">{base64.b64encode(glb).decode()}</script>\n'
        f"{marks_tag}{inline_module_script(bundle_viewer() + LAYOUT_MARKS_JS)}\n</body></html>\n"
    )


class ScreenshotSession:
    """One headless Chromium page reused across cards; started on first use.

    Use as a context manager.  When the browser cannot be had, :attr:`unavailable` says why
    and every card falls back to the z-buffer renders; the reason is printed once.
    """

    def __init__(self) -> None:
        self._pw: Any = None
        self._browser: Any = None
        self._page: Any = None
        self._errors: list[str] = []
        self.unavailable: str | None = None
        self._started = False
        self._warned = False

    def __enter__(self) -> ScreenshotSession:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def page(self) -> Any:
        """The shared page, or ``None`` (with :attr:`unavailable` set) when there is none."""
        if not self._started:
            self._started = True
            self._start()
        return self._page

    def _start(self) -> None:
        if os.environ.get(NO_PLAYWRIGHT_ENV) == "1":
            self.unavailable = f"{NO_PLAYWRIGHT_ENV}=1 is set"
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.unavailable = "Playwright is not installed"
            return
        try:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(args=list(CHROMIUM_ARGS))
            w, h = VIEWPORT
            self._page = self._browser.new_page(
                viewport={"width": w, "height": h}, device_scale_factor=1
            )
        except Exception as exc:  # playwright Error, missing browser binary, sandbox refusals
            first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
            self.unavailable = f"Chromium did not start: {first}"
            self.close()
            return
        self._page.on("pageerror", lambda e: self._errors.append(str(e)))
        self._page.on(
            "console", lambda m: self._errors.append(m.text) if m.type == "error" else None
        )

    def take_errors(self) -> list[str]:
        """Page errors since the last call."""
        errors, self._errors = self._errors, []
        return errors

    def warn(self, note: str) -> None:
        """Print ``note`` dim on stderr, once per session."""
        if self._warned:
            return
        self._warned = True
        from rich.console import Console
        from rich.markup import escape

        Console(stderr=True, highlight=False).print(f"[dim]{escape(note)}[/dim]", soft_wrap=True)

    def close(self) -> None:
        """Close the browser (safe to call twice)."""
        for obj, method in ((self._browser, "close"), (self._pw, "stop")):
            if obj is not None:
                try:
                    getattr(obj, method)()
                except Exception:  # noqa: S110 - closing a dead browser is not an error
                    pass
        self._browser = self._pw = self._page = None


def _fallback(out_dir: Path, why: str, session: ScreenshotSession | None) -> ScreenshotResult:
    note = fallback_note(why)
    paths: dict[str, Path] = {}
    for view in VIEWS:
        src = out_dir / f"{view}.png"
        if src.is_file():
            dest = out_dir / f"styled-{view}.png"
            shutil.copyfile(src, dest)
            paths[view] = dest
    if session is not None:
        session.warn(note)
    else:
        from rich.console import Console
        from rich.markup import escape

        Console(stderr=True, highlight=False).print(f"[dim]{escape(note)}[/dim]", soft_wrap=True)
    return ScreenshotResult(paths, "zbuffer-fallback", [note])


def styled_screenshots(
    card: ConceptCard,
    glb_path: Path,
    style: StyleFile,
    out_dir: Path,
    page: ScreenshotSession | None = None,
) -> ScreenshotResult:
    """Write ``styled-iso.png`` and ``styled-front.png`` for one card into ``out_dir``.

    Args:
        card: the concept card (its massing calls give the node URIs and roles).
        glb_path: the card's ``massing.glb``.
        style: the resolved style (the product's, with the card's sketch laid over it).
        out_dir: the card's ``renders/`` folder (the z-buffer renders live there too).
        page: a :class:`ScreenshotSession` to reuse; without one a session is opened and
            closed for this card.

    Returns:
        The written paths, ``method`` (``viewer`` or ``zbuffer-fallback``) and notes.
    """
    if page is None:
        with ScreenshotSession() as session:
            return styled_screenshots(card, glb_path, style, out_dir, session)
    session = page
    out_dir.mkdir(parents=True, exist_ok=True)
    browser_page = session.page()
    if browser_page is None:
        return _fallback(out_dir, session.unavailable or "no browser", session)
    page_file = out_dir / "styled.html"
    page_file.write_text(
        styled_page(
            glb_path.read_bytes(), card_materials(card, style), style, layout_marks(card, style)
        ),
        encoding="utf-8",
    )
    retried = False
    shots: dict[str, bytes] = {}
    try:
        for attempt in (1, 2):
            got = _capture(browser_page, page_file, session)
            if isinstance(got, str):
                if attempt == 1 and transient_gl_error(got):
                    retried = True  # a shader that failed under load compiles on reload (S-108)
                    continue
                return _fallback(out_dir, f"the viewer failed: {got}", session)
            shots = got
            blank = [v for v, png in shots.items() if blank_capture(png)]
            if not blank:
                break
            if attempt == 2:
                why = f"the viewer drew a blank {' and '.join(blank)} picture twice"
                return _fallback(out_dir, why, session)
            retried = True  # headless GL can hand back an empty frame under load (S-093)
    except Exception as exc:  # a crashed page or a timeout: show the correctness renders
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        return _fallback(out_dir, f"the viewer failed: {first}", session)
    paths: dict[str, Path] = {}
    for view, png in shots.items():
        dest = out_dir / f"styled-{view}.png"
        dest.write_bytes(png)
        paths[view] = dest
    return ScreenshotResult(paths, "viewer", [], retried=retried)


def _capture(
    browser_page: Any, page_file: Path, session: ScreenshotSession
) -> dict[str, bytes] | str:
    """Load the page and snapshot every view: PNG bytes by view, or why the viewer failed."""
    session.take_errors()
    browser_page.goto(page_file.resolve().as_uri())
    ok = browser_page.evaluate("window.n2fMarksReady.then(() => !!window.n2fViewer)")
    errors = session.take_errors()
    if not ok or errors:
        return errors[0] if errors else "the viewer did not load"
    shots: dict[str, bytes] = {}
    for view in VIEWS:
        data_url = browser_page.evaluate(
            "(v) => { window.n2fViewer.view(v); return window.n2fViewer.snapshot(); }", view
        )
        shots[view] = base64.b64decode(str(data_url).split(",", 1)[1])
    return shots


def transient_gl_error(message: str) -> bool:
    """True when a page error is one headless GL raises under load and a reload clears."""
    return any(marker in message for marker in TRANSIENT_GL_ERRORS)


def blank_capture(png: bytes) -> bool:
    """True when a snapshot shows nothing but its backdrop (S-093).

    Under load headless GL now and then hands back a frame with no model in it: one flat
    colour (the background, or black or transparent from a lost context).  A styled picture
    always has the model in the middle, so a frame where almost no pixel differs from the
    border's colour is blank.  An image that cannot be read counts as blank.
    """
    import io

    import numpy as np
    from PIL import Image

    try:
        rgb = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=np.int16)
    except Exception:  # a truncated or empty data URL is as good as no picture
        return True
    if rgb.ndim != 3 or rgb.shape[0] < 3 or rgb.shape[1] < 3:
        return True
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    ref = np.median(border, axis=0)
    differs = (np.abs(rgb - ref) > BLANK_TOLERANCE).any(axis=-1)
    return float(differs.mean()) < BLANK_SHARE


__all__ = [
    "FACES",
    "LAYOUT_MARKS_JS",
    "NO_PLAYWRIGHT_ENV",
    "VIEWPORT",
    "VIEWS",
    "ScreenshotResult",
    "ScreenshotSession",
    "blank_capture",
    "transient_gl_error",
    "card_materials",
    "fallback_note",
    "ink_for",
    "layout_marks",
    "styled_page",
    "styled_screenshots",
]
