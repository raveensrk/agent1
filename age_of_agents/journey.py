# Build ishikari-journey.svg: every node and edge of ishikari.d2, dark, animated.
import re,math
C=dict(plan="#60A5FA",build="#4ADE80",check="#FBBF24",fix="#FB7185",finish="#A78BFA",always="#94A3B8")
F=dict(plan="#172554",build="#052E16",check="#451A03",fix="#4C0519",finish="#2E1065",always="#1E293B")
BUG="#F87171";OK="#4ADE80";FLOW="#CBD5E1";TXT="#E2E8F0";SUB="#94A3B8"
W,H=1960,1030
o=[]
def esc(s):return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def text(x,y,lines,fill=TXT,size=13,anchor="middle",weight="400",lh=None):
    lh=lh or size+4
    y0=y-(len(lines)-1)*lh/2
    return "".join(f'<text x="{x}" y="{y0+i*lh+size*0.35:.1f}" fill="{fill}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}">{esc(l)}</text>' for i,l in enumerate(lines))
frames={}
def frame(k,x,y,w,h,title,sub,col,dash=False):
    frames[k]=(x,y,w,h,col)
    d=' stroke-dasharray="8 5"' if dash else ''
    o.append(f'<g id="f-{k}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{F[col]}" stroke="{C[col]}" stroke-width="2"{d}/>')
    o.append(text(x+14,y+20,[title],C[col],15,"start","700"))
    if sub:o.append(text(x+w-14,y+20,[sub],SUB,11,"end"))
    o.append('</g>')
nodes={}
ANTS={"inv","res","addreq","arch","workers","inspector","together","detective","merger","finisher","janitor","philo"}
def hexp(x,y,w,h):
    i=min(16,h/3)
    return f"M{x+i},{y} H{x+w-i} L{x+w},{y+h/2} L{x+w-i},{y+h} H{x+i} L{x},{y+h/2} Z"
def node(k,x,y,w,h,lines,col,shape="rect",multi=False):
    nodes[k]=(x,y,w,h)
    s=C[col]
    if k in ANTS:shape="hex"
    if multi:
        for dx,op in [(8,0.6),(4,0.8)]:
            if shape=="hex":o.append(f'<path d="{hexp(x+dx,y-dx,w,h)}" fill="#0F172A" stroke="{s}" stroke-width="1.5" opacity="{op}"/>')
            else:o.append(f'<rect x="{x+dx}" y="{y-dx}" width="{w}" height="{h}" rx="8" fill="#0F172A" stroke="{s}" stroke-width="1.5" opacity="{op}"/>')
    if shape=="hex":o.append(f'<path d="{hexp(x,y,w,h)}" fill="#0F172A" stroke="{s}" stroke-width="2"/>')
    elif shape=="oval":o.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="#0F172A" stroke="{s}" stroke-width="2"/>')
    elif shape=="page":o.append(f'<path d="M{x},{y} H{x+w-16} L{x+w},{y+16} V{y+h} H{x} Z" fill="#0F172A" stroke="{s}" stroke-width="2"/><path d="M{x+w-16},{y} V{y+16} H{x+w}" fill="none" stroke="{s}" stroke-width="1.5"/>')
    elif shape=="cyl":o.append(f'<path d="M{x},{y+10} V{y+h-10} A{w/2},10 0 0 0 {x+w},{y+h-10} V{y+10}" fill="#0F172A" stroke="{s}" stroke-width="2"/><ellipse cx="{x+w/2}" cy="{y+10}" rx="{w/2}" ry="10" fill="#1E293B" stroke="{s}" stroke-width="2"/>')
    else:o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#0F172A" stroke="{s}" stroke-width="2"/>')
    o.append(f'<g>{text(x+w/2,y+h/2+(5 if shape=="cyl" else 0),[lines[0]],TXT,13,"middle","700")}</g>' if len(lines)==1 else text(x+w/2,y+h/2+(5 if shape=="cyl" else 0),lines,TXT,12))
def note(x,y,lines,col=SUB,anchor="start"):
    o.append(f'<g class="lb">{text(x,y,lines,col,11,anchor,lh=14)}</g>')

o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="ui-sans-serif,-apple-system,Helvetica,Arial,sans-serif">')
o.append('<title>Ishikari: full animated flow</title>')
o.append('''<defs><filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="antglow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>''')
for n,c in [("f",FLOW),("b",BUG),("o",OK)]:
    o.append(f'<marker id="m{n}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="{c}"/></marker>')
