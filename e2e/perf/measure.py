# e2e/perf/measure.py
"""Measurement procedure of the browser-tier benchmark: one cell, one rep.

The timing lives IN the page — ``performance.now`` around the interaction,
resolved when the DOM condition holds and one more frame has painted —
because a Playwright round trip per check would itself be the measurement at
this scale. CDP's Performance domain adds how long the main thread was busy
(TaskDuration and its script / style / layout parts), and websocket frames are
counted because Streamlit resends the whole options payload on every rerun.
``roundtrip_ms`` ends when the status line shows the rerun; ``settled_ms`` ends
when the frontend's work after it has finished (long tasks ≥ 50 ms are what it
can see).

The helpers are installed with ``page.add_init_script`` as ``window.__bench``.
Playwright's own locators pierce the component's shadow root, but a script
running inside the page does not, so ``root()`` walks every shadow root once
and ``byId`` resolves rows through ``getRootNode().getElementById`` — the same
id-map lookup the component uses for aria-activedescendant.

Graduated from the 2026-10-03 virtualization spike's throwaway harness.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass

from playwright.sync_api import Browser, CDPSession, Page

from e2e.perf.cells import REPO_ROOT, Cell

# The ids and search text this module drives come from the SAME generator, at
# the same n, the harness renders — the pattern e2e/test_performance.py uses.
sys.path.insert(0, str(REPO_ROOT / "demo"))
from data import make_large_dataset  # noqa: E402

INIT_JS = r"""
window.__bench = {
  // The walk visits every element of the light DOM, and byId() asks once per
  // frame inside until(), so the found root is cached and only re-walked when
  // the cached element has left the document (a rerun or a "show" remount).
  root() {
    if (this._root && this._root.isConnected) return this._root;
    const stack = [document];
    while (stack.length) {
      const node = stack.pop();
      const hit = node.querySelector('[data-testid="stListview"]');
      if (hit) return (this._root = hit);
      for (const el of node.querySelectorAll('*')) if (el.shadowRoot) stack.push(el.shadowRoot);
    }
    return null;
  },
  byId(id) {
    const root = this.root();
    return root ? root.getRootNode().getElementById('listview-opt-' + id) : null;
  },
  frame() { return new Promise((resolve) => requestAnimationFrame(() => resolve())); },
  async until(cond, what, timeoutMs) {
    const t0 = performance.now();
    while (!cond()) {
      if (performance.now() - t0 > (timeoutMs || 240000)) throw new Error('benchmark timeout waiting for ' + what);
      await this.frame();
    }
  },
  async painted() { await this.frame(); await new Promise((resolve) => setTimeout(resolve, 0)); },
  // The frontend renders a rerun's payload after the status line shows it, so a
  // window closed on the status line misses that work. Long tasks (>= 50 ms) are
  // the only main-thread work visible from inside the page: watchLongTasks()
  // before the interaction, settled() after the scenario's own window closed.
  watchLongTasks() {
    const ends = [];
    const record = (entries) => { for (const e of entries) ends.push(e.startTime + e.duration); };
    const observer = new PerformanceObserver((list) => record(list.getEntries()));
    observer.observe({ type: 'longtask' });
    return { ends, observer, record };
  },
  // Resolves, in the clock of t0, to when the page went quiet: the later of
  // `endedAt` (when the scenario's own window closed) and the end of the last
  // long task, once 300 ms have passed after both with no new long task.
  async settled(watch, t0, endedAt) {
    const start = performance.now();
    let last = endedAt;
    for (;;) {
      watch.record(watch.observer.takeRecords());
      for (const end of watch.ends) last = Math.max(last, end);
      const now = performance.now();
      if (now - last >= 300) break;
      if (now - start > 240000) throw new Error('benchmark timeout waiting for the page to settle');
      await this.frame();
    }
    watch.observer.disconnect();
    return last - t0;
  },
  status() {
    for (const el of document.querySelectorAll('[data-testid="stText"]'))
      if (el.textContent.includes('BENCH')) return el.textContent;
    return '';
  },
  button(label) {
    for (const b of document.querySelectorAll('button')) if (b.textContent.trim() === label) return b;
    return null;
  },
  setInput(el, value) {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  },
  search() { return this.root().querySelector('[data-testid="stListviewSearch"]'); },
  newOption() { return this.root().querySelector('[data-testid="stListviewNewOption"]'); },
  header() { return this.root().querySelector('button.listview-group-header--collapsible'); },
};
"""

# Each snippet returns the scenario's timings; `rows_ms` is wall time until the
# DOM condition holds, `painted_ms` adds one animation frame plus a macrotask.
MOUNT_JS = """async ([lastId]) => {
  const b = window.__bench;
  const t0 = performance.now();
  b.button('show').click();
  await b.until(() => b.byId(lastId) !== null, 'the last row after show');
  const rows = performance.now() - t0;
  await b.painted();
  return { rows_ms: rows, painted_ms: performance.now() - t0 };
}"""

SEARCH_JS = """async ([value, goneId, presentId, what]) => {
  const b = window.__bench;
  const t0 = performance.now();
  b.setInput(b.search(), value);
  await b.until(
    () => (goneId === null || b.byId(goneId) === null) && (presentId === null || b.byId(presentId) !== null),
    what,
  );
  const rows = performance.now() - t0;
  await b.painted();
  return { rows_ms: rows, painted_ms: performance.now() - t0 };
}"""

# Clicks the named button and waits for the status line's counter to advance;
# for "edit" also for row N/2 to show (or drop) the edited label.
RERUN_JS = """async ([label, counter, midId, expectEdited]) => {
  const b = window.__bench;
  const before = Number(b.status().match(new RegExp(counter + '=(\\\\d+)'))[1]);
  const advanced = new RegExp(counter + '=' + (before + 1) + '(\\\\s|$)');
  const watch = b.watchLongTasks();
  const t0 = performance.now();
  b.button(label).click();
  await b.until(() => advanced.test(b.status()), 'the status line to count the ' + label);
  if (midId !== null) {
    await b.until(() => b.byId(midId).textContent.includes('(edited)') === expectEdited, 'row N/2 to show the edited label');
  }
  await b.painted();
  const endedAt = performance.now();
  return { roundtrip_ms: endedAt - t0, settled_ms: await b.settled(watch, t0, endedAt) };
}"""

CLICK_JS = """async ([id]) => {
  const b = window.__bench;
  const row = b.byId(id);
  const watch = b.watchLongTasks();
  const t0 = performance.now();
  row.click();
  await b.until(() => b.byId(id).getAttribute('aria-selected') === 'true', 'the clicked row to be selected');
  await b.painted();
  const local = performance.now() - t0;
  await b.until(() => b.status().includes('sel=' + id + ' '), 'the selection to echo back');
  await b.painted();
  const endedAt = performance.now();
  return { local_painted_ms: local, roundtrip_ms: endedAt - t0, settled_ms: await b.settled(watch, t0, endedAt) };
}"""

GROUP_JS = """async ([firstId, expectCollapsed]) => {
  const b = window.__bench;
  const header = b.header();
  if (header === null) throw new Error('benchmark precondition failed: the first group header is a toggle');
  const t0 = performance.now();
  header.click();
  await b.until(() => (b.byId(firstId) === null) === expectCollapsed,
    expectCollapsed ? 'the first group to collapse' : 'the first group to expand');
  const rows = performance.now() - t0;
  await b.painted();
  return { rows_ms: rows, painted_ms: performance.now() - t0 };
}"""

# Typing is local input state; the Enter commit builds the synthetic row and
# runs the "already in the list?" lookup, so only the Enter is timed.
ADD_OPTION_JS = """async ([value]) => {
  const b = window.__bench;
  const input = b.newOption();
  if (input === null) throw new Error('benchmark precondition failed: the add-option input renders');
  b.setInput(input, value);
  const t0 = performance.now();
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
  await b.until(() => b.byId(value) !== null, 'the added option to render');
  const rows = performance.now() - t0;
  await b.painted();
  return { rows_ms: rows, painted_ms: performance.now() - t0 };
}"""

SCROLL_JS = """async () => {
  const b = window.__bench;
  const body = b.root().querySelector('.listview-body');
  const max = body.scrollHeight - body.clientHeight;
  const steps = 60;
  const deltas = [];
  let prev = performance.now();
  for (let i = 1; i <= steps; i++) {
    body.scrollTop = (max * i) / steps;
    await b.frame();
    const now = performance.now();
    deltas.push(now - prev);
    prev = now;
  }
  body.scrollTop = 0;
  await b.painted();
  deltas.sort((x, y) => x - y);
  return { p50_ms: deltas[steps >> 1], p95_ms: deltas[Math.floor(steps * 0.95)], max_ms: deltas[steps - 1] };
}"""

METRIC_KEYS = ("ScriptDuration", "LayoutDuration", "RecalcStyleDuration", "TaskDuration")


@dataclass(frozen=True)
class CellIds:
    first: str
    last: str
    mid: str
    needle: str  # the last label's zero-padded number: unique among the labels


def cell_ids(n: int) -> CellIds:
    rows = make_large_dataset(n)
    return CellIds(
        first=rows[0]["id"],
        last=rows[-1]["id"],
        mid=rows[n // 2]["id"],
        needle=rows[-1]["label"].split()[-1],
    )


def _metrics(cdp: CDPSession) -> dict[str, float]:
    return {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}


def _busy(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    """Main-thread time between two metric snapshots, per CDP duration counter."""
    return {
        key.replace("Duration", "").lower() + "_ms": round((after[key] - before[key]) * 1000, 1)
        for key in METRIC_KEYS
    }


def _status_fields(page: Page) -> dict[str, float]:
    text = page.evaluate("() => window.__bench.status()")
    return {k: float(v) for k, v in re.findall(r"(py_ms|options_bytes)=([\d.]+)", text)}


def _open(browser: Browser, throttle: int) -> tuple[Page, CDPSession, list[int]]:
    """A fresh context (fresh Streamlit session state) with the helpers, CDP metrics and ws counting."""
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.set_default_timeout(300_000)
    page.add_init_script(INIT_JS)
    ws_bytes = [0]
    page.on(
        "websocket",
        lambda ws: ws.on(
            "framereceived",
            lambda payload: ws_bytes.__setitem__(0, ws_bytes[0] + len(payload)),
        ),
    )
    cdp = context.new_cdp_session(page)
    cdp.send("Performance.enable")
    if throttle > 1:
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": throttle})
    return page, cdp, ws_bytes


def _show(page: Page, cdp: CDPSession, ws_bytes: list[int], url: str, last_id: str) -> dict:
    """Navigate, wait for the harness, mount the list via "show"; returns the mount record.

    The CDP window and the websocket count open after the page has loaded and
    settled, just before the "show" click, and close after the post-mount wait:
    they cover the mount alone, not Streamlit's page bootstrap.
    """
    page.goto(url)
    page.wait_for_function(
        "() => window.__bench.status().includes('hidden rerun=1') && window.__bench.button('show') !== null"
    )
    page.wait_for_timeout(800)  # let Streamlit's first run settle before anything is timed
    before, ws_bytes[0] = _metrics(cdp), 0
    timings = page.evaluate(MOUNT_JS, [last_id])
    page.wait_for_function("() => window.__bench.status().includes('py_ms=')")
    page.wait_for_timeout(1200)  # let the post-mount work and any trailing rerun settle before the next scenario
    timings.update(_busy(before, _metrics(cdp)), ws_bytes=ws_bytes[0])
    return timings


def run_cell(browser: Browser, server_url: str, cell: Cell, throttle: int) -> dict:
    ids = cell_ids(cell.n)
    record: dict = {"n": cell.n, "grouped": cell.grouped, "throttle": throttle}
    base_url = f"{server_url}/?n={cell.n}&grouped={int(cell.grouped)}"

    page, cdp, ws_bytes = _open(browser, throttle)
    try:
        # 1) mount: "show" -> Python builds the listview -> the frontend renders.
        record["mount"] = _show(page, cdp, ws_bytes, base_url, ids.last)
        record["py_mount"] = _status_fields(page)
        cdp.send("HeapProfiler.collectGarbage")
        metrics = _metrics(cdp)
        record["dom_nodes"] = metrics["Nodes"]
        record["heap_mb"] = round(metrics["JSHeapUsedSize"] / 2**20, 1)

        # 2) search: narrow N -> 1, then clear 1 -> N.
        before = _metrics(cdp)
        record["search_narrow"] = page.evaluate(
            SEARCH_JS, [ids.needle, ids.first, ids.last, "the needle to leave the last row"]
        )
        record["search_clear"] = page.evaluate(
            SEARCH_JS, ["", None, ids.first, "the first row to return after clearing"]
        )
        page.wait_for_timeout(500)
        record["search_busy"] = _busy(before, _metrics(cdp))

        # 3) rerun with the options unchanged (an unrelated button).
        before, ws_bytes[0] = _metrics(cdp), 0
        record["rerun_unchanged"] = page.evaluate(RERUN_JS, ["rerun", "rerun", None, False])
        page.wait_for_timeout(1500)
        record["rerun_unchanged"].update(_busy(before, _metrics(cdp)), ws_bytes=ws_bytes[0])
        record["py_rerun"] = {"py_ms": _status_fields(page)["py_ms"]}

        # 4) rerun with one option changed: the first "edit" flips row N/2's label on.
        before = _metrics(cdp)
        record["rerun_one_changed"] = page.evaluate(RERUN_JS, ["edit", "edit", ids.mid, True])
        page.wait_for_timeout(1500)
        record["rerun_one_changed"].update(_busy(before, _metrics(cdp)))

        # 5) click a row: local highlight, then the selection's round trip.
        before = _metrics(cdp)
        record["click_select"] = page.evaluate(CLICK_JS, [ids.first])
        page.wait_for_timeout(1500)
        record["click_select"].update(_busy(before, _metrics(cdp)))

        # 6) collapse and expand the first group (grouped shape only).
        if cell.grouped:
            record["group_collapse"] = page.evaluate(GROUP_JS, [ids.first, True])
            record["group_expand"] = page.evaluate(GROUP_JS, [ids.first, False])

        # 7) scroll through the whole list.
        record["scroll"] = page.evaluate(SCROLL_JS)
    finally:
        page.context.close()

    # 8) add_option on a page of its own: accept_new_options changes the list's
    # configuration, so the scenarios above ran the plain one.
    page, cdp, ws_bytes = _open(browser, throttle)
    try:
        _show(page, cdp, ws_bytes, base_url + "&newopt=1", ids.last)
        page.evaluate(CLICK_JS, [ids.first])  # "with one row selected"
        page.wait_for_timeout(1500)
        record["add_option"] = page.evaluate(ADD_OPTION_JS, ["bench-added"])
    finally:
        page.context.close()
    return record
