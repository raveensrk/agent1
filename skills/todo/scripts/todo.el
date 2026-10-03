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

(defconst todo-priorities '("A" "B" "C" "D")
  "The priority cookies the CLI writes and filters on. D is the lowest level,
and `org-lowest-priority' below is set to it: org's own default, C, refuses D.")

(defconst todo-flag-aliases '(("-d" . "--due") ("-n" . "--number") ("-p" . "--priority"))
  "Short flag -> long flag. The parser rewrites them, so every verb sees one
spelling of each flag.")

(defconst todo-due-flags '("--due" "--overdue")
  "The two names of one window: the deadline day is today or earlier in IST.")

(defconst todo-deadline-forms
  "2026-11-05, 2026-11-05 20:30 or <2026-11-05 Thu 20:30 +1w>"
  "The deadline forms the CLI accepts, as refusals and SKILL.md print them.")

(defconst todo-value-flags '("--file" "--state" "--tag" "--container" "--deadline"
                             "--priority" "--note" "--dir" "--editor" "--evidence"
                             "--effort" "--number")
  "Flags that take a value.")

(setq org-todo-keywords '((sequence "TODO" "IN_PROGRESS" "OPTIONAL" "LATER"
                                    "|" "DONE" "OBSOLETE"))
      org-log-done 'time                ; DONE writes CLOSED:
      ;; The fourth level. Org's own lowest priority is C and refuses [#D].
      org-lowest-priority ?D
      org-tags-column 0                 ; tags right after the title
      org-adapt-indentation nil
      create-lockfiles nil
      make-backup-files nil
      auto-save-default nil
      org-element-use-cache nil
      ;; A long-lived daemon with the 800 KB default spends its scans in GC:
      ;; the same directory walk took 0.956 s there and 0.58 s in a fresh
      ;; process, and 0.55 s in the daemon once the threshold was raised
      ;; (32 MB already gets it; 64 MB measured the same).
      gc-cons-threshold (* 64 1024 1024)
      ;; en_IN.UTF-8 resolves to a non-UTF-8 coding system, and a daemon then
      ;; asks which one to use and waits for a keypress. Force UTF-8: boards are.
      coding-system-for-write 'utf-8-unix)

;;; Errors and output

(defconst todo-loaded-file (or load-file-name buffer-file-name)
  "This file, as it was loaded.")

(defconst todo-loaded-stamp
  (let ((time (and todo-loaded-file (file-attribute-modification-time
                                     (file-attributes todo-loaded-file)))))
    (and time (format-time-string "%s" time)))
  "Modification time of the loaded file in epoch seconds.")

(defun todo-warm-stamp ()
  "The loaded file's stamp. The wrapper compares it with the file on disk: a
daemon started before an edit is stale and must be restarted."
  todo-loaded-stamp)

(define-error 'todo-warm-fail "todo warm failed")

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

(defun todo-config-file ()
  "The skill config path: default_dirs and ignore."
  (or (getenv "TODO_SKILL_CONFIG")
      (expand-file-name "~/dot_local/config/todo_skill.toml")))

(defun todo--strings (text)
  "The quoted strings in TEXT, in order."
  (let (out (start 0))
    (while (string-match "\"\\([^\"]*\\)\"" text start)
      (push (match-string 1 text) out)
      (setq start (match-end 0)))
    (nreverse out)))

(defun todo-config ()
  "The loaded config as an alist: default_dirs and ignore."
  (let ((file (todo-config-file))
        dirs ignore)
    (when (file-exists-p file)
      (let ((text (with-temp-buffer (insert-file-contents file) (buffer-string))))
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

(defun todo--archive-p (path)
  "Non-nil when PATH is a board's org archive file (`<board>.org_archive').
Archive files are history: no read, ref or write of the skill looks inside one,
and they are not boards. The `\.org\'' glob in `todo--files' already skips
them; this says so out loud, and checks a named path too."
  (string-match-p "_archive\'" path))

(defun todo--files (dir ignore)
  "Every .org file under DIR, minus ignored paths and hidden directories."
  (cl-remove-if
   (lambda (file) (or (todo--archive-p file) (todo-ignored-p file ignore)))
   (directory-files-recursively
    dir "\\.org\\'"
    nil
    (lambda (sub)
      (and (not (string-prefix-p "." (file-name-nondirectory sub)))
           (not (todo--archive-p sub))
           (not (todo-ignored-p sub ignore)))))))

(defvar todo--blocks nil
  "Character ranges of #+BEGIN_* ... #+END_* blocks in the current buffer.")

(defun todo--mark-blocks ()
  "Record the block ranges; a heading inside one is an example, not a task."
  (setq todo--blocks nil)
  (save-excursion
    (goto-char (point-min))
    (let (start)
      (while (re-search-forward "^[ \t]*#\\+\\(BEGIN\\|END\\)_" nil t)
        (if (equal (match-string 1) "BEGIN")
            (unless start (setq start (line-beginning-position)))
          (when start
            (push (cons start (line-end-position)) todo--blocks)
            (setq start nil))))
      (when start
        (push (cons start (point-max)) todo--blocks)))))

(defun todo--in-block-p ()
  "Non-nil when the line at point is inside a #+BEGIN_* block."
  (let ((pos (line-beginning-position)))
    (cl-some (lambda (range) (and (>= pos (car range)) (<= pos (cdr range))))
             todo--blocks)))

(defun todo--archived-p ()
  "Non-nil when the heading at point sits inside a container titled Archive."
  (save-excursion
    (let (found)
      (while (and (not found) (org-up-heading-safe))
        (when (equal (org-get-heading t t t t) "Archive")
          (setq found t)))
      found)))

(defun todo--priority ()
  "The [#A] cookie at point, or nil. Do not invent the default."
  (let ((pri (org-element-property :priority (org-element-at-point))))
    (and pri (char-to-string pri))))