o.append('</defs><style>.e{fill:none;stroke-width:2}.flowing{stroke-dasharray:10 6;animation:dash 1.2s linear infinite}.dot{stroke-dasharray:3 5;animation:dash 1.6s linear infinite}@keyframes dash{to{stroke-dashoffset:-16}}.lb{paint-order:stroke;stroke:#0B1120;stroke-width:4px;stroke-linejoin:round}</style>')
o.append(f'<rect width="{W}" height="{H}" fill="#0B1120"/>')
o.append(text(40,36,["Ishikari - the full flow, animated"],TXT,24,"start","700"))
o.append(text(40,62,["Asks the user only in step 1. Answering approves the whole run, merge to main included. Never pushes: main moves only by the finisher's fast-forward."],SUB,13,"start"))

frame("ask",160,110,280,560,"1. Ask","one live agent, run by the skill","plan",True)
frame("plan",480,110,260,560,"2. Plan workflow","ishikari-plan.js","plan")
frame("build",780,110,240,560,"3. Build","ishikari-build.js","build")
frame("check",1060,110,260,560,"4. Check","ishikari-build.js","check")
frame("fix",1360,110,240,560,"5. Fix","ishikari-build.js","fix")
frame("finish",1640,110,260,560,"6. Finish","ishikari-finish.js","finish")
frame("boards",600,760,600,180,"Logbook","~/.ishikari/<repo>-<hash>/boards/ - for you, no ant reads it","always")
frame("bridge",1215,760,270,180,"Bridge to next run","","always")
note(1230,925,["~/.ishikari/<repo>-<hash>/boards/critiques.md"])
frame("upkeep",1560,760,340,180,"Upkeep ants","","always")
note(1730,780,["before main moves"])

EDGE_AT=len(o)
# user
o.append(f'<circle cx="80" cy="262" r="16" fill="#FDE68A" stroke="#B45309" stroke-width="2"/><path d="M50,318 Q50,284 80,284 Q110,284 110,318 Z" fill="#FDE68A" stroke="#B45309" stroke-width="2"/>')
o.append(text(80,334,["User (me)"],TXT,13,"middle","700"))
node("task",180,140,240,50,["Task"],"plan","oval")
node("inv",180,230,240,90,["Investigator Ant","stays alive, reads repo once,","gets each answer as a message"],"plan")
node("res",184,378,232,62,["Researcher Ants","up to 5, web + computer"],"plan",multi=True)
node("report",180,500,240,60,["investigation_report.md"],"plan","page")
note(180,612,["blocker set: stop it, show reason, stop.","report written: stop it with TaskStop;","the report is all later ants read."])
node("addreq",500,140,220,80,["Add Requirement Ant","entry kept with its :ID:s,","req add, commit that file"],"plan")
node("arch",500,280,220,70,["Architect Ant","architecture.md"],"plan")
node("plans",504,428,212,72,["Worker plans","one per worker ant","title, files, after"],"plan","page",multi=True)
note(500,592,["Saves testCommand and checkCommand.","Answered critiques removed","from the critiques board.","Never asks to approve plans."])
node("workers",804,268,196,102,["Worker Ants","code, tests and docs,","one worktree each, max 5"],"build",multi=True)
note(800,560,["Approve every awaiting review.","Drop escalated, blocked, error","and every task after a dropped one.","A dropped task's branch is kept."])
node("inspector",1084,268,212,102,["Inspector Ants","one per built task,","checks plan + design,","runs its tests"],"check",multi=True)
node("together",1080,420,220,120,["Combined test","Integrator Ant","merges passing tasks","in a scratch copy, tests once"],"check")
node("detective",1384,268,196,112,["Detective Ants","one per task, in parallel:","finds why a bug is still open","after a failed fix, writes the","next fix plan, never code"],"fix",multi=True)
note(1380,600,["Max 3 tries on a bug,","then the task is dropped."])
node("merger",1660,140,220,90,["Merger ant","straight line in a","scratch copy, tests once"],"finish")
node("finisher",1660,420,220,90,["Finisher ant","moves main forward,","cleans up"],"finish")
note(1660,560,["Bugs or waiting: new build round,","then finish again; max 2 rounds.","checkCommand fails: one check-fix","round from moved main. Then req done."])
node("bulletin",630,800,240,110,["Bulletin board","one row per task"],"build","cyl")
node("bounty",930,800,240,110,["Bug bounty board","one row per bug"],"fix","cyl")
node("critiques",1230,800,240,110,["Critiques board"],"always","cyl")
node("janitor",1580,800,140,110,["Janitor ant","cleanup plan,","built now"],"always")
node("philo",1740,800,140,110,["Philosopher ant","after cleanup,","1 critique (--critiques N)"],"always")

