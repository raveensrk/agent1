;;; lemmax_tests.el --- lemmax's own tests (RT-12)  -*- lexical-binding: t; -*-

;; Each test builds an invented repo under ~/tmp and runs the real launcher.
;; Commits in test repos skip every hook. Run: requirements/scripts/lemmax/run_tests

(require 'ert)
(require 'cl-lib)
(require 'subr-x)
(require 'json)

(defconst rt-dir (file-name-directory (or load-file-name buffer-file-name)))
(defconst rt-bin (expand-file-name "lemmax" rt-dir))
(defconst rt-agent1 (file-name-as-directory (expand-file-name "../../.." rt-dir)))

;;;; Helpers

(defun rt-tmp ()
  (make-directory (expand-file-name "~/tmp") t)
  (make-temp-file (expand-file-name "~/tmp/lemmax-test-") t))

(defun rt-sh (dir prog &rest args)
  "Run PROG ARGS in DIR: (EXIT STDOUT STDERR)."
  (let ((default-directory (file-name-as-directory dir))
        (errf (make-temp-file "rt-err")))
    (with-temp-buffer
      (let ((code (apply #'call-process prog nil (list t errf) nil args)))
        (list code (buffer-string)
              (prog1 (with-temp-buffer (insert-file-contents errf) (buffer-string))
                (delete-file errf)))))))

(defun rt-git (dir &rest args)
  (apply #'rt-sh dir "git" "-c" "core.hooksPath=/dev/null" "-c" "user.name=Test"
         "-c" "user.email=test@example.invalid" "-c" "commit.gpgsign=false" args))

(defun rt-write (dir files)
  (dolist (f files)
    (let ((p (expand-file-name (car f) dir)))
      (make-directory (file-name-directory p) t)
      (with-temp-file p (insert (cdr f)))
      (when (string-suffix-p ".sh" (car f)) (set-file-modes p #o755)))))

(defun rt-commit (dir msg &optional day)
  (let ((process-environment
         (append (and day (list (concat "GIT_COMMITTER_DATE=" day "T12:00:00")
                                (concat "GIT_AUTHOR_DATE=" day "T12:00:00")))
                 process-environment)))
    (rt-git dir "add" "-A")
    (rt-git dir "commit" "-q" "--allow-empty" "-m" msg)))

(defun rt-repo (files &optional day)
  (let ((d (rt-tmp)))
    (rt-git d "init" "-q" "-b" "main")
    (rt-write d files)
    (rt-commit d "start" day)
    d))

(defun rt-run (dir &rest args) (apply #'rt-sh dir rt-bin args))

(defmacro rt-env (vars &rest body)
  (declare (indent 1))
  `(let ((process-environment (append ,vars process-environment))) ,@body))

(cl-defun rt-req (id &key (state "OPEN") title (level 1) needs verify verify+ aliases refs
                     (approved "2026-01-05") (created "2026-01-05") (last "2026-01-05")
                     implemented reviewed body noid)
  (concat (make-string level ?*) " " (if state (concat state " ") "") (or title (concat "Title of " id)) "\n"
          ":PROPERTIES:\n"
          (if noid "" (format ":ID:          %s\n" id))
          (if needs (format ":NEEDS:       %s\n" needs) "")
          (if aliases (format ":ALIASES:     %s\n" aliases) "")
          (if refs (format ":REFS:        %s\n" refs) "")
          (if created (format ":CREATED:     %s\n" created) "")
          (if last (format ":LAST_EDITED: %s\n" last) "")
          (if approved (format ":APPROVED:    %s\n" approved) "")
          (if implemented (format ":IMPLEMENTED: %s\n" implemented) "")
          (if reviewed (format ":REVIEWED:    %s\n" reviewed) "")
          (if verify (format ":VERIFY:      %s\n" verify) "")
          (if verify+ (format ":VERIFY+:     %s\n" verify+) "")
          ":END:\n" (or body "Body text.\n")))

(defconst rt-head "#+title: Invented requirements\n#+TODO: OPEN | DONE DROPPED\n#+LEMMAX_TESTS: ./tests.sh\n#+LEMMAX_CODE: src/\n\n")

(defun rt-tests-sh (&rest addrs)
  (concat "#!/bin/sh\nprintf '%s\\n'" (mapconcat (lambda (a) (concat " '" a "'")) addrs "") "\n"))

(defun rt-files (&rest reqs)
  (list (cons "requirements.org" (apply #'concat rt-head reqs))
        (cons "tests.sh" (rt-tests-sh "unit/a" "unit/b"))
        (cons "src/x.clj" "(ns x)\n")))

(defun rt-done (id &rest kv)
  (apply #'rt-req id (append kv (list :state "DONE" :implemented "2026-01-06" :verify "unit/a"))))

(defun rt-set (dir file content) (rt-write dir (list (cons file content))))

(defmacro rt-should-find (r re)
  `(progn (should (= 1 (nth 0 ,r))) (should (string-match-p ,re (nth 2 ,r)))))

(defmacro rt-should-clean (r)
  `(progn (should (equal "" (nth 2 ,r))) (should (= 0 (nth 0 ,r)))))

;;;; RT-1

(ert-deftest reqtrace-end-to-end ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1") (rt-done "RQ-2" :needs "RQ-1")))))
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-commit d "build it (RQ-2)")
    (rt-should-clean (rt-run d "lint"))
    (let ((tr (nth 1 (rt-run d "trace"))))
      (should (string-match-p "^RQ-1 OPEN" tr))
      (should (string-match-p "^RQ-2 DONE" tr))
      (should (string-match-p "build it (RQ-2)" tr)))
    (rt-set d "requirements.org" (concat rt-head (rt-req "RQ-1") (rt-req "RQ-1")))
    (rt-should-find (rt-run d "lint") "used twice")))

;;;; RT-2

(ert-deftest reqtrace-cli-short-help ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (dolist (args '(("-h") ("--help") ("list" "-h") ("lint" "--help") ("trace" "-h") ("next-id" "-h") ("commit-msg" "-h")))
      (let ((r (apply #'rt-run d args)))
        (should (= 0 (nth 0 r)))
        (should (string-match-p "^usage: lemmax" (nth 1 r)))
        (should (string-match-p "example: lemmax" (nth 1 r)))))
    (should-not (string-match-p "^  lint \\[" (nth 1 (rt-run d "--help"))))))

(ert-deftest reqtrace-cli-long-help ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (should (string-match-p "^Commands:" (nth 1 (rt-run d "help"))))
    (should (string-match-p "--staged" (nth 1 (rt-run d "lint" "help"))))
    (should (string-match-p "--unchecked" (nth 1 (rt-run d "list" "help"))))))

(ert-deftest reqtrace-cli-bare-call ()
  (let ((r (rt-run (rt-repo (rt-files (rt-req "RQ-1"))))))
    (should (= 0 (nth 0 r)))
    (should (string-match-p "^usage: lemmax COMMAND" (nth 1 r)))))

(ert-deftest reqtrace-cli-dashdash-help ()
  (let ((r (rt-run (rt-repo (rt-files (rt-req "RQ-1"))) "--help")))
    (should-not (string-match-p "GNU Emacs" (nth 1 r)))
    (should (string-match-p "^usage: lemmax" (nth 1 r)))))

(ert-deftest reqtrace-cli-finding-line ()
  (let ((r (rt-run (rt-repo (rt-files (rt-req "RQ-1" :noid t))) "lint" "--no-tests")))
    (should (string-match-p "^lemmax: requirements\\.org:6: -: no :ID:; add :ID:" (nth 2 r)))))

(ert-deftest reqtrace-cli-exit-codes ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (should (= 0 (nth 0 (rt-run d "lint" "--no-tests"))))
    (should (= 1 (nth 0 (rt-run d "nonsense"))))
    (rt-set d "requirements.org" (concat rt-head (rt-done "RQ-1" :approved nil)))
    (should (= 1 (nth 0 (rt-run d "lint" "--no-tests"))))))

(ert-deftest reqtrace-cli-writes-nothing ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1") (rt-req "RQ-1")))))
    (rt-run d "lint") (rt-run d "trace") (rt-run d "list") (rt-run d "next-id" "RQ")
    (should (equal "" (nth 1 (rt-git d "status" "--porcelain" "--ignored"))))))

;;;; RT-3

(ert-deftest reqtrace-files-opted-in ()
  (rt-should-find (rt-run (rt-repo (rt-files (rt-done "RQ-1" :approved nil))) "lint" "--no-tests")
                  "no :APPROVED:"))

(ert-deftest reqtrace-files-without-keyword ()
  (let* ((d (rt-repo (list (cons "requirements.org" (concat "#+TODO: OPEN | DONE\n" (rt-req "RQ-1" :approved nil))))))
         (r (rt-run d "lint")))
    (should (= 0 (nth 0 r)))
    (should (string-match-p "no requirements file here has" (nth 2 r)))))

(ert-deftest reqtrace-files-keyword-in-text ()
  (let* ((d (rt-repo (list (cons "requirements.org"
                                 (concat "Say =#+LEMMAX_TESTS: ./tests.sh= to opt in.\n\n"
                                         (rt-req "RQ-1" :approved nil))))))
         (r (rt-run d "lint")))
    (should (= 0 (nth 0 r)))
    (should-not (string-match-p "APPROVED" (nth 2 r)))))

(ert-deftest reqtrace-files-none-opted-in ()
  (let ((d (rt-repo (list (cons "notes.org" "* A note\n")))))
    (dolist (cmd '("lint" "trace"))
      (let ((r (rt-run d cmd)))
        (should (= 0 (nth 0 r)))
        (should (string-match-p "no requirements file here" (nth 2 r)))))))

;;;; RT-4

(defun rt-lint (&rest reqs) (rt-run (rt-repo (apply #'rt-files reqs)) "lint" "--no-tests"))

(ert-deftest reqtrace-lint-clean-file ()
  (rt-should-clean (rt-lint (rt-req "RQ-1") (rt-done "RQ-2" :needs "RQ-1") (rt-req "RQ-3" :state "DROPPED"))))
(ert-deftest reqtrace-lint-id-in-heading ()
  (rt-should-find (rt-lint (rt-req "RQ-1" :title "RQ-1 A title")) "starts with an id"))
(ert-deftest reqtrace-lint-id-missing ()
  (rt-should-find (rt-lint (rt-req "RQ-1" :noid t)) "no :ID:"))
(ert-deftest reqtrace-lint-id-shape ()
  (rt-should-find (rt-lint (rt-req "touch-map")) "neither a UUID v7 nor shaped"))
(ert-deftest reqtrace-lint-id-twice ()
  (rt-should-find (rt-lint (rt-req "RQ-1") (rt-req "RQ-1")) "used twice, first at requirements.org:6"))
(ert-deftest reqtrace-lint-needs-unknown ()
  (rt-should-find (rt-lint (rt-req "RQ-1" :needs "RQ-9")) "names RQ-9, which no requirement has"))
(ert-deftest reqtrace-lint-needs-cycle ()
  (rt-should-find (rt-lint (rt-req "RQ-1" :needs "RQ-2") (rt-req "RQ-2" :needs "RQ-1")) "cycle"))
(ert-deftest reqtrace-lint-unapproved ()
  (rt-should-find (rt-lint (rt-done "RQ-1" :approved nil)) "DONE with no :APPROVED:")
  (rt-should-clean (rt-lint (rt-req "RQ-1" :approved nil))))
(ert-deftest reqtrace-lint-dates-missing ()
  (let ((r (rt-lint (rt-req "RQ-1" :created nil :last nil))))
    (rt-should-find r "no :CREATED:")
    (should (string-match-p "no :LAST_EDITED:" (nth 2 r)))))
(ert-deftest reqtrace-lint-implemented-state ()
  :tags (quote (timeout-30))
  (rt-should-find (rt-lint (rt-req "RQ-1" :state "DONE" :verify "unit/a")) "DONE with no :IMPLEMENTED:")
  (rt-should-find (rt-lint (rt-req "RQ-1" :implemented "2026-01-06")) "OPEN with :IMPLEMENTED:")
  (rt-should-find (rt-lint (rt-req "RQ-1" :state "DROPPED" :implemented "2026-01-06")) "DROPPED with :IMPLEMENTED:"))
(ert-deftest reqtrace-lint-date-not-a-day ()
  (rt-should-find (rt-lint (rt-req "RQ-1" :created "2026-02-30")) "not a real day: 2026-02-30"))
(ert-deftest reqtrace-lint-done-verify-empty ()
  (rt-should-find (rt-lint (rt-req "RQ-1" :state "DONE" :implemented "2026-01-06")) "DONE with no :VERIFY:"))

;;;; RT-5

(ert-deftest reqtrace-verify-done-missing ()
  (rt-should-find (rt-run (rt-repo (rt-files (rt-done "RQ-1" :verify "unit/zzz"))) "lint")
                  "names unit/zzz, which the test command does not list"))
(ert-deftest reqtrace-verify-open-waits ()
  (rt-should-clean (rt-run (rt-repo (rt-files (rt-req "RQ-1" :verify "unit/zzz"))) "lint")))
(ert-deftest reqtrace-verify-plus-lines ()
  (rt-should-clean (rt-run (rt-repo (rt-files (rt-done "RQ-1" :verify "unit/a" :verify+ "unit/b"))) "lint"))
  (rt-should-find (rt-run (rt-repo (rt-files (rt-done "RQ-1" :verify "unit/a" :verify+ "unit/zzz"))) "lint")
                  "unit/zzz"))
(ert-deftest reqtrace-verify-quoted ()
  (let ((d (rt-repo (rt-files (rt-done "RQ-1" :verify "unit/a \"process/ids are used once\"")))))
    (rt-set d "tests.sh" (rt-tests-sh "unit/a" "process/ids are used once"))
    (rt-should-clean (rt-run d "lint"))))
(ert-deftest reqtrace-verify-command-fails ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (rt-set d "tests.sh" "#!/bin/sh\nexit 3\n")
    (rt-should-find (rt-run d "lint") "test command failed with exit 3: \\./tests\\.sh")))
(ert-deftest reqtrace-verify-command-timeout ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (rt-set d "tests.sh" "#!/bin/sh\nsleep 5\n")
    (rt-env '("LEMMAX_TEST_SECONDS=1")
      (rt-should-find (rt-run d "lint") "ran over 1 s"))))
(ert-deftest reqtrace-verify-no-tests ()
  (let ((d (rt-repo (rt-files (rt-done "RQ-1" :verify "unit/zzz")))))
    (rt-set d "tests.sh" "#!/bin/sh\nexit 3\n")
    (rt-should-clean (rt-run d "lint" "--no-tests"))))

;;;; RT-6

(defun rt-staged (before after)
  "Commit BEFORE, stage AFTER, run lint --staged on 2026-02-01."
  (let ((d (rt-repo (apply #'rt-files before))))
    (rt-set d "requirements.org" (apply #'concat rt-head after))
    (rt-git d "add" "-A")
    (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests"))))

(ert-deftest reqtrace-staged-done-text ()
  (rt-should-find (rt-staged (list (rt-done "RQ-1"))
                             (list (rt-done "RQ-1" :body "New text.\n" :last "2026-02-01")))
                  "DONE requirement's text changed; make it OPEN"))
(ert-deftest reqtrace-staged-reopened-passes ()
  (rt-should-clean (rt-staged (list (rt-done "RQ-1"))
                              (list (rt-req "RQ-1" :verify "unit/a" :body "New text.\n" :last "2026-02-01")))))
(ert-deftest reqtrace-staged-last-edited ()
  (rt-should-find (rt-staged (list (rt-req "RQ-1")) (list (rt-req "RQ-1" :body "New text.\n")))
                  "LAST_EDITED: is not today; set :LAST_EDITED: 2026-02-01"))
(ert-deftest reqtrace-staged-new-dates ()
  (rt-should-find (rt-staged (list (rt-req "RQ-1")) (list (rt-req "RQ-1") (rt-req "RQ-2")))
                  "RQ-2: a new requirement whose :CREATED:")
  (rt-should-clean (rt-staged (list (rt-req "RQ-1"))
                              (list (rt-req "RQ-1") (rt-req "RQ-2" :created "2026-02-01" :last "2026-02-01")))))
(ert-deftest reqtrace-staged-turned-done ()
  (rt-should-find (rt-staged (list (rt-req "RQ-1" :verify "unit/a")) (list (rt-done "RQ-1")))
                  "turned DONE and :IMPLEMENTED: is not today")
  (rt-should-clean (rt-staged (list (rt-req "RQ-1" :verify "unit/a")) (list (rt-done "RQ-1" :implemented "2026-02-01")))))
(ert-deftest reqtrace-staged-dates-only ()
  (rt-should-clean (rt-staged (list (rt-done "RQ-1")) (list (rt-done "RQ-1" :last "2026-01-20" :approved "2026-01-04")))))

;;;; RT-7

(defun rt-commit-msg (d msg)
  (let ((f (expand-file-name "MSG" (rt-tmp))))
    (with-temp-file f (insert msg))
    (rt-run d "commit-msg" f)))

(defun rt-code-change (&rest reqs)
  (let ((d (rt-repo (apply #'rt-files reqs))))
    (rt-set d "src/x.clj" "(ns x) ;; changed\n")
    (rt-git d "add" "-A")
    d))

(ert-deftest reqtrace-commit-code-needs-id ()
  (let ((d (rt-code-change (rt-req "RQ-1"))))
    (rt-should-find (rt-commit-msg d "change it\n") "names no requirement id; name one in the message, as (RF-3)")
    (rt-should-clean (rt-commit-msg d "change it (RQ-1)\n"))))
(ert-deftest reqtrace-commit-docs-pass ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (rt-set d "README.md" "Docs.\n")
    (rt-git d "add" "-A")
    (rt-should-clean (rt-commit-msg d "docs\n"))))
(ert-deftest reqtrace-commit-unknown-id ()
  (rt-should-find (rt-commit-msg (rt-code-change (rt-req "RQ-1")) "change (ZZ-9)\n") "names no requirement id"))
(ert-deftest reqtrace-commit-id-in-comment ()
  (rt-should-find (rt-commit-msg (rt-code-change (rt-req "RQ-1")) "change\n# RQ-1\n") "names no requirement id"))
(ert-deftest reqtrace-commit-new-id-staged ()
  (let ((d (rt-code-change (rt-req "RQ-1"))))
    (rt-set d "requirements.org" (concat rt-head (rt-req "RQ-1") (rt-req "RQ-2")))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-commit-msg d "add and build (RQ-2)\n"))))
(ert-deftest reqtrace-commit-whole-word ()
  (rt-should-find (rt-commit-msg (rt-code-change (rt-req "RQ-3")) "change (RQ-30)\n") "names no requirement id"))

;;;; RT-8

(ert-deftest reqtrace-trace-block ()
  (let ((out (nth 1 (rt-run (rt-repo (rt-files (rt-req "RQ-1"))) "trace"))))
    (should (string-match-p "^RQ-1 OPEN Title of RQ-1\n  file: requirements\\.org:6\n  parents: none\n  children: none" out))))
(ert-deftest reqtrace-trace-links ()
  (let ((out (nth 1 (rt-run (rt-repo (rt-files (rt-req "RQ-1") (rt-req "RQ-2" :needs "RQ-1"))) "trace"))))
    (should (string-match-p "^RQ-1 OPEN[^\n]*\n[^\n]*\n  parents: none\n  children: RQ-2" out))
    (should (string-match-p "^RQ-2 OPEN[^\n]*\n[^\n]*\n  parents: RQ-1" out))))
(ert-deftest reqtrace-trace-verify-status ()
  (let ((out (nth 1 (rt-run (rt-repo (rt-files (rt-req "RQ-1" :verify "unit/a unit/zzz"))) "trace"))))
    (should (string-match-p "verify: unit/a found" out))
    (should (string-match-p "verify: unit/zzz missing" out))))
(ert-deftest reqtrace-trace-commits ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-commit d "build it (RQ-1)" "2026-01-07")
    (should (string-match-p "commit: [0-9a-f]+ 2026-01-07 build it (RQ-1)" (nth 1 (rt-run d "trace"))))))
(ert-deftest reqtrace-trace-orphans ()
  (let ((out (nth 1 (rt-run (rt-repo (rt-files (rt-req "RQ-1" :verify "unit/a"))) "trace"))))
    (should (string-match-p "Orphan tests: \n  unit/b" out))))
(ert-deftest reqtrace-trace-one-id ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1") (rt-req "RQ-2")))))
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-commit d "build it (RQ-1)")
    (let ((out (nth 1 (rt-run d "trace" "RQ-1"))))
      (should (string-match-p "^RQ-1 OPEN" out))
      (should-not (string-match-p "RQ-2 OPEN" out))
      (should (string-match-p "^    src/x\\.clj" out)))))
(ert-deftest reqtrace-trace-unknown-id ()
  (rt-env (list (concat "LEMMAX_REPOS=" (rt-tmp)))
    (rt-should-find (rt-run (rt-repo (rt-files (rt-req "RQ-1"))) "trace" "ZZ-1") "unknown id ZZ-1")))

;;;; RT-9

(defun rt-suspect-repo (child-state child-extra parent-after)
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")
                              (apply (if (equal child-state "DONE") #'rt-done #'rt-req)
                                     "RQ-2" :needs "RQ-1" :implemented (and (equal child-state "DONE") "2026-01-05")
                                     child-extra))
                    "2026-01-01")))
    (rt-set d "requirements.org"
            (concat rt-head parent-after
                    (apply (if (equal child-state "DONE") #'rt-done #'rt-req)
                           "RQ-2" :needs "RQ-1" :implemented (and (equal child-state "DONE") "2026-01-05")
                           child-extra)))
    (rt-commit d "change the parent" "2026-01-09")
    (nth 1 (rt-run d "trace"))))

(ert-deftest reqtrace-suspect-parent-changed ()
  (let ((out (rt-suspect-repo "DONE" nil (rt-req "RQ-1" :body "Changed.\n" :last "2026-01-09"))))
    (should (string-match-p "suspect: parent RQ-1 changed 2026-01-09" out))
    (should (string-match-p "Suspect: \n  RQ-2: parent RQ-1 changed 2026-01-09" out))))
(ert-deftest reqtrace-suspect-reviewed-clears ()
  (should (string-match-p "Suspect: none"
                          (rt-suspect-repo "DONE" '(:reviewed "2026-01-10")
                                           (rt-req "RQ-1" :body "Changed.\n" :last "2026-01-09")))))
(ert-deftest reqtrace-suspect-dates-only ()
  (should (string-match-p "Suspect: none" (rt-suspect-repo "DONE" nil (rt-req "RQ-1" :last "2026-01-09")))))
(ert-deftest reqtrace-suspect-open-child ()
  (should (string-match-p "Suspect: none"
                          (rt-suspect-repo "OPEN" nil (rt-req "RQ-1" :body "Changed.\n" :last "2026-01-09")))))
(ert-deftest reqtrace-suspect-walk-time ()
  :tags '(timeout-180)
  (let* ((ids (number-sequence 1 150))
         (file (lambda (n) (concat rt-head (mapconcat (lambda (i) (rt-req (format "RQ-%d" i)
                                                                          :body (format "Text %d.\n" (if (= i (1+ (% n 150))) n 0))))
                                                      ids ""))))
         (d (rt-repo (rt-files) "2026-01-01")))
    (dotimes (n 155)
      (rt-set d "requirements.org" (funcall file n))
      (rt-commit d (format "rev %d" n) "2026-01-02"))
    (let* ((start (float-time)) (r (rt-run d "trace")) (took (- (float-time) start)))
      (should (= 0 (nth 0 r)))
      (should (< took 10)))))

;;;; RT-10

(defun rt-check (d stdin)
  (let ((default-directory (file-name-as-directory d)))
    (with-temp-buffer
      (insert stdin)
      (call-process-region (point-min) (point-max) "python3" t t nil
                           (expand-file-name "harness/checks/lemmax_lint.py" rt-agent1))
      (buffer-string))))

(ert-deftest reqtrace-harness-check-finding ()
  (let ((d (rt-repo (rt-files (rt-done "RQ-1" :approved nil)))))
    (should (string-match-p "^requirements\\.org:6: RQ-1: DONE with no :APPROVED:" (rt-check d "requirements.org\n")))))
(ert-deftest reqtrace-harness-check-plain-org ()
  (let ((d (rt-repo (list (cons "notes.org" (rt-req "RQ-1" :approved nil))))))
    (should (equal "" (rt-check d "notes.org\n")))))

;;;; RT-11

(defun rt-hooked (files)
  (let ((d (rt-repo files)))
    (rt-sh d "git" "config" "core.hooksPath" (expand-file-name "harness/githooks" rt-agent1))
    d))

(defun rt-hook-commit (d msg)
  (rt-sh d "git" "-c" "user.name=Test" "-c" "user.email=test@example.invalid" "commit" "-q" "-m" msg))

(ert-deftest reqtrace-global-commit-msg ()
  :tags '(timeout-30)
  (let ((d (rt-hooked (rt-files (rt-req "RQ-1")))))
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-sh d "git" "add" "-A")
    (should (= 1 (nth 0 (rt-hook-commit d "change it"))))
    (should (= 0 (nth 0 (rt-hook-commit d "change it (RQ-1)"))))))
(ert-deftest reqtrace-global-pre-commit ()
  :tags '(timeout-30)
  (let ((d (rt-hooked (rt-files (rt-req "RQ-1")))))
    (rt-set d "requirements.org" (concat rt-head (rt-req "RQ-1" :body "Changed.\n")))
    (rt-sh d "git" "add" "-A")
    (let ((r (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-hook-commit d "edit (RQ-1)"))))
      (should (= 1 (nth 0 r)))
      (should (string-match-p "LAST_EDITED: is not today" (nth 2 r))))))
(ert-deftest reqtrace-global-plain-repo-fast ()
  :tags '(timeout-30)
  (let* ((d (rt-hooked (list (cons "notes.org" "* A note\n") (cons "src/x.clj" "(ns x)\n"))))
         (marker (expand-file-name "started" (rt-tmp)))
         (stub (expand-file-name "stub.sh" (rt-tmp))))
    (with-temp-file stub (insert (format "#!/bin/sh\ntouch %s\n" marker)))
    (set-file-modes stub #o755)
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-sh d "git" "add" "-A")
    (rt-env (list (concat "LEMMAX=" stub))
      (should (= 0 (nth 0 (rt-hook-commit d "change it")))))
    (should-not (file-exists-p marker))))

;;;; RT-12

(defun rt-runner (tests-text &rest args)
  (let ((f (expand-file-name "tests.el" (rt-tmp))))
    (with-temp-file f (insert tests-text))
    (rt-env (list (concat "LEMMAX_TESTS_FILE=" f) "LEMMAX_TEST_TIMEOUT=2")
      (apply #'rt-sh rt-dir (expand-file-name "run_tests" rt-dir) args))))

(defconst rt-small-tests
  "(require 'ert)
(ert-deftest x-pass () (should t))
(ert-deftest x-fail () (should nil))
(ert-deftest x-sleep () (sleep-for 6) (should t))\n")

(ert-deftest reqtrace-runner-addresses ()
  (let ((out (nth 1 (rt-sh rt-dir (expand-file-name "run_tests" rt-dir) "--addresses"))))
    (should (string-match-p "^ert/reqtrace-runner-addresses$" out))
    (should (string-match-p "^ert/reqtrace-list-table$" out))))
(ert-deftest reqtrace-runner-only ()
  (let ((r (rt-runner rt-small-tests "--only" "ert/x-pass")))
    (should (= 0 (nth 0 r)))
    (should (equal "PASS ert/x-pass\n" (nth 1 r))))
  (should (= 1 (nth 0 (rt-runner rt-small-tests "--only" "ert/x-fail")))))
(ert-deftest reqtrace-runner-timeout ()
  :tags '(timeout-30)
  (let ((r (rt-runner rt-small-tests)))
    (should (= 1 (nth 0 r)))
    (should (string-match-p "^TIMEOUT ert/x-sleep" (nth 1 r)))
    (should (string-match-p "^PASS ert/x-pass" (nth 1 r)))
    (should (string-match-p "^FAIL ert/x-fail" (nth 1 r)))))

;;;; RT-13

(defun rt-list (d &rest args) (nth 1 (apply #'rt-run d "list" args)))

(ert-deftest reqtrace-list-table ()
  (let* ((d (rt-repo (append (rt-files (rt-done "RQ-1") (rt-req "RQ-2" :verify "unit/zzz"))
                             (list (cons "requirements/gui.org" (rt-req "gui-look"))))))
         (out (rt-list d)))
    (should (string-match-p "RQ-1 +DONE +approved found +Title of RQ-1 +requirements\\.org:6" out))
    (should (string-match-p "RQ-2 +OPEN +approved missing" out))
    (should (string-match-p "gui-look +OPEN +approved none +Title of gui-look +requirements/gui\\.org:1" out))
    (should (string-match-p "^Total: 3 requirements: 2 open, 1 done, 0 dropped" out))))
(ert-deftest reqtrace-list-groups ()
  (let ((out (rt-list (rt-repo (rt-files (rt-req "RQ-1" :state "DROPPED") (rt-done "RQ-2")
                                         (rt-req "RQ-3") (rt-req "RQ-4" :approved nil))))))
    (should (string-match-p "Waiting for approval (1)\n  RQ-4.*\nApproved and open (1)\n  RQ-3.*\nDone (1)\n  RQ-2.*\nDropped (1)\n  RQ-1" out))))
(ert-deftest reqtrace-list-filters ()
  (let ((d (rt-repo (rt-files (rt-done "RQ-1") (rt-done "RQ-2" :verify "unit/zzz") (rt-req "RQ-3")
                              (rt-req "RQ-4" :approved nil) (rt-req "AB-1")))))
    (let ((out (rt-list d "--state" "done")))
      (should (string-match-p "RQ-1" out)) (should-not (string-match-p "RQ-3" out)))
    (let ((out (rt-list d "--section" "AB")))
      (should (string-match-p "AB-1" out)) (should-not (string-match-p "RQ-" out)))
    (let ((out (rt-list d "--ready")))
      (should (string-match-p "RQ-3" out)) (should-not (string-match-p "RQ-4\\|RQ-1" out)))
    (let ((out (rt-list d "--unchecked")))
      (should (string-match-p "RQ-2" out)) (should-not (string-match-p "RQ-1 " out)))))
(ert-deftest reqtrace-list-no-id ()
  (let ((out (rt-list (rt-repo (rt-files (rt-req "RQ-1") (rt-req "x" :noid t))))))
    (should (string-match-p "(no id) +OPEN" out))
    (should (string-match-p "^No id: 1" out))))
(ert-deftest reqtrace-list-all-repos ()
  (let ((base (rt-tmp)))
    (dolist (name '("alpha" "beta"))
      (let ((d (expand-file-name name base)))
        (make-directory d)
        (rt-git d "init" "-q" "-b" "main")
        (rt-write d (rt-files (rt-req "RQ-1")))
        (rt-commit d "start")))
    (make-directory (expand-file-name "plain" base))
    (let ((out (rt-env (list (concat "LEMMAX_REPOS=" base)) (rt-list base "--all" "--no-tests"))))
      (should (string-match-p "^== alpha" out))
      (should (string-match-p "^== beta" out))
      (should (string-match-p "^Total: 2 requirements in 2 repos" out)))))
(ert-deftest reqtrace-list-json ()
  (let* ((out (rt-list (rt-repo (rt-files (rt-done "RQ-1"))) "--json"))
         (rows (json-parse-string out :object-type 'alist)))
    (should (= 1 (length rows)))
    (should (equal "RQ-1" (alist-get 'id (aref rows 0))))
    (should (equal "found" (alist-get 'check (aref rows 0))))))

;;;; RT-14

(ert-deftest reqtrace-next-id ()
  (should (equal "RQ-4\n" (nth 1 (rt-run (rt-repo (rt-files (rt-req "RQ-1") (rt-req "RQ-3"))) "next-id" "RQ")))))
(ert-deftest reqtrace-next-id-gaps ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1") (rt-req "RQ-5")))))
    (should (equal "RQ-6\n" (nth 1 (rt-run d "next-id" "RQ"))))
    (should (equal "ZZ-1\n" (nth 1 (rt-run d "next-id" "ZZ"))))))
(ert-deftest reqtrace-next-id-unknown ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (should (= 1 (nth 0 (rt-run d "next-id" "rq"))))
    (should (= 1 (nth 0 (rt-run d "next-id"))))))

;;;; RT-15

(ert-deftest reqtrace-skill-uses-reqtrace ()
  (let ((text (with-temp-buffer
                (insert-file-contents (expand-file-name "skills/add-requirement/SKILL.md" rt-agent1))
                (buffer-string))))
    (should (string-match-p "lemmax list --json" text))
    (should (string-match-p "lemmax next-id" text))))

;;; lemmax_tests.el ends here

;;;; RT-16

(ert-deftest reqtrace-project-list-many ()
  (let ((a (rt-repo (rt-files (rt-req "RQ-1"))))
        (b (rt-repo (rt-files (rt-req "AB-1") (rt-req "AB-2"))))
        (elsewhere (rt-tmp)))
    (let ((out (nth 1 (rt-run elsewhere "list" "--no-tests" "-p" a "--project" (expand-file-name "src" b)))))
      (should (string-match-p (concat "^== " (regexp-quote (file-name-nondirectory a))) out))
      (should (string-match-p (concat "^== " (regexp-quote (file-name-nondirectory b))) out))
      (should (string-match-p "^Total: 3 requirements in 2 repos" out)))))
(ert-deftest reqtrace-project-one-command ()
  (let ((a (rt-repo (rt-files (rt-req "RQ-1") (rt-req "RQ-4"))))
        (elsewhere (rt-tmp)))
    (should (equal "RQ-5\n" (nth 1 (rt-run elsewhere "next-id" "RQ" "--project" a))))
    (should (string-match-p "^RQ-1 OPEN" (nth 1 (rt-run elsewhere "trace" "-p" a))))
    (rt-should-clean (rt-run elsewhere "lint" "--no-tests" "-p" a))))
(ert-deftest reqtrace-project-errors ()
  (let ((a (rt-repo (rt-files (rt-req "RQ-1")))) (plain (rt-tmp)))
    (rt-should-find (rt-run plain "list" "-p" (expand-file-name "missing" plain)) "no such folder")
    (rt-should-find (rt-run a "list" "-p" plain) "not inside a git repo")
    (rt-should-find (rt-run a "lint" "-p" a "-p" a) "lint takes one --project")
    (rt-should-find (rt-run a "next-id" "RQ" "-p") "--project needs a folder")))

;;;; RT-19

(ert-deftest reqtrace-trace-finds-other-project ()
  (let* ((base (rt-tmp))
         (a (expand-file-name "alpha" base))
         (plain (rt-tmp)))
    (make-directory a)
    (rt-git a "init" "-q" "-b" "main")
    (rt-write a (rt-files (rt-req "RQ-1")))
    (rt-commit a "start")
    (rt-env (list (concat "LEMMAX_REPOS=" base))
      (let ((r (rt-run plain "trace" "RQ-1")))
        (should (= 0 (nth 0 r)))
        (should (string-match-p "^project: .*alpha\nRQ-1 OPEN Title of RQ-1" (nth 1 r))))
      (let ((other (rt-repo (rt-files (rt-req "AB-1")))))
        (should (string-match-p "^project: .*alpha" (nth 1 (rt-run other "trace" "RQ-1"))))))))
(ert-deftest reqtrace-trace-unknown-anywhere ()
  (let ((base (rt-tmp)))
    (rt-env (list (concat "LEMMAX_REPOS=" base))
      (rt-should-find (rt-run (rt-tmp) "trace" "ZZ-9") "unknown id ZZ-9, here or in any project under"))))

;;;; 01a1fe0c-9c5c-7057-8edc-bc68ccfa0490

(ert-deftest reqtrace-lint-id-uuid7 ()
  :tags '(timeout-30)
  (rt-should-clean (rt-lint (rt-req "01a1fe0c-9c5c-7057-8edc-bc68ccfa0490") (rt-req "RQ-1")))
  (rt-should-find (rt-lint (rt-req "01a1fe0c-9c5c-4057-8edc-bc68ccfa0490")) "neither a UUID v7")
  (rt-should-find (rt-lint (rt-req "01A1FE0C-9C5C-7057-8EDC-BC68CCFA0490")) "neither a UUID v7"))

;;;; RT-17

(ert-deftest reqtrace-trace-one-id-text ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1" :body "First line.\n- a point\n") (rt-req "RQ-2")))))
    (let ((out (nth 1 (rt-run d "trace" "RQ-1"))))
      (should (string-match-p "  text:\n    First line\\.\n    - a point" out))
      (should-not (string-match-p ":PROPERTIES:\\|:ID:" out)))
    (should-not (string-match-p "text:" (nth 1 (rt-run d "trace"))))))

;;;; 01a1ff25-116d-73f1-a45e-dd77e482a983

(ert-deftest lemmax-name-and-place ()
  (should (string-match-p "requirements/scripts/lemmax/\\'" rt-dir))
  (let ((r (rt-sh rt-dir rt-bin "--help")))
    (should (= 0 (nth 0 r)))
    (should (string-match-p "^usage: lemmax COMMAND" (nth 1 r))))
  (should-not (file-exists-p (expand-file-name "harness/reqtrace" rt-agent1)))
  (dolist (f '("harness/githooks/pre-commit" "harness/githooks/commit-msg" "harness/self_check"
               "harness/checks/lemmax_lint.py" "skills/add-requirement/SKILL.md"))
    (let ((text (with-temp-buffer (insert-file-contents (expand-file-name f rt-agent1)) (buffer-string))))
      (should (string-match-p "lemmax" text))
      (should-not (string-match-p "reqtrace" text)))))

(ert-deftest lemmax-reads-old-keyword-in-history ()
  :tags '(timeout-30)
  (let ((d (rt-repo (list (cons "requirements.org"
                                (concat "#+TODO: OPEN | DONE DROPPED\n#+REQTRACE_TESTS: ./tests.sh\n\n" (rt-done "RQ-1")))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))))))
    (rt-set d "requirements.org" (concat "#+TODO: OPEN | DONE DROPPED\n#+LEMMAX_TESTS: ./tests.sh\n\n" (rt-done "RQ-1")))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests")))))

(ert-deftest reqtrace-new-id ()
  (let* ((d (rt-repo (rt-files (rt-req "RQ-1"))))
         (a (rt-run d "new-id")) (b (rt-run d "new-id"))
         (re "\\`[0-9a-f]\\{8\\}-[0-9a-f]\\{4\\}-7[0-9a-f]\\{3\\}-[89ab][0-9a-f]\\{3\\}-[0-9a-f]\\{12\\}\n\\'"))
    (should (= 0 (nth 0 a)))
    (should (string-match-p re (nth 1 a)))
    (should (string-match-p re (nth 1 b)))
    (should-not (equal (nth 1 a) (nth 1 b)))
    (should-not (string> (substring (nth 1 a) 0 13) (substring (nth 1 b) 0 13)))
    (should (= 1 (nth 0 (rt-run d "new-id" "extra"))))
    (should (string-match-p "^usage: lemmax new-id" (nth 1 (rt-run d "new-id" "--help"))))))

;;;; 01a20014-e361-7827-b2a8-d3b2ded3e0b1

(defun rt-marked (code &rest reqs)
  "A repo whose src/x.clj is CODE, with REQS."
  (rt-repo (append (apply #'rt-files reqs) (list (cons "src/x.clj" code)))))

(ert-deftest lemmax-marker-found ()
  :tags '(timeout-30)
  (let ((d (rt-marked "(ns x)\n;; lemma: RQ-1 RQ-2, and more words\n(defn f [])\n"
                      (rt-req "RQ-1") (rt-req "RQ-2"))))
    (should (string-match-p "  code: src/x\\.clj:2" (nth 1 (rt-run d "trace" "RQ-1"))))
    (should (string-match-p "  code: src/x\\.clj:2" (nth 1 (rt-run d "trace" "RQ-2"))))
    (should (string-match-p "RQ-1 .*code:1" (nth 1 (rt-run d "list" "--no-tests"))))
    (rt-should-clean (rt-run d "lint" "--no-tests"))))

(ert-deftest lemmax-marker-unknown-id ()
  (rt-should-find (rt-run (rt-marked "# lemma: ZZ-9\n" (rt-req "RQ-1")) "lint" "--no-tests")
                  "src/x\\.clj:1: ZZ-9: the marker names an id no lemma has"))

(ert-deftest lemmax-marker-dropped ()
  (rt-should-find (rt-run (rt-marked "// lemma: RQ-1\n" (rt-req "RQ-1" :state "DROPPED")) "lint" "--no-tests")
                  "RQ-1: the marker names a DROPPED lemma"))

(ert-deftest lemmax-done-needs-marker ()
  :tags '(timeout-30)
  (rt-should-find (rt-run (rt-repo (rt-files (rt-done "RQ-1" :implemented "2026-11-22"))) "lint" "--no-tests")
                  "RQ-1: DONE with no code marker")
  (let ((d (rt-repo (rt-files (rt-done "RQ-1")))))
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    (should (string-match-p "RQ-1" (nth 1 (rt-run d "list" "--no-tests" "--unmarked"))))))

(ert-deftest lemmax-marker-tests-apart ()
  :tags '(timeout-30)
  (let ((d (rt-repo (append (rt-files (rt-done "RQ-1" :implemented "2026-11-22"))
                            (list (cons "test/x_test.clj" ";; lemma: RQ-1\n"))))))
    (should (string-match-p "  test: test/x_test\\.clj:1" (nth 1 (rt-run d "trace" "RQ-1"))))
    (rt-should-find (rt-run d "lint" "--no-tests") "RQ-1: DONE with no code marker"))
  (let ((d (rt-repo (list (cons "requirements.org"
                                (concat rt-head "#+LEMMAX_TEST_PATHS: checks/\n\n" (rt-req "RQ-1")))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))
                          (cons "checks/x.sh" "# lemma: RQ-1\n")))))
    (should (string-match-p "  test: checks/x\\.sh:1" (nth 1 (rt-run d "trace" "RQ-1"))))))

(ert-deftest lemmax-marker-full-id ()
  (let ((d (rt-marked "# lemma: 01a1ff25-116d\n# a line that says lemma: RQ-1 mid-way is no marker\n"
                      (rt-req "01a1ff25-116d-73f1-a45e-dd77e482a983"))))
    (let ((r (rt-run d "lint" "--no-tests")))
      (rt-should-find r "src/x\\.clj:1: 01a1ff25-116d: the marker names an id no lemma has")
      (should-not (string-match-p "src/x\\.clj:2" (nth 2 r))))))

;;;; 01a2002a-bf93-7475-94c3-d083c65a87d6

(ert-deftest lemmax-heading-id-not-text ()
  :tags '(timeout-30)
  (rt-should-clean (rt-staged (list (rt-done "RQ-1" :title "RQ-1 The look"))
                              (list (rt-done "RQ-1" :title "The look"))))
  (rt-should-find (rt-staged (list (rt-done "RQ-1" :title "RQ-1 The look"))
                             (list (rt-done "RQ-1" :title "The new look")))
                  "DONE requirement's text changed")
  (rt-should-clean (rt-staged (list (rt-done "RQ-1" :body "See [[*RQ-2 The base][RQ-2]] and [[file:x.org::*RQ-2 The base][it]].\n"))
                              (list (rt-done "RQ-1" :body "See [[*The base][RQ-2]] and [[file:x.org::*The base][it]].\n"))))
  (let ((d (rt-repo (rt-files (rt-req "RQ-1" :title "RQ-1 The parent") (rt-done "RQ-2" :needs "RQ-1" :implemented "2026-01-05"))
                    "2026-01-01")))
    (rt-set d "requirements.org" (concat rt-head (rt-req "RQ-1" :title "The parent")
                                         (rt-done "RQ-2" :needs "RQ-1" :implemented "2026-01-05")))
    (rt-commit d "ids leave the headings" "2026-01-09")
    (should (string-match-p "Suspect: none" (nth 1 (rt-run d "trace"))))))

;;;; 01a2002d-fb3b-71e3-ac96-5e1dbba8226c

(ert-deftest lemmax-opt-in-compares-head ()
  :tags '(timeout-30)
  (let ((d (rt-repo (list (cons "requirements.org" (concat "#+TODO: OPEN | DONE DROPPED\n\n" (rt-done "RQ-1")))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))))))
    (rt-set d "requirements.org" (concat rt-head (rt-done "RQ-1")))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests")))))

(ert-deftest lemmax-markers-in-other-repo ()
  :tags '(timeout-30)
  (let* ((base (rt-tmp))
         (book (expand-file-name "book" base)) (code (expand-file-name "code" base)))
    (dolist (d (list book code)) (make-directory d) (rt-git d "init" "-q" "-b" "main"))
    (rt-write book (list (cons "requirements.org" (concat rt-head "#+LEMMAX_MARKERS_IN: ../code\n\n"
                                                          (rt-done "RQ-1" :implemented "2026-11-22")))
                         (cons "tests.sh" (rt-tests-sh "unit/a"))))
    (rt-write code (list (cons "src/x.clj" ";; lemma: RQ-1\n")))
    (rt-commit book "start") (rt-commit code "start")
    (should (string-match-p "  code: \\.\\./code/src/x\\.clj:1" (nth 1 (rt-run book "trace" "RQ-1"))))
    (rt-should-clean (rt-run book "lint" "--no-tests"))))

;;;; 01a202b0-1d09-75f3-99dc-677a4b2ec0be: settings in lemmax/config.eld

(defconst rt-plain-head "#+title: One lemma\n\n")

(defun rt-config (&rest entries)
  (cons "lemmax/config.eld" (format ";; lemmax config\n(:folders %S)\n" entries)))

(ert-deftest lemmax-config-folder-settings ()
  :tags '(timeout-30)
  (let ((d (rt-repo (list (rt-config '("reqs/" :tests "./tests.sh" :code ("src/")))
                          (cons "reqs/RQ-1.org" (concat rt-plain-head (rt-done "RQ-1")))
                          (cons "reqs/RQ-2.org" (concat rt-plain-head (rt-req "RQ-2" :needs "RQ-1")))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))
                          (cons "src/x.clj" "(ns x)\n")))))
    (rt-should-clean (rt-run d "lint"))
    (let ((tr (nth 1 (rt-run d "trace"))))
      (should (string-match-p "^RQ-1 DONE" tr))
      (should (string-match-p "^RQ-2 OPEN" tr)))
    (should (string-match-p "Total: 2 requirements" (nth 1 (rt-run d "list"))))
    (rt-set d "reqs/RQ-3.org" (concat rt-plain-head (rt-req "RQ-1")))
    (rt-git d "add" "-A")
    (rt-should-find (rt-run d "lint" "--no-tests") "used twice")))

(ert-deftest lemmax-config-header-wins ()
  :tags '(timeout-30)
  (let ((d (rt-repo (list (rt-config '("" :tests "./bad.sh"))
                          (cons "requirements.org" (concat rt-head (rt-done "RQ-1")))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))
                          (cons "bad.sh" "#!/bin/sh\nexit 3\n")))))
    (set-file-modes (expand-file-name "bad.sh" d) #o755)
    (rt-should-clean (rt-run d "lint"))))

(ert-deftest lemmax-config-longest-folder ()
  :tags '(timeout-30)
  (let ((d (rt-repo (list (rt-config '("reqs/" :tests "./bad.sh")
                                     '("reqs/deep/" :tests "./tests.sh"))
                          (cons "reqs/deep/RQ-1.org" (concat rt-plain-head (rt-done "RQ-1")))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))
                          (cons "bad.sh" "#!/bin/sh\nexit 3\n")))))
    (rt-should-clean (rt-run d "lint"))))

(ert-deftest lemmax-config-staged ()
  :tags '(timeout-30)
  (let ((d (rt-repo (list (cons "reqs/RQ-1.org" (concat rt-plain-head (rt-done "RQ-1")))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))))))
    ;; The commit that adds the config sees RQ-1 as old, as with a header.
    (rt-write d (list (rt-config '("reqs/" :tests "./tests.sh"))))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests")))
    (rt-commit d "config")
    ;; A staged text change of a DONE lemma is refused through the config.
    (rt-set d "reqs/RQ-1.org" (concat rt-plain-head (rt-done "RQ-1" :body "New text.\n")))
    (rt-git d "add" "-A")
    (rt-should-find (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests"))
                    "DONE requirement's text changed")))

(ert-deftest lemmax-config-never-evaluated ()
  :tags '(timeout-30)
  (let ((d (rt-repo (list (cons "lemmax/config.eld" "(:folders #.(make-directory \"pwned\"))\n")
                          (cons "reqs/RQ-1.org" (concat rt-plain-head (rt-req "RQ-1")))))))
    (rt-should-find (rt-run d "lint" "--no-tests") "lemmax/config.eld:1: -: it does not read")
    (rt-run d "list")
    (should-not (file-exists-p (expand-file-name "pwned" d)))))

(ert-deftest lemmax-config-findings ()
  :tags '(timeout-30)
  (let ((d (rt-repo (list (cons "lemmax/config.eld"
                                "(:folders ((\"reqs/\" :tests \"./tests.sh\" :colour (\"x\"))\n (\"gone/\" :tests \"./tests.sh\")) :extra 1)\n")
                          (cons "reqs/RQ-1.org" (concat rt-plain-head (rt-req "RQ-1")))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))))))
    (let ((r (rt-run d "lint" "--no-tests")))
      (rt-should-find r "unknown key :extra")
      (should (string-match-p "reqs/: unknown key :colour" (nth 2 r)))
      (should (string-match-p "the folder gone/ holds no tracked file" (nth 2 r))))
    (rt-set d "lemmax/config.eld" "(:folders (\"reqs/\" :tests \"x\")")
    (rt-should-find (rt-run d "lint" "--no-tests") "does not read")))

;;;; 01a202bc-49e2-7dba-94f5-0c0952fc91f0: id: links

(ert-deftest lemmax-id-link-unknown ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1" :body "See [[id:RQ-9][nine]]; as text, =[[id:ID]]=.\n")))))
    (let ((r (rt-run d "lint" "--no-tests")))
      (rt-should-find r "requirements.org:[0-9]+: RQ-9: the id: link names an id no lemma has")
      (should-not (string-match-p ": ID: " (nth 2 r))))))

(ert-deftest lemmax-id-link-dropped ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1" :body "See [[id:RQ-2]].\n") (rt-req "RQ-2" :state "DROPPED")))))
    (rt-should-find (rt-run d "lint" "--no-tests") "RQ-2: the id: link names a DROPPED lemma")))

(ert-deftest lemmax-id-link-ok ()
  :tags '(timeout-30)
  (let ((d (rt-repo (rt-files (rt-done "RQ-1" :body "See [[id:RQ-2][two]].\n") (rt-req "RQ-2")))))
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    ;; Only the shown text of the link changed: not a text change of a DONE lemma.
    (rt-set d "requirements.org" (concat rt-head (rt-done "RQ-1" :body "See [[id:RQ-2][the second]].\n") (rt-req "RQ-2")))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests")))))

;;;; 01a202bc-4a88-7993-a717-e8022392b801: a file is one lemma

(cl-defun rt-file-lemma (id &key (state "OPEN") (title (concat "Title of " id)) needs verify implemented
                            (approved "2026-01-05") (created "2026-01-05") (last "2026-01-05") (body "Body text.\n"))
  (concat ":PROPERTIES:\n" (format ":ID:          %s\n" id)
          (if state (format ":STATE:       %s\n" state) "")
          (if needs (format ":NEEDS:       %s\n" needs) "")
          (if created (format ":CREATED:     %s\n" created) "")
          (if last (format ":LAST_EDITED: %s\n" last) "")
          (if approved (format ":APPROVED:    %s\n" approved) "")
          (if implemented (format ":IMPLEMENTED: %s\n" implemented) "")
          (if verify (format ":VERIFY:      %s\n" verify) "")
          ":END:\n#+title: " title "\n\n" body))

(defun rt-file-lemma-repo (&rest files)
  (rt-repo (append (list (rt-config '("reqs/" :tests "./tests.sh" :code ("src/")))
                         (cons "tests.sh" (rt-tests-sh "unit/a"))
                         (cons "src/x.clj" "(ns x)\n"))
                   files)))

(ert-deftest lemmax-file-lemma-read ()
  :tags '(timeout-30)
  (let ((d (rt-file-lemma-repo
            (cons "reqs/one.org" (rt-file-lemma "RQ-1" :title "The whole file" :body "Body.\n* A heading\nMore body.\n"))
            (cons "reqs/two.org" (rt-file-lemma "RQ-2" :needs "RQ-1")))))
    (let ((json (json-read-from-string (nth 1 (rt-run d "list" "--json" "--no-tests")))))
      (should (= 2 (length json)))
      (let ((one (cl-find "RQ-1" json :key (lambda (r) (alist-get 'id r)) :test #'equal)))
        (should (equal "The whole file" (alist-get 'title one)))
        (should (equal "OPEN" (alist-get 'state one)))
        (should (equal "reqs/one.org" (alist-get 'file one)))))
    (let ((tr (nth 1 (rt-run d "trace" "RQ-1"))))
      (should (string-match-p "^RQ-1 OPEN The whole file" tr))
      (should (string-match-p "children: RQ-2" tr))
      (should (string-match-p "More body\\." tr)))))

(ert-deftest lemmax-file-lemma-lint ()
  :tags '(timeout-30)
  (let ((d (rt-file-lemma-repo
            (cons "reqs/one.org" (rt-file-lemma "RQ-1" :state "DONE" :implemented "2026-01-06" :verify "unit/a")))))
    (rt-should-clean (rt-run d "lint"))
    (rt-set d "reqs/one.org" (rt-file-lemma "RQ-1" :state "DONE" :verify "unit/zz"))
    (let ((r (rt-run d "lint")))
      (rt-should-find r "reqs/one.org:1: RQ-1: DONE with no :IMPLEMENTED:")
      (should (string-match-p "names unit/zz, which the test command does not list" (nth 2 r))))))

(ert-deftest lemmax-file-lemma-staged ()
  :tags '(timeout-30)
  (let ((d (rt-file-lemma-repo
            (cons "reqs/one.org" (rt-file-lemma "RQ-1" :state "DONE" :implemented "2026-01-06" :verify "unit/a")))))
    ;; Its state alone is no text change; its body is.
    (rt-set d "reqs/one.org" (rt-file-lemma "RQ-1" :state "DONE" :implemented "2026-01-06" :verify "unit/a" :body "New.\n"))
    (rt-git d "add" "-A")
    (rt-should-find (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests"))
                    "DONE requirement's text changed")
    (rt-set d "reqs/one.org" (rt-file-lemma "RQ-1" :state "DROPPED" :verify "unit/a"))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests")))))

;;;; 01a202bc-4bf0-7fd3-a92c-204eb9fa96f0: :ALIASES:

(ert-deftest lemmax-alias-resolves ()
  :tags '(timeout-30)
  (let ((d (rt-repo (rt-files (rt-done "RQ-10" :aliases "RQ-1" :implemented "2026-11-22")
                              (rt-req "RQ-2" :needs "RQ-1" :body "See [[id:RQ-1]].\n")))))
    (rt-set d "src/x.clj" ";; lemma: RQ-1\n")
    (rt-commit d "code (RQ-1)")
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    (let ((tr (nth 1 (rt-run d "trace" "RQ-1"))))
      (should (string-match-p "^RQ-10 DONE" tr))
      (should (string-match-p "children: RQ-2" tr))
      (should (string-match-p "code: src/x\\.clj:1" tr)))
    (rt-set d "src/x.clj" "(ns x) ;; 3\n")
    (rt-git d "add" "-A")
    (let ((msg (make-temp-file "rt-msg" nil nil "fix it (RQ-1)\n")))
      (rt-should-clean (rt-run d "commit-msg" msg)))))

(ert-deftest lemmax-alias-twice ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1" :aliases "RQ-9") (rt-req "RQ-2" :aliases "RQ-9 RQ-1")))))
    (let ((r (rt-run d "lint" "--no-tests")))
      (rt-should-find r "RQ-2: the alias RQ-9 is also an alias of RQ-1")
      (should (string-match-p "RQ-2: the alias RQ-1 is also the :ID: at" (nth 2 r))))))

;;;; 01a202bc-4cc4-753e-8d51-12d8327dfd9c: :REFS:

(ert-deftest lemmax-refs-shown ()
  :tags '(timeout-30)
  (let ((d (rt-repo (rt-files (rt-req "RQ-1" :refs "https://example.invalid/issues/4 http://example.invalid/spec")))))
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    (should (string-match-p "  refs: https://example.invalid/issues/4 http://example.invalid/spec"
                            (nth 1 (rt-run d "trace" "RQ-1"))))
    (let ((row (aref (json-read-from-string (nth 1 (rt-run d "list" "--json" "--no-tests"))) 0)))
      (should (equal ["https://example.invalid/issues/4" "http://example.invalid/spec"] (alist-get 'refs row))))
    (rt-set d "requirements.org" (concat rt-head (rt-req "RQ-1" :refs "issue-4")))
    (rt-should-find (rt-run d "lint" "--no-tests") "RQ-1: :REFS: names issue-4, which is not an http(s) URL")))

;;;; 01a202bc-4b52-74e6-9d78-591320edcb4f: backlinks

(ert-deftest lemmax-trace-backlinks ()
  :tags '(timeout-30)
  (let ((d (rt-repo (append (rt-files (rt-req "RQ-1" :body "Self [[id:RQ-1]].\n")
                                       (rt-req "RQ-2" :body "Needs [[id:RQ-1][one]].\n")
                                       "* Notes\nAlso [[id:RQ-1]].\n")
                            (list (cons "notes/talk.org" "* Talk\nAbout [[id:RQ-1]] and =[[id:RQ-1]]=.\n"))))))
    (let ((tr (nth 1 (rt-run d "trace" "RQ-1"))))
      (should (string-match-p "  linked from: RQ-2 requirements\\.org:[0-9]+" tr))
      (should (string-match-p "  linked from: requirements\\.org:[0-9]+$" (replace-regexp-in-string "RQ-2 " "" tr)))
      (should (string-match-p "  linked from: notes/talk\\.org:2" tr))
      (should (= 3 (cl-count-if (lambda (l) (string-prefix-p "  linked from:" l)) (split-string tr "\n")))))
    (should (string-match-p "  linked from: none" (nth 1 (rt-run d "trace" "RQ-2"))))
    (let* ((rows (json-read-from-string (nth 1 (rt-run d "list" "--json" "--no-tests"))))
           (one (cl-find "RQ-1" rows :key (lambda (r) (alist-get 'id r)) :test #'equal)))
      (should (= 3 (length (alist-get 'linked_from one))))
      (should (cl-find "RQ-2" (alist-get 'linked_from one) :key (lambda (b) (alist-get 'id b)) :test #'equal)))))

;;;; 01a202bc-4d72-7f9e-8e2d-6f8ae9b27ed5: list --unlinked

(ert-deftest lemmax-unlinked-mentions ()
  :tags '(timeout-30)
  (let ((d (rt-repo (append (rt-files (rt-req "RQ-1" :aliases "OLD-1" :title "First")
                                       (rt-req "RQ-2" :title "Second" :needs "RQ-1" :body "Builds on RQ-1, see [[id:RQ-1][it]]; not RQ-12.\n"))
                            (list (cons "notes/n.org" "OLD-1 came first.\n[[id:RQ-2]]\n"))))))
    (let* ((r (rt-run d "list" "--unlinked")) (out (nth 1 r)))
      (should (= 0 (nth 0 r)))
      (should (string-match-p "^requirements\\.org:[0-9]+: RQ-1$" out))
      (should (string-match-p "^notes/n\\.org:1: OLD-1$" out))
      (should (= 2 (length (split-string out "\n" t))))
      ;; Never a lint finding.
      (rt-should-clean (rt-run d "lint" "--no-tests")))))

;;;; 01a202bc-4e0c-745b-9f61-980ada0f93e5: trace --dot

(ert-deftest lemmax-trace-dot ()
  :tags '(timeout-30)
  (let ((d (rt-repo (rt-files (rt-done "RQ-1" :title "Say \"hi\"")
                              (rt-req "RQ-2" :needs "RQ-1" :body "See [[id:RQ-1]] and [[id:RQ-1][again]].\n")
                              (rt-req "RQ-3" :state "DROPPED")))))
    (let* ((r (rt-run d "trace" "--dot")) (out (nth 1 r)))
      (should (= 0 (nth 0 r)))
      (should (string-prefix-p "digraph lemmax {" out))
      (should (string-match-p "\"RQ-1\" \\[label=\"RQ-1\\\\nSay \\\\\"hi\\\\\"\" fillcolor=palegreen\\];" out))
      (should (string-match-p "\"RQ-2\" .*fillcolor=lightyellow" out))
      (should (string-match-p "\"RQ-3\" .*fillcolor=lightgray" out))
      (should (string-match-p "^  \"RQ-2\" -> \"RQ-1\";$" out))
      (should (= 1 (cl-count-if (lambda (l) (string-match-p "\\[style=dashed\\]" l)) (split-string out "\n"))))
      (should (string-suffix-p "}\n" out)))))

;;;; 01a202f3-8216-7a1e-a34c-80c99d7bbf02: a moved lemma keeps its history

(ert-deftest lemmax-move-lemma-file ()
  :tags '(timeout-30)
  (let ((d (rt-repo (rt-files (rt-done "RQ-1")))))
    (make-directory (expand-file-name "reqs" d))
    (rt-git d "mv" "requirements.org" "reqs/moved.org")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests")))))

(ert-deftest lemmax-move-lemma-between-files ()
  :tags '(timeout-30)
  (let ((d (rt-repo (append (rt-files (rt-done "RQ-1") (rt-done "RQ-2"))
                            (list (rt-config '("reqs/" :tests "./tests.sh")))))))
    ;; RQ-2 leaves the shared file for a file of its own, as a file lemma.
    (rt-set d "requirements.org" (concat rt-head (rt-done "RQ-1")))
    (rt-set d "reqs/RQ-2.org" (concat ":PROPERTIES:\n:ID: RQ-2\n:STATE: DONE\n:CREATED: 2026-01-05\n:LAST_EDITED: 2026-01-05\n:APPROVED: 2026-01-05\n:IMPLEMENTED: 2026-01-06\n:VERIFY: unit/a\n:END:\n#+title: Title of RQ-2\n\nBody text.\n"))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests")))))
