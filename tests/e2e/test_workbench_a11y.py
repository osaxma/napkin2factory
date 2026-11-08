"""M4: the workbench for the keyboard and for screen readers (V8, V9, S-325).

A prebuilt table report in Chromium, from ``file://``: a keyboard-only journey, accessible names on
every control, captions and scoped headers on every table, no status told by colour alone, badge and
status contrast at WCAG AA, a visible focus ring, one announcement per pick, and the address that only
the engineer persona sees.  The static audits also run on the test-stand (``make check-full``).
The 3D asserts read what the page says about itself, so a host with no WebGL still passes.
"""

# ruff: noqa: E501  (the embedded JavaScript and its asserts read better unbroken)
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from tests.conftest import EXAMPLES, copy_product, real_page_errors

GL_ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]
PRODUCT = "manifest://product"

# what a control or a table is called, computed the way a browser's accessibility tree does for these cases
JS_HELPERS = r"""
window.__a11y = (() => {
  const txt = (e) => (e.textContent || '').replace(/\s+/g, ' ').trim();
  const name = (e) => {
    const al = e.getAttribute('aria-label');
    if (al && al.trim()) return al.trim();
    const lb = e.getAttribute('aria-labelledby');
    if (lb) {
      const t = lb.split(/\s+/).map((id) => document.getElementById(id)).filter(Boolean).map(txt).join(' ').trim();
      if (t) return t;
    }
    if (e.labels && e.labels.length) {
      const t = Array.from(e.labels).map(txt).join(' ').trim();
      if (t) return t;
    }
    const alt = e.getAttribute('alt');
    if (alt && alt.trim()) return alt.trim();
    const t = txt(e);
    if (t) return t;
    return (e.getAttribute('title') || '').trim();
  };
  const visible = (e) => {
    if (!e.getClientRects().length) return false;
    for (let p = e; p; p = p.parentElement) if (getComputedStyle(p).visibility === 'hidden') return false;
    return true;
  };
  const describe = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ').join('.') : '');
  const unnamed = () => Array.from(document.querySelectorAll(
    'button, a[href], input, select, summary, [role=tab], [role=treeitem], [tabindex="0"]'))
    .filter((e) => visible(e) && e.type !== 'hidden' && !name(e)).map(describe);
  const lum = (rgb) => {
    const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2]);
  };
  const parse = (s) => { const m = s.match(/[\d.]+/g).map(Number); return { rgb: m.slice(0, 3), a: m.length > 3 ? m[3] : 1 }; };
  const bgOf = (e) => {
    for (let p = e; p; p = p.parentElement) {
      const c = parse(getComputedStyle(p).backgroundColor);
      if (c.a > 0.99) return c.rgb;
    }
    return [255, 255, 255];
  };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const contrast = (sel) => Array.from(document.querySelectorAll(sel)).filter((e) => txt(e)).map((e) => {
    const fg = parse(getComputedStyle(e).color).rgb;
    return { who: describe(e) + ' "' + txt(e).slice(0, 24) + '"', ratio: ratio(fg, bgOf(e)) };
  });
  return { name, visible, describe, unnamed, contrast, txt };
})();
"""


@pytest.fixture(scope="module")
def report_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    root = copy_product(
        EXAMPLES / "table", tmp_path_factory.mktemp("a11y") / "table", git=False, prebuilt=True
    )
    return (root / "build/report/index.html").as_uri()


