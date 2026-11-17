"""Build ishikari-flow.svg: a car carries one task along the exact path.

Reads the rendered ishikari.svg, tags every block and arrow with its D2 name,
and adds a script that drives the car slowly along each arrow of each route in ROUTES. The
buttons under the caption, or the keys + - and space, change speed live.
Clicking a block shows only its arrows; Esc goes back to the tour.
The car leaves a trace; blocks and arrows light up when the task reaches
them; everything not yet reached stays dim.

Run: python3 flow.py  (render.sh runs it after ishikari.svg is built)
"""

import base64
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).parent

# Routes the car drives, one after another. Each step: [arrow, reverse?, caption].
# reverse=True drives the car from the arrow's end back to its start.
FIX_ROUND = [
    ["fix.(bounty -> detective)[0]", False, "A detective ant takes the bug."],
    ["(fix.detective -> build.aw)[0]", False, "It writes a fix plan for a worker ant."],
    ["(build.aw -> check.monitor)[0]", False, "The worker builds the fix; the build script sees it."],
    ["check.(monitor -> inspector)[0]", False, "It sends the fix to the same inspector."],
]

ROUTES = [
    {
        "name": "Route 1 of 2: a bug, fixed on the first try",
        "steps": [
            ["plan.(task -> arta)[0]", False, "A task arrives. The investigator ant reads it."],
            ["plan.(arta <-> research)[0]", False, "It sends researcher ants for missing facts."],
            ["plan.(arta <-> research)[0]", True, "They report back."],
            ["(plan.arta <-> user)[0]", False, "It asks you one question at a time."],
            ["(plan.arta <-> user)[0]", True, "You answer. The review is done."],
            ["plan.(arta -> aara)[0]", False, "Your answers go to the add requirement ant."],
            ["plan.(aara -> plans)[0]", False, "It drafts the requirement and writes the plans."],
            ["(plan.plans -> build.aw)[0]", False, "Worker ants start, each in its own worktree."],
            ["build.(aw -> bulletin)[0]", False, "A worker finishes its build."],
            ["(check.monitor -> build.bulletin)[0]", True, "The build script sees it at once."],
            ["check.(monitor -> inspector)[0]", False, "It starts an inspector ant for this task."],
            ["(check.inspector -> fix.bounty)[0]", False, "The inspector finds a bug and posts it."],
            *FIX_ROUND,
            ["check.(inspector -> together)[0]", False, "All tasks checked: the merger ant tests them together."],
            ["(check.together -> build.bulletin)[0]", False, "They work together. No review needed."],
            ["(build.bulletin -> finish.merger)[0]", False, "The merger ant merges passing tasks in a scratch copy."],
            ["(finish.merger -> always_on)[0]", False, "The janitor and philosopher ants run."],
            ["always_on.(philosopher -> critiques)[0]", False, "The philosopher keeps its 5 best critiques."],
            ["(always_on -> finish.finisher)[0]", False, "Then the finisher ant moves main forward."],
            ["(finish.finisher -> build.bulletin)[0]", False, "Main moved. Status: done."],
            ["(always_on.critiques -> plan.arta)[0]", False, "Next task: the investigator ant asks you about critiques."],
            ["(always_on.janitor -> plan.plans)[0]", False, "The janitor's cleanup plan is offered next time."],
        ],
    },
    {
        "name": "Route 2 of 2: a stuck worker, 3 failed fixes, dropped",
        "steps": [
            ["(plan.plans -> build.aw)[0]", False, "The plans go to the worker ants."],
            ["(build.aw -> fix.bounty)[0]", False, "A worker gets stuck and posts a bug."],
            *[[a, r, f"Try 1: {c}"] for a, r, c in FIX_ROUND],
            ["(check.inspector -> fix.bounty)[0]", False, "Still broken. Back on the bounty board."],
            *[[a, r, f"Try 2: {c}"] for a, r, c in FIX_ROUND],
            ["(check.inspector -> fix.bounty)[0]", False, "Still broken. Back on the bounty board."],
            *[[a, r, f"Try 3: {c}"] for a, r, c in FIX_ROUND],
            ["(check.inspector -> fix.bounty)[0]", False, "Still broken after 3 tries."],
            ["fix.(bounty -> detective)[0]", False, "The detective stops trying."],
            ["(fix.detective -> build.bulletin)[0]", False, "The task is dropped and listed in the report."],
        ],
    },
]

