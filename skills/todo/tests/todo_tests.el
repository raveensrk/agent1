;;; todo_tests.el --- ERT for the todo skill -*- lexical-binding: t; -*-

;; Run with:
;;
;;   emacs -Q --batch -l tests/todo_tests.el -f ert-run-tests-batch-and-exit

(require 'ert)
(require 'cl-lib)
(require 'json)

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
    (should-not (string-match-p ":ID:\\|:CREATED:" text))))

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
  (let ((result (todo-test--cli "create" "--help")))
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

(defun todo-test--json (stdout)
  (json-parse-string stdout :object-type 'alist :array-type 'list :null-object nil))

(defun todo-test--field (item key)
  (alist-get (intern key) item))

(ert-deftest todo-read-json-has-the-card-fields ()
  (todo-test--setup)
  (todo-test--write (concat "* TODO [#A] Pay rent :finance:\n"
                            "DEADLINE: <2026-11-05 Thu>\n"
                            ":PROPERTIES:\n:ID: abc\n:END:\n"
                            "paid \"cash\"\n"
                            "line two\n"
                            "* DONE Say \"hi\"\n"
                            "* TODO Apr\u2013Jun\n"
                            "* Archive\n** DONE Old\n"))
  (let ((hidden (expand-file-name "node_modules/hidden.org" todo-test--dir)))
    (make-directory (file-name-directory hidden) t)
    (with-temp-file hidden (insert "* TODO Hidden\n")))
  (let* ((items (todo-test--json (nth 1 (todo-test--ok "read" "--json"))))
         (pay (cl-find "Pay rent" items :key (lambda (i) (todo-test--field i "title")) :test #'equal))
         (other (cl-find "Say \"hi\"" items :key (lambda (i) (todo-test--field i "title")) :test #'equal))
         (dash (cl-find "Apr\u2013Jun" items :key (lambda (i) (todo-test--field i "title")) :test #'equal)))
    (should (eq 3 (length items)))
    (should dash)
    (should (equal (todo-test--field pay "state") "TODO"))
    (should (equal (todo-test--field pay "deadline") "<2026-11-05 Thu>"))
    (should (equal (todo-test--field pay "priority") "A"))
    (should (equal (todo-test--field pay "tags") '("finance")))
    (should (equal (todo-test--field pay "note") "paid \"cash\"\nline two"))
    (should-not (string-match-p "DEADLINE\\|:ID:" (todo-test--field pay "note")))
    (should (string-match-p "todo.org$" (todo-test--field pay "path")))
    (should-not (todo-test--field other "deadline"))
    (should-not (todo-test--field other "priority"))
    (should (equal (todo-test--field other "state") "DONE"))
    (should (equal (todo-test--field other "note") ""))
    (should-not (cl-find "Old" items :key (lambda (i) (todo-test--field i "title")) :test #'equal))
    (should-not (cl-find "Hidden" items :key (lambda (i) (todo-test--field i "title")) :test #'equal)))
  (let ((done (todo-test--json (nth 1 (todo-test--ok "read" "--json" "--state" "DONE")))))
    (should (equal (mapcar (lambda (i) (todo-test--field i "title")) done) '("Say \"hi\""))))
  (should (equal (nth 1 (todo-test--ok "read" "--json" "--state" "OBSOLETE")) "[]\n")))

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

(ert-deftest todo-set-effort-writes-the-property ()
  (todo-test--setup)
  (todo-test--write "* TODO Buy milk\n")
  (todo-test--ok "set-effort" "Buy milk" "0:15")
  (should (string-match-p "^ *:Effort: +0:15$" (todo-test--text)))
  (should (eq 1 (nth 0 (todo-test--cli "set-effort" "Buy milk" "15")))))

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

(ert-deftest todo-complete-writes-done-closed-and-evidence ()
  (todo-test--setup)
  (todo-test--ok "create" "Pay rent")
  (todo-test--ok "complete" "Pay rent" "--evidence" "paid via bank transfer")
  (let ((text (todo-test--text)))
    (should (string-match-p "^\\* DONE Pay rent$" text))
    (should (string-match-p "^CLOSED: \\[" text))
    (should (string-match-p "^paid via bank transfer$" text))))

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
    (should (string-match-p "^tasks: 2$" out))))

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
            (should (eq 0 (call-process script nil (list out nil) nil "--warm" "read" "--json")))
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
                                         (path . ,file)
                                         (deadline . "<2026-09-28 Mon>"))))
                (repeat (todo-doing-item `((title . "Repeat")
                                           (path . ,file)
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
  (let ((item (todo-test--json (nth 1 (todo-test--ok "doing" "--json")))))
    (should (equal (todo-test--field item "title") "Old"))
    (should (equal (todo-test--field item "state") "TODO")))
  (todo-test--ok "set-state" "Old" "DONE")
  (should (equal (nth 1 (todo-test--ok "doing" "--json")) "null\n")))

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
    (should (equal 1 (length (split-string lines "\n" t))))
    (should (string-match-p "Alpha" lines)))
  (should (equal "Alpha"
                 (todo-test--field
                  (todo-test--json (nth 1 (todo-test--ok "doing" "--priority" "A" "--json")))
                  "title")))
  (should (equal "none\n" (nth 1 (todo-test--ok "doing" "--priority" "B"))))
  (should (equal "null\n" (nth 1 (todo-test--ok "doing" "--priority" "B" "--json"))))
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
