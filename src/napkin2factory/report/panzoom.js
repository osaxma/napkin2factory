// Pan/zoom frames for the report's drawings and wiring diagrams (v0.9 M3b, S-319).
//
// Markup (written by the section templates, so the page reads without this script):
//   <div class="pz" data-panzoom>
//     <div class="pz-bar">buttons with data-pz="in|out|fit|full"</div>
//     <div class="pz-view" role="group" tabindex="0" aria-label="..."><div class="pz-stage"><svg/></div></div>
//   </div>
// The start state is the whole drawing fitted to the frame.  Plain wheel scrolls the page (no scroll
// trap); ctrl or meta + wheel (and a trackpad pinch) zooms.  Import-free IIFE: inline.py inlines it as is.
(function () {
  'use strict';
  const CSS = [
    '.pz{border:1px solid var(--line,#d9d7d0);border-radius:8px;overflow:hidden;background:#fff;position:relative}',
    '.pz-bar{display:flex;flex-wrap:wrap;gap:.3rem;padding:.3rem .4rem;border-bottom:1px solid var(--line,#d9d7d0);background:var(--bg,#f7f6f2)}',
    '.pz-bar button{font:inherit;font-size:.8rem;padding:.2rem .6rem;border:1px solid var(--line,#d9d7d0);border-radius:6px;background:#fff;color:inherit;cursor:pointer;min-height:2rem}',
    '.pz-bar button:hover{border-color:var(--accent,#1f5fbf)}',
    '.pz-view{position:relative;overflow:hidden;outline-offset:-2px;touch-action:pan-y}',
    '.pz.pz-on .pz-view{cursor:grab;height:var(--pz-h,60vh)}',
    '.pz.pz-on .pz-view.pz-zoomed{touch-action:none}',
    '.pz.pz-on .pz-view.pz-drag{cursor:grabbing}',
    '.pz-stage{transform-origin:0 0;will-change:transform}',
    '.pz.pz-on .pz-stage{position:absolute;left:0;top:0}',
    '.pz.pz-on .pz-stage svg{max-width:none!important;min-width:0!important;cursor:inherit!important;display:block}',
    '.pz.pz-full{position:fixed;inset:0;z-index:1000;border-radius:0;display:flex;flex-direction:column}',
    '.pz:fullscreen{display:flex;flex-direction:column;border-radius:0}',
    '.pz.pz-full .pz-view,.pz:fullscreen .pz-view{flex:1;height:auto!important}',
    '@media print{.pz-bar{display:none}.pz-view,.pz.pz-on .pz-view{height:auto!important;overflow:visible}',
    '.pz.pz-on .pz-stage{position:static;transform:none!important;width:auto!important;height:auto!important}',
    '.pz.pz-on .pz-stage svg{width:100%!important;height:auto!important;max-width:100%!important}}'
  ].join('\n');

  function naturalSize(svg) {
    const vb = (svg.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
    let w = vb.length === 4 ? vb[2] : 0;
    let h = vb.length === 4 ? vb[3] : 0;
    if (!(w > 0 && h > 0)) {
      const b = svg.getBBox ? svg.getBBox() : { width: 800, height: 600 };
      w = b.width || 800; h = b.height || 600;
    }
    // one drawing unit is a millimetre; 96 dpi gives the size the file would print at
    const k = 96 / 25.4;
    return { w: w * k, h: h * k };
  }

  function setup(root) {
    const view = root.querySelector('.pz-view');
    const stage = root.querySelector('.pz-stage');
    const svg = stage && stage.querySelector('svg');
    if (!view || !svg || root.__pz) return;
    const nat = naturalSize(svg);
    svg.style.width = nat.w + 'px';
    svg.style.height = nat.h + 'px';
    root.classList.add('pz-on');
    const st = { s: 1, x: 0, y: 0, fit: 1 };
    root.__pz = st;
    let atFit = true;

    function size() { return { w: view.clientWidth, h: view.clientHeight }; }
    function clamp() {
      const v = size();
      const sw = nat.w * st.s, sh = nat.h * st.s;
      st.x = sw <= v.w ? (v.w - sw) / 2 : Math.min(0, Math.max(v.w - sw, st.x));
      st.y = sh <= v.h ? (v.h - sh) / 2 : Math.min(0, Math.max(v.h - sh, st.y));
    }
    function apply() {
      clamp();
      stage.style.transform = 'translate(' + st.x + 'px,' + st.y + 'px) scale(' + st.s + ')';
      atFit = Math.abs(st.s - st.fit) < 1e-6;
      view.classList.toggle('pz-zoomed', !atFit);
      root.setAttribute('data-pz-scale', st.s.toFixed(4));
      root.setAttribute('data-pz-fit', st.fit.toFixed(4));
    }
    function frameHeight() {
      // the whole drawing fits the width; the height follows it, up to most of the window
      const full = root.classList.contains('pz-full') || document.fullscreenElement === root;
      if (full) { view.style.removeProperty('--pz-h'); return; }
      const w = view.clientWidth || root.clientWidth;
      const cap = Math.max(240, Math.round(window.innerHeight * 0.7));
      view.style.setProperty('--pz-h', Math.min(cap, Math.max(160, Math.round(nat.h * w / nat.w))) + 'px');
    }
    function reset() {
      frameHeight();
      const v = size();
      st.fit = Math.min(v.w / nat.w, v.h / nat.h) || 1;
      st.s = st.fit; st.x = 0; st.y = 0;
      apply();
    }
    function zoomAt(k, cx, cy) {
      const s2 = Math.min(st.fit * 24, Math.max(st.fit, st.s * k));
      const r = s2 / st.s;
      st.x = cx - (cx - st.x) * r;
      st.y = cy - (cy - st.y) * r;
      st.s = s2;
      apply();
    }
    function centre() { const v = size(); return { x: v.w / 2, y: v.h / 2 }; }
    function local(ev) { const b = view.getBoundingClientRect(); return { x: ev.clientX - b.left, y: ev.clientY - b.top }; }

    // buttons
    root.addEventListener('click', (ev) => {
      const b = ev.target.closest('button[data-pz]');
      if (!b || !root.contains(b)) return;
      const c = centre();
      const act = b.getAttribute('data-pz');
      if (act === 'in') zoomAt(1.5, c.x, c.y);
      else if (act === 'out') zoomAt(1 / 1.5, c.x, c.y);
      else if (act === 'fit') reset();
      else if (act === 'full') toggleFull();
    });
    function toggleFull() {
      const on = document.fullscreenElement === root || root.classList.contains('pz-full');
      if (on) {
        if (document.fullscreenElement === root) document.exitFullscreen();
        root.classList.remove('pz-full');
        after();
      } else if (root.requestFullscreen) {
        root.requestFullscreen().then(after, () => { root.classList.add('pz-full'); after(); });
      } else { root.classList.add('pz-full'); after(); }
      const fb = root.querySelector('button[data-pz="full"]');
      if (fb) fb.setAttribute('aria-pressed', String(!on));
    }
    function after() { requestAnimationFrame(() => { const keep = atFit; if (keep) reset(); else apply(); }); }
    document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement) root.classList.remove('pz-full'); after(); });
    root.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' && root.classList.contains('pz-full')) { toggleFull(); }
    });

    // wheel: ctrl or meta zooms; a plain wheel is left to the page
    view.addEventListener('wheel', (ev) => {
      if (!(ev.ctrlKey || ev.metaKey)) return;
      ev.preventDefault();
      const p = local(ev);
      zoomAt(Math.exp(-ev.deltaY * 0.01), p.x, p.y);
    }, { passive: false });

    // drag to pan, two pointers to pinch
    const pts = new Map();
    let last = null, pinch = null, moved = 0;
    view.addEventListener('pointerdown', (ev) => {
      if (ev.button !== 0 && ev.pointerType === 'mouse') return;
      pts.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
      try { view.setPointerCapture(ev.pointerId); } catch (e) { /* synthetic pointer */ }
      moved = 0;
      if (pts.size === 1) last = { x: ev.clientX, y: ev.clientY };
      if (pts.size === 2) { const [a, b] = [...pts.values()]; pinch = Math.hypot(a.x - b.x, a.y - b.y); }
    });
    view.addEventListener('pointermove', (ev) => {
      if (!pts.has(ev.pointerId)) return;
      pts.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
      if (pts.size === 2 && pinch) {
        const [a, b] = [...pts.values()];
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        const bb = view.getBoundingClientRect();
        zoomAt(d / pinch, (a.x + b.x) / 2 - bb.left, (a.y + b.y) / 2 - bb.top);
        pinch = d;
        return;
      }
      if (pts.size === 1 && last) {
        const dx = ev.clientX - last.x, dy = ev.clientY - last.y;
        moved += Math.abs(dx) + Math.abs(dy);
        if (moved > 3) view.classList.add('pz-drag');
        last = { x: ev.clientX, y: ev.clientY };
        st.x += dx; st.y += dy;
        apply();
      }
    });
    function up(ev) {
      pts.delete(ev.pointerId);
      if (pts.size < 2) pinch = null;
      if (pts.size === 1) { const [p] = [...pts.values()]; last = { x: p.x, y: p.y }; }
      if (pts.size === 0) { last = null; view.classList.remove('pz-drag'); }
    }
    view.addEventListener('pointerup', up);
    view.addEventListener('pointercancel', up);
    view.addEventListener('dblclick', (ev) => {
      if (!atFit) reset(); else { const p = local(ev); zoomAt(3, p.x, p.y); }
    });
    view.addEventListener('keydown', (ev) => {
      if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
      const c = centre();
      const step = 48;
      let used = true;
      switch (ev.key) {
        case 'ArrowLeft': st.x += step; apply(); break;
        case 'ArrowRight': st.x -= step; apply(); break;
        case 'ArrowUp': st.y += step; apply(); break;
        case 'ArrowDown': st.y -= step; apply(); break;
        case '+': case '=': zoomAt(1.25, c.x, c.y); break;
        case '-': case '_': zoomAt(1 / 1.25, c.x, c.y); break;
        case '0': reset(); break;
        default: used = false;
      }
      if (used) ev.preventDefault();
    });

    // a lens that was hidden has no width yet: fit when it first has one, and when the column changes
    let lastW = 0;
    function onSize() {
      const w = view.clientWidth;
      if (!w || w === lastW) return;
      lastW = w;
      if (atFit) reset(); else apply();
    }
    if (window.ResizeObserver) new ResizeObserver(onSize).observe(view);
    window.addEventListener('resize', onSize);
    reset(); lastW = view.clientWidth;
  }

  function init() {
    if (!document.getElementById('pz-style')) {
      const s = document.createElement('style');
      s.id = 'pz-style'; s.textContent = CSS;
      document.head.appendChild(s);
    }
    document.querySelectorAll('[data-panzoom]').forEach(setup);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
