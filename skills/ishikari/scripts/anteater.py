#!/usr/bin/env python3
"""Ant Eater: what each ant of an Ishikari run cost, on a local web page.

It reads Claude Code's own transcripts, adds up the tokens of every ant, and
shows them per stage, station, ant and plan task, live while a run goes. It is
deterministic: no model is called, the same files give the same numbers, and
what it cannot read is counted and shown, never guessed.

  anteater.py [serve] [--port <n>] [--no-open]
      Serve the page on 127.0.0.1 until Ctrl-C and print its URL. It opens on
      the newest run of any repo under ~/.ishikari; a picker lists the rest.
      The port is 4268, or the next free one of the 20 after it.

  anteater.py snapshot <state> <run> [--dry-run]
      Write the run's token counts to <state>/plans/<run>/tokens.json and
      exit. `ishikari.py save` runs this after every save. The file holds
      counts per ant and model, never dollars and no write time, so the same
      transcripts give a byte-identical file. A saved file is never replaced
      by one with fewer ants (transcripts that Claude Code has cleaned away).
      --dry-run prints the file and writes nothing.

  anteater.py runs
      List every run, newest first: repo, run id, ants and cost.

  anteater.py -h | --help      the commands, one line each
  anteater.py help             this text

How a run is counted
  Stage     main, investigate, plan, build, finish, retro.
  Station   the kind of ant: the label's part before the first colon.
  Ant       one transcript. A message is counted once per message id.
  Task      the plan task in a worker, detective or juror label.
  Workflow ants belong to the run named in their workflow record
  (<session>/workflows/<wf>.json), whose workflowName gives the stage. An
  Agent-tool ant the main session started inside the run's window is the
  investigator; an ant whose parent is the investigator is a researcher. The
  main session counts from the run's setup to its last save; a message in two
  runs of one session belongs to the run set up last before it. A live run
  also shows the tail after its last save.

Cost and percent
  Cost is US dollars at API list price, from assets/prices.json, worked out
  when the page is drawn. It is not a subscription bill. The percent column
  is the share of one 5-hour limit window: the status line logs Claude Code's
  own "percent used" and the session cost to limit.log, and Ant Eater fits
  dollars per percent from it. five_hour_usd in prices.json overrides the fit.

Files read
  ~/.ishikari/<repo>-<hash>/plans/<run>/run.json, tokens.json, <stage>-<n>.json
  ~/.claude/projects/<project>/<session>.jsonl and <session>/subagents, workflows
      ($CLAUDE_CONFIG_DIR replaces ~/.claude)
  ~/.ishikari/anteater/limit.log    time, session, cost, percent, reset time
  assets/prices.json, assets/anteater.html
Files written
  <state>/plans/<run>/tokens.json   by snapshot only
Exit codes
  0 done, also when a snapshot has warnings; 1 a refusal or failure.
"""

import datetime
import glob
import http.server
import json
import mmap
import os
import re
import statistics
import sys
import threading
import time
import urllib.parse
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")
PRICES = os.path.join(ASSETS, "prices.json")
PAGE = os.path.join(ASSETS, "anteater.html")
PORT = 4268
PORT_TRIES = 20
LIVE_SECONDS = 120  # a transcript written this recently is live
LIMIT_MIN_POINTS = 5  # percent points logged before the 5-hour fit is shown
VERSION = 1
SHORT_HELP = """usage: anteater.py [<command>]
Ant Eater: what each ant of an Ishikari run cost, on a local web page. No AI.
  [serve] [--port <n>] [--no-open]        serve the page on 127.0.0.1 (the default)
  snapshot <state> <run> [--dry-run]      write the run's tokens.json and exit
  runs                                    list every run with its cost
  help                                    the long help
example: anteater.py --port 4300
"""
STAGES = ("main", "investigate", "plan", "build", "finish", "retro", "unknown")
# Label kind -> station. test_label_guard fails when a kind in the four
# workflow scripts is missing here.
STATIONS = {
    "investigator-ant": "investigator", "researcher-ant": "researcher",
    "worker-ant": "worker", "detective-ant": "detective", "integrator-ant": "integrator",
    "merger-ant": "merger", "docs-ant": "docs", "janitor-ant": "janitor",
    "juror-ant": "juror", "judge-ant": "judge", "finisher-ant": "finisher",
    "retrospective-ant": "retrospective", "logbook-clerk": "logbook clerk",
}
# Which part of the label names the plan task, counted from 0.
TASK_PART = {"worker-ant": 1, "detective-ant": 1, "juror-ant": 2}
# The stage a kind can only run in, for a workflow with no record yet.
KIND_STAGE = {
    "integrator-ant": "build", "merger-ant": "finish", "docs-ant": "finish", "janitor-ant": "finish",
    "juror-ant": "finish", "judge-ant": "finish", "finisher-ant": "finish", "retrospective-ant": "retro",
}
KINDS = ("in", "out", "cw5m", "cw1h", "cr")
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
STATE_NAME = re.compile(r"[A-Za-z0-9._+-]+")
RUN_TIME = re.compile(r"(\d{8})-(\d{6})")
STAGE_FILE = re.compile(r"([a-z][a-z-]{0,20})-(\d+)\.json")
WF_STAGE = re.compile(r"ishikari-(plan|build|finish|retro)")


