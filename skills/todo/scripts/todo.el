;;; todo.el --- the todo skill's CLI, in Emacs org-mode -*- lexical-binding: t; -*-

;; The only writer of board files. No locks, no ids, no frontmatter: a board
;; is plain org headings and the states live here.
;;
;;   emacs -Q --batch -l todo.el -- <verb> [args]
;;   scripts/todo <verb> [args]          (wrapper)
;;
;; Concurrent writers are fine: every write replaces the file atomically and
;; retries with fresh content when another process wrote it meanwhile.
;; See SKILL.md for the rules.

(require 'org)
(require 'cl-lib)

;;; Setup

(defconst todo-states '("TODO" "IN_PROGRESS" "OPTIONAL" "LATER" "DONE" "OBSOLETE")
  "The state words the skill knows.")

(defconst todo-value-flags '("--file" "--state" "--tag" "--container" "--deadline"
                             "--priority" "--note" "--dir" "--editor" "--evidence")
  "Flags that take a value.")

(setq org-todo-keywords '((sequence "TODO" "IN_PROGRESS" "OPTIONAL" "LATER"
                                    "|" "DONE" "OBSOLETE"))
      org-log-done 'time                ; DONE writes CLOSED:
      org-tags-column 0                 ; tags right after the title
      org-adapt-indentation nil
      create-lockfiles nil
      make-backup-files nil
      auto-save-default nil
      org-element-use-cache nil)

;;; Errors and output

