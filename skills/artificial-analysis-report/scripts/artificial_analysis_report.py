#!/usr/bin/env python3
"""Artificial Analysis report for GLM, DeepSeek and Grok.

Picks each lab's newest model, lists every effort level Artificial Analysis
published for it, and writes a stats-only dark HTML page.

Usage:
  ./artificial_analysis_report.py            fetch, write, open
  ./artificial_analysis_report.py --no-open  fetch and write only
  ./artificial_analysis_report.py --self-test  parser check on fixed fixtures
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import urllib.request

AA_API = "https://artificialanalysis.ai/api/v2/data/llms/models"
CMP_URL = "https://artificialanalysis.ai/models/comparisons/%s-vs-%s"
OUT = os.path.join(os.path.expanduser("~"), "tmp", "artificial_analysis_report.html")
LABS = ["Z AI", "DeepSeek", "SpaceXAI"]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"


def fetch(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    key = os.environ.get("AA_API_KEY")
    if key and url.startswith(AA_API):
        request.add_header("X-API-Key", key)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def plain(page):
    """Visible text of an HTML page, whitespace collapsed."""
    text = re.sub(r"<script.*?</script>", " ", page, flags=re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text))


def family(name):
    """'DeepSeek V4.1 Flash (Max)' -> 'DeepSeek V4.1 Flash'."""
    return name.split(" (")[0].strip()


def effort(name):
    match = re.search(r"\(([^)]+)\)\s*$", name)
    return match.group(1).lower() if match else "only published setting"


def newest_family(models, lab):
    """Newest release for one lab, plus its same-release effort variants."""
    rows = [m for m in models if (m.get("model_creator") or {}).get("name") == lab]
    if not rows:
        return None, [], []
    rows.sort(key=lambda m: m.get("release_date") or "", reverse=True)
    top = rows[0]
    date, base = top.get("release_date"), family(top["name"])
    variants = [m for m in rows
                if m.get("release_date") == date and family(m["name"]) == base]
    variants.sort(key=lambda m: m["name"])
    others = [m for m in rows if m not in variants]
    return top, variants, others


def numbers_after(text, label, count=2):
    """The first `count` dollar values or bare '-" cells after a label."""
    start = text.find(label)
    if start < 0:
        return ["-"] * count
    window = text[start + len(label):start + len(label) + 140]
    found = re.findall(r"\$([0-9]+(?:\.[0-9]+)?)|\b(-)\b", window)[:count]
    cells = [(a or b) for a, b in found]
    return cells + ["-"] * (count - len(cells))


def parse_comparison(text):
    """{'index_version': '4.3.2', 'a': {...}, 'b': {...}} from a comparison page."""
    version = re.search(r"Intelligence Index v([0-9.]+)", text)
    a = {"input": numbers_after(text, "Input Price per 1M Tokens")[0],
         "cached": numbers_after(text, "Cache Hit Price per 1M Tokens")[0],
         "output": numbers_after(text, "Output Price per 1M Tokens")[0],
         "task": numbers_after(text, "Cost per Task")[0]}
    b = {"input": numbers_after(text, "Input Price per 1M Tokens")[1],
         "cached": numbers_after(text, "Cache Hit Price per 1M Tokens")[1],
         "output": numbers_after(text, "Output Price per 1M Tokens")[1],
         "task": numbers_after(text, "Cost per Task")[1]}
    return {"index_version": version.group(1) if version else None, "a": a, "b": b}





def dollars(value):
    if value in (None, "-"):
        return "-"
    if isinstance(value, str):
        return "$" + value
    return "$%.2f" % value if value >= 0.01 else "$%g" % value


def cells_for(variant, partner):
    """Cost per task and cache-hit price for one variant, from AA comparison pages."""
    if variant["slug"] == partner["slug"]:
        return {"cached": "-", "task": "-"}
    url = CMP_URL % (variant["slug"], partner["slug"])
    try:
        parsed = parse_comparison(plain(fetch(url)))
    except Exception as error:  # dash, not zero; the report still writes
        print("warning: %s: %s" % (url, error), file=sys.stderr)
        return {"cached": "-", "task": "-"}
    return {"cached": parsed["a"]["cached"], "task": parsed["a"]["task"],
            "index_version": parsed["index_version"]}