def die(msg):
    print(f"anteater: {msg}", file=sys.stderr)
    sys.exit(1)


def home():
    return os.path.expanduser("~")


def ishikari_root():
    return os.path.join(home(), ".ishikari")


def projects_root():
    return os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(home(), ".claude"), "projects")


def limit_log():
    return os.path.join(ishikari_root(), "anteater", "limit.log")


def epoch(stamp):
    """An ISO time stamp as seconds since 1970, or None."""
    if not isinstance(stamp, str):
        return None
    try:
        return datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def iso(seconds):
    if seconds is None:
        return None
    return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ---- transcripts ----------------------------------------------------------

_parsed = {}  # path -> (size, mtime_ns, parsed): a transcript is read again only when it grew
_lock = threading.Lock()


def parse_transcript(path):
    """One transcript as its counted messages.

    Returns {msgs: [(time, model, in, out, cw5m, cw1h, cr)], first, last, bad:
    [line numbers]} with one entry per message id, the last line of an id
    winning, and <synthetic> messages left out."""
    try:
        st = os.stat(path)
    except OSError:
        return {"msgs": [], "first": None, "last": None, "bad": [], "mtime": None}
    key = (st.st_size, st.st_mtime_ns)
    with _lock:
        hit = _parsed.get(path)
        if hit and hit[0] == key:
            return hit[1]
    by_id, order, bad, first, last = {}, [], [], None, None
    with open(path, "rb") as f:
        data = f.read()
    lines = data.split(b"\n")
    whole = data.endswith(b"\n")
    for n, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
            assert isinstance(row, dict)
        except (ValueError, AssertionError):
            if n == len(lines) and not whole:
                continue  # the line still being written
            bad.append(n)
            continue
        at = epoch(row.get("timestamp"))
        if at is not None:
            first = at if first is None else min(first, at)
            last = at if last is None else max(last, at)
        if row.get("type") != "assistant":
            continue
        msg = row.get("message")
        if not isinstance(msg, dict) or msg.get("model") == "<synthetic>":
            continue
        use, mid, model = msg.get("usage"), msg.get("id"), msg.get("model")
        if not isinstance(use, dict) or not isinstance(mid, str) or not isinstance(model, str) or at is None:
            bad.append(n)
            continue
        counts = usage_counts(use)
        if counts is None:
            bad.append(n)
            continue
        if mid not in by_id:
            order.append(mid)
        by_id[mid] = (at, model) + counts
    out = {"msgs": [by_id[m] for m in order], "first": first, "last": last, "bad": bad, "mtime": st.st_mtime}
    with _lock:
        _parsed[path] = (key, out)
    return out


