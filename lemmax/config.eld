;; lemmax config for agent1: settings by folder, read as data, never run.
;; A file with #+LEMMAX_* lines of its own uses those instead.
;; Form: requirements/scripts/lemmax/README.md, "Config".
;; agent1 asks for a code marker on every lemma done from 2026-11-22 on,
;; and for all code under a marker in code files changed from 2026-11-22 on.
(:markers-required-from "2026-11-22"
 :coverage-required-from "2026-11-22"
 :folders
 (("requirements/scripts/lemmax/"
   :tests "requirements/scripts/lemmax/run_tests --addresses"
   :code ("requirements/scripts/lemmax/" "harness/checks/lemmax_lint.py"))))
