#!/usr/bin/env python3
"""Tests for agent-usage-report.

Run with:

    python3 tests/run_tests.py

The adapter tests point every harness at ``tests/fixtures`` through the
environment overrides the adapters already honour, so they never touch real
logs. Expected token totals are written out explicitly: if an adapter changes
its parsing, these numbers fail loudly.

Options: -h, --help prints this text, then unittest's own options (-k
PATTERN, -f, ...). Sets the AGENT_REPORT_* env vars for its own run; writes
only temp files. Exit 0 when every test passes, 1 on a failure.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts"))

FIXTURES = ROOT / "tests" / "fixtures"


def build_opencode_db(path):
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT);
        CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, data TEXT,
                              time_created INTEGER);
        CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT,
                           data TEXT, time_created INTEGER);
        """
    )
    conn.execute("INSERT INTO session VALUES (?, ?)", ("ses1", "/tmp/demo"))
    conn.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?)",
        ("u1", "ses1", json.dumps({"role": "user"}), 1),
    )
    conn.execute(
        "INSERT INTO part VALUES (?, ?, ?, ?, ?)",
        ("p1", "u1", "ses1", json.dumps({"type": "text", "text": "please run the tests"}), 1),
    )
    conn.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?)",
        ("a1", "ses1", json.dumps({
            "role": "assistant", "cost": 0.004,
            "tokens": {"total": 1600, "input": 1000, "output": 100, "reasoning": 0,
                       "cache": {"write": 0, "read": 500}},
            "modelID": "opencode-test", "providerID": "opencode", "finish": "stop",
        }), 2),
    )
    conn.commit()
    conn.close()


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db = Path(self.tmp.name) / "opencode.db"
        build_opencode_db(db)
        os.environ["AGENT_REPORT_PI_DIR"] = str(FIXTURES / "pi")
        os.environ["AGENT_REPORT_CLAUDE_DIR"] = str(FIXTURES / "claude")
        os.environ["AGENT_REPORT_CODEX_DIR"] = str(FIXTURES / "codex")
        os.environ["AGENT_REPORT_OPENCODE_DB"] = str(db)
        os.environ["AGENT_REPORT_OPENCODE_ZEN_JSON"] = str(FIXTURES / "opencode_zen" / "console_usage.json")

        import collect
        self.collect = collect
        self.records, self.detected, self.missing = collect.load({}, local=True)
        self.turns = {r["harness"]: r for r in self.records if r["kind"] == "assistant"}

    def tearDown(self):
        for key in ("AGENT_REPORT_PI_DIR", "AGENT_REPORT_CLAUDE_DIR",
                    "AGENT_REPORT_CODEX_DIR", "AGENT_REPORT_OPENCODE_DB",
                    "AGENT_REPORT_OPENCODE_ZEN_JSON"):
            os.environ.pop(key, None)
        self.tmp.cleanup()

    def test_all_harnesses_detected(self):
        names = {item["name"] for item in self.detected}
        self.assertEqual(names, {"pi", "claude_code", "codex", "opencode", "opencode_zen"})

    def test_default_mode_is_cloud_only(self):
        records, detected, missing = self.collect.load({}, local=False)
        names = {item["name"] for item in detected}
        self.assertEqual(names, {"opencode_zen"})

    def test_pi_tokens(self):
        turn = self.turns["pi"]
        self.assertEqual((turn["input"], turn["cache_read"], turn["output"], turn["total"]),
                         (1000, 500, 100, 1600))
        self.assertEqual(turn["cost"], 0.004)
        self.assertEqual(turn["tool_calls"], 1)
        self.assertEqual(turn["tool_errors"], 1)

    def test_claude_tokens(self):
        turn = self.turns["claude_code"]
        self.assertEqual((turn["input"], turn["cache_read"], turn["cache_write"],
                          turn["output"], turn["total"]), (2, 400, 300, 50, 752))
        self.assertEqual(turn["reasoning"], 5)
        self.assertEqual(turn["tool_errors"], 1)

    def test_codex_folds_cache_into_input(self):
        turn = self.turns["codex"]
        self.assertEqual((turn["input"], turn["cache_read"], turn["output"], turn["total"]),
                         (400, 600, 40, 1040))
        self.assertEqual(turn["stop_reason"], "error")

    def test_opencode_tokens(self):
        turn = self.turns["opencode"]
        self.assertEqual((turn["input"], turn["cache_read"], turn["output"], turn["total"]),
                         (1000, 500, 100, 1600))
        self.assertEqual(turn["cost"], 0.004)

    def test_opencode_zen_tokens(self):
        turns = [r for r in self.records if r["harness"] == "opencode_zen"]
        self.assertEqual(len(turns), 2)
        self.assertEqual(sum(t["input"] for t in turns), 3000)
        self.assertEqual(sum(t["cache_read"] for t in turns), 750)
        self.assertEqual(sum(t["output"] for t in turns), 150)
        self.assertEqual(sum(t["total"] for t in turns), 3900)
        self.assertEqual(sum(t["cost"] for t in turns), 6.5)
        for t in turns:
            self.assertEqual(t["cost_source"], "recorded")
            self.assertEqual(t["provider"], "opencode")
            self.assertEqual(t["timestamp"], 0.0)

    def test_aggregate_totals(self):
        dataset = self.collect.aggregate(self.records)
        self.assertEqual(dataset["turns"], 6)
        self.assertEqual(dataset["requests"], 4)
        self.assertEqual(dataset["sessions"], 5)
        self.assertEqual(sum(e["total"] for e in dataset["models"].values()), 8892)

    def test_redact_projects(self):
        import report
        dataset = self.collect.aggregate(self.records)
        report._redact_projects(dataset)
        names = {p["project"] for p in dataset["projects"].values()}
        self.assertTrue(names.issubset({"Project %d" % n for n in range(1, len(names) + 1)}))
        for sess in dataset["sessions_detail"]:
            self.assertIn(sess.get("project"), names | {None})


