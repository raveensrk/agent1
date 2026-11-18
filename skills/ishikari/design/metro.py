# Build ishikari-metro.svg: the metro map laid out for reading.
# Four rows read left to right like text; cross-row links are short
# transfer spurs with a named destination instead of long lines.
# Run: python3 metro.py [OUT]  (writes OUT, else ishikari-metro.svg beside it)
import os
import sys
W, H = 2000, 1960
BG = "#0B1120"; TXT = "#F1F5F9"; SUB = "#A8B3C7"
BLUE = "#60A5FA"; GREEN = "#4ADE80"; RED = "#F87171"; GOLD = "#FBBF24"; PURP = "#C4B5FD"; TEAL = "#2DD4BF"; PINK = "#F0ABFC"; GREY = "#94A3B8"
o = []
def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def txt(x, y, lines, fill=TXT, size=14, anchor="start", weight="400", lh=None):
    lh = lh or size + 4
    return "".join(f'<text class="h" x="{x}" y="{y + i * lh}" fill="{fill}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}">{esc(l)}</text>' for i, l in enumerate(lines))
def d(pts): return "M" + " L".join(f"{x},{y}" for x, y in pts)

R1, R2, R3, R4 = 200, 540, 1080, 1520
X = 1900  # where each row wraps down to the next
J1, J2 = 400, 1000  # first and second Judge ant (the gold judge-fix dip runs between)
DIP3, DIP4 = 1170, 1610  # y of the cleanup dip (row 3) and the judge-fix dip (row 4)
lines = [  # name, colour, points, width, dash
 ("plan",  BLUE,  [(120,R1),(X,R1),(X,370),(60,370),(60,R2),(200,R2)], 12, ""),
 ("ask",   GOLD,  [(440,R1),(440,90)], 7, ""),
 ("res",   BLUE,  [(440,R1),(440,300)], 7, ""),
 # "build" is the trains' route only (drawn invisible): it follows the cleanup branch through row 3.
 ("build", "none", [(200,R2),(X,R2),(X,860),(60,860),(60,R3),(760,R3),(800,DIP3),(1520,DIP3),(1580,R3),(X,R3),(X,1400),(60,1400),(60,R4),(1340,R4)], 12, ""),
 ("g1",    GREEN, [(200,R2),(X,R2),(X,860),(60,860),(60,R3),(760,R3)], 12, ""),
 ("g2",    GREEN, [(1580,R3),(X,R3),(X,1400),(60,1400),(60,R4),(1340,R4)], 12, ""),
 ("bugin", RED,   [(760,R2),(760,660),(700,720),(620,720)], 8, ""),
 ("clash", RED,   [(1200,R2),(1200,720),(620,720)], 6, "10 6"),
 ("bugout",RED,   [(620,720),(240,720),(200,680),(200,R2)], 8, ""),
 ("r1",    RED,   [(760,R2),(730,600),(230,600),(200,R2)], 5, ""),
 ("drop",  RED,   [(620,720),(620,790)], 6, ""),
 ("mfail", RED,   [(480,R3),(480,1180)], 6, "10 6"),
 ("tidy",  TEAL,  [(760,R3),(800,DIP3),(1520,DIP3),(1580,R3)], 9, ""),
 ("tloop", TEAL,  [(1240,DIP3),(1240,1270),(940,1270),(940,DIP3)], 6, ""),
 ("tdrop", TEAL,  [(1240,1270),(1340,1340)], 6, "10 6"),
 ("jfix",  GOLD,  [(J1,R4),(460,DIP4),(J2,DIP4),(1060,R4)], 9, ""),
 ("after", PURP,  [(1340,R4),(1780,R4)], 9, ""),
 ("cfix",  PURP,  [(1580,R4),(1580,1660)], 6, "10 6"),
]
# x, y, name, sub lines, kind, label anchor (dx, dy, anchor)
L_UP = (0, -60, "middle"); L_DN = (0, 34, "middle"); RIGHT = (26, -4, "start")
stations = [
 # row 1: ask and plan
 (120,R1,"Task",["you give it, or a","dropped cleanup plan"],"term",L_DN),
 (440,R1,"Investigator ant",["one live agent run by the skill: reads","the repo once, gets each answer as a message;","no Agent tool: the plan workflow runs it"],"x",(-22,-74,"end")),
 (440,90,"You",["up to 4 questions a round (/ask-simple),","8 in all; answering approves the whole run"],"term",(26,-6,"start")),
 (440,300,"Researcher ants  ∥",["up to 5 at once, web + computer,","read only; the investigator waits"],"end",(24,-4,"start")),
 (780,R1,"investigation_report.md",["written when nothing is unclear;","the investigator is stopped"],"st",L_DN),
 (1100,R1,"Add requirement ant",["drafts the requirement entry;","the main session pipes it into ishikari.py req add"],"st",L_DN),
 (1420,R1,"Architect ant",["writes architecture.md","and one plan per task"],"st",L_UP),
 (1700,R1,"Worker plans",["one per task: title, files, after;","checked before anything is built"],"st",L_DN),
 (1370,40,"Logbook",["logbook clerk ant: appends each ant's entry","the moment the ant replies, one clerk at a time, in plan, build and finish.","The live investigator gets only an investigated entry.","Build and finish add a summary at the end. No ant reads it.","~/.ishikari/<repo>-<hash>/logbook.rec"],"log",RIGHT),
 # row 2: build, check, fix
 (200,R2,"Worker ants  ∥",["max 5, one worktree each,","code + tests + docs;","stuck: next fix round"],"x",(0,-84,"middle")),
 (760,R2,"Inspector ants  ∥",["one per built task: plan + design,","runs tests (reuses the worker's if clean)"],"x",(0,-70,"middle")),
 (1200,R2,"Integrator ant",["merges passing tasks in a scratch","copy, tests once: the combined test;","fewer than 2 passing tasks: no combined test"],"x",(0,-78,"middle")),
 (620,720,"Detective ants  ∥",["round 2 on: finds why, writes","the next fix plan, never code"],"x",(-26,34,"end")),
 (620,790,"Dropped",["after 3 tries on a bug or","3 fix rounds; branch kept"],"term",RIGHT),
 # row 3: merge and cleanup
 (200,R3,"Merger ant",["merges in a straight line in a scratch copy,","or reuses build's trial merge; then checks","its own merge with git cherry"],"x",(0,-70,"middle")),
 (480,1180,"merge failed",["a conflict, failed tests, or a task","git finds missing: next build round;","max 2 extra build rounds"],"term",RIGHT),
 (760,R3,"Janitor ant",["plans a cleanup of this run's mess; skipped","under 100 changed lines;","a cleanup run has no janitor"],"x",(0,-70,"middle")),
 (940,DIP3,"Worker ant",["builds the cleanup on the merge"],"st",(0,-44,"middle")),
 (1240,DIP3,"Inspector ant",["checks the cleanup, runs the tests;","fail: one fix round: detective, worker, inspector"],"st",L_UP),
 (1090,1270,"Detective ant",["finds why, plans the one fix"],"st",L_DN),
 (1340,1340,"Dropped cleanup",["still failing: branch kept,","plan offered as the next Task"],"term",RIGHT),
 (1460,DIP3,"Merger ant",["fast-forwards the scratch copy","to the checked cleanup"],"st",L_DN),
 (1580,R3,"cleanup done",["landed or dropped;","nothing to clean also goes straight here"],"x",L_UP),
 # row 4: judge, then main moves
 (160,R4,"Juror ants  ∥",["one per merged task, 5 at once;","only with 3+ merged tasks"],"x",L_DN),
 (J1,R4,"Judge ant",["scores the run 0-10: does the code","match the plans? its own call, not an average"],"x",L_UP),
 (500,DIP4,"Worker ant",["closes the judge's gaps"],"st",L_DN),
 (660,DIP4,"Inspector ant",["checks the fix, runs the tests"],"st",L_UP),
 (820,DIP4,"Merger ant",["fast-forwards the scratch copy to the fix;","the fix lands only through this fast-forward"],"st",L_DN),
 (J2,DIP4,"Judge ant",["scores again; still below 7:","main moves, verdict flagged"],"st",(14,34,"start")),
 (1180,R4,"Finisher ant",["fast-forwards main, removes worktrees,","appends the stage rows, runs the check"],"x",L_UP),
 (1340,R4,"MAIN",["fast-forward only,","never pushed"],"term",L_DN),
 (1580,R4,"checkCommand",["the finisher ant builds and checks the app,","only when main moved and checkCommand is set"],"st",L_UP),
 (1580,1660,"check-fix round",["a failed check: one build round","from the moved main"],"term",RIGHT),
 (1780,R4,"req done",["the main session marks the kept :ID:s","once the check passed, or there is none"],"term",L_DN),
]
o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="ui-sans-serif,-apple-system,Helvetica,Arial,sans-serif">')
o.append('<title>Ishikari metro map, readable</title>')
o.append('<defs><filter id="g" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>')
o.append(f'<style>.h{{paint-order:stroke;stroke:{BG};stroke-width:5px;stroke-linejoin:round}}.flow{{animation:f 1.2s linear infinite}}@keyframes f{{to{{stroke-dashoffset:-32}}}}</style>')
o.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
o.append(txt(40, 44, ["ISHIKARI METRO"], TXT, 28, weight="800"))
o.append(txt(330, 44, ["Read it like a page: each row left to right, then wrap to the next row."], SUB, 15))
# row bands
for y, label, c in [(R1, "1 ASK  ·  2 PLAN", BLUE), (R2, "3 BUILD  ·  4 CHECK  ·  5 FIX", GREEN), (R3, "6 FINISH: MERGE  ·  CLEANUP", GREEN), (R4, "6 FINISH: JUDGE  ·  MAIN MOVES", GREEN)]:
    o.append(txt(W - 30, y - 100 if y != R1 else 120, [label], c, 13, "end", "800"))