def rows_for(models):
    """One row per published effort, newest family per lab first."""
    rows, version = [], None
    for lab in LABS:
        top, variants, others = newest_family(models, lab)
        if not top:
            print("warning: no models for %s" % lab, file=sys.stderr)
            continue
        partners = [v for v in variants]
        if len(partners) < 2 and others:
            partners.append(others[0])
        for variant in variants:
            partner = next((p for p in partners if p["slug"] != variant["slug"]), variant)
            extra = cells_for(variant, partner)
            version = version or extra.get("index_version")
            pricing = variant.get("pricing") or {}
            index = (variant.get("evaluations") or {}).get(
                "artificial_analysis_intelligence_index")
            rows.append({
                "lab": lab, "model": family(variant["name"]), "effort": effort(variant["name"]),
                "index": index,
                "input": pricing.get("price_1m_input_tokens"),
                "cached": extra["cached"], "output": pricing.get("price_1m_output_tokens"),
                "task": extra["task"], "slug": variant["slug"],
                "release": variant.get("release_date"),
            })
    rows.sort(key=lambda r: (r["index"] is None, -(r["index"] or 0)))
    return rows, version


def render(rows, version):
    width = max((r["index"] or 0 for r in rows), default=0) or 1
    body = []
    for r in rows:
        score = "-" if r["index"] is None else "%.1f" % r["index"]
        bar = "" if r["index"] is None else (
            '<span class="bar" style="width:%dpx"></span>' % round(r["index"] / width * 92))
        body.append(
            "      <tr>\n"
            "        <td>%s</td><td>%s</td>\n"
            "        <td>%s%s</td>\n"
            "        <td>%s</td><td>%s</td><td>%s</td><td>%s</td>\n"
            "      </tr>" % (r["model"], r["effort"], bar, score,
                              dollars(r["input"]), dollars(r["cached"]),
                              dollars(r["output"]), dollars(r["task"])))
    template = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "template.html"), encoding="utf-8").read()
    return (template
            .replace("{{VERSION}}", version or "unknown")
            .replace("{{DATE}}", __import__("datetime").date.today().isoformat())
            .replace("{{ROWS}}", "\n".join(body)))


def self_test():
    sample = plain(
        "<p>Intelligence Index v4.3.2</p>"
        "<p>Price per 1M Tokens $0.0982 $0.902 "
        "Input Price per 1M Tokens $0.15 $1.40 "
        "Output Price per 1M Tokens $0.50 $4.40 "
        "Cache Hit Price per 1M Tokens $0.026 $0.26 "
        "Cost per Task $0.25 $2.01</p>")
    parsed = parse_comparison(sample)
    assert parsed["index_version"] == "4.3.2", parsed
    assert parsed["a"]["task"] == "0.25", parsed
    assert parsed["b"]["task"] == "2.01", parsed
    assert parsed["b"]["cached"] == "0.26", parsed
    assert family("DeepSeek V4.1 Flash (Max)") == "DeepSeek V4.1 Flash"
    assert effort("Grok 4.7 (Xhigh)") == "xhigh"
    assert effort("GLM 5.3 Flash") == "only published setting"
    empty = parse_comparison("nothing here")
    assert empty["index_version"] is None
    assert empty["a"]["task"] == "-", empty
    print("self-test ok")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not os.environ.get("AA_API_KEY"):
        print("AA_API_KEY is not set; the AA API needs it", file=sys.stderr)
        return 1
    models = json.loads(fetch(AA_API))["data"]
    rows, version = rows_for(models)
    page = render(rows, version)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as handle:
        handle.write(page)
    print(OUT)
    for r in rows:
        print("  %s | %s | index %s | %s / %s / %s | task %s" % (
            r["model"], r["effort"],
            "-" if r["index"] is None else "%.1f" % r["index"],
            dollars(r["input"]), dollars(r["cached"]), dollars(r["output"]),
            dollars(r["task"])))
    if not args.no_open:
        subprocess.run(["/Applications/Firefox.app/Contents/MacOS/firefox",
                        "-new-tab", "file://" + OUT], check=False)


if __name__ == "__main__":
    sys.exit(main())