class PricingTests(unittest.TestCase):
    def test_cost_from_rates(self):
        import pricing
        rates = {"input": 5.0, "output": 25.0, "cache_read": 0.5, "cache_write": 6.25}
        tokens = {"input": 1_000_000, "output": 1_000_000,
                  "cache_read": 1_000_000, "cache_write": 1_000_000}
        self.assertAlmostEqual(pricing.compute_cost(tokens, rates), 36.75)

    def test_catalog_resolves_namespaced_and_aliased(self):
        import pricing
        catalog = pricing.Catalog()
        catalog.add("openai", "gpt-x", {"input": 1, "output": 2})
        self.assertIsNotNone(catalog.resolve("openai-codex", "gpt-x"))
        self.assertIsNotNone(catalog.resolve("openai", "openai/gpt-x"))
        self.assertIsNone(catalog.resolve("openai", "nope"))

    def test_snapshot_is_usable_offline(self):
        import pricing
        catalog = pricing.build_catalog({}, offline=True)
        self.assertGreater(catalog.size(), 100)


class ValidationTests(unittest.TestCase):
    def test_config_schema_rejects_unknown_keys(self):
        import validate
        with self.assertRaises(SystemExit):
            validate.validate_config({"nonsense": 1})

    def test_config_schema_accepts_known(self):
        import validate
        validate.validate_config({"output_dir": "/tmp", "aa_api_key": "k"})

    def test_prices_schema_rejects_string_rate(self):
        import validate
        with self.assertRaises(SystemExit):
            validate.validate_prices({"anthropic/claude-opus-5": {"input": "five"}})


