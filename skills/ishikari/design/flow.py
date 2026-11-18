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
    ["(check.inspector -> fix.detective)[0]", False, "Still open after round 1: the script hands the bug to a detective ant."],
    ["(fix.detective -> build.aw)[0]", False, "It writes a fix plan for a worker ant."],
    ["(build.aw -> check.inspector)[0]", False, "The worker builds the fix; the script sends it to the same inspector."],
]

ROUTES = [
    {
        "name": "Route 1 of 2: a bug, fixed on the first try",
        "steps": [
            ["ask.(task -> arta)[0]", False, "A task arrives. The skill starts ONE investigator ant; it reads the repo once."],
            ["ask.(arta <-> research)[0]", False, "It sends researcher ants for missing facts, and waits for them."],
            ["ask.(arta <-> research)[0]", True, "They report back. The same investigator is still alive."],
            ["(ask.arta <-> user)[0]", False, "It asks you up to 4 questions at once."],
            ["(ask.arta <-> user)[0]", True, "Your answers go back to the SAME agent. Repeat until clear."],
            ["ask.(arta -> report)[0]", False, "Nothing unclear: it writes investigation_report.md."],
            ["(ask.report -> plan.aara)[0]", False, "Only now the plan workflow runs: the add requirement ant reads it."],
            ["plan.(aara -> arch)[0]", False, "It drafts the requirement for the architect ant."],
            ["plan.(arch -> plans)[0]", False, "The architect writes architecture.md and the plans."],
            ["(plan.plans -> build.aw)[0]", False, "Worker ants start, each in its own worktree."],
            ["(build.aw -> check.inspector)[0]", False, "Built: the build script starts this task's inspector at once."],
            ["(check.inspector -> build.aw)[0]", False, "Round 1: a worker builds the inspector's own fix plan."],
            *FIX_ROUND,
            ["check.(inspector -> together)[0]", False, "All tasks checked: the integrator ant tests them combined."],
            ["(check.together -> finish.merger)[0]", False, "They work combined. The main session approves them, no review."],
            ["finish.(merger -> verifier)[0]", False, "Merged (reusing build's trial merge if the set matches or only adds tasks)."],
            ["(finish.verifier -> always_on)[0]", False, "The verifier ant checks each task landed (git cherry); the janitor plans a cleanup."],
            ["(always_on.janitor -> build.aw)[0]", False, "A worker builds it now; an inspector checks it, one fix round."],
            ["(always_on.philosopher -> critiques)[0]", False, "Alongside it, the philosopher keeps its best critique (--critiques N, default 1)."],
            ["(always_on -> finish.finisher)[0]", False, "Both ended: scratch takes the cleanup; the finisher ant moves main forward."],
            ["(critiques -> ask.arta)[0]", False, "Next task: the investigator ant asks you about critiques."],
            ["(always_on.janitor -> ask.task)[0]", False, "Only a dropped cleanup's plan is offered next time."],
        ],
    },
    {
        "name": "Route 2 of 2: a stuck worker, 3 failed fixes, dropped",
        "steps": [
            ["(plan.plans -> build.aw)[0]", False, "The plans go to the worker ants."],
            ["(build.aw -> fix.detective)[0]", False, "A worker gets stuck: the next fix round goes to a detective."],
            *[[a, r, f"Round 1, try 1 on this bug: {c}"] for a, r, c in FIX_ROUND[1:]],
            ["(check.inspector -> fix.detective)[0]", False, "Still broken. The script hands it back to the detective."],
            *[[a, r, f"Round 2, try 2 on this bug: {c}"] for a, r, c in FIX_ROUND[1:]],
            ["(check.inspector -> fix.detective)[0]", False, "Still broken. The script hands it back to the detective."],
            *[[a, r, f"Round 3, try 3 on this bug: {c}"] for a, r, c in FIX_ROUND[1:]],
            ["(check.inspector -> fix.detective)[0]", False, "Still broken: 3 tries on a bug (MAX_TRIES) ends it; 3 rounds per task (MAX_ROUNDS) caps new bugs. Dropped."],
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
