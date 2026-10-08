---
id: "mg144gxck6"
title: "Investigate the Jev score that returned confidence 0.00"
state: "done"
due: ""
priority: "D"
tag: ["voice_score"]
repeat: ""
effort: ""
postpone: 0
created: "2026-10-04"
closed: "2026-10-06T23:52"
---

Seen in the reviewed session 01a103cc (2026-10-03): one think score came back with confidence 0.00 while the other answers of the same Jev call carried a real confidence.
Evidence: the voice-score entry in /Users/raveen_kumar_personal/.pi/agent/sessions/--Users-raveen_kumar_personal--/2026-10-03T22-04-48-266Z_01a103cc-6109-758b-9e74-9a975cd1980e.jsonl, and the ledger rows for that run.
Check, in order:
- which question id it was (think or reply) and what score it carried;
- whether the other answers of the same call had real confidence values;
- whether the classifier returned a confidence at all, or the extension read a field that was not there.
Done when: one line names the cause beside the code, and the calibration note in the extension header says whether confidence is trustworthy or should leave the display.
Done 2026-10-06. The note evidence was close but wrong: session 01a103cc holds one voice-score entry and no zero, its confidences run 0.32-0.55. The three zeros on disk are in 01a103e4, 01a103f3 and 01a107e5, all think blocks. Answers to the three checks, in order. (1) think every time, scoring 1.14 beside a reply at 0.6, 1.41 beside a reply at 0.8, and 1.81 inside a 19-block call whose confidences run 0.14-0.65 and whose neighbours score 1.82 and 2.00 - ordinary scores, so a zero does not mark a score to distrust. (2) yes, the other answers of the same call carried real confidences, and no call-level failure is recorded. (3) the classifier returned a confidence: pi's parser requires a finite one and throws otherwise (requiredNumber in the system-one bundle), which would fail the whole call and draw voice score unavailable - so a 0 is the floor of a real answer, not a field that was not there. Survey over every voice-score entry on disk, 189 session files, 1,991 answered questions: 3 zeros (0.15 percent), median 0.48, range 0-0.94, 82 distinct values, median within-call spread 0.29 and only 5 of 202 calls flat, so the number separates the blocks of a call. Script kept for re-measurement: ~/tmp/voice_probe/confidence_survey.py. Verdict written where the todo asked: the calibration note in the extension header says keep it in the expanded view and never gate on it - nothing measured says it is calibrated, and no threshold, gate, ledger row or decision reads it - and one line beside the code says a 0 is the floor of a real answer. Verified: test_voice_score.ts green, harness/lint.py --changed 12 checks 0 findings, timeout 90 pi -p loads with no error.