class ScoringTests(unittest.TestCase):
    def _dataset(self):
        def model(name, turns, requests, **kw):
            base = {
                "model": name, "turns": turns, "requests": requests,
                "input": 0, "cache_read": 0, "cache_write": 0, "output": 0,
                "reasoning": 0, "total": 0, "tool_calls": 0, "tool_errors": 0,
                "error_stops": 0, "context_window": 0,
                "cost_total": kw.pop("cost_total", 0.0), "cost_recorded": 0.0,
                "cost_per_million": kw.pop("cost_per_million", 0.0),
                "providers": {}, "harnesses": {}, "thinking_levels": {},
                "rates": None, "tools": {},
            }
            base.update(kw)
            return base

        models = {
            "smart": model("smart", 400, 100, cost_per_million=1.0, output=1000, total=10000),
            "dull": model("dull", 300, 100, cost_per_million=5.0, error_stops=30,
                          total=10000, output=1000),
        }
        return {"models": models, "sessions": 1, "requests": 205, "turns": 705,
                "projects": {}, "daily": {}, "hourly": [[0] * 24 for _ in range(7)],
                "switches": {}}

    def test_aa_index_drives_quality(self):
        import score
        aa = {"smart": {"intelligence_index": 68.0}, "dull": {"intelligence_index": 30.0}}
        dataset = score.compute(self._dataset(), aa, {})
        self.assertEqual(dataset["leaders"]["most_intelligent"]["model"], "smart")
        self.assertEqual(dataset["models"]["smart"]["aa_intelligence"], 68.0)

    def test_efficiency_prefers_cheaper_equal_model(self):
        import score
        dataset = self._dataset()
        dataset["models"]["cheap"] = dict(dataset["models"]["smart"], model="cheap",
                                          cost_per_million=0.1)
        aa = {"smart": {"intelligence_index": 68.0}, "cheap": {"intelligence_index": 68.0}}
        result = score.compute(dataset, aa, {})
        self.assertEqual(result["leaders"]["most_efficient"]["model"], "cheap")
        self.assertGreater(result["models"]["cheap"]["value_per_dollar"],
                           result["models"]["smart"]["value_per_dollar"])

    def test_no_benchmark_leaves_unranked(self):
        import score
        dataset = score.compute(self._dataset(), {}, {})
        self.assertEqual(dataset["leaders"]["most_intelligent"], None)
        self.assertEqual(dataset["models"]["smart"]["aa_intelligence"], None)

    def test_benchmark_name_matching(self):
        import benchmarks
        self.assertEqual(benchmarks.normalize("Claude Opus 5"), "claudeopus5")
        self.assertEqual(benchmarks.normalize("claude-opus-5"), "claudeopus5")

    def test_market_verdict_top3_per_tier(self):
        import score
        aa = {
            "gpt55": {"intelligence_index": 60.0, "price": 3.0, "speed": 90.0,
                      "name": "gpt-5.5"},
            "claudeopu55flash": {"intelligence_index": 30.0, "price": 0.3,
                                 "speed": 120.0, "name": "claude-opus-5.5-flash"},
            "gpt55mini": {"intelligence_index": 20.0, "price": 0.2, "speed": 150.0,
                          "name": "gpt-5.5-mini"},
        }
        or_rankings = [
            {"slug": "openai/gpt-5.5", "tokens": 500, "share": 50.0},
            {"slug": "openai/gpt-5.5-mini", "tokens": 300, "share": 30.0},
            {"slug": "deepseek/claude-opus-5.5-flash", "tokens": 200, "share": 20.0},
            {"slug": "other", "tokens": 100, "share": 10.0},
        ]
        dataset = self._dataset()
        dataset["models"]["gpt-5.5"] = dict(dataset["models"]["smart"], model="gpt-5.5")
        result = score.compute(dataset, aa, or_rankings, {})
        market = result["market"]
        self.assertEqual([e["model"] for e in market["frontier"]], ["gpt-5.5"])
        self.assertEqual([e["model"] for e in market["flash"]],
                         ["gpt-5.5-mini", "claude-opus-5.5-flash"])
        self.assertTrue(market["flash"][0]["used_by_you"] is False)

    def test_verdict_flags_your_models(self):
        import score
        aa = {"smart": {"intelligence_index": 68.0, "price": 3.0, "speed": 90.0,
                        "name": "smart"}}
        or_rankings = [{"slug": "maker/smart", "tokens": 100, "share": 40.0}]
        dataset = self._dataset()
        result = score.compute(dataset, aa, or_rankings, {})
        entry = result["market"]["frontier"][0]
        self.assertTrue(entry["used_by_you"])


