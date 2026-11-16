"""Build ishikari-flow.svg: a car carries one task along the exact path.

Reads the rendered ishikari.svg, tags every block and arrow with its D2 name,
and adds a script that drives the car slowly along each arrow in TOUR order.
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

# One step per arrow the task travels: [arrow, reverse?, caption].
# reverse=True drives the car from the arrow's end back to its start.
TOUR = [
    ["plan.(task -> arta)[0]", False, "A task arrives. The task review ant reads it."],
    ["(plan.arta <-> user)[0]", False, "The task review ant asks you questions."],
    ["(plan.arta <-> user)[0]", True, "You answer. The review is done."],
    ["plan.(arta -> aara)[0]", False, "Approved. On to the add requirement ant."],
    ["(plan.aara <-> user)[0]", False, "It drafts a requirement and asks you."],
    ["(plan.aara <-> user)[0]", True, "You approve the requirement."],
    ["plan.(aara -> plans)[0]", False, "It commits the requirement and writes plans."],
    ["(plan.plans -> build.aw)[0]", False, "Worker ants start, each in its own worktree."],
    ["build.(aw -> bulletin)[0]", False, "A worker finishes and posts \"built\"."],
    ["(check.monitor -> build.bulletin)[0]", True, "The build script sees it at once."],
    ["check.(monitor -> inspector)[0]", False, "It starts an inspector ant for this task."],
    ["(check.inspector -> fix.bounty)[0]", False, "The inspector finds a bug and posts it."],
    ["fix.(bounty -> detective)[0]", False, "A detective ant takes the bug."],
    ["(fix.detective -> build.aw)[0]", False, "It writes a fix plan for a worker ant."],
    ["(fix.detective -> build.aw)[0]", True, "The worker builds the fix."],
    ["(fix.detective -> check.inspector)[0]", False, "The same inspector checks again."],
    ["(check.inspector -> build.bulletin)[0]", False, "No bugs. The task waits for your review."],
    ["(build.bulletin -> user)[0]", False, "You do the final review."],
    ["(user -> finish.merger)[0]", False, "You approve. The merger ant takes it."],
    ["(finish.merger -> build.bulletin)[0]", False, "Merged into main. Status: done."],
    ["always_on.(philosopher -> critiques)[0]", False, "The philosopher ant writes critiques."],
    ["(always_on.critiques -> plan.aara)[0]", False, "Critiques shape the next plans."],
]

SCRIPT = r"""
(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.querySelector('svg svg') || document.documentElement;
  const TOUR = __TOUR__;
  const SPEED = 70;      // px per second: slow
  const PAUSE = 1800;    // ms at each block
  const RESTART = 5000;  // ms before the tour starts again

  const edges = {}, nodes = {};
  svg.querySelectorAll('[data-edge]').forEach(g => edges[g.dataset.edge] = g);
  svg.querySelectorAll('[data-node]').forEach(g => nodes[g.dataset.node] = g);
  const all = [...Object.values(edges), ...Object.values(nodes)];

  const endpoints = name => {
    const m = name.match(/^(?:(.*?)\.)?\((.+?) (?:->|<->) (.+?)\)\[\d+\]$/);
    const pre = m[1] ? m[1] + '.' : '';
    return [pre + m[2], pre + m[3]];
  };
  const withParents = id => {
    const out = [];
    const parts = id.split('.');
    for (let i = 1; i <= parts.length; i++) out.push(parts.slice(0, i).join('.'));
    return out;
  };
  const light = id => withParents(id).forEach(n => nodes[n] && nodes[n].classList.add('lit'));

  const layer = document.createElementNS(NS, 'g');
  svg.appendChild(layer);
  const car = document.createElementNS(NS, 'g');
  car.innerHTML = '<circle r="22" fill="#FDE68A" stroke="#B45309" stroke-width="3"/>' +
    '<text text-anchor="middle" dominant-baseline="central" font-size="26">🚗</text>';
  const cap = document.createElementNS(NS, 'g');
  cap.innerHTML = '<rect x="-80" y="1300" width="1150" height="56" rx="12" fill="#0F172A" opacity="0.9"/>' +
    '<text x="-56" y="1336" font-size="26" fill="#F8FAFC" font-family="sans-serif"></text>';
  svg.appendChild(cap);
  svg.appendChild(car);
  const capText = cap.querySelector('text');

  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const drive = (path, rev) => new Promise(done => {
    const len = path.getTotalLength();
    const trace = path.cloneNode(false);
    trace.removeAttribute('marker-end');
    trace.removeAttribute('marker-start');
    trace.removeAttribute('mask');
    trace.setAttribute('class', 'trace');
    trace.style.strokeDasharray = len + ' ' + len;
    trace.style.strokeDashoffset = rev ? -len : len;
    layer.appendChild(trace);
    const ms = len / SPEED * 1000;
    const t0 = performance.now();
    const tick = now => {
      const k = Math.min(1, (now - t0) / ms);
      const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      const d = rev ? len * (1 - e) : len * e;
      const p = path.getPointAtLength(d);
      car.setAttribute('transform', `translate(${p.x},${p.y})`);
      trace.style.strokeDashoffset = rev ? -(len - len * e) : len - len * e;
      if (k < 1) requestAnimationFrame(tick); else done();
    };
    requestAnimationFrame(tick);
  });

  async function tour() {
    for (;;) {
      layer.innerHTML = '';
      all.forEach(g => g.classList.remove('lit', 'now'));
      for (const [name, rev, caption] of TOUR) {
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
        await sleep(PAUSE);
        nodes[end] && nodes[end].classList.remove('now');
      }
      capText.textContent = 'Done. The tour starts again.';
      await sleep(RESTART);
    }
  }
  tour();
})();
"""

STYLE = """
[data-edge], [data-node] { opacity: 0.12; transition: opacity 1.2s ease; }
[data-edge].lit, [data-node].lit { opacity: 1; }
[data-node].now > .shape { filter: drop-shadow(0 0 10px #F59E0B) drop-shadow(0 0 4px #F59E0B); }
[data-edge].now path { stroke-width: 4 !important; }
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
    script = SCRIPT.replace("__TOUR__", json.dumps(TOUR))
    extra = f"<style>{STYLE}</style><script><![CDATA[{script}]]></script>"
    i = svg.rindex("</svg>", 0, svg.rindex("</svg>"))
    svg = svg[:i] + extra + svg[i:]
    (HERE / "ishikari-flow.svg").write_text(svg)


if __name__ == "__main__":
    main()
