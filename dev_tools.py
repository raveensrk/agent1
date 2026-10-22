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

Edits go through the same checks as a hand edit of dev_tools.rec (recfix for
the schema, then the arrow rules); a change that fails is not written, and one
that passes is written and every chart redrawn.

Usage:
  ./dev_tools.py                      validate, then write all three charts
  ./dev_tools.py --check              exit 1 when the data is invalid or a chart is stale
  ./dev_tools.py add NAME --category C --level N --tier T [--subcategory S] [--url U] [--note N]
  ./dev_tools.py set NAME [--level N] [--tier T] [--category C] [--subcategory S] [--url U] [--note N]
  ./dev_tools.py rename NAME NEW
  ./dev_tools.py link PRE NAME        PRE -> NAME; "A | B" for any one of
  ./dev_tools.py unlink PRE NAME
  ./dev_tools.py rm NAME              also drops every arrow from it
  ./dev_tools.py serve [--port P]     node editor at http://127.0.0.1:P: drag, connect,
                                      rename in place; positions saved as Pos
  ./dev_tools.py help                 this text
"""
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from html import escape

ROOT = os.path.dirname(os.path.realpath(__file__))
REC = os.path.join(ROOT, "dev_tools.rec")
SVG = os.path.join(ROOT, "dev_tools.svg")
PATH_SVG = os.path.join(ROOT, "dev_tools_path.svg")
HTML = os.path.join(ROOT, "dev_tools.html")

# The editor's port, on 127.0.0.1 only; 8765 is alduin's. The editor page
# and the one library it loads, Cytoscape.js 3.30.2 (MIT), kept in the repo
# so the editor works offline.
PORT = 8766
EDITOR = os.path.join(ROOT, "dev_tools_editor.html")
VENDOR = {"/vendor/cytoscape.min.js": os.path.join(ROOT, "vendor", "cytoscape.min.js")}

# Grid for tools off the path when the canvas places them, in px.
GRIDX = 190
GRIDY = 60
GRIDCOLS = 6

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
    with open(path, encoding="utf-8") as f:
        return parse_text(f.read())


def parse_text(text):
    """Read Tool records: `Field: value` lines, a blank line between records.

    Comments (#) and the schema (%) are skipped; `+ ` continues a value.
    """
    records, rec, last = [], {}, None
    for line in text.split("\n"):
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
    """Return the problems with the records, one string each."""
    problems = []

    # Duplicates first: a second fzf would hide the first one below. Names
    # match ignoring case and spaces, which recfix's %key does not.
    seen = {}
    for rec in records:
        seen.setdefault(" ".join(rec["Name"].split()).casefold(), []).append(rec["Name"])
    for names in seen.values():
        if len(names) > 1:
            problems.append("duplicate tool: " + ", ".join(repr(n) for n in names))
    urls = {}
    for rec in records:
        if rec.get("Url"):
            urls.setdefault(rec["Url"].rstrip("/").casefold(), []).append(rec["Name"])
    for url, names in urls.items():
        if len(names) > 1:
            problems.append(f"duplicate Url {url} on " + ", ".join(names))
    for rec in records:
        for g in groups(rec):
            if len(set(g)) < len(g):
                problems.append(f"{rec['Name']}: Requires {' | '.join(g)} names a tool twice")
    if problems:
        return problems

    tools = {r["Name"]: r for r in records}

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

        # An OR line is met already when one of its tools is required alone
        # (Requires: Lua makes Requires: Python | Lua say nothing).
        lines = [" | ".join(g) for g in groups(rec)]
        for g in groups(rec):
            met = [pre for pre in g if len(g) > 1 and pre in direct]
            if met:
                problems.append(
                    f"{rec['Name']}: Requires {' | '.join(g)} is met by Requires {met[0]} - drop it"
                )
        for line in sorted({x for x in lines if lines.count(x) > 1}):
            problems.append(f"{rec['Name']}: Requires {line} appears twice - drop one")
    return problems


# Editing. Every change is made to the text of dev_tools.rec, checked by
# recfix (the schema) and validate() (the arrows), and written only when both
# pass; then the charts are redrawn. A record that changes is rewritten in
# FIELDS order; every other line of the file is left as it was.
FIELDS = ["Name", "Category", "Subcategory", "Level", "Tier", "Requires", "Url", "Note", "Pos"]
REQUIRED = {"Name", "Category", "Level", "Tier"}


def split(text):
    """dev_tools.rec as (head, blocks): the comments and schema, then one
    block of `Field: value` lines per record."""
    at = text.index("\nName: ") + 1
    return text[:at], text[at:].strip("\n").split("\n\n")


def join(head, blocks):
    return head + "\n\n".join(blocks) + "\n"


def fields(block):
    """A record block as [(field, value)], continuation lines folded in."""
    out = []
    for line in block.split("\n"):
        if line.startswith("+") and out:
            out[-1] = (out[-1][0], out[-1][1] + "\n" + line[2:])
            continue
        key, _, value = line.partition(":")
        out.append((key.strip(), value.strip()))
    return out


def unfields(pairs):
    pairs = sorted(pairs, key=lambda kv: FIELDS.index(kv[0]))
    return "\n".join(f"{k}: {v}".replace("\n", "\n+ ") for k, v in pairs)


def find(blocks, name):
    for i, block in enumerate(blocks):
        if dict(fields(block)).get("Name") == name:
            return i
    raise ValueError(f"no tool named {name!r}")


def alternatives(line):
    return [a.strip() for a in line.split("|") if a.strip()]


def edit(text, op, args):
    """Apply one change to the text of dev_tools.rec and return the new text.

    op is add, set, rename, link, unlink or rm; args is a dict:
      add     name, category, level, tier, [subcategory, url, note]
      set     name, and any of category, subcategory, level, tier, url, note
              ("" drops an optional field)
      rename  name, to
      link    pre, name     pre -> name; `A | B` makes an OR line
      unlink  pre, name
      rm      name          also drops every arrow from it
      move    positions     {name: [x, y]}, the canvas Pos of each
      layout                every Pos reset to auto_positions()
    Raises ValueError for a change that cannot apply.
    """
    head, blocks = split(text)
    names = [dict(fields(b))["Name"] for b in blocks]

    if op in ("move", "layout"):
        moves = args.get("positions") if op == "move" else auto_positions(parse_text(text))
        if not isinstance(moves, dict) or not moves:
            raise ValueError("move needs positions")
        for name, xy in moves.items():
            x, y = (round(float(v)) for v in xy)
            i = find(blocks, name)
            kept = [(k, v) for k, v in fields(blocks[i]) if k != "Pos"]
            blocks[i] = unfields(kept + [("Pos", f"{x} {y}")])
        return join(head, blocks)

    if op == "add":
        name = args["name"].strip()
        if name in names:
            raise ValueError(f"{name!r} already exists")
        pairs = [("Name", name)]
        for key in ("category", "subcategory", "level", "tier", "url", "note"):
            value = str(args.get(key) or "").strip()
            if value:
                pairs.append((key.capitalize(), value))
        if args.get("pos"):
            pairs.append(("Pos", " ".join(str(round(float(v))) for v in args["pos"])))
        missing = REQUIRED - {k for k, _ in pairs}
        if missing:
            raise ValueError("add needs " + ", ".join(sorted(missing)).lower())
        # A new tool goes last in its category, the bottom of its preference.
        cats = [dict(fields(b))["Category"] for b in blocks]
        at = max((i for i, c in enumerate(cats) if c == args["category"].strip()), default=len(blocks) - 1)
        blocks.insert(at + 1, unfields(pairs))
        return join(head, blocks)

    i = find(blocks, args["name"])
    pairs = fields(blocks[i])

    if op == "set":
        for key, value in args.items():
            if key == "name":
                continue
            field = key.capitalize()
            if field not in FIELDS or field in ("Name", "Requires", "Pos"):
                raise ValueError(f"set cannot change {key!r}")
            value = str(value).strip()
            if not value and field in REQUIRED:
                raise ValueError(f"{key} cannot be empty")
            pairs = [(k, v) for k, v in pairs if k != field]
            if value:
                pairs.append((field, value))
        blocks[i] = unfields(pairs)
        return join(head, blocks)

    if op == "rename":
        new = args["to"].strip()
        if not new or new in names:
            raise ValueError(f"cannot rename to {new!r}")
        old = args["name"]
        for j, block in enumerate(blocks):
            renamed = [
                (k, new if k == "Name" and v == old else
                 " | ".join(new if a == old else a for a in alternatives(v)) if k == "Requires" else v)
                for k, v in fields(block)
            ]
            blocks[j] = unfields(renamed) if renamed != fields(block) else block
        return join(head, blocks)

    if op == "link":
        line = " | ".join(alternatives(args["pre"]))
        if not line:
            raise ValueError("link needs a prerequisite")
        if ("Requires", line) in pairs:
            raise ValueError(f"{args['name']} already requires {line}")
        blocks[i] = unfields(pairs + [("Requires", line)])
        return join(head, blocks)

    if op == "unlink":
        pre, out, found = args["pre"].strip(), [], False
        for k, v in pairs:
            if k == "Requires" and pre in alternatives(v):
                found = True
                rest = [a for a in alternatives(v) if a != pre]
                if rest:
                    out.append((k, " | ".join(rest)))
                continue
            out.append((k, v))
        if not found:
            raise ValueError(f"{args['name']} does not require {pre}")
        blocks[i] = unfields(out)
        return join(head, blocks)

    if op == "rm":
        gone = args["name"]
        del blocks[i]
        for j, block in enumerate(blocks):
            kept = []
            for k, v in fields(block):
                if k == "Requires" and gone in alternatives(v):
                    rest = [a for a in alternatives(v) if a != gone]
                    if rest:
                        kept.append((k, " | ".join(rest)))
                    continue
                kept.append((k, v))
            if kept != fields(block):
                blocks[j] = unfields(kept)
        return join(head, blocks)

    raise ValueError(f"unknown edit {op!r}")


def apply(op, args):
    """Edit dev_tools.rec, check it, write it and redraw. Returns problems."""
    with open(REC, encoding="utf-8") as f:
        text = f.read()
    try:
        new = edit(text, op, args)
    except ValueError as err:
        return [str(err)]
    except KeyError as err:
        return [f"missing {err.args[0]}"]

    run = subprocess.run(["recfix", "--check"], input=new, capture_output=True, text=True)
    if run.returncode:
        return [line.replace("stdin:", "dev_tools.rec:") for line in run.stderr.splitlines()]
    problems = validate(parse_text(new))
    if problems:
        return problems

    with open(REC, "w", encoding="utf-8") as f:
        f.write(new)
    if op not in ("move", "layout"):
        draw(parse_text(new))
    return []


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
    run = subprocess.run(
        ["dot", "-Tsvg"], input=path_dot(records, tier, title), capture_output=True, text=True, check=True
    )
    return run.stdout


def path_dot(records, tier="max", title=True):
    """The Graphviz source of the learning path, for render_path and
    auto_positions."""
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
    return "\n".join(dot) + "\n"


def auto_positions(records):
    """Canvas positions for every tool, from Graphviz: tools on the path where
    dot puts them, the rest in a grid below. {name: [x, y]}, y pointing down."""
    run = subprocess.run(
        ["dot", "-Tplain"], input=path_dot(records), capture_output=True, text=True, check=True
    )
    names = {r["Name"] for r in records}
    pos, height = {}, 0.0
    for line in run.stdout.splitlines():
        parts = shlex.split(line)
        if parts[0] == "graph":
            height = float(parts[3])
        if parts[0] == "node" and parts[1] in names:
            # dot measures inches from the bottom; the canvas, px from the top.
            pos[parts[1]] = [round(float(parts[2]) * 96), round((height - float(parts[3])) * 96)]

    loose = [r["Name"] for r in records if r["Name"] not in pos]
    top = max((y for _, y in pos.values()), default=0) + 120
    for i, name in enumerate(loose):
        pos[name] = [GRIDX * (i % GRIDCOLS), top + GRIDY * (i // GRIDCOLS)]
    return pos


def positions(records):
    """Saved Pos where a tool has one, auto_positions() for the rest."""
    auto = None
    out = {}
    for rec in records:
        if rec.get("Pos"):
            x, y = rec["Pos"].split()
            out[rec["Name"]] = [int(x), int(y)]
            continue
        auto = auto or auto_positions(records)
        out[rec["Name"]] = auto[rec["Name"]]
    return out


def serve(port):
    """Edit dev_tools.rec as a graph in a browser, on 127.0.0.1 only.

    GET  /                  the node editor, dev_tools_editor.html
    GET  /vendor/...        Cytoscape.js, from vendor/
    GET  /api/graph         tools, canvas positions, levels and tiers as JSON
    GET  /view              the Graphviz page, drawn fresh
    POST /api/edit {op, args} runs apply()

    A POST must carry the X-Dev-Tools header, which another site cannot send
    without a CORS preflight this server never grants, and a Host of this
    machine, which stops DNS rebinding.
    """
    from http.server import BaseHTTPRequestHandler, HTTPServer

    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def reply(self, code, body, kind):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.headers.get("Host") not in hosts:
                return self.reply(403, "forbidden host", "text/plain")
            path = self.path.split("?")[0]
            if path in VENDOR:
                with open(VENDOR[path], "rb") as f:
                    return self.reply(200, f.read(), "text/javascript")
            if path == "/":
                with open(EDITOR, "rb") as f:
                    return self.reply(200, f.read(), "text/html; charset=utf-8")
            if path not in ("/api/graph", "/view"):
                return self.reply(404, "not found", "text/plain")
            records = parse(REC)
            problems = validate(records)
            if problems:
                return self.reply(500, "dev_tools.rec is invalid:\n" + "\n".join(problems), "text/plain")
            if path == "/view":
                return self.reply(200, render_html(records), "text/html; charset=utf-8")
            graph = {
                "tools": records,
                "positions": positions(records),
                "levels": {n: list(v) for n, v in LEVELS.items()},
                "tiers": TIERS,
            }
            self.reply(200, json.dumps(graph), "application/json")

        def do_POST(self):
            if self.headers.get("Host") not in hosts or self.headers.get("X-Dev-Tools") != "1":
                return self.reply(403, "forbidden", "text/plain")
            if self.path != "/api/edit":
                return self.reply(404, "not found", "text/plain")
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or "{}")
                op, args = body["op"], dict(body.get("args") or {})
            except (ValueError, KeyError, TypeError):
                return self.reply(400, json.dumps({"ok": False, "problems": ["bad request"]}), "application/json")
            problems = apply(op, args)
            print(json.dumps({"event": "edit", "op": op, "args": args, "ok": not problems,
                              "problems": problems}), flush=True)
            self.reply(400 if problems else 200, json.dumps({"ok": not problems, "problems": problems}),
                       "application/json")

        def log_request(self, code="-", size="-"):
            print(json.dumps({"event": "request", "method": self.command, "path": self.path,
                              "status": code}), flush=True)

    try:
        server = HTTPServer(("127.0.0.1", port), Handler)
    except OSError as err:
        print(f"dev_tools.py: cannot listen on 127.0.0.1:{port}: {err.strerror} - fix: --port N", file=sys.stderr)
        return 1
    print(f"editing {REC} at http://127.0.0.1:{port} - Ctrl-C to stop", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


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
            f'<span class="chip" data-name="{escape(r["Name"])}" '
            f'style="background:{LEVELS[int(r["Level"])][1]}">{escape(r["Name"])}</span>'
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


def charts(records):
    return {SVG: render(records), PATH_SVG: render_path(records), HTML: render_html(records)}


def draw(records, out=None):
    for path, svg in (out or charts(records)).items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {path}")


def main(argv):
    if argv[:1] == ["help"]:
        print(__doc__)
        return 0

    parser = argparse.ArgumentParser(description="Validate dev_tools.rec and draw its charts.")
    parser.add_argument("--check", action="store_true", help="exit 1 when the data is invalid or a chart is stale")
    cmds = parser.add_subparsers(dest="cmd", metavar="command")

    # Edits: each is checked like a hand edit, then written and redrawn.
    fieldopts = ("category", "subcategory", "level", "tier", "url", "note")
    add = cmds.add_parser("add", help="add a tool")
    add.add_argument("name")
    for key in fieldopts:
        add.add_argument(f"--{key}", required=key in ("category", "level", "tier"))
    edit_ = cmds.add_parser("set", help='change fields of a tool ("" drops an optional one)')
    edit_.add_argument("name")
    for key in fieldopts:
        edit_.add_argument(f"--{key}")
    ren = cmds.add_parser("rename", help="rename a tool and every arrow to it")
    ren.add_argument("name")
    ren.add_argument("to")
    for op, text in (("link", "add the arrow PRE -> NAME"), ("unlink", "remove the arrow PRE -> NAME")):
        cmd = cmds.add_parser(op, help=text)
        cmd.add_argument("pre", help="prerequisite; `A | B` for any one of")
        cmd.add_argument("name")
    rm = cmds.add_parser("rm", help="delete a tool and every arrow from it")
    rm.add_argument("name")
    serve_ = cmds.add_parser("serve", help="edit the graph in a browser (node editor)")
    serve_.add_argument("--port", type=int, default=PORT)
    opts = parser.parse_args(argv)

    if not shutil.which("dot"):
        print("dev_tools.py: Graphviz dot not found - fix: brew install graphviz", file=sys.stderr)
        return 2

    if opts.cmd == "serve":
        return serve(opts.port)
    if opts.cmd:
        args = {k: v for k, v in vars(opts).items() if k not in ("cmd", "check") and v is not None}
        if opts.cmd == "set" and len(args) == 1:
            parser.error("set needs at least one field")
        problems = apply(opts.cmd, args)
        for problem in problems:
            print(f"dev_tools.py: {problem}", file=sys.stderr)
        return 1 if problems else 0

    records = parse(REC)
    problems = validate(records)
    for problem in problems:
        print(f"dev_tools.rec: {problem}", file=sys.stderr)
    if problems:
        return 1

    out = charts(records)
    if opts.check:
        stale = 0
        for path, svg in out.items():
            current = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
            if current != svg:
                print(f"{os.path.basename(path)} is stale - fix: ./dev_tools.py", file=sys.stderr)
                stale = 1
        return stale

    draw(records, out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
