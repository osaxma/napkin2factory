// napkin2factory report workbench (v0.9 M3a: V1 to V8).  Runs in the same inline module script as
// the viewer (inline.py puts it after viewer.js, or alone when the page has no 3D model), so it
// reads everything from the DOM and the embedded inspector index; nothing is fetched (D13).
//
// What it does: the lens tabs, the tree, the inspector, one selection bus that keeps the three
// and the 3D view in step, and the deep links (`#lens=build&select=part://x`, plus every old anchor).
// It names no domain's kind (F9, V5): an entry of a kind it does not know is shown generically.
//
// Public surface (window.n2fWorkbench):
//   select(uri)  -> select an entry (null = the product); a URI with no entry says so (V4)
//   lens(name)   -> open a lens (workbench | drawings | build | verification | history);
//                   with no argument, the name of the open one
//   current()    -> the selected URI
//   index        -> the parsed #inspector-index
// and the event `n2f:lens` (detail: {lens}) on document.
// Below 768 px it also drives the phone's dock and bottom sheets through `.wb[data-sheet]` (V8, M4).
(function () {
  'use strict';
  const PRODUCT = 'manifest://product';
  const indexEl = document.getElementById('inspector-index');
  if (!indexEl) return;
  const index = JSON.parse(indexEl.textContent);
  const $ = (id) => document.getElementById(id);

  // ---- small helpers ---------------------------------------------------------------------
  function el(tag, props, ...kids) {
    const e = document.createElement(tag);
    for (const k of Object.keys(props || {})) {
      const v = props[k];
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class') e.className = v;
      else if (k === 'text') e.textContent = v;
      else e.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) {
      if (kid === null || kid === undefined || kid === false) continue;
      e.appendChild(typeof kid === 'string' ? document.createTextNode(kid) : kid);
    }
    return e;
  }
  const isUri = (s) => typeof s === 'string' && s.indexOf('://') > 0;
  const humanize = (k) => { const t = String(k).replace(/_/g, ' ').trim(); return t.charAt(0).toUpperCase() + t.slice(1); };
  const empty = (v) => v === null || v === undefined || v === '' || v === 'None' ||
    (Array.isArray(v) && v.length === 0) || (typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length === 0);
  const nameOf = (uri) => { const e = index[uri]; return e ? (e.name || e.title || uri) : uri; };
  const scheme = (uri) => uri.slice(0, uri.indexOf('://'));
  const viewer = () => window.n2fViewer || null;
  const NODE_KINDS = { assembly: 'Assembly', interface: 'Interface', requirement: 'Requirement', rule: 'Rule check', doc: 'Document', product: 'Product' };
  function kindWords(e) {
    if (e.kind === 'part') return e.part_kind === 'cots' ? 'Bought part' : 'Custom part';
    return NODE_KINDS[e.kind] || humanize(e.kind || 'entry');
  }

  // ---- hash links: the one way a link moves the page ------------------------------------------
  // `select=` values are written unencoded (part://x) and read with decodeURIComponent, so
  // the encoded form works too (V6).
  const linkTo = (uri, text, cls) => el('a', {
    href: '#lens=workbench&select=' + uri, class: cls || 'ref', title: text,
  }, text);
  const uriLink = (uri) => (index[uri] ? linkTo(uri, nameOf(uri)) : el('span', { class: 'mono', title: uri }, uri));

  // ---- who names whom: "Used by" ---------------------------------------------------------
  const refs = {};
  const usedBy = {};
  (function () {
    const collect = (v, out) => {
      if (typeof v === 'string') { if (index[v]) out.add(v); }
      else if (Array.isArray(v)) v.forEach((x) => collect(x, out));
      else if (v && typeof v === 'object') Object.keys(v).forEach((k) => collect(v[k], out));
    };
    for (const uri of Object.keys(index)) {
      if (uri === PRODUCT) continue;  // the product names everything; that says nothing
      const out = new Set();
      collect(index[uri], out);
      out.delete(uri);
      refs[uri] = out;
      out.forEach((t) => { (usedBy[t] = usedBy[t] || []).push(uri); });
    }
  })();

  // ---- the tree: the product, its units and their children, then the groups ------------------------
  // Hierarchy comes from an assembly's `children` ([{uri, qty}], BOM order); without it, from the
  // items of the assembly's own build steps.
  function childrenOf(uri) {
    const e = index[uri];
    if (!e || e.kind !== 'assembly') return [];
    if (Array.isArray(e.children)) return e.children.filter((c) => c && c.uri);
    const out = [];
    const seen = {};
    for (const st of e.build_steps || []) {
      if (st.unit && st.unit !== uri) continue;
      for (const it of st.items || []) {
        if (!it.uri) continue;
        if (seen[it.uri]) seen[it.uri].qty += it.qty || 1;
        else { seen[it.uri] = { uri: it.uri, qty: it.qty || 1 }; out.push(seen[it.uri]); }
      }
    }
    return out;
  }
  const treeEl = $('tree');
  function buildTree() {
    if (!treeEl) return;
    const reached = new Set();
    const rowOf = (uri, label, opts) => {
      opts = opts || {};
      // the name is set by hand: from its content a parent's name would swallow every child's (S-325)
      const li = el('li', { role: 'treeitem', 'data-uri': uri, 'aria-selected': 'false', 'aria-level': opts.level, tabindex: '-1', class: opts.cls,
        'aria-label': opts.qty > 1 ? label + ', quantity ' + opts.qty : label });
      const row = el('div', { class: 'row' }, el('span', { class: 'tog', 'aria-hidden': 'true' }, ''),
        el('span', { class: 'lbl', title: label }, label));
      if (opts.qty > 1) row.appendChild(el('span', { class: 'qty' }, '× ' + opts.qty));
      if (opts.sub) row.appendChild(el('span', { class: 'sub' }, opts.sub));
      li.appendChild(row);
      return li;
    };
    const addKids = (li, kids, open) => {
      const ul = el('ul', { role: 'group' }, kids);
      li.appendChild(ul);
      li.setAttribute('aria-expanded', open ? 'true' : 'false');
      li.querySelector('.tog').textContent = open ? '▾' : '▸';
    };
    const unitItem = (uri, qty, level, trail) => {
      const e = index[uri];
      reached.add(uri);
      const li = rowOf(uri, nameOf(uri), { qty, level, sub: e && e.kind === 'assembly' && typeof e.build === 'string' ? e.build : '' });
      const kids = trail.includes(uri) ? [] : childrenOf(uri).filter((c) => index[c.uri]).map((c) => unitItem(c.uri, c.qty, level + 1, trail.concat(uri)));
      if (kids.length) addKids(li, kids, true);
      return li;
    };
    const root = el('ul', { role: 'tree', 'aria-label': 'parts and objects' });
    const product = index[PRODUCT] || {};
    const top = (product.unit_uris || product.build_units || []).filter((u) => index[u]);
    const pli = rowOf(PRODUCT, 'Product', { level: 1, cls: 'head' });
    addKids(pli, top.map((u) => unitItem(u, 1, 2, [])), true);
    root.appendChild(pli);
    const group = (label, uris) => {
      if (!uris.length) return;
      const li = rowOf('', label + ' (' + uris.length + ')', { level: 1, cls: 'group' });
      li.removeAttribute('data-uri');
      addKids(li, uris.map((u) => rowOf(u, nameOf(u), { level: 2 })), false);
      root.appendChild(li);
    };
    const all = Object.keys(index);
    group('Interfaces', all.filter((u) => scheme(u) === 'iface'));
    group('Documents', all.filter((u) => scheme(u) === 'doc'));
    // anything the hierarchy did not reach, so every part is one click away
    group('Other parts', all.filter((u) => (scheme(u) === 'part' || scheme(u) === 'asm') && !reached.has(u)));
    // a domain's objects: one group per other scheme, headed by the entries' kind
    const known = ['manifest', 'asm', 'part', 'iface', 'req', 'rule', 'doc'];
    const schemes = [];
    all.forEach((u) => { const s = scheme(u); if (known.indexOf(s) < 0 && schemes.indexOf(s) < 0) schemes.push(s); });
    schemes.forEach((s) => {
      const uris = all.filter((u) => scheme(u) === s);
      const k = humanize(index[uris[0]].kind || s);
      group(k + (uris.length > 1 && !/s$/.test(k) ? 's' : ''), uris);
    });
    treeEl.appendChild(root);
    treeEl.addEventListener('click', (ev) => {
      const row = ev.target.closest('.row');
      if (!row) return;
      const li = row.parentElement;
      const uri = li.getAttribute('data-uri');
      const expandable = li.hasAttribute('aria-expanded');
      if (expandable && (ev.target.closest('.tog') || !uri)) { setOpen(li, li.getAttribute('aria-expanded') !== 'true'); return; }
      if (uri) { li.focus(); select(uri); }
    });
    treeEl.addEventListener('keydown', onTreeKey);
    treeEl.addEventListener('focusin', (ev) => { const li = ev.target.closest && ev.target.closest('li[role=treeitem]'); if (li) rove(li); });
  }
  // roving tabindex (S-325): the tree is one tab stop, on the item last focused or selected, so Tab reaches it
  function rove(li) {
    treeEl.querySelectorAll('li[role=treeitem][tabindex="0"]').forEach((o) => { if (o !== li) o.tabIndex = -1; });
    li.tabIndex = 0;
  }
  function setOpen(li, open) {
    li.setAttribute('aria-expanded', open ? 'true' : 'false');
    const t = li.querySelector(':scope > .row > .tog');
    if (t) t.textContent = open ? '▾' : '▸';
  }
  function visibleItems() {
    return Array.from(treeEl.querySelectorAll('li[role=treeitem]')).filter((li) => {
      for (let p = li.parentElement.closest('li[role=treeitem]'); p; p = p.parentElement.closest('li[role=treeitem]')) {
        if (p.getAttribute('aria-expanded') === 'false') return false;
      }
      return true;
    });
  }
  function onTreeKey(ev) {
    const li = ev.target.closest('li[role=treeitem]');
    if (!li || ev.target !== li) return;
    const items = visibleItems();
    const at = items.indexOf(li);
    const k = ev.key;
    if (k === 'ArrowDown' && at < items.length - 1) items[at + 1].focus();
    else if (k === 'ArrowUp' && at > 0) items[at - 1].focus();
    else if (k === 'Home') items[0].focus();
    else if (k === 'End') items[items.length - 1].focus();
    else if (k === 'ArrowRight' && li.getAttribute('aria-expanded') === 'false') setOpen(li, true);
    else if (k === 'ArrowRight' && li.getAttribute('aria-expanded') === 'true') { const c = li.querySelector('li[role=treeitem]'); if (c) c.focus(); }
    else if (k === 'ArrowLeft' && li.getAttribute('aria-expanded') === 'true') setOpen(li, false);
    else if (k === 'ArrowLeft') { const p = li.parentElement.closest('li[role=treeitem]'); if (p) p.focus(); }
    else if (k === 'Enter' || k === ' ') {
      const uri = li.getAttribute('data-uri');
      if (uri) select(uri); else setOpen(li, li.getAttribute('aria-expanded') !== 'true');
    } else return;
    ev.preventDefault();
  }
  function markTree(uri) {
    if (!treeEl) return;
    let first = null;
    treeEl.querySelectorAll('li[role=treeitem]').forEach((li) => {
      const on = li.getAttribute('data-uri') === uri;
      li.setAttribute('aria-selected', on ? 'true' : 'false');
      if (on && !first) first = li;
    });
    if (!first) return;
    rove(first);
    for (let p = first.parentElement.closest('li[role=treeitem]'); p; p = p.parentElement.closest('li[role=treeitem]')) setOpen(p, true);
    const row = first.querySelector('.row');
    const box = treeEl.getBoundingClientRect();
    const r = row.getBoundingClientRect();
    if (r.top < box.top || r.bottom > box.bottom) treeEl.scrollTop += r.top - box.top - box.height / 2;
  }

  // ---- the inspector -------------------------------------------------------------------------
  // Fields shown, in order, for the core kinds: [key, label, type].  type: row (default), links,
  // table, files, obj.  Any other kind is shown generically from its keys (F9).
  const KNOWN = {
    part: [['material', 'Material'], ['process', 'Process'], ['finish', 'Finish'], ['mass', 'Mass'], ['cost', 'Cost'],
      ['tolerance_class', 'Tolerance'], ['supplier', 'Supplier'], ['mpn', 'Part number'], ['source', 'Source', 'obj'],
      ['artifacts', 'Files', 'files'], ['interfaces', 'Interfaces', 'links'], ['requirements', 'Requirements', 'table'], ['checks', 'Checks', 'table']],
    assembly: [['mass', 'Mass'], ['cost', 'Cost'], ['part_count', 'Parts'], ['drawing', 'Files', 'files'], ['children', 'Contains', 'links'],
      ['interfaces', 'Interfaces', 'links']],
    interface: [['interface_kind', 'Kind'], ['spec', 'Spec'], ['description', 'Description'], ['message', 'Finding'], ['parties', 'Between', 'links']],
    requirement: [['statement', 'Statement'], ['category', 'Category'], ['priority', 'Priority'], ['safety', 'Safety'], ['message', 'Finding'],
      ['allocation', 'Allocated to', 'links'], ['satisfied_by', 'Satisfied by', 'links']],
    rule: [['message', 'Finding'], ['parties', 'Looks at', 'links']],
    doc: [['audience', 'Audience'], ['message', 'Finding'], ['links', 'Mentions', 'links']],
  };
  // keys the header, the buttons or the "Go to" links already carry, or that only repeat another field
  const SKIP = new Set(['uri', 'kind', 'title', 'name', 'id', 'status', 'status_words', 'part_kind', 'links']);
  const skipKey = (k) => SKIP.has(k) || /anchor$/.test(k) || /_words$/.test(k) || /_label$/.test(k) || /_(kg|usd)$/.test(k);

  function genericFields(e) {
    const out = [];
    for (const k of Object.keys(e)) {
      const v = e[k];
      if (skipKey(k) || empty(v)) continue;
      let type = 'row';
      if (Array.isArray(v)) {
        if (v.every(isUri)) type = 'links';
        else if (v.every((x) => x && typeof x === 'object' && !Array.isArray(x))) type = 'table';
      } else if (v && typeof v === 'object') type = 'obj';
      out.push([k, humanize(k), type]);
    }
    return out;
  }
  const scalar = (v) => Array.isArray(v) ? v.map(scalar).join(', ') : typeof v === 'boolean' ? (v ? 'yes' : 'no') : String(v);
  function valueCell(e, key) {
    const shown = e[key + '_words'] !== undefined && e[key + '_words'] !== null && e[key + '_words'] !== '' ? e[key + '_words'] : e[key];
    const lab = e[key + '_label'];
    const s = scalar(shown);
    const kids = [isUri(s) && index[s] ? linkTo(s, nameOf(s)) : s];
    if (typeof lab === 'string' && lab) kids.push(el('span', { class: 'muted' }, lab));
    return el('div', { class: 'v' }, kids);
  }
  function rowsOf(pairs) {
    const kv = el('div', { class: 'kv' });
    pairs.forEach(([k, v]) => { kv.appendChild(el('div', { class: 'k' }, k)); kv.appendChild(v); });
    return kv;
  }
  function renderLinks(v) {
    const seen = new Set();
    const items = v.map((x) => (x && typeof x === 'object' ? x : { uri: x, qty: 1 })).filter((x) => x.uri && !seen.has(x.uri) && seen.add(x.uri));
    return el('ul', { class: 'links' }, items.map((x) => el('li', {}, uriLink(x.uri), x.qty > 1 ? el('span', { class: 'muted' }, ' × ' + x.qty) : '')));
  }
  function renderTable(rows, label) {
    const keys = [];
    rows.forEach((r) => Object.keys(r).forEach((k) => {
      if (!skipKey(k) && k !== 'message' && typeof r[k] !== 'object' && !empty(r[k]) && keys.indexOf(k) < 0) keys.push(k);
    }));
    const cols = [rows.some((r) => r.title || r.name) && '@title', ...keys, rows.some((r) => r.status_words || r.status) && '@status'].filter(Boolean);
    const tbody = el('tbody');
    const thead = el('thead', { class: 'sr' }, el('tr', {}, cols.map((c) => el('th', { scope: 'col' }, c === '@title' ? 'Name' : c === '@status' ? 'Status' : humanize(c)))));
    rows.forEach((r) => {
      const tr = el('tr', {});
      cols.forEach((c) => {
        if (c === '@title') {
          const label = r.title || r.name || '';
          tr.appendChild(el('td', {}, r.uri && index[r.uri] ? linkTo(r.uri, label) : label, r.message ? el('div', { class: 'muted small' }, r.message) : ''));
        } else if (c === '@status') {
          tr.appendChild(el('td', { class: 'stc st-' + (r.status || '') }, scalar(r.status_words || r.status || '')));
        } else tr.appendChild(el('td', {}, empty(r[c]) ? '' : scalar(r[c])));
      });
      tbody.appendChild(tr);
    });
    return el('div', { class: 'scroll' }, el('table', {}, el('caption', { class: 'sr' }, label || 'Details'), thead, tbody));
  }
  function renderField(e, spec) {
    const [key, label, type] = spec;
    const v = e[key];
    if (empty(v)) return null;
    if (type === 'links') return [el('h3', {}, label), renderLinks(v)];
    if (type === 'table') return [el('h3', {}, label), renderTable(v, label)];
    if (type === 'files') {
      const paths = typeof v === 'string' ? [v] : Object.keys(v).map((k) => v[k]).filter((p) => !empty(p));
      return paths.length ? [el('h3', {}, label), el('div', { class: 'files' }, paths.map((p) => el('span', { class: 'mono wrap' }, scalar(p))))] : null;
    }
    if (type === 'obj') {
      const pairs = Object.keys(v).filter((k) => !empty(v[k]) && !skipKey(k)).map((k) => [humanize(k),
        el('div', { class: 'v' + (/url|mpn/.test(k) ? ' mono wrap' : '') }, scalar(v[k]))]);
      return pairs.length ? [el('h3', {}, label), rowsOf(pairs)] : null;
    }
    return { row: [label, valueCell(e, key)] };
  }
  // "Go to": one link per `*anchor` field whose element is on the page, labelled by the lens holding it
  function gotoLinks(e) {
    const keys = Object.keys(e).filter((k) => /anchor$/.test(k) && typeof e[k] === 'string' && e[k]);
    keys.sort((a, b) => (a === 'anchor') - (b === 'anchor'));  // the specific ones first, so a repeat keeps the best label
    const seen = new Set();
    const names = { part: 'Parts list', drawing: 'Drawing', sheet: 'Assembly sheet' };
    const out = [];
    keys.forEach((k) => {
      const id = e[k];
      const target = $(id);
      if (!target || seen.has(id)) return;
      seen.add(id);
      const lensEl = target.closest('[data-lens]');
      const base = k === 'anchor' ? kindWords(e) : (names[k.replace(/_?anchor$/, '')] || humanize(k.replace(/_?anchor$/, '')));
      const where = lensEl ? ', in ' + lensTitle(lensEl.getAttribute('data-lens')) : '';
      out.push(el('li', {}, el('a', { href: '#' + id }, base + where)));
    });
    return out;
  }
  function partsOf(uri) {
    const out = [];
    const walk = (v) => {
      if (typeof v === 'string') { if (v.indexOf('part://') === 0 && out.indexOf(v) < 0) out.push(v); }
      else if (Array.isArray(v)) v.forEach(walk);
      else if (v && typeof v === 'object') Object.keys(v).forEach((k) => walk(v[k]));
    };
    walk(index[uri]);
    return out;
  }
  const inScene = (uris) => { const v = viewer(); if (!v) return []; const n = v.nodes(); return uris.filter((u) => n.indexOf(u) >= 0); };

  function renderHead(uri, e) {
    const head = $('inspector-head');
    head.textContent = '';
    // the address is for the engineer persona only; the CSS hides it for the others, the text stays for deep links (N5, S-325)
    head.appendChild(el('div', { class: 'kindline' }, kindWords(e), el('span', { class: 'addr' }, ' · ', el('span', { class: 'mono' }, uri)),
      e.status_words ? [' · ', el('span', { class: 'st-' + e.status }, e.status_words)] : ''));
    head.appendChild(el('h2', { id: 'inspector-title', tabindex: '-1' }, e.title || e.name || uri));
    if (document.querySelector('[data-n2f-glb]')) {
      const b = el('div', { class: 'btns need3d' });
      const mine = uri === PRODUCT ? [] : partsOf(uri);
      if (uri !== PRODUCT && mine.length) {
        b.appendChild(el('button', { type: 'button', 'data-act': 'frame' }, 'Frame'));
        b.appendChild(el('button', { type: 'button', 'data-act': 'isolate' }, 'Isolate'));
      }
      b.appendChild(el('button', { type: 'button', 'data-act': 'all' }, 'Show all'));
      head.appendChild(b);
    }
  }
  function renderEntry(uri) {
    const box = $('inspector-entry');
    box.textContent = '';
    const e = index[uri];
    if (!e) {  // V4: the honest answer, never a guessed entry
      $('inspector-head').textContent = '';
      $('inspector-head').appendChild(el('h2', { id: 'inspector-title', tabindex: '-1' }, 'Nothing recorded'));
      box.appendChild(el('p', { class: 'muted', id: 'inspector-empty' }, 'This build records nothing for ' + uri + '.'));
      return;
    }
    renderHead(uri, e);
    const specs = KNOWN[e.kind] || genericFields(e);
    const rows = [];
    const blocks = [];
    specs.forEach((spec) => {
      if (spec[0] === 'description' && e.description === (e.title || e.name)) return;  // the heading already says it
      const r = renderField(e, spec);
      if (!r) return;
      if (r.row) rows.push(r.row); else blocks.push(r);
    });
    // `children` (assemblies) is not a field of the entry until the build records it; fall back to the tree's rule
    if (e.kind === 'assembly' && !Array.isArray(e.children)) {
      const kids = childrenOf(uri);
      if (kids.length) blocks.push([el('h3', {}, 'Contains'), renderLinks(kids)]);
    }
    if (rows.length) box.appendChild(rowsOf(rows));
    blocks.forEach((b) => b.forEach((n) => box.appendChild(n)));
    const used = (usedBy[uri] || []).filter((u) => !(refs[uri] && refs[uri].has(u)));
    if (used.length) {
      const more = used.length > 15 ? used.length - 15 : 0;
      box.appendChild(el('h3', {}, 'Used by'));
      box.appendChild(el('ul', { class: 'links' }, used.slice(0, 15).map((u) => el('li', {}, uriLink(u))),
        more ? el('li', { class: 'muted' }, 'and ' + more + ' more') : ''));
    }
    const go = gotoLinks(e);
    if (go.length) { box.appendChild(el('h3', {}, 'Go to')); box.appendChild(el('ul', { class: 'links' }, go)); }
  }

  // ---- 3D sync -------------------------------------------------------------------------------
  let syncing = false;       // our own calls into the viewer fire its n2f:select; those are not picks
  let highlighted = false;
  function clearHighlights() {
    const v = viewer();
    if (!v || !highlighted) return;
    highlighted = false;
    const f = $('explode');
    v.reset();  // the viewer has no "clear highlights"; reset() also drops explode, so put it back
    if (f && parseFloat(f.value) > 0) v.explode(parseFloat(f.value));
  }
  function sync3d() {
    const v = viewer();
    if (!v) return;
    syncing = true;
    try {
      clearHighlights();
      const uri = selected;
      if (uri !== PRODUCT && inScene([uri]).length) v.select(uri);
      else {
        v.select(null);
        if (uri !== PRODUCT) {
          const mine = inScene(partsOf(uri));
          if (mine.length) { v.highlight(mine); highlighted = true; }
        }
      }
    } finally { syncing = false; }
  }

  // ---- selection: one bus ----------------------------------------------------------------------
  let selected = PRODUCT;
  let rendered = false;  // the product's view is on the page from the start, but its head is drawn by the first select
  let fromHash = false;
  function select(uri) {
    uri = uri || PRODUCT;
    if (uri === selected && rendered) { if (!fromHash) sheetForSelection(); return; }
    selected = uri;
    rendered = true;
    const insp = $('inspector');
    const focusWasInside = insp.contains(document.activeElement) && document.activeElement !== insp;
    markTree(uri);
    const isProduct = uri === PRODUCT;
    $('inspector-product').hidden = !isProduct;
    $('inspector-entry').hidden = isProduct;
    if (isProduct) renderHead(uri, index[PRODUCT] || { kind: 'product', title: document.querySelector('header.top h1').textContent });
    else renderEntry(uri);
    $('inspector').scrollTop = 0;
    // the link that was clicked is gone with the old entry: focus goes to the new title, not to the page's top (S-325)
    if (focusWasInside && !insp.contains(document.activeElement) && !phone()) { const t = $('inspector-title'); if (t) t.focus({ preventScroll: true }); }
    sync3d();
    paintTitles();
    if (!fromHash) { sheetForSelection(); writeHash(); }
  }
  function writeHash() {
    const h = '#lens=' + lensName + (selected === PRODUCT ? '' : '&select=' + selected);
    try { history.replaceState(null, '', h); } catch (err) { /* file:// in some browsers: the page still works */ }
  }

  // ---- lenses ---------------------------------------------------------------------------------------
  const panels = Array.from(document.querySelectorAll('.lens[data-lens]'));
  const tabs = Array.from(document.querySelectorAll('[data-lens-tab]'));
  const lensTitle = (name) => { const t = document.querySelector('[data-lens-tab="' + name + '"]'); return t ? t.textContent : humanize(name); };
  let lensName = panels.length ? panels[0].getAttribute('data-lens') : 'workbench';
  const ALIAS = { checks: 'verification' };
  function setLens(name) {
    name = ALIAS[name] || name;
    if (!panels.some((p) => p.getAttribute('data-lens') === name)) name = panels.length ? panels[0].getAttribute('data-lens') : name;
    const changed = name !== lensName;
    lensName = name;
    panels.forEach((p) => { p.hidden = p.getAttribute('data-lens') !== name; });
    tabs.forEach((t) => {
      const on = t.getAttribute('data-lens-tab') === name;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
    });
    // a viewer made while its panel was hidden has no size yet: tell it the panel is on screen
    window.dispatchEvent(new Event('resize'));
    if (changed) { closeSheet(false); document.dispatchEvent(new CustomEvent('n2f:lens', { detail: { lens: name } })); }
    return name;
  }
  function lensFromUser(name) {
    location.hash = '#lens=' + name + (selected === PRODUCT ? '' : '&select=' + selected);  // a history entry: Back returns
    setLens(name);  // now, not at the (later) hashchange, so a caller can read lens() at once
  }
  tabs.forEach((t, i) => {
    t.addEventListener('click', () => lensFromUser(t.getAttribute('data-lens-tab')));
    t.addEventListener('keydown', (ev) => {
      const to = ev.key === 'ArrowRight' ? tabs[(i + 1) % tabs.length] : ev.key === 'ArrowLeft' ? tabs[(i + tabs.length - 1) % tabs.length]
        : ev.key === 'Home' ? tabs[0] : ev.key === 'End' ? tabs[tabs.length - 1] : null;
      if (to) { ev.preventDefault(); to.focus(); lensFromUser(to.getAttribute('data-lens-tab')); }
    });
  });

  // ---- deep links and old anchors (V6) ----------------------------------------------------------
  function applyHash() {
    const raw = location.hash.slice(1);
    fromHash = true;
    try {
      if (/^(lens|select)=/.test(raw)) {
        const p = {};
        raw.split('&').forEach((kv) => {
          const at = kv.indexOf('=');
          if (at > 0) { try { p[kv.slice(0, at)] = decodeURIComponent(kv.slice(at + 1)); } catch (err) { p[kv.slice(0, at)] = kv.slice(at + 1); } }
        });
        const prev = selected;
        if (p.select) select(p.select);
        const before = lensName;
        setLens(p.lens || (p.select ? 'workbench' : lensName));
        if (lensName !== before) window.scrollTo(0, 0);
        if (p.select && selected !== prev) sheetForSelection();  // a new pick from a link or a deep link shows its inspector
        return;
      }
      let id = raw;
      try { id = decodeURIComponent(raw); } catch (err) { /* keep it raw */ }
      const target = id ? $(id) : null;
      if (!target) { setLens('workbench'); return; }
      if (target.closest('#inspector-product')) select(PRODUCT);
      closeSheet(false);  // the page is about to scroll to its target: no sheet over it
      const holder = target.closest('[data-lens]');
      setLens(holder ? holder.getAttribute('data-lens') : 'workbench');
      target.scrollIntoView();
    } finally { fromHash = false; }
  }
  window.addEventListener('hashchange', applyHash);
  // every in-page link goes through the hash, so a link to where we already are still moves the page
  document.addEventListener('click', (ev) => {
    if (ev.defaultPrevented || ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
    const a = ev.target.closest('a');
    if (!a) return;
    const show = a.getAttribute('data-show3d');
    if (show) {  // links that mean "show me this in 3D"
      ev.preventDefault();
      location.hash = '#lens=workbench&select=' + show;
      applyHash();  // the hashchange comes later and finds nothing left to do
      return;
    }
    const h = a.getAttribute('href');
    if (!h || h.charAt(0) !== '#' || h === '#') return;
    ev.preventDefault();
    if (location.hash === h) applyHash(); else location.hash = h;
  });

  // ---- phone sheets (V8, M4, S-324) ------------------------------------------------------------
  // Below 768 px the parts list, the inspector and the 3D controls are bottom sheets opened from the dock;
  // `.wb[data-sheet]` holds which one (tree | inspector | view | none) and the CSS does the rest.  All of
  // it is inert on a wider screen (the attribute is ignored there), and matchMedia is read live.
  const wb = document.querySelector('.wb');
  const mq = window.matchMedia ? window.matchMedia('(max-width:767px)') : { matches: false };
  const phone = () => mq.matches;
  const dockBtns = Array.from(document.querySelectorAll('[data-sheet-open]'));
  const sheetEls = { tree: $('tree'), inspector: $('inspector'), view: $('view-panel') };
  let sheet = 'none';
  let sheetOpener = null;  // the dock button that began this visit; null = a pick (focus then returns to the 3D pane)
  let ready = false;       // false while the page draws itself: a deep link opens a sheet without taking focus
  function paintSheet() {
    if (wb) wb.setAttribute('data-sheet', sheet);
    dockBtns.forEach((b) => b.setAttribute('aria-expanded', b.getAttribute('data-sheet-open') === sheet ? 'true' : 'false'));
  }
  function openSheet(name, opener) {
    if (!wb || !sheetEls[name]) return;
    if (opener !== undefined) sheetOpener = opener;
    else if (sheet === 'none') sheetOpener = null;  // tree -> inspector keeps the button that opened the list
    sheet = name;
    paintSheet();
    const close = sheetEls[name].querySelector('[data-sheet-close]');
    if (ready && close) close.focus({ preventScroll: true });
  }
  function closeSheet(restore) {
    if (sheet === 'none') return;
    const had = sheetEls[sheet] && sheetEls[sheet].contains(document.activeElement);
    const back = sheetOpener || $('model');
    sheet = 'none';
    sheetOpener = null;
    paintSheet();
    if (restore !== false && had && back) back.focus({ preventScroll: true });
  }
  function sheetForSelection() {
    if (!phone() || lensName !== 'workbench') return;
    if (selected === PRODUCT) closeSheet(); else openSheet('inspector');
  }
  // the dock's middle button names what the inspector shows; the sheet's head says the same
  function paintTitles() {
    const t = $('inspector-title');
    const title = t ? t.textContent : '';
    const d = $('dock-details');
    if (d) d.textContent = selected === PRODUCT ? 'Product' : title;
    const h = $('inspector-sheet-title');
    if (h) h.textContent = title;
    const st = $('inspector-status');  // one small announcement per pick, not the whole inspector re-read (S-325)
    if (st && ready) st.textContent = 'Selected: ' + title;
  }
  function paintRoles() {  // a sheet is a labelled region on a phone, the page's own landmark otherwise
    [sheetEls.tree, sheetEls.inspector].forEach((e) => { if (e) { if (phone()) e.setAttribute('role', 'region'); else e.removeAttribute('role'); } });
  }
  dockBtns.forEach((b) => b.addEventListener('click', () => {
    const name = b.getAttribute('data-sheet-open');
    if (sheet === name) closeSheet(); else openSheet(name, b);
  }));
  document.addEventListener('click', (ev) => { if (ev.target.closest('[data-sheet-close]')) closeSheet(); });
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && phone() && sheet !== 'none') closeSheet(); });
  // Escape in the tree or the inspector clears the selection (the product shows again) and leaves focus in the tree; on a
  // phone an open sheet closes first, which the handler above does (S-325)
  function onEscape(ev) {
    if (ev.key !== 'Escape' || (phone() && sheet !== 'none')) return;
    if (selected === PRODUCT) return;
    const inTree = treeEl && treeEl.contains(ev.target);
    select(null);
    if (!inTree && treeEl) { const cur = treeEl.querySelector('li[role=treeitem][tabindex="0"]'); if (cur) cur.focus({ preventScroll: true }); }
    ev.preventDefault();
  }
  if (treeEl) treeEl.addEventListener('keydown', onEscape);
  $('inspector').addEventListener('keydown', onEscape);
  // the skip links: they go where they say, and a lens that does not hold the target gives way to the workbench
  document.querySelectorAll('a[data-skip]').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault();
    const name = a.getAttribute('data-skip');
    if (lensName !== 'workbench') lensFromUser('workbench');
    if (name === 'inspector' && phone()) { openSheet('inspector', null); return; }
    const t = $(name);
    if (t) t.focus();
  }));
  if (mq.addEventListener) mq.addEventListener('change', paintRoles);
  paintRoles();
  paintSheet();

  // the top bar's vitals and counts sit behind one button on a phone (the CSS shows them at any width otherwise)
  const head = document.querySelector('header.top');
  const hdrToggle = document.querySelector('.hdr-toggle');
  if (head && hdrToggle) hdrToggle.addEventListener('click', () => {
    const open = hdrToggle.getAttribute('aria-expanded') !== 'true';
    hdrToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    head.classList.toggle('open', open);
  });
  // the phone's 3D pane is as tall as what the bar leaves (CSS reads --hdr-h); tell the viewer when it changes
  let hdrH = -1;
  function phoneHeader() {
    if (!head || !phone()) return;
    const h = Math.round(head.getBoundingClientRect().height);
    if (h === hdrH) return;
    hdrH = h;
    document.documentElement.style.setProperty('--hdr-h', h + 'px');
    window.dispatchEvent(new Event('resize'));
  }
  if (window.ResizeObserver && head) new ResizeObserver(phoneHeader).observe(head);
  else window.addEventListener('resize', phoneHeader);

  // ---- the 3D toolbar and the inspector's buttons -------------------------------------------------
  function wireToolbar() {
    const ex = $('explode');
    if (ex) ex.addEventListener('input', () => { const v = viewer(); if (v) v.explode(parseFloat(ex.value)); });
    const sec = $('section');
    const axis = $('section-axis');
    const off = $('section-offset');
    if (sec) sec.addEventListener('change', () => {
      const v = viewer();
      if (v) { if (sec.checked) v.section(axis ? axis.value : 'z', off ? parseFloat(off.value) : 0.5); else v.section(false); }
    });
    const fit = $('fit');
    if (fit) fit.addEventListener('click', () => { const v = viewer(); if (v) v.fit(); });
    document.querySelectorAll('.seg [data-axis]').forEach((b) => b.addEventListener('click', () => {
      document.querySelectorAll('.seg [data-axis]').forEach((o) => o.setAttribute('aria-pressed', o === b ? 'true' : 'false'));
      if (axis) { axis.value = b.getAttribute('data-axis'); axis.dispatchEvent(new Event('change')); }
    }));
    $('inspector').addEventListener('click', (ev) => {
      const b = ev.target.closest('button[data-act]');
      const v = viewer();
      if (!b || !v) return;
      const act = b.getAttribute('data-act');
      const mine = inScene(partsOf(selected));
      syncing = true;
      try {
        if (act === 'all') { v.ghost([]); v.fit(); }
        else if (act === 'frame' && mine.length) v.frame(mine[0]);
        else if (act === 'isolate' && mine.length) v.ghost(mine);
      } finally { syncing = false; }
    });
  }

  // a click on a mesh (or on empty space: uri null) selects; our own calls are not picks
  document.addEventListener('n2f:select', (ev) => {
    if (syncing) return;
    select(ev.detail && ev.detail.uri ? ev.detail.uri : PRODUCT);
  }, true);

  // keep the sticky bar's height known to the CSS (the panes and scroll offsets are sized from it)
  function headHeight() {
    const h = document.querySelector('header.top');
    if (h && getComputedStyle(h).position === 'sticky') document.documentElement.style.setProperty('--head-h', h.offsetHeight + 'px');
  }
  headHeight();
  window.addEventListener('resize', headHeight);

  // ---- the requirements filter (kept from the old page script) -----------------------------------
  const only = $('req-open-only');
  if (only) only.addEventListener('change', () => $('req-table').classList.toggle('only-open', only.checked));

  // ---- go ----------------------------------------------------------------------------------------------
  buildTree();
  wireToolbar();
  fromHash = true;  // the first draw must not overwrite the hash applyHash is about to read
  select(PRODUCT);
  fromHash = false;
  if (location.hash.length > 1) applyHash(); else setLens(lensName);
  ready = true;
  if (window.n2fViewerReady) {
    const pane = $('model');
    // S-232: a browser with no WebGL (or one that gives up on it) leaves the tree and inspector as they are
    const noThreeD = () => {
      if (pane) pane.classList.add('off');
      dockBtns.forEach((b) => { if (b.getAttribute('data-sheet-open') === 'view') b.hidden = true; });
      if (sheet === 'view') closeSheet();
      document.querySelectorAll('[data-n2f-glb]').forEach((c) => {
        ['role', 'aria-label', 'tabindex'].forEach((a) => c.removeAttribute(a));  // the notice is text again, not a picture (S-325)
        if (c.querySelector('.n2f-fallback')) return;
        const note = el('p', { class: 'n2f-fallback' }, c.getAttribute('data-n2f-fallback') || 'This browser cannot show the 3D view.');
        note.style.cssText = 'margin:0;padding:4rem 1rem;color:#6b6a66';
        c.appendChild(note);
      });
    };
    window.n2fViewerReady.then(() => {
      const v = viewer();
      if (v && v.glState === 'unavailable') noThreeD();
      else if (v && v.glState === 'pending' && v.settled) v.settled.then((st) => { if (st === 'unavailable') noThreeD(); });
      sync3d();
    }, noThreeD);  // the viewer throws when the browser cannot make a WebGL context at all
  }
  window.n2fWorkbench = {
    select: (uri) => select(uri),
    lens: (name) => (name === undefined ? lensName : (lensFromUser(name), lensName)),
    current: () => selected,
    index,
  };
})();