@pytest.fixture(
    scope="module",
    params=["table", pytest.param("test-stand", marks=pytest.mark.full)],
)
def audit_url(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> str:
    """The reports the static audits read: the table always, the test-stand in check-full."""
    root = copy_product(
        EXAMPLES / request.param,
        tmp_path_factory.mktemp("a11y-" + request.param) / request.param,
        git=False,
        prebuilt=True,
    )
    return (root / "build/report/index.html").as_uri()


@pytest.fixture(scope="module")
def browser() -> Iterator[Any]:
    pytest.importorskip("playwright")
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(args=GL_ARGS)
        except Error as exc:  # browser not installed: logged in BACKLOG.md (B-0001)
            pytest.skip(f"Playwright Chromium unavailable: {exc}")
        yield b
        b.close()


class Page:
    """A page on the report that collects its errors."""

    def __init__(self, browser: Any, url: str, width: int = 1280, height: int = 900) -> None:
        self.errors: list[str] = []
        self.page = browser.new_page(viewport={"width": width, "height": height})
        self.page.set_default_timeout(15000)
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        self.page.goto(url)
        self.page.wait_for_function("window.n2fWorkbench !== undefined")
        self.page.evaluate(JS_HELPERS)
        self.index: dict[str, Any] = self.page.evaluate("window.n2fWorkbench.index")

    def ev(self, js: str) -> Any:
        return self.page.evaluate(js)

    def active(self) -> dict[str, Any]:
        return dict(
            self.ev(
                "(() => { const a = document.activeElement; return {tag: a.tagName.toLowerCase(),"
                " id: a.id, role: a.getAttribute('role'), skip: a.getAttribute('data-skip'),"
                " name: window.__a11y.name(a), uri: a.getAttribute('data-uri'),"
                " inTree: !!a.closest('#tree'), inInspector: !!a.closest('#inspector')}; })()"
            )
        )

    def tab_until(self, js_predicate: str, limit: int = 80) -> dict[str, Any]:
        """Press Tab until ``document.activeElement`` satisfies the predicate (a JS expression on ``a``)."""
        for _ in range(limit):
            self.page.keyboard.press("Tab")
            if self.ev(
                f"(() => {{ const a = document.activeElement; return !!({js_predicate}); }})()"
            ):
                return self.active()
        raise AssertionError(f"no Tab stop matched {js_predicate!r} in {limit} presses")

    def title(self) -> str:
        return str(self.page.text_content("#inspector-title")).strip()

    def status(self) -> str:
        return str(self.page.text_content("#inspector-status")).strip()

    def lenses(self) -> list[str]:
        return list(
            self.ev(
                "Array.from(document.querySelectorAll('[data-lens-tab]')).map(t => t.dataset.lensTab)"
            )
        )

    def close(self, check: bool = True) -> None:
        self.page.close()
        if check:
            assert real_page_errors(self.errors) == [], self.errors


@pytest.fixture
def open_page(browser: Any, report_url: str) -> Iterator[Any]:
    opened: list[Page] = []

    def make(url: str | None = None, **kw: int) -> Page:
        pg = Page(browser, url or report_url, **kw)
        opened.append(pg)
        return pg

    yield make
    for pg in opened:
        pg.close()


def _title_of(pg: Page, uri: str) -> str:
    e = pg.index[uri]
    return str(e.get("title") or e.get("name") or uri)


def test_a_keyboard_alone_reaches_the_3d_view_the_tree_and_the_inspector(open_page: Any) -> None:
    pg = open_page()
    # the skip link is the first stop, visible once it has focus
    pg.page.keyboard.press("Tab")
    first = pg.active()
    assert first["skip"] == "model" and first["name"] == "Skip to the 3D view"
    box = pg.ev(
        "(() => { const r = document.activeElement.getBoundingClientRect(); return [r.top, r.bottom, r.left]; })()"
    )
    assert box[0] >= 0 and box[1] > 0 and box[2] >= 0, box
    pg.page.keyboard.press("Tab")
    assert pg.active()["skip"] == "inspector"
    pg.page.keyboard.press("Shift+Tab")
    pg.page.keyboard.press("Enter")
    assert pg.active()["id"] == "model"
    # what the 3D view says to do, or its notice when the browser has no WebGL
    viewer = pg.ev(
        "(() => { const v = document.querySelector('.viewer'); return {role: v.getAttribute('role'),"
        " tab: v.getAttribute('tabindex'), label: v.getAttribute('aria-label'),"
        " notice: !!v.querySelector('.n2f-fallback')}; })()"
    )
    if viewer["notice"]:
        assert viewer["role"] is None  # a picture hides its text from a screen reader
    else:
        assert viewer["role"] == "img" and viewer["tab"] == "0"
        assert "Choose a part in the parts tree" in viewer["label"]
    # the tree is one tab stop; arrows and Enter pick a part, focus stays on the item
    pg.page.keyboard.press("Shift+Tab")
    assert pg.active()["role"] == "treeitem" and pg.active()["name"] == "Product"
    items = pg.ev(
        "Array.from(document.querySelectorAll('#tree li[role=treeitem]'))"
        ".filter(li => li.getClientRects().length).map(li => li.dataset.uri || '')"
    )
    pg.page.keyboard.press("ArrowDown")
    pg.page.keyboard.press("ArrowDown")
    pg.page.keyboard.press("Enter")
    uri = items[2]
    assert uri and pg.ev("window.n2fWorkbench.current()") == uri
    assert pg.title() == _title_of(pg, uri)
    assert pg.status() == "Selected: " + _title_of(pg, uri)
    assert pg.active()["inTree"] and pg.active()["uri"] == uri
    # Home and End walk the visible items
    pg.page.keyboard.press("End")
    assert (pg.active()["uri"] or "") == items[-1]
    pg.page.keyboard.press("Home")
    assert pg.active()["name"] == "Product"
    # Escape clears the selection and keeps focus in the tree
    pg.page.keyboard.press("Escape")
    assert pg.ev("window.n2fWorkbench.current()") == PRODUCT
    assert pg.title() == _title_of(pg, PRODUCT)
    assert pg.status() == "Selected: " + _title_of(pg, PRODUCT)
    assert pg.active()["inTree"]
    # from the inspector too: focus goes back to the tree's current item
    pg.ev("window.n2fWorkbench.select('part://top-board')")
    pg.ev("document.getElementById('inspector-title').focus()")
    assert pg.active()["inInspector"]
    pg.page.keyboard.press("Escape")
    assert pg.ev("window.n2fWorkbench.current()") == PRODUCT and pg.active()["inTree"]
    # a link that selects leaves focus in the inspector (its own link is gone), not on the page's top
    pg.ev("window.n2fWorkbench.select('part://top-board')")
    pg.page.focus("#inspector-entry a.ref")
    pg.page.keyboard.press("Enter")
    pg.page.wait_for_function("window.n2fWorkbench.current() !== 'part://top-board'")
    assert pg.active()["inInspector"]


def test_the_lens_tabs_are_one_tab_stop_with_arrows_home_and_end(open_page: Any) -> None:
    pg = open_page()
    lenses = pg.lenses()
    assert pg.ev("document.querySelectorAll('[role=tab][tabindex=\"0\"]').length") == 1
    pg.tab_until("a.getAttribute('role') === 'tab'")
    pg.page.keyboard.press("End")
    assert pg.ev("window.n2fWorkbench.lens()") == lenses[-1]
    assert pg.active()["id"] == "tab-" + lenses[-1]
    pg.page.keyboard.press("Home")
    assert pg.ev("window.n2fWorkbench.lens()") == lenses[0]
    pg.page.keyboard.press("ArrowRight")
    assert pg.ev("window.n2fWorkbench.lens()") == lenses[1]
    assert pg.ev("document.querySelectorAll('[role=tab][tabindex=\"0\"]').length") == 1


def test_the_landmarks_the_live_region_and_the_inspector_are_labelled(open_page: Any) -> None:
    pg = open_page()
    assert pg.ev("document.querySelector('header.top').parentElement === document.body")
    assert pg.ev("document.querySelectorAll('main').length") == 1
    assert pg.ev("document.querySelector('[role=tablist]').getAttribute('aria-label')")
    assert pg.ev("document.querySelector('#tree').getAttribute('aria-label')")
    assert pg.ev("document.querySelector('#inspector').getAttribute('aria-label')")
    # the whole inspector is not a live region; one small status says what was picked
    assert pg.ev("document.querySelector('#inspector').closest('[aria-live]')") is None
    assert pg.ev("document.querySelectorAll('#inspector [aria-live]').length") == 0
    assert pg.ev("document.querySelectorAll('[role=status]#inspector-status').length") == 1
    pg.ev("window.n2fWorkbench.select('part://top-board')")
    assert pg.status() == "Selected: " + _title_of(pg, "part://top-board")
    # every tree item is named by its own label, not by the children it holds
    names = pg.ev(
        "Array.from(document.querySelectorAll('#tree li[role=treeitem]')).map(li => li.getAttribute('aria-label'))"
    )
    assert all(names)


def _lens_audit(pg: Page, js: str) -> dict[str, Any]:
    """Run an expression on every lens the page has (each shown in turn) and collect what it returns."""
    out: dict[str, Any] = {}
    for lens in pg.lenses():
        pg.ev(f"window.n2fWorkbench.lens({lens!r})")
        out[lens] = pg.ev(js)
    return out


def test_every_visible_control_has_a_name(open_page: Any, audit_url: str) -> None:
    pg = open_page(audit_url)
    if "part://top-board" in pg.index:  # so the inspector's own markup is audited too
        pg.ev("window.n2fWorkbench.select('part://top-board')")
    bad = {k: v for k, v in _lens_audit(pg, "window.__a11y.unnamed()").items() if v}
    assert bad == {}, bad


def test_every_control_has_a_name_on_a_phone_with_each_sheet_open(
    open_page: Any, report_url: str
) -> None:
    pg = open_page(report_url, width=390, height=844)
    assert pg.ev("window.__a11y.unnamed()") == []
    for sheet in ("tree", "inspector", "view"):
        btn = f"[data-sheet-open={sheet}]"
        if not pg.page.is_visible(btn):
            continue
        pg.page.click(btn)
        assert pg.ev("window.__a11y.unnamed()") == [], sheet
        pg.page.keyboard.press("Escape")
    # the three close buttons say which sheet they close
    closes = pg.ev(
        "Array.from(document.querySelectorAll('[data-sheet-close]')).map(b => b.getAttribute('aria-label'))"
    )
    assert len(set(closes)) == len(closes) and all(closes)


def test_every_table_has_a_caption_and_scoped_headers(open_page: Any, audit_url: str) -> None:
    pg = open_page(audit_url)
    uris = [u for u in ("part://top-board",) if u in pg.index]
    if uris:
        pg.ev(f"window.n2fWorkbench.select({uris[0]!r})")
        assert pg.ev("document.querySelectorAll('#inspector-entry table').length") >= 1
    bad = pg.ev(
        """(() => {
          const out = [];
          for (const t of document.querySelectorAll('table')) {
            const cap = t.querySelector(':scope > caption');
            const named = (cap && cap.textContent.trim()) || t.getAttribute('aria-label');
            const ths = Array.from(t.querySelectorAll('th'));
            const scopes = ['col', 'row', 'colgroup', 'rowgroup'];
            if (!named) out.push('no caption: ' + window.__a11y.describe(t));
            if (!ths.length) out.push('no header cells: ' + (named || window.__a11y.describe(t)));
            for (const th of ths) if (scopes.indexOf(th.getAttribute('scope')) < 0) out.push('no scope: ' + (named || '') + ' / ' + th.textContent.trim().slice(0, 20));
          }
          return out;
        })()"""
    )
    assert bad == [], bad[:10]


def test_no_status_is_told_by_colour_alone(open_page: Any, audit_url: str) -> None:
    pg = open_page(audit_url)
    bad = pg.ev(
        """(() => {
          const out = [];
          const T = window.__a11y.txt;
          for (const e of document.querySelectorAll('.dot'))
            if (e.getAttribute('aria-hidden') !== 'true' && !T(e) && !e.getAttribute('aria-label')) out.push('dot without words');
          for (const e of document.querySelectorAll('.badge')) if (!T(e)) out.push('empty badge');
          for (const e of document.querySelectorAll('td.stc, td[class*=" st-"], span[class^="st-"]')) if (!T(e)) out.push('empty status');
          // a matrix cell says the same word as the legend's dot of its colour
          const legend = {};
          for (const s of document.querySelectorAll('.legend span')) {
            const d = s.querySelector('.dot');
            if (d) legend[d.className.replace('dot', '').trim()] = T(s);
          }
          for (const e of document.querySelectorAll('.matrix td .dot')) {
            const k = e.className.replace('dot', '').trim();
            if (legend[k] && T(e) !== legend[k]) out.push('matrix cell says "' + T(e) + '", legend says "' + legend[k] + '"');
          }
          return out;
        })()"""
    )
    assert bad == [], bad[:10]


def test_badges_and_status_text_reach_aa_contrast(open_page: Any, audit_url: str) -> None:
    pg = open_page(audit_url)
    if "part://top-board" in pg.index:  # so the inspector's own markup is audited too
        pg.ev("window.n2fWorkbench.select('part://top-board')")
    rows = pg.ev(
        "window.__a11y.contrast('.badge, .st-pass, .st-signed, .st-fail, .st-warn, .st-needs-human, .muted')"
    )
    assert len(rows) >= 5
    low = sorted((r["ratio"], r["who"]) for r in rows if r["ratio"] < 4.5)
    assert low == [], low[:8]


def test_a_keyboard_focus_shows_a_ring(open_page: Any) -> None:
    pg = open_page()
    pg.ev("window.n2fWorkbench.select('part://top-board')")
    pg.ev("document.activeElement.blur()")
    ring = (
        "(() => { const a = document.activeElement;"
        " const t = a.getAttribute('role') === 'treeitem' ? a.querySelector(':scope > .row') || a : a;"
        " const s = getComputedStyle(t); const li = a.closest('li:has(a:focus-visible)');"
        " const l = li ? getComputedStyle(li) : null;"
        " return [s.outlineStyle, parseFloat(s.outlineWidth), l ? l.outlineStyle : null, l ? parseFloat(l.outlineWidth) : 0]; })()"
    )
    seen = {}
    for kind, pred in {
        "tab": "a.getAttribute('role') === 'tab'",
        "tree item": "a.getAttribute('role') === 'treeitem'",
        "button": "a.tagName === 'BUTTON' && !!a.closest('.toolbar3d, #inspector')",
        "link": "a.tagName === 'A' && !!a.closest('#inspector')",
    }.items():
        pg.tab_until(pred)
        style, width, li_style, li_width = pg.ev(ring)
        # a link inside a list that clips its names carries the ring on its row
        has = (style != "none" and width > 0) or (li_style not in (None, "none") and li_width > 0)
        seen[kind] = has
    assert seen == {"tab": True, "tree item": True, "button": True, "link": True}, seen


def test_the_address_shows_for_the_engineer_persona_only(open_page: Any) -> None:
    pg = open_page()
    uri = "part://top-board"
    pg.ev(f"window.n2fWorkbench.select({uri!r})")
    shown = "(() => { const a = document.querySelector('#inspector-head .addr'); return [getComputedStyle(a).display, a.textContent]; })()"
    pg.ev("document.documentElement.dataset.persona = 'engineer'")
    display, text = pg.ev(shown)
    assert display != "none" and uri in text
    pg.ev("document.documentElement.dataset.persona = 'owner'")
    display, text = pg.ev(shown)
    assert display == "none" and uri in text  # hidden, but the text stays for deep links
    # no dangling separator: what is left reads "Custom part" and nothing else
    assert (
        pg.ev("document.querySelector('#inspector-head .kindline').innerText.trim()")
        == "Custom part"
    )


def test_headings_never_skip_a_level(open_page: Any, audit_url: str) -> None:
    pg = open_page(audit_url)
    bad = _lens_audit(
        pg,
        """(() => {
          let prev = 0; const out = [];
          for (const h of document.querySelectorAll('h1, h2, h3, h4, h5, h6')) {
            if (!window.__a11y.visible(h)) continue;
            const n = Number(h.tagName[1]);
            if (prev && n > prev + 1) out.push('h' + prev + ' then h' + n + ': ' + h.textContent.trim().slice(0, 30));
            prev = n;
          }
          return out;
        })()""",
    )
    assert {k: v for k, v in bad.items() if v} == {}, bad
