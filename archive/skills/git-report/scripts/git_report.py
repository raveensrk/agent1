#!/usr/bin/env python3
"""Collect a person's git commits across their repos for a time window; prints JSON.

Config: ~/.local/git_report.toml (dirs, repos, emails, and default_hours or
start/end); --suggest proposes values. Every repo is fetched, 8 at a time,
with ssh in batch mode; a remote URL is cloned as a mirror into
~/.cache/git_report first. Exit 0 with JSON on stdout; 1 with an ERROR line
for a bad config, window or flag.

Example: git_report.py -1d
"""
import concurrent.futures, datetime, json, os, re, subprocess, sys

if sys.version_info < (3, 11):
    sys.exit("ERROR: python 3.11+ required (for tomllib); found " + sys.version.split()[0])
import tomllib

CONFIG = os.path.expanduser("~/.local/git_report.toml")
CACHE = os.path.expanduser("~/.cache/git_report")
PRUNE = {"node_modules", ".venv", "venv", "__pycache__"}


def parse_time(s):
    if isinstance(s, datetime.datetime):  # TOML datetime; naive means local time
        return s.astimezone()
    if isinstance(s, datetime.date):  # TOML date: midnight local time
        return datetime.datetime.combine(s, datetime.time()).astimezone()
    if not isinstance(s, str):
        sys.exit(f"ERROR: bad time {s!r}; use 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD'")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).astimezone()
        except ValueError:
            pass
    sys.exit(f"ERROR: bad time {s!r}; use 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD'")


def git(repo, *args, timeout=60, batch_ssh=False):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    if batch_ssh:  # never let ssh prompt; keep any user-configured ssh command
        env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes -o ConnectTimeout=15")
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                          errors="replace", env=env, timeout=timeout,
                          stdin=subprocess.DEVNULL)


def is_url(s):
    return "://" in s or re.match(r"^[\w.-]+@[\w.-]+:", s) is not None


def load_config():
    if not os.path.isfile(CONFIG):
        sys.exit(f"ERROR: config not found: {CONFIG}")
    try:
        with open(CONFIG, "rb") as f:
            cfg = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"ERROR: invalid TOML in {CONFIG}: {e}")
    for key in ("dirs", "repos", "emails"):
        val = cfg.get(key, [])
        if not isinstance(val, list) or not all(isinstance(v, str) for v in val):
            sys.exit(f"ERROR: '{key}' in {CONFIG} must be a list of strings")
        cfg[key] = [v.strip() for v in val if v.strip()]
    if not cfg["emails"]:
        sys.exit(f"ERROR: 'emails' in {CONFIG} is empty")
    if not cfg["dirs"] and not cfg["repos"]:
        sys.exit(f"ERROR: 'dirs' and 'repos' in {CONFIG} are both empty")
    if "default_hours" in cfg and ("start" in cfg or "end" in cfg):
        sys.exit(f"ERROR: {CONFIG} sets default_hours and start/end; keep only one")
    hours = cfg.get("default_hours", 24)
    if isinstance(hours, bool) or not isinstance(hours, (int, float)) or hours <= 0:
        sys.exit(f"ERROR: 'default_hours' in {CONFIG} must be a number above 0")
    cfg["default_hours"] = hours
    for key in ("start", "end"):
        if key in cfg:
            cfg[key] = parse_time(cfg[key])
    return cfg


def discover(root):
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        if ".git" in dirnames or ".git" in filenames:
            yield dirpath
        dirnames[:] = [d for d in dirnames if d != ".git" and d not in PRUNE]