class RenderTests(unittest.TestCase):
    def test_html_is_self_contained(self):
        import collect, pricing, render, score
        records = [
            {"kind": "user", "harness": "t", "session_id": "1", "project": "/p",
             "timestamp": 1, "text": "hi"},
            {"kind": "assistant", "harness": "t", "session_id": "1", "project": "/p",
             "timestamp": 2, "provider": "p", "model": "m", "input": 10, "cache_read": 0,
             "cache_write": 0, "output": 5, "reasoning": 0, "total": 15, "cost": 0.01,
             "cost_source": "recorded", "stop_reason": "stop", "tool_calls": 1,
             "tool_errors": 0, "thinking_level": None, "context_window": None,
             "text": "", "tools": {"read": 1}},
        ]
        dataset = collect.aggregate(records)
        pricing.attach(dataset, pricing.Catalog())
        score.compute(dataset, {}, [], {"score": {}})
        meta = {"window": "all time", "window_start": "a", "window_end": "b",
                "generated": "now", "detected": [], "missing": [],
                "pricing_source": "test", "pricing_models": 0,
                "benchmark_source": "test"}
        html = render.build(dataset, meta, {})
        self.assertIn("<!doctype html>", html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn("<link ", html)
        self.assertNotIn('src="http', html)
        self.assertIn("plotly", html)
        self.assertIn("Most intelligent", html)

    def test_leaderboard_is_sortable_and_filterable(self):
        import collect, pricing, render, score
        records = [
            {"kind": "assistant", "harness": "h<%d>" % index, "session_id": str(index),
             "project": "/p", "timestamp": index + 1, "provider": "p",
             "model": "model-%d" % index, "input": 10 * index, "cache_read": 0,
             "cache_write": 0, "output": 5, "reasoning": 0, "total": 10 * index + 5,
             "cost": 0.01 * index, "cost_source": "recorded", "stop_reason": "stop",
             "tool_calls": 1, "tool_errors": 0, "thinking_level": None,
             "context_window": None, "text": "", "tools": {}}
            for index in range(1, 5)
        ]
        dataset = collect.aggregate(records)
        pricing.attach(dataset, pricing.Catalog())
        score.compute(dataset, {}, [], {"score": {}})
        meta = {"window": "all time", "window_start": "a", "window_end": "b",
                "generated": "now", "detected": [], "missing": [],
                "pricing_source": "test", "pricing_models": 0,
                "benchmark_source": "test"}
        html = render.build(dataset, meta, {})
        self.assertIn('id="lb"', html)
        self.assertIn("data-key='cost_total'", html)
        self.assertIn("data-sort=", html)
        self.assertIn('id="lb-search"', html)
        self.assertIn('id="lb-harness"', html)
        self.assertIn('id="lb-ranked"', html)
        self.assertIn("All harnesses", html)


class OutputDirTests(unittest.TestCase):
    def test_default_is_downloads(self):
        import report
        class Args(object):
            out = None
        self.assertEqual(report._output_dir(Args(), {}), Path.home() / "Downloads")

    def test_out_flag_wins(self):
        import report
        class Args(object):
            out = "/tmp/custom/report.html"
        self.assertEqual(report._output_dir(Args(), {}), Path("/tmp/custom"))

    def test_config_output_dir(self):
        import report
        class Args(object):
            out = None
        self.assertEqual(report._output_dir(Args(), {"output_dir": "/tmp/elsewhere"}),
                         Path("/tmp/elsewhere"))


if __name__ == "__main__":
    # -h and --help: this docstring, then unittest prints its options and exits 0.
    if {"-h", "--help"} & set(sys.argv[1:]):
        print(__doc__)
    unittest.main(verbosity=2)
