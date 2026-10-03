# Jobs

ETA rules for long-running jobs. Loaded from [common.md](common.md) at session start.

## Bash tool timeout

- Max 60 seconds per bash tool call.
- A command that needs longer (release builds, installs, big scans) runs in the background (`nohup ... &`), polled with short calls; or the agent asks the human first and states why.
- Wide scans over `~/repos` exclude `target`, `node_modules` and `.git`; a bare grep there can exceed 60s.

- Anything that can hang carries its own bound: `timeout 180 <command>`. A test
  suite is the usual case - one unbounded `emacs ... ert-run-tests` run hung on a
  warm daemon waiting for a keypress and burned 300s, then 194s when it was
  aborted, while the healthy suite takes 5s.
- `command_guard` refuses a test runner (pytest, `cargo test`, `swift test`,
  `go test`, npm/yarn test, ERT) with no `timeout N`, and prints the bounded form.
  The todo skill's suite is `scripts/test`: bounded, prints the failures.

Applies to any background job, and any foreground job expected to exceed 10 min.

Before launching:

1. Run `date "+%-I:%M %p"` to get the current local time, e.g. `2:23 PM`.
2. Check `tmp/job_timings.jsonl` for prior runs of the same job.
3. Estimate the duration in minutes as a range, e.g. `12-18 min`. State the basis: prior run, sample benchmark, or extrapolation.
4. State the completion time as 12-hour local time with AM/PM, e.g. `ETA 2:35-2:41 PM`. If the range crosses noon or midnight, mark both ends, e.g. `ETA 11:50 AM-12:10 PM`.
5. If the upper bound is 60 min or more: ⚠️ warn me and wait for confirmation before launching.

If the job runs past the upper bound: report once with a new estimate and ETA, and keep running.

After the job finishes, append one line to `tmp/job_timings.jsonl`:

```json
{"date": "2026-09-11T14:23:00-07:00", "job": "pytest tests/", "est_min": [12, 18], "actual_min": 15, "basis": "prior run"}
```

- One JSON object per line. Append only; never rewrite the file.
- Store times as ISO 8601 and durations as numbers in minutes. AM/PM is for display only.

`tmp/` is machine-local and must stay in `.gitignore`. Timings depend on hardware, so they are exempt from the Repeatability rule.
