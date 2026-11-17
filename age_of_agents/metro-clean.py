# Build ishikari-metro-clean.svg: the metro map laid out for reading.
# Three rows read left to right like text; cross-row links are short
# transfer spurs with a named destination instead of long lines.
import os
W, H = 1720, 1230
BG = "#0B1120"; TXT = "#F1F5F9"; SUB = "#A8B3C7"
BLUE = "#60A5FA"; GREEN = "#4ADE80"; RED = "#F87171"; GOLD = "#FBBF24"; PURP = "#C4B5FD"; TEAL = "#2DD4BF"; GREY = "#94A3B8"
o = []
def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def txt(x, y, lines, fill=TXT, size=14, anchor="start", weight="400", lh=None):
    lh = lh or size + 4
    return "".join(f'<text class="h" x="{x}" y="{y + i * lh}" fill="{fill}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}">{esc(l)}</text>' for i, l in enumerate(lines))
def d(pts): return "M" + " L".join(f"{x},{y}" for x, y in pts)

R1, R2, R3 = 200, 520, 980
lines = [  # name, colour, points, width, dash
 ("plan",  BLUE,  [(120,R1),(1440,R1),(1600,R1),(1600,360),(60,360),(60,R2),(200,R2)], 12, ""),
 ("ask",   GOLD,  [(440,R1),(440,90)], 7, ""),
 ("res",   BLUE,  [(440,R1),(440,290)], 7, ""),
 ("build", GREEN, [(200,R2),(1320,R2),(1600,R2),(1600,820),(60,820),(60,R3),(1290,R3)], 12, ""),
 ("bugin", RED,   [(760,R2),(760,640),(700,700),(620,700)], 8, ""),
 ("clash", RED,   [(1040,R2),(1040,700),(620,700)], 6, "10 6"),
 ("bugout",RED,   [(620,700),(240,700),(200,660),(200,R2)], 8, ""),
 ("r1",    RED,   [(760,R2),(730,580),(230,580),(200,R2)], 5, ""),
 ("logA",  GREY,  [(1320,R2),(1320,646)], 4, "4 6"),
 ("drop",  RED,   [(620,700),(620,770)], 6, ""),
 ("mfail", RED,   [(200,R3),(200,1070)], 6, "10 6"),
 ("tidy",  TEAL,  [(440,R3),(500,1050),(560,1050),(760,1050),(940,1050),(1000,R3)], 9, ""),
 ("tdrop", TEAL,  [(760,1050),(760,1160)], 6, "10 6"),
 ("crit",  GREY,  [(1000,R3),(1000,880)], 6, "4 6"),
 ("after", PURP,  [(1290,R3),(1630,R3)], 9, ""),
 ("cfix",  PURP,  [(1450,R3),(1450,1070)], 6, "10 6"),
]
# x, y, name, sub lines, kind, label anchor (dx, dy, anchor)
L_UP = (0, -52, "middle"); L_DN = (0, 34, "middle")
stations = [
 (120,R1,"Task",["you give it, or a","dropped cleanup plan"],"term",L_DN),
 (440,R1,"Investigator Ant",["stays alive, reads the repo once,","gets each answer as a message"],"x",(-22,-60,"end")),
 (440,90,"You",["up to 4 questions a round (/ask-simple);","answering approves the whole run"],"term",(26,-6,"start")),
 (440,290,"Researcher Ants",["up to 5, web + computer;","the investigator waits for facts"],"end",(24,-4,"start")),
 (700,R1,"investigation_report.md",["written when nothing is unclear;","investigator stopped"],"st",L_DN),
 (960,R1,"Add Requirement Ant",["req add, keeps the :ID:s"],"st",L_DN),
 (1200,R1,"Architect Ant",["writes architecture.md"],"st",L_UP),
 (1440,R1,"Worker plans",["one per worker ant:","title, files, after"],"st",L_DN),
 (200,R2,"Worker Ants",["max 5, one worktree each,","code + tests + docs","stuck: next fix round"],"x",(0,-74,"middle")),
 (480,R2,"Anti-monitor",["the build script: starts an","inspector as soon as a task is built"],"st",L_UP),
 (760,R2,"Inspector Ants",["one per built task: checks","plan + design, runs its tests"],"x",(0,-60,"middle")),
 (1040,R2,"Combined test",["Integrator Ant merges passing","tasks in a scratch copy, tests once"],"x",(0,-60,"middle")),
 (1320,660,"Logbook",["bulletin + bug bounty boards,","written at the end of build and","of finish. For you; no ant reads it."],"log",(26,-4,"start")),
 (620,700,"Detective Ant",["finds why, writes the next","fix plan, never code"],"x",(-26,34,"end")),
 (620,770,"Dropped",["after 3 tries on a bug,","branch kept"],"term",(26,-4,"start")),
 (200,R3,"Merger ant",["straight line in a scratch","copy, tests once, no review"],"x",(0,-58,"middle")),
 (200,1070,"merge failed",["next build round,","back to the Worker Ants"],"term",(26,-4,"start")),
 (440,R3,"Janitor ant",["cleanup plan for this run's mess,","built + checked before main moves"],"x",L_UP),
 (560,1050,"Cleanup worker",["builds it on top of the merge"],"st",(0,34,"middle")),
 (760,1050,"Cleanup inspector",["plan + tests = combined test;","fail: one fix round"],"st",(0,34,"middle")),
 (760,1160,"Dropped cleanup",["branch kept, plan offered as","the next run's Task"],"term",(26,-4,"start")),
 (1000,R3,"Philosopher ant",["after the cleanup:","5 best critiques"],"x",(26,40,"start")),
 (1000,880,"Critiques board",["bridge to the next run:","its Investigator reads it"],"term",(-26,-4,"end")),
 (1150,R3,"Finisher ant",["fast-forwards main, cleans","up, sets bulletin rows done"],"st",L_UP),
 (1290,R3,"MAIN",["fast-forward only,","never pushed"],"term",L_DN),
 (1450,R3,"checkCommand",["builds and checks the real app"],"st",(0,-52,"middle")),
 (1450,1070,"check-fix round",["from the moved main, once"],"term",(26,-4,"start")),
 (1630,R3,"req done",["marks the kept :ID:s"],"term",(0,-52,"middle")),
]
o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="ui-sans-serif,-apple-system,Helvetica,Arial,sans-serif">')
o.append('<title>Ishikari metro map, readable</title>')
o.append('<defs><filter id="g" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>')
o.append(f'<style>.h{{paint-order:stroke;stroke:{BG};stroke-width:5px;stroke-linejoin:round}}.flow{{animation:f 1.2s linear infinite}}@keyframes f{{to{{stroke-dashoffset:-32}}}}</style>')
o.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
o.append(txt(40, 44, ["ISHIKARI METRO"], TXT, 28, weight="800"))
o.append(txt(330, 44, ["Read it like a page: each row left to right, then wrap to the next row."], SUB, 15))
# row bands
for y, label, c in [(R1, "1 ASK  ·  2 PLAN", BLUE), (R2, "3 BUILD  ·  4 CHECK  ·  5 FIX", GREEN), (R3, "6 FINISH", GREEN)]:
    o.append(txt(W - 30, y - 100 if y != R1 else 120, [label], c, 13, "end", "800"))