for name, c, pts, w, dash in lines:
    o.append(f'<path id="L-{name}" d="{d(pts)}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"' + (f' stroke-dasharray="{dash}" class="flow"' if dash else '') + '/>')
o.append(txt(X + 12, 290, ["to row 2"], BLUE, 13, weight="700"))
o.append(txt(262, R2 - 108, ["a plan may run a saved workflow in place of a worker ant"], SUB, 13, "middle"))
o.append(txt(480, 494, ["built: the script starts", "its inspector at once"], GREEN, 13, "middle"))
o.append(txt(X + 12, 700, ["to row 3"], GREEN, 13, weight="700"))
o.append(txt(X + 12, 1240, ["to row 4"], GREEN, 13, weight="700"))
o.append(txt(772, 660, ["still open after round 1:", "the script hands it over"], RED, 13))
o.append(txt(480, 624, ["round 1: the inspector's own fix plan"], RED, 13, "middle"))
o.append(txt(1212, 660, ["fail: tasks clash: the task takes", "them in, then the fix loop; 2 rounds"], RED, 13))
o.append(txt(250, 704, ["fix plan back to a worker"], RED, 13))
o.append(txt(720, R4 - 14, ["7+, or no gaps: no fix round"], GREEN, 13, "middle", "700"))
o.append(txt(440, 1612, ["below 7 and gaps: one fix round"], GOLD, 13, "end", "700"))
o.append(txt(740, 1720, ["a failed fix keeps its branch;", "the verdict says why"], GOLD, 13, "middle"))
def is_ant(nm):
    n = nm.lower()
    return " ant" in n