SCRIPT = r"""
(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.querySelector('svg svg') || document.documentElement;
  const ROUTES = __ROUTES__;
  const BASE = 70;       // px per second at 1x: slow
  const PAUSE = 1800;    // ms at each block, at 1x
  const RESTART = 4000;  // ms between routes, at 1x
  const SPEEDS = [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4];
  let si = 3, paused = false, focused = null;
  const rate = () => (paused || focused) ? 0 : SPEEDS[si];

  const edges = {}, nodes = {};
  svg.querySelectorAll('[data-edge]').forEach(g => edges[g.dataset.edge] = g);
  svg.querySelectorAll('[data-node]').forEach(g => nodes[g.dataset.node] = g);
  const all = [...Object.values(edges), ...Object.values(nodes)];

  const endpoints = name => {
    const m = name.match(/^(?:(.*?)\.)?\((.+?) (?:->|<->) (.+?)\)\[\d+\]$/);
    const pre = m[1] ? m[1] + '.' : '';
    return [pre + m[2], pre + m[3]];
  };
  const withParents = id => id.split('.').map((_, i, p) => p.slice(0, i + 1).join('.'));
  const light = id => withParents(id).forEach(n => nodes[n] && nodes[n].classList.add('lit'));
  const el = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };

  const layer = el('g', {}, svg);
  const car = el('g', { class: 'car' }, svg);
  car.innerHTML = '<circle r="22" fill="#FDE68A" stroke="#B45309" stroke-width="3"/>' +
    '<text text-anchor="middle" dominant-baseline="central" font-size="26">🚗</text>';

  // Caption and live speed controls.
  const ui = el('g', { 'font-family': 'sans-serif' }, svg);
  el('rect', { x: -80, y: 1250, width: 1150, height: 110, rx: 12, fill: '#0F172A', opacity: 0.92 }, ui);
  const title = el('text', { x: -56, y: 1282, 'font-size': 20, fill: '#FBBF24' }, ui);
  const capText = el('text', { x: -56, y: 1330, 'font-size': 26, fill: '#F8FAFC' }, ui);
  const setPause = v => { paused = v; pauseLabel.textContent = paused ? '▶' : '❚❚'; show(); };
  const faster = () => { si = Math.min(SPEEDS.length - 1, si + 1); show(); };
  const slower = () => { si = Math.max(0, si - 1); show(); };
  const btn = (x, label, fn, w) => {
    const g = el('g', { cursor: 'pointer', transform: `translate(${x},1262)` }, ui);
    el('rect', { width: w, height: 40, rx: 8, fill: '#334155', stroke: '#94A3B8' }, g);
    const t = el('text', { x: w / 2, y: 28, 'text-anchor': 'middle', 'font-size': 22, fill: '#F8FAFC' }, g);
    t.textContent = label;
    g.addEventListener('click', fn);
    return t;
  };
  btn(780, '−', slower, 56);
  const pauseLabel = btn(846, '❚❚', () => setPause(!paused), 90);
  btn(946, '+', faster, 56);
  const speedText = el('text', { x: 919, y: 1342, 'text-anchor': 'middle', 'font-size': 18, fill: '#CBD5E1' }, ui);
  const show = () => speedText.textContent = paused ? 'paused   (keys: + - space)' : `speed ${SPEEDS[si]}x   (keys: + - space)`;
  document.addEventListener('keydown', e => {
    if (e.key === '+' || e.key === '=' || e.key === 'ArrowUp') faster();
    if (e.key === '-' || e.key === 'ArrowDown') slower();
    if (e.key === ' ') { e.preventDefault(); setPause(!paused); }
  });
  show();

  // A clock that runs at the live rate, so speed changes act mid-arrow.
  const frame = () => new Promise(r => requestAnimationFrame(r));
  async function wait(ms) {
    let left = ms, last = performance.now();
    while (left > 0) { const now = await frame(); left -= (now - last) * rate(); last = now; }
  }
  async function drive(path, rev) {
    const len = path.getTotalLength();
    const trace = path.cloneNode(false);
    ['marker-end', 'marker-start', 'mask'].forEach(a => trace.removeAttribute(a));
    trace.setAttribute('class', 'trace');
    trace.style.strokeDasharray = len + ' ' + len;
    layer.appendChild(trace);
    let d = 0, last = performance.now();
    for (;;) {
      const p = path.getPointAtLength(rev ? len - d : d);
      car.setAttribute('transform', `translate(${p.x},${p.y})`);
      trace.style.strokeDashoffset = rev ? -(len - d) : len - d;
      if (d >= len) break;
      const now = await frame();
      d = Math.min(len, d + (now - last) / 1000 * BASE * rate());
      last = now;
    }
  }

  async function run() {
    for (;;) for (const route of ROUTES) {
      layer.innerHTML = '';
      all.forEach(g => g.classList.remove('lit', 'now'));
      title.textContent = route.name;
      for (const [name, rev, caption] of route.steps) {
        const g = edges[name];
        if (!g) continue;
        const [from, to] = endpoints(name);
        const start = rev ? to : from, end = rev ? from : to;
        light(start);
        capText.textContent = caption;
        g.classList.add('lit', 'now');
        await drive(g.querySelector('path'), rev);
        g.classList.remove('now');
        light(end);
        nodes[end] && nodes[end].classList.add('now');
        await wait(PAUSE);
        nodes[end] && nodes[end].classList.remove('now');
      }
      capText.textContent = 'Route done. Next route soon.';
      await wait(RESTART);
    }
  }
  // Click a block: show only its arrows and the blocks they join; dim the rest.
  // Click it again, click empty space or press Esc to go back to the tour.
  let savedCaption = '';
  const label = id => { const t = nodes[id] && nodes[id].querySelector('text'); return t ? t.textContent : id; };
  function focus(id) {
    if (!focused) savedCaption = capText.textContent;
    unfocus(false);
    focused = id;
    const inside = n => n === id || n.startsWith(id + '.');
    nodes[id].classList.add('on');
    withParents(id).forEach(n => nodes[n] && nodes[n].classList.add('on'));
    let count = 0;
    for (const name in edges) {
      const [a, b] = endpoints(name);
      if (!inside(a) && !inside(b)) continue;
      count++;
      edges[name].classList.add('on');
      [a, b].forEach(n => withParents(n).forEach(x => nodes[x] && nodes[x].classList.add('on')));
    }
    svg.classList.add('focus');
    capText.textContent = `${label(id)}: ${count} arrows. Click it again or press Esc to go back.`;
  }
  function unfocus(restore = true) {
    if (!focused) return;
    svg.classList.remove('focus');
    svg.querySelectorAll('.on').forEach(g => g.classList.remove('on'));
    focused = null;
    if (restore) capText.textContent = savedCaption;
  }
  for (const id in nodes) {
    nodes[id].style.cursor = 'pointer';
    nodes[id].addEventListener('click', e => {
      e.stopPropagation();
      const deepest = e.currentTarget.dataset.node;
      if (focused === deepest) unfocus(); else focus(deepest);
    });
  }
  svg.addEventListener('click', e => { if (!ui.contains(e.target)) unfocus(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') unfocus(); });

  run();
})();
"""

