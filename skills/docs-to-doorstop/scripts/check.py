#!/usr/bin/env python3
"""ASPICE 4.0 checks that Doorstop's own validation does not do.

Usage: check.py REQS_DIR
Exit 0 when clean, 1 when any ERROR is printed.
"""
import pathlib
import sys

import yaml

REQUIREMENT_DOCS = {"SYS1", "SYS2", "HWE1", "SWE1"}
DESIGN_DOCS = {"SYS3", "HWE2", "SWE2", "SWE3"}
TEST_DOCS = {"SYS4", "SYS5", "HWE3", "HWE4", "SWE4", "SWE5", "SWE6"}
ALL_DOCS = REQUIREMENT_DOCS | DESIGN_DOCS | TEST_DOCS

# parent doc -> (child doc, waivable by trace_exception)
COVERAGE = {
    "SYS1": [("SYS2", False)],
    "SYS2": [("SYS3", True), ("SYS5", False)],
    "SYS3": [("SYS4", False)],  # plus HWE1 / SWE1 by allocation
    "HWE1": [("HWE2", True), ("HWE4", False)],
    "HWE2": [("HWE3", False)],
    "SWE1": [("SWE2", True), ("SWE6", False)],
    "SWE2": [("SWE3", True), ("SWE5", False)],
    "SWE3": [("SWE4", False)],
}
# doc -> extra doc it must also link to (ASPICE HWE.1.BP5, SWE.1.BP5)
EXTRA_LINK = {"HWE1": "SYS2", "SWE1": "SYS2"}
ALLOCATION = {"hardware": "HWE1", "software": "SWE1", "other": None}
FIELDS = ["header", "text", "status", "priority", "rationale", "verification", "source"]
STATUS = {"draft", "reviewed", "approved"}
PRIORITY = {"must", "should", "could"}
TEST_LABELS = ["Technique:", "Pass:", "Entry:", "Exit:", "Setup:"]

errors = []


def err(uid, msg):
    errors.append(f"ERROR {uid}: {msg}")


def links_of(item):
    out = []
    for link in item.get("links") or []:
        out.append(next(iter(link)) if isinstance(link, dict) else str(link))
    return out


def load(reqs):
    items, inactive = {}, set()
    for doc in ALL_DOCS:
        d = reqs / doc
        if not (d / ".doorstop.yml").exists():
            err(doc, f"document missing: {d}")
            continue
        for f in sorted(d.glob("*.yml")):
            if f.name == ".doorstop.yml":
                continue
            data = yaml.safe_load(f.read_text()) or {}
            if not data.get("active", True):
                inactive.add(f.stem)
            elif data.get("normative", True):
                items[f.stem] = (doc, data)
    return items, inactive


def main():
    reqs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "reqs")
    items, inactive = load(reqs)
    children = {}
    for uid, (doc, data) in items.items():
        for p in links_of(data):
            children.setdefault(p, set()).add(uid.split("-")[0])

    for uid, (doc, data) in sorted(items.items()):
        for link in links_of(data):
            if link in inactive:
                err(uid, f"links to inactive item {link}: ask the user")
            elif link not in items:
                err(uid, f"links to unknown item {link}")
        for f in FIELDS:
            if not str(data.get(f) or "").strip():
                err(uid, f"missing field: {f}")
        text = str(data.get("text") or "").strip()
        if len(text.splitlines()) > 5:
            err(uid, f"text has {len(text.splitlines())} lines, max 5")
        if data.get("status") not in STATUS:
            err(uid, f"status must be one of {sorted(STATUS)}")
        if data.get("priority") not in PRIORITY:
            err(uid, f"priority must be one of {sorted(PRIORITY)}")
        if doc in REQUIREMENT_DOCS and " shall " not in f" {text} ":
            err(uid, "requirement text needs 'shall'")
        if doc in TEST_DOCS:
            v = str(data.get("verification") or "")
            for label in TEST_LABELS:
                if label not in v:
                    err(uid, f"verification needs '{label}'")
        if doc in EXTRA_LINK and not data.get("derived"):
            want = EXTRA_LINK[doc]
            if not any(link.startswith(want + "-") for link in links_of(data)):
                err(uid, f"must also link to a {want} item")

        waived = bool(str(data.get("trace_exception") or "").strip())
        if waived and doc not in COVERAGE:
            err(uid, "trace_exception only allowed on items with a design child")
        have = children.get(uid, set())
        for child, waivable in COVERAGE.get(doc, []):
            if child not in have and not (waivable and waived):
                err(uid, f"no {child} child")
        if doc == "SYS3":
            alloc = data.get("allocation") or []
            if not alloc or any(a not in ALLOCATION for a in alloc):
                err(uid, f"allocation must be a non-empty list of {list(ALLOCATION)}")
            for a in alloc:
                need = ALLOCATION.get(a)
                if need and need not in have:
                    err(uid, f"allocated to {a} but has no {need} child")

    print("\n".join(errors) or f"check.py: {len(items)} items clean")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
