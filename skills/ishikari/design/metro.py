# Build ishikari-metro.svg: the metro map laid out for reading.
# Four rows read left to right like text; cross-row links are short
# transfer spurs with a named destination instead of long lines.
import os
W, H = 1720, 1740
BG = "#0B1120"; TXT = "#F1F5F9"; SUB = "#A8B3C7"
BLUE = "#60A5FA"; GREEN = "#4ADE80"; RED = "#F87171"; GOLD = "#FBBF24"; PURP = "#C4B5FD"; TEAL = "#2DD4BF"; PINK = "#F0ABFC"; GREY = "#94A3B8"
o = []
def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def txt(x, y, lines, fill=TXT, size=14, anchor="start", weight="400", lh=None):
    lh = lh or size + 4
    return "".join(f'<text class="h" x="{x}" y="{y + i * lh}" fill="{fill}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}">{esc(l)}</text>' for i, l in enumerate(lines))
def d(pts): return "M" + " L".join(f"{x},{y}" for x, y in pts)

R1, R2, R3, R4 = 200, 520, 1080, 1540
lines = [  # name, colour, points, width, dash
 ("plan",  BLUE,  [(120,R1),(1440,R1),(1600,R1),(1600,360),(60,360),(60,R2),(200,R2)], 12, ""),
 ("ask",   GOLD,  [(440,R1),(440,90)], 7, ""),
 ("res",   BLUE,  [(440,R1),(440,290)], 7, ""),
 # "build" is the trains' route only (drawn invisible): it follows the cleanup branch through row 3.
 ("build", "none", [(200,R2),(1320,R2),(1600,R2),(1600,820),(60,820),(60,R3),(440,R3),(500,1150),(940,1150),(1000,R3),(1600,R3),(1600,1390),(60,1390),(60,R4),(560,R4)], 12, ""),
 ("g1",    GREEN, [(200,R2),(1320,R2),(1600,R2),(1600,820),(60,820),(60,R3),(440,R3)], 12, ""),
 ("g2",    GREEN, [(1000,R3),(1600,R3),(1600,1390),(60,1390),(60,R4),(560,R4)], 12, ""),
 ("bugin", RED,   [(760,R2),(760,640),(700,700),(620,700)], 8, ""),
 ("clash", RED,   [(1040,R2),(1040,700),(620,700)], 6, "10 6"),
 ("bugout",RED,   [(620,700),(240,700),(200,660),(200,R2)], 8, ""),
 ("r1",    RED,   [(760,R2),(730,580),(230,580),(200,R2)], 5, ""),
 ("logA",  GREY,  [(1320,R2),(1320,646)], 4, "4 6"),
 ("logB",  GREY,  [(300,R4),(300,1630)], 4, "4 6"),
 ("drop",  RED,   [(620,700),(620,770)], 6, ""),
 ("mfail", RED,   [(200,R3),(200,1170)], 6, "10 6"),
 ("tidy",  TEAL,  [(440,R3),(500,1150),(560,1150),(760,1150),(940,1150),(1000,R3)], 9, ""),
 ("tdrop", TEAL,  [(760,1150),(760,1260)], 6, "10 6"),
 ("jfix",  GOLD,  [(1180,R3),(1230,1170),(1470,1170),(1540,R3)], 9, ""),
 ("after", PURP,  [(560,R4),(1160,R4)], 9, ""),
 ("cfix",  PURP,  [(860,R4),(860,1630)], 6, "10 6"),
]
# x, y, name, sub lines, kind, label anchor (dx, dy, anchor)
L_UP = (0, -52, "middle"); L_DN = (0, 34, "middle")
stations = [
 (120,R1,"Task",["you give it, or a","dropped cleanup plan"],"term",L_DN),
 (440,R1,"Investigator Ant",["stays alive, reads the repo once,","gets each answer as a message"],"x",(-22,-60,"end")),
 (440,90,"You",["up to 4 questions a round (/ask-simple);","answering approves the whole run"],"term",(26,-6,"start")),
 (440,290,"Researcher Ants  ∥",["up to 5, web + computer;","the investigator waits for facts"],"end",(24,-4,"start")),
 (700,R1,"investigation_report.md",["written when nothing is unclear;","investigator stopped"],"st",L_DN),
 (960,R1,"Add Requirement Ant",["req add, keeps the :ID:s"],"st",L_DN),
 (1200,R1,"Architect Ant",["writes architecture.md"],"st",L_UP),
 (1440,R1,"Worker plans",["one per worker ant:","title, files, after"],"st",L_DN),
 (200,R2,"Worker Ants  ∥",["max 5, one worktree each,","code + tests + docs","stuck: next fix round"],"x",(0,-74,"middle")),
 (760,R2,"Inspector Ants  ∥",["one per built task: plan + design,","runs tests (reuses worker's if clean)"],"x",(0,-60,"middle")),
 (1040,R2,"Integrator Ant",["merges passing tasks in a scratch","copy, tests once: the combined test"],"x",(0,-60,"middle")),
 (1320,660,"Logbook",["shared ledger, append only:","tasks, bugs, verdict, main move,","your notes. No ant reads it.","~/.ishikari/<repo>-<hash>/logbook.rec"],"log",(26,-4,"start")),
 (620,700,"Detective Ants  ∥",["finds why, writes the next","fix plan, never code"],"x",(-26,34,"end")),
 (620,770,"Dropped",["after 3 tries on a bug or","3 fix rounds; branch kept"],"term",(26,-4,"start")),
 (200,R3,"Merger ant",["straight line or build's trial","merge; Verifier Ant: git cherry"],"x",(0,-58,"middle")),
 (200,1170,"merge failed",["next build round; also when the","verifier finds a task missing"],"term",(26,-4,"start")),
 (440,R3,"Janitor ant",["cleanup plan for this run's mess,","built + checked before main moves"],"x",L_UP),
 (560,1150,"Worker ant",["builds the cleanup on top of the merge"],"st",(0,34,"middle")),
 (760,1150,"Inspector ant",["checks the cleanup: plan + combined test;","fail: one fix round"],"st",(0,-60,"middle")),
 (760,1260,"Dropped cleanup",["branch kept, plan offered as","the next run's Task"],"term",(26,-4,"start")),
 (1180,R3,"Judge ant  ∥",["final verdict: 2+ tasks, one juror ant each","(5 at once); judge decides the score 0-10:","does the code match the plans?"],"x",(0,-90,"middle")),
 (1270,1170,"Worker ant",["closes the judge's gaps"],"st",(0,34,"middle")),
 (1370,1170,"Inspector ant",["checks, runs tests"],"st",(0,-40,"middle")),
 (1470,1170,"Judge ant again",["7+ or still low: main moves;","still low = flagged"],"st",(0,34,"middle")),
 (1000,R3,"cleanup done",["landed or dropped"],"st",(0,-40,"middle")),
 (300,R4,"Finisher ant",["fast-forwards main, cleans","up, appends to the logbook"],"st",L_UP),
 (300,1640,"Logbook",["end of finish: a second batch,","same file as above"],"log",(26,-4,"start")),
 (560,R4,"MAIN",["fast-forward only,","never pushed"],"term",L_DN),
 (860,R4,"checkCommand",["builds and checks the real app"],"st",(0,-52,"middle")),
 (860,1630,"check-fix round",["from the moved main, once"],"term",(26,-4,"start")),
 (1160,R4,"req done",["marks the kept :ID:s"],"term",(0,-52,"middle")),
]
o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="ui-sans-serif,-apple-system,Helvetica,Arial,sans-serif">')
o.append('<title>Ishikari metro map, readable</title>')
o.append('<defs><filter id="g" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>')
o.append(f'<style>.h{{paint-order:stroke;stroke:{BG};stroke-width:5px;stroke-linejoin:round}}.flow{{animation:f 1.2s linear infinite}}@keyframes f{{to{{stroke-dashoffset:-32}}}}</style>')
o.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
o.append(txt(40, 44, ["ISHIKARI METRO"], TXT, 28, weight="800"))
o.append(txt(330, 44, ["Read it like a page: each row left to right, then wrap to the next row."], SUB, 15))
# row bands
for y, label, c in [(R1, "1 ASK  ·  2 PLAN", BLUE), (R2, "3 BUILD  ·  4 CHECK  ·  5 FIX", GREEN), (R3, "6 FINISH: MERGE · CLEANUP · JUDGE", GREEN), (R4, "6 FINISH: MAIN MOVES", GREEN)]:
    o.append(txt(W - 30, y - 100 if y != R1 else 120, [label], c, 13, "end", "800"))
