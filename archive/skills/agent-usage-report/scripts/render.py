"""Self-contained HTML report: inline CSS, inline SVG, no network, no JS.

Every chart is generated as SVG in Python, so the output file renders on a
plane and can be emailed as a single file. Hover text uses SVG ``<title>``
elements, which every browser shows natively.
"""

from __future__ import annotations

import datetime
import html
import json
import re


def normalize(name):
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())

BG = "#0e1116"
PANEL = "#161b22"
PANEL2 = "#1c232d"
GRID = "#2a2f3a"
TEXT = "#e6edf3"
MUTED = "#8b949e"
BLUE = "#6ea8fe"
GREEN = "#5fd38d"
AMBER = "#f2c14e"
RED = "#ef6f6c"
PURPLE = "#b388ff"
TEAL = "#4dd0c7"

PALETTE = [BLUE, GREEN, AMBER, PURPLE, TEAL, RED, "#f78fb3", "#9ecbff"]

HARNESS_LABELS = {
    "pi": "pi",
    "claude_code": "Claude Code",
    "codex": "Codex",
    "opencode": "opencode",
    "generic": "Other",
}


def esc(value):
    return html.escape(str(value), quote=True)


def fmt_tokens(value):
    value = float(value or 0)
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(value) >= limit:
            return "%.2f%s" % (value / limit, suffix)
    return "%d" % round(value)


def fmt_int(value):
    return "{:,}".format(int(round(float(value or 0))))


def fmt_money(value, places=None):
    value = float(value or 0)
    if places is None:
        places = 4 if abs(value) < 1 else 2
    return "$%s" % ("{:,.%df}" % places).format(value)


def fmt_people(value):
    return "%.2f" % float(value or 0)


# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# Plotly charts. plotly.js itself is inlined into the page once, so the
# report is still a single self-contained HTML file.
# --------------------------------------------------------------------------

import plotly.graph_objects as go

_PLOTLY_JS = None


def _plotly_js():
    global _PLOTLY_JS
    if _PLOTLY_JS is None:
        import plotly.offline
        _PLOTLY_JS = plotly.offline.get_plotlyjs()
    return _PLOTLY_JS


def _rgba(color, alpha):
    color = str(color).lstrip("#")
    return "rgba(%d,%d,%d,%.2f)" % (
        int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), alpha)


def _style(fig, height):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=MUTED, size=12,
                  family="-apple-system, BlinkMacSystemFont, sans-serif"),
        margin=dict(l=10, r=10, t=10, b=10), height=height, autosize=True)
    return fig


def _div(fig, height=240, aria="chart"):
    _style(fig, height)
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displaylogo": False, "responsive": True})


def _fmt_id(value_format, fallback="tokens"):
    """Map a python value_format callable to a client-side formatter id."""
    known = {fmt_tokens: "tokens", fmt_money: "money", fmt_int: "int",
             fmt_people: "score2"}
    if value_format in known:
        return known[value_format]
    return fallback if value_format is None else fallback


def _bar_payload(labels, values, notes, colors, horizontal, height,
                 value_format, aria, fmt=None):
    import json as _json
    payload = {
        "labels": labels, "values": values, "notes": notes, "colors": colors,
        "horizontal": horizontal, "height": height,
        "fmt": fmt or _fmt_id(value_format),
    }
    return ('<div class="cbar" role="img" aria-label="%s" data-chart=\'%s\'></div>'
            % (esc(aria), esc(_json.dumps(payload))))


def hbar(rows, width=760, row_height=28, label_width=210, value_width=90,
         color=BLUE, value_format=fmt_tokens, aria="chart", fmt=None):
    """Horizontal bars, rendered client-side with sort/top-N/filter menus.
    rows = [(label, value, note, color?)]."""
    rows = [r for r in rows if r]
    if not rows:
        return _empty(aria)
    return _bar_payload(
        [str(r[0]) for r in rows],
        [float(r[1] or 0) for r in rows],
        [(r[2] if len(r) > 2 and r[2] else "") for r in rows],
        [(r[3] if len(r) > 3 and r[3] else color) for r in rows],
        True, max(80, row_height * len(rows) + 60), value_format, aria, fmt)


def vbar(rows, width=760, height=240, color=BLUE, value_format=fmt_tokens,
         aria="chart", fmt=None):
    """Vertical bars, rendered client-side with sort/top-N/filter menus.
    rows = [(label, value, note)]."""
    rows = [r for r in rows if r]
    if not rows:
        return _empty(aria)
    return _bar_payload(
        [str(r[0]) for r in rows],
        [float(r[1] or 0) for r in rows],
        [(r[2] if len(r) > 2 and r[2] else "") for r in rows],
        [color] * len(rows),
        False, height, value_format, aria, fmt)


def line_chart(points, width=760, height=240, color=BLUE, value_format=fmt_money,
               aria="chart"):
    """Cumulative or per-day line. points = [(label, value)]."""
    points = [(p[0], float(p[1] or 0)) for p in points if p]
    if not points:
        return _empty(aria)
    if len(points) < 2:
        return vbar([(p[0], p[1]) for p in points], width, height, color,
                    value_format, aria)
    fig = go.Figure(go.Scatter(
        x=[p[0] for p in points], y=[p[1] for p in points],
        mode="lines+markers", line=dict(color=color, width=2),
        marker=dict(color=color, size=4),
        fill="tozeroy", fillcolor=_rgba(color, 0.16),
        customdata=[value_format(p[1]) for p in points],
        hovertemplate="%{x}: %{customdata}<extra></extra>"))
    fig.update_yaxes(gridcolor=GRID)
    return _div(fig, height, aria)