for name, c, pts, w, dash in lines:
    o.append(f'<path id="L-{name}" d="{d(pts)}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"' + (f' stroke-dasharray="{dash}" class="flow"' if dash else '') + '/>')
o.append(txt(1612, 290, ["to row 2"], BLUE, 13, weight="700"))
o.append(txt(1612, 680, ["to row 3"], GREEN, 13, weight="700"))
o.append(txt(1330, 590, ["end of build: written once"], GREY, 13))
o.append(txt(772, 640, ["still open after round 1:", "the script hands it over"], RED, 13))
o.append(txt(480, 604, ["round 1: the inspector's own fix plan"], RED, 13, "middle"))
o.append(txt(1052, 640, ["fail: tasks clash,", "merge, then fix loop"], RED, 13))
o.append(txt(250, 684, ["fix plan back to a worker  ·  max 2 extra build rounds"], RED, 13))
for x, y, nm, sub, kind, (dx, dy, an) in stations:
    if kind == "x":
        o.append(f'<circle cx="{x}" cy="{y}" r="14" fill="{BG}" stroke="{TXT}" stroke-width="5"/>')
    elif kind == "term":
        o.append(f'<rect x="{x-14}" y="{y-14}" width="28" height="28" rx="7" fill="{BG}" stroke="{TXT}" stroke-width="5"/>')
    elif kind == "log":
        o.append(f'<rect x="{x-14}" y="{y-14}" width="28" height="28" rx="4" fill="{BG}" stroke="{GREY}" stroke-width="3" stroke-dasharray="4 3"/>')
    elif kind == "end":
        o.append(f'<line x1="{x-16}" y1="{y}" x2="{x+16}" y2="{y}" stroke="{TXT}" stroke-width="7" stroke-linecap="round"/>')
    else:
        o.append(f'<circle cx="{x}" cy="{y}" r="9" fill="{TXT}"/>')
    o.append(txt(x + dx, y + dy, [nm], TXT, 16, an, "700"))
    o.append(txt(x + dx, y + dy + 19, sub, SUB, 13, an, lh=16))