def hexm(x, y, r, fill, stroke, sw):
    pts = " ".join(f"{x + r * dx:.1f},{y + r * dy:.1f}" for dx, dy in [(-1,0),(-0.5,-0.87),(0.5,-0.87),(1,0),(0.5,0.87),(-0.5,0.87)])
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
for x, y, nm, sub, kind, (dx, dy, an) in stations:
    if is_ant(nm.replace("  ∥", "")):
        if "∥" in nm:
            o.append(hexm(x + 10, y - 10, 16, BG, TXT, 3) + hexm(x + 5, y - 5, 16, BG, TXT, 3))
        o.append(hexm(x, y, 16, BG, TXT, 5))
    elif kind == "x":
        o.append(f'<circle cx="{x}" cy="{y}" r="14" fill="{BG}" stroke="{TXT}" stroke-width="5"/>')
    elif kind == "term":
        o.append(f'<rect x="{x-14}" y="{y-14}" width="28" height="28" rx="7" fill="{BG}" stroke="{TXT}" stroke-width="5"/>')
    elif kind == "log":  # an open logbook: two pages, a spine, ruled lines
        pg = lambda sx: f'<path d="M{x},{y-10} Q{x+sx*9},{y-15} {x+sx*18},{y-11} L{x+sx*18},{y+13} Q{x+sx*9},{y+9} {x},{y+14} Z" fill="{BG}" stroke="{TXT}" stroke-width="3" stroke-linejoin="round"/>'
        o.append(pg(-1) + pg(1) + f'<line x1="{x}" y1="{y-10}" x2="{x}" y2="{y+14}" stroke="{TXT}" stroke-width="3"/>')
        o.append("".join(f'<line x1="{x+sx*4}" y1="{y-4+k*6}" x2="{x+sx*14}" y2="{y-5+k*6}" stroke="{GREY}" stroke-width="1.5"/>' for sx in (-1, 1) for k in range(3)))
    elif kind == "end":
        o.append(f'<line x1="{x-16}" y1="{y}" x2="{x+16}" y2="{y}" stroke="{TXT}" stroke-width="7" stroke-linecap="round"/>')
    else:
        o.append(f'<circle cx="{x}" cy="{y}" r="9" fill="{TXT}"/>')
    o.append(txt(x + dx, y + dy, [nm], TXT, 16, an, "700"))
    o.append(txt(x + dx, y + dy + 19, sub, SUB, 13, an, lh=16))
