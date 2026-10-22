#!/usr/bin/env python3
"""Draw the charts of dev_tools.rec.

dev_tools.svg, the level map: rows are categories in file order, columns are
levels 1-5, and each tool is a chip in its cell, in file order (preference):

            L1        L2        L3   ...
  AI      [models]  [pi]
          [llmfit]  [Claude]

dev_tools_path.svg, the prerequisites, laid out by Graphviz dot: only tools
with a Requires line or a dependant, in level columns left to right. A
prerequisite never sits above its tool's level, and one of the same level puts
its tool a sub-column further right, so every arrow points right. A solid arrow
is a must (AND), a dashed one an alternative (`A | B`, OR):

  L1                L2                    L5
  [Bash] -> [Git] -> [lazygit]
       `----------> [Python] -> [JSON]
                             `---------> [Zig]

Needs Graphviz (`brew install graphviz`).

Before drawing, the Requires lines are validated: every name exists, no
prerequisite has a higher level than its tool, no loops, and no arrow that is
already implied through another prerequisite.

dev_tools.html, one page with a Filter: Base / Extra / Max switch over the
learning path. Tier is importance: each view adds a tier to the one before,
and a tool never requires one of a higher tier.

Usage:
  ./dev_tools.py           validate, then write all three charts
  ./dev_tools.py --check   exit 1 when the data is invalid or a chart is stale
  ./dev_tools.py help      this text
"""
import argparse
import os
import shutil
import subprocess
import sys
from html import escape

ROOT = os.path.dirname(os.path.realpath(__file__))
REC = os.path.join(ROOT, "dev_tools.rec")
SVG = os.path.join(ROOT, "dev_tools.svg")
PATH_SVG = os.path.join(ROOT, "dev_tools_path.svg")
HTML = os.path.join(ROOT, "dev_tools.html")

# Tiers in order: a view shows its tier and every tier before it.
TIERS = {"base": "Base", "extra": "Extra", "max": "Max"}

LEVELS = {
    1: ("Beginner", "#1f5f46"),
    2: ("Easy", "#1f4f6f"),
    3: ("Intermediate", "#5f4f1f"),
    4: ("Advanced", "#6f341f"),
    5: ("Expert", "#5f1f4f"),
}

# Geometry, in px. CHAR is the average glyph width of the 13px chip font.
PAD = 24
TITLE = 56
HEAD = 40
LABEL = 250
COL = 200
CHIP = 24
GAP = 6
CHAR = 7.4

BG = "#0f1115"
LINE = "#2a2f3a"
TEXT = "#e6e6e6"
MUTED = "#9aa3b2"
FONT = "-apple-system, 'Helvetica Neue', Arial, sans-serif"


def parse(path):
    """Read Tool records: `Field: value` lines, a blank line between records.

    Comments (#) and the schema (%) are skipped; `+ ` continues a value.
    """
    records, rec, last = [], {}, None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line.startswith(("#", "%")):
                continue
            if not line.strip():
                if rec:
                    records.append(rec)
                rec, last = {}, None
                continue
            if line.startswith("+") and last:
                rec[last] += "\n" + line[2:]
                continue
            key, _, value = line.partition(":")
            last = key.strip()
            if last == "Requires":
                rec.setdefault(last, []).append(value.strip())
                last = None
                continue
            rec[last] = value.strip()
    if rec:
        records.append(rec)
    return records


def groups(rec):
    """Requires lines as lists: `C | Zig` -> ["C", "Zig"]. Each list is AND-ed."""
    return [[a.strip() for a in line.split("|")] for line in rec.get("Requires", [])]


def rank(rec):
    """Tier position: base 0, extra 1, max 2."""
    return list(TIERS).index(rec["Tier"])