(defun todo-fail (msg)
  "Print MSG to stderr and exit non-zero."
  (princ (concat msg "\n") #'external-debugging-output)
  (kill-emacs 1))

(defun todo-out (pairs)
  "Print PAIRS as `key: value' lines."
  (dolist (pair pairs)
    (let ((value (cdr pair)))
      (princ (format "%s: %s\n" (car pair)
                     (cond ((eq value t) "yes")
                           ((null value) "no")
                           (t value)))))))

;;; Config

(defconst todo-config-file
  (or (getenv "TODO_SKILL_CONFIG")
      (expand-file-name "~/dot_local/config/todo_skill.toml"))
  "The skill config: default_dirs and ignore.")

(defun todo--strings (text)
  "The quoted strings in TEXT, in order."
  (let (out (start 0))
    (while (string-match "\"\\([^\"]*\\)\"" text start)
      (push (match-string 1 text) out)
      (setq start (match-end 0)))
    (nreverse out)))

(defun todo-config ()
  "The loaded config as an alist: default_dirs and ignore."
  (let (dirs ignore)
    (when (file-exists-p todo-config-file)
      (let ((text (with-temp-buffer (insert-file-contents todo-config-file) (buffer-string))))
        (when (string-match "^[ \t]*default_dirs[ \t]*=[ \t]*\\[\\([^]]*\\)\\]" text)
          (setq dirs (mapcar #'expand-file-name (todo--strings (match-string 1 text)))))
        (when (string-match "^[ \t]*ignore[ \t]*=[ \t]*\\[\\([^]]*\\)\\]" text)
          (setq ignore (todo--strings (match-string 1 text))))))
    (list (cons 'default_dirs dirs) (cons 'ignore ignore))))

;;; Paths

(defun todo-board (&optional file)
  "The board file: FILE, or todo.org in the cwd."
  (expand-file-name (or file "todo.org")))

(defun todo--existing (file)
  "The board file, which must exist."
  (let ((board (todo-board file)))
    (unless (file-exists-p board)
      (todo-fail (format "%s does not exist" board)))
    board))

(defun todo-ignored-p (path patterns)
  "Config semantics: a bare name matches a path component, an entry with a
slash matches that run of components, a glob is a glob, and an absolute or
~/ entry matches that exact path and below."
  (let ((text (expand-file-name path)))
    (cl-some
     (lambda (p)
       (cond
        ((string-prefix-p "~" p)
         (let ((base (expand-file-name p)))
           (or (equal text base) (string-prefix-p (concat base "/") text))))
        ((string-prefix-p "/" p)
         (or (equal text p) (string-prefix-p (concat p "/") text)))
        ((string-match-p "[*?[]" p)
         (or (string-match-p (wildcard-to-regexp p) text)
             (string-match-p (wildcard-to-regexp p) (file-name-nondirectory path))))
        ((string-match-p "/" p)
         (or (equal text p)
             (string-suffix-p (concat "/" p) text)
             (string-match-p (concat "/" (regexp-quote p) "/") text)))
        (t (member p (split-string text "/")))))
     patterns)))

;;; Reading

(defun todo--files (dir ignore)
  "Every .org file under DIR, minus ignored paths and hidden directories."
  (cl-remove-if
   (lambda (file) (todo-ignored-p file ignore))
   (directory-files-recursively
    dir "\\.org\\'"
    nil
    (lambda (sub)
      (and (not (string-prefix-p "." (file-name-nondirectory sub)))
           (not (todo-ignored-p sub ignore)))))))

(defun todo--archived-p ()
  "Non-nil when the heading at point sits inside a container titled Archive."
  (save-excursion
    (let (found)
      (while (and (not found) (org-up-heading-safe))
        (when (equal (org-get-heading t t t t) "Archive")
          (setq found t)))
      found)))

(defun todo-tasks (file)
  "Every live task heading in FILE; the Archive container is history."
  (with-temp-buffer
    (insert-file-contents file)
    (org-mode)
    (let (out)
      (org-map-entries
       (lambda ()
         (let ((state (org-get-todo-state)))
           (when (and (member state todo-states) (not (todo--archived-p)))
             (push (list (cons 'file file)
                         (cons 'path file)
                         (cons 'todo state)
                         (cons 'title (org-get-heading t t t t))
                         (cons 'tags (org-get-tags)))
                   out)))))
      (nreverse out))))

(defun todo-read (dirs state tag)
  "Tasks from DIRS, or the configured dirs, plus the cwd board."
  (let* ((config (todo-config))
         (ignore (alist-get 'ignore config))
         (roots (or dirs (alist-get 'default_dirs config)))
         (items nil))
    (dolist (dir roots)
      (when (file-directory-p dir)
        (dolist (file (todo--files dir ignore))
          (setq items (append items (todo-tasks file))))))
    (let ((board (todo-board)))
      (when (and (file-exists-p board)
                 (not (cl-some (lambda (dir)
                                 (and (file-directory-p dir) (file-in-directory-p board dir)))
                               roots))
                 (not (todo-ignored-p board ignore)))
        (setq items (append items (todo-tasks board)))))
    (when state
      (setq items (cl-remove-if-not (lambda (i) (equal (alist-get 'todo i) state)) items)))
    (when tag
      (setq items (cl-remove-if-not (lambda (i) (member tag (alist-get 'tags i))) items)))
    items))

;;; Writing

(defun todo--atomic (file text)
  "Replace FILE with TEXT in one rename, so readers never see a half file."
  (let ((tmp (make-temp-name (concat file ".tmp"))))
    (write-region text nil tmp nil 'silent)
    (rename-file tmp file t)))

(defun todo-write (file fn)
  "Apply FN to FILE's content and replace the file atomically. When another
process wrote FILE meanwhile, retry with fresh content, so concurrent
writers never clobber each other."
  (make-directory (file-name-directory file) t)
  (let ((tries 0) done)
    (while (not done)
      (let* ((exists (file-exists-p file))
             (orig (if exists
                       (with-temp-buffer (insert-file-contents file) (buffer-string))
                     ""))
             (stamp (and exists (file-attribute-modification-time (file-attributes file))))
             (text (with-temp-buffer
                     (insert orig)
                     (org-mode)
                     (funcall fn)
                     (goto-char (point-max))
                     (unless (or (bobp) (eq (char-before) ?\n)) (insert "\n"))
                     (buffer-string))))
        (cond
         ;; Two writers creating the same board: one wins the O_EXCL create,
         ;; the loser retries on the winner's content.
         ((null exists)
          (if (condition-case nil
                  (progn (write-region text nil file nil nil nil 'excl) t)
                (file-already-exists nil))
              (setq done t)
            (todo--retry (cl-incf tries))))
         ((equal stamp (and (file-exists-p file)
                            (file-attribute-modification-time (file-attributes file))))
          (todo--atomic file text)
          (setq done t))
         (t (todo--retry (cl-incf tries))))))))

(defun todo--retry (tries)
  "Wait out a lost race; give up after five tries."
  (when (>= tries 5)
    (todo-fail "the board changed while writing; retry"))
  (sleep-for 0.05))

(defun todo--goto (title)
  "Move to the task named TITLE. Fail when it is absent or ambiguous."
  (let (marker (count 0))
    (org-map-entries
     (lambda ()
       (when (and (member (org-get-todo-state) todo-states)
                  (not (todo--archived-p))
                  (equal (org-get-heading t t t t) title))
         (cl-incf count)
         (unless marker (setq marker (point-marker))))))
    (cond ((null marker) (todo-fail (format "%S is not a task heading in this file" title)))
          ((> count 1) (todo-fail (format "more than one heading matches %S; refine the ref" title))))
    (goto-char marker)
    (set-marker marker nil)))

(defun todo--goto-heading (title)
  "Move to the heading named TITLE, task or container."
  (let (marker)
    (org-map-entries
     (lambda ()
       (when (equal (org-get-heading t t t t) title)
         (unless marker (setq marker (point-marker))))))
    (unless marker (todo-fail (format "headline not found: %s" title)))
    (goto-char marker)
    (set-marker marker nil)))

(defun todo--append-body (text)
  "Append TEXT to the body of the task at point, after its last line."
  (org-end-of-subtree)
  (skip-chars-backward " \t\n")
  (insert "\n" text))

(defun todo--append-root (text)
  "Append a plain level-1 heading TEXT at the end of the buffer and move to it."
  (goto-char (point-max))
  (skip-chars-backward " \t\n")
  (delete-region (point) (point-max))
  (if (= (point) (point-min))
      (insert "* " text "\n")
    (insert "\n\n* " text "\n"))
  (forward-line -1))

;;; Verbs

(defun todo--flag (flags name)
  "The value given for flag NAME."
  (cdr (assoc name flags)))

(defun todo--flags (flags name)
  "All values given for flag NAME."
  (cl-loop for (key . value) in flags when (equal key name) collect value))

(defun todo-create (rest flags)
  (let* ((title (car rest))
         (board (todo-board (todo--flag flags "--file")))
         (state (or (todo--flag flags "--state") "TODO"))
         (container (todo--flag flags "--container"))
         (deadline (todo--flag flags "--deadline"))
         (priority (todo--flag flags "--priority"))
         (note (todo--flag flags "--note"))
         (tags (todo--flags flags "--tag")))
    (unless title (todo-fail "create needs a title"))
    (unless (member state todo-states) (todo-fail (format "unknown state %s" state)))
    (todo-write
     board
     (lambda ()
       (if container
           (progn
             (todo--goto-heading container)
             (org-end-of-subtree)
             (org-insert-subheading nil)
             (insert title))
         (todo--append-root title))
       (org-todo state)
       (when priority (org-priority (string-to-char priority)))
       (when tags (org-set-tags tags))
       (when deadline (org-deadline nil deadline))
       (when note (todo--append-body note))))
    (todo-out (list (cons 'title title) (cons 'file board) (cons 'state state)))))

(defun todo-run (pos flags)
  "Dispatch one CLI call: POS are the positionals, FLAGS the parsed options."
  (let* ((verb (car pos))
         (rest (cdr pos))
         (file (todo--flag flags "--file"))
         (dirs (mapcar #'expand-file-name (todo--flags flags "--dir"))))
    (pcase verb
      ("resolve"
       (let* ((dir (or (car dirs) default-directory))
              (board (if file (expand-file-name file) (expand-file-name "todo.org" dir))))
         (todo-out (list (cons 'file board)
                         (cons 'dir (file-name-directory board))
                         (cons 'exists (file-exists-p board))))))

      ("read"
       (dolist (item (todo-read dirs (todo--flag flags "--state") (car (todo--flags flags "--tag"))))
         (princ (format "%-12s %s  (%s)\n"
                        (alist-get 'todo item) (alist-get 'title item) (alist-get 'path item)))))

      ("create"
       (todo-create rest flags))

      ("rename"
       (let ((title (cadr rest)))
         (unless (and (car rest) title) (todo-fail "rename needs a ref and a title"))
         (when (string-empty-p (string-trim title)) (todo-fail "the title must not be empty"))
         (let ((board (todo--existing file)))
           (todo-write board (lambda () (todo--goto (car rest)) (org-edit-headline title)))
           (todo-out (list (cons 'title title) (cons 'file board))))))

      ("delete"
       (let ((board (todo--existing file)))
         (todo-write board (lambda () (todo--goto (car rest)) (org-cut-subtree)))
         (todo-out (list (cons 'title (car rest)) (cons 'file board)))))

      ("set-state"
       (let ((state (cadr rest)))
         (unless (member state todo-states) (todo-fail (format "unknown state %s" state)))
         (let ((board (todo--existing file)))
           (todo-write board (lambda () (todo--goto (car rest)) (org-todo state)))
           (todo-out (list (cons 'title (car rest)) (cons 'file board) (cons 'state state))))))

      ("set-deadline"
       (let ((board (todo--existing file)))
         (todo-write board (lambda () (todo--goto (car rest)) (org-deadline nil (cadr rest))))
         (todo-out (list (cons 'title (car rest)) (cons 'file board) (cons 'deadline (cadr rest))))))

      ("add-tag"
       (let ((board (todo--existing file)))
         (todo-write board (lambda () (todo--goto (car rest)) (org-toggle-tag (cadr rest) 'on)))
         (todo-out (list (cons 'title (car rest)) (cons 'file board) (cons 'tag (cadr rest))))))

      ("remove-tag"
       (let ((board (todo--existing file)))
         (todo-write board (lambda () (todo--goto (car rest)) (org-toggle-tag (cadr rest) 'off)))
         (todo-out (list (cons 'title (car rest)) (cons 'file board) (cons 'tag (cadr rest))))))

      ("append"
       (let ((board (todo--existing file)))
         (todo-write board (lambda () (todo--goto (car rest)) (todo--append-body (cadr rest))))
         (todo-out (list (cons 'title (car rest)) (cons 'file board)))))

      ("obsolete"
       (let ((board (todo--existing file)))
         (todo-write board (lambda () (todo--goto (car rest)) (org-todo "OBSOLETE")))
         (todo-out (list (cons 'title (car rest)) (cons 'file board) (cons 'state "OBSOLETE")))))

      ("complete"
       (let ((board (todo--existing file))
             (evidence (todo--flag flags "--evidence")))
         (todo-write board
                     (lambda ()
                       (todo--goto (car rest))
                       (when evidence (todo--append-body evidence))
                       (org-todo "DONE")))
         (todo-out (list (cons 'title (car rest)) (cons 'file board) (cons 'state "DONE")))))

      ("capture"
       (let ((text (car rest)))
         (unless text (todo-fail "capture needs text"))
         (let ((board (todo-board file)))
           (todo-write board (lambda () (todo--append-root text)))
           (todo-out (list (cons 'title text) (cons 'file board))))))

      ("status"
       (let* ((board (todo-board file))
              (exists (file-exists-p board)))
         (todo-out (list (cons 'file board)
                         (cons 'exists exists)
                         (cons 'tasks (if exists (length (todo-tasks board)) 0))))))

      ("edit"
       (let* ((board (todo--existing file))
              (editor (or (todo--flag flags "--editor") (getenv "EDITOR") "mvim -f"))
              (code (call-process-shell-command
                     (concat editor " " (shell-quote-argument board)))))
         (unless (eq code 0) (todo-fail (format "%s exited %d" editor code)))
         (todo-out (list (cons 'file board) (cons 'editor editor)))))

      ("config"
       (let ((config (todo-config)))
         (todo-out (list (cons 'default_dirs
                               (mapconcat #'identity (alist-get 'default_dirs config) ", "))
                         (cons 'ignore
                               (mapconcat #'identity (alist-get 'ignore config) ", "))))))

      (_ (todo-fail (format "unknown command %s" (or verb "(none)")))))))

;;; CLI

(defun todo-main ()
  "Parse the command line and run one verb."
  (let ((args command-line-args-left)
        (flags nil)
        (pos nil))
    (when (equal (car args) "--") (setq args (cdr args)))
    (while args
      (let ((arg (car args)))
        (if (member arg todo-value-flags)
            (progn
              (unless (cadr args) (todo-fail (format "%s needs a value" arg)))
              (push (cons arg (cadr args)) flags)
              (setq args (cddr args)))
          (push arg pos)
          (setq args (cdr args)))))
    (condition-case err
        (let ((inhibit-message t))     ; org's progress notes stay out of stderr
          (todo-run (nreverse pos) (nreverse flags)))
      (error (todo-fail (error-message-string err))))))

(provide 'todo)

;; Run only when invoked as a script (the wrapper passes --), not when the
;; test suite loads this file.
(when (equal (car command-line-args-left) "--")
  (todo-main))