# numbered trains
trains = [(1, "plan", BLUE, 20, 0), (2, "build", GREEN, 28, 0), (3, "build", GREEN, 28, 5.6), (4, "build", GREEN, 28, 11.2),
          (5, "build", GREEN, 28, 16.8), (6, "build", GREEN, 28, 22.4), (7, "bugin", RED, 5, 0), (8, "bugout", RED, 8, 0),
          (9, "tidy", TEAL, 8, 0), (10, "after", PURP, 5, 0)]
for n, path, c, sec, beg in trains:
    o.append(f'<g filter="url(#g)"><rect x="-14" y="-11" width="28" height="22" rx="6" fill="#FDE047" stroke="{c}" stroke-width="3"/>'
             f'<text y="5" font-size="14" font-weight="800" fill="{BG}" text-anchor="middle">{n}</text>'
             f'<animateMotion dur="{sec}s" begin="{-beg}s" repeatCount="indefinite"><mpath href="#L-{path}"/></animateMotion></g>')
for path, sec in [("ask", 6), ("res", 5)]:
    o.append(f'<circle r="7" fill="#FDE047" filter="url(#g)"><animateMotion dur="{sec}s" repeatCount="indefinite" keyPoints="0;1;0" keyTimes="0;0.5;1" calcMode="linear"><mpath href="#L-{path}"/></animateMotion></circle>')
# key
kx, ky = 1000, 1060
o.append(f'<rect x="{kx}" y="{ky}" width="420" height="124" rx="12" fill="#0F172A" stroke="#334155"/>')
rows = [(BLUE, "1", "task on the plan line"), (GREEN, "2-6", "five worker tasks to MAIN"), (RED, "7-8", "a bug through the fix loop"),
        (TEAL, "9", "the janitor's cleanup"), (PURP, "10", "after main moves")]
for i, (c, n, t) in enumerate(rows):
    y = ky + 24 + i * 20
    o.append(f'<line x1="{kx+16}" y1="{y}" x2="{kx+60}" y2="{y}" stroke="{c}" stroke-width="7" stroke-linecap="round"/>')
    o.append(f'<rect x="{kx+70}" y="{y-9}" width="34" height="18" rx="5" fill="#FDE047" stroke="{c}" stroke-width="2"/><text x="{kx+87}" y="{y+4}" font-size="11" font-weight="800" fill="{BG}" text-anchor="middle">{n}</text>')
    o.append(txt(kx + 114, y + 5, [t], TXT, 13))
o.append(txt(kx + 320, ky + 30, ["dashed:", "a branch or", "a log", "■ terminus", "○ interchange"], SUB, 12))
o.append('</svg>')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ishikari-metro-clean.svg"), "w").write("\n".join(o))
