;; lemmax config for agent1: settings by folder, read as data, never run.
;; A file with #+LEMMAX_* lines of its own uses those instead.
;; Form: requirements/scripts/lemmax/README.md, "Config".
(:folders
 (("requirements/scripts/lemmax/"
   :tests "requirements/scripts/lemmax/run_tests --addresses"
   :code ("requirements/scripts/lemmax/" "harness/checks/lemmax_lint.py"))))
