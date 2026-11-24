;;; lemmax_tests.el --- lemmax's own tests (RT-12)  -*- lexical-binding: t; -*-

;; Each test builds an invented repo under ~/tmp and runs the real launcher.
;; Commits in test repos skip every hook. Run: lemmax/run_tests
;; lemma: RT-12

(require 'ert)
(require 'cl-lib)
(require 'subr-x)
(require 'json)

(defconst rt-dir (file-name-directory (or load-file-name buffer-file-name)))
(defconst rt-bin (expand-file-name "lmx" rt-dir))
(defconst rt-agent1 (file-name-as-directory (expand-file-name ".." rt-dir)))

;;;; Helpers

;; lemma: 01a20336-c75e-78ac-bf5e-7a72262f73e6
(defvar rt-made nil "The folders this Emacs's tests made, deleted when it exits.")

(defun rt-tmp ()
  "A new folder under $TMPDIR, else /tmp; deleted when this Emacs exits,
passed or failed, unless LEMMAX_KEEP_TMP=1."
  (let ((d (make-temp-file (expand-file-name "lemmax-test-" (or (getenv "TMPDIR") "/tmp")) t)))
    (push d rt-made)
    d))

(add-hook 'kill-emacs-hook
          (lambda ()
            (unless (equal (getenv "LEMMAX_KEEP_TMP") "1")
              (dolist (d rt-made) (ignore-errors (delete-directory d t))))))

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

;; lemma: 01a20930-0aba-7005-8442-d1dc3269c487
(defconst rt-theory "theories/t/" "Where a test repo keeps its theory: every repo keeps it in theories/.")

(defun rt-p (path)
  "PATH in a test repo: an .org file, and a picture, PDF, video or .md file
it may link, goes under theories/t/, as every repo keeps its theory there;
code, scripts, a path already under theories/ and a path written ./PATH,
a file a test keeps outside theories/ on purpose, stay."
  (if (and (string-match-p "\\.\\(?:org\\|setup\\|png\\|svg\\|gif\\|pdf\\|mp4\\|md\\|jpg\\)\\'" path)
           (not (string-prefix-p "theories/" path)) (not (string-match-p "\\`\\.\\.?/" path)))
      (concat rt-theory path)
    path))

(defun rt-write (dir files)
  (dolist (f files)
    (let ((p (expand-file-name (rt-p (car f)) dir)))
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

;; lemma: 01a203c1-983f-77e1-a367-92eb7cba2954
(defun rt-run-proc (dir &rest args)
  "Run the real launcher in a process, for the CLI wrapper and the hooks."
  (apply #'rt-sh dir rt-bin args))

(defun rt-run (dir &rest args)
  "Run lemmax in this Emacs, in DIR: (EXIT STDOUT STDERR), as the launcher would.
lemmax's state is reset first; kill-emacs is caught; message goes to stderr."
  (rt-load)
  (setq args (mapcar (lambda (a) (if (and (string-suffix-p ".org" a) (not (string-match-p "\\`\\.\\.?/" a))) (rt-p a) a)) args))
  (setq lemmax--findings 0 lemmax--run-tests nil lemmax--json-findings nil lemmax--json-mode nil
        lemmax--marks nil lemmax--links nil lemmax--trace-tags nil lemmax--migrate-titles nil
        lemmax--projects nil lemmax--cwd nil)
  (dolist (h (list lemmax--tests-cache lemmax--entry-cache lemmax--files-cache)) (clrhash h))
  (let* ((out (generate-new-buffer " *rt-out*")) (err (generate-new-buffer " *rt-err*"))
         (buffers (buffer-list))
         (default-directory (file-name-as-directory (expand-file-name dir)))
         (code
          (catch 'rt-exit
            (cl-letf (((symbol-function 'kill-emacs) (lambda (&optional c) (throw 'rt-exit (if (integerp c) c 0))))
                      ((symbol-function 'message)
                       (lambda (fmt &rest margs)
                         (when (and fmt (not inhibit-message))
                           (with-current-buffer err (insert (apply #'format fmt margs) "\n")))
                         (and fmt (apply #'format fmt margs)))))
              (let ((standard-output out) (case-fold-search nil))
                (condition-case e
                    (progn (lemmax-main (copy-sequence args)) 0)
                  (error (with-current-buffer err (insert (format "lmx: %s\n" (error-message-string e)))) 1)))))))
    ;; Buffers lemmax opened (archive) are not left for the next call.
    (dolist (b (buffer-list))
      (unless (or (memq b buffers) (eq b out) (eq b err))
        (with-current-buffer b (set-buffer-modified-p nil))
        (kill-buffer b)))
    (prog1 (list code (with-current-buffer out (buffer-string)) (with-current-buffer err (buffer-string)))
      (kill-buffer out) (kill-buffer err))))

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
  (list (cons "theory.org" (apply #'concat rt-head reqs))
        (cons "tests.sh" (rt-tests-sh "unit/a" "unit/b"))
        (cons "src/x.clj" "(ns x)\n")))

(defun rt-done (id &rest kv)
  (apply #'rt-req id (append kv (list :state "DONE" :implemented "2026-01-06" :verify "unit/a"))))

(defun rt-set (dir file content) (rt-write dir (list (cons file content))))

(defmacro rt-should-find (r re)
  `(progn (should (= 1 (nth 0 ,r))) (should (string-match-p ,re (nth 2 ,r)))))

(defun rt-quiet (err)
  "ERR without the warnings that a finished sample project has no bible or
manual (01a20d28-cb41-760a-a477-e1704807a2a8): most samples are finished."
  (replace-regexp-in-string "^lmx: [^\n]*: warning: project [^ ]+ is finished and has no \\(?:bible\\|manual\\);[^\n]*\n" "" (or err "")))

(defmacro rt-should-clean (r)
  `(progn (should (equal "" (rt-quiet (nth 2 ,r)))) (should (= 0 (nth 0 ,r)))))

;;;; RT-1

(ert-deftest lemmax-end-to-end ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1") (rt-done "RQ-2" :needs "RQ-1")))))
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-commit d "build it (RQ-2)")
    (rt-should-clean (rt-run d "lint"))
    (let ((tr (nth 1 (rt-run d "trace"))))
      (should (string-match-p "^RQ-1 OPEN" tr))
      (should (string-match-p "^RQ-2 DONE" tr))
      (should (string-match-p "build it (RQ-2)" tr)))
    (rt-set d "theory.org" (concat rt-head (rt-req "RQ-1") (rt-req "RQ-1")))
    (rt-should-find (rt-run d "lint") "used twice")))

;;;; RT-2

(ert-deftest lemmax-cli-short-help ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (dolist (args '(("-h") ("--help") ("list" "-h") ("lint" "--help") ("trace" "-h") ("next-id" "-h") ("commit-msg" "-h")))
      ;; The real launcher, in a process: the CLI wrapper is part of what this shows.
      (let ((r (apply #'rt-run-proc d args)))
        (should (= 0 (nth 0 r)))
        (should (string-match-p "^usage: lmx" (nth 1 r)))
        (should (string-match-p "example: lmx" (nth 1 r)))))
    (should-not (string-match-p "^  lint \\[" (nth 1 (rt-run d "--help"))))))

(ert-deftest lemmax-cli-long-help ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (should (string-match-p "^Commands:" (nth 1 (rt-run d "help"))))
    (should (string-match-p "--staged" (nth 1 (rt-run d "lint" "help"))))
    (should (string-match-p "--unchecked" (nth 1 (rt-run d "list" "help"))))))

(ert-deftest lemmax-cli-bare-call ()
  (let ((r (rt-run (rt-repo (rt-files (rt-req "RQ-1"))))))
    (should (= 0 (nth 0 r)))
    (should (string-match-p "^usage: lmx COMMAND" (nth 1 r)))))

(ert-deftest lemmax-cli-dashdash-help ()
  (let ((r (rt-run (rt-repo (rt-files (rt-req "RQ-1"))) "--help")))
    (should-not (string-match-p "GNU Emacs" (nth 1 r)))
    (should (string-match-p "^usage: lmx" (nth 1 r)))))

(ert-deftest lemmax-cli-finding-line ()
  (let ((r (rt-run (rt-repo (rt-files (rt-req "RQ-1" :noid t))) "lint" "--no-tests")))
    (should (string-match-p "^lmx: theories/t/theory\\.org:6: -: no :ID:; add :ID:" (nth 2 r)))))

(ert-deftest lemmax-cli-exit-codes ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (should (= 0 (nth 0 (rt-run d "lint" "--no-tests"))))
    (should (= 1 (nth 0 (rt-run d "nonsense"))))
    (rt-set d "theory.org" (concat rt-head (rt-done "RQ-1" :approved nil)))
    (should (= 1 (nth 0 (rt-run d "lint" "--no-tests"))))))

(ert-deftest lemmax-cli-writes-nothing ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1") (rt-req "RQ-1")))))
    (rt-run d "lint") (rt-run d "trace") (rt-run d "list") (rt-run d "next-id" "RQ")
    (should (equal "" (nth 1 (rt-git d "status" "--porcelain" "--ignored"))))))

;;;; RT-3

(ert-deftest lemmax-files-opted-in ()
  (rt-should-find (rt-run (rt-repo (rt-files (rt-done "RQ-1" :approved nil))) "lint" "--no-tests")
                  "no :APPROVED:"))

(ert-deftest lemmax-files-without-keyword ()
  (let* ((d (rt-repo (list (cons "theory.org" (concat "#+TODO: OPEN | DONE\n" (rt-req "RQ-1" :approved nil))))))
         (r (rt-run d "lint")))
    (should (= 0 (nth 0 r)))
    (should (string-match-p "no theory file here has" (nth 2 r)))))

(ert-deftest lemmax-files-keyword-in-text ()
  (let* ((d (rt-repo (list (cons "theory.org"
                                 (concat "Say =#+LEMMAX_TESTS: ./tests.sh= to opt in.\n\n"
                                         (rt-req "RQ-1" :approved nil))))))
         (r (rt-run d "lint")))
    (should (= 0 (nth 0 r)))
    (should-not (string-match-p "APPROVED" (nth 2 r)))))

(ert-deftest lemmax-files-none-opted-in ()
  (let ((d (rt-repo (list (cons "notes.org" "* A note\n")))))
    (dolist (cmd '("lint" "trace"))
      (let ((r (rt-run d cmd)))
        (should (= 0 (nth 0 r)))
        (should (string-match-p "no theory file here" (nth 2 r)))))))

;;;; RT-4

(defun rt-lint (&rest reqs) (rt-run (rt-repo (apply #'rt-files reqs)) "lint" "--no-tests"))

(ert-deftest lemmax-lint-clean-file ()
  (rt-should-clean (rt-lint (rt-req "RQ-1") (rt-done "RQ-2" :needs "RQ-1") (rt-req "RQ-3" :state "DROPPED"))))
(ert-deftest lemmax-lint-id-in-heading ()
  (rt-should-find (rt-lint (rt-req "RQ-1" :title "RQ-1 A title")) "starts with an id"))
(ert-deftest lemmax-lint-id-missing ()
  (rt-should-find (rt-lint (rt-req "RQ-1" :noid t)) "no :ID:"))
(ert-deftest lemmax-lint-id-shape ()
  (rt-should-find (rt-lint (rt-req "touch-map")) "neither a UUID v7 nor shaped"))
(ert-deftest lemmax-lint-id-twice ()
  (rt-should-find (rt-lint (rt-req "RQ-1") (rt-req "RQ-1")) "used twice, first at theories/t/theory.org:6"))
(ert-deftest lemmax-lint-needs-unknown ()
  (rt-should-find (rt-lint (rt-req "RQ-1" :needs "RQ-9")) "names RQ-9, which no statement has"))
(ert-deftest lemmax-lint-needs-cycle ()
  (rt-should-find (rt-lint (rt-req "RQ-1" :needs "RQ-2") (rt-req "RQ-2" :needs "RQ-1")) ":NEEDS: makes a cycle back to this id"))
(ert-deftest lemmax-lint-unapproved ()
  (rt-should-find (rt-lint (rt-done "RQ-1" :approved nil)) "DONE with no :APPROVED:")
  (rt-should-clean (rt-lint (rt-req "RQ-1" :approved nil))))
(ert-deftest lemmax-lint-dates-missing ()
  (let ((r (rt-lint (rt-req "RQ-1" :created nil :last nil))))
    (rt-should-find r "no :CREATED:")
    (should (string-match-p "no :LAST_EDITED:" (nth 2 r)))))
(ert-deftest lemmax-lint-implemented-state ()
  :tags (quote (timeout-30))
  (rt-should-find (rt-lint (rt-req "RQ-1" :state "DONE" :verify "unit/a")) "DONE with no :IMPLEMENTED:")
  (rt-should-find (rt-lint (rt-req "RQ-1" :implemented "2026-01-06")) "OPEN with :IMPLEMENTED:")
  (rt-should-find (rt-lint (rt-req "RQ-1" :state "DROPPED" :implemented "2026-01-06")) "DROPPED with :IMPLEMENTED:"))
(ert-deftest lemmax-lint-date-not-a-day ()
  (rt-should-find (rt-lint (rt-req "RQ-1" :created "2026-02-30")) "not a real day: 2026-02-30"))
(ert-deftest lemmax-lint-done-verify-empty ()
  (rt-should-find (rt-lint (rt-req "RQ-1" :state "DONE" :implemented "2026-01-06")) "DONE with no :VERIFY:"))

;;;; RT-5

(ert-deftest lemmax-verify-done-missing ()
  (rt-should-find (rt-run (rt-repo (rt-files (rt-done "RQ-1" :verify "unit/zzz"))) "lint")
                  "names unit/zzz, which the test command does not list"))
(ert-deftest lemmax-verify-open-waits ()
  (rt-should-clean (rt-run (rt-repo (rt-files (rt-req "RQ-1" :verify "unit/zzz"))) "lint")))
(ert-deftest lemmax-verify-plus-lines ()
  (rt-should-clean (rt-run (rt-repo (rt-files (rt-done "RQ-1" :verify "unit/a" :verify+ "unit/b"))) "lint"))
  (rt-should-find (rt-run (rt-repo (rt-files (rt-done "RQ-1" :verify "unit/a" :verify+ "unit/zzz"))) "lint")
                  "unit/zzz"))
(ert-deftest lemmax-verify-quoted ()
  (let ((d (rt-repo (rt-files (rt-done "RQ-1" :verify "unit/a \"process/ids are used once\"")))))
    (rt-set d "tests.sh" (rt-tests-sh "unit/a" "process/ids are used once"))
    (rt-should-clean (rt-run d "lint"))))
(ert-deftest lemmax-verify-command-fails ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (rt-set d "tests.sh" "#!/bin/sh\nexit 3\n")
    (rt-should-find (rt-run d "lint") "test command failed with exit 3: \\./tests\\.sh")))
(ert-deftest lemmax-verify-command-timeout ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (rt-set d "tests.sh" "#!/bin/sh\nsleep 5\n")
    (rt-env '("LEMMAX_TEST_SECONDS=1")
      (rt-should-find (rt-run d "lint") "ran over 1 s"))))
(ert-deftest lemmax-verify-no-tests ()
  (let ((d (rt-repo (rt-files (rt-done "RQ-1" :verify "unit/zzz")))))
    (rt-set d "tests.sh" "#!/bin/sh\nexit 3\n")
    (rt-should-clean (rt-run d "lint" "--no-tests"))))

;;;; RT-6

(defun rt-staged (before after)
  "Commit BEFORE, stage AFTER, run lint --staged on 2026-02-01."
  (let ((d (rt-repo (apply #'rt-files before))))
    (rt-set d "theory.org" (apply #'concat rt-head after))
    (rt-git d "add" "-A")
    (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests"))))

(ert-deftest lemmax-staged-done-text ()
  (rt-should-find (rt-staged (list (rt-done "RQ-1"))
                             (list (rt-done "RQ-1" :body "New text.\n" :last "2026-02-01")))
                  "DONE statement's text changed; make it OPEN"))
(ert-deftest lemmax-staged-reopened-passes ()
  (rt-should-clean (rt-staged (list (rt-done "RQ-1"))
                              (list (rt-req "RQ-1" :verify "unit/a" :body "New text.\n" :last "2026-02-01")))))
(ert-deftest lemmax-staged-last-edited ()
  (rt-should-find (rt-staged (list (rt-req "RQ-1")) (list (rt-req "RQ-1" :body "New text.\n")))
                  "LAST_EDITED: is not today; set :LAST_EDITED: 2026-02-01"))
(ert-deftest lemmax-staged-new-dates ()
  (rt-should-find (rt-staged (list (rt-req "RQ-1")) (list (rt-req "RQ-1") (rt-req "RQ-2")))
                  "RQ-2: a new statement whose :CREATED:")
  (rt-should-clean (rt-staged (list (rt-req "RQ-1"))
                              (list (rt-req "RQ-1") (rt-req "RQ-2" :created "2026-02-01" :last "2026-02-01")))))
(ert-deftest lemmax-staged-turned-done ()
  (rt-should-find (rt-staged (list (rt-req "RQ-1" :verify "unit/a")) (list (rt-done "RQ-1")))
                  "turned DONE and :IMPLEMENTED: is not today")
  (rt-should-clean (rt-staged (list (rt-req "RQ-1" :verify "unit/a")) (list (rt-done "RQ-1" :implemented "2026-02-01")))))
(ert-deftest lemmax-staged-dates-only ()
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

(ert-deftest lemmax-commit-code-needs-id ()
  (let ((d (rt-code-change (rt-req "RQ-1"))))
    (rt-should-find (rt-commit-msg d "change it\n") "names no statement id; name one in the message, as (RQ-1)")
    (rt-should-clean (rt-commit-msg d "change it (RQ-1)\n"))))
(ert-deftest lemmax-commit-docs-pass ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (rt-set d "README.md" "Docs.\n")
    (rt-git d "add" "-A")
    (rt-should-clean (rt-commit-msg d "docs\n"))))
(ert-deftest lemmax-commit-unknown-id ()
  (rt-should-find (rt-commit-msg (rt-code-change (rt-req "RQ-1")) "change (ZZ-9)\n") "names no statement id"))
(ert-deftest lemmax-commit-id-in-comment ()
  (rt-should-find (rt-commit-msg (rt-code-change (rt-req "RQ-1")) "change\n# RQ-1\n") "names no statement id"))
(ert-deftest lemmax-commit-new-id-staged ()
  (let ((d (rt-code-change (rt-req "RQ-1"))))
    (rt-set d "theory.org" (concat rt-head (rt-req "RQ-1") (rt-req "RQ-2")))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-commit-msg d "add and build (RQ-2)\n"))))
(ert-deftest lemmax-commit-whole-word ()
  (rt-should-find (rt-commit-msg (rt-code-change (rt-req "RQ-3")) "change (RQ-30)\n") "names no statement id"))

;;;; RT-8

(ert-deftest lemmax-trace-block ()
  (let ((out (nth 1 (rt-run (rt-repo (rt-files (rt-req "RQ-1"))) "trace"))))
    (should (string-match-p "^RQ-1 OPEN Title of RQ-1\n  file: theories/t/theory\\.org:6\n  parents: none\n  children: none" out))))
(ert-deftest lemmax-trace-links ()
  (let ((out (nth 1 (rt-run (rt-repo (rt-files (rt-req "RQ-1") (rt-req "RQ-2" :needs "RQ-1"))) "trace"))))
    (should (string-match-p "^RQ-1 OPEN[^\n]*\n[^\n]*\n  parents: none\n  children: RQ-2" out))
    (should (string-match-p "^RQ-2 OPEN[^\n]*\n[^\n]*\n  parents: RQ-1" out))))
(ert-deftest lemmax-trace-verify-status ()
  (let ((out (nth 1 (rt-run (rt-repo (rt-files (rt-req "RQ-1" :verify "unit/a unit/zzz"))) "trace" "--run-tests"))))
    (should (string-match-p "verify: unit/a found" out))
    (should (string-match-p "verify: unit/zzz missing" out))))
(ert-deftest lemmax-trace-commits ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-commit d "build it (RQ-1)" "2026-01-07")
    (should (string-match-p "commit: [0-9a-f]+ 2026-01-07 build it (RQ-1)" (nth 1 (rt-run d "trace"))))))
(ert-deftest lemmax-trace-orphans ()
  (let ((out (nth 1 (rt-run (rt-repo (rt-files (rt-req "RQ-1" :verify "unit/a"))) "trace" "--run-tests"))))
    (should (string-match-p "Orphan tests: \n  unit/b\nSuspect" out))
    ;; Emacs's default sentinel once wrote "Process ... finished" into the addresses.
    (should-not (string-match-p "Process lemmax-tests" out))))
(ert-deftest lemmax-trace-one-id ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1") (rt-req "RQ-2")))))
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-commit d "build it (RQ-1)")
    (let ((out (nth 1 (rt-run d "trace" "RQ-1"))))
      (should (string-match-p "^RQ-1 OPEN" out))
      (should-not (string-match-p "RQ-2 OPEN" out))
      (should (string-match-p "^    src/x\\.clj" out)))))
(ert-deftest lemmax-trace-unknown-id ()
  (rt-env (list (concat "LEMMAX_REPOS=" (rt-tmp)))
    (rt-should-find (rt-run (rt-repo (rt-files (rt-req "RQ-1"))) "trace" "ZZ-1") "unknown id ZZ-1")))

;;;; RT-9

(defun rt-suspect-repo (child-state child-extra parent-after)
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")
                              (apply (if (equal child-state "DONE") #'rt-done #'rt-req)
                                     "RQ-2" :needs "RQ-1" :implemented (and (equal child-state "DONE") "2026-01-05")
                                     child-extra))
                    "2026-01-01")))
    (rt-set d "theory.org"
            (concat rt-head parent-after
                    (apply (if (equal child-state "DONE") #'rt-done #'rt-req)
                           "RQ-2" :needs "RQ-1" :implemented (and (equal child-state "DONE") "2026-01-05")
                           child-extra)))
    (rt-commit d "change the parent" "2026-01-09")
    (nth 1 (rt-run d "trace"))))

(ert-deftest lemmax-suspect-parent-changed ()
  (let ((out (rt-suspect-repo "DONE" nil (rt-req "RQ-1" :body "Changed.\n" :last "2026-01-09"))))
    (should (string-match-p "suspect: parent RQ-1 changed 2026-01-09" out))
    (should (string-match-p "Suspect: \n  RQ-2: parent RQ-1 changed 2026-01-09" out))))
(ert-deftest lemmax-suspect-reviewed-clears ()
  (should (string-match-p "Suspect: none"
                          (rt-suspect-repo "DONE" '(:reviewed "2026-01-10")
                                           (rt-req "RQ-1" :body "Changed.\n" :last "2026-01-09")))))
(ert-deftest lemmax-suspect-dates-only ()
  (should (string-match-p "Suspect: none" (rt-suspect-repo "DONE" nil (rt-req "RQ-1" :last "2026-01-09")))))
(ert-deftest lemmax-suspect-open-child ()
  (should (string-match-p "Suspect: none"
                          (rt-suspect-repo "OPEN" nil (rt-req "RQ-1" :body "Changed.\n" :last "2026-01-09")))))
(ert-deftest lemmax-suspect-walk-time ()
  :tags '(timeout-180)
  (let* ((ids (number-sequence 1 150))
         (file (lambda (n) (concat rt-head (mapconcat (lambda (i) (rt-req (format "RQ-%d" i)
                                                                          :body (format "Text %d.\n" (if (= i (1+ (% n 150))) n 0))))
                                                      ids ""))))
         (d (rt-repo (rt-files) "2026-01-01")))
    (dotimes (n 155)
      (rt-set d "theory.org" (funcall file n))
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

(ert-deftest lemmax-harness-check-finding ()
  (let ((d (rt-repo (rt-files (rt-done "RQ-1" :approved nil)))))
    (should (string-match-p "^theories/t/theory\\.org:6: RQ-1: DONE with no :APPROVED:" (rt-check d "theories/t/theory.org\n")))))
;; lemma: 01a203e8-0c8b-713e-8f21-ffee439bcbb0
(ert-deftest lemmax-harness-check-setupfile ()
  ;; A file that opts in only through #+SETUPFILE: is checked.
  (let ((d (rt-repo (list (cons "lemmax.setup" "#+TODO: OPEN | DONE DROPPED\n#+LEMMAX_TESTS: ./tests.sh\n")
                          (cons "theory.org" (concat "#+SETUPFILE: lemmax.setup\n\n" (rt-done "RQ-1" :approved nil)))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))))))
    (should (string-match-p "^theories/t/theory\\.org:[0-9]+: RQ-1: DONE with no :APPROVED:" (rt-check d "theories/t/theory.org\n")))))

(ert-deftest lemmax-harness-check-plain-org ()
  (let ((d (rt-repo (list (cons "notes.org" (rt-req "RQ-1" :approved nil))))))
    (should (equal "" (rt-check d "notes.org\n")))))

;;;; RT-11

(defun rt-hooked (files)
  (let ((d (rt-repo files)))
    (rt-sh d "git" "config" "core.hooksPath" (expand-file-name "harness/githooks" rt-agent1))
    d))

(defun rt-hook-commit (d msg)
  (rt-sh d "git" "-c" "user.name=Test" "-c" "user.email=test@example.invalid" "commit" "-q" "-m" msg))

(ert-deftest lemmax-global-commit-msg ()
  :tags '(timeout-30)
  (let ((d (rt-hooked (rt-files (rt-req "RQ-1")))))
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-sh d "git" "add" "-A")
    (should (= 1 (nth 0 (rt-hook-commit d "change it"))))
    (should (= 0 (nth 0 (rt-hook-commit d "change it (RQ-1)"))))))
(ert-deftest lemmax-global-pre-commit ()
  :tags '(timeout-30)
  (let ((d (rt-hooked (rt-files (rt-req "RQ-1")))))
    (rt-set d "theory.org" (concat rt-head (rt-req "RQ-1" :body "Changed.\n")))
    (rt-sh d "git" "add" "-A")
    (let ((r (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-hook-commit d "edit (RQ-1)"))))
      (should (= 1 (nth 0 r)))
      (should (string-match-p "LAST_EDITED: is not today" (nth 2 r))))))
(ert-deftest lemmax-global-plain-repo-fast ()
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

(ert-deftest lemmax-runner-addresses ()
  (let ((out (nth 1 (rt-sh rt-dir (expand-file-name "run_tests" rt-dir) "--addresses"))))
    (should (string-match-p "^ert/lemmax-runner-addresses$" out))
    (should (string-match-p "^ert/lemmax-list-table$" out))))
(ert-deftest lemmax-runner-only ()
  (let ((r (rt-runner rt-small-tests "--only" "ert/x-pass")))
    (should (= 0 (nth 0 r)))
    (should (equal "PASS ert/x-pass\n" (nth 1 r))))
  (should (= 1 (nth 0 (rt-runner rt-small-tests "--only" "ert/x-fail")))))
(ert-deftest lemmax-runner-timeout ()
  :tags '(timeout-30)
  (let ((r (rt-runner rt-small-tests)))
    (should (= 1 (nth 0 r)))
    (should (string-match-p "^TIMEOUT ert/x-sleep" (nth 1 r)))
    (should (string-match-p "^PASS ert/x-pass" (nth 1 r)))
    (should (string-match-p "^FAIL ert/x-fail" (nth 1 r)))))

;;;; RT-13

(defun rt-list (d &rest args) (nth 1 (apply #'rt-run d "list" args)))
(defun rt-json-rows (out) (alist-get 'rows (json-read-from-string out)))

(ert-deftest lemmax-list-table ()
  (let* ((d (rt-repo (append (rt-files (rt-done "RQ-1") (rt-req "RQ-2" :verify "unit/zzz"))
                             (list (cons "requirements/gui.org" (rt-req "gui-look"))))))
         (out (rt-list d "--run-tests")))
    (should (string-match-p "RQ-1 +DONE +approved found +Title of RQ-1 +theories/t/theory\\.org:6" out))
    (should (string-match-p "RQ-2 +OPEN +approved missing" out))
    (should (string-match-p "gui-look +OPEN +approved none +Title of gui-look +theories/t/requirements/gui\\.org:1" out))
    (should (string-match-p "^Total: 3 statements: 2 open, 1 done, 0 dropped" out))))
(ert-deftest lemmax-list-groups ()
  (let ((out (rt-list (rt-repo (rt-files (rt-req "RQ-1" :state "DROPPED") (rt-done "RQ-2")
                                         (rt-req "RQ-3") (rt-req "RQ-4" :approved nil))))))
    (should (string-match-p "Waiting for approval (1)\n  RQ-4.*\nApproved and open (1)\n  RQ-3.*\nDone (1)\n  RQ-2.*\nDropped (1)\n  RQ-1" out))))
(ert-deftest lemmax-list-filters ()
  (let ((d (rt-repo (rt-files (rt-done "RQ-1") (rt-done "RQ-2" :verify "unit/zzz") (rt-req "RQ-3")
                              (rt-req "RQ-4" :approved nil) (rt-req "AB-1")))))
    (let ((out (rt-list d "--state" "done")))
      (should (string-match-p "RQ-1" out)) (should-not (string-match-p "RQ-3" out)))
    (let ((out (rt-list d "--section" "AB")))
      (should (string-match-p "AB-1" out)) (should-not (string-match-p "RQ-" out)))
    (let ((out (rt-list d "--ready")))
      (should (string-match-p "RQ-3" out)) (should-not (string-match-p "RQ-4\\|RQ-1" out)))
    (let ((out (rt-list d "--unchecked" "--run-tests")))
      (should (string-match-p "RQ-2" out)) (should-not (string-match-p "RQ-1 " out)))))
(ert-deftest lemmax-list-no-id ()
  (let ((out (rt-list (rt-repo (rt-files (rt-req "RQ-1") (rt-req "x" :noid t))))))
    (should (string-match-p "(no id) +OPEN" out))
    (should (string-match-p "^No id: 1" out))))
(ert-deftest lemmax-list-all-repos ()
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
      (should (string-match-p "^Total: 2 statements in 2 repos" out)))))
(ert-deftest lemmax-list-json ()
  (let* ((out (rt-list (rt-repo (rt-files (rt-done "RQ-1"))) "--json" "--run-tests"))
         (rows (alist-get 'rows (json-parse-string out :object-type 'alist))))
    (should (= 1 (length rows)))
    (should (equal "RQ-1" (alist-get 'id (aref rows 0))))
    (should (equal "found" (alist-get 'check (aref rows 0))))))

;;;; RT-14

(ert-deftest lemmax-next-id ()
  (should (equal "RQ-4\n" (nth 1 (rt-run (rt-repo (rt-files (rt-req "RQ-1") (rt-req "RQ-3"))) "next-id" "RQ")))))
(ert-deftest lemmax-next-id-gaps ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1") (rt-req "RQ-5")))))
    (should (equal "RQ-6\n" (nth 1 (rt-run d "next-id" "RQ"))))
    (should (equal "ZZ-1\n" (nth 1 (rt-run d "next-id" "ZZ"))))))
(ert-deftest lemmax-next-id-unknown ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (should (= 1 (nth 0 (rt-run d "next-id" "rq"))))
    (should (= 1 (nth 0 (rt-run d "next-id"))))))

;;;; RT-15

(ert-deftest lemmax-skill-uses-lemmax ()
  (let ((text (with-temp-buffer
                (insert-file-contents (expand-file-name "skills/add-requirement/SKILL.md" rt-agent1))
                (buffer-string))))
    (should (string-match-p "lmx list --json" text))
    (should (string-match-p "lmx next-id" text))))

;;;; 01a2090e-8591-756c-a9f1-dd473d9c3ce4: any heading has attachments, as org-attach keeps them

(defun rt-attach-conj (id tag body)
  "A conjecture ID, tagged TAG when non-nil, whose text is BODY."
  (replace-regexp-in-string "Statement\\.\n" body
                            (replace-regexp-in-string (concat "Title of " id "\n")
                                                      (concat "Title of " id (if tag (concat " :" tag ":") "") "\n")
                                                      (rt-conj id) t t)
                            t t))

;; lemma: 01a2090e-8591-756c-a9f1-dd473d9c3ce4
(ert-deftest lemmax-attach-links ()
  :tags '(timeout-60)
  (let* ((d (rt-repo (append (rt-math-files (list (rt-attach-conj "RQ-1" "ATTACH" "See [[attachment:a.png]] and [[file:docs/b.pdf]], [[file:other.org]], [[https://example.invalid/x.png]].\n")) nil)
                             (list (cons "data/RQ/-1/a.png" "png") (cons "docs/b.pdf" "pdf"))))))
    ;; The folder is the one org-attach-dir gives: data/ + the id split by Org.
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    (should (string-match-p "^  files: theories/t/data/RQ/-1/a.png theories/t/docs/b.pdf$" (nth 1 (rt-run d "trace" "RQ-1"))))
    (let* ((rows (append (cdr (assq 'rows (json-read-from-string (nth 1 (rt-run d "list" "--json"))))) nil))
           (row (cl-find "RQ-1" rows :key (lambda (x) (cdr (assq 'id x))) :test #'equal)))
      (should (equal ["theories/t/data/RQ/-1/a.png" "theories/t/docs/b.pdf"] (cdr (assq 'files row)))))
    ;; No :ATTACH: tag.
    (rt-set d "theory.org" (concat rt-math-head (rt-attach-conj "RQ-1" nil "See [[attachment:a.png]] and [[file:docs/b.pdf]].\n")))
    (rt-should-find (rt-run d "lint" "--no-tests") "RQ-1: an attachment: link, and the heading has no :ATTACH: tag")
    ;; A file git does not track.
    (rt-set d "theory.org" (concat rt-math-head (rt-attach-conj "RQ-1" "ATTACH" "See [[attachment:a.png]], [[file:docs/b.pdf]] and [[file:docs/new.gif]].\n")))
    (rt-set d "docs/new.gif" "gif")
    (rt-should-find (rt-run d "lint" "--no-tests") "RQ-1: it links theories/t/docs/new.gif, which git does not track")
    ;; An orphan: a tracked file in the attach folder that nothing links.
    (rt-set d "theory.org" (concat rt-math-head (rt-attach-conj "RQ-1" "ATTACH" "See [[file:docs/b.pdf]].\n")))
    (rt-git d "add" "-A")
    (rt-should-find (rt-run d "lint" "--no-tests") "theories/t/data/RQ/-1/a.png:1: -: a tracked file in an attach folder that no heading links")
    ;; :DIR: names the folder; over 5 MB warns and fails nothing.
    (rt-set d "theory.org"
            (concat rt-math-head
                    (replace-regexp-in-string ":END:" ":DIR:         pics\n:END:"
                                              (rt-attach-conj "RQ-1" "ATTACH" "See [[attachment:big.png]] and [[attachment:a.png]].\n") t t)
                    (rt-attach-conj "RQ-2" "ATTACH" "See [[attachment:a.png]].\n")))
    (rt-write d (list (cons "pics/big.png" (make-string (* 6 1024 1024) ?x)) (cons "pics/a.png" "png")))
    (rt-git d "rm" "-q" "theories/t/data/RQ/-1/a.png")
    (rt-set d "data/RQ/-2/a.png" "png")
    (rt-git d "add" "-A")
    (let ((r (rt-run d "lint" "--no-tests")))
      (should (= 0 (nth 0 r)))
      (should (string-match-p "RQ-1: warning: theories/t/pics/big.png is 6.0 MB, over 5 MB" (nth 2 r))))))

;;;; 01a2090e-8b52-7173-947b-d882b237ad05: publish shows attachments, with Org's own export

;; lemma: 01a2090e-8b52-7173-947b-d882b237ad05
(ert-deftest lemmax-publish-attachments ()
  :tags '(timeout-60)
  (let* ((body (concat "A picture [[attachment:a.png]] and [[file:pics/b.svg]], a [[file:docs/c.pdf][paper]].\n"
                       "#+ATTR_HTML: :src clip.mp4 :controls t\n#+begin_video\n#+end_video\n"))
         (d (rt-repo (append (rt-math-files (list (rt-attach-conj "RQ-1" "ATTACH" body)) nil)
                             (list (cons "data/RQ/-1/a.png" "png") (cons "pics/b.svg" "<svg/>")
                                   (cons "docs/c.pdf" "pdf") (cons "clip.mp4" "mp4"))))))
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    (should (= 0 (nth 0 (rt-run d "publish"))))
    (let ((html (with-temp-buffer (insert-file-contents (expand-file-name "theories/_site/t/theory.html" d)) (buffer-string))))
      (should (string-match-p "<img src=\"data/RQ/-1/a.png\"" html))
      (should (string-match-p "<img src=\"pics/b.svg\"" html))
      (should (string-match-p "<a href=\"docs/c.pdf\">paper</a>" html))
      (should (string-match-p "<video src=\"clip.mp4\" controls=\"t\"" html)))
    (dolist (f '("data/RQ/-1/a.png" "pics/b.svg" "docs/c.pdf" "clip.mp4"))
      (should (file-exists-p (expand-file-name (concat "theories/_site/" (string-remove-prefix "theories/" (rt-p f))) d))))
    ;; A video linked as a plain link is refused.
    (rt-set d "theory.org" (concat rt-math-head (rt-attach-conj "RQ-1" "ATTACH" "See [[attachment:a.png]], [[file:pics/b.svg]], [[file:docs/c.pdf]], [[file:clip.mp4]].\n")))
    (rt-should-find (rt-run d "lint" "--no-tests") "RQ-1: it links the video theories/t/clip.mp4; publish shows a video only from a block")))

;;;; 01a20927-9aac-7817-8e46-8635aa0ae127: lmx book writes the theory as one HTML file

;; lemma: 01a20927-9aac-7817-8e46-8635aa0ae127
(ert-deftest lemmax-book-one-file ()
  :tags '(timeout-60)
  (let* ((df "#+title: Terms\n#+TODO: | DEFINITION\n#+LEMMAX_TESTS: ./tests.sh\n\n* DEFINITION Word\n:PROPERTIES:\n:ID:          DF-1\n:CREATED:     2026-01-05\n:LAST_EDITED: 2026-01-05\n:END:\nA term.\n")
         (d (rt-repo (append (rt-math-files (list (rt-attach-conj "RQ-1" "ATTACH" "See [[attachment:a.png]] and [[id:PR-1][its proof]].\n")
                                                  (rt-conj "RQ-2" :state "THEOREM" :uses "RQ-1" :implemented "2026-01-06"))
                                            (list (rt-proof "PR-1" "RQ-1") (rt-proof "PR-2" "RQ-2")))
                             (list (cons "zz/theory.definitions.org" df)
                                   (cons "data/RQ/-1/a.png" "PNGDATA"))))))
    (let ((before (nth 1 (rt-git d "status" "--porcelain" "--ignored")))
          (r (rt-run d "book")))
      (should (= 0 (nth 0 r)))
      (should (equal "theories/_site/t.html\n" (nth 1 r)))
      (should (equal before (replace-regexp-in-string "^!! \\(?:.lemmax/\\|theories/_site/\\)\n" "" (nth 1 (rt-git d "status" "--porcelain" "--ignored"))))))
    (let ((org (with-temp-buffer (insert-file-contents (expand-file-name ".lemmax/book/t.org" d)) (buffer-string)))
          (html (with-temp-buffer (insert-file-contents (expand-file-name "theories/_site/t.html" d)) (buffer-string))))
      ;; Definitions first, then the theory, then its proofs.
      (should (string-match-p "#\\+INCLUDE: \"../../theories/t/zz/theory.definitions.org\"\n#\\+INCLUDE: \"../../theories/t/theory.org\"\n#\\+INCLUDE: \"../../theories/t/theory.proofs.org\"" org))
      (should (< (string-match "A term" html) (string-match "Title of RQ-1" html) (string-match "Title of RQ-2" html)))
      ;; The id: link points inside the page.
      (should (string-match "<a href=\"#\\([^\"]+\\)\">its proof</a>" html))
      (should (string-match-p (format "id=\"%s\"" (match-string 1 html)) html))
      (should (string-match-p (concat "<img src=\"data:image/png;base64," (base64-encode-string "PNGDATA" t) "\"") html))
      (should-not (string-match-p "src=\"[^d]" html)))
    (rt-run d "book" "--out" "b.html")
    (should (file-exists-p (expand-file-name "b.html" d)))))

;;;; 01a20930-0aba-7005-8442-d1dc3269c487: a project keeps its theory in theories/

;; lemma: 01a20930-0aba-7005-8442-d1dc3269c487
;; lemma: 01a2091c-4bcc-7ddb-9796-619468dd401c
(ert-deftest lemmax-org-extension ()
  :tags '(timeout-60)
  (let* ((d (rt-repo (list (cons (rt-p "theory.org") (concat "#+LEMMAX_TESTS: ./tests.sh\n\n" (rt-conj "RQ-1" :state "LEMMA")))
                           (cons "tests.sh" (rt-tests-sh "unit/a")))))
         (cli (rt-run d "lint" "--no-tests")))
    ;; Every command is an M-x command, and gives the terminal's output.
    (dolist (c '("lint" "commit-msg" "trace" "list" "plan" "new-id" "next-id"
                 "install-hooks" "migrate" "archive" "publish" "book"))
      (should (commandp (intern (concat "lemmax-" c)))))
    (let ((default-directory (file-name-as-directory d)))
      (should (= (nth 0 cli) (lemmax--interactive "lint" "--no-tests"))))
    (let ((shown (with-current-buffer "*lmx*"
                   (should (derived-mode-p 'compilation-mode))
                   (buffer-string))))
      (dolist (l (split-string (concat (nth 1 cli) (nth 2 cli)) "\n" t))
        (should (string-search l shown))))
    ;; Each add-on loads, and the README names it.
    (let ((readme (with-temp-buffer (insert-file-contents (expand-file-name "README.md" rt-dir)) (buffer-string))))
      (dolist (a lemmax-addons)
        (should (require a))
        (should (string-search (format "`%s`" a) readme))))
    ;; Each part lmx invented that Org covers has a task to switch to Org's way.
    (let ((tasks (with-temp-buffer (insert-file-contents (expand-file-name "../theories/lemmax/theory.tasks.org" rt-dir)) (buffer-string))))
      (should (string-match-p "^\\* \\(TODO\\|DONE\\) Dates come from Org's log" tasks))
      (should (string-match-p ":FOR: +01a2091c-4bcc-7ddb-9796-619468dd401c" tasks)))))

(ert-deftest lemmax-theories-folder ()
  :tags '(timeout-60)
  (let* ((setup "#+TODO: CONJECTURE | LEMMA THEOREM REFUTED\n#+LEMMAX_TESTS: ./tests.sh\n#+LEMMAX_CODE: src/\n")
         (proofs "#+SETUPFILE: setup.org\n#+TODO: OPEN | PASSED\n\n")
         (d (rt-repo (list (cons "theories/a/setup.org" setup) (cons "theories/b/setup.org" setup)
                           (cons "theories/a/theory.org" (concat "#+SETUPFILE: setup.org\n\n" (rt-lemma "RQ-1")))
                           (cons "theories/a/theory.proofs.org" (concat proofs (rt-proof "PR-1" "RQ-1")))
                           (cons "theories/b/theory.org" (concat "#+SETUPFILE: setup.org\n\n" (rt-conj "RQ-2" :state "THEOREM" :uses "RQ-1" :implemented "2026-01-06")))
                           (cons "theories/b/theory.proofs.org" (concat proofs (rt-proof "PR-2" "RQ-2")))
                           (cons "tests.sh" (rt-tests-sh "unit/a"))
                           (cons "src/x.clj" "(ns x)\n")))))
    (rt-should-clean (rt-run d "lint"))
    ;; publish: a page per file and a book per project under theories/_site/.
    (should (= 0 (nth 0 (rt-run d "publish"))))
    (dolist (f '("a/theory.html" "a/theory.proofs.html" "b/theory.html" "a.html" "b.html" ".gitignore"))
      (should (file-exists-p (expand-file-name (concat "theories/_site/" f) d))))
    (should-not (file-exists-p (expand-file-name "theories/_site/book.html" d)))
    (should (string-match-p "Title of RQ-2" (with-temp-buffer (insert-file-contents (expand-file-name "theories/_site/b.html" d)) (buffer-string))))
    (should-not (string-match-p "Title of RQ-1" (with-temp-buffer (insert-file-contents (expand-file-name "theories/_site/b.html" d)) (buffer-string))))
    ;; book --all: one book for the repo too.
    (should (= 0 (nth 0 (rt-run d "book" "--all"))))
    (let ((html (with-temp-buffer (insert-file-contents (expand-file-name "theories/_site/book.html" d)) (buffer-string))))
      (should (string-match-p "Title of RQ-1" html))
      (should (string-match-p "Title of RQ-2" html)))
    ;; git tracks nothing under _site/.
    (should (equal "" (nth 1 (rt-git d "status" "--porcelain"))))
    ;; A theory file outside theories/ is refused, by state, keyword or name.
    (rt-set d "./notes/x.org" (concat "#+TODO: CONJECTURE | LEMMA\n\n" (rt-conj "RQ-3")))
    (rt-set d "./theory.org" "#+title: Stray\n")
    (rt-set d "./docs/y.org" "#+LEMMAX_TESTS: ./tests.sh\n")
    (rt-git d "add" "-A")
    (let ((r (rt-run d "lint" "--no-tests")))
      (should (= 1 (nth 0 r)))
      (dolist (f '("notes/x.org" "theory.org" "docs/y.org"))
        (should (string-match-p (concat "^lmx: " (regexp-quote f) ":1: -: a theory file outside theories/, and every repo keeps its theory there") (nth 2 r)))))))

;;;; 01a20caa-4660-77a9-bf48-db8448f75366: a theory file is named theory.org

;; lemma: 01a20caa-4660-77a9-bf48-db8448f75366
(ert-deftest lemmax-theory-file-name ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    ;; Each requirements name is refused, in theories/ and out, and named its theory name.
    (rt-set d "theories/t/requirements.org" "#+title: Old\n")
    (rt-set d "theories/t/requirements.proofs.org" "#+title: Old proofs\n")
    (rt-set d "theories/t/requirements_archive.org" "#+title: Old archive\n")
    (rt-set d "./requirements.org" "#+title: Stray\n")
    ;; A topic file keeps its own name.
    (rt-set d "theories/t/gui.org" "#+title: GUI\n")
    (rt-git d "add" "-A")
    (let ((r (rt-run d "lint" "--no-tests")))
      (should (= 1 (nth 0 r)))
      (pcase-dolist (`(,f . ,to) '(("theories/t/requirements.org" . "theory.org")
                                   ("theories/t/requirements.proofs.org" . "theory.proofs.org")
                                   ("theories/t/requirements_archive.org" . "theory_archive.org")
                                   ("requirements.org" . "theory.org")))
        (should (string-match-p (concat "^lmx: " (regexp-quote f) ":1: -: a theory file named requirements, "
                                        "and every theory file is named theory; rename it " (regexp-quote to) "$")
                                (nth 2 r))))
      (should-not (string-match-p "gui\\.org" (nth 2 r))))))

;;;; 01a20d28-cb41-760a-a477-e1704807a2a8: an agent writes the bible and the manual

;; lemma: 01a20d28-cb41-760a-a477-e1704807a2a8
(ert-deftest lemmax-docs-warnings ()
  :tags '(timeout-60)
  (let* ((d (rt-repo (rt-math-files (list (rt-lemma "RQ-1")) (list (rt-proof "PR-1" "RQ-1")))))
         (bible "theories/t/t.bible.html") (manual "theories/t/t.manual.html"))
    ;; Finished, with neither: two warnings, and lint still passes.
    (let ((r (rt-run d "lint" "--no-tests")))
      (should (= 0 (nth 0 r)))
      (should (string-match-p (concat "^lmx: " (regexp-quote bible) ":1: -: warning: project t is finished and has no bible; run /docs") (nth 2 r)))
      (should (string-match-p (concat "^lmx: " (regexp-quote manual) ":1: -: warning: project t is finished and has no manual") (nth 2 r))))
    ;; Written after the theory: no warning.
    (rt-set d bible "<html></html>\n")
    (rt-set d manual "<html></html>\n")
    (rt-commit d "docs" "2026-02-01")
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    ;; Older than the theory: a warning naming the document.
    (rt-set d bible "<html>old</html>\n")
    (rt-commit d "old docs" "2025-12-01")
    (let ((r (rt-run d "lint" "--no-tests")))
      (should (= 0 (nth 0 r)))
      (should (string-match-p (concat "^lmx: " (regexp-quote bible) ":1: -: warning: the bible is older than the theory, edited 2026-01-05") (nth 2 r)))
      (should-not (string-match-p "manual is older" (nth 2 r))))
    ;; Not finished: no missing-document warning.
    (let ((e (rt-repo (rt-math-files (list (rt-conj "RQ-1")) (list (rt-proof "PR-1" "RQ-1" :state "OPEN"))))))
      (should-not (string-match-p "is finished and has no" (nth 2 (rt-run e "lint" "--no-tests")))))))

;; lemma: 01a20d28-cb41-760a-a477-e1704807a2a8
(ert-deftest lemmax-docs-skill-writes-them ()
  ;; The /docs skill, not lmx, writes both: it reads the project and researches first.
  (let ((text (with-temp-buffer
                (insert-file-contents (expand-file-name "skills/docs/SKILL.md" rt-agent1))
                (buffer-string))))
    (should (string-match-p "^## LemmaX mode" text))
    (dolist (re '("Read the whole project" "Research the web before writing"
                  "theories/PROJECT/PROJECT\\.bible\\.html" "theories/PROJECT/PROJECT\\.manual\\.html"
                  "https://www\\.gnu\\.org/manual/manual\\.html" "`lmx` never does"))
      (should (string-match-p re text))))
  ;; lmx has no command that writes either.
  (let ((help (nth 1 (rt-run (rt-repo (rt-files (rt-req "RQ-1"))) "help"))))
    (should-not (string-match-p "^  \\(?:bible\\|manual\\)\\b" help))))

;;;; 01a20a84-971d-767f-8a26-c98f6d132b7f: a moved link is not a text change

;; lemma: 01a20a84-971d-767f-8a26-c98f6d132b7f
(ert-deftest lemmax-moved-link-same-text ()
  :tags '(timeout-60)
  (let* ((lemma (lambda (link) (replace-regexp-in-string "Statement\\." (format "See [[file:%s][the doc]]." link) (rt-lemma "RQ-1") t t)))
         (d (rt-repo (append (rt-math-files (list (funcall lemma "rules/a.md")) (list (rt-proof "PR-1" "RQ-1")))
                             (list (cons "theories/t/rules/a.md" "# A\n") (cons "theories/t/rules/b.md" "# B\n"))))))
    ;; Move the theory and the doc; the link is rewritten to name the same file.
    (dolist (f '("theories/t/sub" "theories/t/docs")) (make-directory (expand-file-name f d) t))
    (rt-git d "mv" "theories/t/theory.org" "theories/t/sub/theory.org")
    (rt-git d "mv" "theories/t/theory.proofs.org" "theories/t/sub/theory.proofs.org")
    (rt-git d "mv" "theories/t/rules/a.md" "theories/t/docs/a.md")
    (rt-set d "theories/t/sub/theory.org" (concat rt-math-head (funcall lemma "../docs/a.md")))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-11-24") (rt-run d "lint" "--staged" "--no-tests")))
    ;; A link to another file is a text change.
    (rt-set d "theories/t/sub/theory.org" (concat rt-math-head (funcall lemma "../rules/b.md")))
    (rt-git d "add" "-A")
    (rt-should-find (rt-env '("LEMMAX_TODAY=2026-11-24") (rt-run d "lint" "--staged" "--no-tests"))
                    "RQ-1: a LEMMA statement's text changed")))

;; lemma: 01a20c8e-872d-75b3-97fe-22718d4b809b
(ert-deftest lemmax-mended-link-same-text ()
  :tags '(timeout-60)
  (let* ((lemma (lambda (link follows)
                  (replace-regexp-in-string
                   ":END:" (format ":FOLLOWS: %s::a\n:END:" follows)
                   (replace-regexp-in-string "Statement\\." (format "See [[file:%s][the doc]]." link) (rt-lemma "RQ-1") t t)
                   t t)))
         (d (rt-repo (append (rt-math-files (list (funcall lemma "gone.md" "nowhere/gone.org")) (list (rt-proof "PR-1" "RQ-1")))
                             (list (cons "theories/t/rules/a.md" "# A\n") (cons "theories/t/rules/b.md" "# B\n")))))
         (here (concat (file-name-nondirectory (directory-file-name d)) "/theories/t/rules/a.md"))
         (lint (lambda (link follows)
                 (rt-set d "theories/t/theory.org" (concat rt-math-head (funcall lemma link follows)))
                 (rt-git d "add" "-A")
                 (rt-env '("LEMMAX_TODAY=2026-11-24") (rt-run d "lint" "--staged" "--no-tests")))))
    ;; Both named files that are gone; mending them is no change.
    (rt-should-clean (funcall lint "rules/a.md" here))
    (rt-commit d "mend")
    ;; A link to a file that exists, pointed at another, is a change.
    (rt-should-find (funcall lint "rules/b.md" here) "RQ-1: a LEMMA statement's text changed")))


;;; lemmax_tests.el ends here

;;;; RT-16

(ert-deftest lemmax-project-list-many ()
  (let ((a (rt-repo (rt-files (rt-req "RQ-1"))))
        (b (rt-repo (rt-files (rt-req "AB-1") (rt-req "AB-2"))))
        (elsewhere (rt-tmp)))
    (let ((out (nth 1 (rt-run elsewhere "list" "--no-tests" "-p" a "--project" (expand-file-name "src" b)))))
      (should (string-match-p (concat "^== " (regexp-quote (file-name-nondirectory a))) out))
      (should (string-match-p (concat "^== " (regexp-quote (file-name-nondirectory b))) out))
      (should (string-match-p "^Total: 3 statements in 2 repos" out)))))
(ert-deftest lemmax-project-one-command ()
  (let ((a (rt-repo (rt-files (rt-req "RQ-1") (rt-req "RQ-4"))))
        (elsewhere (rt-tmp)))
    (should (equal "RQ-5\n" (nth 1 (rt-run elsewhere "next-id" "RQ" "--project" a))))
    (should (string-match-p "^RQ-1 OPEN" (nth 1 (rt-run elsewhere "trace" "-p" a))))
    (rt-should-clean (rt-run elsewhere "lint" "--no-tests" "-p" a))))
(ert-deftest lemmax-project-errors ()
  (let ((a (rt-repo (rt-files (rt-req "RQ-1")))) (plain (rt-tmp)))
    (rt-should-find (rt-run plain "list" "-p" (expand-file-name "missing" plain)) "no such folder")
    (rt-should-find (rt-run a "list" "-p" plain) "not inside a git repo")
    (rt-should-find (rt-run a "lint" "-p" a "-p" a) "lint takes one --project")
    (rt-should-find (rt-run a "next-id" "RQ" "-p") "--project needs a folder")))

;;;; RT-19

(ert-deftest lemmax-trace-finds-other-project ()
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
(ert-deftest lemmax-trace-unknown-anywhere ()
  (let ((base (rt-tmp)))
    (rt-env (list (concat "LEMMAX_REPOS=" base))
      (rt-should-find (rt-run (rt-tmp) "trace" "ZZ-9") "unknown id ZZ-9, here or in any project under"))))

;;;; 01a1fe0c-9c5c-7057-8edc-bc68ccfa0490

(ert-deftest lemmax-lint-id-uuid7 ()
  :tags '(timeout-30)
  (rt-should-clean (rt-lint (rt-req "01a1fe0c-9c5c-7057-8edc-bc68ccfa0490") (rt-req "RQ-1")))
  (rt-should-find (rt-lint (rt-req "01a1fe0c-9c5c-4057-8edc-bc68ccfa0490")) "neither a UUID v7")
  (rt-should-find (rt-lint (rt-req "01A1FE0C-9C5C-7057-8EDC-BC68CCFA0490")) "neither a UUID v7"))

;;;; RT-17

(ert-deftest lemmax-trace-one-id-text ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1" :body "First line.\n- a point\n") (rt-req "RQ-2")))))
    (let ((out (nth 1 (rt-run d "trace" "RQ-1"))))
      (should (string-match-p "  text:\n    First line\\.\n    - a point" out))
      (should-not (string-match-p ":PROPERTIES:\\|:ID:" out)))
    (should-not (string-match-p "text:" (nth 1 (rt-run d "trace"))))))

;;;; 01a1ff25-116d-73f1-a45e-dd77e482a983

(ert-deftest lemmax-name-and-place ()
  (should (string-match-p "lemmax/\\'" rt-dir))
  (let ((r (rt-sh rt-dir rt-bin "--help")))
    (should (= 0 (nth 0 r)))
    (should (string-match-p "^usage: lmx COMMAND" (nth 1 r))))
  (should-not (file-exists-p (expand-file-name "harness/reqtrace" rt-agent1)))
  (dolist (f '("harness/githooks/pre-commit" "harness/githooks/commit-msg" "harness/self_check"
               "harness/checks/lemmax_lint.py" "skills/add-requirement/SKILL.md"))
    (let ((text (with-temp-buffer (insert-file-contents (expand-file-name f rt-agent1)) (buffer-string))))
      (should (string-match-p "lemmax" text))
      (should-not (string-match-p "reqtrace" text)))))

(ert-deftest lemmax-reads-old-keyword-in-history ()
  :tags '(timeout-30)
  (let ((d (rt-repo (list (cons "theory.org"
                                (concat "#+TODO: OPEN | DONE DROPPED\n#+REQTRACE_TESTS: ./tests.sh\n\n" (rt-done "RQ-1")))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))))))
    (rt-set d "theory.org" (concat "#+TODO: OPEN | DONE DROPPED\n#+LEMMAX_TESTS: ./tests.sh\n\n" (rt-done "RQ-1")))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests")))))

(ert-deftest lemmax-new-id ()
  (let* ((d (rt-repo (rt-files (rt-req "RQ-1"))))
         (a (rt-run d "new-id")) (b (rt-run d "new-id"))
         (re "\\`[0-9a-f]\\{8\\}-[0-9a-f]\\{4\\}-7[0-9a-f]\\{3\\}-[89ab][0-9a-f]\\{3\\}-[0-9a-f]\\{12\\}\n\\'"))
    (should (= 0 (nth 0 a)))
    (should (string-match-p re (nth 1 a)))
    (should (string-match-p re (nth 1 b)))
    (should-not (equal (nth 1 a) (nth 1 b)))
    (should-not (string> (substring (nth 1 a) 0 13) (substring (nth 1 b) 0 13)))
    (should (= 1 (nth 0 (rt-run d "new-id" "extra"))))
    (should (string-match-p "^usage: lmx new-id" (nth 1 (rt-run d "new-id" "--help"))))))

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
  (rt-should-find (rt-run (rt-repo (append (rt-files (rt-done "RQ-1" :implemented "2026-11-22"))
                                           (list (cons "lemmax/config.eld" "(:markers-required-from \"2026-11-22\")\n"))))
                          "lint" "--no-tests")
                  "RQ-1: DONE with no code marker")
  (let ((d (rt-repo (append (rt-files (rt-done "RQ-1"))
                            (list (cons "lemmax/config.eld" "(:markers-required-from \"2026-11-22\")\n"))))))
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    (should (string-match-p "RQ-1" (nth 1 (rt-run d "list" "--no-tests" "--unmarked"))))))

(ert-deftest lemmax-marker-tests-apart ()
  :tags '(timeout-30)
  (let ((d (rt-repo (append (rt-files (rt-done "RQ-1" :implemented "2026-11-22"))
                            (list (cons "test/x_test.clj" ";; lemma: RQ-1\n")
                                  (cons "lemmax/config.eld" "(:markers-required-from \"2026-11-22\")\n"))))))
    (should (string-match-p "  test: test/x_test\\.clj:1" (nth 1 (rt-run d "trace" "RQ-1"))))
    (rt-should-find (rt-run d "lint" "--no-tests") "RQ-1: DONE with no code marker"))
  (let ((d (rt-repo (list (cons "theory.org"
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
                  "DONE statement's text changed")
  (rt-should-clean (rt-staged (list (rt-done "RQ-1" :body "See [[*RQ-2 The base][RQ-2]] and [[file:x.org::*RQ-2 The base][it]].\n"))
                              (list (rt-done "RQ-1" :body "See [[*The base][RQ-2]] and [[file:x.org::*The base][it]].\n"))))
  (let ((d (rt-repo (rt-files (rt-req "RQ-1" :title "RQ-1 The parent") (rt-done "RQ-2" :needs "RQ-1" :implemented "2026-01-05"))
                    "2026-01-01")))
    (rt-set d "theory.org" (concat rt-head (rt-req "RQ-1" :title "The parent")
                                         (rt-done "RQ-2" :needs "RQ-1" :implemented "2026-01-05")))
    (rt-commit d "ids leave the headings" "2026-01-09")
    (should (string-match-p "Suspect: none" (nth 1 (rt-run d "trace"))))))

;;;; 01a2002d-fb3b-71e3-ac96-5e1dbba8226c

(ert-deftest lemmax-opt-in-compares-head ()
  :tags '(timeout-30)
  (let ((d (rt-repo (list (cons "theory.org" (concat "#+TODO: OPEN | DONE DROPPED\n\n" (rt-done "RQ-1")))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))))))
    (rt-set d "theory.org" (concat rt-head (rt-done "RQ-1")))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests")))))

(ert-deftest lemmax-markers-in-other-repo ()
  :tags '(timeout-30)
  (let* ((base (rt-tmp))
         (book (expand-file-name "book" base)) (code (expand-file-name "code" base)))
    (dolist (d (list book code)) (make-directory d) (rt-git d "init" "-q" "-b" "main"))
    (rt-write book (list (cons "theory.org" (concat rt-head "#+LEMMAX_MARKERS_IN: ../code\n\n"
                                                          (rt-done "RQ-1" :implemented "2026-11-22")))
                         (cons "tests.sh" (rt-tests-sh "unit/a"))))
    (rt-write code (list (cons "src/x.clj" ";; lemma: RQ-1\n")))
    (rt-commit book "start") (rt-commit code "start")
    (should (string-match-p "  code: \\.\\./code/src/x\\.clj:1" (nth 1 (rt-run book "trace" "RQ-1"))))
    (rt-should-clean (rt-run book "lint" "--no-tests"))))

;;;; 01a202b0-1d09-75f3-99dc-677a4b2ec0be: settings in lemmax/config.eld

(defconst rt-plain-head "#+title: One lemma\n\n")

(defun rt-config (&rest entries)
  (cons "lemmax/config.eld"
        (format ";; lemmax config\n(:folders %S)\n"
                (mapcar (lambda (e) (if (string-empty-p (car e)) e (cons (concat rt-theory (car e)) (cdr e)))) entries))))

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
    (should (string-match-p "Total: 2 statements" (nth 1 (rt-run d "list"))))
    (rt-set d "reqs/RQ-3.org" (concat rt-plain-head (rt-req "RQ-1")))
    (rt-git d "add" "-A")
    (rt-should-find (rt-run d "lint" "--no-tests") "used twice")))

(ert-deftest lemmax-config-header-wins ()
  :tags '(timeout-30)
  (let ((d (rt-repo (list (rt-config '("" :tests "./bad.sh"))
                          (cons "theory.org" (concat rt-head (rt-done "RQ-1")))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))
                          (cons "bad.sh" "#!/bin/sh\nexit 3\n")))))
    (set-file-modes (expand-file-name "bad.sh" d) #o755)
    ;; The header wins: bad.sh never runs. Set both ways, it is refused
    ;; (01a20ed2-d34b-71f9-a19a-04bb7cc6cf6e).
    (let ((r (rt-run d "lint")))
      (rt-should-find r "LEMMAX_TESTS is set both in lemmax/config.eld for the root and in theories/t/theory.org's header")
      (should-not (string-match-p "exit 3" (nth 2 r))))))

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
                    "DONE statement's text changed")))

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
    (rt-set d "lemmax/config.eld" "(:folders (\"theories/t/reqs/\" :tests \"x\")")
    (rt-should-find (rt-run d "lint" "--no-tests") "does not read")))

;;;; 01a202bc-49e2-7dba-94f5-0c0952fc91f0: id: links

(ert-deftest lemmax-id-link-unknown ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1" :body "See [[id:RQ-9][nine]]; as text, =[[id:ID]]=.\n")))))
    (let ((r (rt-run d "lint" "--no-tests")))
      (rt-should-find r "theory.org:[0-9]+: RQ-9: the id: link names an id no lemma has")
      (should-not (string-match-p ": ID: " (nth 2 r))))))

(ert-deftest lemmax-id-link-dropped ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1" :body "See [[id:RQ-2]].\n") (rt-req "RQ-2" :state "DROPPED")))))
    (rt-should-find (rt-run d "lint" "--no-tests") "RQ-2: the id: link names a DROPPED lemma")))

(ert-deftest lemmax-id-link-ok ()
  :tags '(timeout-30)
  (let ((d (rt-repo (rt-files (rt-done "RQ-1" :body "See [[id:RQ-2][two]].\n") (rt-req "RQ-2")))))
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    ;; Only the shown text of the link changed: not a text change of a DONE lemma.
    (rt-set d "theory.org" (concat rt-head (rt-done "RQ-1" :body "See [[id:RQ-2][the second]].\n") (rt-req "RQ-2")))
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
    (let ((json (rt-json-rows (nth 1 (rt-run d "list" "--json" "--no-tests")))))
      (should (= 2 (length json)))
      (let ((one (cl-find "RQ-1" json :key (lambda (r) (alist-get 'id r)) :test #'equal)))
        (should (equal "The whole file" (alist-get 'title one)))
        (should (equal "OPEN" (alist-get 'state one)))
        (should (equal "theories/t/reqs/one.org" (alist-get 'file one)))))
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
                    "DONE statement's text changed")
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
    (let ((row (aref (rt-json-rows (nth 1 (rt-run d "list" "--json" "--no-tests"))) 0)))
      (should (equal ["https://example.invalid/issues/4" "http://example.invalid/spec"] (alist-get 'refs row))))
    (rt-set d "theory.org" (concat rt-head (rt-req "RQ-1" :refs "issue-4")))
    (rt-should-find (rt-run d "lint" "--no-tests") "RQ-1: :REFS: names issue-4, which is not an http(s) URL")))

;;;; 01a202bc-4b52-74e6-9d78-591320edcb4f: backlinks

(ert-deftest lemmax-trace-backlinks ()
  :tags '(timeout-30)
  (let ((d (rt-repo (append (rt-files (rt-req "RQ-1" :body "Self [[id:RQ-1]].\n")
                                       (rt-req "RQ-2" :body "Needs [[id:RQ-1][one]].\n")
                                       "* Notes\nAlso [[id:RQ-1]].\n")
                            (list (cons "notes/talk.org" "* Talk\nAbout [[id:RQ-1]] and =[[id:RQ-1]]=.\n"))))))
    (let ((tr (nth 1 (rt-run d "trace" "RQ-1"))))
      (should (string-match-p "  linked from: RQ-2 theories/t/theory\\.org:[0-9]+" tr))
      (should (string-match-p "  linked from: theories/t/theory\\.org:[0-9]+$" (replace-regexp-in-string "RQ-2 " "" tr)))
      (should (string-match-p "  linked from: theories/t/notes/talk\\.org:2" tr))
      (should (= 3 (cl-count-if (lambda (l) (string-prefix-p "  linked from:" l)) (split-string tr "\n")))))
    (should (string-match-p "  linked from: none" (nth 1 (rt-run d "trace" "RQ-2"))))
    (let* ((rows (rt-json-rows (nth 1 (rt-run d "list" "--json" "--no-tests"))))
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
      (should (string-match-p "^theories/t/theory\\.org:[0-9]+: RQ-1$" out))
      (should (string-match-p "^theories/t/notes/n\\.org:1: OLD-1$" out))
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
    (rt-git d "mv" "theory.org" "reqs/moved.org")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests")))))

(ert-deftest lemmax-move-lemma-between-files ()
  :tags '(timeout-30)
  (let ((d (rt-repo (append (rt-files (rt-done "RQ-1") (rt-done "RQ-2"))
                            (list (rt-config '("reqs/" :tests "./tests.sh")))))))
    ;; RQ-2 leaves the shared file for a file of its own, as a file lemma.
    (rt-set d "theory.org" (concat rt-head (rt-done "RQ-1")))
    (rt-set d "reqs/RQ-2.org" (concat ":PROPERTIES:\n:ID: RQ-2\n:STATE: DONE\n:CREATED: 2026-01-05\n:LAST_EDITED: 2026-01-05\n:APPROVED: 2026-01-05\n:IMPLEMENTED: 2026-01-06\n:VERIFY: unit/a\n:END:\n#+title: Title of RQ-2\n\nBody text.\n"))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests")))))

;;;; 01a202f3-82c0-7905-9aa6-cafdcd9235e8: paths with colons

(ert-deftest lemmax-colon-path-marker ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (rt-set d "src/a:b.el" ";; lemma: RQ-9\n")
    (rt-git d "add" "-A")
    (rt-should-find (rt-run d "lint" "--no-tests") "src/a:b\\.el:1: RQ-9: the marker names an id no lemma has")))

(ert-deftest lemmax-colon-path-link ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (rt-set d "notes/a:b.org" "See [[id:RQ-1]].\n")
    (rt-git d "add" "-A")
    (should (string-match-p "linked from: theories/t/notes/a:b\\.org:1" (nth 1 (rt-run d "trace" "RQ-1"))))))

;;;; 01a202f3-834a-7fcc-9a94-a50f2d1ab85c: list and trace run no test command unless asked

(ert-deftest lemmax-list-runs-no-tests ()
  :tags '(timeout-30)
  (let ((d (rt-repo (rt-files (rt-done "RQ-1")))))
    (rt-set d "tests.sh" "#!/bin/sh\ntouch RAN\necho unit/a\n")
    (set-file-modes (expand-file-name "tests.sh" d) #o755)
    (should (string-match-p "RQ-1 +DONE +approved named" (rt-list d)))
    (rt-list d "--json")
    (rt-run d "trace")
    (rt-run d "trace" "RQ-1")
    (rt-run d "trace" "--dot")
    (should-not (file-exists-p (expand-file-name "RAN" d)))))

(ert-deftest lemmax-run-tests-flag ()
  :tags '(timeout-30)
  (let ((d (rt-repo (rt-files (rt-done "RQ-1")))))
    (should (string-match-p "RQ-1 +DONE +approved found" (rt-list d "--run-tests")))
    (should (string-match-p "verify: unit/a found" (nth 1 (rt-run d "trace" "RQ-1" "--run-tests"))))
    (should (string-match-p "verify: unit/a unchecked" (nth 1 (rt-run d "trace" "RQ-1"))))))

;;;; In-process tests: lemmax.el loaded, its command line not run

(defun rt-load ()
  (unless (fboundp 'lemmax--parse)
    (let ((process-environment (cons "LEMMAX_LOAD_ONLY=1" process-environment)))
      (load (expand-file-name "lemmax.el" rt-dir) nil t))))

;;;; 01a202f3-83dc-76e8-b198-68db19d1e4cd: one parser

(defconst rt-odd-files
  (list (concat rt-head (rt-req "RQ-1") (rt-req "RQ-2" :level 2) "* Notes\nNo id.\n" (rt-req "RQ-3" :state nil))
        (concat "# a comment\n" (rt-file-lemma "RQ-4" :body "Body.\n* Sub\n:PROPERTIES:\n:ID: NOT-1\n:END:\n"))
        (concat "#+title: Late\n:PROPERTIES:\n:ID: RQ-5\n:END:\n* OPEN Real\n:PROPERTIES:\n:ID: RQ-6\n:END:\n")
        (concat rt-head (rt-req "RQ-7" :body "Has [[id:RQ-1][a link]] and\n\n\n trailing.\n\n"))
        ""))

(ert-deftest lemmax-one-parser-same-ids ()
  (rt-load)
  (dolist (c rt-odd-files)
    (let ((full (cl-loop for r in (plist-get (lemmax--parse c "f.org") :statements)
                         when (plist-get r :id) collect (cons (plist-get r :id) (plist-get r :text))))
          (quick (lemmax--quick-ids c)))
      (should (equal full quick))))
  (should (equal '("RQ-4") (mapcar #'car (lemmax--quick-ids (nth 1 rt-odd-files)))))
  (should (equal '("RQ-6") (mapcar #'car (lemmax--quick-ids (nth 2 rt-odd-files))))))

;;;; 01a202f3-8475-7f4f-b0e2-5cd8c782e520: a file lemma's drawer comes first

(ert-deftest lemmax-file-drawer-first ()
  :tags '(timeout-30)
  (let ((d (rt-file-lemma-repo
            (cons "reqs/late.org" "#+title: Late\n\n:PROPERTIES:\n:ID: RQ-5\n:END:\nBody.\n")
            (cons "reqs/ok.org" (concat "# kept\n" (rt-file-lemma "RQ-1"))))))
    (let ((r (rt-run d "lint" "--no-tests")))
      (rt-should-find r "theories/t/reqs/late\\.org:3: -: a drawer with :ID: below other text is no file lemma")
      (should-not (string-match-p "reqs/ok\\.org" (nth 2 r))))
    (should-not (string-match-p "RQ-5" (rt-list d)))
    (should (string-match-p "RQ-1" (rt-list d)))))

;;;; 01a202f3-850b-7e3f-93f9-655397189d53: today is the local day

(ert-deftest lemmax-today-local ()
  :tags '(timeout-30)
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    ;; 02:00 at +05:00: 2026-01-08 in Karachi, 2026-01-07 in UTC.
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-git d "add" "-A")
    (rt-env '("GIT_COMMITTER_DATE=2026-01-08T02:00:00+05:00" "GIT_AUTHOR_DATE=2026-01-08T02:00:00+05:00")
      (rt-git d "commit" "-q" "-m" "build it (RQ-1)"))
    (should (string-match-p "commit: [0-9a-f]+ 2026-01-08 build it" (nth 1 (rt-env '("TZ=Asia/Karachi") (rt-run d "trace" "RQ-1")))))
    (should (string-match-p "commit: [0-9a-f]+ 2026-01-07 build it" (nth 1 (rt-env '("TZ=UTC0") (rt-run d "trace" "RQ-1")))))
    ;; With no LEMMAX_TODAY, the fix names the local day of TZ.
    (rt-set d "theory.org" (concat rt-head (rt-req "RQ-1") (rt-req "RQ-2")))
    (rt-git d "add" "-A")
    (dolist (tz '("Pacific/Kiritimati" "Pacific/Pago_Pago"))
      (let ((day (format-time-string "%F" nil tz))
            (r (rt-env (list (concat "TZ=" tz)) (rt-run d "lint" "--staged" "--no-tests"))))
        (should (string-match-p (concat "set both to " day) (nth 2 r)))))))

;;;; 01a202f3-85a4-76cd-bf13-05f6e723c5b2: missing or old Emacs

(defun rt-bin-dir (&rest progs)
  "A folder holding links to PROGS, to stand for PATH."
  (let ((b (expand-file-name "bin" (rt-tmp))))
    (make-directory b t)
    (dolist (p progs) (make-symbolic-link (executable-find p) (expand-file-name p b)))
    b))

(ert-deftest lemmax-launcher-no-emacs ()
  (let* ((d (rt-repo (rt-files (rt-req "RQ-1"))))
         (bin (rt-bin-dir "bash" "dirname" "readlink" "git")))
    (let ((r (rt-env (list (concat "PATH=" bin)) (rt-run-proc d "list"))))
      (should (= 2 (nth 0 r)))
      (should (string-match-p "lmx: needs Emacs 29 or newer; found none on PATH" (nth 2 r))))))

(ert-deftest lemmax-launcher-old-emacs ()
  (let* ((d (rt-repo (rt-files (rt-req "RQ-1"))))
         (bin (rt-bin-dir "bash" "dirname" "readlink" "git")))
    (with-temp-file (expand-file-name "emacs" bin)
      ;; The launcher calls emacs -Q --script FILE -- ARGS; --script runs before any
      ;; --eval, so the stand-in loads FILE with -l after setting the version.
      (insert "#!" (executable-find "bash") "\nshift 2\nf=\"$1\"; shift\nexec " (executable-find "emacs")
              " -Q --batch --eval '(setq emacs-major-version 28 emacs-version \"28.2\")' -l \"$f\" \"$@\"\n"))
    (set-file-modes (expand-file-name "emacs" bin) #o755)
    (let ((r (rt-env (list (concat "PATH=" bin)) (rt-run-proc d "list"))))
      (should (= 2 (nth 0 r)))
      (should (string-match-p "lmx: needs Emacs 29 or newer; found 28.2" (nth 2 r))))))

;;;; 01a202f3-86d9-7db2-a0dc-accec28dfe29 and 01a202f3-863b-7c04-9728-0c9dd9346002: CI

(defun rt-workflow ()
  (with-temp-buffer
    (insert-file-contents (expand-file-name ".github/workflows/lemmax.yml" rt-agent1))
    (buffer-string)))

(ert-deftest lemmax-ci-workflow ()
  (let ((w (rt-workflow)))
    (should (string-match-p "^on:\n  push:\n  pull_request:" w))
    (should (string-match-p "run: lemmax/run_tests$" w))
    (should (string-match-p "run: lemmax/lmx lint$" w))
    (should-not (string-match-p "lmx lint --no-tests" w))))

(ert-deftest lemmax-ci-matrix ()
  (let ((w (rt-workflow)))
    (should (string-match "emacs_version: \\[\\(.*\\)\\]" w))
    (let ((vs (split-string (match-string 1 w) "[\", ]+" t)))
      (should (member "29.4" vs))
      (should (cl-some (lambda (v) (or (equal v "release-snapshot") (>= (string-to-number v) 30))) vs)))
    (should (string-match-p "container: silex/emacs:\\${{ matrix.emacs_version }}" w))))

;;;; 01a202f3-878b-75cb-98e0-9d7929ef88c1: --json says its version

(ert-deftest lemmax-json-version ()
  (let ((j (json-read-from-string (rt-list (rt-repo (rt-files (rt-req "RQ-1"))) "--json"))))
    (should (equal 1 (alist-get 'version j)))
    (should (vectorp (alist-get 'rows j)))))

(ert-deftest lemmax-json-shape ()
  ;; Every key of a row, and the JSON type of each: a change here bumps version.
  (let* ((j (json-parse-string (rt-list (rt-repo (rt-files (rt-req "RQ-1"))) "--json") :object-type 'alist
                               :null-object :null :false-object :false))
         (row (aref (alist-get 'rows j) 0))
         (type (lambda (v) (cond ((eq v :null) 'null) ((memq v '(t :false)) 'bool) ((stringp v) 'string)
                                 ((numberp v) 'number) ((vectorp v) 'array) (t 'object)))))
    (should (equal '((id . string) (state . string) (group . string) (approved . string) (verify . array)
                     (check . string) (needs . array) (refs . array) (files . array) (linked_from . array) (title . string)
                     (file . string) (line . number) (markers . array))
                   (mapcar (lambda (kv) (cons (car kv) (funcall type (cdr kv)))) row)))))

;;;; 01a202f3-88bb-704d-9ea9-74714f841514: the history walk stays fast

(ert-deftest lemmax-history-cache ()
  :tags '(timeout-300 alone)
  (let* ((d (rt-repo (rt-files (rt-req "RQ-1")) "2026-01-01"))
         (reqs (lambda (n) (concat rt-head (rt-req "RQ-1" :body (format "Text %d.\n" (/ n 50)))
                                   (rt-done "RQ-2" :needs "RQ-1" :implemented "2026-01-02")
                                   (mapconcat (lambda (i) (rt-req (format "RQ-%d" i))) (number-sequence 3 20) "")))))
    ;; 500 commits: the requirements file changes on 1 in 5, back and forth.
    (dotimes (n 500)
      (if (= 0 (% n 5))
          (rt-set d "theory.org" (funcall reqs n))
        (rt-set d "src/x.clj" (format "(ns x) ;; %d\n" n)))
      (rt-commit d (format "c%d" n) "2026-02-01"))
    (rt-git d "repack" "-adq")
    (let* ((start (float-time)) (out (nth 1 (rt-run d "trace"))) (took (- (float-time) start)))
      (should (string-match-p "suspect: parent RQ-1 changed 2026-02-01" out))
      (message "trace over 500 commits: %.2f s" took)
      (should (< took 2.0)))))

;;;; 01a202f3-8964-7333-8165-dba3d86556b5: odd input reads as plain input

(defun rt-lemmas (content)
  (mapcar (lambda (r) (list (plist-get r :id) (plist-get r :state) (plist-get r :title)
                            (plist-get r :verify) (plist-get r :text) (plist-get r :created)))
          (plist-get (lemmax--parse content "f.org") :statements)))

(ert-deftest lemmax-odd-input ()
  (rt-load)
  (let* ((plain (concat rt-head (rt-req "RQ-1" :verify "unit/a \"unit/with space\"") (rt-req "RQ-2")))
         (want (rt-lemmas plain)))
    (should (equal '("unit/a" "unit/with space") (nth 3 (car want))))
    (should (equal want (rt-lemmas (replace-regexp-in-string "\n" "\r\n" plain))))
    (should (equal want (rt-lemmas (concat "\ufeff" plain))))
    (should (equal want (rt-lemmas (replace-regexp-in-string "^\\(:[A-Z_]+:\\) +" "\\1\t" plain))))
    (should (null (rt-lemmas "")))
    (should (equal (mapcar #'car (rt-lemmas (rt-file-lemma "RQ-3")))
                   (mapcar #'car (rt-lemmas (concat "\ufeff" (replace-regexp-in-string "\n" "\r\n" (rt-file-lemma "RQ-3")))))))))

(ert-deftest lemmax-odd-input-id-space ()
  (let ((d (rt-repo (rt-files (rt-req "RQ 1")))))
    (rt-should-find (rt-run d "lint" "--no-tests") "RQ 1: an id has no spaces")))

;;;; 01a202f3-8822-7602-98a4-67acc268e3b0: golden, generated and mutation tests

(defconst rt-golden-dir (expand-file-name "golden/" rt-dir))

(defun rt-golden (name text)
  "TEXT, its commit hashes masked, against golden/NAME; LEMMAX_UPDATE_GOLDEN=1 writes it."
  (let ((text (replace-regexp-in-string "\\_<[0-9a-f]\\{7,40\\}\\_>" "HASH" text))
        (file (expand-file-name name rt-golden-dir)))
    (if (getenv "LEMMAX_UPDATE_GOLDEN")
        (progn (make-directory rt-golden-dir t) (with-temp-file file (insert text)))
      (should (equal (with-temp-buffer (insert-file-contents file) (buffer-string)) text)))))

(defun rt-golden-repo ()
  (let ((d (rt-repo (append (rt-files (rt-done "RQ-1" :title "The base" :refs "https://example.invalid/1")
                                      (rt-done "RQ-2" :title "Builds on it" :needs "RQ-1" :body "Uses [[id:RQ-1]].\n")
                                      (rt-req "RQ-3" :title "Not yet" :aliases "OLD-3")
                                      (rt-req "RQ-4" :title "Dropped one" :state "DROPPED"))
                            (list (cons "notes/n.org" "About [[id:RQ-2]].\n")))
                    "2026-01-05")))
    (rt-set d "src/x.clj" ";; lemma: RQ-1 RQ-2\n(ns x)\n")
    (rt-commit d "build them (RQ-1 RQ-2)" "2026-01-06")
    d))

(ert-deftest lemmax-golden-trace ()
  :tags '(timeout-30)
  (let ((d (rt-golden-repo)))
    (rt-golden "trace.txt" (nth 1 (rt-run d "trace" "--run-tests")))
    (rt-golden "trace-one.txt" (nth 1 (rt-run d "trace" "RQ-2" "--run-tests")))
    (rt-golden "trace.dot" (nth 1 (rt-run d "trace" "--dot")))))

(ert-deftest lemmax-golden-list ()
  :tags '(timeout-30)
  (let ((d (rt-golden-repo)))
    (rt-golden "list.txt" (rt-list d "--run-tests"))
    (rt-golden "list.json" (rt-list d "--json" "--run-tests"))))

(defun rt-gen-file (seed)
  "A generated org file and the lemmas it holds, as (CONTENT . ((ID STATE TITLE NEEDS) ...))."
  (random (format "lemmax-%d" seed))
  (let* ((n (random 6)) (lemmas nil) (parts (list rt-head))
         (words ["alpha" "beta" "gamma" "δέλτα" "naïve" "x=1" "~code~" "a:b" "[[id:RQ-1][l]]" "50%"]))
    (dotimes (i n)
      (let* ((id (format "G%d-%d" seed (1+ i)))
             (state (nth (random 3) '("OPEN" "DONE" "DROPPED")))
             (title (mapconcat (lambda (_) (aref words (random (length words)))) (number-sequence 0 (random 4)) " "))
             (needs (and lemmas (= 0 (random 2)) (list (car (nth (random (length lemmas)) lemmas))))))
        (push (list id state (string-trim title) needs) lemmas)
        (push (rt-req id :state state :title title :level (1+ (random 3)) :needs (and needs (car needs))
                      :body (if (= 0 (random 3)) "" (concat (aref words (random (length words))) "\n* Not a lemma\n")))
              parts)))
    (cons (apply #'concat (nreverse parts)) (nreverse lemmas))))

(ert-deftest lemmax-generated-roundtrip ()
  :tags '(timeout-60)
  (rt-load)
  (dotimes (seed 200)
    (let* ((g (rt-gen-file seed))
           (got (cl-loop for r in (plist-get (lemmax--parse (car g) "g.org") :statements)
                         when (plist-get r :id)
                         collect (list (plist-get r :id) (plist-get r :state) (plist-get r :title) (plist-get r :needs)))))
      (should (equal (cdr g) got))
      (should (equal (mapcar #'car (cdr g)) (mapcar #'car (lemmax--quick-ids (car g))))))))

(defun rt-lint-rules ()
  "Each lint rule of lemmax.el, as the key that names it: the longest plain
run of its finding's why text."
  (let (keys)
    (with-temp-buffer
      (insert-file-contents (expand-file-name "lemmax.el" rt-dir))
      (goto-char (point-min))
      (condition-case nil
          (while t
            (let ((walk nil))
              (setq walk (lambda (f)
                           (when (consp f)
                             (when (and (eq (car f) 'lemmax--finding) (>= (length f) 6))
                               (let* ((why (nth 4 f))
                                      (s (cond ((stringp why) why)
                                               ((and (eq (car-safe why) 'format) (stringp (nth 1 why))) (nth 1 why)))))
                                 (when s
                                   (let ((best "") (pos 0) (s (replace-regexp-in-string "%[a-zA-Z]" "|" s)))
                                     (while (string-match "[A-Za-z0-9_:' ]+" s pos)
                                       (when (> (length (match-string 0 s)) (length best)) (setq best (match-string 0 s)))
                                       (setq pos (match-end 0)))
                                     (push (string-trim best) keys)))))
                             (while (consp f) (funcall walk (car f)) (setq f (cdr f))))))
              (funcall walk (read (current-buffer)))))
        (end-of-file nil)))
    (delete-dups (nreverse keys))))

(defun rt-key-windows (key)
  "Each two-word window of KEY, 9 characters or more."
  (let ((w (split-string key " " t)))
    (cl-loop for (a b) on w while b
             for win = (concat a " " b)
             when (>= (length win) 9) collect win)))

(defun rt-tests-naming (key)
  "Names of the tests whose code holds a two-word window of KEY, most first."
  (let ((wins (or (rt-key-windows key) (list key))) scored)
    (with-temp-buffer
      (insert-file-contents (expand-file-name "lemmax_tests.el" rt-dir))
      (goto-char (point-min))
      (condition-case nil
          (while t
            (let ((f (read (current-buffer))))
              (when (and (eq (car-safe f) 'ert-deftest)
                         (not (eq (nth 1 f) 'lemmax-mutation-lint-rules)))
                (let* ((code (prin1-to-string f))
                       (n (cl-count-if (lambda (w) (string-search w code)) wins)))
                  (when (> n 0) (push (cons n (nth 1 f)) scored))))))
        (end-of-file nil)))
    (mapcar #'cdr (sort (nreverse scored) (lambda (a b) (> (car a) (car b)))))))

(ert-deftest lemmax-mutation-lint-rules ()
  :tags '(timeout-600 alone)
  (let ((rules (rt-lint-rules)) uncovered survived)
    (should (> (length rules) 25))
    ;; With the rule off, at least one test that names it must fail. Each
    ;; rule tries its tests in turn; rules run 8 at a time.
    ;; lemma: RT-12
    (let ((queue (cl-loop for key in rules
                          for tests = (rt-tests-naming key)
                          if tests collect (cons key tests)
                          else do (push key uncovered)))
          (running nil))
      (cl-flet ((start (job)
                  (let ((process-environment (cons (concat "LEMMAX_MUTATE=" (car job)) process-environment)))
                    (push (cons (make-process :name "rt-mutant" :buffer nil :noquery t
                                              :command (list "emacs" "-Q" "--batch"
                                                             "-l" (expand-file-name "ert_roster.el" rt-dir)
                                                             "-l" (expand-file-name "lemmax_tests.el" rt-dir)
                                                             "--eval" (format "(ert-run-tests-batch-and-exit '%s)" (cadr job))))
                                job)
                          running))))
        (while (or queue running)
          (while (and queue (< (length running) 8)) (start (pop queue)))
          (accept-process-output nil 0.05)
          (dolist (r running)
            (let ((proc (car r)) (job (cdr r)))
              (unless (process-live-p proc)
                (setq running (delq r running))
                ;; A test that passes with the rule off cannot show it: try the next.
                (when (= 0 (process-exit-status proc))
                  (if (cddr job) (push (cons (car job) (cddr job)) queue) (push (car job) survived)))))))))
    (should (equal (list :uncovered nil :survived nil) (list :uncovered uncovered :survived survived)))))

;;;; 01a20336-c4d6-73d3-a429-0a755d277123: read only candidate files, once

(defmacro rt-in (dir &rest body)
  "BODY with lemmax loaded, in DIR, its caches empty."
  (declare (indent 1))
  `(progn (rt-load)
          (let ((default-directory (file-name-as-directory ,dir)))
            (clrhash lemmax--files-cache)
            ,@body)))

(defun rt-counting-parses (thunk)
  "Call THUNK; the list of files `lemmax--parse' read meanwhile."
  (let (seen)
    (let ((f (lambda (_content file) (push file seen))))
      (advice-add 'lemmax--parse :before f)
      (unwind-protect (funcall thunk) (advice-remove 'lemmax--parse f)))
    (nreverse seen)))

(ert-deftest lemmax-reads-candidates-only ()
  (let ((d (rt-repo (append (rt-files (rt-req "RQ-1"))
                            (list (cons "./notes/plain.org" "* A note\n:PROPERTIES:\n:ID: n-1\n:END:\nOPEN word in text.\n")
                                  (cons "./notes/todo.org" "* DONE A done note\n")
                                  (cons "./notes/file-lemma.org" (rt-file-lemma "RQ-2"))
                                  (cons "requirements/gui.org" "* Title only\n"))))))
    (rt-in d
      (let ((read (rt-counting-parses #'lemmax--worktree-files)))
        (should (equal (sort (copy-sequence read) #'string<)
                       '("notes/file-lemma.org" "notes/todo.org" "theories/t/requirements/gui.org" "theories/t/theory.org")))))))

;; lemma: 01a2058c-5dff-75bc-b089-998d5425915a
(ert-deftest lemmax-reads-theory-files ()
  ;; Unmarked theory.org, theory/a.org and requirements/b.org: list shows all
  ;; three; lint checks none, since none has #+LEMMAX_TESTS:.
  (let* ((file (lambda (id) (concat "#+TODO: CONJECTURE | LEMMA THEOREM REFUTED\n\n"
                                    "* CONJECTURE A thing\n:PROPERTIES:\n:ID:          " id
                                    "\n:CREATED:     2026-01-01\n:LAST_EDITED: 2026-01-01\n:END:\nBody.\n")))
         (d (rt-repo (list (cons "requirements/b.org" (funcall file "X-1"))
                           (cons "theory/a.org" (funcall file "X-2"))
                           (cons "theory.org" (funcall file "X-3")))))
         (out (nth 1 (rt-run d "list"))))
    (dolist (id '("X-1" "X-2" "X-3"))
      (should (string-match-p (concat "^  " id " ") out)))
    (should (= 0 (nth 0 (rt-run d "lint" "--no-tests"))))))

(ert-deftest lemmax-parse-once ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (rt-in d
      (let ((read (rt-counting-parses (lambda () (lemmax--worktree-files) (lemmax--worktree-files)
                                         (lemmax--rev-files "") (lemmax--rev-files "") (lemmax--rev-files "HEAD")))))
        (should (equal read '("theories/t/theory.org" "theories/t/theory.org" "theories/t/theory.org")))))))

(ert-deftest lemmax-big-notes-repo-time ()
  :tags '(timeout-120 alone)
  (let ((d (rt-repo (append (rt-files (rt-req "RQ-1" :created "2026-11-22" :last "2026-11-22"))
                            (cl-loop for i from 1 to 1500
                                     collect (cons (format "./notes/n%d.org" i)
                                                   (format "* Note %d\n:PROPERTIES:\n:ID: note-%d\n:END:\nText.\n" i i)))))))
    (rt-set d "theory.org" (concat rt-head (rt-req "RQ-1" :created "2026-11-22" :last "2026-11-22" :body "Changed.\n")))
    (rt-git d "add" "-A")
    ;; The fastest of 3 runs: run_tests runs 8 tests at once, and their load
    ;; alone can push one run past 2 s on a lemmax that takes 0.3 s idle.
    (let (r took)
      (dotimes (_ 3)
        (let ((start (float-time)))
          (setq r (rt-env '("LEMMAX_TODAY=2026-11-22") (rt-run d "lint" "--staged" "--no-tests")))
          (setq took (min (or took 1e9) (- (float-time) start)))))
      (rt-should-clean r)
      (should (< took 2.0)))))

;;;; 01a20336-c583-720a-b661-c9b5a5dec1a4: FILE arguments are paths from where lemmax runs

(ert-deftest lemmax-file-arg-from-cwd ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1" :created nil)))))
    (make-directory (expand-file-name "sub" d))
    (rt-should-find (rt-run (expand-file-name "sub" d) "lint" "--no-tests" "../theories/t/theory.org")
                    "theory.org:[0-9]+: RQ-1: no :CREATED:")
    (rt-should-find (rt-run d "lint" "--no-tests" "./theories/t/theory.org") "no :CREATED:")))

(ert-deftest lemmax-file-arg-unknown ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (dolist (f '("nope.org" "src/x.clj"))
      (let ((r (rt-run d "lint" "--no-tests" f)))
        (should (= 1 (nth 0 r)))
        (should (string-match-p (concat "lmx: " (regexp-quote (rt-p f)) ": not a tracked \\.org file") (nth 2 r)))))))

;;;; 01a20336-c611-73c8-bb70-4a8e70e675d1: agent1's own rules are config

(ert-deftest lemmax-config-markers-required-from ()
  :tags '(timeout-30)
  ;; No key: no lemma needs a marker, however new.
  (rt-should-clean (rt-run (rt-repo (rt-files (rt-done "RQ-1" :implemented "2030-01-01"))) "lint" "--no-tests"))
  (let ((d (rt-repo (append (rt-files (rt-done "RQ-1" :implemented "2026-03-01") (rt-done "RQ-2" :implemented "2026-02-27"))
                            (list (cons "lemmax/config.eld" "(:markers-required-from \"2026-02-28\")\n"))))))
    (let ((r (rt-run d "lint" "--no-tests")))
      (rt-should-find r "RQ-1: DONE with no code marker")
      (should-not (string-match-p "RQ-2" (nth 2 r)))))
  (let ((d (rt-repo (append (rt-files (rt-req "RQ-1"))
                            (list (cons "lemmax/config.eld" "(:markers-required-from \"soon\")\n"))))))
    (rt-should-find (rt-run d "lint" "--no-tests") ":markers-required-from is not a day")))

(ert-deftest lemmax-config-repos ()
  :tags '(timeout-30)
  (let* ((base (rt-tmp)) (here (expand-file-name "here" base)) (far (expand-file-name "far" base)))
    (make-directory (expand-file-name "other" far) t)
    (make-directory here)
    (dolist (d (list here (expand-file-name "other" far))) (rt-git d "init" "-q" "-b" "main"))
    (rt-write (expand-file-name "other" far) (rt-files (rt-req "OT-1")))
    (rt-commit (expand-file-name "other" far) "start")
    (rt-write here (append (rt-files (rt-req "RQ-1"))
                           (list (cons "lemmax/config.eld" (format "(:repos %S)\n" far)))))
    (rt-commit here "start")
    (let ((out (nth 1 (rt-env '("LEMMAX_REPOS=/nonexistent") (rt-run here "list" "--all")))))
      (should (string-match-p "== other" out))
      (should (string-match-p "OT-1" out)))))

(ert-deftest lemmax-messages-neutral ()
  (let ((src (with-temp-buffer (insert-file-contents (expand-file-name "lemmax.el" rt-dir)) (buffer-string)))
        (help (nth 1 (rt-run (rt-repo (rt-files (rt-req "RQ-1"))) "help"))))
    (dolist (word '("agent1" "RF-3" "arcadia" "2026-11-22" "theory.org forbids"))
      (should-not (string-search word src))
      (should-not (string-search word help)))))

;;;; 01a20336-c75e-78ac-bf5e-7a72262f73e6: tests clean up after themselves

(ert-deftest lemmax-tests-clean-up ()
  :tags '(timeout-60)
  (dolist (keep '(nil t))
    (let ((tmp (make-temp-file "rt-clean" t)))
      (let ((process-environment (append (list (concat "TMPDIR=" tmp) (concat "LEMMAX_KEEP_TMP=" (if keep "1" "0")))
                                         process-environment)))
        ;; One passing and one failing test, each in its own Emacs, as run_tests runs them.
        (dolist (form '((ert-deftest rt-probe-pass () (rt-repo (rt-files (rt-req "RQ-1"))) (should t))
                        (ert-deftest rt-probe-fail () (rt-repo (rt-files (rt-req "RQ-1"))) (should nil))))
          (call-process "emacs" nil nil nil "-Q" "--batch"
                        "-l" (expand-file-name "ert_roster.el" rt-dir) "-l" (expand-file-name "lemmax_tests.el" rt-dir)
                        "--eval" (format "(progn %S (ert-run-tests-batch-and-exit '%s))" form (nth 1 form)))))
      (let ((left (directory-files tmp nil "\\`lemmax-test-")))
        (if keep (should (= 2 (length left))) (should (null left))))
      (delete-directory tmp t))))

;;;; 01a20336-c80d-733a-a251-ad26a0ebf7d3: version, licence, changelog

(ert-deftest lemmax-version ()
  (rt-load)
  (let ((r (rt-run (rt-tmp) "--version")))
    (should (= 0 (nth 0 r)))
    (should (equal (format "lmx %s\n" lemmax-version) (nth 1 r)))
    (should (string-match-p "\\`[0-9]+\\.[0-9]+\\.[0-9]+\\'" lemmax-version))))

(ert-deftest lemmax-licence-and-changelog ()
  (rt-load)
  (let ((lic (with-temp-buffer (insert-file-contents (expand-file-name "LICENSE" rt-dir)) (buffer-string)))
        (log (with-temp-buffer (insert-file-contents (expand-file-name "CHANGELOG.md" rt-dir)) (buffer-string))))
    (should (string-prefix-p "MIT License\n" lic))
    (should (string-match "^## \\([0-9.]+\\) " log))
    (should (equal lemmax-version (match-string 1 log)))))

;;;; RT-18: a duplicate id is shown, never hidden

(ert-deftest lemmax-trace-duplicate-id ()
  :tags '(timeout-30)
  (let* ((d (rt-repo (append (rt-files (rt-req "RQ-1" :title "First") (rt-req "RQ-2"))
                             (list (rt-config '("reqs/" :tests "./tests.sh"))
                                   (cons "reqs/again.org" (rt-file-lemma "RQ-1" :title "Second"))))))
         (r (rt-run d "trace" "RQ-1")))
    (should (= 1 (nth 0 r)))
    ;; File order: reqs/again.org sorts before theory.org.
    (should (string-match-p "\\`RQ-1 OPEN Second\n\\(?:.*\n\\)*RQ-1 OPEN First" (nth 1 r)))
    (should-not (string-match-p "#\\+title" (nth 1 r)))
    (should (string-match-p "lmx: RQ-1 is used 2 times" (nth 2 r)))
    (should (= 0 (nth 0 (rt-run d "trace" "RQ-2"))))))

(ert-deftest lemmax-list-duplicates ()
  :tags '(timeout-30)
  (let* ((d (rt-repo (append (rt-files (rt-req "RQ-1") (rt-req "RQ-2"))
                             (list (cons "requirements/other.org" (rt-req "RQ-1"))))))
         (out (rt-list d "--duplicates")))
    (should (= 2 (cl-count-if (lambda (l) (string-match-p "^  RQ-1 " l)) (split-string out "\n"))))
    (should-not (string-match-p "RQ-2" out))))

;;;; 01a20336-c953-745d-aef4-90ee2141e08d: markers come only from sibling repos

(ert-deftest lemmax-markers-in-siblings-only ()
  :tags '(timeout-30)
  (let* ((base (rt-tmp)) (book (expand-file-name "book" base)) (far (expand-file-name "x/far" base)))
    (make-directory book) (make-directory far t)
    (dolist (d (list book far)) (rt-git d "init" "-q" "-b" "main"))
    (rt-write far (list (cons "src/x.clj" ";; lemma: RQ-9\n")))
    (rt-commit far "start")
    (make-directory (expand-file-name "plain" base))
    (dolist (dir (list "../x/far" far "../plain" "../../etc"))
      (rt-write book (list (cons "theory.org" (concat rt-head (format "#+LEMMAX_MARKERS_IN: %s\n\n" dir) (rt-req "RQ-1")))
                           (cons "tests.sh" (rt-tests-sh "unit/a"))))
      (rt-commit book (concat "use " dir))
      (let ((r (rt-run book "lint" "--no-tests")))
        (rt-should-find r (concat "markers-in names " (regexp-quote dir) ", which is not a git repo beside this one"))
        ;; Not read: far's marker for RQ-9 would be a finding of its own.
        (should-not (string-match-p "RQ-9" (nth 2 r)))))))

;;;; 01a20336-c9e9-7664-ba5c-e5e12d249d48: fork pull requests are safe

(ert-deftest lemmax-ci-safe-trigger ()
  (let ((w (rt-workflow))
        (readme (with-temp-buffer (insert-file-contents (expand-file-name "README.md" rt-dir)) (buffer-string))))
    (should (string-match-p "^permissions:\n  contents: read$" w))
    (should-not (string-match-p "^  pull_request_target:" w))
    (should-not (string-match-p "\\${{ *secrets\\." w))
    (should (string-match-p "Never run\nlemmax under `pull_request_target`" readme))))

;;;; 01a20336-cb25-779d-9e80-e04a22bd235d: where lemmax runs is said

(ert-deftest lemmax-readme-platforms ()
  (let ((readme (with-temp-buffer (insert-file-contents (expand-file-name "README.md" rt-dir)) (buffer-string))))
    (dolist (w '("macOS and Linux" "WSL or Git Bash" "Emacs 29 or newer" "git and Bash" "Perl"))
      (should (string-search w readme)))))

;;;; 01a20336-cbc7-70a7-9473-18325683fba6: config checks every path it names

(ert-deftest lemmax-config-empty-tests ()
  (let ((d (rt-repo (append (rt-files (rt-req "RQ-1")) (list (rt-config '("" :tests "  ")))))))
    (rt-should-find (rt-run d "lint" "--no-tests") ":tests is empty; name the command")))

(ert-deftest lemmax-config-unknown-paths ()
  (let ((d (rt-repo (append (rt-files (rt-req "RQ-1"))
                            (list (rt-config '("" :tests "./tests.sh" :code ("src/" "gone/" "tests.sh") :test-paths ("_spec." "src/"))))))))
    (let ((r (rt-run d "lint" "--no-tests")))
      (rt-should-find r ":code names gone/, which holds no tracked file")
      (should (string-match-p ":test-paths names _spec\\., which no tracked file matches" (nth 2 r)))
      (should-not (string-match-p "names src/\\|names tests\\.sh" (nth 2 r))))))

;;;; 01a20336-ca8d-75bf-bedc-33da69c29468: stable output, lint speaks JSON

(ert-deftest lemmax-lint-json ()
  (let* ((d (rt-repo (rt-files (rt-req "RQ-1" :created nil) (rt-req "RQ-2"))))
         (r (rt-run d "lint" "--no-tests" "--json"))
         (j (json-parse-string (nth 1 r) :object-type 'alist :null-object nil)))
    (should (= 1 (nth 0 r)))
    (should (equal "" (nth 2 r)))
    (should (equal 1 (alist-get 'version j)))
    (let ((f (aref (alist-get 'findings j) 0)))
      (should (equal '(file line id why fix) (mapcar #'car f)))
      (should (equal "RQ-1" (alist-get 'id f)))
      (should (equal "no :CREATED:" (alist-get 'why f)))))
  (let ((r (rt-run (rt-repo (rt-files (rt-req "RQ-1"))) "lint" "--no-tests" "--json")))
    (should (= 0 (nth 0 r)))
    (should (equal "{\"version\":1,\"findings\":[]}\n" (nth 1 r)))))

(ert-deftest lemmax-exit-codes ()
  (let ((d (rt-repo (rt-files (rt-req "RQ-1")))))
    (should (= 0 (nth 0 (rt-run d "lint" "--no-tests"))))
    (should (string-match-p "\\`lmx: theories/t/theory\\.org:[0-9]+: RQ-1: [^;]+; .+\n\\'"
                            (progn (rt-set d "theory.org" (concat rt-head (rt-req "RQ-1" :created nil)))
                                   (nth 2 (rt-run d "lint" "--no-tests")))))
    (should (= 1 (nth 0 (rt-run d "lint" "--no-tests"))))
    (should (= 1 (nth 0 (rt-run d "lint" "--bogus"))))
    (should (= 1 (nth 0 (rt-run d "nonsense"))))))

;;;; 01a20336-c6c6-7ac0-aea1-6d5ff12a8fea: lmx install-hooks

(defun rt-hook-env ()
  "PATH with lemmax on it, as a user's install leaves it."
  (let ((bin (expand-file-name "bin" (rt-tmp))))
    (make-directory bin t)
    (make-symbolic-link rt-bin (expand-file-name "lmx" bin))
    (list (concat "PATH=" bin ":" (getenv "PATH")))))

(defun rt-real-commit (dir msg)
  "git commit in DIR through its .git/hooks: (EXIT STDOUT STDERR)."
  (rt-sh dir "git" "-c" "core.hooksPath=.git/hooks" "-c" "user.name=Test" "-c" "user.email=test@example.invalid"
         "-c" "commit.gpgsign=false" "commit" "-q" "-m" msg))

;; lemma: 01a20d0f-f245-7678-b438-511c148c4eb7
(ert-deftest lemmax-install-hooks ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-files (rt-req "RQ-1"))))
        (env (rt-hook-env)))
    (should (string-match-p "pre-commit: written\ncommit-msg: written" (nth 1 (rt-run d "install-hooks"))))
    ;; The hooks call lmx, the program's name.
    (should (string-match-p "^\tlmx lint --staged" (with-temp-buffer (insert-file-contents (expand-file-name ".git/hooks/pre-commit" d)) (buffer-string))))
    (should (string-match-p "^\tlmx commit-msg" (with-temp-buffer (insert-file-contents (expand-file-name ".git/hooks/commit-msg" d)) (buffer-string))))
    (rt-env env
      ;; pre-commit refuses a broken lemma.
      (rt-set d "theory.org" (concat rt-head (rt-req "RQ-1" :created nil)))
      (rt-git d "add" "-A")
      (let ((r (rt-real-commit d "docs: break it")))
        (should (/= 0 (nth 0 r)))
        (should (string-match-p "no :CREATED:" (nth 2 r))))
      ;; commit-msg refuses a code commit that names no id.
      (rt-set d "theory.org" (concat rt-head (rt-req "RQ-1")))
      (rt-set d "src/x.clj" "(ns x) ;; 2\n")
      (rt-git d "add" "-A")
      (should (/= 0 (nth 0 (rt-real-commit d "change it"))))
      (should (= 0 (nth 0 (rt-real-commit d "change it (RQ-1)")))))))

(ert-deftest lemmax-install-hooks-chains ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-files (rt-req "RQ-1"))))
        (env (rt-hook-env)))
    (rt-write d (list (cons ".git/hooks/pre-commit" "#!/bin/sh\ntouch OLD_RAN\n")))
    (set-file-modes (expand-file-name ".git/hooks/pre-commit" d) #o755)
    (should (string-match-p "kept the old hook as pre-commit.local" (nth 1 (rt-run d "install-hooks"))))
    (rt-env env
      (rt-set d "src/x.clj" "(ns x) ;; 2\n")
      (rt-git d "add" "-A")
      (should (= 0 (nth 0 (rt-real-commit d "change it (RQ-1)")))))
    (should (file-exists-p (expand-file-name "OLD_RAN" d)))))

(ert-deftest lemmax-install-hooks-again ()
  (let* ((d (rt-repo (rt-files (rt-req "RQ-1"))))
         (_ (rt-run d "install-hooks"))
         (before (with-temp-buffer (insert-file-contents (expand-file-name ".git/hooks/pre-commit" d)) (buffer-string)))
         (out (nth 1 (rt-run d "install-hooks"))))
    (should (string-match-p "pre-commit: already lemmax's\ncommit-msg: already lemmax's" out))
    (should-not (file-exists-p (expand-file-name ".git/hooks/pre-commit.local" d)))
    (should (equal before (with-temp-buffer (insert-file-contents (expand-file-name ".git/hooks/pre-commit" d)) (buffer-string))))))

;;;; 01a20336-cc5d-70ae-878b-b241ecc9ef61: the name is lemmax everywhere

(ert-deftest lemmax-no-old-name ()
  ;; The old name stays only where it must: install removes the old command,
  ;; tests check it is gone, two lemmas tell the rename, README says it once.
  (let ((allowed-lemmas '("01a1ff25-116d-73f1-a45e-dd77e482a983" "01a20336-cc5d-70ae-878b-b241ecc9ef61"))
        bad)
    (dolist (f (split-string (with-temp-buffer
                               (let ((default-directory rt-agent1))
                                 (call-process "git" nil t nil "ls-files" "lemmax" "theories/lemmax" "skills/add-requirement"
                                               ".github"))
                               (buffer-string))
                             "\n" t))
      (unless (member (file-name-nondirectory f) '("install" "lemmax_tests.el"))
        (let ((text (with-temp-buffer (insert-file-contents (expand-file-name f rt-agent1)) (buffer-string))))
          (if (or (string-suffix-p "theory.org" f) (string-suffix-p ".proofs.org" f))
              (dolist (e (split-string text "^\\*+ " t))
                ;; A proof of an allowed lemma takes its title.
                (when (and (string-search "reqtrace" e)
                           (not (cl-some (lambda (id) (or (string-search (concat ":ID:          " id) e)
                                                          (string-search (concat ":PROVES:      " id) e)))
                                         allowed-lemmas)))
                  (push (concat f ": " (car (split-string e "\n"))) bad)))
            (dolist (l (split-string text "\n"))
              (when (and (string-search "reqtrace" l) (not (string-search "lemmax was reqtrace" l)))
                (push (concat f ": " l) bad)))))))
    (should (equal nil bad))))

;;;; 01a20369-38d2-7202-8b53-6e296aaac489: conjectures, proofs, lemmas and theorems

(defconst rt-math-head "#+title: Invented\n#+TODO: CONJECTURE | LEMMA THEOREM REFUTED\n#+LEMMAX_TESTS: ./tests.sh\n#+LEMMAX_CODE: src/\n\n")
(defconst rt-proofs-head "#+title: Proofs\n#+TODO: OPEN | PASSED\n#+LEMMAX_TESTS: ./tests.sh\n#+LEMMAX_CODE: src/\n\n")

(cl-defun rt-conj (id &key (state "CONJECTURE") uses verify (approved "2026-01-05") implemented (level 1))
  (concat (make-string level ?*) " " state " Title of " id "\n:PROPERTIES:\n"
          (format ":ID:          %s\n" id)
          (if uses (format ":USES:        %s\n" uses) "")
          ":CREATED:     2026-01-05\n:LAST_EDITED: 2026-01-05\n"
          (if approved (format ":APPROVED:    %s\n" approved) "")
          (if implemented (format ":IMPLEMENTED: %s\n" implemented) "")
          (if verify (format ":VERIFY:      %s\n" verify) "")
          ":END:\nStatement.\n"))

(cl-defun rt-proof (id proves &key (state "PASSED") (test "unit/a") implemented)
  (concat "* " (if state (concat state " ") "") "Proof " id "\n:PROPERTIES:\n"
          (format ":ID:          %s\n" id)
          (if proves (format ":PROVES:      %s\n" proves) "")
          (if test (format ":TEST:        %s\n" test) "")
          (if implemented (format ":IMPLEMENTED: %s\n" implemented) "")
          ":CREATED:     2026-01-05\n:LAST_EDITED: 2026-01-05\n:END:\nIt passes.\n"))

(defun rt-math-files (reqs proofs)
  (list (cons "theory.org" (apply #'concat rt-math-head reqs))
        (cons "theory.proofs.org" (apply #'concat rt-proofs-head proofs))
        (cons "tests.sh" (rt-tests-sh "unit/a" "unit/b"))
        (cons "src/x.clj" "(ns x)\n")))

(defun rt-lemma (id &rest kv)
  (apply #'rt-conj id (append kv (list :state "LEMMA" :implemented "2026-01-06"))))

(ert-deftest lemmax-math-states ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-math-files (list (rt-conj "RQ-1") (rt-lemma "RQ-2")
                                         (rt-conj "RQ-3" :state "THEOREM" :uses "RQ-2" :implemented "2026-01-06")
                                         (rt-conj "RQ-4" :state "REFUTED"))
                                   (list (rt-proof "PR-1" "RQ-2") (rt-proof "PR-2" "RQ-3"))))))
    (rt-should-clean (rt-run d "lint"))
    (let ((out (nth 1 (rt-run d "list"))))
      (should (string-match-p "RQ-1 +CONJECTURE" out))
      (should (string-match-p "RQ-2 +LEMMA" out))
      (should (string-match-p "RQ-3 +THEOREM" out))
      (should (string-match-p "RQ-4 +REFUTED" out))
      (should (string-match-p "Total: 4 statements: 1 open, 2 done, 1 dropped; 2 proofs" out)))
    (should (string-match-p "uses: RQ-2" (nth 1 (rt-run d "trace" "RQ-3"))))
    (should (string-match-p "used by: RQ-3" (nth 1 (rt-run d "trace" "RQ-2"))))
    ;; :USES: is read as :NEEDS:, unknown ids too.
    (rt-set d "theory.org" (concat rt-math-head (rt-conj "RQ-1" :uses "RQ-9")))
    (rt-set d "theory.proofs.org" rt-proofs-head)
    (rt-should-find (rt-run d "lint") "names RQ-9, which no statement has")
    ;; A :VERIFY: line is not a lemma's text: changing a proof leaves the lemma.
    (rt-set d "theory.org" (concat rt-head (rt-done "RQ-1")))
    (rt-commit d "old")
    (rt-set d "theory.org" (concat rt-head (rt-req "RQ-1" :state "DONE" :implemented "2026-01-06" :verify "unit/b")))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-11-22") (rt-run d "lint" "--staged" "--no-tests")))))

(ert-deftest lemmax-math-proofs-file ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-math-files (list (rt-lemma "RQ-1"))
                                   (list (rt-proof "PR-1" "RQ-1") (rt-proof "PR-2" "RQ-1" :test "unit/b"))))))
    (rt-should-clean (rt-run d "lint"))
    (let ((tr (nth 1 (rt-run d "trace" "RQ-1"))))
      (should (string-match-p "proof: PR-1 PASSED" tr))
      (should (string-match-p "proof: PR-2 PASSED" tr))
      (should (string-match-p "verify: unit/a" tr))
      (should (string-match-p "verify: unit/b" tr)))
    ;; A proof's :TEST: is checked against the test command.
    (rt-set d "theory.proofs.org" (concat rt-proofs-head (rt-proof "PR-1" "RQ-1" :test "unit/zz")))
    (rt-should-find (rt-run d "lint") ":TEST: names unit/zz, which the test command does not list")))

;;;; 01a20369-38f7-7229-8232-1b8cbb98e6bc: lint proves a lemma from its proofs

(ert-deftest lemmax-math-lint ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-math-files (list (rt-lemma "RQ-1")) (list (rt-proof "PR-1" "RQ-1")))))
        (case (lambda (d reqs proofs re)
                (rt-set d "theory.org" (apply #'concat rt-math-head reqs))
                (rt-set d "theory.proofs.org" (apply #'concat rt-proofs-head proofs))
                (rt-should-find (rt-run d "lint" "--no-tests") re))))
    (rt-should-clean (rt-run d "lint"))
    (funcall case d (list (rt-lemma "RQ-1")) nil "a LEMMA with no proof")
    (funcall case d (list (rt-lemma "RQ-1")) (list (rt-proof "PR-1" "RQ-1" :state "OPEN"))
             "proof PR-1 is OPEN, a counterexample until it passes")
    (funcall case d (list (rt-conj "RQ-1" :state "THEOREM" :implemented "2026-01-06")) (list (rt-proof "PR-1" "RQ-1"))
             "a THEOREM with no :USES:")
    (funcall case d (list (rt-conj "RQ-0") (rt-lemma "RQ-1" :uses "RQ-0")) (list (rt-proof "PR-1" "RQ-1"))
             "a LEMMA with :USES: is a THEOREM")
    (funcall case d (list (rt-conj "RQ-0") (rt-conj "RQ-1" :state "THEOREM" :uses "RQ-0" :implemented "2026-01-06"))
             (list (rt-proof "PR-1" "RQ-1"))
             "a THEOREM that uses RQ-0, which is CONJECTURE, not proven")
    (funcall case d (list (rt-lemma "RQ-1" :verify "unit/a")) (list (rt-proof "PR-1" "RQ-1"))
             "a LEMMA has no :VERIFY:; its tests are in its proofs")
    (funcall case d (list (rt-lemma "RQ-1")) (list (rt-proof "PR-1" "RQ-1") (rt-proof "PR-2" nil))
             "a proof with no :PROVES:")
    (funcall case d (list (rt-lemma "RQ-1")) (list (rt-proof "PR-1" "RQ-1 RQ-7"))
             ":PROVES: names RQ-7, which no conjecture has")
    (funcall case d (list (rt-lemma "RQ-1")) (list (rt-proof "PR-1" "RQ-1" :test nil))
             "a PASSED proof with no :TEST:")
    (funcall case d (list (rt-lemma "RQ-1")) (list (rt-proof "PR-1" "RQ-1" :implemented "2026-01-06"))
             "a proof with :IMPLEMENTED:")
    (funcall case d (list (rt-lemma "RQ-1")) (list (rt-proof "PR-1" "RQ-1" :state nil))
             "a proof's state is OPEN or PASSED, not none")
    ;; Only a file whose #+TODO: names PASSED reads it as a state.
    (rt-set d "theory.org" (concat (string-replace "REFUTED" "REFUTED PASSED" rt-math-head)
                                         (rt-lemma "RQ-1") (rt-conj "RQ-2" :state "PASSED")))
    (rt-set d "theory.proofs.org" (concat rt-proofs-head (rt-proof "PR-1" "RQ-1")))
    (rt-should-find (rt-run d "lint" "--no-tests") "PASSED is a proof's state")
    (funcall case d (list (rt-lemma "RQ-1") (rt-proof "PR-1" "RQ-1")) nil
             "a proof outside a .proofs.org file")
    (funcall case d (list (rt-conj "RQ-1" :implemented "2026-01-06")) nil
             "CONJECTURE with :IMPLEMENTED:; remove :IMPLEMENTED:, or prove it a LEMMA")
    (funcall case d (list (rt-lemma "RQ-1" :approved nil)) (list (rt-proof "PR-1" "RQ-1"))
             "LEMMA with no :APPROVED:")
    (funcall case d (list (rt-conj "RQ-1" :state "LEMMA")) (list (rt-proof "PR-1" "RQ-1"))
             "LEMMA with no :PROVEN:")
    ;; A proven lemma whose text changes goes back to CONJECTURE.
    (rt-set d "theory.org" (concat rt-math-head (rt-lemma "RQ-1")))
    (rt-set d "theory.proofs.org" (concat rt-proofs-head (rt-proof "PR-1" "RQ-1")))
    (rt-commit d "proven")
    (rt-set d "theory.org" (concat rt-math-head (replace-regexp-in-string "Statement" "Changed" (rt-lemma "RQ-1"))))
    (rt-git d "add" "-A")
    (rt-should-find (rt-env '("LEMMAX_TODAY=2026-01-05") (rt-run d "lint" "--staged" "--no-tests"))
                    "a LEMMA statement's text changed; make it CONJECTURE until the owner accepts it again")))

;;;; 01a2052f-a14c-7e72-8a8f-57ab97635a10: the proven date is called PROVEN

(defun rt-proven (text)
  "TEXT with its :IMPLEMENTED: line named :PROVEN:."
  (replace-regexp-in-string "^:IMPLEMENTED: " ":PROVEN:      " text t t))

(ert-deftest lemmax-proven-date ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-math-files (list (rt-proven (rt-lemma "RQ-1"))
                                         (rt-proven (rt-conj "RQ-2" :state "THEOREM" :uses "RQ-1" :implemented "2026-01-06"))
                                         (rt-lemma "RQ-3"))
                                   (list (rt-proof "PR-1" "RQ-1") (rt-proof "PR-2" "RQ-2") (rt-proof "PR-3" "RQ-3")))))
        (case (lambda (d reqs proofs want)
                (rt-set d "theory.org" (apply #'concat rt-math-head reqs))
                (rt-set d "theory.proofs.org" (apply #'concat rt-proofs-head proofs))
                (rt-should-find (rt-run d "lint" "--no-tests") want))))
    ;; :PROVEN: and the old :IMPLEMENTED: both hold a lemma's day.
    (rt-should-clean (rt-run d "lint"))
    (should (string-match-p "RQ-1 +LEMMA" (nth 1 (rt-run d "list"))))
    (funcall case d (list (rt-conj "RQ-1" :state "LEMMA")) (list (rt-proof "PR-1" "RQ-1"))
             "LEMMA with no :PROVEN:; add :PROVEN: with the day it was proven")
    (funcall case d (list (rt-proven (rt-conj "RQ-1" :implemented "2026-01-06"))) nil
             "CONJECTURE with :PROVEN:; remove :PROVEN:, or prove it a LEMMA")
    (funcall case d (list (concat (string-replace ":END:" ":PROVEN:      2026-01-06\n:END:" (rt-lemma "RQ-1"))))
             (list (rt-proof "PR-1" "RQ-1"))
             "both :PROVEN: and :IMPLEMENTED:; keep :PROVEN: and remove :IMPLEMENTED:")
    (funcall case d (list (rt-proven (rt-lemma "RQ-1"))) (list (rt-proven (rt-proof "PR-1" "RQ-1" :implemented "2026-01-06")))
             "a proof with :PROVEN:")
    ;; Only a LEMMA or THEOREM has :PROVEN:; an old DONE keeps :IMPLEMENTED:.
    (rt-set d "theory.org" (concat rt-head (rt-proven (rt-req "RQ-1" :state "DONE" :implemented "2026-01-06" :verify "unit/a"))))
    (rt-set d "theory.proofs.org" rt-proofs-head)
    (rt-should-find (rt-run d "lint" "--no-tests") "DONE with :PROVEN:; only a LEMMA or THEOREM has :PROVEN:")
    ;; A conjecture proven today is told to set :PROVEN:.
    (rt-set d "theory.org" (concat rt-math-head (rt-conj "RQ-1")))
    (rt-set d "theory.proofs.org" (concat rt-proofs-head (rt-proof "PR-1" "RQ-1")))
    (rt-commit d "conjecture")
    (rt-set d "theory.org" (concat rt-math-head (rt-proven (rt-lemma "RQ-1"))))
    (rt-git d "add" "-A")
    (rt-should-find (rt-env '("LEMMAX_TODAY=2026-01-07") (rt-run d "lint" "--staged" "--no-tests"))
                    "it turned DONE and :PROVEN: is not today; set :PROVEN: 2026-01-07")
    ;; migrate moves :IMPLEMENTED: on a LEMMA or THEOREM into Org's log, in a
    ;; migrated file too (01a20e7b-c7c0-77fc-bc53-bc963ab4843f).
    (rt-set d "theory.org" (concat rt-math-head (rt-lemma "RQ-1") (rt-conj "RQ-2")))
    (let ((out (nth 1 (rt-run d "migrate" "theory.org"))))
      (should (string-match-p "^\\+- State \"LEMMA\" +from \"THESIS\" +\\[2026-01-06 Tue\\]$" out))
      (should-not (string-match-p "^\\+:IMPLEMENTED:\\|^\\+:PROVEN:" out)))
    (rt-set d "theory.org" (concat rt-head (rt-req "RQ-1" :state "DONE" :implemented "2026-01-06" :verify "unit/a")))
    (should (string-match-p "^\\+- State \"LEMMA\" +from \"THESIS\" +\\[2026-01-06 Tue\\]$"
                            (nth 1 (rt-run d "migrate" "theory.org"))))))

;;;; 01a20369-391b-768e-8c98-180facc0ff77: lmx migrate

(defun rt-old-files ()
  (rt-files (rt-done "RQ-1") (rt-req "RQ-2" :state "DONE" :implemented "2026-01-06" :needs "RQ-1"
                                     :verify "unit/a" :verify+ "unit/b" :level 2)
            (rt-req "RQ-3") (rt-req "RQ-4" :state "DROPPED" :verify "unit/b")))

(ert-deftest lemmax-migrate-dry-run ()
  :tags '(timeout-60)
  (let* ((d (rt-repo (rt-old-files)))
         (before (with-temp-buffer (insert-file-contents (expand-file-name (rt-p "theory.org") d)) (buffer-string)))
         (r (rt-env '("LEMMAX_TODAY=2026-11-22") (rt-run d "migrate" "theory.org")))
         (out (nth 1 r)))
    (should (= 0 (nth 0 r)))
    (should (string-match-p "^-\\* DONE Title of RQ-1" out))
    ;; RQ-2 needed RQ-1: inverted, RQ-1 uses RQ-2 and is the theorem.
    (should (string-match-p "^\\+\\* THEOREM Title of RQ-1" out))
    (should (string-match-p "^\\+\\*\\* LEMMA Title of RQ-2" out))
    (should (string-match-p "^-:NEEDS: +RQ-1" out))
    ;; RQ-3 was approved: a THESIS (01a20e7b-c7c0-77fc-bc53-bc963ab4843f).
    (should (string-match-p "^\\+\\* THESIS Title of RQ-3" out))
    (should (string-match-p "^\\+\\* REFUTED Title of RQ-4" out))
    (should (string-match-p "^\\+:USES: +RQ-2" out))
    (should (string-match-p "^\\+#\\+TODO: CONJECTURE(c) THESIS(h!) | LEMMA(l!) THEOREM(t!) REFUTED(r!)" out))
    (should (string-match-p "^\\+\\+\\+ theories/t/theory.proofs.org" out))
    (should (string-match-p "^\\+:TEST: +unit/a unit/b" out))
    (should (string-match-p "^\\+\\* OPEN Proof: Title of RQ-4" out))
    (should-not (file-exists-p (expand-file-name (rt-p "theory.proofs.org") d)))
    (should (equal before (with-temp-buffer (insert-file-contents (expand-file-name (rt-p "theory.org") d)) (buffer-string))))
    (rt-set d "other.org" (concat rt-head (rt-req "RQ-8" :needs "RQ-9")))
    (should (string-match-p "RQ-8 needs RQ-9, which is not in this file; add :USES: RQ-8 to it by hand"
                            (nth 2 (rt-run d "migrate" "other.org"))))
    (should (= 1 (nth 0 (rt-run d "migrate"))))
    (should (= 1 (nth 0 (rt-run d "migrate" "--bogus" "theory.org"))))))

(ert-deftest lemmax-migrate-write ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-old-files) "2026-01-06")))
    (rt-should-clean (rt-run d "lint"))
    (should (string-match-p "wrote theories/t/theory.org\nwrote theories/t/theory.proofs.org"
                            (nth 1 (rt-env '("LEMMAX_TODAY=2026-11-22") (rt-run d "migrate" "--write" "theory.org")))))
    (let ((proofs (with-temp-buffer (insert-file-contents (expand-file-name (rt-p "theory.proofs.org") d)) (buffer-string))))
      ;; The settings move to #+PROPERTY: lines (01a20eb5-f066-7481-9fd1-9ac7705ef6b2).
      (should (string-match-p "^#\\+PROPERTY: LEMMAX_TESTS ./tests.sh" proofs))
      (should (string-match-p "^\\* PASSED Proof: Title of RQ-1\n:PROPERTIES:\n:ID: +[0-9a-f]\\{8\\}-[0-9a-f]\\{4\\}-7" proofs))
      (should (string-match-p ":PROVES: +RQ-1\n" proofs))
      (should (string-match-p ":CREATED: +2026-11-22" proofs)))
    (rt-git d "add" "-A")
    ;; The migrated file lints clean, and no lemma's text changed.
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-11-22") (rt-run d "lint" "--staged")))
    (rt-commit d "migrate")
    (should (string-match-p "Suspect: none" (nth 1 (rt-run d "trace"))))
    ;; Run again it changes nothing.
    (should (equal "" (nth 1 (rt-run d "migrate" "theory.org"))))))

;;;; 01a20369-393d-77bf-a35a-a1c03780a751: trace and list show proofs

(ert-deftest lemmax-math-trace-list ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-math-files (list (rt-lemma "RQ-1") (rt-conj "RQ-2"))
                                   (list (rt-proof "PR-1" "RQ-1 RQ-2") (rt-proof "PR-2" "RQ-2" :state "OPEN"))))))
    (let ((tr (nth 1 (rt-run d "trace" "PR-1"))))
      (should (string-match-p "^PR-1 PASSED" tr))
      (should (string-match-p "proves: RQ-1 RQ-2" tr)))
    (let ((tr (nth 1 (rt-run d "trace" "RQ-2"))))
      (should (string-match-p "proof: PR-1 PASSED" tr))
      (should (string-match-p "proof: PR-2 OPEN" tr)))
    (let ((out (nth 1 (rt-run d "list"))))
      (should (string-match-p "^Proofs (2)\n  PR-1 " out))
      (should-not (string-match-p "Approved and open ([0-9]+)\n  PR-" out)))
    (should (string-match-p "PR-2" (nth 1 (rt-run d "list" "--state" "open"))))
    (should (string-match-p "RQ-1" (nth 1 (rt-run d "list" "--state" "lemma"))))
    (should-not (string-match-p "RQ-1" (nth 1 (rt-run d "list" "--state" "conjecture"))))
    (should (string-match-p "PR-1" (nth 1 (rt-run d "list" "--state" "passed"))))
    (should-not (string-match-p "PR-" (nth 1 (rt-run d "list" "--ready"))))
    (let ((dot (nth 1 (rt-run d "trace" "--dot"))))
      (should (string-match-p "\"PR-1\" \\[label=[^]]*shape=ellipse\\]" dot))
      (should (string-match-p "\"PR-1\" -> \"RQ-2\" \\[style=dotted\\];" dot)))))

;;;; 01a2038d-cc5f-7324-8de8-1b067284e640 and the rest: tasks, notes, axioms, task ids

(defconst rt-tasks-head "#+title: Tasks\n#+TODO: TODO | DONE CANCELLED\n#+LEMMAX_TESTS: ./tests.sh\n#+LEMMAX_CODE: src/\n\n")
(defconst rt-notes-head "#+title: Notes\n#+LEMMAX_TESTS: ./tests.sh\n\n")

(cl-defun rt-task (id &key (state "TODO") for)
  (concat "* " (if state (concat state " ") "") "Task " id "\n:PROPERTIES:\n:ID:          " id "\n"
          (if for (format ":FOR:         %s\n" for) "")
          ":CREATED:     2026-01-05\n:LAST_EDITED: 2026-01-05\n:END:\nTidy it.\n"))

(cl-defun rt-note (id &key about state)
  (concat "* " (if state (concat state " ") "") "Note " id "\n:PROPERTIES:\n:ID:          " id "\n"
          (if about (format ":ABOUT:       %s\n" about) "") ":END:\nA thought.\n"))

(defun rt-kinds-files (&rest extra)
  (append (rt-math-files (list (rt-lemma "RQ-1")) (list (rt-proof "PR-1" "RQ-1"))) extra))

(ert-deftest lemmax-tasks-file ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-kinds-files (cons "dev.tasks.org" (concat rt-tasks-head (rt-task "TK-1" :for "RQ-1")
                                                                    (rt-task "TK-2" :state "DONE")
                                                                    (rt-task "TK-3" :state "CANCELLED")))))))
    (rt-should-clean (rt-run d "lint"))
    (let ((out (nth 1 (rt-run d "list"))))
      (should (string-match-p "^Tasks (3)\n  TK-1 " out))
      (should (string-match-p "; 3 tasks" out)))
    (should (string-match-p "TK-1" (nth 1 (rt-run d "list" "--state" "todo"))))
    (should (string-match-p "TK-3" (nth 1 (rt-run d "list" "--state" "cancelled"))))
    (should (string-match-p "for: RQ-1" (nth 1 (rt-run d "trace" "TK-1"))))
    (rt-set d "dev.tasks.org" (concat rt-tasks-head (rt-task "TK-1" :for "RQ-9")))
    (rt-should-find (rt-run d "lint" "--no-tests") ":FOR: names RQ-9, which no record has")
    (rt-set d "dev.tasks.org" (concat rt-tasks-head (rt-task "TK-1" :state nil)))
    (rt-should-find (rt-run d "lint" "--no-tests") "a task's state is TODO, DONE or CANCELLED, not none")))

(ert-deftest lemmax-notes-file ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-kinds-files (cons "ideas.notes.org" (concat rt-notes-head (rt-note "NT-1" :about "RQ-1 PR-1")))))))
    (rt-should-clean (rt-run d "lint"))
    (should (string-match-p "^Notes (1)\n  NT-1 " (nth 1 (rt-run d "list"))))
    (should (string-match-p "about: RQ-1 PR-1" (nth 1 (rt-run d "trace" "NT-1"))))
    (rt-set d "ideas.notes.org" (concat rt-notes-head (rt-note "NT-1" :about "RQ-7")))
    (rt-should-find (rt-run d "lint" "--no-tests") ":ABOUT: names RQ-7, which no record has")
    (rt-set d "ideas.notes.org" (concat "#+TODO: TODO | DONE\n" rt-notes-head (rt-note "NT-1" :state "TODO")))
    (rt-should-find (rt-run d "lint" "--no-tests") "a note has no state, not TODO")))

(ert-deftest lemmax-axioms ()
  :tags '(timeout-60)
  (let* ((ax "* AXIOM Git\n:PROPERTIES:\n:ID:          AX-1\n:CREATED:     2026-01-05\n:LAST_EDITED: 2026-01-05\n:END:\nSee [[file:rules/git.md][Git]].\n")
         (d (rt-repo (append (rt-kinds-files (cons "axioms.org" (concat "#+TODO: | AXIOM\n#+LEMMAX_TESTS: ./tests.sh\n\n" ax)))
                             (list (cons "rules/git.md" "# Git\n"))))))
    (rt-should-clean (rt-run d "lint"))
    (should (string-match-p "^Axioms (1)\n  AX-1 " (nth 1 (rt-run d "list"))))
    (should (string-match-p "AX-1" (nth 1 (rt-run d "list" "--state" "axiom"))))
    ;; A theorem may use an axiom.
    (rt-set d "theory.org" (concat rt-math-head (rt-conj "RQ-1" :state "THEOREM" :uses "AX-1" :implemented "2026-01-06")))
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    (rt-set d "theory.proofs.org" (concat rt-proofs-head (rt-proof "PR-1" "RQ-1 AX-1")))
    (rt-should-find (rt-run d "lint" "--no-tests") ":PROVES: names the axiom AX-1; an axiom is accepted without proof")))

;; lemma: 01a20757-95c1-70d9-882a-875672207343
(ert-deftest lemmax-definition-headings ()
  :tags '(timeout-60)
  (let* ((df "* DEFINITION Statement\n:PROPERTIES:\n:ID:          DF-1\n:CREATED:     2026-01-05\n:LAST_EDITED: 2026-01-05\n:END:\nAny item, whatever its state.\n")
         (d (rt-repo (rt-kinds-files (cons "definitions.org" (concat "#+TODO: | DEFINITION\n#+LEMMAX_TESTS: ./tests.sh\n\n" df))))))
    ;; A definition needs no approval, proven day, proof or code marker.
    (rt-should-clean (rt-run d "lint"))
    (should (string-match-p "^Definitions (1)\n  DF-1 " (nth 1 (rt-run d "list"))))
    (should (string-match-p "DF-1" (nth 1 (rt-run d "list" "--state" "definition"))))
    (should (string-match-p "1 definition" (nth 1 (rt-run d "list"))))
    ;; A lemma and a theorem may use a definition, which counts as proven.
    (rt-set d "theory.org" (concat rt-math-head (rt-lemma "RQ-1" :uses "DF-1")
                                         (rt-conj "RQ-2" :state "THEOREM" :uses "DF-1 RQ-1" :implemented "2026-01-06")))
    (rt-set d "theory.proofs.org" (concat rt-proofs-head (rt-proof "PR-1" "RQ-1") (rt-proof "PR-2" "RQ-2")))
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    ;; A lemma that uses more than definitions is still a theorem.
    (rt-set d "theory.org" (concat rt-math-head (rt-lemma "RQ-1" :uses "DF-1 RQ-2") (rt-lemma "RQ-2")))
    (rt-should-find (rt-run d "lint" "--no-tests") "a LEMMA with :USES: is a THEOREM")
    ;; A proof never proves a definition.
    (rt-set d "theory.org" (concat rt-math-head (rt-lemma "RQ-1")))
    (rt-set d "theory.proofs.org" (concat rt-proofs-head (rt-proof "PR-1" "RQ-1 DF-1")))
    (rt-should-find (rt-run d "lint" "--no-tests")
                    ":PROVES: names the definition DF-1; a definition is accepted without proof")))

(ert-deftest lemmax-commit-task-id ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-kinds-files (cons "dev.tasks.org" (concat rt-tasks-head (rt-task "TK-1")))))))
    (rt-set d "src/x.clj" "(ns x) ;; tidy\n")
    (rt-git d "add" "-A")
    (rt-set d "msg" "refactor: tidy (TK-1)\n")
    (rt-should-clean (rt-run d "commit-msg" "msg"))
    (rt-set d "msg" "refactor: tidy\n")
    (rt-should-find (rt-run d "commit-msg" "msg") "names no statement id")))

;;;; 01a2039c-9e67-74bb-9ac4-63eac14f1e7c: tags declared, nested, inherited

(defun rt-tag-files (tags-line body)
  (rt-files-with-head (concat "#+title: T\n#+TODO: OPEN | DONE DROPPED\n" tags-line
                              "#+LEMMAX_TESTS: ./tests.sh\n#+LEMMAX_CODE: src/\n\n")
                      body))

(defun rt-files-with-head (head body)
  (list (cons "theory.org" (concat head body))
        (cons "tests.sh" (rt-tests-sh "unit/a" "unit/b"))
        (cons "src/x.clj" "(ns x)\n")))

(defun rt-tagged (id tags &optional level)
  (replace-regexp-in-string "\\`\\(\\*+ OPEN Title of [^\n]*\\)" (concat "\\1 " tags)
                            (rt-req id :level (or level 1))))

(ert-deftest lemmax-tags-declared ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-tag-files "#+TAGS: ui other\n" (rt-tagged "RQ-1" ":ui:")))))
    (rt-should-clean (rt-run d "lint"))
    (rt-set d "theory.org" (concat "#+TAGS: ui\n#+LEMMAX_TESTS: ./tests.sh\n" (rt-tagged "RQ-1" ":nope:")))
    (rt-should-find (rt-run d "lint" "--no-tests") "the tag nope is not declared")
    (rt-set d "theory.org" (concat "#+TAGS: ui\n#+FILETAGS: :zz:\n#+LEMMAX_TESTS: ./tests.sh\n" (rt-req "RQ-1")))
    (rt-should-find (rt-run d "lint" "--no-tests") "the file tag zz is not declared")
    ;; A tag edit is not a text change.
    (rt-set d "theory.org" (concat "#+TAGS: ui other\n#+LEMMAX_TESTS: ./tests.sh\n" (rt-done "RQ-1")))
    (rt-commit d "done")
    (rt-set d "theory.org" (concat "#+TAGS: ui other\n#+LEMMAX_TESTS: ./tests.sh\n"
                                         (replace-regexp-in-string "\\`\\(\\* DONE Title of RQ-1\\)" "\\1 :ui:" (rt-done "RQ-1"))))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-11-22") (rt-run d "lint" "--staged" "--no-tests")))))

(ert-deftest lemmax-tags-groups ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-tag-files "#+TAGS: [ ui : button menu ] [ button : big ]\n"
                                  (concat (rt-tagged "RQ-1" ":big:") (rt-tagged "RQ-2" ":menu:"))))))
    (rt-should-clean (rt-run d "lint"))
    ;; A group matches its children at depth 2.
    (let ((out (nth 1 (rt-run d "list" "--tag" "ui"))))
      (should (string-match-p "RQ-1" out)) (should (string-match-p "RQ-2" out)))
    (let ((out (nth 1 (rt-run d "list" "--tag" "button"))))
      (should (string-match-p "RQ-1" out)) (should-not (string-match-p "RQ-2" out)))
    (rt-set d "theory.org" (concat "#+TAGS: [ a : b ] [ b : a ]\n#+LEMMAX_TESTS: ./tests.sh\n" (rt-req "RQ-1")))
    (rt-should-find (rt-run d "lint" "--no-tests") "the tag group [ab] holds itself, a cycle")))

(ert-deftest lemmax-tags-inherit ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-tag-files "#+TAGS: ui other\n#+FILETAGS: :other:\n"
                                  (concat (rt-tagged "RQ-1" ":ui:") (rt-req "RQ-2" :level 2) (rt-req "RQ-3"))))))
    (rt-should-clean (rt-run d "lint"))
    (let ((out (nth 1 (rt-run d "list" "--tag" "ui"))))
      (should (string-match-p "RQ-1" out)) (should (string-match-p "RQ-2" out)) (should-not (string-match-p "RQ-3" out)))
    (should (string-match-p "RQ-3" (nth 1 (rt-run d "list" "--tag" "other"))))))

;;;; 01a2039c-9e67-74bb-9ac4-63eb06d24a3f: --tag filters

(ert-deftest lemmax-tags-filter ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-tag-files "#+TAGS: ui cli\n"
                                  (concat (rt-tagged "RQ-1" ":ui:cli:") (rt-tagged "RQ-2" ":ui:"))))))
    (let ((out (nth 1 (rt-run d "list" "--tag" "ui" "--tag" "cli"))))
      (should (string-match-p "RQ-1" out)) (should-not (string-match-p "RQ-2 " out)))
    (let ((out (nth 1 (rt-run d "trace" "--tag" "cli"))))
      (should (string-match-p "^RQ-1 " out)) (should-not (string-match-p "^RQ-2 " out)))
    (should (string-match-p "^RQ-2 " (nth 1 (rt-run d "trace" "--tag" "ui"))))))

;;;; 01a203a6-a702-71c0-8239-e0d41380d2dd: link properties take id: links

(ert-deftest lemmax-id-link-props ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-math-files (list (rt-lemma "RQ-1") (rt-conj "RQ-2" :state "THEOREM" :uses "[[id:RQ-1][the first]]" :implemented "2026-01-06"))
                                   (list (rt-proof "PR-1" "[[id:RQ-1][the first]] [[id:RQ-2]]"))))))
    (rt-should-clean (rt-run d "lint"))
    (should (string-match-p "uses: RQ-1" (nth 1 (rt-run d "trace" "RQ-2"))))
    (should (string-match-p "proves: RQ-1 RQ-2" (nth 1 (rt-run d "trace" "PR-1"))))
    (rt-set d "theory.proofs.org" (concat rt-proofs-head (rt-proof "PR-1" "[[id:RQ-1]] [[id:RQ-9][gone]] RQ-2")))
    (rt-should-find (rt-run d "lint" "--no-tests") ":PROVES: names RQ-9, which no conjecture has")
    ;; migrate --links writes links.
    (let ((d2 (rt-repo (rt-old-files))))
      (let ((out (nth 1 (rt-env '("LEMMAX_TODAY=2026-11-22") (rt-run d2 "migrate" "--links" "theory.org")))))
        (should (string-match-p "^\\+:USES: +\\[\\[id:RQ-2\\]\\[Title of RQ-2\\]\\]" out))
        (should (string-match-p "^\\+:PROVES: +\\[\\[id:RQ-1\\]\\[Title of RQ-1\\]\\]" out))))))

;;;; 01a203a6-a716-738e-a95b-18086050d5eb: ORDERED and BLOCKER

(ert-deftest lemmax-ordered-blocker ()
  :tags '(timeout-60)
  (let* ((parent "* CONJECTURE Parent\n:PROPERTIES:\n:ID:          RQ-0\n:ORDERED:     t\n:CREATED:     2026-01-05\n:LAST_EDITED: 2026-01-05\n:END:\n")
         (d (rt-repo (rt-math-files (list parent (rt-lemma "RQ-1" :level 2) (rt-conj "RQ-2" :level 2))
                                    (list (rt-proof "PR-1" "RQ-1"))))))
    (rt-should-clean (rt-run d "lint"))
    (rt-set d "theory.org" (concat rt-math-head parent (rt-conj "RQ-2" :level 2) (rt-lemma "RQ-1" :level 2)))
    (rt-should-find (rt-run d "lint" "--no-tests") "ORDERED: proven before its earlier sibling RQ-2, which is CONJECTURE")
    (rt-set d "theory.org"
            (concat rt-math-head (rt-lemma "RQ-1")
                    (replace-regexp-in-string ":END:" ":BLOCKER:     RQ-9\n:END:"
                                              (rt-conj "RQ-3" :state "THEOREM" :uses "RQ-1" :implemented "2026-01-06"))))
    (rt-set d "theory.proofs.org" (concat rt-proofs-head (rt-proof "PR-1" "RQ-1 RQ-3")))
    (rt-should-find (rt-run d "lint" "--no-tests") ":BLOCKER: and :USES: name different ids")))

;;;; 01a203a6-a729-7420-980a-1702a0de05ad: a LOGBOOK is not the text

(ert-deftest lemmax-logbook ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-files (rt-done "RQ-1") (rt-req "RQ-2" :state "DONE" :implemented "2026-01-06" :verify "unit/a" :needs "RQ-1"))
                    "2026-01-06")))
    (rt-set d "theory.org"
            (concat rt-head
                    (replace-regexp-in-string ":END:\n" ":END:\n:LOGBOOK:\n- State \"DONE\"       from \"OPEN\"       [2026-01-06 Tue 10:00]\n:END:\n"
                                              (rt-done "RQ-1"))
                    (rt-req "RQ-2" :state "DONE" :implemented "2026-01-06" :verify "unit/a" :needs "RQ-1")))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-11-22") (rt-run d "lint" "--staged" "--no-tests")))
    (rt-commit d "log")
    (should (string-match-p "Suspect: none" (nth 1 (rt-run d "trace"))))
    (should-not (string-match-p "State \"DONE\"" (nth 1 (rt-run d "trace" "RQ-1"))))))

;;;; 01a203a6-a73d-7772-a4cb-fc4917fefd50: lmx archive

(ert-deftest lemmax-archive ()
  :tags '(timeout-60)
  (let ((d (rt-repo (append (rt-math-files (list (rt-lemma "RQ-1") (rt-conj "RQ-2" :state "REFUTED"))
                                           (list (rt-proof "PR-1" "RQ-1")))
                            (list (cons "dev.tasks.org" (concat rt-tasks-head (rt-task "TK-1" :state "DONE")
                                                                (rt-task "TK-2") (rt-task "TK-3" :state "CANCELLED"))))))))
    (let ((out (nth 1 (rt-env '("LEMMAX_TODAY=2026-11-22") (rt-run d "archive" "theory.org")))))
      (should (string-match-p "would move theories/t/theory.org:[0-9]+ RQ-2 REFUTED" out))
      (should-not (string-match-p "RQ-1" out)))
    (should-not (file-exists-p (expand-file-name (rt-p "theory_archive.org") d)))
    (rt-env '("LEMMAX_TODAY=2026-11-22") (rt-run d "archive" "--write" "theory.org"))
    (let ((a (with-temp-buffer (insert-file-contents (expand-file-name (rt-p "theory_archive.org") d)) (buffer-string))))
      (should (string-match-p "^#\\+LEMMAX_TESTS: ./tests.sh" a))
      (should (string-match-p "^\\* REFUTED Title of RQ-2" a)))
    (should-not (string-match-p "RQ-2" (with-temp-buffer (insert-file-contents (expand-file-name (rt-p "theory.org") d)) (buffer-string))))
    (let ((out (nth 1 (rt-env '("LEMMAX_TODAY=2026-11-22") (rt-run d "archive" "--write" "dev.tasks.org")))))
      (should (string-match-p "moved theories/t/dev.tasks.org:[0-9]+ TK-1 DONE" out))
      (should (string-match-p "TK-3 CANCELLED" out))
      (should-not (string-match-p "TK-2" out)))
    (should (file-exists-p (expand-file-name (rt-p "dev_archive.tasks.org") d)))
    ;; Links into the archive resolve, and ids stay unique across both.
    (rt-set d "ideas.notes.org" (concat rt-notes-head (rt-note "NT-1" :about "RQ-2 TK-1")))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-11-22") (rt-run d "lint" "--staged" "--no-tests")))
    (rt-set d "theory.org" (concat rt-math-head (rt-lemma "RQ-1") (rt-conj "RQ-2")))
    (rt-should-find (rt-run d "lint" "--no-tests") "used twice")))

;;;; 01a203a6-a752-75ed-8359-a8147e95a33d: lmx publish

(ert-deftest lemmax-publish ()
  :tags '(timeout-60)
  (let* ((d (rt-repo (rt-math-files (list (replace-regexp-in-string "Statement\\." "See [[id:PR-1][its proof]]." (rt-lemma "RQ-1") t))
                                    (list (rt-proof "PR-1" "RQ-1")))))
         (r (rt-run d "publish")))
    (should (= 0 (nth 0 r)))
    (should (string-match-p "^theories/_site/t/theory.html$" (nth 1 r)))
    (let ((html (with-temp-buffer (insert-file-contents (expand-file-name "theories/_site/t/theory.html" d)) (buffer-string))))
      (should (string-match-p "href=\"theory.proofs.html#ID-PR-1\"" html)))
    (should (equal "*\n" (with-temp-buffer (insert-file-contents (expand-file-name "theories/_site/.gitignore" d)) (buffer-string))))
    (should (equal "" (nth 1 (rt-git d "status" "--porcelain"))))
    (rt-run d "publish" "--out" "site")
    (should (file-exists-p (expand-file-name "site/t/theory.proofs.html" d)))))

;;;; 01a203a6-a766-76c6-9931-753ee75e9318: SETUPFILE carries a file's keywords

(ert-deftest lemmax-setupfile ()
  :tags '(timeout-60)
  (let ((d (rt-repo (list (cons "lemmax.setup" "#+TODO: CONJECTURE | LEMMA THEOREM REFUTED\n#+TAGS: ui\n#+LEMMAX_TESTS: ./tests.sh\n#+LEMMAX_CODE: src/\n")
                          (cons "reqs/theory.org" (concat "#+SETUPFILE: ../lemmax.setup\n\n" (rt-tagged "RQ-1" ":ui:")))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))
                          (cons "src/x.clj" "(ns x)\n")))))
    (rt-should-clean (rt-run d "lint"))
    (should (string-match-p "RQ-1" (nth 1 (rt-run d "list" "--tag" "ui"))))
    ;; The setup's #+LEMMAX_CODE: holds: a code commit names an id.
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-git d "add" "-A")
    (rt-set d "msg" "fix: no id\n")
    (rt-should-find (rt-run d "commit-msg" "msg") "names no statement id")
    ;; The setup's tags are the declared list.
    (rt-set d "reqs/theory.org" (concat "#+SETUPFILE: ../lemmax.setup\n\n" (rt-tagged "RQ-1" ":zz:")))
    (rt-should-find (rt-run d "lint" "--no-tests") "the tag zz is not declared")))

;;;; 01a203a6-a779-73fc-8abf-99f8c8816867: every footnote has a definition

(ert-deftest lemmax-footnotes ()
  :tags '(timeout-60)
  (let ((d (rt-repo (rt-files (rt-req "RQ-1" :body "Uses a rule.[fn:rule] And one inline.[fn:x: here] And [fn:: anon].\n\n[fn:rule] The rule.\n")))))
    (rt-should-clean (rt-run d "lint"))
    (rt-set d "theory.org" (concat rt-head (rt-req "RQ-1" :body "Uses a rule.[fn:gone] Not =[fn:code]=.\n")))
    (let ((r (rt-run d "lint" "--no-tests")))
      (rt-should-find r "theory.org:[0-9]+: RQ-1: the footnote fn:gone has no definition")
      (should-not (string-match-p "fn:code" (nth 2 r))))))

;;;; 01a203c1-983f-77e1-a367-92ea000ab72f and 01a203c1-983f-77e1-a367-92eb7cba2954: speed

(ert-deftest lemmax-run-time ()
  :tags '(timeout-60 alone)
  ;; One real run, launcher and all, on a small repo: well under the old 1.2 s.
  (let* ((d (rt-repo (rt-files (rt-req "RQ-1"))))
         (start (float-time)) (r (rt-run-proc d "list")) (took (- (float-time) start)))
    (should (= 0 (nth 0 r)))
    (should (< took 0.9))))

(ert-deftest lemmax-in-process ()
  ;; rt-run gives what the launcher gives: output, findings and exit code.
  (let ((d (rt-repo (rt-files (rt-req "RQ-1" :created nil)))))
    (let ((a (rt-run d "lint" "--no-tests")) (b (rt-run-proc d "lint" "--no-tests")))
      (should (equal a b))
      (should (= 1 (nth 0 a))))
    (should (equal (rt-run d "list") (rt-run-proc d "list")))
    (should (equal (rt-run d "bogus") (rt-run-proc d "bogus")))))

;;;; plan (01a204fc-d718-7e50-95a3-4ca72898a15b)

;; lemma: 01a204fc-d718-7e50-95a3-4ca72898a15b
(defun rt-plan-ids (out)
  "The step ids of plan's text OUT, in order."
  (let ((pos 0) ids)
    (while (string-match "^Step [0-9]+: \\([^ ]+\\)" out pos)
      (push (match-string 1 out) ids)
      (setq pos (match-end 0)))
    (nreverse ids)))

(defun rt-prio (prio conj)
  "CONJ, a heading from rt-conj, with priority PRIO after its state."
  (replace-regexp-in-string "\\` *\\(\\*+ [A-Z]+\\) " (concat "\\1 [#" prio "] ") conj))

(ert-deftest lemmax-plan-order ()
  (let* ((d (rt-repo (rt-math-files (list (rt-conj "RQ-3" :state "THEOREM" :uses "RQ-2 RQ-1" :implemented "2026-01-06")
                                          (rt-conj "RQ-2" :state "THEOREM" :uses "RQ-1" :implemented "2026-01-06")
                                          (rt-lemma "RQ-1")
                                          (rt-conj "RQ-4"))
                                    (list (rt-proof "PR-1" "RQ-1") (rt-proof "PR-2" "RQ-2") (rt-proof "PR-3" "RQ-3" :test "unit/b")))))
         (r (rt-run d "plan")))
    (should (= 0 (nth 0 r)))
    (should (equal '("RQ-1" "RQ-2" "RQ-3") (rt-plan-ids (nth 1 r))))
    (should (string-match-p "uses: RQ-2 RQ-1" (nth 1 r)))
    (should (string-match-p "| Statement\\." (nth 1 r)))
    (should (string-match-p "proof PR-3 PASSED: unit/b" (nth 1 r)))
    (should (string-match-p "Total: 3 steps" (nth 1 r)))
    (should (equal r (rt-run d "plan")))))

(ert-deftest lemmax-plan-ties ()
  (let* ((d (rt-repo (rt-math-files (list (rt-lemma "RQ-5")
                                          (rt-prio "B" (rt-lemma "RQ-4"))
                                          (rt-prio "A" (rt-lemma "RQ-9"))
                                          (rt-lemma "RQ-2"))
                                    (list (rt-proof "PR-1" "RQ-5 RQ-4 RQ-9 RQ-2"))))))
    (should (equal '("RQ-9" "RQ-4" "RQ-2" "RQ-5") (rt-plan-ids (nth 1 (rt-run d "plan")))))))

(ert-deftest lemmax-plan-cycle ()
  (let* ((d (rt-repo (rt-math-files (list (rt-lemma "RQ-1" :uses "RQ-2") (rt-conj "RQ-2" :state "THEOREM" :uses "RQ-1" :implemented "2026-01-06") (rt-lemma "RQ-3"))
                                    (list (rt-proof "PR-1" "RQ-1 RQ-2 RQ-3")))))
         (r (rt-run d "plan")))
    (should (= 1 (nth 0 r)))
    (should (string-match-p ":USES: cycle: RQ-1 RQ-2" (nth 2 r)))
    (should-not (string-match-p "RQ-3" (nth 2 r)))))

(ert-deftest lemmax-plan-json ()
  (let* ((d (rt-repo (rt-math-files (list (rt-lemma "RQ-1") (rt-conj "RQ-2" :state "THEOREM" :uses "RQ-1" :implemented "2026-01-06"))
                                    (list (rt-proof "PR-1" "RQ-1 RQ-2")))))
         (j (json-parse-string (nth 1 (rt-run d "plan" "--json")) :object-type 'alist))
         (steps (alist-get 'steps j)))
    (should (= 1 (alist-get 'version j)))
    (should (= 2 (length steps)))
    (should (equal "RQ-2" (alist-get 'id (aref steps 1))))
    (should (equal ["RQ-1"] (alist-get 'uses (aref steps 1))))
    (should (equal "PR-1" (alist-get 'id (aref (alist-get 'proofs (aref steps 0)) 0))))
    (should (equal ["unit/a"] (alist-get 'test (aref (alist-get 'proofs (aref steps 0)) 0))))))

;;;; Coverage (01a204fc-dadb-7a6d-bef9-7ebadcbfc6cd)

;; lemma: 01a204fc-dcd2-7a9e-a3ab-d5f3376159e2
(defun rt-covered (from code &optional day extra)
  "A repo whose src/x.clj is CODE and whose config has :coverage-required-from FROM,
committed on DAY, with EXTRA files."
  (rt-repo (append (rt-math-files (list (rt-lemma "RQ-1")) (list (rt-proof "PR-1" "RQ-1")))
                   (list (cons "src/x.clj" code))
                   (and from (list (cons "lemmax/config.eld" (format "(:coverage-required-from %S)\n" from))))
                   extra)
           day))

(ert-deftest lemmax-coverage-code-before-marker ()
  :tags '(timeout-30)
  (rt-should-find (rt-run (rt-covered "2026-01-01" "(ns x)\n;; lemma: RQ-1\n") "lint" "--no-tests")
                  "src/x\\.clj:1: -: code above the file's first lemma: marker")
  (rt-should-clean (rt-run (rt-covered "2026-01-01" "#!/bin/sh\n# head\n\n;; lemma: RQ-1\n(ns x)\n;; lemma: RQ-1\n(defn f [])\n")
                           "lint" "--no-tests"))
  ;; A file of comments only holds no code.
  (rt-should-clean (rt-run (rt-covered "2026-01-01" ";; nothing yet\n") "lint" "--no-tests"))
  ;; No key: nothing is refused.
  (rt-should-clean (rt-run (rt-covered nil "(ns x)\n;; lemma: RQ-1\n") "lint" "--no-tests")))

(ert-deftest lemmax-coverage-proof-marker ()
  :tags '(timeout-30)
  (rt-should-clean (rt-run (rt-covered "2026-01-01" ";; lemma: RQ-1\n(ns x)\n" nil
                                       (list (cons "test/x_test.clj" ";; lemma: PR-1\n(ns x-test)\n")))
                           "lint" "--no-tests"))
  (rt-should-find (rt-run (rt-covered nil ";; lemma: PR-1\n(ns x)\n") "lint" "--no-tests")
                  "src/x\\.clj:1: PR-1: a marker outside tests names a proof"))

(ert-deftest lemmax-coverage-from-day ()
  :tags '(timeout-30)
  ;; Committed before the day, untouched since: listed, not refused.
  (let ((d (rt-covered "2026-06-01" "(ns x)\n" "2026-01-05")))
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    (should (equal "src/x.clj:1\n" (nth 1 (rt-run d "list" "--uncovered"))))
    ;; Changed since HEAD: refused.
    (rt-set d "src/x.clj" "(ns x)\n(defn g [])\n")
    (rt-should-find (rt-run d "lint" "--no-tests") "src/x\\.clj:1: -: code above"))
  ;; A day still to come refuses nothing.
  (rt-env '("LEMMAX_TODAY=2026-05-01")
    (rt-should-clean (rt-run (rt-covered "2026-06-01" "(ns x)\n") "lint" "--no-tests"))))

(ert-deftest lemmax-coverage-not-code ()
  :tags '(timeout-30)
  (let ((d (rt-covered "2026-01-01" ";; lemma: RQ-1\n(ns x)\n" nil
                       (list (cons "src/README.md" "Plain prose.\n") (cons "src/LICENSE" "MIT\n")
                             (cons "src/run" "#!/bin/sh\necho hi\n")))))
    (should (equal "src/run:2\n" (nth 1 (rt-run d "list" "--uncovered"))))))

;;;; Environment (01a204fc-dec1-7ac6-8408-c3a69aedfebd)

;; lemma: 01a204fc-e0b3-7557-a319-f3ab61c5bc52
(defun rt-env-repo (env)
  "A repo with one proven lemma and theory.env.org holding ENV."
  (rt-repo (append (rt-math-files (list (rt-lemma "RQ-1")) (list (rt-proof "PR-1" "RQ-1")))
                   (list (cons "theory.env.org" env)))))

(ert-deftest lemmax-env-toolchain-version ()
  :tags '(timeout-30)
  (rt-should-find (rt-run (rt-env-repo "* Toolchain\n** Emacs\n") "lint" "--no-tests")
                  "theory\\.env\\.org:2: -: toolchain Emacs has no :VERSION:")
  (rt-should-find (rt-run (rt-env-repo "* Tools\n** Emacs\n") "lint" "--no-tests")
                  "Tools is no environment section")
  (rt-should-clean (rt-run (rt-env-repo "* Toolchain\n** Emacs\n:PROPERTIES:\n:VERSION: 29.4\n:END:\n") "lint" "--no-tests")))

(ert-deftest lemmax-env-secret-no-value ()
  :tags '(timeout-30)
  (rt-should-clean (rt-run (rt-env-repo "* Secrets\n** API key\n:PROPERTIES:\n:WHERE: the macOS keychain\n:END:\n")
                           "lint" "--no-tests"))
  (rt-should-find (rt-run (rt-env-repo "* Secrets\n** API key\n:PROPERTIES:\n:WHERE: keychain\n:VALUE: sk-123\n:END:\n")
                          "lint" "--no-tests")
                  "secret API key holds more than its :WHERE:")
  (rt-should-find (rt-run (rt-env-repo "* Secrets\n** API key\nsk-123\n") "lint" "--no-tests")
                  "secret API key holds more than its :WHERE:"))

(ert-deftest lemmax-env-first-in-plan ()
  :tags '(timeout-30)
  (let* ((d (rt-env-repo (concat "* Setup\n** Install Emacs\nbrew install emacs\n"
                                 "* Toolchain\n** Emacs\n:PROPERTIES:\n:VERSION: 29.4\n:END:\n")))
         (out (nth 1 (rt-run d "plan")))
         (j (json-parse-string (nth 1 (rt-run d "plan" "--json")) :object-type 'alist))
         (steps (alist-get 'steps j)))
    (should (string-match-p "\\`Step 1: Toolchain: Emacs  version=29\\.4\n" out))
    (should (string-match-p "^Step 2: Setup: Install Emacs\n.*\n  | brew install emacs" out))
    (should (string-match-p "^Step 3: RQ-1 LEMMA" out))
    (should (string-match-p "Total: 3 steps" out))
    (should (equal "environment" (alist-get 'kind (aref steps 0))))
    (should (equal "29.4" (alist-get 'version (alist-get 'properties (aref steps 0)))))
    (should (equal "lemma" (alist-get 'kind (aref steps 2))))))

;;;; 01a20e7b-c7c0-77fc-bc53-bc963ab4843f: thesis and proof are Org states, dated by Org's log

;; lemma: 01a20e7b-c7c0-77fc-bc53-bc963ab4843f
(defconst rt-log-head
  "#+title: Invented\n#+TODO: CONJECTURE(c) THESIS(h!) | LEMMA(l!) THEOREM(t!) REFUTED(r!)\n#+STARTUP: logdrawer\n#+LEMMAX_TESTS: ./tests.sh\n#+LEMMAX_CODE: src/\n\n")

(defun rt-log (state from day)
  "The line Org itself writes for a change to STATE from FROM on DAY."
  (require 'org)
  (concat "- " (org-replace-escapes (cdr (assq 'state org-log-note-headings))
                                    (list (cons "%s" (format "\"%s\"" state)) (cons "%S" (format "\"%s\"" from))
                                          (cons "%t" (format "[%s]" day))))
          "\n"))

(cl-defun rt-logged (id &key (state "CONJECTURE") logs props (body "Statement.\n"))
  "A heading in the logged form: no :LAST_EDITED:, its LOGS in :LOGBOOK:."
  (concat "* " state " Title of " id "\n:PROPERTIES:\n"
          (format ":ID:          %s\n" id) ":CREATED:     2026-01-05\n" (or props "") ":END:\n"
          (if logs (concat ":LOGBOOK:\n" (apply #'concat logs) ":END:\n") "")
          body))

(defun rt-log-files (reqs proofs)
  (list (cons "theory.org" (apply #'concat rt-log-head reqs))
        (cons "theory.proofs.org" (apply #'concat rt-proofs-head proofs))
        (cons "tests.sh" (rt-tests-sh "unit/a" "unit/b"))
        (cons "src/x.clj" "(ns x)\n")))

(defconst rt-thesis-log (rt-log "THESIS" "CONJECTURE" "2026-01-05 Mon"))
(defconst rt-lemma-log (rt-log "LEMMA" "THESIS" "2026-01-06 Tue"))

(ert-deftest lemmax-thesis-ready ()
  :tags '(timeout-30)
  ;; Bullet 1: THESIS sits between CONJECTURE and the done states; list --ready
  ;; lists the theses, and an old file's approved CONJECTURE still.
  (let* ((d (rt-repo (rt-log-files (list (rt-logged "RQ-1" :state "THESIS" :logs (list rt-thesis-log))
                                         (rt-logged "RQ-2"))
                                   nil)
                     "2026-01-05"))
         (out (rt-list d "--ready")))
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    (should (string-match-p "^  RQ-1 +THESIS +approved" out))
    (should-not (string-match-p "RQ-2" out))
    (let ((rows (rt-json-rows (rt-list d "--json"))))
      (should (equal "2026-01-05" (alist-get 'approved (aref rows 0))))
      (should (equal "approved" (alist-get 'group (aref rows 0)))))
    (let ((e (rt-repo (rt-math-files (list (rt-conj "RQ-3") (rt-conj "RQ-4" :approved nil)) nil))))
      (should (string-match-p "RQ-3" (rt-list e "--ready")))
      (should-not (string-match-p "RQ-4" (rt-list e "--ready"))))))

(ert-deftest lemmax-thesis-log-dates ()
  :tags '(timeout-30)
  ;; Bullet 2: the accepted day is the newest log line into THESIS, the proven
  ;; day the newest into LEMMA or THEOREM; no :APPROVED: or :PROVEN: is needed.
  (let ((d (rt-repo (rt-log-files (list (rt-logged "RQ-1" :state "LEMMA"
                                                   :logs (list rt-lemma-log (rt-log "LEMMA" "THESIS" "2026-01-02 Fri")
                                                               rt-thesis-log)))
                                  (list (rt-proof "PR-1" "RQ-1")))
                    "2026-01-05")))
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    (let ((r (car (plist-get (lemmax--parse (with-temp-buffer (insert-file-contents (expand-file-name (rt-p "theory.org") d))
                                                                (buffer-string))
                                            "theory.org")
                             :statements))))
      (should (equal "2026-01-05" (plist-get r :approved)))
      (should (equal "2026-01-06" (plist-get r :implemented)))))
  ;; Never accepted: refused, as an old LEMMA with no :APPROVED:.
  (rt-should-find (rt-run (rt-repo (rt-log-files (list (rt-logged "RQ-1" :state "LEMMA" :logs (list rt-lemma-log)))
                                                 (list (rt-proof "PR-1" "RQ-1"))))
                          "lint" "--no-tests")
                  "LEMMA with no :APPROVED:; get the owner's approval, then make it THESIS")
  ;; No log line into LEMMA: no proven day.
  (rt-should-find (rt-run (rt-repo (rt-log-files (list (rt-logged "RQ-1" :state "LEMMA" :logs (list rt-thesis-log)))
                                                 (list (rt-proof "PR-1" "RQ-1"))))
                          "lint" "--no-tests")
                  "LEMMA with no :PROVEN:; set the state LEMMA again so Org logs")
  ;; Sent back to CONJECTURE, its old log lines are history, not dates.
  (rt-should-clean (rt-run (rt-repo (rt-log-files (list (rt-logged "RQ-1" :logs (list rt-lemma-log rt-thesis-log))) nil))
                           "lint" "--no-tests")))

(ert-deftest lemmax-thesis-git-edited-day ()
  :tags '(timeout-60)
  ;; Bullet 3: the last-edited day is git's, or today for a change not committed.
  (let ((d (rt-repo (rt-log-files (list (rt-logged "RQ-1" :state "LEMMA" :logs (list rt-lemma-log rt-thesis-log)))
                                  (list (rt-proof "PR-1" "RQ-1")))
                    "2026-01-05")))
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    ;; Bullet 4: a committed text change after the accepted day sends it back.
    (rt-set d "theory.org" (concat rt-log-head (rt-logged "RQ-1" :state "LEMMA" :logs (list rt-lemma-log rt-thesis-log)
                                                          :body "New statement.\n")))
    (rt-commit d "edit" "2026-01-10")
    (rt-should-find (rt-run d "lint" "--no-tests")
                    "theory\\.org:7: RQ-1: a LEMMA whose text changed 2026-01-10, after it was accepted 2026-01-05; make it CONJECTURE until the owner accepts it again")
    ;; Accepted again: clean.
    (rt-set d "theory.org" (concat rt-log-head (rt-logged "RQ-1" :state "LEMMA"
                                                          :logs (list (rt-log "LEMMA" "THESIS" "2026-01-11 Sun")
                                                                      (rt-log "THESIS" "CONJECTURE" "2026-01-11 Sun")
                                                                      rt-lemma-log rt-thesis-log)
                                                          :body "New statement.\n")))
    (rt-commit d "accept" "2026-01-11")
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    ;; A change not committed is today's.
    (rt-set d "theory.org" (concat rt-log-head (rt-logged "RQ-1" :state "LEMMA"
                                                          :logs (list (rt-log "LEMMA" "THESIS" "2026-01-11 Sun")
                                                                      (rt-log "THESIS" "CONJECTURE" "2026-01-11 Sun"))
                                                          :body "Newer statement.\n")))
    (rt-should-find (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--no-tests"))
                    "a LEMMA whose text changed 2026-02-01, after it was accepted 2026-01-11")
    ;; The bible older than the git day warns, with no :LAST_EDITED: anywhere.
    (rt-set d "theory.org" (concat rt-log-head (rt-logged "RQ-1" :state "LEMMA"
                                                          :logs (list (rt-log "LEMMA" "THESIS" "2026-01-11 Sun")
                                                                      (rt-log "THESIS" "CONJECTURE" "2026-01-11 Sun"))
                                                          :body "New statement.\n")))
    (rt-set d "theories/t/t.bible.html" "<html></html>\n")
    (rt-commit d "bible" "2026-01-08")
    (should (string-match-p "warning: the bible is older than the theory, edited 2026-01-10"
                            (nth 2 (rt-run d "lint" "--no-tests")))))
  ;; Archive reads git's day for a DONE task with no :LAST_EDITED:.
  (let ((d (rt-repo (append (rt-log-files (list (rt-logged "RQ-1")) nil)
                            (list (cons "dev.tasks.org"
                                        (concat "#+title: Tasks\n#+TODO: TODO | DONE CANCELLED\n#+STARTUP: logdrawer\n#+LEMMAX_TESTS: ./tests.sh\n\n"
                                                "* DONE Task TK-1\n:PROPERTIES:\n:ID:          TK-1\n:CREATED:     2026-01-05\n:END:\nTidy it.\n"))))
                    "2026-01-05")))
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    (should (string-match-p "would move theories/t/dev.tasks.org:[0-9]+ TK-1 DONE"
                            (nth 1 (rt-env '("LEMMAX_TODAY=2026-03-01") (rt-run d "archive" "dev.tasks.org")))))
    (should (equal "" (nth 1 (rt-env '("LEMMAX_TODAY=2026-01-20") (rt-run d "archive" "dev.tasks.org")))))))

(ert-deftest lemmax-thesis-staged-sent-back ()
  :tags '(timeout-30)
  ;; Bullet 4: a staged text change to a THESIS, LEMMA or THEOREM sends it back.
  (let ((d (rt-repo (rt-log-files (list (rt-logged "RQ-1" :state "THESIS" :logs (list rt-thesis-log))) nil))))
    (rt-set d "theory.org" (concat rt-log-head (rt-logged "RQ-1" :state "THESIS" :logs (list rt-thesis-log)
                                                          :body "New statement.\n")))
    (rt-git d "add" "-A")
    (rt-should-find (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests"))
                    "RQ-1: a THESIS statement's text changed; make it CONJECTURE until the owner accepts it again")
    ;; Back to CONJECTURE: no finding, and no :LAST_EDITED: is asked for.
    (rt-set d "theory.org" (concat rt-log-head (rt-logged "RQ-1" :logs (list rt-thesis-log) :body "New statement.\n")))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests")))
    ;; A new heading needs :CREATED: today, and no :LAST_EDITED:.
    (rt-set d "theory.org" (concat rt-log-head (rt-logged "RQ-1" :logs (list rt-thesis-log) :body "New statement.\n")
                                   (replace-regexp-in-string "2026-01-05" "2026-02-01" (rt-logged "RQ-2"))))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-02-01") (rt-run d "lint" "--staged" "--no-tests")))))

(ert-deftest lemmax-thesis-created-required ()
  :tags '(timeout-30)
  ;; Bullet 5: :CREATED: stays a property, required in the logged form too.
  (rt-should-find (rt-run (rt-repo (rt-log-files (list (replace-regexp-in-string ":CREATED: .*\n" "" (rt-logged "RQ-1"))) nil))
                          "lint" "--no-tests")
                  "RQ-1: no :CREATED:")
  ;; An old file still needs :LAST_EDITED:.
  (rt-should-find (rt-lint (rt-req "RQ-1" :last nil)) "no :LAST_EDITED:"))

(ert-deftest lemmax-thesis-old-and-both ()
  :tags '(timeout-30)
  ;; Bullet 6: old dates still read; both a log line and its property is refused.
  (rt-should-clean (rt-run (rt-repo (rt-math-files (list (rt-proven (rt-lemma "RQ-1")) (rt-conj "RQ-2"))
                                                   (list (rt-proof "PR-1" "RQ-1"))))
                           "lint" "--no-tests"))
  (rt-should-find (rt-run (rt-repo (rt-log-files (list (rt-logged "RQ-1" :state "THESIS" :logs (list rt-thesis-log)
                                                                  :props ":APPROVED:    2026-01-05\n"))
                                                 nil))
                          "lint" "--no-tests")
                  "RQ-1: both a log line into THESIS and :APPROVED:; keep the log line and remove :APPROVED:")
  (rt-should-find (rt-run (rt-repo (rt-log-files (list (rt-logged "RQ-1" :state "LEMMA" :logs (list rt-lemma-log rt-thesis-log)
                                                                  :props ":PROVEN:      2026-01-06\n"))
                                                 (list (rt-proof "PR-1" "RQ-1"))))
                          "lint" "--no-tests")
                  "RQ-1: both a log line into LEMMA or THEOREM and :PROVEN:"))

(ert-deftest lemmax-thesis-migrate ()
  :tags '(timeout-60)
  ;; Bullet 7: migrate moves the dates into Org's log lines, makes each approved
  ;; CONJECTURE a THESIS, deletes :LAST_EDITED:, and writes the #+TODO: where
  ;; the file reads it, here its setup file, with #+STARTUP: logdrawer.
  (let* ((head "#+title: Invented\n#+SETUPFILE: setup.org\n#+STARTUP: overview\n\n")
         (d (rt-repo (list (cons "setup.org" "#+TODO: CONJECTURE(c) | LEMMA(l) THEOREM(t) REFUTED(r)\n#+LEMMAX_TESTS: ./tests.sh\n#+LEMMAX_CODE: src/\n")
                           (cons "theory.org" (concat head (rt-proven (rt-lemma "RQ-1")) (rt-conj "RQ-2") (rt-conj "RQ-3" :approved nil)
                                                       (rt-conj "RQ-4" :approved "2026-01-02")))
                           (cons "theory.proofs.org" (concat rt-proofs-head (rt-proof "PR-1" "RQ-1")))
                           (cons "tests.sh" (rt-tests-sh "unit/a"))
                           (cons "src/x.clj" "(ns x)\n"))
                     "2026-01-05"))
         (r (rt-run d "migrate" "theory.org"))
         (out (nth 1 r)))
    (should (= 0 (nth 0 r)))
    (should (string-match-p (regexp-quote (concat "+:LOGBOOK:\n+" rt-lemma-log "+" rt-thesis-log "+:END:\n")) out))
    (should (string-match-p "^-:APPROVED: \\|^-:PROVEN: \\|^-:LAST_EDITED: " out))
    (should-not (string-match-p "^\\+:\\(?:APPROVED\\|PROVEN\\|LAST_EDITED\\):" out))
    (should (string-match-p "^\\+\\* THESIS Title of RQ-2" out))
    (should-not (string-match-p "^\\+\\* [A-Z]+ Title of RQ-3" out))
    ;; An edit after approval counts as accepted: RQ-4, approved 01-02 and
    ;; edited 01-05, is accepted on 01-05.
    (should (string-match-p "^\\+\\* THESIS Title of RQ-4" out))
    (should-not (string-match-p "^\\+.*\\[2026-01-02" out))
    (should (string-match-p "^\\+#\\+STARTUP: overview logdrawer$" out))
    (should (string-match-p "^\\+\\+\\+ theories/t/setup.org" out))
    (should (string-match-p "^\\+#\\+TODO: CONJECTURE(c) THESIS(h!) | LEMMA(l!) THEOREM(t!) REFUTED(r!)$" out))
    (should (string-match-p "wrote theories/t/theory.org\nwrote theories/t/setup.org"
                            (nth 1 (rt-run d "migrate" "--write" "theory.org"))))
    (rt-git d "add" "-A")
    ;; No lemma's text changed, the migrated file lints clean, and run again
    ;; migrate changes nothing.
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-01-06") (rt-run d "lint" "--staged" "--no-tests")))
    (rt-commit d "migrate" "2026-01-06")
    (rt-should-clean (rt-run d "lint" "--no-tests"))
    (should (string-match-p "RQ-2" (rt-list d "--ready")))
    (should (equal "" (nth 1 (rt-run d "migrate" "theory.org"))))))

(ert-deftest lemmax-thesis-logbook-not-text ()
  :tags '(timeout-30)
  ;; Bullet 8: :LOGBOOK: is not a heading's text: a new log line sends nothing back.
  (let ((d (rt-repo (rt-log-files (list (rt-logged "RQ-1" :state "THESIS" :logs (list rt-thesis-log)))
                                  (list (rt-proof "PR-1" "RQ-1")))
                    "2026-01-05")))
    (rt-set d "theory.org" (concat rt-log-head (rt-logged "RQ-1" :state "LEMMA" :logs (list rt-lemma-log rt-thesis-log))))
    (rt-git d "add" "-A")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-01-06") (rt-run d "lint" "--staged" "--no-tests")))))

(ert-deftest lemmax-thesis-migrate-kinds ()
  :tags '(timeout-30)
  ;; Bullet 7: a tasks or notes file keeps its states and dates; migrate moves
  ;; only its settings keywords (01a20eb5-f066-7481-9fd1-9ac7705ef6b2).
  (let ((d (rt-repo (append (rt-math-files (list (rt-conj "RQ-1")) nil)
                            (list (cons "dev.tasks.org" (concat rt-tasks-head (rt-task "TK-1" :state "DONE") (rt-task "TK-2")))
                                  (cons "dev.notes.org" (concat rt-notes-head (rt-note "NT-1"))))))))
    (dolist (f '("dev.tasks.org" "dev.notes.org"))
      (let ((r (rt-run d "migrate" f)))
        (should (= 0 (nth 0 r)))
        (let ((changed (cl-remove-if-not (lambda (l) (string-match-p "\\`[-+][^-+]" l)) (split-string (nth 1 r) "\n"))))
          (should changed)
          (should (cl-every (lambda (l) (string-match-p "\\`\\(?:-#\\+LEMMAX_[A-Z_]+: \\|\\+#\\+PROPERTY: LEMMAX_\\)" l)) changed)))))
    (rt-should-clean (rt-run d "lint" "--no-tests"))))

(ert-deftest lemmax-thesis-edited-day-follows-move ()
  :tags '(timeout-30)
  ;; Bullet 3: the last-edited day follows a file's move, and a link the move
  ;; rewrites to name the same file is no text change.
  (let ((d (rt-repo (list (cons "./old/theory.org"
                                (concat rt-log-head (rt-logged "RQ-1" :state "THESIS" :logs (list rt-thesis-log)
                                                               :body "See [[file:../src/x.clj][x]].\n")))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))
                          (cons "src/x.clj" "(ns x)\n"))
                    "2026-01-05")))
    (rt-git d "mv" "old/theory.org" "theory.org")
    (make-directory (expand-file-name "theories/t" d) t)
    (rt-git d "mv" "theory.org" "theories/t/theory.org")
    (rt-set d "theory.org" (concat rt-log-head (rt-logged "RQ-1" :state "THESIS" :logs (list rt-thesis-log)
                                                          :body "See [[file:../../src/x.clj][x]].\n")))
    (rt-commit d "move" "2026-01-09")
    (rt-should-clean (rt-env '("LEMMAX_TODAY=2026-01-20") (rt-run d "lint" "--no-tests")))
    ;; A real edit after the move still counts.
    (rt-set d "theory.org" (concat rt-log-head (rt-logged "RQ-1" :state "THESIS" :logs (list rt-thesis-log)
                                                          :body "See [[file:../../src/x.clj][x]] now.\n")))
    (rt-commit d "edit" "2026-01-10")
    (rt-should-find (rt-env '("LEMMAX_TODAY=2026-01-20") (rt-run d "lint" "--no-tests"))
                    "a THESIS whose text changed 2026-01-10, after it was accepted 2026-01-05")))

;;;; 01a20eb5-f066-7481-9fd1-9ac7705ef6b2: file settings are Org #+PROPERTY: lines

;; lemma: 01a20eb5-f066-7481-9fd1-9ac7705ef6b2
(defconst rt-prop-head
  "#+title: Invented requirements\n#+TODO: OPEN | DONE DROPPED\n#+PROPERTY: LEMMAX_TESTS ./tests.sh\n#+PROPERTY: LEMMAX_CODE src/\n\n"
  "`rt-head' with its settings as #+PROPERTY: lines, on the same lines.")

(defun rt-prop-files (head &rest reqs)
  (list (cons "theory.org" (apply #'concat head reqs))
        (cons "tests.sh" (rt-tests-sh "unit/a" "unit/b"))
        (cons "src/x.clj" "(ns x)\n")))

(defun rt-parse-in (d file)
  "FILE of the test repo D, parsed as lmx parses it, in D."
  (rt-load)
  (let ((default-directory (file-name-as-directory d)))
    (lemmax--parse (with-temp-buffer (insert-file-contents (rt-p file)) (buffer-string)) (rt-p file))))

(ert-deftest lemmax-settings-property ()
  :tags '(timeout-30)
  ;; Bullet 1: #+PROPERTY: LEMMAX_TESTS and LEMMAX_CODE opt a file in and set it up.
  (let ((d (rt-repo (rt-prop-files rt-prop-head (rt-done "RQ-1" :verify "unit/zzz")))))
    (rt-should-find (rt-run d "lint") "theory\\.org:6: RQ-1: :VERIFY: names unit/zzz, which the test command does not list")
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-git d "add" "-A")
    (should (= 1 (nth 0 (rt-commit-msg d "change it"))))
    (should (= 0 (nth 0 (rt-commit-msg d "change it (RQ-1)")))))
  (let ((info (rt-parse-in (rt-repo (rt-prop-files (concat rt-prop-head "#+PROPERTY: LEMMAX_TEST_PATHS spec/\n#+PROPERTY: LEMMAX_MARKERS_IN ../code\n")))
                           "theory.org")))
    (should (equal "./tests.sh" (plist-get info :tests)))
    (should (equal '("src/") (plist-get info :code)))
    (should (equal '("spec/") (plist-get info :test-paths)))
    (should (equal '("../code") (plist-get info :markers-in)))))

(ert-deftest lemmax-settings-setupfile-and-append ()
  :tags '(timeout-30)
  ;; Bullets 2 and 3: a setup file's #+PROPERTY: lines count, and NAME+ appends.
  (let* ((d (rt-repo (list (cons "setup.org" "#+PROPERTY: LEMMAX_TESTS ./tests.sh\n#+PROPERTY: LEMMAX_CODE src/\n")
                           (cons "theory.org" (concat "#+SETUPFILE: setup.org\n#+TODO: OPEN | DONE DROPPED\n#+PROPERTY: LEMMAX_CODE+ lib/\n\n"
                                                      (rt-done "RQ-1" :approved nil)))
                           (cons "tests.sh" (rt-tests-sh "unit/a"))
                           (cons "src/x.clj" "(ns x)\n"))))
         (info (rt-parse-in d "theory.org")))
    (should (equal '("src/" "lib/") (plist-get info :code)))
    (rt-should-find (rt-run d "lint" "--no-tests") "RQ-1: DONE with no :APPROVED:")))

(ert-deftest lemmax-settings-file-level-only ()
  :tags '(timeout-30)
  ;; Bullet 4: a LEMMAX_ setting in a heading's drawer is refused.
  (rt-should-find (rt-run (rt-repo (rt-prop-files rt-prop-head
                                                  (replace-regexp-in-string ":END:" ":LEMMAX_CODE: lib/\n:END:" (rt-req "RQ-1"))))
                          "lint" "--no-tests")
                  "theory\\.org:6: RQ-1: LEMMAX_CODE in a heading's :PROPERTIES: drawer; a setting is file-level only"))

(ert-deftest lemmax-settings-both-ways ()
  :tags '(timeout-30)
  ;; Bullet 5: old keywords still read; one setting set both ways is refused,
  ;; also when the setup file brings one of them.
  (rt-should-clean (rt-lint (rt-req "RQ-1")))
  (rt-should-find (rt-run (rt-repo (rt-prop-files (concat rt-prop-head "#+LEMMAX_CODE: lib/\n") (rt-req "RQ-1")))
                          "lint" "--no-tests")
                  "theory\\.org:1: -: LEMMAX_CODE is set both as #\\+LEMMAX_CODE: and as #\\+PROPERTY: LEMMAX_CODE")
  (rt-should-find (rt-run (rt-repo (list (cons "setup.org" "#+LEMMAX_TESTS: ./tests.sh\n")
                                         (cons "theory.org" (concat "#+SETUPFILE: setup.org\n#+TODO: OPEN | DONE DROPPED\n#+PROPERTY: LEMMAX_TESTS ./tests.sh\n\n" (rt-req "RQ-1")))
                                         (cons "tests.sh" (rt-tests-sh "unit/a"))))
                          "lint" "--no-tests")
                  "LEMMAX_TESTS is set both"))

(ert-deftest lemmax-settings-migrate ()
  :tags '(timeout-60)
  ;; Bullet 6: migrate moves each old keyword into a #+PROPERTY: line, in place,
  ;; in a theory file, its setup file, a setup file alone and a proofs file.
  (let* ((d (rt-repo (list (cons "setup.org" "#+title: s\n#+LEMMAX_TESTS: ./tests.sh\n#+TAGS: x\n")
                           (cons "theory.org" (concat "#+title: T\n#+SETUPFILE: setup.org\n#+TODO: CONJECTURE | LEMMA THEOREM REFUTED\n#+LEMMAX_CODE: src/\n\n" (rt-conj "RQ-1")))
                           (cons "theory.proofs.org" rt-proofs-head)
                           (cons "tests.sh" (rt-tests-sh "unit/a"))
                           (cons "src/x.clj" "(ns x)\n"))))
         (out (nth 1 (rt-run d "migrate" "theory.org"))))
    (should (string-match-p "^-#\\+LEMMAX_CODE: src/$" out))
    (should (string-match-p "^\\+#\\+PROPERTY: LEMMAX_CODE src/$" out))
    (should (string-match-p "^ #\\+title: s\n-#\\+LEMMAX_TESTS: ./tests.sh\n\\+#\\+PROPERTY: LEMMAX_TESTS ./tests.sh\n #\\+TAGS: x" out))
    (should (string-match-p "^-#\\+LEMMAX_TESTS: ./tests.sh\n-#\\+LEMMAX_CODE: src/\n\\+#\\+PROPERTY: LEMMAX_TESTS ./tests.sh\n\\+#\\+PROPERTY: LEMMAX_CODE src/"
                            (nth 1 (rt-run d "migrate" "theory.proofs.org"))))
    (rt-run d "migrate" "--write" "theory.org")
    (rt-run d "migrate" "--write" "theory.proofs.org")
    (rt-git d "add" "-A")
    (rt-should-clean (rt-run d "lint" "--staged" "--no-tests"))
    (should (equal "" (nth 1 (rt-run d "migrate" "setup.org"))))
    (let ((e (rt-repo (list (cons "setup.org" "#+LEMMAX_TESTS: ./tests.sh\n")))))
      (should (string-match-p "^\\+#\\+PROPERTY: LEMMAX_TESTS ./tests.sh$" (nth 1 (rt-run e "migrate" "setup.org")))))))

(ert-deftest lemmax-settings-opt-in ()
  :tags '(timeout-30)
  ;; Bullet 7: the hooks and lemmax_lint.py treat a #+PROPERTY: LEMMAX_TESTS
  ;; line, in a file or its setup file, as opted in.
  (let ((d (rt-hooked (rt-prop-files rt-prop-head (rt-req "RQ-1")))))
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-sh d "git" "add" "-A")
    (should (= 1 (nth 0 (rt-hook-commit d "change it"))))
    (should (= 0 (nth 0 (rt-hook-commit d "change it (RQ-1)")))))
  (should (string-match-p "^theories/t/theory\\.org:6: RQ-1: DONE with no :APPROVED:"
                          (rt-check (rt-repo (rt-prop-files rt-prop-head (rt-done "RQ-1" :approved nil))) "theories/t/theory.org\n")))
  (let ((d (rt-repo (list (cons "lemmax.setup" "#+TODO: OPEN | DONE DROPPED\n#+PROPERTY: LEMMAX_TESTS ./tests.sh\n")
                          (cons "theory.org" (concat "#+SETUPFILE: lemmax.setup\n\n" (rt-done "RQ-1" :approved nil)))
                          (cons "tests.sh" (rt-tests-sh "unit/a"))))))
    (should (string-match-p "RQ-1: DONE with no :APPROVED:" (rt-check d "theories/t/theory.org\n"))))
  ;; install-hooks writes the same test.
  (rt-load)
  (should (string-search lemmax--opted-re (lemmax--hook-text "pre-commit"))))

;;;; 01a20ed2-d34b-71f9-a19a-04bb7cc6cf6e: repo settings live in theories/setup.org

;; lemma: 01a20ed2-d34b-71f9-a19a-04bb7cc6cf6e
(defun rt-chain-files (root &rest reqs)
  "A repo whose theories/setup.org holds ROOT, read by theories/t/setup.org,
which holds the tests and code, read by theory.org with REQS."
  (list (cons "theories/setup.org" (concat "#+title: Repo settings\n" root))
        (cons "setup.org" "#+title: t settings\n#+SETUPFILE: ../setup.org\n#+PROPERTY: LEMMAX_TESTS ./tests.sh\n#+PROPERTY: LEMMAX_CODE src/\n")
        (cons "theory.org" (apply #'concat "#+title: T\n#+SETUPFILE: setup.org\n#+TODO: OPEN | DONE DROPPED\n\n" reqs))
        (cons "tests.sh" (rt-tests-sh "unit/a"))
        (cons "src/x.clj" "(ns x)\n")))

(ert-deftest lemmax-repo-settings-chain ()
  :tags '(timeout-30)
  ;; Bullets 1 and 2: the repo-wide settings reach a file through a nested
  ;; #+SETUPFILE: chain, theories/setup.org read by the project's setup.org.
  (let ((d (rt-repo (rt-chain-files "#+PROPERTY: LEMMAX_MARKERS_REQUIRED_FROM 2026-11-22\n"
                                    (rt-done "RQ-1" :implemented "2026-11-22")))))
    (rt-should-find (rt-run d "lint" "--no-tests") "RQ-1: DONE with no code marker")
    (rt-set d "src/x.clj" "(ns x)\n;; lemma: RQ-1\n")
    (rt-should-clean (rt-run d "lint" "--no-tests")))
  (rt-should-find (rt-run (rt-repo (rt-chain-files "#+PROPERTY: LEMMAX_COVERAGE_REQUIRED_FROM 2026-01-01\n"
                                                   (rt-done "RQ-1")))
                          "lint" "--no-tests")
                  "src/x\\.clj:1: -: code above the file's first lemma: marker")
  (rt-should-find (rt-run (rt-repo (rt-chain-files "#+PROPERTY: LEMMAX_MARKERS_REQUIRED_FROM 22 Nov\n" (rt-done "RQ-1")))
                          "lint" "--no-tests")
                  "LEMMAX_MARKERS_REQUIRED_FROM is not a day: 22 Nov"))

(ert-deftest lemmax-repo-settings-repos ()
  :tags '(timeout-30)
  ;; Bullet 1: list --all reads LEMMAX_REPOS from theories/setup.org at the root.
  (let* ((base (rt-tmp)) (here (expand-file-name "here" base)) (far (expand-file-name "far" base)))
    (make-directory (expand-file-name "other" far) t)
    (make-directory here)
    (dolist (d (list here (expand-file-name "other" far))) (rt-git d "init" "-q" "-b" "main"))
    (rt-write (expand-file-name "other" far) (rt-files (rt-req "OT-1")))
    (rt-commit (expand-file-name "other" far) "start")
    (rt-write here (rt-chain-files (format "#+PROPERTY: LEMMAX_REPOS %s\n" far) (rt-req "RQ-1")))
    (rt-commit here "start")
    (let ((out (nth 1 (rt-env '("LEMMAX_REPOS=/nonexistent") (rt-run here "list" "--all")))))
      (should (string-match-p "== other" out))
      (should (string-match-p "OT-1" out)))))

(ert-deftest lemmax-repo-settings-no-folders ()
  :tags '(timeout-30)
  ;; Bullets 3 and 4: with no config, a project's own #+PROPERTY: lines are its
  ;; folder's settings, and a lemma file with no header has none.
  (let ((d (rt-repo (append (rt-chain-files "" (rt-done "RQ-1" :verify "unit/zzz"))
                            (list (cons "RQ-2.org" (concat ":PROPERTIES:\n:ID: RQ-2\n:STATE: DONE\n:CREATED: 2026-01-05\n"
                                                           ":LAST_EDITED: 2026-01-05\n:END:\n#+title: Bare\n")))))))
    (let ((r (rt-run d "lint")))
      (rt-should-find r "theory\\.org:[0-9]+: RQ-1: :VERIFY: names unit/zzz")
      (should-not (string-match-p "RQ-2" (nth 2 r))))))

(ert-deftest lemmax-repo-settings-both-ways ()
  :tags '(timeout-30)
  ;; Bullet 5: an old config still reads; a setting set both there and by a
  ;; #+PROPERTY: line is refused, per folder and repo-wide.
  (rt-should-find (rt-run (rt-repo (append (rt-files (rt-done "RQ-1" :implemented "2026-11-22"))
                                           (list (cons "lemmax/config.eld" "(:markers-required-from \"2026-11-22\")\n"))))
                          "lint" "--no-tests")
                  "RQ-1: DONE with no code marker")
  (rt-should-find (rt-run (rt-repo (append (rt-chain-files "#+PROPERTY: LEMMAX_MARKERS_REQUIRED_FROM 2026-11-22\n" (rt-req "RQ-1"))
                                           (list (cons "lemmax/config.eld" "(:markers-required-from \"2026-11-22\")\n"))))
                          "lint" "--no-tests")
                  "lemmax/config\\.eld:1: -: LEMMAX_MARKERS_REQUIRED_FROM is set both as :markers-required-from in lemmax/config.eld and as #\\+PROPERTY: LEMMAX_MARKERS_REQUIRED_FROM")
  (rt-should-find (rt-run (rt-repo (append (rt-chain-files "" (rt-req "RQ-1"))
                                           (list (rt-config '("" :code ("src/"))))))
                          "lint" "--no-tests")
                  "LEMMAX_CODE is set both in lemmax/config.eld for the root and in theories/t/"))

(ert-deftest lemmax-repo-settings-migrate ()
  :tags '(timeout-60)
  ;; Bullet 6: lmx migrate lemmax/config.eld writes theories/setup.org, moves
  ;; each folder entry to its setup.org unless already there, adds
  ;; #+SETUPFILE: ../setup.org to each project's setup.org, deletes the config.
  (let* ((d (rt-repo (list (cons "lemmax/config.eld"
                                 (format "(:markers-required-from \"2026-11-22\" :repos \"~/r\" :folders ((%S :tests \"./tests.sh\" :code (\"src/\" \"lib/\")) (%S :tests \"./tests.sh\")))\n"
                                         "theories/t/" "theories/u/"))
                           (cons "setup.org" "#+title: t settings\n#+PROPERTY: LEMMAX_TESTS ./tests.sh\n")
                           (cons "theory.org" (concat "#+SETUPFILE: setup.org\n#+TODO: OPEN | DONE DROPPED\n\n" (rt-done "RQ-1" :implemented "2026-11-22")))
                           (cons "theories/u/theory.org" (concat "#+TODO: OPEN | DONE DROPPED\n\n" (rt-req "RQ-2")))
                           (cons "tests.sh" (rt-tests-sh "unit/a"))
                           (cons "src/x.clj" "(ns x)\n"))))
         (r (rt-run d "migrate" "lemmax/config.eld"))
         (out (nth 1 r)))
    (should (= 0 (nth 0 r)))
    (should (string-match-p "^\\+\\+\\+ theories/setup\\.org\n@@ -0,0 \\+1,4 @@\n\\+#\\+title: Repo settings\n\\+# .*\n\\+#\\+PROPERTY: LEMMAX_MARKERS_REQUIRED_FROM 2026-11-22\n\\+#\\+PROPERTY: LEMMAX_REPOS ~/r\n" out))
    (should (string-match-p "^ #\\+title: t settings\n\\+#\\+SETUPFILE: \\.\\./setup\\.org\n #\\+PROPERTY: LEMMAX_TESTS ./tests.sh\n\\+#\\+PROPERTY: LEMMAX_CODE src/ lib/" out))
    (should-not (string-match-p "^\\+#\\+PROPERTY: LEMMAX_TESTS" (car (split-string out "theories/u/"))))
    (should (string-match-p "^\\+\\+\\+ theories/u/setup\\.org\n@@ -0,0 \\+1,3 @@\n\\+#\\+title: u settings\n\\+#\\+SETUPFILE: \\.\\./setup\\.org\n\\+#\\+PROPERTY: LEMMAX_TESTS ./tests.sh" out))
    (should (string-match-p "^--- lemmax/config\\.eld\n\\+\\+\\+ /dev/null" out))
    (should (file-exists-p (expand-file-name "lemmax/config.eld" d)))
    (should (string-match-p "deleted lemmax/config.eld" (nth 1 (rt-run d "migrate" "--write" "lemmax/config.eld"))))
    (should-not (file-exists-p (expand-file-name "lemmax/config.eld" d)))
    (rt-git d "add" "-A")
    ;; The markers rule still holds, now from theories/setup.org.
    (rt-should-find (rt-run d "lint" "--staged" "--no-tests") "RQ-1: DONE with no code marker")))

(ert-deftest lemmax-repo-settings-opt-in ()
  :tags '(timeout-30)
  ;; Bullet 7: #+PROPERTY: LEMMAX_TESTS opts a repo in; an old config opts in
  ;; only while it names :tests; a config with none opts nothing in.
  (let ((d (rt-hooked (rt-chain-files "" (rt-req "RQ-1")))))
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-sh d "git" "add" "-A")
    (should (= 1 (nth 0 (rt-hook-commit d "change it"))))
    (should (string-match-p "RQ-1: DONE with no :APPROVED:"
                            (progn (rt-set d "theory.org" (concat "#+title: T\n#+SETUPFILE: setup.org\n#+TODO: OPEN | DONE DROPPED\n\n" (rt-done "RQ-1" :approved nil)))
                                   (rt-check d "theories/t/theory.org\n")))))
  (let ((d (rt-hooked (list (cons "lemmax/config.eld" "(:markers-required-from \"2026-11-22\")\n")
                            (cons "notes.org" "* x\n") (cons "src/x.clj" "(ns x)\n")))))
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-sh d "git" "add" "-A")
    (should (= 0 (nth 0 (rt-hook-commit d "change it")))))
  (let ((d (rt-hooked (list (rt-config '("" :tests "./tests.sh" :code ("src/"))) (cons "theory.org" (rt-req "RQ-1"))
                            (cons "tests.sh" (rt-tests-sh "unit/a")) (cons "src/x.clj" "(ns x)\n")))))
    (rt-set d "src/x.clj" "(ns x) ;; 2\n")
    (rt-sh d "git" "add" "-A")
    (should (= 1 (nth 0 (rt-hook-commit d "change it")))))
  (rt-load)
  (should (string-search "-F ':tests' -- lemmax/config.eld" (lemmax--hook-text "pre-commit"))))
