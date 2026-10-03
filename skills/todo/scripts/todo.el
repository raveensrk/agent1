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
(require 'json)

;;; Setup

(defconst todo-states '("TODO" "IN_PROGRESS" "OPTIONAL" "LATER" "DONE" "OBSOLETE")
  "The state words the skill knows.")

(defconst todo-deadline-forms
  "2026-11-05, 2026-11-05 20:30 or <2026-11-05 Thu 20:30 +1w>"
  "The deadline forms the CLI accepts, as refusals and SKILL.md print them.")

(defconst todo-value-flags '("--file" "--state" "--tag" "--container" "--deadline"
                             "--priority" "--note" "--dir" "--editor" "--evidence"
                             "--effort")
  "Flags that take a value.")

(setq org-todo-keywords '((sequence "TODO" "IN_PROGRESS" "OPTIONAL" "LATER"
                                    "|" "DONE" "OBSOLETE"))
      org-log-done 'time                ; DONE writes CLOSED:
      org-tags-column 0                 ; tags right after the title
      org-adapt-indentation nil
      create-lockfiles nil
      make-backup-files nil
      auto-save-default nil
      org-element-use-cache nil
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

(defun todo--checked-effort (value)
  "VALUE as H:MM, or fail. Org's own Effort format."
  (unless (string-match-p "\\`[0-9]+:[0-5][0-9]\\'" value)
    (todo-fail (format "effort takes H:MM, got %s" value)))
  value)

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

(defun todo-print-json (items)
  "Print ITEMS as one JSON array and a newline.
json-serialize returns raw UTF-8 bytes. princ of those bytes into the
warm process's multibyte buffer writes illegal \\342 escapes."
  (todo--print-json (vconcat (mapcar #'todo--json-task items))))

(defun todo-print-json-object (item)
  "Print ITEM as one JSON object, or null."
  (todo--print-json (if item (todo--json-task item) :null)))

(defun todo--print-json (value)
  (princ (decode-coding-string
          (json-serialize value :null-object :null)
          'utf-8))
  (princ "\n"))

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
  "A is 0. A missing priority sorts after C."
  (if (and priority (string-match "\\`[ABC]\\'" priority))
      (- (aref priority 0) ?A)
    3))

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
    (car (sort (cl-remove-if-not
                (lambda (item)
                  (let ((due (todo--due-day (alist-get 'deadline item))))
                    (and (member (alist-get 'todo item) todo-doing-states)
                         due
                         (<= due today))))
                items)
               (lambda (a b)
                 (let ((late-a (- today (todo--due-day (alist-get 'deadline a))))
                       (late-b (- today (todo--due-day (alist-get 'deadline b))))
                       (rank-a (todo--priority-rank (alist-get 'priority a)))
                       (rank-b (todo--priority-rank (alist-get 'priority b))))
                   (cond ((/= late-a late-b) (> late-a late-b))
                         ((/= rank-a rank-b) (< rank-a rank-b))
                         ((not (equal (alist-get 'title a) (alist-get 'title b)))
                          (string< (alist-get 'title a) (alist-get 'title b)))
                         (t (string< (alist-get 'path a) (alist-get 'path b))))))))))

(defun todo--json-task (item)
  "ITEM as the read --json object. Missing deadline and priority are null."
  `((title . ,(alist-get 'title item))
    (state . ,(alist-get 'todo item))
    (deadline . ,(or (alist-get 'deadline item) :null))
    (priority . ,(or (alist-get 'priority item) :null))
    (effort . ,(or (alist-get 'effort item) :null))
    (tags . ,(vconcat (alist-get 'tags item)))
    (note . ,(or (alist-get 'note item) ""))
    (path . ,(alist-get 'path item))))

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
    (when deadline (todo--checked-deadline deadline))
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

      ("doing"
       (let ((priority (todo--flag flags "--priority")))
         (when (and priority (not (member priority '("A" "B" "C"))))
           (todo-fail (format "priority takes A, B or C, got %s" priority)))
         (let ((pick (todo-doing-pick (todo-read dirs nil nil file) (todo-ist-day) priority)))
           (if (member "--json" rest)
               (todo-print-json-object pick)
             (if pick
                 (princ (format "%-12s %s  (%s)\n"
                                (alist-get 'todo pick) (alist-get 'title pick) (alist-get 'path pick)))
               (princ "none\n"))))))

      ("read"
       (let ((items (todo-read dirs (todo--flag flags "--state") (car (todo--flags flags "--tag")) file)))
         (if (member "--json" rest)
             (todo-print-json items)
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
       (let ((board (todo--existing file))
             (deadline (todo--checked-deadline (cadr rest))))
         (todo-write board (lambda () (todo--goto (car rest)) (org-deadline nil deadline)))
         (todo-out (list (cons 'title (car rest)) (cons 'file board) (cons 'deadline deadline)))))

      ("set-priority"
       (let ((priority (cadr rest)))
         (unless (and (car rest) priority) (todo-fail "set-priority needs a ref and A, B or C"))
         (unless (member priority '("A" "B" "C"))
           (todo-fail (format "priority takes A, B or C, got %s" priority)))
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

      (_ (todo-fail (format "unknown command %s" (or verb "(none)")))))))

;;; CLI

(defun todo--parse (args)
  "Split ARGS into (POSITIONALS FLAGS). A leading -- is dropped."
  (when (equal (car args) "--") (setq args (cdr args)))
  (let ((flags nil)
        (pos nil))
    (while args
      (let ((arg (car args)))
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
