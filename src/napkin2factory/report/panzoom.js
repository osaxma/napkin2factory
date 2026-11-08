// The drawing viewer for the report's drawings and wiring diagrams (v0.9 M3b, S-319, amended by S-322).
//
// Markup (written by the section templates, so the page reads without this script):
//   <div class="pz-card" data-pzcard data-title="Bracket">(a button, class pz-open, holding the svg)</div>
// A card is a title and a static preview, no controls.  Opening one builds ONE full-screen viewer
// (a modal dialog) for the page: a slim bar (Drawings list, pan arrows, Zoom in, Zoom out, Fit, Close),
// a collapsible list of every drawing on the page, and a clone of the card's SVG.  Zoom sets the SVG's
// own width and height (no CSS transform), so lines stay sharp at any zoom.  Import-free IIFE.
(function () {
  'use strict';
  const CSS = [
    '.pz-card{margin:0}',
    '.pz-open{display:block;width:100%;margin:0;padding:0;border:0;background:#fff;font:inherit;color:inherit;cursor:zoom-in;text-align:left}',
    '.pz-open:hover{outline:2px solid var(--accent,#1f5fbf);outline-offset:-2px}',
    '.pz-open:focus-visible{outline:3px solid var(--accent,#1f5fbf);outline-offset:-3px}',
    '.pzv{position:fixed;inset:0;z-index:2000;display:flex;flex-direction:column;background:var(--bg,#f7f6f2);color:var(--ink,#1c1b19)}',
    '.pzv[hidden]{display:none}',
    '.pzv-bar{display:flex;flex-wrap:nowrap;align-items:center;gap:.35rem;padding:.35rem .5rem;border-bottom:1px solid var(--line,#d9d7d0);background:var(--bg,#f7f6f2)}',
    '.pzv-bar button,.pzv-side button{font:inherit;font-size:.85rem;padding:.2rem .65rem;border:1px solid var(--line,#d9d7d0);border-radius:6px;background:#fff;color:inherit;cursor:pointer;min-height:2.25rem;min-width:2.25rem}',
    '.pzv-bar button:hover,.pzv-side button:hover{border-color:var(--accent,#1f5fbf)}',
    '.pzv-bar button:focus-visible,.pzv-side button:focus-visible,.pzv-view:focus-visible{outline:3px solid var(--accent,#1f5fbf);outline-offset:-1px}',
    '.pzv-title{flex:1 1 0;font-weight:600;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
    '.pzv-pan{display:inline-flex;gap:.2rem}',
    '.pzv-more,.pzv-bar .s{display:none}',
    '.pzv-narrow .pzv-bar .l{display:none}',
    '.pzv-narrow .pzv-bar .s{display:inline;font-size:1.1rem;line-height:1}',
    '.pzv-narrow .pzv-bar button{padding:.2rem .5rem}',
    '.pzv-narrow .pzv-more{display:inline-block}',
    '.pzv-narrow .pzv-pan{position:absolute;z-index:3;right:.5rem;bottom:.75rem;display:none;padding:.3rem;border:1px solid var(--line,#d9d7d0);border-radius:8px;background:var(--bg,#f7f6f2);box-shadow:0 2px 8px rgba(0,0,0,.25)}',
    '.pzv-narrow .pzv-pan.pz-on{display:inline-flex}',
    '.pzv-body{position:relative;flex:1;display:flex;min-height:0}',
    '.pzv-side{flex:0 0 15rem;max-width:70vw;overflow:auto;border-right:1px solid var(--line,#d9d7d0);background:var(--bg,#f7f6f2);padding:.4rem}',
    '.pzv-side[hidden]{display:none}',
    '.pzv-side ul{list-style:none;margin:0;padding:0;display:grid;gap:.25rem}',
    '.pzv-side button{display:block;width:100%;text-align:left;overflow-wrap:anywhere}',
    '.pzv-side button[aria-current="true"]{border-color:var(--accent,#1f5fbf);background:#e8f0fc;font-weight:600}',
    '.pzv-view{position:relative;flex:1;min-width:0;overflow:hidden;background:#fff;cursor:grab;touch-action:none}',
    '.pzv-view.pz-drag{cursor:grabbing}',
    '.pzv-view svg{position:absolute;max-width:none!important;min-width:0!important;cursor:inherit!important;display:block}',
    '.pzv-narrow .pzv-side{position:absolute;z-index:2;top:0;bottom:0;left:0;box-shadow:2px 0 8px rgba(0,0,0,.25)}',
    '@media print{.pzv{display:none!important}.pz-open{display:block!important;cursor:default}}'
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

  // the clone lives beside the card's SVG: give every id a prefix (and its references) so none repeats
  function uniqueIds(svg, prefix) {
    const ids = new Set();
    svg.querySelectorAll('[id]').forEach((e) => { ids.add(e.id); });
    if (svg.id) ids.add(svg.id);
    if (!ids.size) return;
    const fix = (v) => v.replace(/url\(\s*(['"]?)#([^)'"]+)\1\s*\)/g, (m, q, id) => (ids.has(id) ? 'url(#' + prefix + id + ')' : m));
    const all = [svg, ...svg.querySelectorAll('*')];
    all.forEach((e) => {
      if (e.id) e.id = prefix + e.id;
      for (const a of [...e.attributes]) {
        if ((a.name === 'href' || a.name === 'xlink:href') && a.value.charAt(0) === '#' && ids.has(a.value.slice(1))) a.value = '#' + prefix + a.value.slice(1);
        else if (a.value.indexOf('url(') >= 0) a.value = fix(a.value);
      }
    });
  }

  function el(tag, attrs, text) {
    const e = document.createElement(tag);
    for (const k in (attrs || {})) e.setAttribute(k, attrs[k]);
    if (text) e.textContent = text;
    return e;
  }

  let viewer = null;

  function build(cards) {
    const root = el('div', { class: 'pzv', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Drawing viewer', hidden: '' });
    const bar = el('div', { class: 'pzv-bar' });
    const toggle = el('button', { type: 'button', 'aria-expanded': 'false', 'aria-controls': 'pzv-side' }, 'Drawings');
    const title = el('span', { class: 'pzv-title', 'aria-live': 'polite' });
    const pan = el('span', { class: 'pzv-pan', role: 'group', 'aria-label': 'Move the drawing' });
    [['left', '←'], ['right', '→'], ['up', '↑'], ['down', '↓']].forEach((d) => {
      pan.appendChild(el('button', { type: 'button', 'data-pan': d[0], 'aria-label': 'Pan ' + d[0] }, d[1]));
    });
    // a button shows its full word, or a short sign on a phone; its accessible name is always the word
    const mk = (act, word, sign) => {
      const b = el('button', { type: 'button', 'data-pz': act, 'aria-label': word });
      b.appendChild(el('span', { class: 'l', 'aria-hidden': 'true' }, word));
      b.appendChild(el('span', { class: 's', 'aria-hidden': 'true' }, sign));
      return b;
    };
    const bIn = mk('in', 'Zoom in', '+');
    const bOut = mk('out', 'Zoom out', '\u2212');
    const bFit = mk('fit', 'Fit', 'Fit');
    const bClose = mk('close', 'Close', '\u00d7');
    const more = el('button', { type: 'button', class: 'pzv-more', 'aria-expanded': 'false', 'aria-label': 'Move the drawing' }, 'Move');
    if (cards.length > 1) bar.appendChild(toggle);
    [title, pan, more, bIn, bOut, bFit, bClose].forEach((e) => bar.appendChild(e));
    const body = el('div', { class: 'pzv-body' });
    const side = el('nav', { class: 'pzv-side', id: 'pzv-side', 'aria-label': 'All drawings', hidden: '' });
    const ul = el('ul');
    const items = cards.map((c, i) => {
      const li = el('li');
      const b = el('button', { type: 'button', 'data-i': String(i) }, c.getAttribute('data-title') || 'Drawing ' + (i + 1));
      li.appendChild(b); ul.appendChild(li);
      return b;
    });
    side.appendChild(ul);
    const view = el('div', { class: 'pzv-view', tabindex: '0', role: 'group', 'aria-label': 'Drawing: arrow keys move, plus and minus zoom, 0 fits' });
    body.appendChild(side); body.appendChild(view);
    root.appendChild(bar); root.appendChild(body);
    document.body.appendChild(root);

    const st = { s: 1, x: 0, y: 0, fit: 1, i: -1, nat: { w: 1, h: 1 }, svg: null, opener: null };
    let atFit = true;
    // phone layout is decided by the viewer's own width, not the media query (S-323)
    const narrow = () => root.clientWidth <= 640;
    const mark = () => root.classList.toggle('pzv-narrow', narrow());
    const isOpen = () => !root.hidden;

    function clamp() {
      const w = view.clientWidth, h = view.clientHeight;
      const sw = st.nat.w * st.s, sh = st.nat.h * st.s;
      st.x = sw <= w ? (w - sw) / 2 : Math.min(0, Math.max(w - sw, st.x));
      st.y = sh <= h ? (h - sh) / 2 : Math.min(0, Math.max(h - sh, st.y));
    }
    function apply() {
      if (!st.svg) return;
      clamp();
      const s = st.svg.style;
      s.setProperty('width', st.nat.w * st.s + 'px', 'important');
      s.setProperty('height', st.nat.h * st.s + 'px', 'important');
      s.left = st.x + 'px'; s.top = st.y + 'px';
      atFit = Math.abs(st.s - st.fit) < 1e-6;
      root.setAttribute('data-pz-scale', st.s.toFixed(4));
      root.setAttribute('data-pz-fit', st.fit.toFixed(4));
    }
    function reset() {
      const w = view.clientWidth, h = view.clientHeight;
      st.fit = (Math.min(w / st.nat.w, h / st.nat.h) * 0.96) || 1;
      st.s = st.fit; st.x = 0; st.y = 0;
      apply();
    }
    function zoomAt(k, cx, cy) {
      const s2 = Math.min(st.fit * 12, Math.max(st.fit, st.s * k));
      const r = s2 / st.s;
      st.x = cx - (cx - st.x) * r;
      st.y = cy - (cy - st.y) * r;
      st.s = s2;
      apply();
    }
    const centre = () => ({ x: view.clientWidth / 2, y: view.clientHeight / 2 });
    function move(dx, dy) { st.x += dx; st.y += dy; apply(); }

    function show(i) {
      const card = cards[i];
      const src = card.querySelector('svg');
      if (!src) return;
      if (st.svg) st.svg.remove();
      const svg = src.cloneNode(true);
      uniqueIds(svg, 'pzv' + i + '-');
      svg.removeAttribute('width'); svg.removeAttribute('height'); svg.removeAttribute('style');
      st.nat = naturalSize(src);
      st.svg = svg; st.i = i;
      view.appendChild(svg);
      title.textContent = card.getAttribute('data-title') || '';
      root.setAttribute('aria-label', (card.getAttribute('data-title') || 'Drawing') + ' drawing');
      items.forEach((b, j) => { if (j === i) b.setAttribute('aria-current', 'true'); else b.removeAttribute('aria-current'); });
      reset();
    }
    function setSide(open) {
      side.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
    }
    function open(i, opener) {
      st.opener = opener;
      root.hidden = false;
      document.documentElement.style.overflow = 'hidden';
      mark();
      pan.classList.remove('pz-on'); more.setAttribute('aria-expanded', 'false');
      setSide(!narrow() && cards.length > 1);
      show(i);
      view.focus();
    }
    function close() {
      root.hidden = true;
      document.documentElement.style.overflow = '';
      if (st.svg) { st.svg.remove(); st.svg = null; }
      const o = st.opener; st.opener = null;
      if (o && o.focus) o.focus();
    }
    viewer = { open, isOpen };

    toggle.addEventListener('click', () => setSide(side.hidden));
    more.addEventListener('click', () => {
      const on = !pan.classList.contains('pz-on');
      pan.classList.toggle('pz-on', on); more.setAttribute('aria-expanded', String(on));
    });
    items.forEach((b) => b.addEventListener('click', () => {
      show(Number(b.getAttribute('data-i')));
      if (narrow()) setSide(false);
      view.focus();
    }));
    root.addEventListener('click', (ev) => {
      const b = ev.target.closest('button');
      if (!b || !root.contains(b)) return;
      const c = centre();
      const act = b.getAttribute('data-pz');
      const p = b.getAttribute('data-pan');
      if (act === 'in') zoomAt(1.5, c.x, c.y);
      else if (act === 'out') zoomAt(1 / 1.5, c.x, c.y);
      else if (act === 'fit') reset();
      else if (act === 'close') close();
      else if (p) { const d = 120; move(p === 'left' ? d : p === 'right' ? -d : 0, p === 'up' ? d : p === 'down' ? -d : 0); }
    });

    root.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') { ev.preventDefault(); close(); return; }
      if (ev.key === 'Tab') { // keep focus inside the dialog
        const f = [...root.querySelectorAll('button,[tabindex="0"]')].filter((e) => !e.closest('[hidden]'));
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
        else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
        return;
      }
      if (ev.ctrlKey || ev.metaKey || ev.altKey || ev.target.closest('button')) return;
      const c = centre();
      let used = true;
      switch (ev.key) {
        case 'ArrowLeft': move(48, 0); break;
        case 'ArrowRight': move(-48, 0); break;
        case 'ArrowUp': move(0, 48); break;
        case 'ArrowDown': move(0, -48); break;
        case '+': case '=': zoomAt(1.25, c.x, c.y); break;
        case '-': case '_': zoomAt(1 / 1.25, c.x, c.y); break;
        case '0': reset(); break;
        default: used = false;
      }
      if (used) ev.preventDefault();
    });

    // wheel: the viewer is a modal, so a plain wheel zooms too (ctrl and a trackpad pinch faster)
    view.addEventListener('wheel', (ev) => {
      ev.preventDefault();
      const b = view.getBoundingClientRect();
      zoomAt(Math.exp(-ev.deltaY * ((ev.ctrlKey || ev.metaKey) ? 0.01 : 0.002)), ev.clientX - b.left, ev.clientY - b.top);
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
        move(dx, dy);
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
      if (!atFit) reset(); else { const b = view.getBoundingClientRect(); zoomAt(3, ev.clientX - b.left, ev.clientY - b.top); }
    });

    // a resize (window, or the list opening beside the drawing) refits while the drawing is at fit
    let lw = 0, lh = 0;
    function onSize() {
      if (!isOpen() || !st.svg) return;
      const wasNarrow = root.classList.contains('pzv-narrow');
      mark();
      if (narrow() && !wasNarrow) setSide(false);
      const w = view.clientWidth, h = view.clientHeight;
      if (!w || (w === lw && h === lh)) return;
      lw = w; lh = h;
      if (atFit) reset(); else apply();
    }
    if (window.ResizeObserver) new ResizeObserver(onSize).observe(view);
    window.addEventListener('resize', onSize);
  }

  function init() {
    if (!document.getElementById('pz-style')) {
      const s = document.createElement('style');
      s.id = 'pz-style'; s.textContent = CSS;
      document.head.appendChild(s);
    }
    const cards = [...document.querySelectorAll('[data-pzcard]')];
    if (!cards.length) return;
    build(cards);
    cards.forEach((c, i) => {
      const b = c.querySelector('button.pz-open');
      if (b) b.addEventListener('click', () => viewer.open(i, b));
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
