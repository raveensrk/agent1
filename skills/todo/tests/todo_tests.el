;;; todo_tests.el --- ERT for the todo skill -*- lexical-binding: t; -*-

;; Run with:
;;
;;   emacs -Q --batch -l tests/todo_tests.el -f ert-run-tests-batch-and-exit

(require 'ert)
(require 'cl-lib)

(defconst todo-test--root
  (file-name-directory
   (directory-file-name
    (file-name-directory (expand-file-name (or load-file-name buffer-file-name)))))
  "The skill directory.")

(load (expand-file-name "scripts/todo.el" todo-test--root))

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

(defun todo-test--cli (&rest args)
  "Run the CLI in the test dir with ARGS. Returns (code stdout stderr)."
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