STYLE = """
[data-edge], [data-node] { opacity: 0.12; transition: opacity 1.2s ease; }
[data-edge].lit, [data-node].lit { opacity: 1; }
[data-node].now > .shape { filter: drop-shadow(0 0 10px #F59E0B) drop-shadow(0 0 4px #F59E0B); }
[data-edge].now path { stroke-width: 4 !important; }
svg.focus [data-edge], svg.focus [data-node] { opacity: 0.08 !important; }
svg.focus [data-edge].on, svg.focus [data-node].on { opacity: 1 !important; }
svg.focus [data-edge].on path { stroke-width: 4 !important; }
svg.focus .trace, svg.focus .car { opacity: 0 !important; }
.trace { stroke: #F59E0B !important; stroke-width: 8 !important; opacity: 0.55; fill: none; }
"""


def tag(svg: str) -> str:
    def repl(m: re.Match) -> str:
        b64, rest = m.group(1), m.group(2)
        try:
            name = html.unescape(base64.b64decode(b64).decode())
        except Exception:
            return m.group(0)
        if name.startswith("legend"):
            return m.group(0)
        kind = "edge" if re.search(r"\((.+) (->|<->) (.+)\)\[\d+\]$", name) else "node"
        return f'<g class="{b64}{rest}" data-{kind}="{html.escape(name)}">'

    return re.sub(r'<g class="([A-Za-z0-9+/=]{4,})((?: [\w-]+)*)">', repl, svg)


def main() -> None:
    svg = (HERE / "ishikari.svg").read_text()
    svg = tag(svg)
    script = SCRIPT.replace("__ROUTES__", json.dumps(ROUTES))
    extra = f"<style>{STYLE}</style><script><![CDATA[{script}]]></script>"
    i = svg.rindex("</svg>", 0, svg.rindex("</svg>"))
    svg = svg[:i] + extra + svg[i:]
    (HERE / "ishikari-flow.svg").write_text(svg)


if __name__ == "__main__":
    main()
