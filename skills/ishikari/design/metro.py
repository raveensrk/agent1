# Build ishikari-metro.svg: Ishikari as a dark, animated subway map.
import os
W, H = 1820, 1010
BG = "#0B1120"; TXT = "#E2E8F0"; SUB = "#94A3B8"
BLUE = "#60A5FA"; GREEN = "#4ADE80"; RED = "#F87171"; GREY = "#94A3B8"; GOLD = "#FBBF24"; TEAL = "#2DD4BF"; PURP = "#A78BFA"
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
 ("ring",  RED,   [(1060,420),(1074,434),(1366,434),(1380,420),(1380,280),(1300,200),(1100,200),(1060,240),(1060,420)], 7, "", 2, 12),
 ("r1",    RED,   [(1380,420),(1366,450),(1074,450),(1060,420)], 4, "", 1, 5),
 ("clash", RED,   [(1540,420),(1540,280),(1460,200),(1300,200)], 5, "8 5", 1, 5),
 ("stuck", RED,   [(1060,420),(1024,384),(1024,186),(1300,186)], 5, "8 5", 1, 5),
 ("mfail", RED,   [(1360,780),(1700,780),(1700,140),(1010,140),(1010,370),(1060,420)], 5, "8 5", 1, 9),
 ("logA",  GREY,  [(1380,450),(1380,560),(1300,640)], 3, "3 6", 0, 0),
 ("logB",  GREY,  [(760,780),(760,700),(1220,700),(1300,640)], 3, "3 6", 0, 0),
 ("drop",  RED,   [(1300,200),(1300,100)], 5, "", 0, 0),
 ("check", PURP,  [(560,780),(240,780)], 7, "", 1, 4),
 ("crit",  GREY,  [(960,780),(960,900),(200,900),(200,140),(250,140),(292,192)], 4, "3 6", 1, 10),
 ("tidy",  TEAL,  [(1160,780),(1160,560),(1080,480),(1060,420)], 6, "", 1, 6),
 ("clean", GREY,  [(1160,780),(1160,960),(60,960),(60,200),(120,200)], 4, "3 6", 1, 12),
]
# (x, y, name lines, sub lines, kind, label side, colour)
stations = [
 (120,200,["Task"],["you give it, or a","dropped cleanup plan"],"term","n",BLUE),
 (300,200,["Investigator Ant"],["stays alive, reads repo once,","gets each answer as a message"],"x","s2",BLUE),
 (300,90,["You"],["answering approves the whole run"],"term","e",GOLD),
 (300,320,["Researcher Ants  ∥"],["up to 5, web + computer","facts, it waits"],"end","e",BLUE),
 (480,200,["investigation_report.md"],["nothing unclear: write it,","investigator stopped"],"st","n",BLUE),
 (640,200,["Add Requirement Ant"],["req add, keeps :ID:s"],"st","s",BLUE),
 (800,200,["Architect Ant"],["architecture.md"],"st","n",BLUE),
 (960,200,["Worker plans"],["one per worker ant:","title, files, after"],"x","n",BLUE),
 (1060,420,["Worker Ants  ∥"],["code, tests, docs","one worktree each, max 5"],"x","sw",GREEN),
 (1380,420,["Inspector Ants  ∥"],["one per built task, plan + design;","runs tests (reuses worker's if clean)"],"x","s",GREEN),
 (1540,420,["Combined test"],["Integrator Ant merges passing","tasks in a scratch copy, tests once"],"x","e",GREEN),
 (1300,640,["Logbook"],["bulletin + bug bounty boards:","for you to read, no ant reads it","~/.ishikari/<repo>-<hash>/boards/"],"term","e",GREY),
 (1300,200,["Detective Ants  ∥"],["why is the bug still open?","writes next fix plan, never code"],"x","w2",RED),
 (1300,100,["Dropped"],["after 3 tries on a bug or","3 fix rounds; branch kept"],"term","e",RED),
 (1360,780,["Merger ant"],["straight line, or build's trial","merge; verifier: git cherry"],"x","s",GREEN),
 (1160,780,["Janitor ant"],["cleanup plan for this run's mess,","built + checked before main moves"],"x","n",GREEN),
 (960,780,["Philosopher ant"],["alongside the cleanup,","1 best critique (--critiques N)"],"x","n",GREEN),
 (760,780,["Finisher ant"],["moves main, cleans up,","sets rows done"],"st","s",GREEN),
 (560,780,["MAIN"],["fast-forward only, never pushed"],"term","n",GREEN),
 (400,780,["checkCommand"],["fails: one check-fix round","from the moved main"],"st","s",PURP),
 (240,780,["req done"],["marks the kept :ID:s"],"term","n",PURP),
 (960,900,["Critiques board"],["bridge to the next run: its","investigator turns them into questions","~/.ishikari/<repo>-<hash>/boards/critiques.md"],"x","s",GREY),
 (1160,960,["Dropped cleanup"],["plan offered next time,","branch kept"],"st","n",GREY),
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
o.append(txt(1030, 176, ["stuck: next fix round"], RED, 11))
o.append(txt(1220, 400, ["round 1 (lowest red track): the inspector's own fix plan"], RED, 11, "middle"))
o.append(txt(1550, 300, ["fail: tasks clash,", "merge, fix loop"], RED, 11))
o.append(txt(1392, 300, ["still open after", "round 1: the script", "hands it over"], RED, 11))
o.append(txt(1708, 700, ["merge failed or", "task missing:", "next build round"], RED, 11))
o.append(txt(1220, 380, ["built: script starts its inspector"], GREEN, 11, "middle"))
o.append(txt(1550, 560, ["pass: they work combined"], GREEN, 11))
o.append(txt(1388, 560, ["end of build"], GREY, 11))
o.append(txt(1000, 694, ["end of finish"], GREY, 11))
o.append(txt(1066, 330, ["fix plan"], RED, 11))
o.append(txt(976, 200 + 160, ["start in parallel"], BLUE, 11))
o.append(txt(308, 140, ["up to 4 questions a round", "/ask-simple"], GOLD, 11))
o.append(txt(212, 600, ["critiques"], GREY, 11))
o.append(txt(72, 600, ["dropped cleanup"], GREY, 11))
o.append(txt(1168, 640, ["cleanup plan", "built now"], TEAL, 11))
def is_ant(nm):
    n = nm.lower()
    return " ant" in n or n in ("combined test", "cleanup worker", "cleanup inspector")
def hexm(x, y, r, fill, stroke, sw):
    pts = " ".join(f"{x + r * dx:.1f},{y + r * dy:.1f}" for dx, dy in [(-1,0),(-0.5,-0.87),(0.5,-0.87),(1,0),(0.5,0.87),(-0.5,0.87)])
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
# stations
for x, y, nm, sub, kind, side, c in stations:
    if is_ant(nm[0]):
        if "∥" in nm[0]:
            o.append(hexm(x + 9, y - 9, 15, BG, TXT, 3) + hexm(x + 4.5, y - 4.5, 15, BG, TXT, 3))
        o.append(hexm(x, y, 15, BG, TXT, 4) + f'<circle cx="{x}" cy="{y}" r="4" fill="{c}"/>')
    elif kind == "x":
        o.append(f'<circle cx="{x}" cy="{y}" r="12" fill="{BG}" stroke="{TXT}" stroke-width="4"/><circle cx="{x}" cy="{y}" r="4" fill="{c}"/>')
    elif kind == "term":
        o.append(f'<rect x="{x-14}" y="{y-14}" width="28" height="28" rx="6" fill="{c}" stroke="{TXT}" stroke-width="3"/>')
    elif kind == "end":
        o.append(f'<line x1="{x-14}" y1="{y}" x2="{x+14}" y2="{y}" stroke="{c}" stroke-width="6" stroke-linecap="round"/>')
    else:
        o.append(f'<circle cx="{x}" cy="{y}" r="8" fill="{TXT}" stroke="{c}" stroke-width="3"/>')
    ax, ay, an = {"n": (x, y - 50, "middle"), "s": (x, y + 32, "middle"), "e": (x + 22, y - 4, "start"),
                  "sw": (x - 20, y + 30, "end"), "se": (x + 20, y + 36, "start"), "s2": (x + 10, y + 40, "start"), "w2": (x - 24, y + 34, "end")}[side]
    o.append(txt(ax, ay, nm, TXT, 14, an, "700"))
    o.append(txt(ax, ay + 17, sub, SUB, 11, an))
# trains: numbered, upright, slow enough to follow
def train(num, c, path, sec, begin="0", pingpong=False):
    kp = ' keyPoints="0;1;0" keyTimes="0;0.5;1" calcMode="linear"' if pingpong else ''
    return (f'<g filter="url(#g)"><rect x="-12" y="-10" width="24" height="20" rx="6" fill="#FDE047" stroke="{c}" stroke-width="3"/>'
            f'<text y="5" font-size="13" font-weight="800" fill="{BG}" text-anchor="middle">{num}</text>'
            f'<animateMotion dur="{sec}s" begin="{begin}s" repeatCount="indefinite"{kp}><mpath href="#L-{path}"/></animateMotion></g>')
trains = []
n = 1
for name, c, pts, w, dash, k, sec in lines:
    for i in range(k):
        trains.append((n, name, c))
        o.append(train(n, c, name, sec * 2, f"{-i*sec*2/k:.2f}"))
        n += 1
for name, c, sec in [("ask", GOLD, 6), ("res", BLUE, 5)]:
    trains.append((n, name, c))
    o.append(train(n, c, name, sec, pingpong=True))
    n += 1
# MAIN pulse
o.append(f'<circle class="pulse" cx="560" cy="780" r="22" fill="none" stroke="{GREEN}" stroke-width="2" opacity="0.6"/>')
# key
kx, ky = 1380, 862
o.append(f'<rect x="{kx}" y="{ky-16}" width="420" height="141" rx="12" fill="#0F172A" stroke="#334155"/>')
o.append(txt(kx + 16, ky + 24, ["LINES"], SUB, 12, weight="800"))
for i, (c, dash, t) in enumerate([(BLUE, "", "Plan line - Ask + Plan workflow"), (GREEN, "", "Build line - build, check, merge, upkeep"),
                                  (RED, "", "Bug loop - inspector, Detective, worker"), (RED, "8 5", "Bug branch - clash, stuck, merge failed"),
                                  (TEAL, "", "Cleanup line - janitor plan to worker ants"), (GREY, "3 6", "Logs and feedback - boards, critiques, cleanup")]):
    y = ky + 44 + i * 16
    o.append(f'<line x1="{kx+16}" y1="{y}" x2="{kx+60}" y2="{y}" stroke="{c}" stroke-width="5"' + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')
    o.append(txt(kx + 70, y + 4, [t], TXT, 11))
o.append(txt(kx + 290, ky + 48, ["⬡  an ant (AI agent)", "o  interchange", "■  terminus", "▬  dead end"], SUB, 11))
o.append(txt(kx + 290, ky + 118, ["PURPLE: after main moves"], PURP, 11))
o.append(txt(kx + 290, ky + 104, ["stacked ∥  many in parallel"], SUB, 11))
what = {"plan": "task riding the plan line", "build": "a worker's task: build to MAIN", "ring": "a bug going round the bug loop", "r1": "round 1: inspector's fix plan to a worker",
        "clash": "tasks clash: into the fix loop", "stuck": "a worker got stuck: to the Detective", "mfail": "merge failed: next build round",
        "check": "checkCommand, then req done", "crit": "critique back to the Investigator", "tidy": "cleanup built by a worker, 1 fix round", "clean": "dropped cleanup plan back to Task",
        "ask": "questions to you and answers back", "res": "researcher fetching facts"}
tx, ty = 740, 60
o.insert(len(o), f'<rect x="{tx-480}" y="{ty+300}" width="470" height="{len(what)*15+34}" rx="12" fill="#0F172A" stroke="#334155"/>')
o.append(txt(tx - 464, ty + 322, ["TRAINS"], SUB, 12, weight="800"))
row = 0
for name in what:
    nums = [str(k) for k, nm, c in trains if nm == name]
    col = next(c for k, nm, c in trains if nm == name)
    label = nums[0] if len(nums) == 1 else f"{nums[0]}-{nums[-1]}"
    o.append(f'<rect x="{tx-464}" y="{ty+332+row*15}" width="34" height="13" rx="4" fill="#FDE047" stroke="{col}" stroke-width="2"/>')
    o.append(f'<text x="{tx-447}" y="{ty+342+row*15}" font-size="10" font-weight="800" fill="{BG}" text-anchor="middle">{label}</text>')
    o.append(txt(tx - 422, ty + 342 + row * 15, [what[name]], TXT, 11))
    row += 1
o.append('</svg>')
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ishikari-metro.svg"), "w") as f:
    f.write("\n".join(o))