def mirror(url):
    name = re.sub(r"[^\w.-]+", "_", re.sub(r"^\w+://", "", url)).strip("_")
    path = os.path.join(CACHE, name if name.endswith(".git") else name + ".git")
    if not os.path.isdir(path):
        os.makedirs(CACHE, exist_ok=True)
        r = subprocess.run(["git", "clone", "--mirror", "--quiet", url, path],
                           capture_output=True, text=True, timeout=600,
                           stdin=subprocess.DEVNULL,
                           env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
        if r.returncode:
            return None, r.stderr.strip()
    return path, None


def fetch(repo):
    if not git(repo, "remote").stdout.strip():
        return "no remote"
    try:
        custom_ssh = git(repo, "config", "--get", "core.sshCommand").stdout.strip()
        r = git(repo, "fetch", "--all", "--prune", "--quiet", timeout=180,
                batch_ssh=not custom_ssh)
    except subprocess.TimeoutExpired:
        return "fetch timed out after 180s"
    if not r.returncode:
        return None
    lines = [x for x in r.stderr.splitlines() if x.strip()]
    return next((x for x in lines if x.startswith(("fatal:", "error:"))), " ".join(lines))[:300]


def commits(repo, bare, start, end, emails):
    fmt = "%x1e%H%x1f%h%x1f%at%x1f%ae%x1f%an%x1f%s%x1f%b"
    r = git(repo, "log", "--all", "--no-merges", f"--since=@{int(start.timestamp())}",
            f"--format={fmt}", timeout=300)
    out = {}
    for rec in r.stdout.split("\x1e")[1:]:
        h, short, at, ae, an, subj, body = rec.split("\x1f", 6)
        at = int(at)
        if ae.strip().lower() not in emails or not start.timestamp() <= at <= end.timestamp():
            continue
        refs = git(repo, "for-each-ref", "--contains", h,
                   "--format=%(refname)", "refs/heads", "refs/remotes").stdout.split()
        pushed = bare or any(x.startswith("refs/remotes/") for x in refs)
        branches = sorted({re.sub(r"^refs/(heads|remotes)/", "", x) for x in refs
                           if not x.endswith("/HEAD")})
        stat = git(repo, "show", "--shortstat", "--format=", h).stdout.strip()
        key = (ae.lower(), at, subj)  # rebased or amended copies of the same work
        if key in out:
            out[key]["branches"] = sorted(set(out[key]["branches"]) | set(branches))
            out[key]["pushed"] |= pushed
            continue
        out[key] = {
            "time": datetime.datetime.fromtimestamp(at).astimezone().strftime("%Y-%m-%d %H:%M"),
            "hash": short, "author": f"{an} <{ae}>", "subject": subj,
            "body": body.strip()[:1500], "stat": stat, "branches": branches[:5],
            "pushed": pushed,
        }
    return sorted(out.values(), key=lambda c: c["time"])


def resolve_repos(cfg, clone=True):
    """Unique repos from dirs and repos: {git common dir: (worktree path, is_mirror)}."""
    skipped, found = [], []
    for d in cfg["dirs"]:
        p = os.path.expanduser(d)
        if os.path.isdir(p):
            found += [(x, False) for x in discover(p)]
        else:
            skipped.append(f"dirs: {d} (not a directory)")
    for entry in cfg["repos"]:
        if is_url(entry):
            if not clone:  # --check never clones
                continue
            path, err = mirror(entry)
            if path:
                found.append((path, True))
            else:
                skipped.append(f"repos: {entry} (clone failed: {err})")
        else:
            p = os.path.expanduser(entry)
            if git(p, "rev-parse", "--git-dir").returncode if os.path.isdir(p) else True:
                skipped.append(f"repos: {entry} (not a git repo)")
            else:
                found.append((p, False))

    repos = {}
    for path, bare in found:
        r = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
        if r.returncode:
            skipped.append(f"{path} (not readable as a git repo)")
            continue
        repos.setdefault(os.path.realpath(r.stdout.strip()), (os.path.realpath(path), bare))
    return repos, skipped


SHORTCUT = re.compile(r"^(-?\d+)\s*(d|days?|w|wk|weeks?)?$", re.I)


def shortcut(text):
    """0d today, -1d yesterday, -Nd that one day; -N last N days and -Nw last
    N weeks, both counting today and ending now. Returns (start, end)."""
    m = SHORTCUT.match(text.strip())
    n = int(m.group(1)) if m else 1
    unit = (m.group(2) or "").lower()[:1] if m else ""
    if not m or n > 0 or (n == 0 and unit != "d"):
        sys.exit(f"ERROR: bad window {text!r}; use 0d, -1d, -Nd, -N or -Nw (e.g. -1 week)")
    now = datetime.datetime.now().astimezone()
    today = now.date()
    def midnight(days_ago):
        d = today - datetime.timedelta(days=days_ago)
        return datetime.datetime.combine(d, datetime.time()).astimezone()
    if unit == "d":  # one calendar day
        return midnight(-n), now if n == 0 else midnight(-n - 1)
    days = -n * 7 if unit == "w" else -n  # whole days, today included
    return midnight(days - 1), now


def window(cfg, args, short=None):
    # Any flag or shortcut overrides the config window as a whole, so a stale
    # config start or end never mixes with it.
    if short:
        (start, end), source = shortcut(short), f"shortcut {short}"
    elif args:
        source, start, end = "flags", args.get("--start"), args.get("--end")
        start, end = start and parse_time(start), end and parse_time(end)
    elif "start" in cfg or "end" in cfg:
        source, start, end = "config", cfg.get("start"), cfg.get("end")
    else:
        source, start, end = "default_hours", None, None
    end = end or datetime.datetime.now().astimezone()
    start = start or end - datetime.timedelta(hours=cfg["default_hours"])
    if start >= end:
        sys.exit(f"ERROR: start {start} is not before end {end}")
    return start, end, {"start": start.isoformat(timespec="minutes"),
                        "end": end.isoformat(timespec="minutes"), "source": source}


SUGGEST_SKIP = {"Library", "Applications", "Movies", "Music", "Pictures"}


def tilde(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path == home or path.startswith(home + os.sep) else path


def suggest():
    """Suggest config values from this machine. Reads only; writes nothing."""
    home = os.path.expanduser("~")
    roots = []  # repo roots up to 4 levels below home, not inside other repos
    for dirpath, dirnames, filenames in os.walk(home, onerror=lambda e: None):
        depth = dirpath[len(home):].count(os.sep)
        if dirpath != home and (".git" in dirnames or ".git" in filenames):
            roots.append(dirpath)
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in PRUNE
                       and not (dirpath == home and d in SUGGEST_SKIP) and depth < 4]
    groups = {}
    for r in roots:
        top = os.path.join(home, os.path.relpath(r, home).split(os.sep)[0])
        groups[top] = groups.get(top, 0) + 1

    # Candidate emails come only from git config (global and per repo), never
    # from other people's commits.
    sources = {}
    def add(email, where):
        if email.strip():
            sources.setdefault(email.strip().lower(), set()).add(where)
    add(git(home, "config", "--global", "--get", "user.email").stdout, "global git config")
    for r in roots:
        add(git(r, "config", "--get", "user.email").stdout, tilde(r))
    add(git(os.getcwd(), "config", "--get", "user.email").stdout, "current directory")
    counts = dict.fromkeys(sources, 0)
    for r in roots:
        for ae in git(r, "log", "--all", "--format=%ae", timeout=300).stdout.split():
            if ae.lower() in counts:
                counts[ae.lower()] += 1

    json.dump({
        "config_path": tilde(CONFIG), "config_exists": os.path.isfile(CONFIG),
        "dirs": [{"dir": tilde(d), "repos": n} for d, n in sorted(groups.items())],
        "emails": [{"email": e, "commits": counts[e],
                    "from": sorted(w for w in sources[e] if not w.startswith("~"))
                    + [f"{sum(w.startswith('~') for w in sources[e])} repo config(s)"]
                    * any(w.startswith("~") for w in sources[e])}
                   for e in sorted(sources, key=lambda e: -counts[e])],
        "default_hours": 24,
    }, sys.stdout, indent=1, ensure_ascii=False)


USAGE = """usage:
  git_report.py [--start 'YYYY-MM-DD HH:MM'] [--end 'YYYY-MM-DD HH:MM']
  git_report.py WINDOW      0d today, -1d yesterday, -Nd that one day,
                            -N last N days, -Nw or '-N week' last N weeks
  git_report.py --check [--start ...] [--end ...]   validate config, no fetch
  git_report.py --suggest                           suggest config values
  git_report.py -h|--help                           this text"""


def main():
    argv = sys.argv[1:]
    if {"-h", "--help"} & set(argv):
        print(__doc__)
        print(USAGE)
        return
    if argv == ["--suggest"]:
        return suggest()
    check = "--check" in argv
    argv = [a for a in argv if a != "--check"]
    # Shortcut words come before any flag: "-1d", or "-1 week" as two words.
    i = next((j for j, a in enumerate(argv) if a.startswith("--")), len(argv))
    short, argv = " ".join(argv[:i]), argv[i:]
    if len(argv) % 2 or any(k not in ("--start", "--end") for k in argv[::2]):
        sys.exit("ERROR: " + USAGE)
    if short and argv:
        sys.exit("ERROR: give a window shortcut or --start/--end, not both")
    args = dict(zip(argv[::2], argv[1::2]))
    cfg = load_config()
    start, end, win = window(cfg, args, short)
    emails = {e.lower() for e in cfg["emails"]}

    if check:
        repos, skipped = resolve_repos(cfg, clone=False)
        urls = sum(map(is_url, cfg["repos"]))
        json.dump({"config_ok": not skipped and bool(repos or urls),
                   "config_path": tilde(CONFIG), "window": win,
                   "repos_found": len(repos), "remote_urls": urls,
                   "emails": sorted(emails), "skipped": skipped},
                  sys.stdout, indent=1, ensure_ascii=False)
        return

    repos, skipped = resolve_repos(cfg)
    failed = []
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        results = dict(zip(repos, ex.map(lambda k: fetch(repos[k][0]), repos)))
    for k, err in results.items():
        if err and err != "no remote":
            failed.append({"repo": repos[k][0], "error": err})

    report = []
    for k, (path, bare) in sorted(repos.items(), key=lambda kv: kv[1][0]):
        c = commits(path, bare, start, end, emails)
        if c:
            report.append({"repo": path, "local_only_repo": results[k] == "no remote", "commits": c})

    json.dump({
        "window": win, "repos_scanned": len(repos), "repos_with_commits": report,
        "skipped": skipped, "fetch_failed": failed,
    }, sys.stdout, indent=1, ensure_ascii=False)


main()
