# Decisions log (system build-out)

Decisions beyond `GRAND_PLAN.md` §2, with rationale. `[revisit]` marks ones the owner may
want to reopen; `[verify]` marks engineering numbers taken from published sources that a
human should confirm before relying on them.

## S-001 — Host platform differs from the plan (2026-10-30)
The build runs on an Intel macOS host (Darwin 25.6, x86_64, 16 cores, 32 GB), not the
sandboxed Linux the plan assumed. Nothing in the plan is Linux-specific; CI (`ci.yml`)
runs both `ubuntu-latest` and `macos-latest` so the Linux definition of done is exercised
there. `[revisit]` The owner should run `make check-full` once on Linux before relying on
the DoD timing numbers.

## S-002 — OCP wheel and render path pairing (D2 / D12) (2026-10-30)
`uv sync` with `build123d>=0.12,<0.13` on Python 3.13.18 resolves, through build123d's
`cadquery-ocp-proxy`, to **`cadquery-ocp-novtk 7.9.3.1.1`** (no VTK). Therefore the
VTK offscreen render path is unavailable and the render path is the **numpy z-buffer
rasterizer** over the OCCT tessellation (`geometry/render.py`): orthographic front/top/right,
an isometric view, and a crude section (triangles above a Z plane dropped). Flat shading,
one hash-derived colour per part. `tests/smoke/test_toolchain.py` asserts VTK is absent so a
future wheel change forces this entry to be revisited. Python 3.13 pinned; 3.14 not tried.

## S-003 — three.js pinned at r170 (0.170.0), vendored, inlined (D13) (2026-10-30)
One download from jsdelivr of four files into `src/napkin2factory/report/vendor/three/`:

| file | sha256 |
|---|---|
| three.module.js | ce1fa418de16a19495a9f72495580e3015d7745c296d3ce0485897f902ddedfb |
| GLTFLoader.js | 45139faddd5aaf48ed2d62203d976e5cbd703db1a592de40527f9f6cf58abd44 |
| OrbitControls.js | 80efaadea4f8a636a65fb0bd08bfef62f3d93a0bb94e2e7500f23176c5c07f4e |
| BufferGeometryUtils.js | c25b7930e570e9ec56173cd3b866ec8d2e10016630db3937efb439daf1cedbf6 |

`report/inline.py` strips `import`/`export` statements, wraps each addon in a block scope with
its exports re-bound through a holder object, and concatenates core + addons + `viewer.js`
into one inline `<script type="module">`. Proven from `file://` with Playwright Chromium
(`tests/smoke/test_viewer_skeleton.py`): zero console errors, the single cube mesh reports
two instances.

## S-004 — In-house GLB writer; URIs carried in glTF `extras` (2026-10-30)
build123d's `export_gltf` propagates labels into node and mesh names but writes **no
materials** and **duplicates meshes per instance**. D13 requires one mesh per part URI,
instanced per occurrence, with material names equal to URIs, so `geometry/glb.py` writes
GLB directly through pygltflib. three.js's `GLTFLoader` sanitizes node names (strips `/`,
`:`, `.`), so each node and mesh also carries `extras: {n2f_uri, n2f_node, n2f_kind}`, which
the loader exposes untouched as `userData`; the viewer keys on that, not on `name`.

## S-005 — selectolax lexbor backend (2026-10-30)
selectolax 1.0 removed the Modest backend; all HTML parsing in tests uses
`selectolax.lexbor.LexborHTMLParser`.

## S-006 — `rich` and `packaging` added as runtime dependencies (2026-10-30)
`rich` for tables and persona-vocabulary output in the CLI (typer already depends on it);
`packaging` to evaluate the product repo's `system: ">=0.1,<0.2"` pin.
