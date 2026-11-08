// napkin2factory report viewer.  Runs inside the single inline module script that the
// report builder emits (see inline.py); `THREE` names, GLTFLoader and OrbitControls are
// already in scope.  Everything it needs is read from the DOM, nothing is fetched.
//
// Public surface (window.n2fViewer):
//   nodes()                -> array of part URIs present in the scene
//   instanceCount(uri)     -> number of scene instances for a part URI
//   select(uri)            -> highlight one part, fire 'n2f:select' on the container
//   highlight(uris, color) -> colour a set of parts (changed-part highlighting)
//   clearHighlights()      -> undo highlight() only; selection, ghosting and explode stay (build player)
//   frame(uri)             -> orbit target to part's centre and fit distance along current view
//   ghost(uris)            -> make every part not in uris transparent; ghost([]) restores all
//   screenPoint(uri)       -> {x, y} client pixels of part's projected bounding-box centre
//   explode(factor)        -> each unit along its own n2f_explode direction; one axis when the GLB has none
//   explodeInfo()          -> {[nodeName]: {dir, distance, source}} for top-level units with n2f_explode
//   section(axisOrOn, off) -> clip high side along 'x'|'y'|'z' at 0..1 offset (true/false toggles)
//   sectionState()         -> {on, axis, offset} current section cut state
//   fit()                  -> frame the whole model from the default isometric direction
//   reset()                -> clear selection, highlights, ghosting and explode
//   render()               -> queue a redraw (after mutating scene/camera directly)
//   ready                  -> Promise resolving after the first frame
//   applyMaterials(map)    -> {uri: {color: '#hex', metallic, roughness}} per part (style.yaml)
//   view(name)             -> frame the model from a preset camera: 'iso' | 'front'
//   snapshot()             -> PNG data URL of the current view
//   settled                -> Promise resolving to 'ok' or 'unavailable' once the browser's WebGL
//                             has either drawn the scene or been given up on (S-232)
//   shaderRetries          -> how many times a failed shader was recompiled
//   glState                -> 'pending' | 'ok' | 'unavailable' (also data-n2f-webgl on the container)
//
// Options beyond the report's defaults (all optional; the report passes none of them, so its
// behaviour is unchanged): background ('#hex' or number), materials (as applyMaterials,
// applied after load), lighting: 'studio' (a fixed three-point rig, a soft environment for
// metals and a contact shadow), camera: 'iso' | 'front' (applied after load instead of the
// default fit), transparent (no background).  An element may carry them as JSON in
// data-n2f-options.
//
// Rendering is on demand: a frame is drawn only when something changed (orbit/zoom, an API
// call, a resize) and only while the viewer is on screen and the tab is visible.  An always-on
// requestAnimationFrame loop kept the GPU and main thread busy for the whole page lifetime.