def validate(records):
    """Return the problems with the Requires lines, one string each."""
    tools = {r["Name"]: r for r in records}
    problems = []

    for rec in records:
        name, level = rec["Name"], int(rec["Level"])
        for group in groups(rec):
            for pre in group:
                if pre not in tools:
                    problems.append(f"{name}: requires unknown tool {pre!r}")
                    continue
                if int(tools[pre]["Level"]) > level:
                    problems.append(
                        f"{name} (L{level}) requires {pre} (L{tools[pre]['Level']}): "
                        "a prerequisite may not have a higher level"
                    )
                if rank(tools[pre]) > rank(rec):
                    problems.append(
                        f"{name} ({rec['Tier']}) requires {pre} ({tools[pre]['Tier']}): "
                        "a prerequisite may not have a higher tier"
                    )
    if problems:
        return problems

    # Loops: walk each tool's prerequisites depth-first.
    state = {}

    def visit(name, trail):
        if state.get(name) == "done":
            return
        if state.get(name) == "open":
            problems.append("loop: " + " -> ".join(trail + [name]))
            return
        state[name] = "open"
        for group in groups(tools[name]):
            for pre in group:
                visit(pre, trail + [name])
        state[name] = "done"

    for name in tools:
        visit(name, [])
    if problems:
        return problems

    # Redundant arrows: B requires A while another prerequisite of B already
    # leads back to A (Rust requires Bash when Python requires Bash).
    def ancestors(name, seen=None):
        seen = set() if seen is None else seen
        for group in groups(tools[name]):
            for pre in group:
                if pre not in seen:
                    seen.add(pre)
                    ancestors(pre, seen)
        return seen

    for rec in records:
        direct = [g[0] for g in groups(rec) if len(g) == 1]
        others = {pre for g in groups(rec) for pre in g}
        for pre in direct:
            via = [o for o in others - {pre} if pre in ancestors(o)]
            if via:
                problems.append(
                    f"{rec['Name']}: Requires {pre} is implied through {via[0]} - drop it"
                )
    return problems


