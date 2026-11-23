;;; ert_roster.el --- list ERT tests with their time, for run_tests  -*- lexical-binding: t; -*-
;; lemma: RT-12
(require 'ert)
(require 'cl-lib)

(defun lemmax-tests-roster (default)
  "Print \"NAME SECONDS\" per loaded test, then \" alone\" for a test tagged alone;
a timeout-N tag sets SECONDS, else DEFAULT."
  (dolist (test (ert-select-tests t t))
    (let ((secs (or (cl-loop for tag in (ert-test-tags test)
                             for s = (symbol-name tag)
                             when (string-match "\\`timeout-\\([0-9]+\\)\\'" s)
                             return (string-to-number (match-string 1 s)))
                    default)))
      ;; An alone tag: run_tests runs the test after the rest, on its own.
      (princ (format "%s %d%s\n" (ert-test-name test) secs (if (memq 'alone (ert-test-tags test)) " alone" ""))))))
;;; ert_roster.el ends here
