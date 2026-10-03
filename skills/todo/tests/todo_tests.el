;;; todo_tests.el --- ERT for the todo skill -*- lexical-binding: t; -*-

;; Run with:
;;
;;   emacs -Q --batch -l tests/todo_tests.el -f ert-run-tests-batch-and-exit

(require 'ert)
(require 'cl-lib)
(require 'seq)

(defconst todo-test--root
  (file-name-directory
   (directory-file-name
    (file-name-directory (expand-file-name (or load-file-name buffer-file-name)))))
  "The skill directory.")

(load (expand-file-name "scripts/todo.el" todo-test--root))
(load (expand-file-name "emacs.el" todo-test--root))

(defvar todo-test--dir nil)
(defvar todo-test--config nil)

;;; Harness

(defun todo-test--setup ()
  "A fresh temp dir and a config that points read at it."
  (ignore-errors (delete-directory todo-test--dir t))
  (setq todo-test--dir (make-temp-file "todo-test-" t)
        todo-test--config (expand-file-name "todo_skill.toml" todo-test--dir))
  (with-temp-file todo-test--config
    (insert (format "default_dirs = [\"%s\"]\nignore = [\"node_modules\"]\n" todo-test--dir))))

(define-error 'todo-test-fail "todo failed")

(defun todo-test--fail (msg)
  (signal 'todo-test-fail (list msg)))

(defun todo-test--cli (&rest args)
  "Run the CLI in-process in the test dir. Returns (code stdout stderr).
Spawning a fresh Emacs per call made the suite take 35s; this is the same
verbs, same parsing, a few milliseconds each."
  (let* ((default-directory (file-name-as-directory todo-test--dir))
         (process-environment (cons (concat "TODO_SKILL_CONFIG=" todo-test--config)
                                    process-environment))
         (out (generate-new-buffer "todo-out"))
         (parsed (todo--parse args))
         (code 0)
         (stderr ""))
    (condition-case err
        (let ((inhibit-message t))
          (cl-letf (((symbol-function 'todo-fail) #'todo-test--fail))
            (let ((standard-output out))
              (todo-run (car parsed) (cadr parsed)))))
      (todo-test-fail (setq code 1 stderr (car (cdr err))))
      (error (setq code 1 stderr (error-message-string err))))
    (list code (with-current-buffer out (prog1 (buffer-string) (kill-buffer out))) stderr)))

(defun todo-test--spawn (&rest args)
  "Run the CLI in a fresh Emacs, as the wrapper does. Returns (code stdout stderr)."
  (let* ((out (generate-new-buffer "todo-out"))
         (err (make-temp-file "todo-err"))
         (default-directory (file-name-as-directory todo-test--dir))
         (process-environment (cons (concat "TODO_SKILL_CONFIG=" todo-test--config)
                                    process-environment))
         (code (apply #'call-process "emacs" nil (list out err) nil
                      "-Q" "--batch" "-l" (expand-file-name "scripts/todo.el" todo-test--root)
                      "--" args))
         (stdout (with-current-buffer out (prog1 (buffer-string) (kill-buffer out))))
         (stderr (with-temp-buffer (insert-file-contents err) (buffer-string))))
    (delete-file err)
    (list code stdout stderr)))

(defun todo-test--ok (&rest args)
  "Run the CLI and fail the test when it exits non-zero."
  (let ((result (apply #'todo-test--cli args)))
    (should (eq 0 (nth 0 result)))
    result))

(defun todo-test--file (&optional name)
  (expand-file-name (or name "todo.org") todo-test--dir))

(defun todo-test--text (&optional name)
  (with-temp-buffer (insert-file-contents (todo-test--file name)) (buffer-string)))

(defun todo-test--write (text &optional name)
  (with-temp-file (todo-test--file name) (insert text)))

;;; create

(ert-deftest todo-create-writes-a-task ()
  (todo-test--setup)
  (todo-test--ok "create" "Pay rent" "--deadline" "2026-11-05" "--tag" "finance" "--priority" "A")
  (let ((text (todo-test--text)))
    (should (string-match-p "^\\* TODO \\[#A\\] Pay rent :finance:$" text))
    (should (string-match-p "^DEADLINE: <2026-11-05 Thu>$" text))
    (should-not (string-match-p ":PROPERTIES:\\|:ID:\\|:CREATED:" text))))

(ert-deftest todo-create-records-an-effort-estimate ()
  (todo-test--setup)
  (todo-test--write (concat "* Tasks\n"
                            "** TODO Existing\n"
                            "   :PROPERTIES:\n"
                            "   :ID: 11111111-1111-4111-8111-111111111111\n"
                            "   :Effort:   2:00\n"
                            "   :END:\n"))
  (todo-test--ok "create" "Write the report" "--container" "Tasks" "--effort" "0:30")
  (let ((text (todo-test--text)))
    (should (string-match-p "^ *:Effort: +0:30$" text))
    (should (string-match-p ":Effort:   2:00" text))
    (should (string-match-p ":ID: 11111111-1111-4111-8111-111111111111" text)))
  (should (equal "0:30"
                 (todo-test--field
                  (cl-find "Write the report"
                           (todo-test--records (nth 1 (todo-test--ok "read" "--records")))
                           :key (lambda (i) (todo-test--field i "title")) :test #'equal)
                  "effort")))
  (should (eq 1 (nth 0 (todo-test--cli "create" "Bad estimate" "--effort" "30"))))
  (should-not (string-match-p "Bad estimate" (todo-test--text))))

;;; postpone

(defun todo-test--ist-date (&optional days)
  "The date DAYS from today in IST, as YYYY-MM-DD, through the CLI's own clock."
  (todo--day-string (todo--day-plus (todo-ist-day) (or days 0) "d")))

(ert-deftest todo-postpone-shifts-a-deadline-both-ways-it-can-spell-a-shift ()
  (todo-test--setup)
  ;; Org forces a year into 1970-2037, the same on the create path, so a date
  ;; out here would be testing org, not this verb.
  (todo-test--write (concat "* TODO [#B] Report :work:\n"
                            "DEADLINE: <2027-01-31 Sun 09:00 +1m>\n"))
  (let ((result (todo-test--ok "postpone" "Report" "+1m")))
    ;; 2027 is no leap year, so 31 January clamps to 28 February.
    (should (string-match-p (concat "^deadline: <2027-02-28 \\w\\{3\\}"
                                    (regexp-quote " 09:00 ++1m>") "$")
                            (nth 1 result)))
    (should (string-match-p "^priority: B$" (nth 1 result))))
  ;; The + is optional: 28 February plus one week is 7 March.
  (todo-test--ok "postpone" "Report" "1w")
  (let ((text (todo-test--text)))
    (should (string-match-p (regexp-quote "DEADLINE: <2027-03-07") text))
    (should (string-match-p (regexp-quote "09:00 ++1m>") text))
    (should-not (string-match-p "2027-01-31" text))))

(ert-deftest todo-postpone-clamps-a-month-to-the-month-it-lands-in ()
  (let ((day (lambda (date) (org-time-string-to-absolute date))))
    (should (equal "2027-02-28" (todo--day-string (todo--month-shift (funcall day "2027-01-31") 1))))
    (should (equal "2028-02-29" (todo--day-string (todo--month-shift (funcall day "2028-01-31") 1))))
    (should (equal "2028-01-31" (todo--day-string (todo--month-shift (funcall day "2027-01-31") 12))))
    (should (equal "2029-02-28" (todo--day-string (todo--month-shift (funcall day "2028-02-29") 12))))))

(ert-deftest todo-postpone-lifts-a-lapsed-task-ahead-of-today ()
  (todo-test--setup)
  (todo-test--write (concat "* TODO [#B] Cut nails :routine:\n"
                            "DEADLINE: <2020-01-01 Wed 21:30 +1w>\n"))
  (todo-test--ok "postpone" "Cut nails" "+1d")
  (let ((text (todo-test--text)))
    ;; The deadline lapsed in 2020, so the day counts from today, not from it.
    (should (string-match-p (regexp-quote (format "DEADLINE: <%s " (todo-test--ist-date 1)))
                            text))
    (should (string-match-p (regexp-quote "21:30 ++1w>") text))
    (should-not (string-match-p "2020" text))))

(ert-deftest todo-postpone-takes-today-and-tomorrow ()
  (todo-test--setup)
  (todo-test--write "* TODO Later\nDEADLINE: <2999-01-01 Thu>\n")
  (todo-test--ok "postpone" "Later" "tomorrow")
  (should (string-match-p (regexp-quote (format "DEADLINE: <%s " (todo-test--ist-date 1)))
                          (todo-test--text)))
  (todo-test--ok "postpone" "Later" "today")
  (should (string-match-p (regexp-quote (format "DEADLINE: <%s " (todo-test--ist-date)))
                          (todo-test--text))))

(ert-deftest todo-postpone-dates-a-task-that-had-no-deadline ()
  (todo-test--setup)
  (todo-test--ok "create" "No deadline yet")
  (todo-test--ok "postpone" "No deadline yet" "+2d")
  (let ((text (todo-test--text)))
    (should (string-match-p (regexp-quote (format "DEADLINE: <%s " (todo-test--ist-date 2)))
                            text))
    (should (string-match-p "^\\* TODO No deadline yet" text))))

(ert-deftest todo-postpone-refuses-a-shift-it-cannot-read ()
  (todo-test--setup)
  (todo-test--ok "create" "Keep me" "--deadline" "2026-11-05")
  (let ((before (todo-test--text)))
    (dolist (bad '("+0d" "+0h" "later" "next friday" "-1d" "1x" ""))
      (let ((result (todo-test--cli "postpone" "Keep me" bad)))
        (should (eq 1 (nth 0 result)))
        (should (string-match-p "shift takes" (nth 2 result)))))
    (should (string-match-p "needs a ref and a shift"
                            (nth 2 (todo-test--cli "postpone" "Keep me"))))
    (should (eq 1 (nth 0 (todo-test--cli "postpone" "Ghost" "+1d"))))
    (should (equal before (todo-test--text)))))

(ert-deftest todo-postpone-hours-count-from-the-later-moment ()
  (let ((day (lambda (date) (org-time-string-to-absolute date)))
        (now (cons (org-time-string-to-absolute "2026-10-03") 1423))) ; 23:43
    ;; The deadline lapsed, so now is the base: +2h is tomorrow at 01:43.
    (should (equal (cons (funcall day "2026-10-04") 103)
                   (todo--postponed-moment (funcall day "2026-09-27") "07:30"
                                           (funcall day "2026-10-03") now (cons 2 "h"))))
    ;; A deadline still ahead of now is the base instead: 09:00 +2h.
    (should (equal (cons (funcall day "2026-10-04") 660)
                   (todo--postponed-moment (funcall day "2026-10-04") "09:00"
                                           (funcall day "2026-10-03") now (cons 2 "h"))))
    ;; A day interval keeps the time of day: the lapsed 07:30 counts from today.
    (should (equal (cons (funcall day "2026-10-10") 450)
                   (todo--postponed-moment (funcall day "2026-09-27") "07:30"
                                           (funcall day "2026-10-03") now (cons 1 "w"))))))

(ert-deftest todo-postpone-hours-move-the-clock-in-the-file ()
  (todo-test--setup)
  (todo-test--write (concat "* TODO [#B] Trim :routine:\n"
                            "DEADLINE: <2027-01-31 Sun 09:00 +1m>\n"))
  (todo-test--ok "postpone" "Trim" "+2h")
  (let ((text (todo-test--text)))
    (should (string-match-p (regexp-quote "DEADLINE: <2027-01-31") text))
    (should (string-match-p (regexp-quote " 11:00 ++1m>") text))))

(ert-deftest todo-postpone-hours-lift-a-lapsed-task-ahead-of-now ()
  (todo-test--setup)
  (todo-test--write (concat "* TODO [#B] Trim :routine:\n"
                            "DEADLINE: <2020-01-01 Wed 07:30 +1w>\n"))
  (todo-test--ok "postpone" "Trim" "+2h")
  (let* ((text (todo-test--text))
         (stamp (and (string-match "DEADLINE: \\(<[^>]+>\\)" text) (match-string 1 text)))
         (parts (todo--deadline-parts stamp))
         (landed (+ (* 1440 (car parts)) (or (todo--minutes-of-time (cadr parts)) 0)))
         (now (todo-ist-now))
         (wanted (+ (* 1440 (car now)) (cdr now) 120)))
    (should stamp)
    ;; Now plus two hours, within a minute of this test's own reading of the clock.
    (should (<= (abs (- landed wanted)) 1))))

(ert-deftest todo-deadline-takes-three-forms-and-refuses-the-rest ()
  (todo-test--setup)
  (dolist (good '("2026-11-05" "2026-11-05 20:30" "<2026-11-05 Thu 20:30 +1w>"))
    (todo-test--ok "create" (format "Good %s" good) "--deadline" good))
  (let ((text (todo-test--text)))
    (should (string-match-p "DEADLINE: <2026-11-05 Thu>$" text))
    (should (string-match-p "DEADLINE: <2026-11-05 Thu 20:30>$" text))
    (should (string-match-p (regexp-quote "DEADLINE: <2026-11-05 Thu 20:30 ++1w>") text)))
  (dolist (bad '("garbage" "next friday" "2026-13-45" "2026-11-05 +1w" "<2026-11-05"))
    (should (eq 1 (nth 0 (todo-test--cli "create" (format "Bad %s" bad) "--deadline" bad))))
    (should-not (string-match-p (format "Bad %s" (regexp-quote bad)) (todo-test--text))))
  (todo-test--ok "create" "Edit me" "--deadline" "2026-12-01")
  (should (eq 1 (nth 0 (todo-test--cli "set-deadline" "Edit me" "garbage"))))
  (should (string-match-p "DEADLINE: <2026-12-01 Tue>" (todo-test--text))))

(ert-deftest todo-write-refuses-a-heading-inside-a-block ()
  (todo-test--setup)
  (todo-test--write (concat "#+TODO: TODO | DONE\n"
                            "* Tasks\n"
                            "** TODO Real\n"
                            "#+BEGIN_SRC text\n"
                            "* TODO Not a task\n"
                            "#+END_SRC\n"))
  (let ((result (todo-test--cli "create" "New")))
    (should (eq 1 (nth 0 result)))
    (should (string-match-p "todo.org:5: a column-0 \\* heading sits inside #\\+SRC\\b" (nth 2 result))))
  (should-not (string-match-p "New" (todo-test--text)))
  ;; The line indented by one space is prose to org too, so the write goes through.
  (todo-test--write (concat "#+TODO: TODO | DONE\n"
                            "* Tasks\n"
                            "** TODO Real\n"
                            "#+BEGIN_SRC text\n"
                            "  * indented stays prose\n"
                            "#+END_SRC\n"))
  (todo-test--ok "append" "Real" "note added")
  (should (string-match-p "note added" (todo-test--text))))

(ert-deftest todo-create-starts-a-plain-file ()
  (todo-test--setup)
  (todo-test--ok "create" "First")
  (should (string-match-p "\\`\\* TODO First\n\\'" (todo-test--text))))

(ert-deftest todo-create-under-a-container ()
  (todo-test--setup)
  (todo-test--write "* hi\n")
  (todo-test--ok "create" "Nested" "--container" "hi")
  (should (string-match-p "\\* hi\n\\*\\* TODO Nested" (todo-test--text))))

(ert-deftest todo-create-under-a-container-stays-a-sibling ()
  (todo-test--setup)
  (todo-test--write "* hi\n** TODO Old\n")
  (todo-test--ok "create" "New" "--container" "hi")
  (should (string-match-p "\\* hi\n\\*\\* TODO Old\n\\*\\* TODO New" (todo-test--text))))

(ert-deftest todo-create-refuses-a-flag-title ()
  (todo-test--setup)
  (let ((result (todo-test--cli "create" "--frobnicate")))
    (should (eq 1 (nth 0 result)))
    (should (string-match-p "must not be a flag" (nth 2 result)))))

(ert-deftest todo-create-refuses-a-missing-container ()
  (todo-test--setup)
  (let ((result (todo-test--cli "create" "X" "--container" "nope")))
    (should (eq 1 (nth 0 result)))
    (should (string-match-p "headline not found" (nth 2 result)))))

(ert-deftest todo-create-refuses-an-unknown-state ()
  (todo-test--setup)
  (let ((result (todo-test--cli "create" "X" "--state" "BOGUS")))
    (should (eq 1 (nth 0 result)))
    (should (string-match-p "unknown state" (nth 2 result)))))

;;; read

(ert-deftest todo-read-lists-tasks-and-drops-ignored ()
  (todo-test--setup)
  (todo-test--ok "create" "Visible")
  (let ((hidden (expand-file-name "node_modules/hidden.org" todo-test--dir)))
    (make-directory (file-name-directory hidden) t)
    (with-temp-file hidden (insert "* TODO Hidden\n")))
  (let ((out (nth 1 (todo-test--ok "read"))))
    (should (string-match-p "Visible" out))
    (should-not (string-match-p "Hidden" out))))

(ert-deftest todo-read-filters-state-and-tag ()
  (todo-test--setup)
  (todo-test--ok "create" "Tagged" "--tag" "home")
  (todo-test--ok "create" "Plain")
  (let ((tagged (nth 1 (todo-test--ok "read" "--tag" "home"))))
    (should (string-match-p "Tagged" tagged))
    (should-not (string-match-p "Plain" tagged)))
  (todo-test--ok "set-state" "Plain" "DONE")
  (let ((done (nth 1 (todo-test--ok "read" "--state" "DONE"))))
    (should (string-match-p "Plain" done))
    (should-not (string-match-p "Tagged" done))))

(ert-deftest todo-read-filters-overdue-and-recurring ()
  (todo-test--setup)
  (with-temp-file (expand-file-name "board.org" todo-test--dir)
    (insert "* TODO Overdue plain\nDEADLINE: <2020-01-01 Wed>\n"
            "* TODO Routine late\nDEADLINE: <2020-01-01 Wed 08:00 +1w>\n"
            "* TODO Future plain\nDEADLINE: <2999-01-01 Thu>\n"))
  (let ((overdue (nth 1 (todo-test--ok "read" "--overdue")))
        (recurring (nth 1 (todo-test--ok "read" "--recurring")))
        (both (nth 1 (todo-test--ok "read" "--overdue" "--recurring"))))
    (should (string-match-p "Overdue plain" overdue))
    (should (string-match-p "Routine late" overdue))
    (should-not (string-match-p "Future plain" overdue))
    (should (string-match-p "Routine late" recurring))
    (should-not (string-match-p "Overdue plain" recurring))
    (should (string-match-p "Routine late" both))
    (should-not (string-match-p "Overdue plain" both))
    (should-not (string-match-p "Future plain" both))))

(defun todo-test--pairs (text)
  "TEXT as an alist of `key: value' lines; indented note lines are skipped."
  (let (out)
    (dolist (line (split-string text "\n" t))
      (when (string-match "\\`\\([a-z_]+\\): \\(.*\\)\\'" line)
        (push (cons (intern (match-string 1 line)) (match-string 2 line)) out)))
    (nreverse out)))

(defun todo-test--record-note (record)
  "The indented note lines of RECORD, unindented and trimmed."
  (string-trim
   (mapconcat (lambda (line) (if (string-prefix-p "    " line) (substring line 4) ""))
              (seq-filter (lambda (line) (string-prefix-p "    " line))
                          (split-string record "\n" t))
              "\n")))

(defun todo-test--records (stdout)
  "STDOUT as a list of task alists, the CLI's plain records."
  (mapcar (lambda (record)
            (let* ((pairs (todo-test--pairs record))
                   (some (lambda (key)
                           (let ((v (alist-get key pairs)))
                             (and v (not (string-empty-p v)) v)))))
              (list (cons 'title (alist-get 'title pairs))
                    (cons 'state (alist-get 'state pairs))
                    (cons 'deadline (funcall some 'deadline))
                    (cons 'priority (funcall some 'priority))
                    (cons 'effort (funcall some 'effort))
                    (cons 'tags (split-string (or (alist-get 'tags pairs) "") " " t))
                    (cons 'note (todo-test--record-note record))
                    (cons 'path (alist-get 'path pairs)))))
          (split-string stdout "\n\n" t)))

(defun todo-test--field (item key)
  (alist-get (intern key) item))

(ert-deftest todo-read-and-doing-honor-file ()
  (todo-test--setup)
  (todo-test--ok "create" "In the test dir")
  (let* ((dir (make-temp-file "todo-other-" t))
         (other (expand-file-name "other.org" dir)))
    (with-temp-file other
      (insert "* TODO Only in the other board\nDEADLINE: <2020-01-01 Wed>\n"))
    (should (equal '("Only in the other board")
                   (mapcar (lambda (i) (todo-test--field i "title"))
                           (todo-test--records (nth 1 (todo-test--ok "read" "--records" "--file" other))))))
    (should (equal "Only in the other board"
                   (todo-test--field
                    (car (todo-test--records (nth 1 (todo-test--ok "doing" "--file" other))))
                    "title")))
    (should (equal '("In the test dir")
                   (mapcar (lambda (i) (todo-test--field i "title"))
                           (todo-test--records (nth 1 (todo-test--ok "read" "--records"))))))
    (should (eq 1 (nth 0 (todo-test--cli "read" "--records" "--file" (expand-file-name "nope.org" dir)))))))

(ert-deftest todo-read-records-have-the-card-fields ()
  (todo-test--setup)
  (todo-test--write (concat "* TODO [#A] Pay rent :finance:\n"
                            "DEADLINE: <2026-11-05 Thu>\n"
                            ":PROPERTIES:\n:ID: abc\n:Effort: 0:30\n:END:\n"
                            "paid \"cash\"\n"
                            "line two\n"
                            "* DONE Say \"hi\"\n"
                            "* TODO Apr\u2013Jun\n"
                            "* Archive\n** DONE Old\n"))
  (let ((hidden (expand-file-name "node_modules/hidden.org" todo-test--dir)))
    (make-directory (file-name-directory hidden) t)
    (with-temp-file hidden (insert "* TODO Hidden\n")))
  (let* ((items (todo-test--records (nth 1 (todo-test--ok "read" "--records"))))
         (pay (cl-find "Pay rent" items :key (lambda (i) (todo-test--field i "title")) :test #'equal))
         (other (cl-find "Say \"hi\"" items :key (lambda (i) (todo-test--field i "title")) :test #'equal))
         (dash (cl-find "Apr\u2013Jun" items :key (lambda (i) (todo-test--field i "title")) :test #'equal)))
    (should (eq 3 (length items)))
    (should dash)
    (should (equal (todo-test--field pay "state") "TODO"))
    (should (equal (todo-test--field pay "deadline") "<2026-11-05 Thu>"))
    (should (equal (todo-test--field pay "priority") "A"))
    (should (equal (todo-test--field pay "effort") "0:30"))
    (should (equal (todo-test--field pay "tags") '("finance")))
    (should (equal (todo-test--field pay "note") "paid \"cash\"\nline two"))
    (should-not (string-match-p "DEADLINE\\|:ID:" (todo-test--field pay "note")))
    (should (string-match-p "todo.org$" (todo-test--field pay "path")))
    (should-not (todo-test--field other "deadline"))
    (should-not (todo-test--field other "priority"))
    (should-not (todo-test--field other "effort"))
    (should (equal (todo-test--field other "state") "DONE"))
    (should (equal (todo-test--field other "note") ""))
    (should-not (cl-find "Old" items :key (lambda (i) (todo-test--field i "title")) :test #'equal))
    (should-not (cl-find "Hidden" items :key (lambda (i) (todo-test--field i "title")) :test #'equal)))
  (let ((done (todo-test--records (nth 1 (todo-test--ok "read" "--records" "--state" "DONE")))))
    (should (equal (mapcar (lambda (i) (todo-test--field i "title")) done) '("Say \"hi\""))))
  (should (equal (nth 1 (todo-test--ok "read" "--records" "--state" "OBSOLETE")) "")))

;;; repeat cookies

(ert-deftest todo-opens-the-emacs-that-runs-it ()
  ;; The binary comes from Emacs's own invocation info, never a hardcoded path.
  (should (file-executable-p (todo--emacs-bin)))
  (should (string-prefix-p (expand-file-name invocation-directory)
                           (expand-file-name (todo--emacs-bin)))))

(ert-deftest todo-ist-day-is-orgs-day-number ()  ;; Emacs numbers days for the CLI; org numbers them for timestamps. If those
  ;; two ever drifted, every due window would be off by one.
  (dolist (date '("2026-10-04" "2026-01-01" "2027-02-28" "1999-12-31" "2037-01-19"))
    (should (= (org-time-string-to-absolute date)
               (time-to-days (org-time-from-absolute (org-time-string-to-absolute date)))))))

(ert-deftest todo-routine-detection-follows-org-repeater-syntax ()
  ;; Org's three repeater forms, every unit, and hours among them.
  (dolist (deadline '("<2026-11-05 Thu 20:30 +1w>" "<2026-11-05 Thu 20:30 ++1w>"
                      "<2026-11-05 Thu 20:30 .+1w>" "<2026-11-05 Thu 20:30 +2h>"
                      "<2026-11-05 Thu +6m>" "<2026-11-05 Thu ++1y>"))
    (should (todo--recurring deadline)))
  (dolist (deadline '("<2026-11-05 Thu 20:30>" "2026-11-05" "2026-11-05 20:30" nil))
    (should-not (todo--recurring deadline))))

(ert-deftest todo-writes-orgs-catch-up-cookie-for-a-repeating-deadline ()
  (todo-test--setup)
  (todo-test--ok "create" "Rent" "--deadline" "<2026-11-05 Thu 20:30 +1m>")
  (should (string-match-p (regexp-quote "DEADLINE: <2026-11-05 Thu 20:30 ++1m>")
                          (todo-test--text)))
  ;; `++' and `.+' say what they mean and pass through untouched.
  (todo-test--ok "create" "Sheets" "--deadline" "<2026-11-06 Fri 09:00 .+1w>")
  (todo-test--ok "create" "Trash" "--deadline" "<2026-11-07 Sat 09:00 ++1d>")
  (let ((text (todo-test--text)))
    (should (string-match-p (regexp-quote "DEADLINE: <2026-11-06 Fri 09:00 .+1w>") text))
    (should (string-match-p (regexp-quote "DEADLINE: <2026-11-07 Sat 09:00 ++1d>") text)))
  ;; A one-off deadline is untouched, bare or stamped.
  (todo-test--ok "create" "Tax" "--deadline" "2026-12-01")
  (should (string-match-p (regexp-quote "DEADLINE: <2026-12-01 Tue>") (todo-test--text)))
  ;; And so is the same date moved by set-deadline.
  (todo-test--ok "set-deadline" "Tax" "<2026-12-01 Tue 20:30 +1m>")
  (should (string-match-p (regexp-quote "DEADLINE: <2026-12-01 Tue 20:30 ++1m>")
                          (todo-test--text))))

(ert-deftest todo-postpone-keeps-a-catch-up-repeater ()
  (todo-test--setup)
  (todo-test--write (concat "* TODO [#B] Rent :routine:\n"
                            "DEADLINE: <2027-01-31 Sun 09:00 ++1m>\n"))
  (todo-test--ok "postpone" "Rent" "+1m")
  (should (string-match-p (regexp-quote "DEADLINE: <2027-02-28 Sun 09:00 ++1m>")
                          (todo-test--text)))
  ;; A lone `+' is upgraded on the way through, and `.+h' survives with its hours.
  (todo-test--write (concat "* TODO [#B] Trash :routine:\n"
                            "DEADLINE: <2027-01-31 Sun 09:00 +1m>\n"
                            "* TODO [#B] Stretch :routine:\n"
                            "DEADLINE: <2027-01-31 Sun 09:00 .+2h>\n"))
  (todo-test--ok "postpone" "Trash" "+1m")
  (todo-test--ok "postpone" "Stretch" "+2h")
  (let ((text (todo-test--text)))
    (should (string-match-p (regexp-quote "++1m>") text))
    (should (string-match-p (regexp-quote ".+2h>") text))))

(ert-deftest todo-complete-lets-org-catch-a-routine-up ()
  (todo-test--setup)
  ;; A weekly routine whose anchor lapsed years ago: org has to shift it past
  ;; ten intervals, which is where it asks its "Continue?" question.
  (todo-test--write (concat "* TODO [#B] Sheets :routine:\n"
                            "DEADLINE: <2020-01-01 Wed 09:00 ++1w>\n"))
  (let ((result (todo-test--ok "complete" "Sheets")))
    (should (string-match-p "^routine: yes$" (nth 1 result)))
    (should (string-match-p "^deadline: <" (nth 1 result))))
  (let* ((text (todo-test--text))
         (stamp (and (string-match "DEADLINE: \\(<[^>]+>\\)" text) (match-string 1 text)))
         (parts (todo--deadline-parts stamp))
         (landed (car parts))
         (today (todo-ist-day))
         (anchor (org-time-string-to-absolute "2020-01-01")))
    (should stamp)
    ;; Org's rule: a whole number of weeks past the anchor, and in the future.
    (should (> landed today))
    (should (<= landed (+ today 7)))
    (should (= 0 (% (- landed anchor) 7)))))

(ert-deftest todo-complete-keeps-an-hour-routine ()
  (todo-test--setup)
  ;; A two-hour routine whose anchor is two hours behind now: org has to catch up.
  (let* ((now (todo-ist-now))
         (earlier (- (+ (* 1440 (car now)) (cdr now)) 120))
         (day (floor earlier 1440))
         (deadline (todo--deadline-text day
                                        (todo--time-of-minutes (- earlier (* 1440 day)))
                                        "++2h")))
    (todo-test--write (concat "* TODO [#B] Stretch :routine:\nDEADLINE: " deadline "\n"))
    (should (string-match-p "^routine: yes$" (nth 1 (todo-test--ok "complete" "Stretch"))))
    (let* ((text (todo-test--text))
           (stamp (and (string-match "DEADLINE: \\(<[^>]+>\\)" text) (match-string 1 text)))
           (parts (todo--deadline-parts stamp))
           (landed (+ (* 1440 (or (car parts) 0))
                      (or (todo--minutes-of-time (cadr parts)) 0)))
           (after (todo-ist-now)))
      (should stamp)
      (should (> landed (+ (* 1440 (car after)) (cdr after)))))))

;;; update

(ert-deftest todo-update-by-title ()
  (todo-test--setup)
  (todo-test--ok "create" "Edit me")
  (todo-test--ok "set-state" "Edit me" "IN_PROGRESS")
  (todo-test--ok "set-deadline" "Edit me" "2026-12-01")
  (todo-test--ok "add-tag" "Edit me" "home")
  (todo-test--ok "append" "Edit me" "note from the agent")
  (let ((text (todo-test--text)))
    (should (string-match-p "^\\* IN_PROGRESS Edit me :home:$" text))
    (should (string-match-p "^DEADLINE: <2026-12-01 Tue>$" text))
    (should (string-match-p "^note from the agent$" text)))
  (todo-test--ok "remove-tag" "Edit me" "home")
  (should-not (string-match-p ":home:" (todo-test--text))))

(ert-deftest todo-a-recurring-task-is-priority-b ()
  (todo-test--setup)
  (todo-test--ok "create" "Water the plants" "--deadline" "<2026-11-05 Thu 08:00 +1w>")
  (should (string-match-p "^\\* TODO \\[#B\\] Water the plants$" (todo-test--text)))
  (should (string-match-p "priority: B"
                          (nth 1 (todo-test--ok "create" "Water more plants"
                                                "--deadline" "<2026-11-05 Thu 08:00 +1w>"))))
  (should (eq 1 (nth 0 (todo-test--cli
                        "create" "Bad routine" "--deadline" "<2026-11-05 Thu 08:00 +1w>"
                        "--priority" "A"))))
  (should-not (string-match-p "Bad routine" (todo-test--text)))
  (todo-test--ok "create" "Plain task" "--deadline" "2026-11-05")
  (should (string-match-p "^\\* TODO Plain task$" (todo-test--text)))
  ;; A plain task that gains a repeater becomes a routine, so it gains B.
  (todo-test--ok "set-deadline" "Plain task" "<2026-11-05 Thu 08:00 +1w>")
  (should (string-match-p "^\\* TODO \\[#B\\] Plain task$" (todo-test--text))))

(ert-deftest todo-set-priority-writes-the-cookie ()
  (todo-test--setup)
  (todo-test--write "* TODO Buy milk\n")
  (todo-test--ok "set-priority" "Buy milk" "B")
  (should (string-match-p "^\\* TODO \\[#B\\] Buy milk$" (todo-test--text)))
  (should (equal "B"
                 (todo-test--field
                  (car (todo-test--records (nth 1 (todo-test--ok "read" "--records"))))
                  "priority")))
  (should (eq 1 (nth 0 (todo-test--cli "set-priority" "Buy milk" "High")))))

(ert-deftest todo-set-effort-writes-the-property ()
  (todo-test--setup)
  (todo-test--write "* TODO Buy milk\n")
  (todo-test--ok "set-effort" "Buy milk" "0:15")
  (should (string-match-p "^ *:Effort: +0:15$" (todo-test--text)))
  (should (eq 1 (nth 0 (todo-test--cli "set-effort" "Buy milk" "15")))))

;;; note

(ert-deftest todo-set-note-replaces-the-note-and-keeps-the-meta-data ()
  (todo-test--setup)
  (todo-test--write (concat "* TODO Pay rent :finance:\n"
                            "DEADLINE: <2026-12-01 Tue>\n"
                            "   :PROPERTIES:\n"
                            "   :Effort:   0:30\n"
                            "   :END:\n"
                            "old note line\n"
                            "old note line two\n"
                            "\n"
                            "** TODO Sibling\n"))
  (todo-test--ok "set-note" "Pay rent" "paid, receipt in mail")
  (let ((text (todo-test--text)))
    (should (string-match-p "^DEADLINE: <2026-12-01 Tue>$" text))
    (should (string-match-p ":Effort:   0:30" text))
    (should (string-match-p "^paid, receipt in mail$" text))
    (should-not (string-match-p "old note" text))
    ;; The blank line before the child survives, so the diff is the note alone.
    (should (string-match-p "^paid, receipt in mail\n\n\\*\\* TODO Sibling$" text))
    (should (string-match-p "^\\* TODO Pay rent :finance:$" text)))
  (should (string-match-p "paid, receipt in mail"
                          (nth 1 (todo-test--ok "read" "--records")))))

(ert-deftest todo-set-note-takes-a-container-and-a-multi-line-note ()
  (todo-test--setup)
  (todo-test--write (concat "* Inbox\n"
                            "    > old triage rule\n"
                            "** TODO Child\n"
                            "* Archive\n"
                            "** DONE Old task\n"))
  (todo-test--ok "set-note" "Inbox" "    > new rule one\n    > new rule two")
  (let ((text (todo-test--text)))
    (should (string-match-p "^    > new rule one\n    > new rule two\n\\*\\* TODO Child$" text))
    (should-not (string-match-p "old triage" text)))
  ;; The Archive container is history, and a name with no heading is refused.
  (should (eq 1 (nth 0 (todo-test--cli "set-note" "Archive" "nope"))))
  (should (eq 1 (nth 0 (todo-test--cli "set-note" "Ghost" "nope"))))
  (should-not (string-match-p "nope" (todo-test--text))))

(ert-deftest todo-set-note-refuses-text-that-would-become-a-task ()
  (todo-test--setup)
  (todo-test--write "* TODO Pay rent\nold note\n")
  (let ((result (todo-test--cli "set-note" "Pay rent" "new line\n* TODO Sneaky")))
    (should (eq 1 (nth 0 result)))
    (should (string-match-p "column 0" (nth 2 result))))
  ;; An empty note and a missing TEXT are refused too.
  (should (eq 1 (nth 0 (todo-test--cli "set-note" "Pay rent" ""))))
  (should (eq 1 (nth 0 (todo-test--cli "set-note" "Pay rent"))))
  (should (string-match-p "^old note$" (todo-test--text))))

(ert-deftest todo-rename-changes-only-the-title ()
  (todo-test--setup)
  (todo-test--ok "create" "First task")
  (todo-test--ok "create" "Second task" "--priority" "B" "--tag" "keep")
  (let ((before (todo-test--text)))
    (todo-test--ok "rename" "Second task" "Second task renamed")
    (let* ((after (todo-test--text))
           (changed (cl-set-difference (split-string before "\n")
                                       (split-string after "\n")
                                       :test #'equal)))
      (should (string-match-p "^\\* TODO \\[#B\\] Second task renamed :keep:$" after))
      (should (string-match-p "^\\* TODO First task$" after))
      (should (equal changed '("* TODO [#B] Second task :keep:"))))))

(ert-deftest todo-delete-removes-only-the-subtree ()
  (todo-test--setup)
  (todo-test--ok "create" "Keep me")
  (todo-test--ok "create" "Delete me" "--note" "a body line")
  (todo-test--ok "delete" "Delete me")
  (let ((text (todo-test--text)))
    (should-not (string-match-p "Delete me" text))
    (should-not (string-match-p "a body line" text))
    (should (string-match-p "^\\* TODO Keep me$" text))))

(ert-deftest todo-set-state-promotes-a-plain-heading ()
  (todo-test--setup)
  (todo-test--write (concat "* Idea worth keeping\n"
                            "  a line of note\n"
                            "* Archive\n"
                            "** DONE Old\n"))
  (todo-test--ok "set-state" "Idea worth keeping" "TODO")
  (let ((text (todo-test--text)))
    (should (string-match-p "^\\* TODO Idea worth keeping$" text))
    (should (string-match-p "a line of note" text)))
  (should (equal "TODO"
                 (todo-test--field
                  (car (todo-test--records (nth 1 (todo-test--ok "read" "--records"))))
                  "state")))
  (should (eq 1 (nth 0 (todo-test--cli "set-state" "Archive" "TODO"))))
  (should (string-match-p "^\\* Archive$" (todo-test--text)))
  (should (eq 1 (nth 0 (todo-test--cli "set-state" "Old" "TODO")))))

(ert-deftest todo-delete-refuses-an-unknown-task ()
  (todo-test--setup)
  (todo-test--ok "create" "Real task")
  (let ((result (todo-test--cli "delete" "Ghost")))
    (should (eq 1 (nth 0 result)))
    (should (string-match-p "not a task heading" (nth 2 result)))))

(ert-deftest todo-refuses-an-ambiguous-title ()
  (todo-test--setup)
  (todo-test--ok "create" "Same")
  (todo-test--ok "create" "Same")
  (let ((result (todo-test--cli "set-state" "Same" "DONE")))
    (should (eq 1 (nth 0 result)))
    (should (string-match-p "more than one" (nth 2 result)))))

(ert-deftest todo-obsolete-keeps-the-record ()
  (todo-test--setup)
  (todo-test--ok "create" "Old work")
  (todo-test--ok "obsolete" "Old work")
  (should (string-match-p "^\\* OBSOLETE Old work$" (todo-test--text))))

(ert-deftest todo-complete-moves-the-task-to-the-archive ()
  (todo-test--setup)
  (todo-test--ok "create" "Pay rent")
  (let ((out (nth 1 (todo-test--ok "complete" "Pay rent" "--evidence" "paid via bank transfer"))))
    (should (string-match-p "^archived: .*todo\\.org_archive$" out)))
  ;; Off the board, with org's own archive furniture on the copy.
  (should (equal "" (todo-test--text)))
  (let ((archive (todo-test--text "todo.org_archive")))
    (should (string-match-p "^#    -\\*- mode: org -\\*-$" archive))
    (should (string-match-p "^Archived entries from file " archive))
    (should (string-match-p "^\\* DONE Pay rent$" archive))
    (should (string-match-p "^CLOSED: \\[" archive))
    (should (string-match-p "^paid via bank transfer$" archive))
    (should (string-match-p "^:ARCHIVE_TIME: " archive))
    (should (string-match-p "^:ARCHIVE_TODO: DONE$" archive))))

(ert-deftest todo-complete-keeps-a-routine-on-the-board ()
  (todo-test--setup)
  (todo-test--ok "create" "Water plants" "--deadline" "2026-10-05" "--tag" "routine")
  (todo-test--ok "set-deadline" "Water plants" "<2026-10-05 Mon 09:00 +1w>")
  (let ((out (nth 1 (todo-test--ok "complete" "Water plants"))))
    (should (string-match-p "^routine: yes$" out)))
  (let ((board (todo-test--text)))
    ;; Still there, priority B from the repeater, and org advanced the date.
    (should (string-match-p "^\\* .*Water plants :routine:$" board))
    (should (string-match-p (regexp-quote "DEADLINE: <2026-10-12 Mon 09:00 ++1w>") board)))
  (should-not (file-exists-p (todo-test--file "todo.org_archive"))))

(ert-deftest todo-read-never-sees-an-archive-file ()
  (todo-test--setup)
  (todo-test--ok "create" "Pay rent")
  (todo-test--ok "complete" "Pay rent")
  (should (equal "" (nth 1 (todo-test--ok "read"))))
  (should (equal "" (nth 1 (todo-test--ok "read" "--state" "DONE"))))
  ;; ... and the file itself is still readable when named on purpose.
  (should (string-match-p "Pay rent"
                          (nth 1 (todo-test--ok "read" "--file" (todo-test--file "todo.org_archive"))))))

(ert-deftest todo-archive-moves-the-inline-container ()
  (todo-test--setup)
  (todo-test--write (concat "* TODO Live one\n"
                            "* DONE Old one\n"
                            "  CLOSED: [2025-01-02 Thu]\n"
                            "* Archive\n"
                            "** DONE Ancient one\n"
                            "** DONE Ancient two\n"
                            "* TODO Live two\n"))
  (should (string-match-p "^containers: 1$" (nth 1 (todo-test--ok "archive"))))
  (let ((board (todo-test--text)))
    (should-not (string-match-p "Archive" board))
    (should (string-match-p "Live one" board))
    (should (string-match-p "Live two" board)))
  ;; Both children, not just the first: the cut takes the whole subtree.
  (let ((archive (todo-test--text "todo.org_archive")))
    (should (string-match-p "Ancient one" archive))
    (should (string-match-p "Ancient two" archive)))
  (should (string-match-p "^containers: 0$" (nth 1 (todo-test--ok "archive")))))

(ert-deftest todo-archive-drops-a-blank-container-without-an-archive-file ()
  (todo-test--setup)
  (todo-test--write "* TODO Live one\n* Archive\n* TODO Live two\n")
  (should (string-match-p "^containers: 1$" (nth 1 (todo-test--ok "archive"))))
  (should (equal "* TODO Live one\n* TODO Live two\n" (todo-test--text)))
  (should-not (file-exists-p (todo-test--file "todo.org_archive"))))

;;; capture, resolve, status, config

(ert-deftest todo-capture-appends-a-plain-heading ()
  (todo-test--setup)
  (todo-test--ok "create" "A task")
  (todo-test--ok "capture" "Look into routing")
  (let ((text (todo-test--text)))
    (should (string-match-p "^\\* Look into routing$" text))
    (should (string-match-p "^\\* TODO A task$" text))))

(ert-deftest todo-capture-starts-a-missing-board ()
  (todo-test--setup)
  (todo-test--ok "capture" "Idea")
  (should (string-match-p "\\`\\* Idea\n\\'" (todo-test--text))))

(ert-deftest todo-resolve-reports-the-cwd-board ()
  (todo-test--setup)
  (let ((out (nth 1 (todo-test--ok "resolve"))))
    (should (string-match-p (regexp-quote (todo-test--file)) out))
    (should (string-match-p "^exists: no$" out)))
  (todo-test--ok "create" "Made it")
  (should (string-match-p "^exists: yes$" (nth 1 (todo-test--ok "resolve")))))

(ert-deftest todo-status-counts-tasks ()
  (todo-test--setup)
  (todo-test--ok "create" "One")
  (todo-test--ok "create" "Two")
  (todo-test--ok "complete" "One" "--evidence" "done")
  (let ((out (nth 1 (todo-test--ok "status"))))
    (should (string-match-p "^exists: yes$" out))
    ;; One is archived on completion, so the board holds one task.
    (should (string-match-p "^tasks: 1$" out))))

(ert-deftest todo-config-prints-the-loaded-file ()
  (todo-test--setup)
  (let ((out (nth 1 (todo-test--ok "config"))))
    (should (string-match-p (regexp-quote todo-test--dir) out))
    (should (string-match-p "^ignore: node_modules$" out))))

;;; pure helpers

(ert-deftest todo-ignored-matches-the-config-semantics ()
  (should (todo-ignored-p "/a/node_modules/b.org" '("node_modules")))
  (should (todo-ignored-p "/a/b/node_modules/c.org" '("b/node_modules")))
  (should (todo-ignored-p "/a/x.org" '("*.org")))
  (should (todo-ignored-p "/a/b.org" '("/a")))
  (should-not (todo-ignored-p "/a/b.org" '("node_modules"))))

;;; the real process boundary

(defun todo-test--emacs-pid (socket)
  (with-temp-buffer
    (call-process "emacsclient" nil t nil "-s" socket "--eval" "(emacs-pid)")
    (string-to-number (buffer-string))))

(ert-deftest todo-warm-stamp-matches-the-file-on-disk ()
  (let ((file (expand-file-name "scripts/todo.el" todo-test--root)))
    (should (equal (todo-warm-stamp)
                   (string-trim
                    (shell-command-to-string
                     (format "stat -f %%m %s" (shell-quote-argument file))))))))

(ert-deftest todo-warm-wrapper-finds-emacs-with-launchd-path ()
  "The Main Quest window spawns the wrapper with launchd's PATH, which holds no
emacs. The wrapper must resolve its own binaries, or the window reports
\"warm Emacs did not start\" and every GUI verb fails."
  (todo-test--setup)
  (let* ((socket (format "todo-skill-path-%s" (emacs-pid)))
         (board (expand-file-name "gui.org" todo-test--dir))
         (script (expand-file-name "scripts/todo" todo-test--root))
         (client "/Applications/Emacs.app/Contents/MacOS/bin/emacsclient")
         (out (generate-new-buffer "todo-path")))
    (unwind-protect
        (progn
          (with-temp-file board (insert "* TODO Seen from a GUI PATH\n"))
          (let ((code (call-process "env" nil (list out nil) nil
                                    "-i" "PATH=/usr/bin:/bin"
                                    (concat "HOME=" (expand-file-name "~"))
                                    (concat "TMPDIR=" (or (getenv "TMPDIR") "/tmp"))
                                    (concat "TODO_SKILL_SOCKET=" socket)
                                    (concat "TODO_SKILL_CONFIG=" todo-test--config)
                                    script "--warm" "status" "--file" board)))
            (should (eq code 0))
            (should (string-match-p "tasks: 1" (with-current-buffer out (buffer-string))))))
      (ignore-errors (call-process client nil nil nil "-s" socket "--eval" "(kill-emacs)"))
      (kill-buffer out))))

(ert-deftest todo-warm-write-does-not-kill-emacs ()
  (todo-test--setup)
  (let ((process-environment (cons (concat "TODO_SKILL_CONFIG=" todo-test--config)
                                   process-environment))
        (args (expand-file-name "args" todo-test--dir))
        (out (expand-file-name "out" todo-test--dir))
        (err (expand-file-name "err" todo-test--dir)))
    (with-temp-file args (insert "create\0Warm\0"))
    (should (eq 0 (todo-warm-write args out err todo-test--dir)))
    (should (string-match-p "Warm" (todo-test--text)))
    (with-temp-file args (insert "bogus\0"))
    (should (eq 1 (todo-warm-write args out err todo-test--dir)))
    (should (string-match-p "unknown command"
                            (with-temp-buffer (insert-file-contents err) (buffer-string))))))

(ert-deftest todo-warm-wrapper-reuses-the-daemon ()
  (todo-test--setup)
  (let* ((socket (format "todo-skill-test-%s" (emacs-pid)))
         (process-environment
          (append (list (concat "TODO_SKILL_SOCKET=" socket)
                        (concat "TODO_SKILL_CONFIG=" todo-test--config))
                  process-environment))
         (default-directory (file-name-as-directory todo-test--dir))
         (script (expand-file-name "scripts/todo" todo-test--root))
         (out (generate-new-buffer "todo-warm")))
    (unwind-protect
        (progn
          (should (eq 0 (call-process script nil nil nil "--warm" "create" "Warm")))
          (should (string-match-p "Warm" (todo-test--text)))
          (let ((pid (todo-test--emacs-pid socket)))
            (should (> pid 0))
            (should (eq 0 (call-process script nil nil nil "--warm" "create" "Apr\u2013Jun")))
            (should (eq 0 (call-process script nil (list out nil) nil "--warm" "read" "--records")))
            (should (string-match-p "Warm" (with-current-buffer out (buffer-string))))
            (should (string-match-p "Apr\u2013Jun" (with-current-buffer out (buffer-string))))
            (should-not (string-match-p "\\\\342" (with-current-buffer out (buffer-string))))
            (should (eq 1 (call-process script nil nil nil "--warm" "bogus")))
            (should (eq pid (todo-test--emacs-pid socket)))))
      (ignore-errors (call-process "emacsclient" nil nil nil "-s" socket "--eval" "(kill-emacs)"))
      (kill-buffer out))))

(ert-deftest todo-doing-item-is-one-agenda-line ()
  (let* ((root (make-temp-file "doing-" t))
         (file (expand-file-name "todo.org" root)))
    (unwind-protect
        (progn
          (with-temp-file file
            (insert "* TODO Pay rent\nDEADLINE: <2026-09-28 Mon>\n* TODO Other\nDEADLINE: <2026-09-28 Mon>\n* TODO Repeat\nDEADLINE: <2026-09-27 Sun +1w>\n"))
          (let ((item (todo-doing-item `((title . "Pay rent")
                                         (file . ,file)
                                         (deadline . "<2026-09-28 Mon>"))))
                (repeat (todo-doing-item `((title . "Repeat")
                                           (file . ,file)
                                           (deadline . "<2026-09-27 Sun +1w>")))))
            (should (string-match-p "Pay rent" item))
            (should-not (string-match-p "Other" item))
            (should (equal "Pay rent"
                           (org-with-point-at (get-text-property 0 'org-hd-marker item)
                             (org-get-heading t t t t))))
            (should (string-match-p "Repeat" repeat))
            (should (commandp 'agenda2))))
      (dolist (buffer (buffer-list))
        (with-current-buffer buffer
          (when (and buffer-file-name (file-in-directory-p buffer-file-name root))
            (set-buffer-modified-p nil)
            (kill-buffer buffer))))
      (delete-directory root t))))

(ert-deftest todo-doing-picks-the-most-late-open-task ()
  (let* ((today (org-time-string-to-absolute "2026-10-02"))
         (items (list
                 (list (cons 'todo "TODO") (cons 'title "Buy iron")
                       (cons 'deadline "<2026-10-02 Fri>") (cons 'priority nil) (cons 'path "/b"))
                 (list (cons 'todo "TODO") (cons 'title "Pay rent")
                       (cons 'deadline "<2026-09-28 Mon>") (cons 'priority nil) (cons 'path "/a"))
                 (list (cons 'todo "LATER") (cons 'title "Sheets")
                       (cons 'deadline "<2026-09-01 Tue>") (cons 'priority nil) (cons 'path "/a"))
                 (list (cons 'todo "TODO") (cons 'title "Future")
                       (cons 'deadline "<2026-10-08 Thu +1w>") (cons 'priority nil) (cons 'path "/a"))
                 (list (cons 'todo "TODO") (cons 'title "Undated")
                       (cons 'deadline nil) (cons 'priority nil) (cons 'path "/a"))
                 (list (cons 'todo "IN_PROGRESS") (cons 'title "Urgent")
                       (cons 'deadline "<2026-09-28 Mon>") (cons 'priority "A") (cons 'path "/z")))))
    (should (equal (alist-get 'title (todo-doing-pick items today)) "Urgent"))
    (should (equal (alist-get 'title
                              (todo-doing-pick
                               (cl-remove-if (lambda (i) (equal (alist-get 'title i) "Urgent")) items)
                               today))
                   "Pay rent"))
    (should (equal (alist-get 'title
                              (todo-doing-pick
                               (list (list (cons 'todo "TODO") (cons 'title "Beta")
                                           (cons 'deadline "<2026-10-02 Fri>") (cons 'priority nil) (cons 'path "/b"))
                                     (list (cons 'todo "TODO") (cons 'title "Alpha")
                                           (cons 'deadline "<2026-10-02 Fri>") (cons 'priority nil) (cons 'path "/a")))
                               today))
                   "Alpha"))
    (should-not (todo-doing-pick nil today))
    (should (todo--due-day "<2026-09-27 Sun +1w>"))))

(ert-deftest todo-ist-day-crosses-midnight ()
  (let ((evening (encode-time (list 0 0 20 2 10 2026 nil nil t))))
    (should (equal (format-time-string "%Y-%m-%d" evening "Asia/Kolkata") "2026-10-03"))
    (should (eq (todo-ist-day evening)
                (org-time-string-to-absolute "2026-10-03")))))

(ert-deftest todo-doing-command-returns-the-overdue-task ()
  (todo-test--setup)
  (todo-test--ok "create" "Old" "--deadline" "2026-01-01")
  (todo-test--ok "create" "Far" "--deadline" "2099-01-01")
  (let ((item (car (todo-test--records (nth 1 (todo-test--ok "doing"))))))
    (should (equal (todo-test--field item "title") "Old"))
    (should (equal (todo-test--field item "state") "TODO")))
  (todo-test--ok "set-state" "Old" "DONE")
  (should (equal (nth 1 (todo-test--ok "doing")) "none\n")))

(ert-deftest todo-doing-priority-picks-one-open-a-task ()
  (todo-test--setup)
  (todo-test--ok "create" "Low" "--priority" "C" "--deadline" "2099-01-01")
  (todo-test--ok "create" "Beta" "--priority" "A" "--deadline" "2099-01-01")
  (todo-test--ok "create" "Alpha" "--priority" "A")
  (todo-test--ok "create" "Beaten" "--priority" "A")
  (todo-test--ok "set-state" "Beaten" "DONE")
  (todo-test--ok "create" "Deferred" "--priority" "A")
  (todo-test--ok "set-state" "Deferred" "LATER")
  (let ((lines (nth 1 (todo-test--ok "doing" "--priority" "A"))))
    (should (equal 1 (length (split-string lines "\n\n" t))))
    (should (string-match-p "Alpha" lines)))
  (should (equal "Alpha"
                 (todo-test--field
                  (car (todo-test--records (nth 1 (todo-test--ok "doing" "--priority" "A"))))
                  "title")))
  (should (equal "none\n" (nth 1 (todo-test--ok "doing" "--priority" "B"))))
  (should (equal "none\n" (nth 1 (todo-test--ok "doing" "--priority" "B"))))
  (should (eq 1 (nth 0 (todo-test--cli "doing" "--priority" "High")))))

(ert-deftest todo-task-line-is-the-heading ()
  (todo-test--setup)
  (todo-test--write "* TODO First\nnote\n* TODO Second\n")
  (should (eq 1 (todo--task-line (todo-test--file) "First")))
  (should (eq 3 (todo--task-line (todo-test--file) "Second"))))

(ert-deftest todo-editor-command-includes-the-line ()
  (should (equal (todo--editor-command "mvim -f" "/tmp/a.org" 12)
                 "mvim -f +12 /tmp/a.org")))

(ert-deftest todo-editor-uses-mvim-without-a-tty ()
  (should (equal (todo--editor-for "vim" nil "/m/mvim") "vim"))
  (should (equal (todo--editor-for "vim" "todo-skill" "/m/mvim") "mvim -f"))
  (should (equal (todo--editor-for "nvim" "todo-skill" nil) "nvim"))
  (should (equal (todo--editor-for "mvim -f" "todo-skill" "/m/mvim") "mvim -f"))
  (should (equal (todo--editor-for nil "todo-skill" "/m/mvim") "mvim -f")))

(ert-deftest todo-cli-runs-as-a-script ()
  (todo-test--setup)
  (let ((result (todo-test--spawn "create" "Spawned")))
    (should (eq 0 (nth 0 result)))
    (should (string-match-p "Spawned" (todo-test--text))))
  (let ((result (todo-test--spawn "bogus")))
    (should (eq 1 (nth 0 result)))
    (should (string-match-p "unknown command" (nth 2 result)))))

;;; blocks

(ert-deftest todo-ignores-headings-inside-blocks ()
  (todo-test--setup)
  (todo-test--write (concat "#+BEGIN_SRC org\n* TODO Call mom\n** TODO Pick a good time\n#+END_SRC\n\n"
                            "#+BEGIN_EXAMPLE\n* TODO Example\n#+END_EXAMPLE\n\n"
                            "* TODO Real\n"))
  (let ((out (nth 1 (todo-test--ok "read"))))
    (should (string-match-p "Real" out))
    (should-not (string-match-p "Call mom" out))
    (should-not (string-match-p "Example" out)))
  (let ((result (todo-test--cli "complete" "Call mom")))
    (should (eq 1 (nth 0 result)))
    (should (string-match-p "not a task heading" (nth 2 result)))))

;;; help

(ert-deftest todo-help-lists-every-verb ()
  (todo-test--setup)
  (let ((result (todo-test--cli)))
    (should (eq 0 (nth 0 result)))
    (let ((out (nth 1 result)))
      (should (string-match-p "usage: todo <verb>" out))
      (dolist (verb '("resolve" "doing" "read" "create" "complete" "config"))
        (should (string-match-p (format "^  %s " verb) out))))))

(ert-deftest todo-help-verb-prints-usage-options-and-example ()
  (todo-test--setup)
  (let ((result (todo-test--cli "create" "--help")))
    (should (eq 0 (nth 0 result)))
    (should (string-empty-p (nth 2 result)))
    (let ((out (nth 1 result)))
      (should (string-match-p "^usage: todo create <title>" out))
      (should (string-match-p "^options:$" out))
      (should (string-match-p "--deadline D" out))
      (should (string-match-p "^example:$" out)))))

(ert-deftest todo-help-takes-h-in-any-position ()
  (todo-test--setup)
  (should (eq 0 (nth 0 (todo-test--cli "-h"))))
  (should (eq 0 (nth 0 (todo-test--cli "--help"))))
  (should (string-match-p "usage: todo read" (nth 1 (todo-test--cli "read" "-h"))))
  (should (string-match-p "usage: todo read" (nth 1 (todo-test--cli "--help" "read")))))

(ert-deftest todo-help-does-not-touch-the-board ()
  (todo-test--setup)
  (todo-test--ok "create" "First")
  (let ((before (todo-test--text)))
    (todo-test--ok "create" "--help")
    (todo-test--ok "delete" "First" "--help")
    (should (equal before (todo-test--text)))))

(ert-deftest todo-help-covers-every-verb ()
  ;; A verb with no entry would be missing from the main help; this fails
  ;; until the table above grows the same entry.
  (should (equal (mapcar #'car todo-help)
                 '("resolve" "doing" "read" "create" "rename" "delete"
                   "set-state" "set-deadline" "postpone" "set-priority" "set-effort"
                   "add-tag" "remove-tag" "append" "set-note" "obsolete" "complete"
                   "archive" "capture" "status" "edit" "edit-vim"
                   "edit-emacs" "config")))
  (dolist (spec todo-help)
    (should (plist-get (cdr spec) :summary))
    (should (plist-get (cdr spec) :example))
    (should (string-prefix-p "todo " (plist-get (cdr spec) :usage)))))

(ert-deftest todo-help-through-the-wrapper ()
  "The real entry point, `scripts/todo --help', as the user runs it."
  (let* ((out (generate-new-buffer "todo-out"))
         (code (call-process (expand-file-name "scripts/todo" todo-test--root)
                             nil out nil "--help"))
         (text (with-current-buffer out (prog1 (buffer-string) (kill-buffer out)))))
    (should (eq 0 code))
    (should (string-match-p "usage: todo <verb>" text))))

;;; read filters

(ert-deftest todo-read-due-sorts-most-urgent-first ()
  (todo-test--setup)
  ;; Dates far in the past, so the lateness gaps do not move with today.
  (todo-test--write (concat "* TODO [#D] Sheets\nDEADLINE: <2020-01-01 Wed>\n"
                            "* TODO [#A] Pay rent\nDEADLINE: <2020-02-01 Sat>\n"
                            "* TODO [#A] Tax\nDEADLINE: <2020-01-15 Wed>\n"
                            "* TODO Late but last\nDEADLINE: <2020-03-01 Sun>\n"
                            "* TODO Future\nDEADLINE: <2099-01-01 Thu>\n"))
  (let ((titles (lambda (out)
                  (mapcar (lambda (item) (todo-test--field item "title"))
                          (todo-test--records out)))))
    ;; Most days late first, then A before D: Sheets (D, most late), Tax and
    ;; Pay rent (both A, Tax later), then the task with no priority.
    (let ((expected '("Sheets" "Tax" "Pay rent" "Late but last")))
      (should (equal expected (funcall titles (nth 1 (todo-test--ok "read" "--due" "--records")))))
      (should (equal expected (funcall titles (nth 1 (todo-test--ok "read" "-d" "--records")))))
      (should (equal expected (funcall titles (nth 1 (todo-test--ok "read" "--overdue" "--records"))))))
    ;; Without --due the listing stays board order, the future task and all.
    (should (equal '("Sheets" "Pay rent" "Tax" "Late but last" "Future")
                   (funcall titles (nth 1 (todo-test--ok "read" "--records")))))
    ;; -n cuts the sorted head, the most urgent N.
    (should (equal '("Sheets" "Tax")
                   (funcall titles (nth 1 (todo-test--ok "read" "--due" "-n" "2" "--records")))))
    ;; One comparator orders both, so `doing' picks that same head.
    (should (equal "Sheets"
                   (todo-test--field (car (todo-test--records
                                           (nth 1 (todo-test--ok "doing"))))
                                     "title")))))

(ert-deftest todo-read-due-keeps-open-work-only ()
  (todo-test--setup)
  (todo-test--write (concat "* TODO Open late\nDEADLINE: <2020-01-01 Wed>\n"
                            "* IN_PROGRESS Working late\nDEADLINE: <2020-01-02 Thu>\n"
                            "* LATER Deferred late\nDEADLINE: <2020-01-03 Fri>\n"
                            "* OPTIONAL Optional late\nDEADLINE: <2020-01-04 Sat>\n"
                            "* OBSOLETE Dropped late\nDEADLINE: <2020-01-05 Sun>\n"))
  (let ((titles (lambda (out)
                  (mapcar (lambda (item) (todo-test--field item "title"))
                          (todo-test--records out)))))
    ;; Open work only, most late first.
    (let ((expected '("Open late" "Working late")))
      (should (equal expected (funcall titles (nth 1 (todo-test--ok "read" "--due" "--records")))))
      (should (equal expected (funcall titles (nth 1 (todo-test--ok "read" "-d" "--records")))))
      (should (equal expected (funcall titles (nth 1 (todo-test--ok "read" "--overdue" "--records"))))))
    ;; `--state' names a state and wins on its own.
    (should (equal '("Deferred late")
                   (funcall titles (nth 1 (todo-test--ok "read" "--due" "--state" "LATER" "--records")))))
    (should (equal '("Dropped late")
                   (funcall titles (nth 1 (todo-test--ok "read" "--due" "--state" "OBSOLETE" "--records")))))
    (should (equal '("Open late")
                   (funcall titles (nth 1 (todo-test--ok "read" "--due" "--state" "TODO" "--records")))))
    ;; Plain read still shows every state.
    (should (equal '("Open late" "Working late" "Deferred late" "Optional late" "Dropped late")
                   (funcall titles (nth 1 (todo-test--ok "read" "--records")))))))

(ert-deftest todo-read-filters-priority-and-takes-the-first-n ()
  (todo-test--setup)
  (todo-test--ok "create" "Alpha" "-p" "A")
  (todo-test--ok "create" "Bravo" "-p" "B")
  (todo-test--ok "create" "Delta" "-p" "D")
  (todo-test--ok "create" "Plain")
  (let ((a (nth 1 (todo-test--ok "read" "-p" "A")))
        (d (nth 1 (todo-test--ok "read" "--priority" "D"))))
    (should (string-match-p "Alpha" a))
    (should-not (string-match-p "Bravo\\|Delta\\|Plain" a))
    (should (string-match-p "Delta" d))
    (should-not (string-match-p "Alpha\\|Plain" d)))
  ;; Board order, as a plain `read' prints; -n cuts that list.
  (let* ((all (split-string (nth 1 (todo-test--ok "read")) "\n" t))
         (one (split-string (nth 1 (todo-test--ok "read" "-n" "1")) "\n" t))
         (two (split-string (nth 1 (todo-test--ok "read" "--number" "2")) "\n" t))
         (counted (split-string (nth 1 (todo-test--ok "read" "-n" "9")) "\n" t)))
    (should (equal 4 (length all)))
    (should (equal (list (car all)) one))
    (should (equal (cl-subseq all 0 2) two))
    (should (equal all counted))))

(ert-deftest todo-read-refuses-a-bad-number-and-priority ()
  (todo-test--setup)
  (let ((zero (todo-test--cli "read" "-n" "0"))
        (word (todo-test--cli "read" "--number" "two"))
        (bad (todo-test--cli "read" "-p" "Z")))
    (should (eq 1 (nth 0 zero)))
    (should (string-match-p "number takes a positive count" (nth 2 zero)))
    (should (eq 1 (nth 0 word)))
    (should (string-match-p "number takes a positive count" (nth 2 word)))
    (should (eq 1 (nth 0 bad)))
    (should (string-match-p "priority takes A, B, C or D" (nth 2 bad)))))

(ert-deftest todo-read-due-is-overdue-including-today ()
  (todo-test--setup)
  (let ((today (format-time-string "%Y-%m-%d" nil "Asia/Kolkata")))
    (todo-test--ok "create" "Due today" "--deadline" today)
    (todo-test--ok "create" "Future" "--deadline" "2099-01-01")
    (let ((due (nth 1 (todo-test--ok "read" "--due")))
          (overdue (nth 1 (todo-test--ok "read" "--overdue")))
          (short (nth 1 (todo-test--ok "read" "-d"))))
      (should (string-match-p "Due today" due))
      (should-not (string-match-p "Future" due))
      (should (equal overdue due))
      (should (equal short due)))))

(ert-deftest todo-priority-d-is-a-fourth-level ()
  (todo-test--setup)
  (todo-test--ok "create" "Low thing" "-p" "D")
  (should (string-match-p "^\\* TODO \\[#D\\] Low thing$" (todo-test--text)))
  (let ((pick (car (todo-test--records (nth 1 (todo-test--ok "doing" "-p" "D"))))))
    (should (equal "Low thing" (todo-test--field pick "title"))))
  (todo-test--ok "set-priority" "Low thing" "A")
  (should (string-match-p "\\[#A\\] Low thing" (todo-test--text)))
  (should (eq 1 (nth 0 (todo-test--cli "create" "Bad" "-p" "E"))))
  (should (eq 1 (nth 0 (todo-test--cli "set-priority" "Low thing" "Z"))))
  (should (eq 1 (nth 0 (todo-test--cli "doing" "--priority" "Z"))))
  (should (eq 3 (todo--priority-rank "D")))
  (should (eq 4 (todo--priority-rank nil))))

;;; archive

(ert-deftest todo-read-and-refs-skip-the-archive-container ()
  (todo-test--setup)
  (todo-test--write (concat "* TODO Live\n\n" (make-string 40 ?\n)
                            "* Archive\n** DONE Old work\n\n** OBSOLETE Dropped\n"))
  (let ((out (nth 1 (todo-test--ok "read"))))
    (should (string-match-p "Live" out))
    (should-not (string-match-p "Old work" out))
    (should-not (string-match-p "Dropped" out)))
  (let ((result (todo-test--cli "complete" "Old work")))
    (should (eq 1 (nth 0 result)))
    (should (string-match-p "not a task heading" (nth 2 result)))))

;;; concurrency

(ert-deftest todo-concurrent-creates-both-land ()
  (todo-test--setup)
  (let* ((script (expand-file-name "scripts/todo.el" todo-test--root))
         (default-directory (file-name-as-directory todo-test--dir))
         (process-environment (cons (concat "TODO_SKILL_CONFIG=" todo-test--config)
                                    process-environment))
         (procs (mapcar (lambda (title)
                          (make-process :name title :noquery t :buffer nil
                                        :command (list "emacs" "-Q" "--batch" "-l" script
                                                       "--" "create" title)))
                        '("One" "Two")))
         (deadline (+ (float-time) 30)))
    (while (and (cl-some #'process-live-p procs) (< (float-time) deadline))
      (accept-process-output nil 0.1))
    (let ((text (todo-test--text)))
      (should (string-match-p "^\\* TODO One$" text))
      (should (string-match-p "^\\* TODO Two$" text)))))

(provide 'todo-tests)