# legend
o.append(f'<rect x="220" y="760" width="340" height="200" rx="14" fill="#1E293B" stroke="{SUB}" stroke-width="2"/>')
o.append(text(236,782,["Legend"],SUB,15,"start","700"))
for i,(c,cls,t) in enumerate([(OK,"flowing","approval"),(BUG,"flowing","bug"),(FLOW,"flowing","normal flow"),(FLOW,"dot","log, watch or comment"),("#FDE047","","glowing dot: one task's trip"),("HEX","","hexagon: an ant (an AI agent)"),("STACK","","stacked: many run in parallel")]):
    y=804+i*20
    if c=="HEX":o.append(f'<path d="{hexp(258,y-7,34,14)}" fill="#0F172A" stroke="{TXT}" stroke-width="1.5"/>')
    elif c=="STACK":o.append(f'<path d="{hexp(264,y-11,34,14)}" fill="none" stroke="{TXT}" stroke-width="1.5" opacity="0.6"/><path d="{hexp(258,y-7,34,14)}" fill="#0F172A" stroke="{TXT}" stroke-width="1.5"/>')
    elif cls:o.append(f'<path class="e {cls}" d="M240,{y} H310" stroke="{c}"/>')
    else:o.append(f'<circle cx="275" cy="{y}" r="7" fill="{c}" filter="url(#antglow)"/>')
    o.append(text(325,y,[t],TXT,12,"start"))

edges=[ # id, d, kind, dashed, both, label, lx, ly
("e1","M300,190 V228","f",0,0,"review",330,210),
("e2","M300,322 V376","f",1,1,"facts, it waits",360,350),
("e3","M420,262 H432 V530 H422","o",0,0,"nothing unclear:|write report",400,460),
("e4","M178,275 H112","f",0,1,"up to 4 questions|a round, /ask-simple",145,212),
("e5","M420,545 H460 V180 H498","o",0,0,"report",462,620),
("e6","M610,220 V278","f",0,0,"requirement",650,250),
("e7","M610,350 V420","f",0,0,"design,|write plans",655,385),
("e8","M720,460 H760 V320 H798","o",0,0,"start in|parallel",760,500),
("e10","M1306,335 H1378","b",0,0,"still open after|round 1: script|hands it over",1340,410),
("e11","M1810,910 V950 H1350 V912","f",1,0,"critique",1580,950),
("e16","M1480,258 V96 H900 V266","f",0,0,"fix plan",1190,96),
("e17","M1002,285 H1082","f",0,0,"built: script starts|its inspector at once",1041,250),
("e22","M1880,205 H1910 V758","f",0,0,"then",1910,560),
("e23","M1620,758 V465 H1658","f",0,0,"then",1620,600),
("e25","M1650,912 V975 H20 V165 H178","f",1,0,"dropped cleanup, offered next time",900,975),
("e26","M1300,912 V960 H140 V300 H178","f",1,0,"turned into questions for the next task",500,960),
("e29","M1600,798 V752 H990 V372","f",0,0,"cleanup plan: built,|checked, 1 fix round",1250,745),
("e30","M1082,322 H1002","b",0,0,"fail, round 1:|inspector's|fix plan",1041,345),
("e31","M1080,480 H1030 V352 H1002","b",0,0,"fail: clash,|merge, fix loop",1030,505),
("e32","M960,266 V104 H1520 V258","b",0,0,"stuck: next fix round",1330,104),
("e33","M1260,540 V690 H1630 V185 H1658","o",0,0,"pass: main session|approves, no review",1630,300),
("e34","M1720,138 V84 H850 V266","b",0,0,"merge failed: next build round",1300,84),
("e40","M1190,670 V720 H750 V798","f",1,0,"end of build: every task and bug, once",960,720),
("e41","M1770,670 V706 H1060 V798","f",1,0,"end of finish: merged tasks \"done\"",1480,706),
("e28","M1190,370 V418","o",0,0,"pass, once every|task is checked",1190,395),
]
col={"f":FLOW,"b":BUG,"o":OK}
E={}
for i,d,k,dash,both,lab,lx,ly in edges:
    E[i]=d
    st="" if not both else f' marker-start="url(#m{k})"'
    o.insert(EDGE_AT,f'<path id="{i}" class="e {"dot" if dash else "flowing"}" d="{d}" stroke="{col[k]}" marker-end="url(#m{k})"{st}/>')
labels=[(lx,ly,lab,col[k]) for i,d,k,dash,both,lab,lx,ly in edges]
for lx,ly,lab,c in labels:
    o.append(f'<g class="lb">{text(lx,ly,lab.split("|"),c,11)}</g>')

