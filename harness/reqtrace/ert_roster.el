;;; ert_roster.el --- list ERT tests with their time, for run_tests  -*- lexical-binding: t; -*-
(require 'ert)
(require 'cl-lib)

(defun reqtrace-tests-roster (default)
  "Print \"NAME SECONDS\" per loaded test; a timeout-N tag sets SECONDS, else DEFAULT."
  (dolist (test (ert-select-tests t t))
    (let ((secs (or (cl-loop for tag in (ert-test-tags test)
                             for s = (symbol-name tag)
                             when (string-match "\\`timeout-\\([0-9]+\\)\\'" s)
                             return (string-to-number (match-string 1 s)))
                    default)))
      (princ (format "%s %d\n" (ert-test-name test) secs)))))
;;; ert_roster.el ends here