for name, c, pts, w, dash in lines:
    o.append(f'<path id="L-{name}" d="{d(pts)}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"' + (f' stroke-dasharray="{dash}" class="flow"' if dash else '') + '/>')
o.append(txt(1612, 290, ["to row 2"], BLUE, 13, weight="700"))
o.append(txt(480, 474, ["built: the script starts", "its inspector at once"], GREEN, 13, "middle"))
o.append(txt(1612, 680, ["to row 3"], GREEN, 13, weight="700"))
o.append(txt(1360, R3 - 14, ["7+: main moves"], GREEN, 13, "middle", "700"))
o.append(txt(1192, 1140, ["below 7: one fix round"], GOLD, 13, "end", "700"))
o.append(txt(1612, 1240, ["to row 4"], GREEN, 13, weight="700"))
o.append(txt(1330, 590, ["end of build: one batch"], GREY, 13))
o.append(txt(772, 640, ["still open after round 1:", "the script hands it over"], RED, 13))
o.append(txt(480, 604, ["round 1: the inspector's own fix plan"], RED, 13, "middle"))
o.append(txt(1052, 640, ["fail: tasks clash,", "merge, then fix loop"], RED, 13))
o.append(txt(250, 684, ["fix plan back to a worker  ·  max 2 extra build rounds"], RED, 13))
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
kx, ky = 1260, 1480
o.append(f'<rect x="{kx}" y="{ky}" width="430" height="160" rx="12" fill="#0F172A" stroke="#334155"/>')
rows = [(BLUE, "1", "task on the plan line"), (GREEN, "2-6", "five worker tasks to MAIN"), (RED, "7-8", "a bug through the fix loop"),
        (TEAL, "9", "the janitor's cleanup"), (PURP, "10", "after main moves"), (GOLD, "11", "the judge's fix round, below 7")]
for i, (c, n, t) in enumerate(rows):
    y = ky + 24 + i * 20
    o.append(f'<line x1="{kx+16}" y1="{y}" x2="{kx+60}" y2="{y}" stroke="{c}" stroke-width="7" stroke-linecap="round"/>')
    o.append(f'<rect x="{kx+70}" y="{y-9}" width="34" height="18" rx="5" fill="#FDE047" stroke="{c}" stroke-width="2"/><text x="{kx+87}" y="{y+4}" font-size="11" font-weight="800" fill="{BG}" text-anchor="middle">{n}</text>')
    o.append(txt(kx + 114, y + 5, [t], TXT, 13))
o.append(txt(kx + 320, ky + 30, ["dashed:", "a branch or", "a log", "⬡ an ant (AI agent)", "■ terminus", "○ interchange", "stacked ∥: parallel"], SUB, 12))
o.append('</svg>')
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ishikari-metro.svg"), "w") as f:
    f.write("\n".join(o))