# ant path through the run
seq=["e1","e4","e3","e5","e6","e7","e8","e17","e30","e17","e10","e16","e17","e28","e33","e22","e29","e17","e23"]
def pts(d):
    t=re.findall(r'[MHVL]|-?\d+',d);p=[];x=y=0;i=0
    while i<len(t):
        c=t[i]
        if c in"ML":x,y=int(t[i+1]),int(t[i+2]);i+=3
        elif c=="H":x=int(t[i+1]);i+=2
        elif c=="V":y=int(t[i+1]);i+=2
        p.append((x,y))
    return p
P=[];marks=[]
for s in seq:
    q=pts(s and E[s])
    if s=="e4":q=q[::-1]+q  # to user and back
    P+=q;marks.append((s,len(P)))
L=[0]
for a,b in zip(P,P[1:]):L.append(L[-1]+math.dist(a,b))
tot=L[-1];D=48.0;MOVE=0.92
def t_at(idx):return L[idx-1]/tot*D*MOVE
ends={s:t_at(n) for s,n in marks}
path="M"+" L".join(f"{x},{y}" for x,y in P)
# stage windows (seconds) from segment end times
seg_t=[];prev=0
for s,n in marks:seg_t.append((s,prev,t_at(n)));prev=t_at(n)
stage_of={"e1":"ask","e4":"ask","e3":"ask","e5":"plan","e6":"plan","e7":"plan","e8":"build","e17":"check","e27":"check","e15":"boards","e10":"fix","e16":"build","e28":"check","e13":"boards","e20":"finish","e22":"upkeep","e30":"build","e10":"fix","e33":"finish","e29":"build","e23":"finish","e24":"boards"}
cap={"e1":"The task reaches the live Investigator Ant.","e4":"It asks the user up to 4 questions a round; answers come back as messages.","e3":"Nothing unclear: it writes investigation_report.md, then stops.","e5":"Plan workflow: the Add Requirement Ant reads the report.","e6":"Architect Ant writes architecture.md.","e7":"One plan per worker ant.","e8":"Worker Ants start in parallel, one worktree each, max 5.","e17":"Built: the build script starts this task's inspector at once.","e27":"An Inspector Ant starts at once for that task.","e30":"Fail, round 1: a worker builds the inspector's own fix plan.","e33":"They work combined: the main session approves them for the Merger, no review.","e10":"Still open after round 1: the script hands the bug to the Detective Ant.","e16":"Detective's fix plan goes back to a Worker Ant.","e28":"Fix re-inspected: pass, once every task is checked.","e13":"Combined test passes: the bulletin board records it.","e20":"Passing tasks go to the Merger, no review.","e22":"Merged in a straight line: the Janitor plans a cleanup of this run's mess.","e29":"A Worker Ant builds the cleanup now, on top of the merge.","e23":"Cleanup landed; Philosopher critiques; the Finisher moves main. Boards log it all.","e24":"Main fast-forwards; bulletin rows set to \"done\"."}
def win(spans):
    kt=[0];v=[0]
    for a,b in spans:kt+=[a/D,min(b,D-0.01)/D];v+=[1,0]
    return f'<animate attributeName="opacity" dur="{D}s" repeatCount="indefinite" calcMode="discrete" keyTimes="{";".join(f"{k:.4f}" for k in kt)}" values="{";".join(map(str,v))}"/>'
spans={}
for s,a,b in seg_t:spans.setdefault(stage_of[s],[]).append((a,b))
spans["finish"].append((D*MOVE,D))
for k,(x,y,w,h,c) in frames.items():
    o.append(f'<rect x="{x-4}" y="{y-4}" width="{w+8}" height="{h+8}" rx="17" fill="none" stroke="{C[c]}" stroke-width="5" filter="url(#glow)" opacity="0">{win(spans.get(k,[]))}</rect>')
# edge highlight overlays
for s,a,b in seg_t:
    o.append(f'<path d="{E[s]}" fill="none" stroke="#FDE047" stroke-width="5" stroke-linecap="round" opacity="0" filter="url(#antglow)">{win([(a,b)])}</path>')
for s,a,b in seg_t:
    o.append(f'<g opacity="0">{text(W-40,40,[cap[s]],"#FDE047",16,"end","700")}{win([(a,b)])}</g>')
o.append(f'<g opacity="0">{text(W-40,40,["Done. Report once: what landed, dropped tasks, critiques, cleanup plan."],"#FDE047",16,"end","700")}{win([(D*MOVE,D)])}</g>')
o.append(f'<circle r="9" fill="#FDE047" stroke="#0B1120" stroke-width="2" filter="url(#antglow)"><animateMotion dur="{D}s" repeatCount="indefinite" path="{path}" keyPoints="0;1;1" keyTimes="0;{MOVE};1" calcMode="linear"/></circle>')
o.append('</svg>')
open(__import__("os").path.join(__import__("os").path.dirname(__file__),"ishikari-journey.svg"),"w").write("\n".join(o))