def render(records):
    # Group tools by category, then level, keeping file order.
    grid = {}
    for rec in records:
        row = grid.setdefault(rec["Category"], {n: [] for n in LEVELS})
        row[int(rec["Level"])].append(rec["Name"])

    width = PAD * 2 + LABEL + COL * len(LEVELS)
    heights = {
        cat: max(1, *(len(v) for v in row.values())) * (CHIP + GAP) + GAP * 2
        for cat, row in grid.items()
    }
    height = PAD * 2 + TITLE + HEAD + sum(heights.values())

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="{FONT}">',
        f'<rect width="{width}" height="{height}" fill="{BG}"/>',
        f'<text x="{PAD}" y="{PAD + 24}" fill="{TEXT}" font-size="22" '
        f'font-weight="600">Dev Tools by Level</text>',
        f'<text x="{PAD}" y="{PAD + 44}" fill="{MUTED}" font-size="13">'
        f"Generated from dev_tools.rec by dev_tools.py. Order within a cell is preference.</text>",
    ]

    # Column headers: level number and name, tinted with the level colour.
    top = PAD + TITLE
    for n, (name, color) in LEVELS.items():
        x = PAD + LABEL + COL * (n - 1)
        out.append(
            f'<rect x="{x + 4}" y="{top + 4}" width="{COL - 8}" height="{HEAD - 8}" '
            f'rx="6" fill="{color}"/>'
        )
        out.append(
            f'<text x="{x + COL / 2}" y="{top + HEAD / 2 + 5}" fill="{TEXT}" '
            f'font-size="14" font-weight="600" text-anchor="middle">L{n} {name}</text>'
        )

    # One row per category: label, separator, then the chips in each cell.
    y = top + HEAD
    for cat, row in grid.items():
        h = heights[cat]
        out.append(
            f'<line x1="{PAD}" y1="{y}" x2="{width - PAD}" y2="{y}" stroke="{LINE}"/>'
        )
        out.append(
            f'<text x="{PAD}" y="{y + GAP + CHIP / 2 + 5}" fill="{TEXT}" '
            f'font-size="14" font-weight="600">{escape(cat)}</text>'
        )
        for n, names in row.items():
            x = PAD + LABEL + COL * (n - 1)
            color = LEVELS[n][1]
            for i, name in enumerate(names):
                cy = y + GAP + i * (CHIP + GAP)
                w = min(COL - 12, len(name) * CHAR + 20)
                out.append(
                    f'<rect x="{x + 6}" y="{cy}" width="{w:.0f}" height="{CHIP}" '
                    f'rx="12" fill="{color}"/>'
                )
                out.append(
                    f'<text x="{x + 16}" y="{cy + CHIP / 2 + 4.5}" fill="{TEXT}" '
                    f'font-size="13">{escape(name)}</text>'
                )
        y += h

    # Column separators over the full grid.
    for n in range(len(LEVELS) + 1):
        x = PAD + LABEL + COL * n
        out.append(
            f'<line x1="{x}" y1="{top}" x2="{x}" y2="{y}" stroke="{LINE}"/>'
        )
    out.append(
        f'<line x1="{PAD}" y1="{y}" x2="{width - PAD}" y2="{y}" stroke="{LINE}"/>'
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def render_path(records, tier="max", title=True):
    """Lay the learning path out with Graphviz dot and return the SVG.

    Only tools up to `tier` are drawn; validate() guarantees their
    prerequisites are too. `title` adds the heading inside the SVG.
    """
    records = [r for r in records if rank(r) <= list(TIERS).index(tier)]
    tools = {r["Name"]: r for r in records}
    edges = [
        (pre, rec["Name"], len(group) > 1)
        for rec in records
        for group in groups(rec)
        for pre in group
    ]
    linked = {a for a, _, _ in edges} | {b for _, b, _ in edges}
    order = [r["Name"] for r in records if r["Name"] in linked]

    def level(name):
        return int(tools[name]["Level"])

    # Sub-column: a tool that needs a prerequisite of its own level sits one
    # sub-column right of it, inside the level (Bash -> Git in L1), so every
    # arrow points right.
    subs = {}

    def sub(name):
        if name not in subs:
            same = [p for g in groups(tools[name]) for p in g if level(p) == level(name)]
            subs[name] = 1 + max(map(sub, same)) if same else 0
        return subs[name]

    cols = sorted({(level(m), sub(m)) for m in order})

    def quote(text):
        return '"' + text.replace('"', '\\"') + '"'

    heading = (
        f'<<FONT POINT-SIZE="22">Dev Tools Learning Path</FONT><BR ALIGN="LEFT"/>'
        f'<FONT POINT-SIZE="13" COLOR="{MUTED}">Generated from dev_tools.rec by dev_tools.py. '
        f"A &#8594; B: know A before B. Solid = required, dashed = any one of.</FONT>"
        f'<BR ALIGN="LEFT"/>>'
    )
    dot = [
        "digraph path {",
        f'  graph [rankdir=LR, bgcolor="{BG}", ranksep=0.9, nodesep=0.35, splines=spline, '
        f'fontname="Helvetica", fontcolor="{TEXT}", label={heading if title else '""'}, '
        f"labelloc=t, labeljust=l, pad=0.4];",
        f'  node [shape=box, style="rounded,filled", penwidth=0, fontname="Helvetica", '
        f'fontsize=13, fontcolor="{TEXT}", height=0.3, margin="0.15,0.04"];',
        f'  edge [color="{MUTED}", arrowsize=0.7, penwidth=1.2];',
    ]

    # One rank per column, pinned in order by an invisible chain of anchors;
    # a level's first column carries its header as the anchor.
    for i, (n, s) in enumerate(cols):
        name, color = LEVELS[n]
        if s:
            dot.append(f'  a{i} [label="", style=invis, width=0.1];')
        else:
            dot.append(f'  a{i} [label="L{n} {name}", fillcolor="{color}", fontsize=14, style=filled];')
        members = " ".join(quote(m) for m in order if (level(m), sub(m)) == (n, s))
        dot.append(f"  {{ rank=same; a{i}; {members} }}")
    dot.append("  " + " -> ".join(f"a{i}" for i in range(len(cols))) + " [style=invis];")

    for name in order:
        dot.append(f"  {quote(name)} [fillcolor={quote(LEVELS[level(name)][1])}];")
    for pre, name, alt in edges:
        dot.append(f"  {quote(pre)} -> {quote(name)}" + (" [style=dashed];" if alt else ";"))
    dot.append("}")

    run = subprocess.run(
        ["dot", "-Tsvg"], input="\n".join(dot) + "\n", capture_output=True, text=True, check=True
    )
    return run.stdout


def render_html(records):
    """One page with a Base / Extra / Max switch over three dot layouts.

    Each tier gets its own layout rather than hiding nodes in one, so a
    smaller view has no holes. No server, no libraries: open it in a browser.
    """
    views = []
    for tier, label in TIERS.items():
        svg = render_path(records, tier, title=False)
        svg = svg[svg.index("<svg"):]
        shown = [r for r in records if rank(r) <= list(TIERS).index(tier)]

        # Tools with no arrow are not in the chart; list them by level below
        # it, so a view still shows the whole tier (Firefox, Bitwarden).
        linked = {r["Name"] for r in shown if groups(r)} | {
            p for r in shown for g in groups(r) for p in g
        }
        loose = "".join(
            f'<span class="chip" style="background:{LEVELS[int(r["Level"])][1]}">'
            f'{escape(r["Name"])}</span>'
            for r in sorted(shown, key=lambda r: int(r["Level"]))
            if r["Name"] not in linked
        )
        if loose:
            loose = f'<h2>Not on a path yet</h2><div class="legend">{loose}</div>'
        views.append(
            f'<section class="view" id="{tier}" data-count="{len(shown)}"'
            f'{"" if tier == "base" else " hidden"}>'
            f"\n{svg}{loose}</section>"
        )
    buttons = "".join(
        f'<button type="button" data-tier="{t}">Filter: {label}</button>' for t, label in TIERS.items()
    )
    legend = "".join(
        f'<span class="chip" style="background:{color}">L{n} {name}</span>'
        for n, (name, color) in LEVELS.items()
    )
    views = "\n".join(views)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dev Tools Path</title>
<style>
  :root {{ --bg: {BG}; --text: {TEXT}; --muted: {MUTED}; --line: {LINE}; }}
  body {{ margin: 0; background: var(--bg); color: var(--text);
         font: 14px/1.4 -apple-system, "Helvetica Neue", Arial, sans-serif; }}
  header {{ padding: 20px 24px 12px; }}
  h1 {{ margin: 0 0 4px; font-size: 22px; }}
  p {{ margin: 0 0 12px; color: var(--muted); }}
  .bar {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
  button {{ font: inherit; color: var(--text); background: transparent; cursor: pointer;
           border: 1px solid var(--line); border-radius: 8px; padding: 6px 14px; }}
  button[aria-pressed="true"] {{ background: var(--line); border-color: var(--muted); }}
  .count {{ color: var(--muted); margin-left: 8px; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }}
  .chip {{ border-radius: 10px; padding: 2px 10px; font-size: 12px; }}
  .view {{ overflow-x: auto; padding: 0 8px 24px; }}
  .view svg {{ display: block; }}
  h2 {{ font-size: 14px; color: var(--muted); margin: 8px 16px 0; font-weight: 600; }}
  .view .legend {{ margin: 8px 16px 0; }}
</style>
</head>
<body>
<header>
  <h1>Dev Tools Learning Path</h1>
  <p>Generated from dev_tools.rec by dev_tools.py. A &rarr; B: know A before B.
     Solid = required, dashed = any one of. Columns are levels, left to right.</p>
  <div class="bar">{buttons}<span class="count" id="count"></span></div>
  <div class="legend">{legend}</div>
</header>
{views}
<script>
  // Show one tier; remember it in the URL hash and, where allowed, storage.
  const views = document.querySelectorAll(".view");
  const buttons = document.querySelectorAll("button[data-tier]");
  function show(tier) {{
    const view = document.getElementById(tier) || views[0];
    views.forEach(v => v.hidden = v !== view);
    buttons.forEach(b => b.setAttribute("aria-pressed", b.dataset.tier === view.id));
    document.getElementById("count").textContent = view.dataset.count + " tools";
    history.replaceState(null, "", "#" + view.id);
    try {{ localStorage.setItem("tier", view.id); }} catch (e) {{}}
  }}
  buttons.forEach(b => b.addEventListener("click", () => show(b.dataset.tier)));
  let saved = null;
  try {{ saved = localStorage.getItem("tier"); }} catch (e) {{}}
  show(location.hash.slice(1) || saved || "base");
</script>
</body>
</html>
"""


def main(argv):
    if argv[:1] == ["help"]:
        print(__doc__)
        return 0

    parser = argparse.ArgumentParser(description="Validate dev_tools.rec and draw its charts.")
    parser.add_argument("--check", action="store_true", help="exit 1 when the data is invalid or a chart is stale")
    opts = parser.parse_args(argv)

    if not shutil.which("dot"):
        print("dev_tools.py: Graphviz dot not found - fix: brew install graphviz", file=sys.stderr)
        return 2

    records = parse(REC)
    problems = validate(records)
    for problem in problems:
        print(f"dev_tools.rec: {problem}", file=sys.stderr)
    if problems:
        return 1

    charts = {SVG: render(records), PATH_SVG: render_path(records), HTML: render_html(records)}
    if opts.check:
        stale = 0
        for path, svg in charts.items():
            current = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
            if current != svg:
                print(f"{os.path.basename(path)} is stale - fix: ./dev_tools.py", file=sys.stderr)
                stale = 1
        return stale

    for path, svg in charts.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