(defun todo--note ()
  "Body after the planning line and drawers, up to the next heading."
  (save-excursion
    (let ((start (progn (org-end-of-meta-data t) (point))))
      (if (re-search-forward "^\\*+ " nil t)
          (goto-char (match-beginning 0))
        (goto-char (point-max)))
      (string-trim (buffer-substring-no-properties start (point))))))

(defun todo--editor-for (editor daemon mvim)
  "EDITOR to run. Terminal vim cannot run in the warm daemon."
  (let* ((editor (or editor "mvim -f"))
         (bin (file-name-nondirectory (car (split-string editor)))))
    (if (or (not daemon) (not (member bin '("vim" "vi" "nvim"))))
        editor
      (if mvim "mvim -f" editor))))

(defun todo--recurring (deadline)
  "Non-nil when DEADLINE carries a repeater, so the task is a routine.
Raveen's rule: a recurring task is always priority B."
  (and deadline (string-match-p "\\+[0-9]+[dwmy]" deadline)))

(defun todo--checked-effort (value)
  "VALUE as H:MM, or fail. Org's own Effort format."
  (unless (string-match-p "\\`[0-9]+:[0-5][0-9]\\'" value)
    (todo-fail (format "effort takes H:MM, got %s" value)))
  value)

(defun todo--checked-priority (value)
  "VALUE as A, B, C or D, or fail. Nil passes: the flag is optional."
  (when (and value (not (member value todo-priorities)))
    (todo-fail (format "priority takes A, B, C or D, got %s" value)))
  value)

(defun todo--checked-number (value)
  "VALUE as a positive integer, or fail. Nil passes: the flag is optional."
  (if (null value)
      nil
    (unless (string-match-p "\\`[1-9][0-9]*\\'" value)
      (todo-fail (format "number takes a positive count, got %s" value)))
    (string-to-number value)))

(defun todo--checked-deadline (value)
  "VALUE in one of the three accepted deadline forms, or fail.
A bare date, a date with a time, or a full org timestamp - the only form that
keeps a repeater. Prose, an out-of-range date and an unwrapped repeater are
refused: org would otherwise absorb them silently - garbage becomes today,
2026-13-45 becomes 2027-02-14."
  (let ((bare "\\`[0-9]\\{4\\}-[0-9]\\{2\\}-[0-9]\\{2\\}\\( [0-9]\\{2\\}:[0-9]\\{2\\}\\)?\\'")
        (stamp "\\`<[0-9]\\{4\\}-[0-9]\\{2\\}-[0-9]\\{2\\} [^>]+>\\'"))
    (unless (or (string-match-p bare value) (string-match-p stamp value))
      (todo-fail (format "deadline takes %s, got %s" todo-deadline-forms value)))
    (let* ((date (substring value (if (eq (aref value 0) ?<) 1 0)
                            (+ (if (eq (aref value 0) ?<) 1 0) 10)))
           (parts (mapcar #'string-to-number (split-string date "-")))
           (real (ignore-errors (apply #'encode-time 0 0 0 (nreverse parts)))))
      (unless (and real (equal date (format-time-string "%Y-%m-%d" real)))
        (todo-fail (format "%s is not a real date" date)))))
  value)

(defun todo--task-line (file title)
  "Line number of the task heading TITLE in FILE."
  (with-temp-buffer
    (insert-file-contents file)
    (org-mode)
    (todo--mark-blocks)
    (todo--goto title)
    (line-number-at-pos)))

(defun todo--editor-command (editor file line)
  "Shell command that opens FILE at LINE."
  (format "%s +%d %s" editor line (shell-quote-argument file)))

(defun todo--emacs-bin ()
  "The GUI Emacs binary, or emacs on PATH."
  (let ((app "/Applications/Emacs.app/Contents/MacOS/Emacs"))
    (if (file-executable-p app) app (or (executable-find "emacs") "emacs"))))

(defun todo--open-editor (editor file line)
  "Run EDITOR on FILE at LINE. Wait until it exits."
  (let* ((buf (generate-new-buffer " *editor*"))
         (code (call-process-shell-command
                (todo--editor-command editor file line)
                nil (cons buf buf))))
    (unwind-protect
        (unless (eq code 0)
          (todo-fail (format "%s exited %d%s" editor code
                             (let ((err (string-trim (with-current-buffer buf (buffer-string)))))
                               (if (string-empty-p err) "" (concat "\n" err))))))
      (kill-buffer buf))))

(defun todo--open-emacs (file line)
  "Open FILE at LINE in GUI Emacs. Do not wait for that Emacs to quit."
  (let* ((bin (todo--emacs-bin))
         (proc (start-process "todo-edit-emacs" nil bin (format "+%d" line) file)))
    (unless proc (todo-fail "emacs did not start"))
    (sit-for 0.3)
    (when (and (not (process-live-p proc))
               (not (eq 0 (process-exit-status proc))))
      (todo-fail (format "emacs exited %s" (process-exit-status proc))))))

(defun todo-edit (title file kind)
  "Open the heading TITLE in FILE with KIND, vim or emacs, at that line."
  (unless title (todo-fail "edit needs a ref"))
  (let* ((board (todo--existing file))
         (line (todo--task-line board title))
         (editor (if (equal kind "emacs")
                     (todo--emacs-bin)
                   (todo--editor-for "vim" (daemonp) (executable-find "mvim")))))
    (if (equal kind "emacs")
        (todo--open-emacs board line)
      (todo--open-editor editor board line))
    (todo-out (list (cons 'title title)
                    (cons 'file board)
                    (cons 'line line)
                    (cons 'editor editor)))))

(defun todo--record (item)
  "ITEM as one plain record: `key: value' lines, the note indented four spaces.
One record per task, records separated by a blank line. No serialization
layer: the CLI is Emacs reading org, and both consumers parse text."
  (let ((note (or (alist-get 'note item) "")))
    (concat
     (format (concat "title: %s\nstate: %s\ndeadline: %s\npriority: %s\n"
                     "effort: %s\ntags: %s\npath: %s\n")
             (alist-get 'title item)
             (alist-get 'todo item)
             (or (alist-get 'deadline item) "")
             (or (alist-get 'priority item) "")
             (or (alist-get 'effort item) "")
             (mapconcat #'identity (alist-get 'tags item) " ")
             (alist-get 'path item))
     (if (string-empty-p note)
         ""
       (concat (mapconcat (lambda (line) (concat "    " line))
                          (split-string note "\n") "\n")
               "\n")))))

(defun todo-print-records (items)
  "Print ITEMS as plain records separated by a blank line."
  (princ (mapconcat #'todo--record items "\n")))

(defconst todo-doing-states '("TODO" "IN_PROGRESS")
  "States that can be the main quest.")

(defun todo-ist-day (&optional time)
  "Absolute day of TIME in IST. TIME defaults to now."
  (let ((old (getenv "TZ"))
        (time (or time (current-time))))
    (setenv "TZ" "Asia/Kolkata")
    (unwind-protect
        (org-time-string-to-absolute (format-time-string "%Y-%m-%d" time))
      (if old (setenv "TZ" old) (setenv "TZ" nil)))))

(defun todo--due-day (deadline)
  "Absolute day of DEADLINE, or nil. Org reads the stamp, including a repeater."
  (and deadline (ignore-errors (org-time-string-to-absolute deadline))))

(defun todo--priority-rank (priority)
  "A is 0, D is 3. A missing priority sorts after D."
  (if (and priority (string-match "\\`[A-D]\\'" priority))
      (- (aref priority 0) ?A)
    4))

(defun todo-late-sort (items today)
  "ITEMS sorted the urgency way: most days late first, then A before D, then
title, then path. `doing' picks the head of it and `read --due' prints the whole
thing, so one definition orders both. Every item must carry a deadline - both
callers filter first."
  (sort items
        (lambda (a b)
          (let ((late-a (- today (todo--due-day (alist-get 'deadline a))))
                (late-b (- today (todo--due-day (alist-get 'deadline b))))
                (rank-a (todo--priority-rank (alist-get 'priority a)))
                (rank-b (todo--priority-rank (alist-get 'priority b))))
            (cond ((/= late-a late-b) (> late-a late-b))
                  ((/= rank-a rank-b) (< rank-a rank-b))
                  ((not (equal (alist-get 'title a) (alist-get 'title b)))
                   (string< (alist-get 'title a) (alist-get 'title b)))
                  (t (string< (alist-get 'path a) (alist-get 'path b))))))))

(defun todo-doing-pick (items today &optional priority)
  "The main quest in ITEMS for absolute day TODAY, or nil.
With PRIORITY, pick any open task at that priority instead, due or not, title
then path: the priority-only pick."
  (if priority
      (car (sort (cl-remove-if-not
                  (lambda (item)
                    (and (member (alist-get 'todo item) todo-doing-states)
                         (equal (alist-get 'priority item) priority)))
                  items)
                 (lambda (a b)
                   (if (not (equal (alist-get 'title a) (alist-get 'title b)))
                       (string< (alist-get 'title a) (alist-get 'title b))
                     (string< (alist-get 'path a) (alist-get 'path b))))))
    (car (todo-late-sort
          (cl-remove-if-not
           (lambda (item)
             (let ((due (todo--due-day (alist-get 'deadline item))))
               (and (member (alist-get 'todo item) todo-doing-states)
                    due
                    (<= due today))))
           items)
          today))))

(defun todo-tasks (file)
  "Every live task heading in FILE; the Archive container is history."
  (with-temp-buffer
    (insert-file-contents file)
    (org-mode)
    (todo--mark-blocks)
    (let (out)
      (org-map-entries
       (lambda ()
         (let ((state (org-get-todo-state)))
           (when (and (member state todo-states)
                      (not (todo--in-block-p))
                      (not (todo--archived-p)))
             (push (list (cons 'file file)
                         (cons 'path file)
                         (cons 'todo state)
                         (cons 'title (org-get-heading t t t t))
                         (cons 'tags (org-get-tags))
                         (cons 'deadline (org-entry-get nil "DEADLINE"))
                         (cons 'priority (todo--priority))
                         (cons 'effort (org-entry-get nil "Effort"))
                         (cons 'note (todo--note)))
                   out)))))
      (nreverse out))))

(defun todo-read (dirs state tag &optional file)
  "Tasks from DIRS, or the configured dirs, plus the cwd board.
With FILE, read exactly that one board and nothing else."
  (let* ((config (todo-config))
         (ignore (alist-get 'ignore config))
         (roots (or dirs (alist-get 'default_dirs config)))
         (items nil))
    (if file
        (setq items (todo-tasks (expand-file-name file)))
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
          (setq items (append items (todo-tasks board))))))
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

(defun todo--heading-in-block (text)
  "First (LINE . BLOCK) where a column-0 heading sits inside a #+BEGIN_* block
in TEXT, or nil. Org counts that line as a real task; this CLI's read skips it,
so the two disagree until the line is indented."
  (let ((depth 0) (line 0) (block nil) found)
    (dolist (l (split-string text "\n"))
      (setq line (1+ line))
      (cond ((string-match "\\`[ \t]*#\\+BEGIN_\\([A-Za-z0-9_]+\\)" l)
             (cl-incf depth)
             (when (= depth 1) (setq block (match-string 1 l))))
            ((string-match "\\`[ \t]*#\\+END_" l)
             (setq depth (max 0 (1- depth))))
            ((and (> depth 0) (not found) (string-match "\\`\\*+ " l))
             (setq found (cons line block)))))
    found))

(defun todo--check-blocks (file text)
  "Fail when TEXT would leave a column-0 heading inside a block in FILE."
  (let ((hit (todo--heading-in-block text)))
    (when hit
      (todo-fail (format (concat "%s:%d: a column-0 * heading sits inside #+%s"
                                 " (org counts it as a real task). Indent it by"
                                 " one space, then retry.")
                         file (car hit) (cdr hit))))))

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
        (todo--check-blocks file text)
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

(defun todo--goto (title &optional container)
  "Move to the task named TITLE. Fail when it is absent or ambiguous.
With CONTAINER, a state-less heading matches too - the only path that promotes a
plain heading, so the Archive container is refused."
  (todo--mark-blocks)
  (let (marker (count 0))
    (org-map-entries
     (lambda ()
       (when (and (or (member (org-get-todo-state) todo-states) container)
                  (not (todo--in-block-p))
                  (not (todo--archived-p))
                  (not (and container
                            (null (org-get-todo-state))
                            (equal (org-get-heading t t t t) "Archive")))
                  (equal (org-get-heading t t t t) title))
         (cl-incf count)
         (unless marker (setq marker (point-marker))))))
    (cond ((null marker) (todo-fail (format "%S is not a %sheading in this file" title
                                            (if container "" "task "))))
          ((> count 1) (todo-fail (format "more than one heading matches %S; refine the ref" title))))
    (goto-char marker)
    (set-marker marker nil)))

(defun todo--goto-heading (title)
  "Move to the heading named TITLE, task or container."
  (todo--mark-blocks)
  (let (marker)
    (org-map-entries
     (lambda ()
       (when (and (not (todo--in-block-p))
                  (equal (org-get-heading t t t t) title))
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

;;; Archiving

;; Archiving is org's own arrangement: a completed task leaves the board for
;; `<board>.org_archive', the default `org-archive-location' is "%s_archive::",
;; with the header org writes and the ARCHIVE_* context properties it records.
;; Two atomic writes, archive first: a failure between them duplicates a task,
;; never loses one, and every append goes through `todo-write' so two archivings
;; at once cannot clobber each other.

(require 'org-archive)

(defun todo--archive-file (board)
  "BOARD's archive file. Org's default location for todo.org is
`todo.org_archive'; a board outside that default is archived next to itself."
  (concat (expand-file-name board) "_archive"))

(defun todo--archive-header (board)
  "The header org puts at the top of a new archive file. The mode line is not
cosmetic: `todo.org_archive' does not match `auto-mode-alist', so without it the
file opens as text."
  (concat "#    -*- mode: org -*-\n"
          (format org-archive-file-header-format (expand-file-name board))))

(defun todo--category (board)
  "The board's category: its `#+CATEGORY:' keyword, else the file name base.
Org's own `org-get-category' is the reference, but it resolves through
org-element's deferred global properties, which is fragile in a buffer that only
had `org-mode' and a scan. Last keyword wins, as it does for org."
  (let ((category (file-name-base (expand-file-name board))))
    (save-excursion
      (goto-char (point-min))
      (while (re-search-forward "^[ \t]*#\\+CATEGORY:[ \t]*\\(.+?\\)[ \t]*$" nil t)
        (setq category (match-string 1))))
    category))

(defun todo--context-info (board)
  "The ARCHIVE_* properties to stamp on the task at point, as (NAME . VALUE).
Which ones is org's `org-archive-save-context-info'; the values come from org's
own accessors, so nothing here decides org semantics."
  (let* ((all (org-get-tags))
         (inherited (cl-remove-if-not (lambda (tag) (get-text-property 0 'inherited tag)) all))
         (local (cl-remove-if (lambda (tag) (get-text-property 0 'inherited tag)) all))
         (values (list (cons 'time (format-time-string (org-time-stamp-format 'with-time 'no-brackets)))
                       (cons 'file (abbreviate-file-name (expand-file-name board)))
                       (cons 'olpath (mapconcat #'identity (org-get-outline-path) "/"))
                       (cons 'category (todo--category board))
                       (cons 'todo (org-entry-get (point) "TODO"))
                       (cons 'itags (mapconcat #'identity inherited " "))
                       (cons 'ltags (mapconcat #'identity local " ")))))
    (cl-loop for item in org-archive-save-context-info
             for value = (cdr (assq item values))
             when (org-string-nw-p value)
             collect (cons (concat "ARCHIVE_" (upcase (symbol-name item))) value))))

(defun todo--archive-capture (board)
  "The task at point as text plus the properties to stamp on it: (TEXT . PROPS).
Point is left alone: the caller archives, then cuts. The properties are read
first, while point is still on the heading - `org-end-of-subtree' below moves
it, and reading them afterwards took the next task's state."
  (let ((props (todo--context-info board)))
    (cons (buffer-substring-no-properties (progn (org-back-to-heading t) (point))
                                          (org-end-of-subtree t t))
          props)))

(defun todo--archive-append (archive header text props)
  "Append TEXT to ARCHIVE, with PROPS as a property drawer, creating ARCHIVE
with HEADER when it does not exist yet."
  (let ((fresh (not (file-exists-p archive))))
    (todo-write archive
                (lambda ()
                  (when fresh (insert header))
                  (goto-char (point-max))
                  (unless (bolp) (insert "\n"))
                  (let ((start (point)))
                    (insert (string-trim-right text) "\n")
                    ;; PROPERTIES arrive only with a task, which starts with its own
                    ;; heading. A container body may be prose or empty, and
                    ;; `org-back-to-heading' there signals before-first-headline.
                    (when props
                      (goto-char start)
                      (org-back-to-heading t)
                      (dolist (pair props)
                        (org-entry-put (point) (car pair) (cdr pair)))))))))

(defun todo-archive-move (board title text props)
  "Move TEXT, the task TITLE, out of BOARD into BOARD's archive file.
Archive first, then cut: a failure between the two leaves the task in both
files, which is recoverable, instead of in neither, which is not."
  (let ((archive (todo--archive-file board)))
    (todo--archive-append archive (todo--archive-header board) text props)
    (todo-write board (lambda () (todo--goto title) (org-cut-subtree)))
    archive))

(defun todo--archive-container ()
  "Marker at the board's inline Archive container, or nil.
A state-less heading titled Archive at any level, which is exactly what
`todo--archived-p' treats as history: reader and migration must agree on what an
Archive is, or one moves what the other still shows."
  (todo--mark-blocks)
  (let (marker)
    (org-map-entries
     (lambda ()
       (when (and (null (org-get-todo-state))
                  (not (todo--in-block-p))
                  (equal (org-get-heading t t t t) "Archive"))
         (unless marker (setq marker (point-marker))))))
    marker))

(defun todo--heading-count (text)
  "Level-1+ headings in TEXT. `count-matches' with explicit bounds: bare
`how-many' returned 0 on the same buffer."
  (with-temp-buffer (insert text) (count-matches "^\\*+ " (point-min) (point-max))))

(defvar todo--moved-note nil
  "The container body just appended, for the cut pass to check itself against.")

(defun todo--archive-container-at-point ()
  "Cut the Archive container at point, refusing when it is not what was moved."
  (let ((m (todo--archive-container)))
    (when m
      (goto-char m)
      ;; What is cut must be what was appended: the container's own heading is
      ;; the only difference.
      (let ((cut (todo--heading-count
                  (buffer-substring-no-properties
                   (point) (save-excursion (org-end-of-subtree t t))))))
        (unless (= (1- cut) (todo--heading-count todo--moved-note))
          (todo-fail "the Archive container changed while archiving; nothing cut")))
      (org-cut-subtree))))

(defun todo-archive-container (board)
  "Move BOARD's first inline Archive container into its archive file.
Nil when the board has none, so a re-run settles. A container whose body is
blank is dropped without touching the archive file."
  (let (text marker)
    (with-temp-buffer
      (insert-file-contents board)
      (org-mode)
      (setq marker (todo--archive-container))
      (when marker
        ;; Both boundaries are read at the container itself. `org-end-of-subtree'
        ;; moves point, and called after `forward-line' it returned the first
        ;; child's end - the cut then took every child and the archive got one.
        (let ((end (save-excursion (goto-char marker) (org-end-of-subtree t t))))
          (save-excursion
            (goto-char marker)
            (org-back-to-heading t)
            (forward-line)
            (setq text (buffer-substring-no-properties (point) end))))))
    (when text
      (let ((archive (todo--archive-file board))
            (todo--moved-note text))
        (unless (string-blank-p text)
          (todo--archive-append archive (todo--archive-header board) text nil))
        (todo-write board (lambda () (todo--archive-container-at-point)))
        archive))))

(defun todo-archive-containers (board)
  "Move every inline Archive container out of BOARD into its archive file.
Returns (COUNT . ARCHIVE-FILE): how many containers went, and the file appended
to, or nil when every container was already empty."
  (let ((count 0) (tries 0))
    (while (and (todo-archive-container board) (< (cl-incf tries) 50))
      (cl-incf count))
    (let ((archive (todo--archive-file board)))
      (cons count (and (> count 0) (file-exists-p archive) archive)))))

;;; Help

;; One table, so the main help and every verb's help cannot disagree: the
;; summary is the verb's line in the main help, and the same entry prints the
;; usage, options, note and example of `todo <verb> --help'.

(defconst todo-help-flags '("-h" "--help")
  "The flags that ask for help: the main help, or a verb's.")

(defconst todo-help
  '(("resolve"
     :summary "board file and dir"
     :usage "todo resolve [--file F] [--dir D]"
     :options (("--file F" "that board, as given")
               ("--dir D" "the dir the board sits in; default the cwd"))
     :example "todo resolve --dir ~/repos/agent1")
    ("doing"
     :summary "the one task to do now: one record, or none"
     :usage "todo doing [-p A|B|C|D] [--file F] [--dir D]"
     :options (("-p, --priority A|B|C|D" "any open task at that priority, due or not")
               ("--file F" "that board, and nothing else")
               ("--dir D" "scan D's *.org files instead of the configured dirs"))
     :note "The default pick is the head of the same urgency order `read --due' prints: most days late, then A before D, then title, then path."
     :example "todo doing -p A")
    ("read"
     :summary "list tasks: STATE  Title  (path)"
     :usage "todo read [--state S] [--tag T] [-d|--due] [--recurring] [--records] [-p A|B|C|D] [-n N] [--file F] [--dir D]"
     :options (("--state S" "only that state")
               ("--tag T" "only that tag")
               ("-d, --due" "today or earlier in IST, most urgent first, open work only")
               ("--overdue" "the long name of the same window and order as --due")
               ("--recurring" "routines: a deadline carrying a repeater")
               ("-p, --priority A|B|C|D" "only tasks at that priority")
               ("-n, --number N" "the first N: urgency order with --due, else board order")
               ("--records" "one plain record per task, instead of a line")
               ("--file F" "that board, and nothing else")
               ("--dir D" "scan D's *.org files instead of the configured dirs"))
     :note "--due and --overdue keep open work, TODO and IN_PROGRESS, unless --state names another one - which wins on its own. The list is one urgency order: most days late first, then A before D, then title, then path."
     :example "todo read --due -p A -n 1")
    ("create"
     :summary "add a task"
     :usage "todo create <title> [options]"
     :options (("--state S" "TODO (default), IN_PROGRESS, OPTIONAL, LATER")
               ("--tag T" "repeatable; :finance:home:")
               ("-p, --priority A|B|C|D" "ask Raveen first; a repeater forces B")
               ("--deadline D" "2026-11-05 | 2026-11-05 20:30 | <2026-11-05 Thu 20:30 +1w>")
               ("--effort H:MM" "org's :Effort: property")
               ("--note TEXT" "body under the heading")
               ("--container NAME" "nest under an existing heading")
               ("--file F" "the board; default todo.org in the cwd"))
     :example "todo create \"Pay rent\" --deadline 2026-11-05 --tag finance --priority A")
    ("rename"
     :summary "change a task's title"
     :usage "todo rename <ref> <title> [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :example "todo rename \"Pay rent\" \"Pay the rent\"")
    ("delete"
     :summary "remove the subtree, body and all"
     :usage "todo delete <ref> [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :note "Git keeps history; outside git this is unrecoverable. `obsolete' keeps the record."
     :example "todo delete \"Pay rent\"")
    ("set-state"
     :summary "move a task to a state; promotes a plain heading"
     :usage "todo set-state <ref> STATE [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :note "STATE is one of TODO, IN_PROGRESS, OPTIONAL, LATER, DONE, OBSOLETE."
     :example "todo set-state \"Pay rent\" IN_PROGRESS")
    ("set-deadline"
     :summary "set DEADLINE, with a time or a repeater"
     :usage "todo set-deadline <ref> D [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :note "D is 2026-11-05, 2026-11-05 20:30 or <2026-11-05 Thu 20:30 +1w>. A repeater forces priority B."
     :example "todo set-deadline \"Pay rent\" 2026-12-01")
    ("set-priority"
     :summary "set A, B, C or D"
     :usage "todo set-priority <ref> A|B|C|D [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :note "Ask Raveen first. D is the lowest level, and a recurring task is always priority B."
     :example "todo set-priority \"Pay rent\" B")
    ("set-effort"
     :summary "set :Effort: H:MM"
     :usage "todo set-effort <ref> H:MM [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :example "todo set-effort \"Pay rent\" 0:30")
    ("add-tag"
     :summary "add one tag"
     :usage "todo add-tag <ref> TAG [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :note "Tags are lowercase and colon-delimited, charset [[:alnum:]_@#%]: a hyphen is not a tag character."
     :example "todo add-tag \"Pay rent\" home")
    ("remove-tag"
     :summary "remove one tag"
     :usage "todo remove-tag <ref> TAG [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :example "todo remove-tag \"Pay rent\" home")
    ("append"
     :summary "add text to the note"
     :usage "todo append <ref> TEXT [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :note "Indent TEXT that starts with `*': a star at column 0 is a heading."
     :example "todo append \"Pay rent\" \"receipt in mail\"")
    ("obsolete"
     :summary "OBSOLETE, keeping the record"
     :usage "todo obsolete <ref> [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :example "todo obsolete \"Pay rent\"")
    ("complete"
     :summary "DONE + CLOSED, then archive; a routine stays"
     :usage "todo complete <ref> [--evidence TEXT] [--file F]"
     :options (("--evidence TEXT" "appended to the note before the state changes")
               ("--file F" "the board; default todo.org in the cwd"))
     :note "A task whose deadline carries a repeater stays on the board; everything else moves to <board>.org_archive."
     :example "todo complete \"Pay rent\" --evidence \"paid from the joint account\"")
    ("archive"
     :summary "inline `* Archive' containers to <board>.org_archive"
     :usage "todo archive [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :example "todo archive --file ~/repos/agent1/todo.org")
    ("capture"
     :summary "append a plain heading, no state"
     :usage "todo capture <text> [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :example "todo capture \"Look into OpenRouter routing\"")
    ("status"
     :summary "board path, existence, task count"
     :usage "todo status [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :example "todo status")
    ("edit"
     :summary "open vim at the heading line"
     :usage "todo edit <ref> [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :note "With no terminal this opens as `mvim -f'."
     :example "todo edit \"Pay rent\" --file ~/repos/agent1/todo.org")
    ("edit-vim"
     :summary "same as edit: vim at the heading line"
     :usage "todo edit-vim <ref> [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :example "todo edit-vim \"Pay rent\" --file ~/repos/agent1/todo.org")
    ("edit-emacs"
     :summary "open Emacs at the heading line"
     :usage "todo edit-emacs <ref> [--file F]"
     :options (("--file F" "the board; default todo.org in the cwd"))
     :example "todo edit-emacs \"Pay rent\" --file ~/repos/agent1/todo.org")
    ("config"
     :summary "default_dirs and ignore"
     :usage "todo config"
     :note "The file is ~/dot_local/config/todo_skill.toml; TODO_SKILL_CONFIG overrides it."
     :example "todo config"))
  "Per-verb help: :summary, :usage, :options, :note and :example.")

(defun todo--help-main ()
  "Print the main help: usage, every verb and its summary, then the flags."
  (princ "todo - the board CLI: Emacs org-mode, the only writer of a board\n\n")
  (princ "usage: todo <verb> [args] [--file F] [--dir D]\n")
  (princ "       todo --warm <verb> [args]\n")
  (princ "       todo <verb> --help\n\nverbs:\n")
  (dolist (spec todo-help)
    (princ (format "  %-13s %s\n" (car spec) (plist-get (cdr spec) :summary))))
  (princ "\noptions:\n")
  (princ "  -h, --help      this help; after a verb, that verb's help\n")
  (princ "  -p, --priority  A, B, C or D, where the verb takes a priority\n")
  (princ "  -n, --number N  read: the first N of that list, urgency order with --due\n")
  (princ "  -d, --due       read: the same window as --overdue\n")
  (princ "  --warm          one background Emacs (socket todo-skill) serves the call\n")
  (princ "  --file F        the board for this call; wins over --dir\n")
  (princ "  --dir D         a read scans D's *.org files instead of the configured dirs\n")
  (princ "\nconfig: ~/dot_local/config/todo_skill.toml (TODO_SKILL_CONFIG overrides it)\n")
  (princ "see also: SKILL.md, next to scripts/\n"))

(defun todo--help-verb (spec)
  "Print SPEC as one verb's help: usage, summary, options, note, example."
  (let* ((options (plist-get (cdr spec) :options))
         (note (plist-get (cdr spec) :note))
         (example (plist-get (cdr spec) :example))
         ;; Wide enough for this verb's longest flag; never narrower than the
         ;; common column, so short verbs do not breathe in.
         (width (if options
                    (apply #'max 17 (mapcar (lambda (option) (length (car option))) options))
                  17)))
    (princ (format "usage: %s\n\n  %s\n"
                   (plist-get (cdr spec) :usage) (plist-get (cdr spec) :summary)))
    (when options
      (princ "\noptions:\n")
      (dolist (option options)
        (princ (format (format "  %%-%ds %%s\n" width) (car option) (cadr option)))))
    (when note
      ;; Filled at 78 columns, so a long note does not run off the screen.
      ;; adaptive-fill off: it reads a note starting with `--' as a fill
      ;; prefix and indents every line after the first.
      (princ (format "\n%s\n"
                     (with-temp-buffer
                       (let ((fill-column 78)
                             (adaptive-fill-mode nil))
                         (insert note)
                         (fill-region (point-min) (point-max)))
                       (buffer-string)))))
    (when example (princ (format "\nexample:\n  %s\n" example)))))

(defun todo--help (verb)
  "Print help for VERB, or the main help when VERB is nil or unknown."
  (let ((spec (and verb (assoc verb todo-help))))
    (if spec (todo--help-verb spec) (todo--help-main))))

(defun todo--help-reply (pos)
  "Print the help POS asks for, and return t. Nil when POS asks for none.
A bare call is a help request too, so `todo' on its own prints the main help,
and `todo --help read' is the same as `todo read --help'."
  (when (or (null pos)
            (cl-some (lambda (arg) (member arg todo-help-flags)) pos))
    (todo--help (cl-find-if (lambda (arg) (assoc arg todo-help)) pos))
    t))

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
         (effort (todo--flag flags "--effort"))
         (note (todo--flag flags "--note"))
         (tags (todo--flags flags "--tag")))
    (unless title (todo-fail "create needs a title"))
    (when (string-prefix-p "-" title)
      (todo-fail "create title must not be a flag"))
    (unless (member state todo-states) (todo-fail (format "unknown state %s" state)))
    (when effort (todo--checked-effort effort))
    (when priority (todo--checked-priority priority))
    (when deadline (todo--checked-deadline deadline))
    (when (todo--recurring deadline)
      (when (and priority (not (equal priority "B")))
        (todo-fail (format "a recurring task is always priority B, not %s" priority)))
      (setq priority "B"))
    (todo-write
     board
     (lambda ()
       (if container
           (progn
             (todo--goto-heading container)
             (let ((level (org-current-level)))
               (org-end-of-subtree t)
               (insert "\n" (make-string (1+ level) ?*) " " title)))
         (todo--append-root title))
       (org-todo state)
       (when priority (org-priority (string-to-char priority)))
       (when tags (org-set-tags tags))
       (when deadline (org-deadline nil deadline))
       (when effort (org-set-property "Effort" effort))
       (when note (todo--append-body note))))
    (todo-out (append (list (cons 'title title) (cons 'file board) (cons 'state state))
                      ;; The window updates its card from these pairs; a
                      ;; recurring create must show the B the CLI just applied.
                      (when priority (list (cons 'priority priority)))))))

(defun todo-run (pos flags)
  "Dispatch one CLI call: POS are the positionals, FLAGS the parsed options.
A help request is answered here, before any verb runs."
  (unless (todo--help-reply pos)
    (todo-run-verb pos flags)))

(defun todo-run-verb (pos flags)
  "The verbs, without the help gate."
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

      ("doing"
       (let ((priority (todo--checked-priority (todo--flag flags "--priority"))))
         (let ((pick (todo-doing-pick (todo-read dirs nil nil file) (todo-ist-day) priority)))
           (if pick
               (todo-print-records (list pick))
             (princ "none\n")))))

      ("read"
       (let* ((state (todo--flag flags "--state"))
              (items (todo-read dirs state (car (todo--flags flags "--tag")) file))
              (priority (todo--checked-priority (todo--flag flags "--priority")))
              (number (todo--checked-number (todo--flag flags "--number"))))
         (when priority
           (setq items (cl-remove-if-not
                        (lambda (i) (equal (alist-get 'priority i) priority)) items)))
         (when (member "--recurring" rest)
           (setq items (cl-remove-if-not
                        (lambda (i) (todo--recurring (alist-get 'deadline i))) items)))
         (when (cl-some (lambda (flag) (member flag rest)) todo-due-flags)
           (let ((today (todo-ist-day)))
             ;; The window's own default: open work only, unless --state named a
             ;; state, which wins outright. The order is the flag's default too:
             ;; most urgent first, the same comparator `doing' picks with.
             (setq items (todo-late-sort
                          (cl-remove-if-not
                           (lambda (i)
                             (let ((due (todo--due-day (alist-get 'deadline i))))
                               (and due (<= due today)
                                    (or state
                                        (member (alist-get 'todo i) todo-doing-states)))))
                           items)
                          today))))
         ;; Filter first, then cut the list to the first N: with --due those
         ;; are the N most urgent, without it board order.
         (when number
           (setq items (cl-subseq items 0 (min number (length items)))))
         (if (member "--records" rest)
             (todo-print-records items)
           (dolist (item items)
             (princ (format "%-12s %s  (%s)\n"
                            (alist-get 'todo item) (alist-get 'title item) (alist-get 'path item)))))))

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
           (todo-write board (lambda () (todo--goto (car rest) t) (org-todo state)))
           (todo-out (list (cons 'title (car rest)) (cons 'file board) (cons 'state state))))))

      ("set-deadline"
       (let* ((board (todo--existing file))
              (deadline (todo--checked-deadline (cadr rest)))
              (routine (todo--recurring deadline)))
         (todo-write board (lambda () (todo--goto (car rest))
                               (org-deadline nil deadline)
                               (when routine (org-priority ?B))))
         (todo-out (append (list (cons 'title (car rest)) (cons 'file board)
                                 (cons 'deadline deadline))
                           (when routine (list (cons 'priority "B")))))))

      ("set-priority"
       (let ((priority (cadr rest)))
         (unless (and (car rest) priority) (todo-fail "set-priority needs a ref and A, B, C or D"))
         (todo--checked-priority priority)
         (let ((board (todo--existing file)))
           (todo-write board (lambda () (todo--goto (car rest))
                                 (org-priority (string-to-char priority))))
           (todo-out (list (cons 'title (car rest)) (cons 'file board)
                           (cons 'priority priority))))))

      ("set-effort"
       (let ((effort (cadr rest)))
         (unless (and (car rest) effort) (todo-fail "set-effort needs a ref and an H:MM value"))
         (todo--checked-effort effort)
         (let ((board (todo--existing file)))
           (todo-write board (lambda () (todo--goto (car rest)) (org-set-property "Effort" effort)))
           (todo-out (list (cons 'title (car rest)) (cons 'file board) (cons 'effort effort))))))

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
       (let* ((board (todo--existing file))
              (title (car rest))
              (evidence (todo--flag flags "--evidence"))
              routine captured)
         (todo-write board
                     (lambda ()
                       (todo--goto title)
                       (when evidence (todo--append-body evidence))
                       (org-todo "DONE")
                       ;; A routine repeats: completing it must not take it off
                       ;; the board, or the next occurrence never shows up.
                       (setq routine (todo--recurring (org-entry-get nil "DEADLINE")))
                       (unless routine (setq captured (todo--archive-capture board)))))
         (if captured
             (todo-out (list (cons 'title title)
                             (cons 'state "DONE")
                             (cons 'file board)
                             (cons 'archived (todo-archive-move board title (car captured) (cdr captured)))))
           (todo-out (list (cons 'title title)
                           (cons 'state "DONE")
                           (cons 'file board)
                           (cons 'routine (and routine t)))))))

      ("archive"
       (let* ((board (todo--existing file))
              (result (todo-archive-containers board)))
         (todo-out (list (cons 'file board)
                         (cons 'containers (car result))
                         (cons 'archive (cdr result))))))

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

      ((or "edit" "edit-vim")
       (todo-edit (car rest) file "vim"))

      ("edit-emacs"
       (todo-edit (car rest) file "emacs"))

      ("config"
       (let ((config (todo-config)))
         (todo-out (list (cons 'default_dirs
                               (mapconcat #'identity (alist-get 'default_dirs config) ", "))
                         (cons 'ignore
                               (mapconcat #'identity (alist-get 'ignore config) ", "))))))

      (_ (todo-fail (format "unknown command %s - for the verbs and their flags: todo --help"
                            (or verb "(none)")))))))

;;; CLI

(defun todo--parse (args)
  "Split ARGS into (POSITIONALS FLAGS). A leading -- is dropped, and a short
flag is rewritten to its long name, so one spelling reaches the verbs."
  (when (equal (car args) "--") (setq args (cdr args)))
  (let ((flags nil)
        (pos nil))
    (while args
      (let ((arg (or (cdr (assoc (car args) todo-flag-aliases)) (car args))))
        (if (member arg todo-value-flags)
            (progn
              (unless (cadr args) (todo-fail (format "%s needs a value" arg)))
              (push (cons arg (cadr args)) flags)
              (setq args (cddr args)))
          (push arg pos)
          (setq args (cdr args)))))
    (list (nreverse pos) (nreverse flags))))

(defun todo-main ()
  "Parse the command line and run one verb."
  (let* ((parsed (todo--parse command-line-args-left))
         (pos (car parsed))
         (flags (cadr parsed)))
    ;; Emacs batch mode visits whatever is left in `command-line-args-left'
    ;; as files once this returns.  Clear it, or a long append or evidence
    ;; string becomes a filename and the call exits 255 after writing.
    (setq command-line-args-left nil)
    (condition-case err
        (let ((inhibit-message t))     ; org's progress notes stay out of stderr
          (todo-run pos flags))
      (error (todo-fail (error-message-string err))))))

(defun todo-warm-write (argsfile outfile errfile dir)
  "Run the null-delimited args in ARGSFILE as one CLI call.
Write stdout to OUTFILE and stderr to ERRFILE. Return the exit code.
DIR is the caller's cwd. Do not kill Emacs: the warm process stays up.
ponytail: one Emacs serves every warm call. `edit` blocks the others
until the editor exits. A second socket if that wait matters."
  (let ((args (split-string
               (with-temp-buffer
                 (insert-file-contents-literally argsfile)
                 (buffer-string))
               "\0" t))
        (default-directory (file-name-as-directory dir))
        (out (generate-new-buffer " *todo-warm-out*"))
        (code 0)
        (stderr ""))
    (unwind-protect
        (condition-case err
            (let ((standard-output out)
                  (inhibit-message t))
              (cl-letf (((symbol-function 'todo-fail)
                         (lambda (msg) (signal 'todo-warm-fail (list msg)))))
                (let ((parsed (todo--parse args)))
                  (todo-run (car parsed) (cadr parsed)))))
          (todo-warm-fail (setq code 1 stderr (concat (car (cdr err)) "\n")))
          (error (setq code 1 stderr (concat (error-message-string err) "\n"))))
      (let ((coding-system-for-write 'utf-8-unix))
        (write-region (with-current-buffer out (buffer-string)) nil outfile nil 'silent)
        (write-region stderr nil errfile nil 'silent))
      (kill-buffer out))
    code))

(provide 'todo)

;; Run only when invoked as a script (the wrapper passes --), not when the
;; test suite loads this file.
(when (equal (car command-line-args-left) "--")
  (todo-main))