// The studio rig (lighting: 'studio'): key, fill and rim directional lights plus a soft
// hemisphere, a blurred procedural "softbox room" as the environment so metals and paints
// have something to reflect, neutral tone mapping (keeps palette hues), and a contact shadow
// on an invisible floor.  place(box) aims the shadow at the loaded model.
function studioRig(scene, renderer) {
  // Tone curve: linear below 0.6, then the Khronos PBR Neutral highlight roll-off (so
  // off-white bodies keep their faces), but without Neutral's toe, which crushes dark
  // palettes (charcoal turns blue-black).  The palette hue is the point of the picture.
  ShaderChunk.tonemapping_pars_fragment = ShaderChunk.tonemapping_pars_fragment.replace(
    'vec3 CustomToneMapping( vec3 color ) { return color; }',
    `vec3 CustomToneMapping( vec3 color ) {
      const float StartCompression = 0.6;
      const float Desaturation = 0.15;
      color *= toneMappingExposure;
      float peak = max( color.r, max( color.g, color.b ) );
      if ( peak < StartCompression ) return color;
      float d = 1. - StartCompression;
      float newPeak = 1. - d * d / ( peak + d - StartCompression );
      color *= newPeak / peak;
      float g = 1. - 1. / ( Desaturation * ( peak - newPeak ) + 1. );
      return mix( color, vec3( newPeak ), g );
    }`);
  renderer.toneMapping = CustomToneMapping;
  renderer.toneMappingExposure = 0.8;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = PCFShadowMap;  // honours shadow.radius: a soft contact shadow
  // Rig intensities are in classic units (key 1.0, fill 0.5, rim 0.6, sky 0.6); three.js
  // lights are physically based since r155, so they are scaled by PI to keep that meaning.
  const sky = new HemisphereLight(0xffffff, 0x8c8c8c, 0.6 * Math.PI);
  sky.position.set(0, 0, 1);  // Z is up in the model
  scene.add(sky);
  const lights = [
    [1.0, new Vector3(1, -1, 2)],
    [0.5, new Vector3(-1.5, -0.5, 1)],
    [0.6, new Vector3(0, 1.5, 1.5)],
  ].map(([intensity, dir]) => {
    const light = new DirectionalLight(0xffffff, intensity * Math.PI);
    light.position.copy(dir);
    scene.add(light);
    scene.add(light.target);
    return [light, dir];
  });
  const key = lights[0][0];
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.radius = 8;

  const room = new Scene();
  const box = (color, pos, scale, side) => {
    const m = new Mesh(new BoxGeometry(1, 1, 1), new MeshBasicMaterial({ color, side: side || FrontSide }));
    m.position.set(pos[0], pos[1], pos[2]);
    m.scale.set(scale[0], scale[1], scale[2]);
    room.add(m);
  };
  // The room is lopsided on purpose: the key light sits almost behind an iso camera, so
  // the environment carries the modelling: a big softbox front-left, a dim right side.
  box(new Color(0.32, 0.32, 0.32), [0, 0, 0], [20, 20, 20], BackSide);    // walls
  box(new Color(0.12, 0.12, 0.12), [0, 0, -9.8], [20, 20, 0.2]);          // floor
  box(new Color(3.5, 3.5, 3.5), [0, 0, 9.6], [9, 9, 0.2]);                // overhead softbox
  box(new Color(5, 5, 5), [-4, -9.6, 4], [10, 0.2, 7]);                   // front-left softbox
  box(new Color(2.5, 2.5, 2.5), [-9.6, -2, 3], [0.2, 8, 6]);              // left softbox
  box(new Color(1.5, 1.5, 1.5), [0, 9.6, 5], [8, 0.2, 4]);                // rim softbox
  const pmrem = new PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(room, 0.04).texture;
  scene.environmentIntensity = 0.6;
  pmrem.dispose();

  const floor = new Mesh(new PlaneGeometry(1, 1), new ShadowMaterial({ opacity: 0.14 }));
  floor.receiveShadow = true;
  floor.visible = false;
  scene.add(floor);
  return {
    place(bbox) {
      const center = bbox.getCenter(new Vector3());
      const size = bbox.getSize(new Vector3());
      const radius = Math.max(size.length() / 2, 1);
      for (const [light, dir] of lights) {
        light.target.position.copy(center);
        light.position.copy(center).addScaledVector(dir.clone().normalize(), radius * 3);
      }
      const cam = key.shadow.camera;
      cam.left = -radius * 1.6; cam.right = radius * 1.6;
      cam.top = radius * 1.6; cam.bottom = -radius * 1.6;
      cam.near = radius * 0.5; cam.far = radius * 6;
      cam.updateProjectionMatrix();
      key.shadow.bias = -0.0001;
      key.shadow.normalBias = radius * 0.004;  // no acne on the faces the key light hits
      floor.scale.set(radius * 8, radius * 8, 1);
      floor.position.set(center.x, center.y, bbox.min.z - radius * 0.002);
      floor.visible = true;
    },
  };
}

