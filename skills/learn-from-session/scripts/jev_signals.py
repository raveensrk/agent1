#!/usr/bin/env python3
"""One batched Jev request for a session review, instead of 22 retyped questions.

    jev_signals.py --session [FILE] [--rules rules.json] [--turns turns.json] [--json]

`--turns` takes `[{"text": "..."}, ...]` and skips the generated turn list. Use it
when precision matters: a two-word turn like "hanged?" labels 0.36 confidence
from its bare text and 0.93 when the reviewer annotates what it answered ("sent
while a command had been running for two minutes"). Everything below 0.6 lands
in the report's Open questions, which is the honest place for it.

Reads the transcript through `analyze_commands.py` (same directory), so the
durations and statuses here are the ones the timer printed, not a second
opinion. It builds the state Jev needs - the turns, the calls worth judging, the
candidate rules - and asks the four question families the review asks every
time:

    label_*      one choice per user turn
    waste_*      one noul per slow, aborted, failed or waiting call
    quadrant_*   one choice per finding, over the talk's four cells
    impact_*     one choice per finding
    rule_*       four nouls per candidate rule (falsifiable, scoped, evidence,
                 duplicate)

Input for the rule questions is a JSON file, because a candidate rule is a
judgement the reviewer made, not something the transcript holds:

    [{"id": "R1", "text": "the rule as it would be written"}]

Needs TYPESAFE_API_KEY. Without it, the script prints that the judgements were
not machine-labeled rather than guessing at numbers. Counts are computed in
code, never asked of the model, which cannot count.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
API_URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
MAX_JUDGED_CALLS = 8
MAX_FINDINGS = 6

LABELS = {
    "new_goal": "Asks for new work or a new question",
    "correction": "Corrects the assistant because the previous answer or code was wrong, or the agent had to change course",
    "answer": "Answers a question the assistant asked",
    "praise": "Approves or praises the assistant's work",
    "off_topic": "Unrelated to the session goal",
}
CELLS = {
    "feedback/computational": "A machine decides it after the work, such as a lint or a test",
    "feedback/inferential": "A reviewer judges it after the work",
    "feedforward/computational": "A machine decides it before the work, such as a guard or a generator",
    "feedforward/inferential": "Prose or a rule shapes the work before it happens",
}
IMPACT = {
    "high": "Lost minutes, a repeated mistake, or a wrong result",
    "medium": "Lost a round trip or two",
    "low": "Cosmetic",
}


def load_analyze():
    spec = importlib.util.spec_from_file_location(
        "analyze_commands", HERE / "analyze_commands.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def user_turns(path: str) -> list[dict]:
    """User turns, each with the assistant reply that preceded it.

    Without that context a two-word turn like "next" is unlabelable: the first
    run asked with bare text and Jev answered `answer` at 0.6 confidence for a
    command, which is what the context fixes.
    """
    turns: list[dict] = []
    last_reply = ""
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            message = entry.get("message") or {}
            role = message.get("role")
            content = message.get("content")
            if not isinstance(content, (str, list)):
                continue
            text = content if isinstance(content, str) else " ".join(
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
            if role == "assistant" and text.strip():
                last_reply = text[:300]
            elif role == "user" and text.strip():
                # a pasted skill or long prompt ends with the actual ask
                if len(text) > 500:
                    text = text[:200].rstrip() + " [...] " + text[-300:].lstrip()
                turns.append(
                    {
                        "id": f"t{len(turns) + 1}",
                        "text": text[:500],
                        "after": last_reply,
                    }
                )
    return turns


def judgeable(path: str) -> tuple[list[dict], list[dict]]:
    """The calls worth judging, and the findings that follow from them."""
    analyze = load_analyze()
    calls, results, _ = analyze.read_transcript(path)
    rows = []
    for call in calls:
        result = results.get(call.get("id"))
        rows.append(
            {
                "name": call.get("name"),
                "command": analyze.command_of(call)[:160],
                "seconds": analyze.seconds(call.get("ts"), (result or {}).get("ts")),
                "status": analyze.status_of(result, str(call.get("name"))),
            }
        )
    notable = [
        row
        for row in rows
        if row["status"] in ("aborted", "error", "waiting")
        or (row["seconds"] or 0.0) >= analyze.SLOW_SECONDS
    ]
    notable = sorted(notable, key=lambda r: -(r["seconds"] or 0.0))[:MAX_JUDGED_CALLS]
    findings = [
        {
            "id": f"f{index}",
            "text": f"{row['seconds']:.1f}s {row['status']} call: {row['command'][:120]}",
        }
        for index, row in enumerate(
            [r for r in notable if r["status"] in ("aborted", "error")][:MAX_FINDINGS], start=1
        )
    ]
    return notable, findings


def question_set(turns, calls, findings, rules, target) -> dict:
    questions: dict[str, dict] = {}
    for turn in turns:
        questions[f"label_{turn['id']}"] = {
            "type": "choice",
            "instructions": {
                "question": "Which single label fits this user turn best?",
                "turn": turn["text"][:300],
                "the_agents_previous_reply": turn.get("after", "")[:200],
            },
            "criteria": LABELS,
        }
    for index, call in enumerate(calls, start=1):
        questions[f"waste_c{index}"] = {
            "type": "noul",
            "instructions": {
                "rule": (
                    f"The {call['name']} call `{call['command']}` "
                    f"({call['seconds']:.1f}s, {call['status']}) was a wasted tool call."
                ),
                "question": "Was this tool call wasted?",
            },
            "criteria": {
                "true": "The session paid for it without gaining information it needed, or had to retry it",
                "false": "It earned its cost",
            },
        }
    for finding in findings:
        questions[f"quadrant_{finding['id']}"] = {
            "type": "choice",
            "instructions": {
                "question": "Which cell of the talk's grid does this finding belong in?",
                "turn": f"Finding {finding['id']}: {finding['text']}",
            },
            "criteria": CELLS,
        }
        questions[f"impact_{finding['id']}"] = {
            "type": "choice",
            "instructions": {
                "question": "How much impact did this finding have on the session?",
                "turn": f"Finding {finding['id']}: {finding['text']}",
            },
            "criteria": IMPACT,
        }
    for rule in rules:
        text = rule["text"]
        rid = rule["id"]
        questions[f"rule_{rid}_falsifiable"] = {
            "type": "noul",
            "instructions": {"rule": text, "question": "Is this rule falsifiable?"},
            "criteria": {
                "true": "A command or a read can prove a violation",
                "false": "Only the model's memory can judge it",
            },
        }
        questions[f"rule_{rid}_scoped"] = {
            "type": "noul",
            "instructions": {"rule": text, "question": "Is this rule scoped?"},
            "criteria": {
                "true": f"The rule names where it applies. Target: {target}",
                "false": "It reads as true everywhere or nowhere in particular",
            },
        }
        questions[f"rule_{rid}_evidence"] = {
            "type": "noul",
            "instructions": {
                "rule": text,
                "question": "Is this rule backed by evidence observed in this session, not by imagination?",
            },
            "criteria": {
                "true": "This session measured or observed it",
                "false": "It comes from expectation rather than observation",
            },
        }
        questions[f"rule_{rid}_duplicate"] = {
            "type": "noul",
            "instructions": {
                "rule": text,
                "question": "Does this rule duplicate something the target file already says?",
            },
            "criteria": {
                "true": f"An existing rule covers the same behaviour. Target: {target}",
                "false": "Nothing in the target file covers this behaviour",
            },
        }
    return questions


def evaluate(state: dict, questions: dict) -> dict:
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY not set")
    body = json.dumps({"model": MODEL, "state": state, "questions": questions}).encode()
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)["answers"]


def report(answers: dict, turns, calls, findings, rules) -> str:
    lines = ["| question | answer | confidence |", "| --- | --- | --- |"]
    # sorted, so two runs on one transcript produce a diffable table
    for key in sorted(answers):
        value = answers[key]
        if value.get("type") == "choice":
            answer = f"{value.get('choice')}"
            confidence = f"{value.get('confidence', 0):.2f}"
        else:
            answer = "yes" if value.get("noul", 0) >= 0.5 else "no"
            confidence = f"{value.get('noul', 0):.2f}"
        lines.append(f"| {key} | {answer} | {confidence} |")
    labels = [
        (key, answers[key].get("choice"))
        for key in sorted(answers)
        if key.startswith("label_")
    ]
    corrections = sum(1 for _, choice in labels if choice == "correction")
    wasted = [
        key
        for key in sorted(answers)
        if key.startswith("waste_") and answers[key].get("noul", 0) >= 0.5
    ]
    low = [
        key
        for key in sorted(answers)
        if answers[key].get("confidence", 1) < 0.6
    ]
    counts = [
        "",
        f"Counts (code, not Jev): {len(turns)} user turns, {corrections} corrections, "
        f"{len(calls)} judged calls, {len(wasted)} of them wasted, "
        f"{len(findings)} findings, {len(rules)} candidate rules.",
    ]
    if low:
        counts.append(
            "Below 0.6 confidence, so they are Open questions rather than verdicts: "
            + ", ".join(low)
        )
    return "\n".join(lines + counts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", nargs="?", const="", default=None)
    parser.add_argument("--rules", help="JSON file: [{id, text}, ...]")
    parser.add_argument(
        "--turns",
        help='JSON file: [{"text": "..."}, ...]; skips the generated turn list',
    )
    parser.add_argument("--target", default="the AGENTS.md this review merges into")
    parser.add_argument("--json", action="store_true", help="raw answers, not a table")
    args = parser.parse_args()

    path = args.session or os.environ.get("PI_SESSION_FILE")
    if not path:
        print("no transcript: pass --session FILE or set PI_SESSION_FILE")
        return 2
    if not os.path.exists(path):
        print(f"{path}: not found")
        return 2

    turns = user_turns(path)
    if args.turns:
        curated = json.load(open(args.turns))
        turns = [
            {
                "id": f"t{index}",
                "text": item["text"][:500],
                "after": item.get("after", ""),
            }
            for index, item in enumerate(curated, start=1)
        ]
    calls, findings = judgeable(path)
    rules = json.load(open(args.rules)) if args.rules else []
    state = {
        "session_goal": turns[0]["text"][:300] if turns else "",
        "user_turns": turns,
        "judged_calls": calls,
        "findings": findings,
        "candidate_rules": rules,
    }
    questions = question_set(turns, calls, findings, rules, args.target)
    try:
        answers = evaluate(state, questions)
    except RuntimeError as error:
        print(f"{error}: the judgements were not machine-labeled, say so in the report")
        return 1
    if args.json:
        print(json.dumps(answers, indent=1, sort_keys=True))
    else:
        print(report(answers, turns, calls, findings, rules))
    return 0


if __name__ == "__main__":
    sys.exit(main())