def usage_counts(use):
    """(in, out, cw5m, cw1h, cr) from one usage object, or None when a count is not a whole number."""
    def num(v):
        return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None

    got = [num(use.get(k, 0)) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")]
    if None in got:
        return None
    tin, tout, cw, cr = got
    split = use.get("cache_creation")
    cw5, cw1 = cw, 0
    if isinstance(split, dict):
        a, b = num(split.get("ephemeral_5m_input_tokens", 0)), num(split.get("ephemeral_1h_input_tokens", 0))
        if a is None or b is None:
            return None
        cw1 = b
        cw5 = max(cw - b, a)
    return (tin, tout, cw5, cw1, cr)


def tally(msgs):
    """Counted messages as {usage: {model: [5 counts]}, turns, peakContext, start, end}."""
    usage, peak = {}, 0
    for at, model, tin, tout, cw5, cw1, cr in msgs:
        row = usage.setdefault(model, [0, 0, 0, 0, 0])
        for i, v in enumerate((tin, tout, cw5, cw1, cr)):
            row[i] += v
        peak = max(peak, tin + cw5 + cw1 + cr)
    return {
        "usage": {m: usage[m] for m in sorted(usage)},
        "turns": len(msgs),
        "peakContext": peak,
        "start": iso(min((m[0] for m in msgs), default=None)),
        "end": iso(max((m[0] for m in msgs), default=None)),
    }


# ---- runs -----------------------------------------------------------------


def state_dirs():
    root = ishikari_root()
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return []
    return [os.path.join(root, n) for n in names if os.path.isdir(os.path.join(root, n, "plans"))]


def repo_name(state):
    name = os.path.basename(state.rstrip("/"))
    return re.sub(r"-[0-9a-f]{8}$", "", name)


def run_info(state, run):
    """What is known of a run: setup time, last save time, sessions, stages saved."""
    folder = os.path.join(state, "plans", run)
    info = read_json(os.path.join(folder, "run.json"))
    info = info if isinstance(info, dict) else {}
    saved = read_json(os.path.join(folder, "tokens.json"))
    saved = saved if isinstance(saved, dict) and isinstance(saved.get("ants"), list) else None
    setup = epoch(info.get("setupAt"))
    if setup is None:  # a run from before run.json: the id holds its local start time
        m = RUN_TIME.match(run)
        if m:
            try:
                setup = datetime.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").timestamp()
            except ValueError:
                setup = None
    stages, newest = set(), None
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        names = []
    for name in names:
        m = STAGE_FILE.fullmatch(name)
        if m:
            stages.add(m.group(1))
            try:
                t = os.path.getmtime(os.path.join(folder, name))
                newest = t if newest is None else max(newest, t)
            except OSError:
                pass
    last = epoch(info.get("lastSaveAt"))
    if last is None and "setupAt" not in info:
        last = newest
    sessions = [s for s in info.get("sessions", []) if isinstance(s, str)] if isinstance(info.get("sessions"), list) else []
    if not sessions and saved:
        sessions = [s for s in saved.get("sessions", []) if isinstance(s, str)]
    return {"state": state, "run": run, "repo": repo_name(state), "setup": setup, "lastSave": last,
            "sessions": sessions, "stages": sorted(stages), "saved": saved, "folder": folder}


def all_runs():
    """Every run under ~/.ishikari, newest first."""
    out = []
    for state in state_dirs():
        plans = os.path.join(state, "plans")
        for run in sorted(os.listdir(plans)):
            if RUN_ID.fullmatch(run) and os.path.isdir(os.path.join(plans, run)):
                out.append(run_info(state, run))
    out.sort(key=lambda r: (-(r["setup"] or 0), r["state"], r["run"]))
    return out


def session_file(sid):
    hits = sorted(glob.glob(os.path.join(glob.escape(projects_root()), "*", glob.escape(sid) + ".jsonl")))
    return hits[0] if hits else None


def scan_sessions(info):
    """Sessions whose main transcript holds the run's env ("run": "<id>", as
    setup prints it and every workflow call passes it): the fallback
    for a run with no recorded session. A session that only mentions the run id
    is not one of its sessions. Only transcripts written after the run began."""
    needle, found = re.compile(rb'\\?"run\\?":\s*\\?"' + re.escape(info["run"].encode()) + rb'\\?"'), []
    for path in sorted(glob.glob(os.path.join(glob.escape(projects_root()), "*", "*.jsonl"))):
        try:
            st = os.stat(path)
            if st.st_size == 0 or (info["setup"] is not None and st.st_mtime < info["setup"] - 1):
                continue
            with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                if needle.search(mm):
                    found.append(os.path.basename(path)[:-len(".jsonl")])
        except (OSError, ValueError):
            continue
    return found


# ---- collecting a run -----------------------------------------------------


def label_parts(label):
    """(kind, station, task) of a workflow ant label."""
    parts = label.split(":")
    kind = parts[0]
    k = TASK_PART.get(kind)
    task = parts[k] if k is not None and len(parts) > k else ""
    return kind, STATIONS.get(kind), task


def owner(session_runs, at):
    """The run of a session a moment belongs to: the newest setup at or before it."""
    best = None
    for r in session_runs:
        if r["setup"] is not None and r["setup"] <= at and (best is None or r["setup"] > best["setup"]):
            best = r
    return best


def collect(info, runs, live=False):
    """The ants of a run, from the transcripts. Returns (ants, sessions, warnings)."""
    warnings, ants = [], []
    sessions = [s for s in info["sessions"] if session_file(s)]
    if not sessions:
        sessions = scan_sessions(info)
    end = None if live else info["lastSave"]

    for sid in sessions:
        main = session_file(sid)
        if not main:
            continue
        base = main[:-len(".jsonl")]
        mates = [r for r in runs if sid in r["sessions"] and (r["state"], r["run"]) != (info["state"], info["run"])] + [info]

        def mine(at, bounded=True):
            if at is None or info["setup"] is None:
                return False
            if bounded and not live and (end is None or at > end):
                return False
            own = owner(mates, at)
            return own is not None and (own["state"], own["run"]) == (info["state"], info["run"])

        def note_bad(path, parsed):
            for n in parsed["bad"]:
                warnings.append(f"unreadable line: {path}:{n}")

        # The main session, cut to the run's window.
        parsed = parse_transcript(main)
        note_bad(main, parsed)
        msgs = [m for m in parsed["msgs"] if mine(m[0])]
        if msgs:
            ants.append({"id": f"main:{sid}", "session": sid, "stage": "main", "station": "main session", "task": "",
                         "label": "main session", "model": "", "effort": "", "transcript": main,
                         "mtime": parsed["mtime"], **tally(msgs)})

        # Workflow ants: the workflow record names the run and the stage.
        by_id = {}
        for wf_dir in sorted(glob.glob(os.path.join(glob.escape(base), "subagents", "workflows", "*"))):
            wf = os.path.basename(wf_dir)
            record = read_json(os.path.join(base, "workflows", wf + ".json"))
            record = record if isinstance(record, dict) else None
            wf_run, stage = None, None
            if record:
                args = record.get("args")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = None
                env = args.get("env") if isinstance(args, dict) else None
                wf_run = env.get("run") if isinstance(env, dict) else None
                m = WF_STAGE.search(str(record.get("workflowName") or ""))
                stage = m.group(1) if m else None
            if stage is None:
                for script in glob.glob(os.path.join(glob.escape(base), "workflows", "scripts", f"*{glob.escape(wf)}*")):
                    m = WF_STAGE.search(os.path.basename(script))
                    stage = m.group(1) if m else stage
            found = []
            for path in sorted(glob.glob(os.path.join(glob.escape(wf_dir), "agent-*.jsonl"))):
                meta = read_json(path[:-len(".jsonl")] + ".meta.json")
                meta = meta if isinstance(meta, dict) else {}
                parsed = parse_transcript(path)
                found.append((path, meta, parsed))
            if isinstance(wf_run, str):
                if wf_run != info["run"]:
                    continue
            elif not any(mine(p["first"]) for _, _, p in found):
                continue  # no record yet: the workflow is placed by when its ants began
            if stage is None:
                kinds = {KIND_STAGE.get(str(meta.get("description") or "").split(":")[0]) for _, meta, _ in found} - {None}
                stage = kinds.pop() if len(kinds) == 1 else "unknown"
                if stage == "unknown":
                    warnings.append(f"unknown stage: workflow {wf} has no record and no ant that names its stage")
            for path, meta, parsed in found:
                note_bad(path, parsed)
                aid = os.path.basename(path)[len("agent-"):-len(".jsonl")]
                label = str(meta.get("description") or "")
                kind, station, task = label_parts(label)
                if station is None:
                    station = "unknown"
                    warnings.append(f"unknown label: {label or '(none)'} in {path}")
                ant = {"id": aid, "session": sid, "stage": stage, "station": station, "task": task,
                       "label": label, "model": str(meta.get("model") or ""), "effort": str(meta.get("effort") or ""),
                       "transcript": path, "mtime": parsed["mtime"], **tally(parsed["msgs"])}
                by_id[aid] = ant
                ants.append(ant)

        # Agent-tool ants: sorted by who started them, never by their name.
        loose = {}
        for path in sorted(glob.glob(os.path.join(glob.escape(base), "subagents", "agent-*.jsonl"))):
            meta = read_json(path[:-len(".jsonl")] + ".meta.json")
            loose[os.path.basename(path)[len("agent-"):-len(".jsonl")]] = (path, meta if isinstance(meta, dict) else {})
        placed = {}

        def place(aid, seen=()):
            """(stage, station, task, root) of an Agent-tool ant, or None when it is not this run's."""
            if aid in placed:
                return placed[aid]
            path, meta = loose[aid]
            parent = meta.get("parentAgentId")
            got = None
            if isinstance(parent, str) and parent:
                if parent in by_id:
                    p = by_id[parent]
                    got = (p["stage"], p["station"], p["task"], "helper")
                elif parent in loose and parent not in seen:
                    up = place(parent, seen + (aid,))
                    if up:
                        got = (up[0], "researcher" if up[3] == "investigator" else up[1], up[2], up[3])
            elif mine(parse_transcript(path)["first"]):
                got = ("investigate", "investigator", "", "investigator")
            placed[aid] = got
            return got

        for aid in sorted(loose):
            got = place(aid)
            if not got:
                continue
            path, meta = loose[aid]
            parsed = parse_transcript(path)
            note_bad(path, parsed)
            ants.append({"id": aid, "session": sid, "stage": got[0], "station": got[1], "task": got[2],
                         "label": str(meta.get("description") or ""), "model": str(meta.get("model") or ""),
                         "effort": str(meta.get("effort") or ""), "transcript": path, "mtime": parsed["mtime"],
                         **tally(parsed["msgs"])})

    ants.sort(key=lambda a: (STAGES.index(a["stage"]) if a["stage"] in STAGES else len(STAGES), a["start"] or "", a["id"]))
    tries = {}
    for a in ants:
        k = (a["stage"], a["station"], a["task"])
        tries[k] = tries.get(k, 0) + 1
        a["try"] = tries[k]
        if a["usage"]:  # the model that did the work, not the alias the ant was asked for
            a["model"] = max(sorted(a["usage"]), key=lambda m: sum(a["usage"][m]))
    return ants, sessions, sorted(set(warnings))


def snapshot_doc(info, ants, sessions, warnings):
    """The tokens.json of a run: counts only, no dollars, no write time."""
    keep = ("id", "session", "stage", "station", "task", "try", "label", "model", "effort",
            "start", "end", "turns", "peakContext", "usage", "transcript")
    return {
        "version": VERSION,
        "run": info["run"],
        "repo": info["repo"],
        "setupAt": iso(info["setup"]),
        "lastSaveAt": iso(info["lastSave"]),
        "sessions": sessions,
        "fastPath": not any(a["stage"] in ("plan", "build", "finish", "retro") for a in ants),
        "ants": [{k: a[k] for k in keep} for a in ants],
        "warnings": warnings,
    }


def snapshot(state, run, dry=False):
    if not RUN_ID.fullmatch(run):
        die(f"bad run id {run!r}")
    state = os.path.abspath(state)
    if not os.path.isdir(os.path.join(state, "plans", run)):
        die(f"no run {run} in {state}/plans; `anteater.py runs` lists them")
    info = run_info(state, run)
    ants, sessions, warnings = collect(info, all_runs())
    text = json.dumps(snapshot_doc(info, ants, sessions, warnings), indent=2, sort_keys=True) + "\n"
    path = os.path.join(info["folder"], "tokens.json")
    if dry:
        print(text, end="")
        return
    old = info["saved"]
    if old and len(old["ants"]) > len(ants):
        print(f"anteater: kept {path}: it holds {len(old['ants'])} ants and the transcripts now give {len(ants)}")
        return
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    print(f"{path}: {len(ants)} ants, {len(warnings)} warnings")


# ---- prices, the 5-hour limit, the view ----------------------------------


def load_prices():
    data = read_json(PRICES)
    if not isinstance(data, dict) or not isinstance(data.get("models"), dict):
        return {"models": {}, "five_hour_usd": None, "flag_ratio": 2, "flag_runs": 3, "broken": True}
    return data


def price_of(prices, model):
    models = prices["models"]
    if model in models:
        return models[model]
    best = None
    for key in models:
        if (model.startswith(key + "-20") or model.startswith(key + "[")) and (best is None or len(key) > len(best)):
            best = key
    return models[best] if best else None


def cost_of(prices, usage):
    """(dollars or None, [dollars per kind] or None, models with no price)."""
    total, split, missing = 0.0, [0.0] * 5, []
    for model in sorted(usage):
        p = price_of(prices, model)
        if not isinstance(p, dict) or any(not isinstance(p.get(k), (int, float)) for k in KINDS):
            if sum(usage[model]):
                missing.append(model)
            continue
        for i, k in enumerate(KINDS):
            c = usage[model][i] * p[k] / 1e6
            split[i] += c
            total += c
    return (None, None, missing) if missing else (total, split, [])


def limit_fit(prices):
    """Dollars per percent of the 5-hour limit, with what it rests on."""
    fixed = prices.get("five_hour_usd")
    if isinstance(fixed, (int, float)) and not isinstance(fixed, bool) and fixed > 0:
        return {"usdPerPercent": fixed / 100, "basis": f"five_hour_usd = {fixed:g} in prices.json"}
    rows = []
    try:
        with open(limit_log(), encoding="utf-8") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                try:
                    rows.append((float(p[0]), p[1], float(p[2]), float(p[3]), p[4]))
                except (IndexError, ValueError):
                    continue
    except OSError:
        return {"usdPerPercent": None, "basis": "no limit.log yet: the status line has logged no 5-hour sample"}
    rows.sort(key=lambda r: r[0])
    points, dollars, windows = 0.0, 0.0, set()
    last_pct, last_cost = {}, {}  # window -> percent; (window, session) -> cost
    for _, sid, cost, pct, window in rows:
        if window in last_pct and pct > last_pct[window]:
            points += pct - last_pct[window]
            windows.add(window)
        last_pct[window] = pct
        key = (window, sid)
        if key in last_cost and cost > last_cost[key]:
            dollars += cost - last_cost[key]
        last_cost[key] = cost
    if points < LIMIT_MIN_POINTS or dollars <= 0:
        return {"usdPerPercent": None, "basis": f"{points:g} percent points logged so far; {LIMIT_MIN_POINTS} are needed"}
    return {"usdPerPercent": dollars / points,
            "basis": f"fitted from {points:g} percent points over {len(windows)} limit windows in limit.log"}


def add_up(prices, ants, key):
    """Ants grouped by key(ant): [{name, ants, cost, usage(5), turns, missing}] costliest first."""
    groups = {}
    for a in ants:
        g = groups.setdefault(key(a), {"name": key(a), "ants": 0, "cost": 0.0, "usage": [0] * 5, "turns": 0, "incomplete": False})
        g["ants"] += 1
        g["turns"] += a["turns"]
        for row in a["usage"].values():
            for i, v in enumerate(row):
                g["usage"][i] += v
        c = cost_of(prices, a["usage"])[0]
        if c is None:
            g["incomplete"] = True
        else:
            g["cost"] += c
    return sorted(groups.values(), key=lambda g: (-g["cost"], str(g["name"])))


def baseline(prices, info, runs):
    """Per station, the usual cost per ant: the median over the repo's other saved runs."""
    per = {}
    for r in runs:
        if r["state"] != info["state"] or r["run"] == info["run"] or not r["saved"]:
            continue
        for g in add_up(prices, r["saved"]["ants"], lambda a: a.get("station", "unknown")):
            if not g["incomplete"] and g["ants"]:
                per.setdefault(g["name"], []).append(g["cost"] / g["ants"])
    return {s: {"usual": statistics.median(v), "runs": len(v)} for s, v in sorted(per.items())}


def is_live(info, runs):
    """A run is live while it has no saved retrospective, no newer run shares
    its sessions, and one of its transcripts was written in the last minutes."""
    if "retro" in info["stages"] or info["setup"] is None:
        return False
    for r in runs:
        if r["setup"] and r["setup"] > info["setup"] and set(r["sessions"]) & set(info["sessions"]):
            return False
    now = time.time()
    for sid in info["sessions"]:
        main = session_file(sid)
        if not main:
            continue
        paths = [main] + glob.glob(os.path.join(glob.escape(main[:-len(".jsonl")]), "subagents", "**", "*.jsonl"), recursive=True)
        for p in paths:
            try:
                if now - os.path.getmtime(p) < LIVE_SECONDS:
                    return True
            except OSError:
                pass
    return False


def view(state, run):
    """Everything the page shows for one run."""
    runs = all_runs()
    info = next((r for r in runs if r["state"] == state and r["run"] == run), None)
    if info is None:
        return None
    prices = load_prices()
    live = is_live(info, runs)
    ants, sessions, warnings = collect(info, runs, live=live)
    source = "transcripts"
    if info["saved"] and len(info["saved"]["ants"]) > len(ants):
        ants = [dict(a) for a in info["saved"]["ants"]]
        warnings = list(info["saved"].get("warnings", [])) + ["transcripts gone: shown from the saved tokens.json"]
        source, live = "tokens.json", False
    elif not ants:
        warnings.append("no transcript found for this run")
    fit = limit_fit(prices)
    per = fit["usdPerPercent"]
    now = time.time()
    rows, total, incomplete = [], 0.0, False
    for a in ants:
        cost, split, missing = cost_of(prices, a["usage"])
        for m in missing:
            warnings.append(f"no price for model {m}: its cost shows as ?")
        if cost is None:
            incomplete = True
        else:
            total += cost
        use = [0] * 5
        for row in a["usage"].values():
            for i, v in enumerate(row):
                use[i] += v
        start, stop = epoch(a.get("start")), epoch(a.get("end"))
        rows.append({**{k: a.get(k) for k in ("id", "session", "stage", "station", "task", "try", "label", "model",
                                               "effort", "start", "end", "turns", "peakContext", "transcript")},
                     "tokens": use, "cost": cost, "split": split,
                     "percent": None if cost is None or not per else cost / per,
                     "seconds": None if start is None or stop is None else round(stop - start),
                     "live": bool(live and a.get("mtime") and now - a["mtime"] < LIVE_SECONDS)})
    if prices.get("broken"):
        warnings.append(f"prices file unreadable: {PRICES}")
    base = baseline(prices, info, runs)
    stations = add_up(prices, ants, lambda a: a["station"])
    for g in stations:
        b = base.get(g["name"])
        g["usual"] = b["usual"] if b else None
        g["usualRuns"] = b["runs"] if b else 0
        each = g["cost"] / g["ants"] if g["ants"] else 0
        g["flag"] = bool(b and not g["incomplete"] and b["runs"] >= prices.get("flag_runs", 3)
                         and b["usual"] > 0 and each >= prices.get("flag_ratio", 2) * b["usual"])
    return {
        "run": run, "state": os.path.basename(state), "repo": info["repo"], "live": live, "source": source,
        "fastPath": not any(a["stage"] in ("plan", "build", "finish", "retro") for a in ants),
        "setupAt": iso(info["setup"]), "lastSaveAt": iso(info["lastSave"]),
        "total": total, "incomplete": incomplete,
        "percent": None if not per else total / per,
        "limit": fit,
        "stages": add_up(prices, ants, lambda a: a["stage"]),
        "stations": stations,
        "tasks": add_up(prices, [a for a in ants if a["task"]], lambda a: a["task"]),
        "ants": rows,
        "warnings": sorted(set(warnings)),
        "pricesNote": "US dollars at API list price; not a subscription bill",
    }


def run_list():
    out = []
    for r in all_runs():
        out.append({"state": os.path.basename(r["state"]), "run": r["run"], "repo": r["repo"],
                    "setupAt": iso(r["setup"]), "stages": r["stages"], "saved": bool(r["saved"]),
                    "fastPath": bool(r["saved"] and r["saved"].get("fastPath"))})
    return out


def print_runs():
    prices = load_prices()
    rows = []
    for r in all_runs():
        ants = r["saved"]["ants"] if r["saved"] else None
        if ants is None:
            ants = collect(r, [], live=False)[0] if r["sessions"] else []
        total = sum(c for c in (cost_of(prices, a["usage"])[0] for a in ants) if c is not None)
        rows.append((r["repo"], r["run"], str(len(ants)), f"${total:.2f}" if ants else "-"))
    if not rows:
        print("no Ishikari runs under ~/.ishikari")
        return
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    for r in rows:
        print("  ".join(c.ljust(widths[i]) for i, c in enumerate(r)).rstrip())


# ---- the server -----------------------------------------------------------


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, kind):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        try:
            if url.path == "/":
                with open(PAGE, "rb") as f:
                    return self.send(200, f.read(), "text/html; charset=utf-8")
            if url.path == "/api/runs":
                return self.send(200, json.dumps(run_list()), "application/json")
            if url.path == "/api/run":
                q = urllib.parse.parse_qs(url.query)
                state, run = q.get("state", [""])[0], q.get("run", [""])[0]
                if not STATE_NAME.fullmatch(state) or not RUN_ID.fullmatch(run):
                    return self.send(400, json.dumps({"error": "bad state or run"}), "application/json")
                data = view(os.path.join(ishikari_root(), state), run)
                if data is None:
                    return self.send(404, json.dumps({"error": "no such run"}), "application/json")
                return self.send(200, json.dumps(data), "application/json")
            return self.send(404, "not found\n", "text/plain")
        except BrokenPipeError:
            pass
        except Exception as e:  # one bad request never stops the page
            self.send(500, json.dumps({"error": f"{type(e).__name__}: {e}"}), "application/json")