def heatmap(matrix, row_labels, col_labels, width=760, height=250, aria="heatmap"):
    fig = go.Figure(go.Heatmap(
        z=matrix, x=[str(c) for c in col_labels], y=[str(r) for r in row_labels],
        colorscale=[[0, PANEL2], [1, BLUE]], showscale=False, xgap=2, ygap=2,
        hovertemplate="%{y} %{x}:00 - %{z} turns<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    return _div(fig, height, aria)


def donut(parts_in, width=260, height=260, aria="donut"):
    """parts = [(label, value, color)]."""
    parts_in = [(p[0], float(p[1] or 0), p[2])
                for p in parts_in if p and float(p[1] or 0) > 0]
    total = sum(p[1] for p in parts_in)
    if not parts_in or not total:
        return _empty(aria)
    fig = go.Figure(go.Pie(
        labels=[p[0] for p in parts_in], values=[p[1] for p in parts_in],
        hole=0.62, marker=dict(colors=[p[2] for p in parts_in]),
        sort=False, textinfo="none",
        customdata=["%s (%.1f%%)" % (fmt_tokens(p[1]), p[1] / total * 100.0)
                    for p in parts_in],
        hovertemplate="%{label}: %{customdata}<extra></extra>"))
    fig.add_annotation(text=fmt_tokens(total), showarrow=False,
                       font=dict(color=TEXT, size=16))
    fig.add_annotation(text="tokens", showarrow=False, yshift=-16,
                       font=dict(color=MUTED, size=10))
    return _div(fig, height, aria)


def scatter(points, width=760, height=340, x_label="cost per 1M ($)",
            y_label="intelligence", aria="scatter"):
    """points = [(label, x, y, color)]."""
    points = [p for p in points if p]
    if not points:
        return _empty(aria)
    fig = go.Figure()
    for label, x, y, color in points:
        fig.add_trace(go.Scatter(
            x=[float(x)], y=[float(y)], mode="markers+text",
            marker=dict(color=color, size=9),
            text=[str(label)], textposition="middle right",
            customdata=["%s=%s, %s=%s" % (
                x_label, fmt_money(float(x)), y_label, fmt_people(float(y)))],
            hovertemplate="%{text}<br>%{customdata}<extra></extra>"))
    fig.update_layout(showlegend=False, xaxis_title=x_label,
                      yaxis_title=y_label)
    fig.update_xaxes(gridcolor=GRID)
    fig.update_yaxes(gridcolor=GRID)
    return _div(fig, height, aria)


def _empty(aria):
    return ('<svg viewBox="0 0 760 80" width="100%%" role="img" aria-label="%s">'
            '<text x="10" y="44" fill="%s" font-size="12">no data</text></svg>'
            % (esc(aria), MUTED))


def _clip(text, limit):
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "\u2026"


# --------------------------------------------------------------------------
# Client-side table: sorting and filtering (no dependencies, offline-safe)
# --------------------------------------------------------------------------

_SCRIPT = """
(function () {
  // Every table inside a section with controls is sortable + filterable.
  // Controls are optional per table: text input, select, checkbox, count span.
  Array.prototype.slice.call(document.querySelectorAll('table')).forEach(function (table) {
    var section = table.closest ? table.closest('section') : null;
    if (!section || !table.tHead || !table.tHead.rows.length) { return; }
    var headers = Array.prototype.slice.call(table.tHead.rows[0].cells);
    var sortable = headers.some(function (h) { return h.getAttribute('data-key'); });
    if (!sortable) { return; }
    var search = section.querySelector('input[type=text]');
    var select = section.querySelector('select');
    var checkbox = section.querySelector('input[type=checkbox]');
    var count = section.querySelector('.count');
    var hint = section.querySelector('.nojs');
    if (hint) { hint.style.display = 'none'; }
    var tbody = table.tBodies[0];
    var sortKey = null;
    var sortDir = -1;

    function cell(row, key) {
      for (var i = 0; i < row.cells.length; i++) {
        if (row.cells[i].getAttribute('data-key') === key) { return row.cells[i]; }
      }
      return null;
    }

    function numeric(row, key) {
      var node = cell(row, key);
      if (!node) { return -Infinity; }
      var raw = node.getAttribute('data-sort');
      if (raw === null) { return -Infinity; }
      var value = parseFloat(raw);
      return isNaN(value) ? -Infinity : value;
    }

    function text(row, key) {
      var node = cell(row, key);
      return node ? node.textContent.trim().toLowerCase() : '';
    }

    function passes(row) {
      if (checkbox && !checkbox.checked &&
          row.getAttribute('data-ranked') === '0') { return false; }
      if (select && select.value &&
          row.getAttribute('data-' + (select.getAttribute('data-attr') || 'harness')) !== select.value) {
        return false;
      }
      if (search && search.value.trim()) {
        var query = search.value.trim().toLowerCase();
        var haystack = row.textContent.toLowerCase();
        if (haystack.indexOf(query) < 0) { return false; }
      }
      return true;
    }

    function sortRows(rows) {
      if (!sortKey) { return rows; }
      // numeric columns carry a data-sort value on their cells; text columns do not
      var probe = rows.length ? cell(rows[0], sortKey) : null;
      var isText = !probe || probe.getAttribute('data-sort') === null;
      rows.sort(function (a, b) {
        var result;
        if (isText) {
          var ta = text(a, sortKey), tb = text(b, sortKey);
          result = ta < tb ? -1 : ta > tb ? 1 : 0;
        } else {
          result = numeric(a, sortKey) - numeric(b, sortKey);
        }
        return result * sortDir;
      });
      return rows;
    }

    function render() {
      var rows = Array.prototype.slice.call(tbody.rows);
      var shown = sortRows(rows.filter(passes));
      for (var j = 0; j < rows.length; j++) {
        rows[j].style.display = shown.indexOf(rows[j]) >= 0 ? '' : 'none';
      }
      for (var i = 0; i < shown.length; i++) { tbody.appendChild(shown[i]); }
      if (count) { count.textContent = shown.length + ' of ' + rows.length + ' rows'; }
    }

    headers.forEach(function (node) {
      var key = node.getAttribute('data-key');
      if (!key) { return; }
      var arrow = document.createElement('span');
      arrow.className = 'arrow';
      node.appendChild(arrow);
      node.addEventListener('click', function () {
        if (sortKey === key) { sortDir = -sortDir; }
        else { sortKey = key; sortDir = -1; }
        headers.forEach(function (other) {
          var mark = other.querySelector('.arrow');
          if (mark) {
            mark.textContent = other.getAttribute('data-key') === sortKey
              ? (sortDir < 0 ? '\u25bc' : '\u25b2') : '';
          }
        });
        render();
      });
    });

    if (search) { search.addEventListener('input', render); }
    if (select) { select.addEventListener('change', render); }
    if (checkbox) { checkbox.addEventListener('change', render); }
    render();
  });
})();

// ---- client-side bar charts with sort / top-N / filter menus ----------
(function () {
  function fmtFor(kind) {
    var fns = {
      money: function (v) {
        var places = Math.abs(v) < 1 ? 4 : 2;
        return '$' + v.toLocaleString(undefined,
          {minimumFractionDigits: places, maximumFractionDigits: places});
      },
      tokens: function (v) {
        var abs = Math.abs(v);
        if (abs >= 1e9) { return (v / 1e9).toFixed(2) + 'B'; }
        if (abs >= 1e6) { return (v / 1e6).toFixed(2) + 'M'; }
        if (abs >= 1e3) { return (v / 1e3).toFixed(2) + 'k'; }
        return String(Math.round(v));
      },
      int: function (v) { return Math.round(v).toLocaleString(); },
      score2: function (v) { return v.toFixed(2); },
      score1: function (v) { return v.toFixed(1); },
      score0: function (v) { return String(Math.round(v)); }
    };
    return fns[kind] || fns.tokens;
  }

  Array.prototype.slice.call(document.querySelectorAll('.cbar')).forEach(function (host) {
    var data = JSON.parse(host.getAttribute('data-chart'));
    var fmt = fmtFor(data.fmt);
    var horizontal = data.horizontal;
    var controls = document.createElement('div');
    controls.className = 'controls';
    controls.innerHTML =
      '<select class="cbar-sort">' +
      '<option value="vdesc">Value high to low</option>' +
      '<option value="vasc">Value low to high</option>' +
      '<option value="name">Label A to Z</option></select>' +
      '<select class="cbar-top"><option value="5">Top 5</option>' +
      '<option value="10">Top 10</option><option value="20">Top 20</option>' +
      '<option value="0" selected>All</option></select>' +
      '<input type="text" placeholder="Filter...">';
    host.parentNode.insertBefore(controls, host);

    function draw() {
      var sort = controls.querySelector('.cbar-sort').value;
      var top = parseInt(controls.querySelector('.cbar-top').value, 10);
      var query = controls.querySelector('input').value.trim().toLowerCase();
      var items = data.labels.map(function (label, i) {
        return {label: label, value: data.values[i], note: data.notes[i],
                color: data.colors[i]};
      });
      if (query) {
        items = items.filter(function (it) {
          return (it.label + ' ' + it.note).toLowerCase().indexOf(query) >= 0;
        });
      }
      if (sort === 'vdesc') { items.sort(function (a, b) { return b.value - a.value; }); }
      else if (sort === 'vasc') { items.sort(function (a, b) { return a.value - b.value; }); }
      else { items.sort(function (a, b) { return a.label < b.label ? -1 : 1; }); }
      if (top > 0) { items = items.slice(0, top); }
      var trace = {
        type: 'bar', orientation: horizontal ? 'h' : 'v',
        x: horizontal ? items.map(function (it) { return it.value; })
                      : items.map(function (it) { return it.label; }),
        y: horizontal ? items.map(function (it) { return it.label; })
                      : items.map(function (it) { return it.value; }),
        marker: {color: items.map(function (it) { return it.color; })},
        text: items.map(function (it) { return fmt(it.value); }),
        textposition: 'outside', cliponaxis: false,
        customdata: items.map(function (it) {
          return fmt(it.value) + (it.note ? ' - ' + it.note : '');
        }),
        hovertemplate: '%{customdata}<extra></extra>'
      };
      var height = Math.max(120, data.height / Math.max(1, data.labels.length) *
                          Math.max(1, items.length));
      Plotly.newPlot(host, [trace], {
        template: 'plotly_dark',
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        font: {color: '#8b949e', size: 12,
               family: '-apple-system, BlinkMacSystemFont, sans-serif'},
        margin: {l: 10, r: 10, t: 10, b: 10}, height: height, autosize: true,
        xaxis: horizontal ? {gridcolor: '#2a2f3a'} : {},
        yaxis: horizontal ? {autorange: 'reversed', automargin: true}
                          : {gridcolor: '#2a2f3a', automargin: true}
      }, {displaylogo: false, responsive: true});
    }
    Array.prototype.slice.call(controls.querySelectorAll('select,input'))
      .forEach(function (el) { el.addEventListener('change', draw); el.addEventListener('input', draw); });
    // lazy: first draw only when the chart is near the viewport
    var reserve = Math.max(120, data.height / Math.max(1, data.labels.length) * 2);
    host.style.minHeight = reserve + 'px';
    if ('IntersectionObserver' in window) {
      var drawn = false;
      var drawOnce = function () { if (!drawn) { drawn = true; draw(); } };
      new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { if (e.isIntersecting) { drawOnce(); } });
      }, {rootMargin: '400px'}).observe(host);
    } else {
      draw();
    }
  });
})();
"""

# --------------------------------------------------------------------------
# Report assembly
# --------------------------------------------------------------------------

def build(dataset, meta, config=None):
    models = dataset["models"]
    totals = dataset["totals"]
    ranked = sorted(dataset["ranking"], key=lambda e: (e.get("aa_intelligence") or 0), reverse=True)
    all_models = sorted(models.values(), key=lambda e: e["total"], reverse=True)

    sections = [
        _hero(dataset, meta, totals),
        _leaders(dataset, totals),
        _leaderboard(all_models, dataset),
        _cost_section(all_models, totals),
        _benchmark_section(ranked, dataset),
        _efficiency_section(dataset),
        _projects_section(dataset),
        _sessions_section(dataset),
        _time_section(dataset),        _tools_section(all_models),
        _context_section(all_models),
        _activity_section(dataset),
        _switching_section(dataset),
        _waste_section(all_models, totals),
        _methodology(dataset, meta),
    ]
    return _page(meta, sections)


def _page(meta, sections):
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent usage report - %(title)s</title>
<script>
%(plotlyjs)s
</script>
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: %(bg)s; color: %(text)s;
  font: 14px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Ubuntu, sans-serif;
  -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }
.wrap { max-width: 1400px; margin: 0 auto; padding: 40px 32px 80px; }
h1 { font-size: 30px; margin: 0 0 4px; letter-spacing: -0.02em; }
h2 { font-size: 19px; margin: 0 0 16px; letter-spacing: -0.01em; }
h3 { font-size: 14px; margin: 0 0 10px; color: %(muted)s; text-transform: uppercase; letter-spacing: 0.08em; }
p { margin: 0 0 12px; }
.sub { color: %(muted)s; margin-bottom: 26px; }
section { background: %(panel)s; border: 1px solid %(grid)s; border-radius: 12px;
  padding: 24px; margin-bottom: 18px; }
section.lazy { content-visibility: auto; contain-intrinsic-size: auto 420px; }
.grid { display: grid; gap: 14px; }
.cards { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
.two { grid-template-columns: 1fr 1fr; }
@media (max-width: 720px) { .two { grid-template-columns: 1fr; } }
.card { background: %(panel2)s; border: 1px solid %(grid)s; border-radius: 10px; padding: 16px; }
.card .k { color: %(muted)s; font-size: 11px; text-transform: uppercase; letter-spacing: 0.07em; }
.card .v { font-size: 24px; font-weight: 600; margin-top: 4px; letter-spacing: -0.02em; }
.card .n { color: %(muted)s; font-size: 11px; margin-top: 2px; }
table { width: 100%%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: right; padding: 8px 10px; border-bottom: 1px solid %(grid)s; white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
th { color: %(muted)s; font-weight: 500; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
td.num, th.num { font-variant-numeric: tabular-nums; }
tbody tr:hover td { background: rgba(110,168,254,0.05); }
tr.dim td { opacity: 0.5; }
tr.market-top td { background: rgba(95,211,141,0.08); }
.badge { display: inline-block; padding: 1px 7px; border-radius: 20px; font-size: 11px;
  border: 1px solid %(grid)s; color: %(muted)s; }
.badge.good { color: %(green)s; border-color: rgba(95,211,141,0.4); }
.badge.warn { color: %(amber)s; border-color: rgba(242,193,78,0.4); }
.badge.bad { color: %(red)s; border-color: rgba(239,111,108,0.4); }
.winner { border-color: rgba(110,168,254,0.5);
  background: linear-gradient(180deg, rgba(110,168,254,0.09), rgba(110,168,254,0.02)); }
.winner .v { color: %(blue)s; }
.scroll { overflow-x: auto; }
.scroll::-webkit-scrollbar { height: 10px; }
.scroll::-webkit-scrollbar-thumb { background: %(grid)s; border-radius: 5px; }
.reasons { margin: 0; padding-left: 18px; color: %(muted)s; font-size: 13px; }
.reasons li { margin-bottom: 3px; }
.reasons b { color: %(text)s; font-weight: 600; }
.legend { display: flex; gap: 14px; flex-wrap: wrap; color: %(muted)s; font-size: 12px; margin-top: 8px; }
.legend span i { display: inline-block; width: 9px; height: 9px; border-radius: 3px; margin-right: 5px; }
svg { display: block; }
footer { color: %(muted)s; font-size: 12px; margin-top: 26px; }
code { background: %(panel2)s; padding: 1px 5px; border-radius: 4px; font-size: 12px; }
.cbar { min-height: 160px; }
.controls { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; }
.controls input[type=text], .controls select { background: %(panel2)s; border: 1px solid %(grid)s;
  color: %(text)s; padding: 6px 10px; border-radius: 8px; font-size: 13px; min-width: 150px; }
.controls input[type=text]:focus, .controls select:focus { outline: 1px solid %(blue)s; }
.controls label { color: %(muted)s; font-size: 12px; display: flex; align-items: center; gap: 5px; }
.controls .count { color: %(muted)s; font-size: 12px; margin-left: auto; }
th[data-key] { cursor: pointer; user-select: none; }
th[data-key]:hover { color: %(text)s; }
th .arrow { opacity: 0.55; margin-left: 4px; font-size: 9px; }
.nojs { color: %(amber)s; font-size: 12px; }
</style>
</head>
<body><div class="wrap">
%(body)s
<footer>Generated %(generated)s by <code>agent-usage-report</code>.</footer>
</div>
<script>
%(script)s
</script>
</body></html>""" % {
        "bg": BG, "panel": PANEL, "panel2": PANEL2, "grid": GRID, "text": TEXT,
        "muted": MUTED, "blue": BLUE, "green": GREEN, "amber": AMBER, "red": RED,
        "title": esc(meta["window"]),
        "generated": esc(meta["generated"]),
        "body": "\n".join(sections),
        "script": _SCRIPT,
        "plotlyjs": _plotly_js(),
    }


def _card(key, value, note="", klass=""):
    return ('<div class="card %s"><div class="k">%s</div><div class="v">%s</div>'
            '<div class="n">%s</div></div>' % (klass, esc(key), esc(value), esc(note)))


def _hero(dataset, meta, totals):
    cards = [
        _card("Total spend", fmt_money(totals["cost"]),
              "%s recorded, %s estimated" % (
                  fmt_money(totals["cost_recorded"]), fmt_money(totals["cost_computed"]))),
        _card("Total tokens", fmt_tokens(totals["tokens"]),
              "%s in, %s out" % (fmt_tokens(totals["input"] + totals["cache_read"]),
                                 fmt_tokens(totals["output"]))),
        _card("Models", fmt_int(totals["models"]),
              "%d with AA benchmarks, %d without" % (len(dataset["ranking"]), len(dataset["unranked"]))),
        _card("Sessions", fmt_int(totals["sessions"]),
              "%s requests, %s turns" % (fmt_int(totals["requests"]), fmt_int(totals["turns"]))),
        _card("Blended rate", "%s / 1M" % fmt_money(totals["blended_per_million"]),
              "across all models and harnesses"),
        _card("Cache hit rate", "%.1f%%" % totals["cache_hit_rate"],
              "%s avoided at full input rates" % fmt_money(totals["cache_saving"])),
    ]
    harness_bits = ", ".join("%s (%s)" % (esc(h["label"]), fmt_int(h["records"]))
                             for h in meta["detected"]) or "none"
    window = ("%s to %s" % (esc(meta["window_start"]), esc(meta["window_end"])))
    return section(
        "<h1>Agent usage and spend</h1>"
        '<p class="sub">%s &middot; harnesses found: %s</p>'
        '<div class="grid cards">%s</div>' % (window, harness_bits, "".join(cards)),
        title=None)


def section(body, title=None, lazy=False):
    heading = "<h2>%s</h2>" % esc(title) if title else ""
    cls = " class=\"lazy\"" if lazy else ""
    return '<section%s>%s%s</section>' % (cls, heading, body)


def _leaders(dataset, totals):
    """The verdict: market's 3 top frontier + 3 top flash-tier models,
    flagged when they also appear in your logs."""
    market = dataset.get("market") or {}
    cards = [_tier_card("Most popular frontier models", market.get("frontier") or []),
             _tier_card("Most popular flash-tier models", market.get("flash") or [])]
    return section('<div class="grid two">%s</div>' % "".join(cards),
                   "The verdict - world's most-used models")


def _tier_card(title, entries):
    if not entries:
        return ('<div class="card"><div class="k">%s</div><div class="v">&ndash;</div>'
                '<div class="n">no usage data (set openrouter_api_key in config '
                'or OR_API_KEY)</div></div>' % esc(title))
    rows = []
    for rank, e in enumerate(entries, 1):
        mine = (" <span class='badge good'>you use it</span>" if e.get("used_by_you")
                else " <span class='badge'>not in your logs</span>")
        intel = ("AA index %.1f &middot; " % e["aa_intelligence"]
                 if e.get("aa_intelligence") is not None else "")
        rows.append("<li>%d. <b>%s</b> &middot; %.1f%% of market tokens &middot; %s%s</li>"
                    % (rank, esc(e["model"]), e["share"], intel, mine))
    return ('<div class="card winner"><div class="k">%s</div>'
            '<div class="v">%s</div>'
            '<ul class="reasons">%s</ul></div>'
            % (esc(title), esc(entries[0]["model"]), "".join(rows)))


def _market_keys(dataset):
    market = dataset.get("market") or {}
    return {e["key"] for tier in ("frontier", "flash")
            for e in (market.get(tier) or [])}


def _leaderboard(all_models, dataset):
    if not all_models:
        return section("<p>No model turns found.</p>", "Model leaderboard", lazy=True)
    market_keys = _market_keys(dataset)

    columns = [
        ("model", "Model", "text"),
        ("harness", "Harness", "text"),
        ("turns", "Turns", "num"),
        ("input", "Input", "num"),
        ("output", "Output", "num"),
        ("total", "Total", "num"),
        ("cost_per_million", "$/1M", "num"),
        ("cost_total", "Cost", "num"),
        ("intelligence_score", "AA Intel", "num"),
        ("efficiency_score", "Eff", "num"),
        ("provenance", "Cost source", "text"),
    ]
    head = "<tr>" + "".join(
        "<th data-key='%s' class='%s'>%s</th>" % (key, "num" if kind == "num" else "", label)
        for key, label, kind in columns) + "</tr>"

    rows = []
    for entry in all_models:
        harness = _dominant(entry.get("harnesses"))
        is_ranked = entry.get("aa_intelligence") is not None
        is_market = normalize(entry["model"]) in market_keys
        classes = []
        if not is_ranked:
            classes.append("dim")
        if is_market:
            classes.append("market-top")
        dim = ' class="%s"' % " ".join(classes) if classes else ""
        provenance = entry.get("cost_provenance") or "?"
        prov_class = {"recorded": "good", "computed": "warn", "mixed": ""}.get(provenance, "")
        cells = [
            ("model",
             entry["model"] + (" <span class='badge good'>market top</span>" if is_market else ""),
             None, "text"),
            ("harness", HARNESS_LABELS.get(harness, harness), None, "text"),
            ("turns", fmt_int(entry["turns"]), entry["turns"], "num"),
            ("input", fmt_tokens(entry["input"]), entry["input"], "num"),
            ("output", fmt_tokens(entry["output"]), entry["output"], "num"),
            ("total", fmt_tokens(entry["total"]), entry["total"], "num"),
            ("cost_per_million", fmt_money(entry["cost_per_million"]),
             entry["cost_per_million"], "num"),
            ("cost_total", fmt_money(entry["cost_total"]), entry["cost_total"], "num"),
            ("intelligence_score",
             "%.1f" % entry["aa_intelligence"] if is_ranked else "&ndash;",
             entry["aa_intelligence"] if is_ranked else None, "num"),
            ("efficiency_score",
             "%.0f" % entry["efficiency_score"] if is_ranked else "&ndash;",
             entry["efficiency_score"] if is_ranked else None, "num"),
            ("provenance", "<span class='badge %s'>%s</span>" % (prov_class, esc(provenance)),
             None, "text"),
        ]
        rendered = []
        for key, display, sort_value, kind in cells:
            sort_attr = "" if sort_value is None else " data-sort='%s'" % sort_value
            klass = " class='num'" if kind == "num" else ""
            rendered.append("<td data-key='%s'%s%s>%s</td>" % (key, klass, sort_attr, display))
        rows.append("<tr%s data-model=\"%s\" data-harness=\"%s\" data-ranked=\"%d\">%s</tr>"
                    % (dim, esc(entry["model"]), esc(harness), 1 if is_ranked else 0,
                       "".join(rendered)))

    harnesses = sorted({_dominant(e.get("harnesses")) for e in all_models})
    options = "".join("<option value='%s'>%s</option>" % (esc(name), esc(HARNESS_LABELS.get(name, name)))
                      for name in harnesses)
    controls = (
        '<div class="controls">'
        '<input type="text" id="lb-search" placeholder="Filter models...">'
        '<select id="lb-harness"><option value="">All harnesses</option>%s</select>'
        '<label><input type="checkbox" id="lb-ranked"> With AA data only</label>'
        '<span class="count" id="lb-count"></span>'
        '</div>' % options)
    hint = ('<p class="nojs" id="lb-hint">Sort by clicking a column header, or filter '
            'with the controls above. (Enable JavaScript to use them.)</p>')
    note = ("Dimmed rows have no Artificial Analysis benchmark match (fix with "
            "aa.json overrides). Click a column to sort. AA Intel is the "
            "Artificial Analysis Intelligence Index; Eff ranks AA-index points "
            "per dollar you paid.")
    return section(controls + hint
                   + '<div class="scroll"><table id="lb" data-default-key="total" data-default-dir="desc"><thead>%s</thead><tbody>%s</tbody></table></div>'
                   % (head, "".join(rows))
                   + '<p class="sub" style="margin-top:12px">%s</p>' % esc(note),
                   "Model leaderboard", lazy=True)


def _dominant(mapping):
    if not mapping:
        return ""
    return sorted(mapping.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _cost_section(all_models, totals):
    with_cost = [e for e in all_models if e.get("cost_per_million")]
    rows = [(e["model"], e["cost_per_million"],
             "%s total, %s turns" % (fmt_money(e["cost_total"]), fmt_int(e["turns"])),
             PALETTE[index % len(PALETTE)]) for index, e in enumerate(with_cost)]
    split = totals.get("cost_split") or {}
    donut_parts = [
        ("Cache read", split.get("cache_read", 0), TEAL),
        ("Cache write", split.get("cache_write", 0), PURPLE),
        ("Output", split.get("output", 0), GREEN),
        ("Input (uncached)", split.get("input", 0), BLUE),
    ]
    top = sorted(with_cost, key=lambda e: -e["cost_total"])[:5]
    legend = "".join('<span><i style="background:%s"></i>%s %s</span>'
                     % (color, esc(label), fmt_money(value))
                     for label, value, color in donut_parts)
    body = ('<div class="grid two"><div><h3>Cost per 1 million tokens</h3>%s</div>'
            '<div><h3>Where the money went (estimated from rates)</h3>%s'
            '<div class="legend">%s</div></div></div>'
            '<p class="sub" style="margin-top:14px">Blended rate across everything: '
            '<b>%s per 1M</b>. Cache reads served <b>%.1f%%</b> of all input tokens; '
            'paying full input rates for that volume would have added about <b>%s</b>.</p>'
            '<h3 style="margin-top:18px">Top spenders</h3>%s'
            % (hbar(rows, value_format=lambda v: fmt_money(v), color=AMBER, fmt="money"),
               donut(donut_parts), legend,
               fmt_money(totals["blended_per_million"]), totals["cache_hit_rate"],
               fmt_money(totals["cache_saving"]),
               hbar([(e["model"], e["cost_total"],
                      "%s%% of spend" % fmt_people(
                          e["cost_total"] * 100.0 / (totals["cost"] or 1)))
                     for e in top], value_format=fmt_money, color=RED)))
    return section(body, "Cost", lazy=True)


def _benchmark_section(ranked, dataset):
    """Artificial Analysis Intelligence Index of the models you used."""
    with_index = [e for e in ranked if e.get("aa_intelligence") is not None]
    if not with_index:
        return section("<p>No Artificial Analysis data: set aa_api_key in "
                       "config.json (or the AA_API_KEY environment variable) and "
                       "re-run with --refresh-pricing.</p>", "Benchmarks", lazy=True)
    rows = [(e["model"], e["aa_intelligence"],
             "%s turns, %s / 1M" % (fmt_int(e["turns"]), fmt_money(e["cost_per_million"])),
             PALETTE[index % len(PALETTE)]) for index, e in enumerate(with_index)]
    note = ("Artificial Analysis Intelligence Index (0-100): independent "
            "benchmark composite, describing the model in general - not your "
            "usage. Only models that appear in your logs are shown.")
    return section(hbar(rows, value_format=lambda v: "%.1f" % v, color=BLUE, fmt="score1")
                   + '<p class="sub" style="margin-top:12px">%s</p>' % esc(note),
                   "Benchmarks (Artificial Analysis)", lazy=True)


def _efficiency_section(dataset):
    ranked = [e for e in dataset["ranking"] if e.get("aa_intelligence") is not None]
    if not ranked:
        return section("<p>No benchmark data.</p>", "Efficiency", lazy=True)
    points = [(e["model"], e["cost_per_million"], e["aa_intelligence"],
               PALETTE[index % len(PALETTE)]) for index, e in enumerate(ranked)]
    rows = [(e["model"], e["value_per_dollar"],
             "%.1f AA-index points per $1/1M" % e.get("value_per_dollar", 0)) for e in
            sorted(ranked, key=lambda x: -x["value_per_dollar"])]
    return section(
        '<h3>AA Intelligence vs cost - upper-left is best</h3>%s'
        '<div class="grid two" style="margin-top:14px"><div><h3>Efficiency</h3>%s</div></div>'
        % (scatter(points, y_label="AA Intelligence Index"),
           hbar(rows, value_format=lambda v: "%.1f" % v, color=GREEN, fmt="score1")),
        "Efficiency", lazy=True)


def _projects_section(dataset):
    projects = sorted(dataset["projects"].values(), key=lambda p: -p["total"])[:12]
    if not projects:
        return section("<p>No project data.</p>", "Projects")
    rows = [(p["project"], p["total"],
             "%s, %s turns" % (fmt_money(p.get("cost_recorded", 0)), fmt_int(p["turns"])),
             PALETTE[index % len(PALETTE)]) for index, p in enumerate(projects)]
    return section(hbar(rows, label_width=280), "Projects by tokens", lazy=True)


def _sessions_section(dataset):
    sessions = sorted(
        dataset.get("sessions_detail") or [],
        key=lambda s: (-(s.get("cost_total") or 0),
                       -(s.get("input") + s.get("cache_read")
                         + s.get("cache_write") + s.get("output"))))
    sessions = [s for s in sessions if s.get("turns")][:20]
    if not sessions:
        return section("<p>No session data.</p>", "Most expensive sessions", lazy=True)
    head = "<tr>" + "".join(
        "<th data-key='%s' class='%s'>%s</th>" % (key, "num" if kind == "num" else "", label)
        for key, label, kind in [
            ("session", "Session", "text"), ("harness", "Harness", "text"),
            ("project", "Project", "text"), ("models", "Models", "text"),
            ("turns", "Turns", "num"), ("tokens", "Tokens", "num"),
            ("cost", "Cost", "num"), ("provenance", "Cost source", "text")]) + "</tr>"
    rows = []
    for sess in sessions:
        tokens = sess["input"] + sess["cache_read"] + sess["cache_write"] + sess["output"]
        sid = str(sess.get("session_id") or "")
        sid = sid if len(sid) <= 18 else sid[:8] + "\u2026" + sid[-6:]
        prov = sess.get("cost_provenance") or "?"
        prov_class = {"recorded": "good", "computed": "warn"}.get(prov, "")
        mix = ", ".join("%s (%d)" % (esc(_clip(name, 24)), count)
                        for name, count in sorted((sess.get("models") or {}).items(),
                                                  key=lambda kv: -kv[1])[:3])
        rows.append(
            "<tr>"
            "<td data-key='session'>%s</td>"
            "<td data-key='harness'>%s</td>"
            "<td data-key='project'>%s</td>"
            "<td data-key='models'>%s</td>"
            "<td data-key='turns' class='num' data-sort='%d'>%s</td>"
            "<td data-key='tokens' class='num' data-sort='%d'>%s</td>"
            "<td data-key='cost' class='num' data-sort='%.6f'>%s</td>"
            "<td data-key='provenance'><span class='badge %s'>%s</span></td>"
            "</tr>" % (
                esc(sid),
                esc(HARNESS_LABELS.get(sess.get("harness"), sess.get("harness") or "")),
                esc(_clip(sess.get("project") or "", 34)), mix,
                sess["turns"], fmt_int(sess["turns"]),
                tokens, fmt_tokens(tokens),
                sess.get("cost_total") or 0.0, fmt_money(sess.get("cost_total")),
                prov_class, esc(prov)))
    note = ("Top %d sessions in the window by cost. Sessions from harnesses that "
            "record real spend (pi, opencode) show billed dollars; the rest are "
            "estimated from rates." % len(sessions))
    return section('<div class="controls">'
                   '<input type="text" placeholder="Filter sessions...">'
                   '<span class="count"></span></div>'
                   + '<div class="scroll"><table data-default-key="cost" data-default-dir="desc"><thead>%s</thead><tbody>%s</tbody></table></div>'
                   % (head, "".join(rows))
                   + '<p class="sub" style="margin-top:12px">%s</p>' % esc(note),
                   "Most expensive sessions", lazy=True)


def _time_section(dataset):
    daily = sorted(dataset["daily"].values(), key=lambda d: d["day"])
    if not daily:
        return section("<p>No time data.</p>", "Spend over time", lazy=True)
    cost_points = [(d["day"][5:], d["cost_recorded"]) for d in daily]
    token_points = [(d["day"][5:], d["total"]) for d in daily]
    total_cost = sum(d["cost_recorded"] for d in daily)
    days = max(1, len(daily))
    burn = total_cost / days
    body = ('<div class="grid two"><div><h3>Recorded cost per day</h3>%s</div>'
            '<div><h3>Tokens per day</h3>%s</div></div>'
            '<p class="sub" style="margin-top:12px">Average burn %s/day across %d active days '
            '(recorded cost only; estimated cost from Claude Code and Codex is not dated per day).</p>'
            % (line_chart(cost_points, value_format=fmt_money, color=AMBER),
               line_chart(token_points, value_format=fmt_tokens, color=BLUE),
               fmt_money(burn), days))
    return section(body, "Spend over time", lazy=True)


def _tools_section(all_models):
    totals = {}
    for entry in all_models:
        for name, count in (entry.get("tools") or {}).items():
            totals[name] = totals.get(name, 0) + count
    if not totals:
        return section("<p>No tool call data in these harnesses.</p>", "Tool usage", lazy=True)
    rows = sorted(totals.items(), key=lambda kv: -kv[1])[:14]
    per_model = [(e["model"], e["tool_calls"], "%s%% tool error rate" % fmt_people(e["tool_error_rate"]))
                 for e in sorted(all_models, key=lambda x: -x["tool_calls"])[:10] if e["tool_calls"]]
    body = ('<div class="grid two"><div><h3>Most-called tools (all harnesses)</h3>%s</div>'
            '<div><h3>Tool calls per model</h3>%s</div></div>'
            % (hbar([(k, v) for k, v in rows], color=TEAL, fmt="int"),
               hbar(per_model, color=PURPLE, fmt="int")))
    return section(body, "Tool usage", lazy=True)


def _context_section(all_models):
    rows = [(e["model"], e.get("avg_input_per_turn", 0),
             "%s%% of a %s window" % (fmt_people(e.get("context_pressure", 0)),
                                      fmt_tokens(e.get("context_window", 0))))
            for e in all_models if e.get("context_window")]
    if not rows:
        return section("<p>No context window data (pricing catalog unavailable).</p>",
                       "Context pressure", lazy=True)
    rows.sort(key=lambda r: -r[1])
    body = ('<h3>Average input tokens per turn</h3>%s'
            '<p class="sub" style="margin-top:12px">How much of the model context window an '
            'average turn consumes. Higher means you rely on long context and pay more per call.</p>'
            % hbar(rows[:14], color=BLUE))
    return section(body, "Context pressure", lazy=True)


def _activity_section(dataset):
    matrix = dataset["hourly"]
    if not any(any(row) for row in matrix):
        return section("<p>No activity data.</p>", "When you work", lazy=True)
    body = ('<h3>Turns by weekday and hour (local time)</h3>%s'
            % heatmap(matrix, dataset["weekdays"], [str(h) for h in range(24)]))
    return section(body, "When you work", lazy=True)


def _switching_section(dataset):
    switches = dataset.get("switches") or {}
    if not switches:
        return section("<p>No model switching detected.</p>", "Model switching", lazy=True)
    rows = sorted(switches.items(), key=lambda kv: -kv[1])[:10]
    items = [("%s → %s" % (a, b), count) for (a, b), count in rows]
    return section(hbar(items, label_width=300, color=PURPLE, fmt="int"), "Model switching", lazy=True)


def _waste_section(all_models, totals):
    wasteful = [e for e in all_models if e.get("error_stops")]
    if not wasteful:
        return section('<p class="sub">No failed or aborted turns recorded. Clean run.</p>',
                       "Waste", lazy=True)
    rows = [(e["model"], e["waste_cost"],
             "%s failed/aborted of %s turns (%s%%)"
             % (fmt_int(e["error_stops"]), fmt_int(e["turns"]), fmt_people(e["error_rate"])))
            for e in sorted(wasteful, key=lambda x: -x.get("waste_cost", 0))]
    body = ('<div class="grid cards">%s%s</div><div style="margin-top:16px">%s</div>'
            % (_card("Failed turns", fmt_int(totals["wasted_turns"])),
               _card("Estimated waste", fmt_money(totals["waste"]),
                     "cost of turns that errored or aborted"),
               hbar(rows, value_format=fmt_money, color=RED)))
    return section(body, "Waste", lazy=True)


def _methodology(dataset, meta):
    detected = ", ".join("%s (%s records)" % (esc(h["label"]), fmt_int(h["records"]))
                         for h in meta["detected"]) or "none"
    missing = ", ".join(esc(m) for m in meta["missing"]) or "none"
    body = """
<h3>Model quality</h3>
<p class="sub">Quality comes from the <b>Artificial Analysis Intelligence Index</b>
(0-100), an independent public benchmark composite of reasoning and knowledge
evaluations. It describes the model in general, not how you used it. The earlier
usage-derived "intelligence" composite (turn counts, correction guesses, token
burn) was removed: it measured your tasks, not the model.</p>
<h3>Ranking rules</h3>
<ul class="reasons">
<li><b>Most intelligent</b>: highest AA Intelligence Index among the models that
appear in your logs.</li>
<li><b>Efficiency</b> = AA index divided by the blended cost per 1M tokens you
actually paid; a free model that scores well wins outright. Ranked per-dollar,
not as a raw index.</li>
<li>Models without an AA benchmark match are dimmed in the leaderboard; fix name
mismatches with aa.json overrides.</li>
</ul>
<h3>Cost</h3>
<p class="sub">Harnesses that record real spend (pi, opencode) keep it. Claude Code
and Codex log tokens but no dollars, so their cost is estimated from per-million
rates. Rates come from: <b>%s</b>. Records marked <span class="badge good">recorded</span>
are billed truth; <span class="badge warn">computed</span> are estimates.</p>
<h3>Sources</h3>
<ul class="reasons">
<li>Harnesses found: %s</li>
<li>Harnesses not present: %s</li>
<li>Pricing catalog: %s</li>
<li>Benchmarks: %s</li>
<li>Market usage share: %s (OpenRouter daily token totals; flash/frontier tiers
from Artificial Analysis: frontier = top quartile of the AA Intelligence Index
catalog, flash = cheap fast variants by name or price/speed)</li>
</ul>
""" % (esc(meta["pricing_source"]),
       detected, missing, fmt_int(meta["pricing_models"]) + " models",
       esc(meta["benchmark_source"]),
       esc(meta.get("usage_source", "-")))
    return section(body, "Methodology", lazy=True)
