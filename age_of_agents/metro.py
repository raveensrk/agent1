# Build ishikari-metro.svg: Ishikari as a dark, animated subway map.
import os
W, H = 1820, 1010
BG = "#0B1120"; TXT = "#E2E8F0"; SUB = "#94A3B8"
BLUE = "#60A5FA"; GREEN = "#4ADE80"; RED = "#F87171"; GREY = "#94A3B8"; GOLD = "#FBBF24"; PURP = "#A78BFA"
o = []
def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def txt(x, y, lines, fill=TXT, size=13, anchor="start", weight="400"):
    lh = size + 3
    return "".join(f'<text class="h" x="{x}" y="{y + i * lh}" fill="{fill}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}">{esc(l)}</text>' for i, l in enumerate(lines))
def d(pts): return "M" + " L".join(f"{x},{y}" for x, y in pts)

# (name, colour, points, width, dash, trains, seconds)
lines = [
 ("plan",  BLUE,  [(120,200),(960,200),(960,340),(1040,420),(1060,420)], 10, "", 1, 9),
 ("ask",   GOLD,  [(300,90),(300,200)], 6, "", 0, 0),
 ("res",   BLUE,  [(300,200),(300,320)], 6, "", 0, 0),
 ("build", GREEN, [(1060,420),(1540,420),(1540,700),(1460,780),(560,780)], 10, "", 5, 14),
 ("ring",  RED,   [(1060,420),(1074,434),(1366,434),(1380,420),(1380,330),(1450,260),(1640,260),(1580,200),(1100,200),(1060,240),(1060,420)], 7, "", 2, 12),
 ("clash", RED,   [(1540,420),(1640,320),(1640,260)], 5, "8 5", 1, 4),
 ("stuck", RED,   [(1060,420),(1120,500),(1760,500),(1760,300),(1700,260),(1640,260)], 5, "8 5", 1, 8),
 ("mfail", RED,   [(1360,780),(1700,780),(1700,560),(1700,320),(1640,260)], 5, "8 5", 1, 7),
 ("drop",  RED,   [(1300,200),(1300,100)], 5, "", 0, 0),
 ("check", PURP,  [(560,780),(240,780)], 7, "", 1, 4),
 ("crit",  GREY,  [(960,780),(960,900),(200,900),(200,140),(250,140),(292,192)], 4, "3 6", 1, 10),
 ("clean", GREY,  [(1160,780),(1160,960),(60,960),(60,200),(120,200)], 4, "3 6", 1, 12),
 ("board", GREY,  [(1220,420),(1300,560),(1540,620)], 3, "3 6", 0, 0),
 ("board2",GREY,  [(1060,420),(1060,620),(1540,620)], 3, "3 6", 0, 0),
 ("board3",GREY,  [(760,780),(760,700),(1400,700),(1540,620)], 3, "3 6", 0, 0),
]
# (x, y, name lines, sub lines, kind, label side, colour)
stations = [
 (120,200,["Task"],["you give it, or the","last cleanup plan"],"term","n",BLUE),
 (300,200,["Investigator Ant"],["stays alive, reads repo once,","gets each answer as a message"],"x","s2",BLUE),
 (300,90,["You"],["answering approves the whole run"],"term","e",GOLD),
 (300,320,["Researcher Ants"],["up to 5, web + computer","facts, it waits"],"end","e",BLUE),
 (480,200,["investigation_report.md"],["nothing unclear: write it,","investigator stopped"],"st","n",BLUE),
 (640,200,["Add Requirement Ant"],["req add, keeps :ID:s"],"st","s",BLUE),
 (800,200,["Architect Ant"],["architecture.md"],"st","n",BLUE),
 (960,200,["Worker plans"],["one per worker ant:","title, files, after"],"x","n",BLUE),
 (1060,420,["Worker Ants"],["code, tests, docs","one worktree each, max 5"],"x","sw",GREEN),
 (1220,420,["Anti-monitor"],["the build script"],"x","s",GREEN),
 (1380,420,["Inspector Ants"],["one per built task,","checks plan + design, runs tests"],"x","s",GREEN),
 (1540,420,["Combined test"],["Integrator Ant merges passing","tasks in a scratch copy, tests once"],"x","e",GREEN),
 (1540,620,["Bulletin board"],["one row per task"],"x","e",GREEN),
 (1640,260,["Bug bounty board"],["one row per bug"],"x","se",RED),
 (1300,200,["Detective Ant"],["why is the bug still open?","writes next fix plan, never code"],"x","s",RED),
 (1300,100,["Dropped"],["after 3 tries on a bug","branch kept, not deleted"],"term","e",RED),
 (1360,780,["Merger ant"],["straight line in a scratch copy,","tests once, no review"],"x","s",GREEN),
 (1160,780,["Janitor ant"],["writes a cleanup plan"],"x","n",GREEN),
 (960,780,["Philosopher ant"],["5 best critiques of the merge"],"x","n",GREEN),
 (760,780,["Finisher ant"],["moves main, cleans up,","sets rows done"],"st","s",GREEN),
 (560,780,["MAIN"],["fast-forward only, never pushed"],"term","n",GREEN),
 (400,780,["checkCommand"],["fails: one check-fix round","from the moved main"],"st","s",PURP),
 (240,780,["req done"],["marks the kept :ID:s"],"term","n",PURP),
 (960,900,["Critiques board"],["turned into questions","for the next task"],"x","s",GREY),
 (1160,960,["Cleanup plan"],["offered next time"],"st","n",GREY),
]
o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="ui-sans-serif,-apple-system,Helvetica,Arial,sans-serif">')
o.append('<title>Ishikari metro map</title>')
o.append('<defs><filter id="g" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>')
o.append(f'<style>.h{{paint-order:stroke;stroke:{BG};stroke-width:4px;stroke-linejoin:round}}.flow{{animation:f 1s linear infinite}}@keyframes f{{to{{stroke-dashoffset:-18}}}}.pulse{{animation:p 2s ease-in-out infinite}}@keyframes p{{50%{{r:13px}}}}</style>')
o.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
# faint city grid
for x in range(0, W, 40): o.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{H}" stroke="#111A2E" stroke-width="1"/>')
for y in range(0, H, 40): o.append(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="#111A2E" stroke-width="1"/>')
o.append(txt(40, 44, ["ISHIKARI METRO"], TXT, 26, weight="800"))
o.append(txt(40, 66, ["One task rides from Task to MAIN. Questions only at the first stop; after that it runs on its own."], SUB, 13))
# lines
for name, c, pts, w, dash, n, sec in lines:
    o.append(f'<path id="L-{name}" d="{d(pts)}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"' + (f' stroke-dasharray="{dash}" class="flow"' if dash else '') + ' opacity="0.95"/>')
# ask line is two-way: double rail
o.append(f'<path d="M300,96 V194" stroke="{BG}" stroke-width="2"/>')
# zones
o.append(f'<path d="M1200,140 H1820" stroke="none"/>')
o.append(txt(1100, 300, ["BUG LOOP"], RED, 12, weight="800"))
o.append(txt(1100, 316, ["max 2 extra build rounds"], RED, 11))
o.append(txt(1124, 494, ["stuck"], RED, 11))
o.append(txt(1600, 360, ["fail: tasks clash"], RED, 11))
o.append(txt(1408, 324, ["fail: bugs +", "first fix plan"], RED, 11))
o.append(txt(1708, 700, ["merge failed"], RED, 11))
o.append(txt(1550, 560, ["pass: they work combined"], GREEN, 11))
o.append(txt(1068, 236, ["fix plan"], RED, 11))
o.append(txt(1320, 556, ["board tool writes once per stage"], GREY, 11))
o.append(txt(1066, 600, ["built"], GREY, 11))
o.append(txt(1000, 694, ["main moved, set \"done\""], GREY, 11))
o.append(txt(976, 200 + 160, ["start in parallel"], BLUE, 11))
o.append(txt(308, 140, ["up to 4 questions a round", "/ask-simple"], GOLD, 11))
o.append(txt(212, 600, ["critiques"], GREY, 11))
o.append(txt(72, 600, ["cleanup"], GREY, 11))
# stations
for x, y, nm, sub, kind, side, c in stations:
    if kind == "x":
        o.append(f'<circle cx="{x}" cy="{y}" r="12" fill="{BG}" stroke="{TXT}" stroke-width="4"/><circle cx="{x}" cy="{y}" r="4" fill="{c}"/>')
    elif kind == "term":
        o.append(f'<rect x="{x-14}" y="{y-14}" width="28" height="28" rx="6" fill="{c}" stroke="{TXT}" stroke-width="3"/>')
    elif kind == "end":
        o.append(f'<line x1="{x-14}" y1="{y}" x2="{x+14}" y2="{y}" stroke="{c}" stroke-width="6" stroke-linecap="round"/>')
    else:
        o.append(f'<circle cx="{x}" cy="{y}" r="8" fill="{TXT}" stroke="{c}" stroke-width="3"/>')
    ax, ay, an = {"n": (x, y - 50, "middle"), "s": (x, y + 32, "middle"), "e": (x + 22, y - 4, "start"),
                  "sw": (x - 20, y + 30, "end"), "se": (x + 20, y + 36, "start"), "s2": (x + 10, y + 40, "start")}[side]
    o.append(txt(ax, ay, nm, TXT, 14, an, "700"))
    o.append(txt(ax, ay + 17, sub, SUB, 11, an))
# trains
for name, c, pts, w, dash, n, sec in lines:
    for i in range(n):
        o.append(f'<g filter="url(#g)"><rect x="-9" y="-5" width="18" height="10" rx="4" fill="#FDE047" stroke="{c}" stroke-width="2"><animateMotion dur="{sec}s" begin="{-i*sec/max(n,1):.2f}s" repeatCount="indefinite" rotate="auto"><mpath href="#L-{name}"/></animateMotion></rect></g>')
# ask: gold shuttle both ways
o.append(f'<circle r="6" fill="#FDE047" filter="url(#g)"><animateMotion dur="3s" repeatCount="indefinite" keyPoints="0;1;0" keyTimes="0;0.5;1" calcMode="linear"><mpath href="#L-ask"/></animateMotion></circle>')
o.append(f'<circle r="6" fill="#93C5FD" filter="url(#g)"><animateMotion dur="2.4s" repeatCount="indefinite" keyPoints="0;1;0" keyTimes="0;0.5;1" calcMode="linear"><mpath href="#L-res"/></animateMotion></circle>')
# MAIN pulse
o.append(f'<circle class="pulse" cx="560" cy="780" r="22" fill="none" stroke="{GREEN}" stroke-width="2" opacity="0.6"/>')
# key
kx, ky = 1380, 870
o.append(f'<rect x="{kx}" y="{ky}" width="420" height="125" rx="12" fill="#0F172A" stroke="#334155"/>')
o.append(txt(kx + 16, ky + 24, ["LINES"], SUB, 12, weight="800"))
for i, (c, dash, t) in enumerate([(BLUE, "", "Plan line - Ask + Plan workflow"), (GREEN, "", "Build line - build, check, merge, upkeep"),
                                  (RED, "", "Bug loop - bounty, Detective, fix"), (RED, "8 5", "Bug branch - clash, stuck, merge failed"),
                                  (GREY, "3 6", "Feedback - board writes, critiques, cleanup")]):
    y = ky + 44 + i * 16
    o.append(f'<line x1="{kx+16}" y1="{y}" x2="{kx+60}" y2="{y}" stroke="{c}" stroke-width="5"' + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')
    o.append(txt(kx + 70, y + 4, [t], TXT, 11))
o.append(txt(kx + 290, ky + 48, ["o  interchange", "■  terminus", "▬  dead end"], SUB, 11))
o.append(txt(kx + 290, ky + 100, ["PURPLE: after main moves"], PURP, 11))
o.append('</svg>')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ishikari-metro.svg"), "w").write("\n".join(o))