def serve(port, open_page):
    server = None
    for p in range(port, port + PORT_TRIES + 1):
        try:
            server = http.server.ThreadingHTTPServer(("127.0.0.1", p), Handler)
            break
        except OSError:
            continue
    if server is None:
        die(f"no free port from {port} to {port + PORT_TRIES}; pass --port <n>")
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Ant Eater: {url}  (Ctrl-C stops it)", flush=True)
    if open_page:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


def run(argv):
    if argv[:1] in (["-h"], ["--help"]) or (argv[:1] in (["serve"], ["snapshot"], ["runs"]) and set(argv[1:]) & {"-h", "--help"}):
        return print(SHORT_HELP, end="")
    if argv[:1] == ["help"]:
        return print(__doc__, end="")
    if argv[:1] == ["runs"] and len(argv) == 1:
        return print_runs()
    if argv[:1] == ["snapshot"]:
        rest = [a for a in argv[1:] if a != "--dry-run"]
        if len(rest) == 2:
            return snapshot(rest[0], rest[1], dry="--dry-run" in argv)
        die("snapshot takes <state> <run> [--dry-run]; see anteater.py --help")
    rest = argv[1:] if argv[:1] == ["serve"] else argv
    port, open_page = PORT, True
    while rest:
        arg = rest.pop(0)
        if arg == "--no-open":
            open_page = False
        elif arg in ("--port", "-p") and rest and rest[0].isdigit() and 0 < int(rest[0]) < 65536:
            port = int(rest.pop(0))
        else:
            die(f"unknown argument {arg!r}; see anteater.py --help")
    serve(port, open_page)


if __name__ == "__main__":
    run(sys.argv[1:])