# numbered trains
trains = [(1, "plan", BLUE, 20, 0), (2, "build", GREEN, 28, 0), (3, "build", GREEN, 28, 5.6), (4, "build", GREEN, 28, 11.2),
          (5, "build", GREEN, 28, 16.8), (6, "build", GREEN, 28, 22.4), (7, "bugin", RED, 5, 0), (8, "bugout", RED, 8, 0),
          (9, "tidy", TEAL, 8, 0), (10, "after", PURP, 5, 0), (11, "jfix", GOLD, 5, 0)]
for n, path, c, sec, beg in trains:
    o.append(f'<g filter="url(#g)"><rect x="-14" y="-11" width="28" height="22" rx="6" fill="#FDE047" stroke="{c}" stroke-width="3"/>'
             f'<text y="5" font-size="14" font-weight="800" fill="{BG}" text-anchor="middle">{n}</text>'
             f'<animateMotion dur="{sec}s" begin="{-beg}s" repeatCount="indefinite"><mpath href="#L-{path}"/></animateMotion></g>')
for path, sec in [("ask", 6), ("res", 5)]:
    o.append(f'<circle r="7" fill="#FDE047" filter="url(#g)"><animateMotion dur="{sec}s" repeatCount="indefinite" keyPoints="0;1;0" keyTimes="0;0.5;1" calcMode="linear"><mpath href="#L-{path}"/></animateMotion></circle>')
# key
kx, ky = 1440, 1770
o.append(f'<rect x="{kx}" y="{ky}" width="500" height="160" rx="12" fill="#0F172A" stroke="#334155"/>')
rows = [(BLUE, "1", "task on the plan line"), (GREEN, "2-6", "five worker tasks to MAIN"), (RED, "7-8", "a bug through the fix loop"),
        (TEAL, "9", "the janitor's cleanup"), (PURP, "10", "after main moves"), (GOLD, "11", "the judge's fix round: below 7 and gaps")]
for i, (c, n, t) in enumerate(rows):
    y = ky + 24 + i * 20
    o.append(f'<line x1="{kx+16}" y1="{y}" x2="{kx+60}" y2="{y}" stroke="{c}" stroke-width="7" stroke-linecap="round"/>')
    o.append(f'<rect x="{kx+70}" y="{y-9}" width="34" height="18" rx="5" fill="#FDE047" stroke="{c}" stroke-width="2"/><text x="{kx+87}" y="{y+4}" font-size="11" font-weight="800" fill="{BG}" text-anchor="middle">{n}</text>')
    o.append(txt(kx + 114, y + 5, [t], TXT, 13))
o.append(txt(kx + 360, ky + 30, ["dashed:", "a side branch", "⬡ an ant (AI agent)", "■ terminus", "○ interchange", "stacked ∥: parallel"], SUB, 12))
o.append('</svg>')
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "ishikari-metro.svg")
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(o))
