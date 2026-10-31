// napkin2factory report viewer.  Runs inside the single inline module script that the
// report builder emits (see inline.py); `THREE` names, GLTFLoader and OrbitControls are
// already in scope.  Everything it needs is read from the DOM, nothing is fetched.
//
// Public surface (window.n2fViewer):
//   nodes()                -> array of part URIs present in the scene
//   select(uri)            -> highlight one part, fire 'n2f:select' on the container
//   highlight(uris, color) -> colour a set of parts (changed-part highlighting)
//   explode(factor)        -> move top-level instances along the exploded axis
//   render()               -> queue a redraw (after mutating scene/camera directly)
//   ready                  -> Promise resolving after the first frame
//
// Rendering is on demand: a frame is drawn only when something changed (orbit/zoom, an API
// call, a resize) and only while the viewer is on screen and the tab is visible.  An always-on
// requestAnimationFrame loop kept the GPU and main thread busy for the whole page lifetime.

function n2fCreateViewer(container, options) {
  const opts = Object.assign({ background: 0xf4f4f2, explodeAxis: 'z', explodeSpacing: 80 }, options || {});
  const width = container.clientWidth || 800;
  const height = container.clientHeight || 500;
  const scene = new Scene();
  scene.background = new Color(opts.background);
  const camera = new PerspectiveCamera(40, width / height, 0.1, 100000);
  // No preserveDrawingBuffer: snapshot() renders and reads back in the same task instead.
  const renderer = new WebGLRenderer({ antialias: true });
  renderer.localClippingEnabled = true;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(width, height);
  container.appendChild(renderer.domElement);
  scene.add(new HemisphereLight(0xffffff, 0x888888, 1.2));
  const key = new DirectionalLight(0xffffff, 1.0);
  key.position.set(1, -1, 2);
  scene.add(key);
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
  function frame() {
    pending = false;
    if (!canDraw() && !firstFrame) { dirty = true; return; }
    dirty = false;
    // With damping, update() keeps returning true (and firing 'change') until the motion settles.
    if (controls.update()) requestRender();
    renderer.render(scene, camera);
    if (firstFrame) { firstFrame(api); firstFrame = null; }
  }
  function requestRender() {
    if (pending) return;
    if (!canDraw() && !firstFrame) { dirty = true; return; }
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
    fit();
    requestRender();
  }

  function fit() {
    const box = new Box3().setFromObject(root || scene);
    const size = box.getSize(new Vector3());
    const center = box.getCenter(new Vector3());
    const radius = Math.max(size.x, size.y, size.z, 1);
    camera.up.set(0, 0, 1);
    camera.position.copy(center).add(new Vector3(radius * 1.4, -radius * 1.6, radius * 1.1));
    camera.near = radius / 100;
    camera.far = radius * 100;
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls.update();
    requestRender();
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
      for (const uri of uris) setColor(uri, hex === undefined ? 0x2e8b57 : hex, 0x002200);
    },
    reset() {
      for (const uri of partNodes.keys()) setColor(uri, null);
      selected = null;
      api.explode(0);
    },
    explode(factor) {
      if (!root) return;
      const axis = opts.explodeAxis;
      const children = root.children.slice();
      children.sort((a, b) => basePositions.get(a.uuid)[axis] - basePositions.get(b.uuid)[axis]);
      children.forEach((child, i) => {
        const base = basePositions.get(child.uuid);
        child.position.copy(base);
        child.position[axis] = base[axis] + factor * opts.explodeSpacing * i;
      });
      requestRender();
    },
    fit,
    // Section: clip everything above the model's mid-height (a global clipping plane).
    section(on) {
      if (!on) { renderer.clippingPlanes = []; requestRender(); return; }
      const box = new Box3().setFromObject(root || scene);
      const midZ = (box.min.z + box.max.z) / 2;
      renderer.clippingPlanes = [new Plane(new Vector3(0, 0, -1), midZ)];
      requestRender();
    },
    render: requestRender,
    snapshot() { renderer.render(scene, camera); return renderer.domElement.toDataURL('image/png'); },
  };

  const raycaster = new Raycaster();
  renderer.domElement.addEventListener('pointerdown', (ev) => {
    const rect = renderer.domElement.getBoundingClientRect();
    const ndc = new Vector2(((ev.clientX - rect.left) / rect.width) * 2 - 1, -((ev.clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    const hits = raycaster.intersectObjects(scene.children, true);
    api.select(hits.length ? uriOf(hits[0].object) : null);
  });

  // The first frame is drawn even off screen so that `ready` always resolves.
  api.ready = new Promise((resolve) => { firstFrame = resolve; });
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
    const viewer = n2fCreateViewer(el, {
      explodeAxis: el.getAttribute('data-explode-axis') || 'z',
      explodeSpacing: parseFloat(el.getAttribute('data-explode-spacing') || '80'),
    });
    try {
      await viewer.loadBase64(dataEl.textContent.trim());
      await viewer.ready;
      window.n2fViewers[el.id || 'default'] = viewer;
      el.dispatchEvent(new CustomEvent('n2f:loaded', { detail: { nodes: viewer.nodes() } }));
    } catch (err) {
      console.error('n2f viewer failed', err);
      el.setAttribute('data-n2f-error', String(err));
    }
  }
  window.n2fViewer = window.n2fViewers.default || Object.values(window.n2fViewers)[0] || null;
  return window.n2fViewers;
})();