function n2fCreateViewer(container, options) {
  const opts = Object.assign({ background: 0xf4f4f2, explodeAxis: 'z', explodeSpacing: 80 }, options || {});
  const width = container.clientWidth || 800;
  const height = container.clientHeight || 500;
  const scene = new Scene();
  scene.background = opts.transparent ? null : new Color(opts.background);
  const camera = new PerspectiveCamera(40, width / height, 0.1, 100000);
  // No preserveDrawingBuffer: snapshot() renders and reads back in the same task instead.
  const renderer = new WebGLRenderer(opts.transparent ? { antialias: true, alpha: true } : { antialias: true });
  renderer.localClippingEnabled = true;
  // A shader that fails to link (software WebGL under load does this, with an empty log) is not
  // a page error: the frame loop below recompiles a few times, then shows a notice (S-232).
  let shaderFailed = false;
  renderer.debug.onShaderError = () => { shaderFailed = true; };
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(width, height);
  container.appendChild(renderer.domElement);
  const studio = opts.lighting === 'studio' ? studioRig(scene, renderer) : null;
  if (!studio) {
    scene.add(new HemisphereLight(0xffffff, 0x888888, 1.2));
    const key = new DirectionalLight(0xffffff, 1.0);
    key.position.set(1, -1, 2);
    scene.add(key);
  }
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  // The wheel scrolls the page until the viewer is clicked; otherwise scrolling past the model
  // zooms it instead (and renders a frame per wheel tick).  A click elsewhere hands the wheel back.
  controls.enableZoom = false;
  container.addEventListener('pointerdown', () => { controls.enableZoom = true; container.classList.add('n2f-active'); });
  document.addEventListener('pointerdown', (ev) => {
    if (!container.contains(ev.target)) { controls.enableZoom = false; container.classList.remove('n2f-active'); }
  });

  let firstFrame = null;
  let pending = false;   // a frame is queued
  let dirty = true;      // something changed while we were not allowed to draw
  let onScreen = true;   // until the IntersectionObserver says otherwise
  function canDraw() { return onScreen && !document.hidden; }
  // The first frame, and every frame until the loaded model has been drawn once, run even off
  // screen so that `ready` and `settled` always resolve.
  let drawModelOnce = false;
  function mustDraw() { return firstFrame || drawModelOnce; }
  function frame() {
    pending = false;
    if (!canDraw() && !mustDraw()) { dirty = true; return; }
    dirty = false;
    // With damping, update() keeps returning true (and firing 'change') until the motion settles.
    if (controls.update()) requestRender();
    renderer.render(scene, camera);
    if (root) drawModelOnce = false;
    checkShaders();
    if (firstFrame) { firstFrame(api); firstFrame = null; }
  }
  // After a frame: no shader failure settles the viewer as 'ok'; a failure disposes every
  // material (so three.js compiles it afresh) and draws again, up to SHADER_RETRIES times; then
  // the canvas gives way to a plain notice.  The page's own lists and tables carry the content.
  const SHADER_RETRIES = 3;
  let shaderRetries = 0;
  function checkShaders() {
    const lost = renderer.getContext().isContextLost();  // the driver gave up on the context
    if (!shaderFailed && !lost) { if (root) settle('ok'); return; }
    shaderFailed = false;
    if (!lost && shaderRetries < SHADER_RETRIES) {
      shaderRetries++;
      api.shaderRetries = shaderRetries;
      scene.traverse((o) => { if (o.isMesh) { o.material.dispose(); o.material.needsUpdate = true; } });
      drawModelOnce = true;
      requestRender();
      return;
    }
    renderer.domElement.style.display = 'none';
    const note = document.createElement('p');
    note.className = 'n2f-fallback';
    note.textContent = container.getAttribute('data-n2f-fallback') ||
      'The 3D view could not start in this browser.';
    note.style.cssText = 'margin:0;padding:1rem;color:#6b6a66;font:14px/1.4 sans-serif';
    container.appendChild(note);
    console.warn('n2f viewer: 3D view unavailable (WebGL failed to link a shader); showing a notice instead.');
    settle('unavailable');
  }
  let settleState = null;
  function settle(state) {
    if (settleState) return;
    settleState = state;
    api.glState = state;
    container.setAttribute('data-n2f-webgl', state);
    if (state === 'unavailable') ['role', 'aria-label', 'tabindex'].forEach((n) => container.removeAttribute(n));  // the fallback notice must stay readable (S-325)
    resolveSettled(state);
  }
  let resolveSettled = null;
  function requestRender() {
    if (pending) return;
    if (!canDraw() && !mustDraw()) { dirty = true; return; }
    pending = true;
    requestAnimationFrame(frame);
  }
  controls.addEventListener('change', requestRender);
  if ('IntersectionObserver' in window) {
    new IntersectionObserver((entries) => {
      onScreen = entries[entries.length - 1].isIntersecting;
      if (onScreen && dirty) requestRender();
    }).observe(container);
  }
  document.addEventListener('visibilitychange', () => { if (canDraw() && dirty) requestRender(); });

  const partNodes = new Map();   // uri -> [Object3D]
  const baseMaterials = new Map(); // mesh.uuid -> material
  const basePositions = new Map(); // object.uuid -> Vector3
  const ghosted = new Set();     // ghosted part URIs (skipped by raycast)
  const secState = { on: false, axis: 'z', offset: 0.5 };
  let root = null;
  let selected = null;

  // GLTFLoader sanitizes node names (strips '/', ':', '.'), so URIs ride in extras/userData.
  function uriOf(obj) {
    let o = obj;
    while (o) {
      if (o.userData && o.userData.n2f_kind === 'instance' && o.userData.n2f_uri) return o.userData.n2f_uri;
      o = o.parent;
    }
    return null;
  }

  function registerScene(gltfScene) {
    root = gltfScene;
    drawModelOnce = true;
    scene.add(root);
    root.traverse((o) => {
      if (o.userData && o.userData.n2f_kind === 'instance' && o.userData.n2f_uri) {
        const uri = o.userData.n2f_uri;
        if (!partNodes.has(uri)) partNodes.set(uri, []);
        partNodes.get(uri).push(o);
      }
      if (o.isMesh) {
        baseMaterials.set(o.uuid, o.material);
        o.material = o.material.clone();
        o.material.side = DoubleSide;
      }
    });
    for (const child of root.children) basePositions.set(child.uuid, child.position.clone());
    if (opts.materials) applyMaterials(opts.materials);
    if (studio) studio.place(new Box3().setFromObject(root));
    if (opts.camera) view(opts.camera); else fit();
    requestRender();
  }

  function applyMaterials(map) {
    for (const [uri, m] of Object.entries(map || {})) {
      for (const node of partNodes.get(uri) || []) {
        node.traverse((o) => {
          if (!o.isMesh) return;
          if (m.color) o.material.color.set(m.color);
          if (typeof m.metallic === 'number') o.material.metalness = m.metallic;
          if (typeof m.roughness === 'number') o.material.roughness = m.roughness;
          o.material.needsUpdate = true;
          if (studio) { o.castShadow = true; o.receiveShadow = true; }
          baseMaterials.set(o.uuid, o.material.clone());  // reset() returns to the styled look
        });
      }
    }
    requestRender();
  }

  // Preset cameras: the model's bounding box is fitted to the frame with a margin.
  const VIEWS = { iso: new Vector3(1.4, -1.6, 1.1), front: new Vector3(0, -1, 0.06) };
  function view(name) {
    const dir = (VIEWS[name] || VIEWS.iso).clone().normalize();
    camera.fov = 26;  // a longer lens than the orbit view: product shots, little keystoning
    camera.updateProjectionMatrix();
    const box = new Box3().setFromObject(root || scene);
    const center = box.getCenter(new Vector3());
    const size = box.getSize(new Vector3());
    camera.up.set(0, 0, 1);
    const right = new Vector3().crossVectors(dir, camera.up).normalize().negate();
    const up = new Vector3().crossVectors(right, dir).normalize().negate();
    const margin = 1.15;
    const ty = Math.tan((camera.fov * Math.PI) / 360) / margin;
    const tx = ty * camera.aspect;
    let dist = 0;
    for (const sx of [-0.5, 0.5]) for (const sy of [-0.5, 0.5]) for (const sz of [-0.5, 0.5]) {
      const c = new Vector3(size.x * sx, size.y * sy, size.z * sz);
      const toward = c.dot(dir);
      dist = Math.max(dist, toward + Math.abs(c.dot(right)) / tx, toward + Math.abs(c.dot(up)) / ty);
    }
    const radius = Math.max(size.length() / 2, 1);
    camera.position.copy(center).addScaledVector(dir, dist);
    camera.near = Math.max(dist - radius * 2, radius / 100);
    camera.far = dist + radius * 4;
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls.update();
    camera.updateMatrixWorld();
    requestRender();
  }

  function fit() {
    const box = new Box3().setFromObject(root || scene);
    const size = box.getSize(new Vector3());
    const center = box.getCenter(new Vector3());
    const radius = Math.max(size.x, size.y, size.z, 1);
    camera.up.set(0, 0, 1);
    // a frame taller than wide (a phone's full-screen pane, S-324) would cut the sides: stand back by the shortfall
    const back = camera.aspect < 0.75 ? 0.75 / camera.aspect : 1;
    camera.position.copy(center).add(new Vector3(radius * 1.4, -radius * 1.6, radius * 1.1).multiplyScalar(back));
    camera.near = radius / 100;
    camera.far = radius * 100;
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls._sphericalDelta.set(0, 0, 0);
    controls._panOffset.set(0, 0, 0);
    controls.update();
    camera.updateMatrixWorld();
    requestRender();
  }

  // Bounding box across all instance nodes of one part URI (V3).
  function partBox(uri) {
    const nodes = partNodes.get(uri);
    if (!nodes || !nodes.length) return null;
    const box = new Box3();
    for (const node of nodes) box.expandByObject(node);
    return box.isEmpty() ? null : box;
  }

  // Frame one part by moving the orbit target to its centre along the current viewing direction (V3).
  function framePart(uri) {
    const box = partBox(uri);
    if (!box) return;
    const size = box.getSize(new Vector3());
    const center = box.getCenter(new Vector3());
    const radius = Math.max(size.x, size.y, size.z, 1);
    const dir = camera.position.clone().sub(controls.target);
    if (dir.lengthSq() === 0) dir.set(1.4, -1.6, 1.1);
    dir.normalize();
    camera.position.copy(center).addScaledVector(dir, radius * 2.4);
    camera.near = radius / 100;
    camera.far = radius * 100;
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls._sphericalDelta.set(0, 0, 0);
    controls._panOffset.set(0, 0, 0);
    controls.update();
    camera.updateMatrixWorld();
    requestRender();
  }

  // Isolate listed parts by turning every other part translucent; empty/null restores all (V3).
  function ghost(uris) {
    ghosted.clear();
    const keep = uris && uris.length ? new Set(uris) : null;
    for (const [uri, nodes] of partNodes.entries()) {
      const isGhost = keep !== null && !keep.has(uri);
      if (isGhost) ghosted.add(uri);
      for (const node of nodes) {
        node.traverse((o) => {
          if (!o.isMesh) return;
          const base = baseMaterials.get(o.uuid);
          if (isGhost) {
            o.material.transparent = true;
            o.material.opacity = 0.12;
            o.material.depthWrite = false;
          } else {
            o.material.transparent = base ? Boolean(base.transparent) : false;
            o.material.opacity = base && typeof base.opacity === 'number' ? base.opacity : 1;
            o.material.depthWrite = base && typeof base.depthWrite === 'boolean' ? base.depthWrite : true;
          }
          o.material.needsUpdate = true;
        });
      }
    }
    requestRender();
  }

  // Project a part's bounding-box centre to client (page) pixels for interaction tests (V3).
  function screenPoint(uri) {
    const box = partBox(uri);
    if (!box) return null;
    camera.updateMatrixWorld();
    const p = box.getCenter(new Vector3()).project(camera);
    const rect = renderer.domElement.getBoundingClientRect();
    return {
      x: rect.left + ((p.x + 1) / 2) * rect.width,
      y: rect.top + ((1 - p.y) / 2) * rect.height,
    };
  }

  function setColor(uri, hex, emissive) {
    for (const node of partNodes.get(uri) || []) {
      node.traverse((o) => {
        if (o.isMesh) {
          if (hex === null) {
            const base = baseMaterials.get(o.uuid);
            o.material.color.copy(base.color);
            o.material.emissive && o.material.emissive.setHex(0x000000);
          } else {
            o.material.color.setHex(hex);
            if (o.material.emissive) o.material.emissive.setHex(emissive || 0x000000);
          }
        }
      });
    }
    requestRender();
  }

  const highlighted = new Set();  // uris coloured by highlight(), for clearHighlights()
  const api = {
    scene, camera, renderer, controls,
    nodes() { return Array.from(partNodes.keys()).sort(); },
    instanceCount(uri) { return (partNodes.get(uri) || []).length; },
    select(uri) {
      if (selected) setColor(selected, null);
      selected = uri;
      if (uri) setColor(uri, 0xffa500, 0x331a00);
      container.dispatchEvent(new CustomEvent('n2f:select', { detail: { uri } }));
    },
    highlight(uris, hex) {
      for (const uri of uris) { highlighted.add(uri); setColor(uri, hex === undefined ? 0x2e8b57 : hex, 0x002200); }
    },
    clearHighlights() {
      for (const uri of highlighted) if (uri !== selected) setColor(uri, null);
      highlighted.clear();
    },
    reset() {
      highlighted.clear();
      for (const uri of partNodes.keys()) setColor(uri, null);
      selected = null;
      ghost([]);
      api.explode(0);
    },
    // Move each top-level unit along its n2f_explode direction; fall back to one axis for older GLBs (B-0304).
    explode(factor) {
      if (!root) return;
      const hasExtra = root.children.some((c) => c.userData && c.userData.n2f_explode);
      if (hasExtra) {
        for (const child of root.children) {
          const base = basePositions.get(child.uuid);
          child.position.copy(base);
          const ex = child.userData && child.userData.n2f_explode;
          if (ex && factor) {
            const d = ex.dir || [0, 0, 0];
            const s = (ex.distance || 0) * factor;
            child.position.x = base.x + (d[0] || 0) * s;
            child.position.y = base.y + (d[1] || 0) * s;
            child.position.z = base.z + (d[2] || 0) * s;
          }
        }
      } else {
        const axis = opts.explodeAxis;
        const children = root.children.slice();
        children.sort((a, b) => basePositions.get(a.uuid)[axis] - basePositions.get(b.uuid)[axis]);
        children.forEach((child, i) => {
          const base = basePositions.get(child.uuid);
          child.position.copy(base);
          child.position[axis] = base[axis] + factor * opts.explodeSpacing * i;
        });
      }
      requestRender();
    },
    explodeInfo() {
      const out = {};
      if (!root) return out;
      for (const child of root.children) {
        const ex = child.userData && child.userData.n2f_explode;
        if (ex) {
          const name = (child.userData && (child.userData.n2f_node || child.userData.n2f_uri)) || child.name;
          out[name] = {
            dir: Array.isArray(ex.dir) ? ex.dir.slice() : [0, 0, 0],
            distance: typeof ex.distance === 'number' ? ex.distance : 0,
            source: ex.source || '',
          };
        }
      }
      return out;
    },
    frame: framePart,
    ghost,
    screenPoint,
    fit,
    view,
    applyMaterials,
    // Section cut on x, y or z at 0..1 offset (keeps low side); true/false toggles last cut (V3).
    section(axisOrOn, offset) {
      if (!axisOrOn) {
        secState.on = false;
        renderer.clippingPlanes = [];
        requestRender();
        return;
      }
      if (axisOrOn === 'x' || axisOrOn === 'y' || axisOrOn === 'z') {
        secState.axis = axisOrOn;
        secState.offset = typeof offset === 'number' && !Number.isNaN(offset)
          ? Math.max(0, Math.min(1, offset))
          : 0.5;
      }
      secState.on = true;
      const box = new Box3().setFromObject(root || scene);
      const a = secState.axis;
      const cut = box.min[a] + (box.max[a] - box.min[a]) * secState.offset;
      const normal = new Vector3(a === 'x' ? -1 : 0, a === 'y' ? -1 : 0, a === 'z' ? -1 : 0);
      renderer.clippingPlanes = [new Plane(normal, cut)];
      requestRender();
    },
    sectionState() { return { on: secState.on, axis: secState.axis, offset: secState.offset }; },
    render: requestRender,
    snapshot() { renderer.render(scene, camera); return renderer.domElement.toDataURL('image/png'); },
  };

  const raycaster = new Raycaster();
  // Raycast from client coordinates, skipping ghosted (transparent) parts (V3).
  function pickUri(ev) {
    camera.updateMatrixWorld();
    const rect = renderer.domElement.getBoundingClientRect();
    const ndc = new Vector2(((ev.clientX - rect.left) / rect.width) * 2 - 1, -((ev.clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    const hits = raycaster.intersectObjects(scene.children, true);
    for (const h of hits) {
      const uri = uriOf(h.object);
      if (uri && !ghosted.has(uri)) return uri;
    }
    return null;
  }
  // Pick only on a click (< 5 px pointer travel since down) so orbit drags never change selection (V3).
  let downPos = null;
  renderer.domElement.addEventListener('pointerdown', (ev) => {
    downPos = { x: ev.clientX, y: ev.clientY, t: ev.timeStamp };
  });
  renderer.domElement.addEventListener('pointerup', (ev) => {
    if (!downPos) return;
    const moved = Math.hypot(ev.clientX - downPos.x, ev.clientY - downPos.y);
    downPos = null;
    if (moved >= 5) return;
    const uri = pickUri(ev);
    if (!uri) ghost([]);
    api.select(uri);
  });
  // Double-click isolates and frames the clicked part; empty space does nothing (V3).
  renderer.domElement.addEventListener('dblclick', (ev) => {
    const uri = pickUri(ev);
    if (!uri) return;
    api.select(uri);
    framePart(uri);
    ghost([uri]);
  });

  // The first frame is drawn even off screen so that `ready` always resolves.
  api.ready = new Promise((resolve) => { firstFrame = resolve; });
  api.glState = 'pending';
  api.shaderRetries = 0;
  api.settled = new Promise((resolve) => { resolveSettled = resolve; });
  requestRender();

  api.loadBase64 = function (b64) {
    return new Promise((resolve, reject) => {
      const bin = atob(b64);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      new GLTFLoader().parse(bytes.buffer, '', (gltf) => { registerScene(gltf.scene); resolve(api); }, reject);
    });
  };
  window.addEventListener('resize', () => {
    const w = container.clientWidth || width, h = container.clientHeight || height;
    camera.aspect = w / h; camera.updateProjectionMatrix(); renderer.setSize(w, h);
    requestRender();
  });
  return api;
}

// Bootstrap: every element with data-n2f-glb holds a base64 GLB; mount a viewer on it.
window.n2fViewers = {};
window.n2fViewerReady = (async () => {
  for (const el of document.querySelectorAll('[data-n2f-glb]')) {
    const dataEl = document.getElementById(el.getAttribute('data-n2f-glb'));
    if (!dataEl) continue;
    let extra = {};
    if (el.hasAttribute('data-n2f-options')) {
      try { extra = JSON.parse(el.getAttribute('data-n2f-options')); } catch (err) { console.error('n2f viewer options', err); }
    }
    const viewer = n2fCreateViewer(el, Object.assign({
      explodeAxis: el.getAttribute('data-explode-axis') || 'z',
      explodeSpacing: parseFloat(el.getAttribute('data-explode-spacing') || '80'),
    }, extra));
    try {
      await viewer.loadBase64(dataEl.textContent.trim());
      await viewer.ready;
      await viewer.settled;
      window.n2fViewers[el.id || 'default'] = viewer;
      el.dispatchEvent(new CustomEvent('n2f:loaded', { detail: { nodes: viewer.nodes() } }));
    } catch (err) {
      console.error('n2f viewer failed', err);
      el.setAttribute('data-n2f-error', String(err));
    }
  }
  window.n2fViewer = window.n2fViewers.default || Object.values(window.n2fViewers)[0] || null;
  // Wire the section axis/offset and show-all controls on the default viewer (V3).
  if (window.n2fViewer) {
    const v = window.n2fViewer;
    const secCheck = document.getElementById('section');
    const secAxis = document.getElementById('section-axis');
    const secOff = document.getElementById('section-offset');
    const showAll = document.getElementById('show-all');
    const applySec = () => {
      const axis = secAxis ? secAxis.value : 'z';
      const off = secOff ? parseFloat(secOff.value) : 0.5;
      if (secCheck) secCheck.checked = true;
      v.section(axis, off);
    };
    if (secAxis) secAxis.addEventListener('change', applySec);
    if (secOff) {
      secOff.addEventListener('input', applySec);
      secOff.addEventListener('change', applySec);
    }
    if (showAll) showAll.addEventListener('click', () => { v.select(null); v.ghost([]); v.fit(); });
  }
  return window.n2fViewers;
})();
