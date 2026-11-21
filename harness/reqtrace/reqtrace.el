;;; reqtrace.el --- lint, trace and list org requirements  -*- lexical-binding: t; -*-

;; Run through the launcher: harness/reqtrace/reqtrace COMMAND ...
;; Requirements: harness/reqtrace/requirements.org (RT-1 to RT-15).
;; It reads files and git, and never writes a file.

(require 'org)
(require 'org-element)
(require 'subr-x)
(require 'cl-lib)
(require 'json)
(require 'time-date)

(defconst reqtrace-states '("OPEN" "DONE" "DROPPED"))
(defconst reqtrace-dates '("CREATED" "LAST_EDITED" "APPROVED" "IMPLEMENTED" "REVIEWED"))
(defvar reqtrace--findings 0)
(defvar reqtrace--tests-cache (make-hash-table :test #'equal))

;;;; Output

(defun reqtrace--out (fmt &rest args)
  (princ (apply #'format fmt args))
  (princ "\n"))

(defun reqtrace--err (fmt &rest args)
  (message "%s" (apply #'format fmt args)))

(defun reqtrace--finding (file line id why fix)
  "One finding line on stderr (RT-2)."
  (setq reqtrace--findings (1+ reqtrace--findings))
  (reqtrace--err "reqtrace: %s:%s: %s: %s; %s" file line (or id "-") why fix))

;;;; Git

(defun reqtrace--git (&rest args)
  "Run git with ARGS in `default-directory'; (EXIT . OUTPUT)."
  (with-temp-buffer
    (let ((code (apply #'call-process "git" nil (list t nil) nil args)))
      (cons code (buffer-string)))))

(defun reqtrace--git-out (&rest args)
  (let ((r (apply #'reqtrace--git args)))
    (and (zerop (car r)) (cdr r))))

(defun reqtrace--lines (s)
  (split-string (or s "") "\n" t))

(defun reqtrace--root ()
  (let ((top (reqtrace--git-out "rev-parse" "--show-toplevel")))
    (and top (file-name-as-directory (string-trim top)))))

;;;; Parsing

(defun reqtrace--entry-text (raw)
  "The text of an entry from RAW, its heading line to the next heading:
heading, body and properties, without its state and the 5 dates."
  (let* ((lines (split-string raw "\n"))
         (head (replace-regexp-in-string
                (concat "\\`\\(\\*+\\) +" (regexp-opt reqtrace-states) "\\_>")
                "\\1" (car lines)))
         (date-re (concat "\\`[ \t]*:" (regexp-opt reqtrace-dates) ":")))
    (string-trim-right
     (string-join (cons (string-trim-right head)
                        (cl-remove-if (lambda (l) (string-match-p date-re l)) (cdr lines)))
                  "\n"))))

(defun reqtrace--split-headings (content)
  "Each heading of CONTENT with its body, up to the next heading."
  (let ((pos 0) starts)
    (while (string-match "^\\*+ " content pos)
      (push (match-beginning 0) starts)
      (setq pos (match-end 0)))
    (setq starts (nreverse starts))
    (cl-loop for (a b) on starts
             collect (substring content a (or b (length content))))))

(defun reqtrace--quick-ids (content)
  "Alist (ID . TEXT) for each heading of CONTENT with an :ID:; headlines only (RT-9)."
  (let (out)
    (dolist (c (reqtrace--split-headings content))
      (when (string-match "^[ \t]*:ID:[ \t]+\\(\\S-+\\)" c)
        (push (cons (match-string 1 c) (reqtrace--entry-text c)) out)))
    (nreverse out)))

(defun reqtrace--parse (content file)
  "Parse org CONTENT named FILE: plist (:file :keywords :opted :listed :reqs)."
  (with-temp-buffer
    (insert content)
    (let ((org-todo-keywords '((sequence "OPEN" "|" "DONE" "DROPPED")))
          (org-element-use-cache nil)
          (org-inhibit-startup t))
      (delay-mode-hooks (org-mode))
      (let* ((kw (org-collect-keywords '("REQTRACE_TESTS" "REQTRACE_CODE" "TODO")))
             (todo (cadr (assoc "TODO" kw)))
             reqs)
        (org-map-entries
         (lambda ()
           (let ((state (org-get-todo-state))
                 (id (org-entry-get nil "ID")))
             (when (or (member state reqtrace-states) id)
               (let* ((beg (point))
                      (end (save-excursion (outline-next-heading) (point)))
                      (get (lambda (p) (let ((v (org-entry-get nil p)))
                                         (and v (not (string-empty-p (string-trim v)))
                                              (string-trim v))))))
                 (push (list :id (and id (string-trim id))
                             :state (and (member state reqtrace-states) state)
                             :title (org-get-heading t t t t)
                             :file file
                             :line (line-number-at-pos beg)
                             :created (funcall get "CREATED")
                             :last-edited (funcall get "LAST_EDITED")
                             :approved (funcall get "APPROVED")
                             :implemented (funcall get "IMPLEMENTED")
                             :reviewed (funcall get "REVIEWED")
                             :needs (let ((v (funcall get "NEEDS"))) (and v (split-string v)))
                             :verify (let ((v (funcall get "VERIFY")))
                                       (and v (split-string-and-unquote v)))
                             :text (reqtrace--entry-text
                                    (buffer-substring-no-properties beg end)))
                       reqs))))))
        (let ((opted (and (assoc "REQTRACE_TESTS" kw) t)))
          (list :file file
                :keywords kw
                :opted opted
                :tests (cadr (assoc "REQTRACE_TESTS" kw))
                :code (let ((c (cadr (assoc "REQTRACE_CODE" kw)))) (and c (split-string c)))
                :listed (or opted
                            (equal (file-name-nondirectory file) "requirements.org")
                            (member "requirements" (split-string (or (file-name-directory file) "") "/" t))
                            (and todo (string-match-p "\\_<OPEN\\_>" todo) t))
                :reqs (nreverse reqs)))))))

(defun reqtrace--worktree-files ()
  "Parsed infos of the repo's git-tracked .org files, from the work tree."
  (cl-loop for f in (reqtrace--lines (reqtrace--git-out "ls-files" "*.org"))
           when (file-readable-p f)
           collect (reqtrace--parse (with-temp-buffer (insert-file-contents f) (buffer-string)) f)))

(defun reqtrace--rev-files (rev)
  "Parsed infos of the .org files at REV: \"\" for the index, \"HEAD\" for HEAD."
  (let ((names (if (string-empty-p rev)
                   (reqtrace--lines (reqtrace--git-out "ls-files" "*.org"))
                 (cl-remove-if-not (lambda (f) (string-suffix-p ".org" f))
                                   (reqtrace--lines (reqtrace--git-out "ls-tree" "-r" "--name-only" rev))))))
    (cl-loop for f in names
             for c = (reqtrace--git-out "show" (concat rev ":" f))
             when c collect (reqtrace--parse c f))))

(defun reqtrace--opted (infos) (cl-remove-if-not (lambda (i) (plist-get i :opted)) infos))
(defun reqtrace--listed (infos) (cl-remove-if-not (lambda (i) (plist-get i :listed)) infos))
(defun reqtrace--all-reqs (infos) (cl-mapcan (lambda (i) (copy-sequence (plist-get i :reqs))) infos))

;;;; The test command (RT-5)

(defun reqtrace--test-addresses (cmd)
  "Run CMD from the repo root: (t . ADDRESSES) or (nil . WHY)."
  (or (gethash cmd reqtrace--tests-cache)
      (puthash
       cmd
       (let* ((limit (string-to-number (or (getenv "REQTRACE_TEST_SECONDS") "60")))
              (buf (generate-new-buffer " *reqtrace-tests*"))
              (errbuf (generate-new-buffer " *reqtrace-tests-err*"))
              (proc (make-process :name "reqtrace-tests" :buffer buf :stderr errbuf
                                  :command (list "sh" "-c" cmd)
                                  :connection-type 'pipe :noquery t))
              (start (float-time)))
         (while (and (process-live-p proc) (< (- (float-time) start) limit))
           (accept-process-output proc 0.05))
         (cond
          ((process-live-p proc)
           (delete-process proc)
           (cons nil (format "test command ran over %s s: %s" limit cmd)))
          (t
           (while (accept-process-output proc 0.02))
           (if (/= 0 (process-exit-status proc))
               (cons nil (format "test command failed with exit %d: %s"
                                 (process-exit-status proc) cmd))
             (cons t (split-string (with-current-buffer buf (buffer-string)) "\n" t "[ \t\r]+"))))))
       reqtrace--tests-cache)))

;;;; Dates

(defun reqtrace--day-p (s)
  (and s (string-match "\\`\\([0-9]\\{4\\}\\)-\\([0-9]\\{2\\}\\)-\\([0-9]\\{2\\}\\)\\'" s)
       (let ((y (string-to-number (match-string 1 s)))
             (m (string-to-number (match-string 2 s)))
             (d (string-to-number (match-string 3 s))))
         (and (<= 1 m 12) (<= 1 d (date-days-in-month y m))))))

(defun reqtrace--today ()
  (or (getenv "REQTRACE_TODAY") (format-time-string "%F")))

;;;; lint (RT-4, RT-5, RT-6)

(defun reqtrace--lint-file-rules (infos only)
  "RT-4 over the opted-in INFOS; findings only for files in ONLY, when given."
  (let ((seen (make-hash-table :test #'equal))
        (all (reqtrace--all-reqs infos))
        (show (lambda (r) (or (null only) (member (plist-get r :file) only)))))
    (dolist (r all)
      (let ((id (plist-get r :id)) (state (plist-get r :state))
            (f (plist-get r :file)) (l (plist-get r :line)))
        (when (funcall show r)
          (when (string-match-p "\\`[A-Z]+-[0-9]+\\_>" (plist-get r :title))
            (reqtrace--finding f l id "the heading text starts with an id"
                               "keep the id in :ID: only"))
          (cond ((null id) (reqtrace--finding f l nil "no :ID:" "add :ID: as RF-3"))
                ((not (string-match-p "\\`[A-Z]+-[0-9]+\\'" id))
                 (reqtrace--finding f l id "the id is not shaped [A-Z]+-[0-9]+" "rename it, as RF-3")))
          (when (and (member state '("OPEN" "DONE")) (null (plist-get r :approved)))
            (reqtrace--finding f l id (format "%s with no :APPROVED:" state)
                               "get the owner's approval, then add :APPROVED: with its day"))
          (unless (plist-get r :created) (reqtrace--finding f l id "no :CREATED:" "add :CREATED: YYYY-MM-DD"))
          (unless (plist-get r :last-edited)
            (reqtrace--finding f l id "no :LAST_EDITED:" "add :LAST_EDITED: YYYY-MM-DD"))
          (when (and (equal state "DONE") (null (plist-get r :implemented)))
            (reqtrace--finding f l id "DONE with no :IMPLEMENTED:" "add :IMPLEMENTED: with the day it was built"))
          (when (and (member state '("OPEN" "DROPPED")) (plist-get r :implemented))
            (reqtrace--finding f l id (format "%s with :IMPLEMENTED:" state)
                               "remove :IMPLEMENTED:, or make it DONE"))
          (dolist (p '(:created :last-edited :approved :implemented :reviewed))
            (let ((v (plist-get r p)))
              (when (and v (not (reqtrace--day-p v)))
                (reqtrace--finding f l id (format "%s is not a real day: %s" (substring (symbol-name p) 1) v)
                                   "write it as YYYY-MM-DD"))))
          (when (and (equal state "DONE") (null (plist-get r :verify)))
            (reqtrace--finding f l id "DONE with no :VERIFY:" "name the checks that verify it")))
        (when id
          (if (gethash id seen)
              (when (funcall show r)
                (reqtrace--finding f l id (format "the id is used twice, first at %s" (gethash id seen))
                                   "give this one a new id"))
            (puthash id (format "%s:%s" f l) seen)))))
    ;; NEEDS: unknown ids and cycles.
    (dolist (r all)
      (when (funcall show r)
        (dolist (n (plist-get r :needs))
          (unless (gethash n seen)
            (reqtrace--finding (plist-get r :file) (plist-get r :line) (plist-get r :id)
                               (format ":NEEDS: names %s, which no requirement has" n)
                               "fix the id, or remove it")))))
    (let ((graph (make-hash-table :test #'equal)) (reported (make-hash-table :test #'equal)))
      (dolist (r all) (when (plist-get r :id) (puthash (plist-get r :id) r graph)))
      (dolist (r all)
        (let ((id (plist-get r :id)))
          (when (and id (funcall show r) (not (gethash id reported)))
            (let ((stack (list id)) (visited (make-hash-table :test #'equal)) found)
              (while (and stack (not found))
                (let ((cur (pop stack)))
                  (unless (gethash cur visited)
                    (puthash cur t visited)
                    (dolist (n (plist-get (gethash cur graph) :needs))
                      (if (equal n id) (setq found t) (push n stack))))))
              (when found
                (puthash id t reported)
                (reqtrace--finding (plist-get r :file) (plist-get r :line) id
                                   ":NEEDS: makes a cycle back to this id"
                                   "remove one :NEEDS: link of the cycle")))))))))

(defun reqtrace--lint-verify (infos only)
  "RT-5: a DONE requirement's :VERIFY: names tests the command prints."
  (dolist (info infos)
    (when (or (null only) (member (plist-get info :file) only))
      (let ((res (reqtrace--test-addresses (plist-get info :tests))))
        (if (not (car res))
            (reqtrace--finding (plist-get info :file) 1 nil (cdr res)
                               "make the command print one test address a line")
          (dolist (r (plist-get info :reqs))
            (when (equal (plist-get r :state) "DONE")
              (dolist (a (plist-get r :verify))
                (unless (member a (cdr res))
                  (reqtrace--finding (plist-get r :file) (plist-get r :line) (plist-get r :id)
                                     (format ":VERIFY: names %s, which the test command does not list" a)
                                     "write the test, or fix the address"))))))))))

(defun reqtrace--lint-staged (staged head)
  "RT-6: the change rules, STAGED infos against HEAD infos."
  (let ((before (make-hash-table :test #'equal)) (today (reqtrace--today)))
    (dolist (r (reqtrace--all-reqs head)) (when (plist-get r :id) (puthash (plist-get r :id) r before)))
    (dolist (r (reqtrace--all-reqs staged))
      (let* ((id (plist-get r :id)) (old (and id (gethash id before)))
             (f (plist-get r :file)) (l (plist-get r :line))
             (done (equal (plist-get r :state) "DONE")))
        (when id
          (if old
              (let ((changed (not (equal (plist-get old :text) (plist-get r :text)))))
                (when (and changed done (equal (plist-get old :state) "DONE"))
                  (reqtrace--finding f l id "a DONE requirement's text changed"
                                     "make it OPEN until the change is built"))
                (when (and changed (not (equal (plist-get r :last-edited) today)))
                  (reqtrace--finding f l id "its text changed and :LAST_EDITED: is not today"
                                     (format "set :LAST_EDITED: %s" today)))
                (when (and done (not (equal (plist-get old :state) "DONE"))
                           (not (equal (plist-get r :implemented) today)))
                  (reqtrace--finding f l id "it turned DONE and :IMPLEMENTED: is not today"
                                     (format "set :IMPLEMENTED: %s" today))))
            (unless (and (equal (plist-get r :created) today) (equal (plist-get r :last-edited) today))
              (reqtrace--finding f l id "a new requirement whose :CREATED: or :LAST_EDITED: is not today"
                                 (format "set both to %s" today)))
            (when (and done (not (equal (plist-get r :implemented) today)))
              (reqtrace--finding f l id "new and DONE, and :IMPLEMENTED: is not today"
                                 (format "set :IMPLEMENTED: %s" today)))))))))

(defun reqtrace-lint (args)
  (let ((staged (member "--staged" args))
        (no-tests (member "--no-tests" args))
        (only (cl-remove-if (lambda (a) (string-prefix-p "--" a)) args)))
    (let ((bad (cl-find-if (lambda (a) (and (string-prefix-p "--" a)
                                             (not (member a '("--staged" "--no-tests")))))
                           args)))
      (when bad (reqtrace--err "reqtrace: unknown option %s; see reqtrace lint --help" bad) (kill-emacs 1)))
    (let* ((infos (reqtrace--opted (if staged (reqtrace--rev-files "") (reqtrace--worktree-files))))
           (only (and only (mapcar (lambda (f) (file-relative-name (expand-file-name f) default-directory)) only))))
      (if (null infos)
          (reqtrace--err "reqtrace: no requirements file here has #+REQTRACE_TESTS:")
        (reqtrace--lint-file-rules infos only)
        (unless no-tests (reqtrace--lint-verify infos only))
        (when staged
          (reqtrace--lint-staged infos (reqtrace--opted (reqtrace--rev-files "HEAD"))))))
    (kill-emacs (if (> reqtrace--findings 0) 1 0))))

;;;; commit-msg (RT-7)

(defun reqtrace--names-id-p (text id)
  (string-match-p (concat "\\(?:\\`\\|[^A-Za-z0-9_-]\\)" (regexp-quote id) "\\(?:\\'\\|[^A-Za-z0-9_-]\\)")
                  text))

(defun reqtrace-commit-msg (args)
  (unless (= (length args) 1)
    (reqtrace--err "reqtrace: commit-msg takes one MSGFILE; see reqtrace commit-msg --help")
    (kill-emacs 1))
  (let* ((msgfile (car args))
         (infos (reqtrace--opted (reqtrace--rev-files "")))
         (code (cl-mapcan (lambda (i) (copy-sequence (plist-get i :code))) infos))
         (paths (reqtrace--lines (reqtrace--git-out "diff" "--cached" "--name-only")))
         (touches (cl-some (lambda (p) (cl-some (lambda (c) (or (equal p c) (string-prefix-p (file-name-as-directory (directory-file-name c)) p)
                                                                  (and (string-suffix-p "/" c) (string-prefix-p c p))))
                                                  code))
                           paths)))
    (when touches
      (let* ((msg (string-join (cl-remove-if (lambda (l) (string-prefix-p "#" l))
                                             (split-string (with-temp-buffer (insert-file-contents msgfile) (buffer-string)) "\n"))
                               "\n"))
             (ids (delq nil (mapcar (lambda (r) (plist-get r :id)) (reqtrace--all-reqs infos)))))
        (unless (cl-some (lambda (id) (reqtrace--names-id-p msg id)) ids)
          (reqtrace--finding msgfile 1 nil
                             (format "this commit changes code (%s) and names no requirement id" touches)
                             "name one in the message, as (RF-3)"))))
    (kill-emacs (if (> reqtrace--findings 0) 1 0))))

;;;; trace (RT-8, RT-9)

(defun reqtrace--commits ()
  "List of (HASH SHORT DATE SUBJECT BODY), newest first."
  (let ((out (reqtrace--git-out "log" "--format=%H%x1f%h%x1f%cs%x1f%s%x1f%B%x1e")))
    (cl-loop for rec in (split-string (or out "") "\x1e" t)
             for f = (split-string (string-trim-left rec) "\x1f")
             when (>= (length f) 5) collect f)))

(defun reqtrace--last-changes (infos)
  "Hash ID -> the last day its text changed in git, walking each file's revisions."
  (let ((changed (make-hash-table :test #'equal)))
    (dolist (info infos)
      (let ((file (plist-get info :file)) (prev (make-hash-table :test #'equal)))
        (dolist (line (reqtrace--lines (reqtrace--git-out "log" "--reverse" "--format=%H %cs" "--" file)))
          (let* ((parts (split-string line " ")) (rev (car parts)) (day (cadr parts))
                 (content (reqtrace--git-out "show" (concat rev ":" file))))
            (when content
              (dolist (pair (reqtrace--quick-ids content))
                (unless (equal (gethash (car pair) prev) (cdr pair))
                  (puthash (car pair) day changed)
                  (puthash (car pair) (cdr pair) prev))))))))
    changed))

(defun reqtrace--suspects (reqs changed)
  "List of (CHILD PARENT DAY) for DONE children whose parent changed after them."
  (let (out)
    (dolist (r reqs)
      (when (equal (plist-get r :state) "DONE")
        (let ((since (car (sort (delq nil (list (plist-get r :implemented) (plist-get r :reviewed)))
                                #'string>))))
          (dolist (p (plist-get r :needs))
            (let ((day (gethash p changed)))
              (when (and day since (string> day since))
                (push (list (plist-get r :id) p day) out)))))))
    (nreverse out)))

(defun reqtrace--block (r reqs addresses commits suspects one)
  (let* ((id (plist-get r :id))
         (children (cl-loop for c in reqs when (member id (plist-get c :needs)) collect (plist-get c :id))))
    (reqtrace--out "%s %s %s" (or id "(no id)") (or (plist-get r :state) "-") (plist-get r :title))
    (reqtrace--out "  file: %s:%d" (plist-get r :file) (plist-get r :line))
    (reqtrace--out "  parents: %s" (if (plist-get r :needs) (string-join (plist-get r :needs) " ") "none"))
    (reqtrace--out "  children: %s" (if children (string-join children " ") "none"))
    (if (plist-get r :verify)
        (dolist (a (plist-get r :verify))
          (reqtrace--out "  verify: %s %s" a
                         (cond ((not (car addresses)) "unchecked")
                               ((member a (cdr addresses)) "found")
                               (t "missing"))))
      (reqtrace--out "  verify: none"))
    (let ((mine (and id (cl-remove-if-not (lambda (c) (reqtrace--names-id-p (nth 4 c) id)) commits))))
      (if (null mine)
          (reqtrace--out "  commits: none")
        (dolist (c mine)
          (reqtrace--out "  commit: %s %s %s" (nth 1 c) (nth 2 c) (nth 3 c))
          (when one
            (dolist (f (reqtrace--lines (reqtrace--git-out "show" "--name-only" "--format=" (nth 0 c))))
              (reqtrace--out "    %s" f))))))
    (dolist (s suspects)
      (when (equal (car s) id)
        (reqtrace--out "  suspect: parent %s changed %s" (nth 1 s) (nth 2 s))))))

(defun reqtrace--opted-here-p ()
  "Whether this repo has an opted-in file; a git grep, so no parse."
  (zerop (car (reqtrace--git "grep" "--cached" "-q" "-E" "^#\\+REQTRACE_TESTS:" "--" "*.org"))))

(defun reqtrace--projects-with (id)
  "Git roots under ~/repos, other than this one, whose opted-in files hold ID (RT-19)."
  (let ((here (and (reqtrace--root) (file-truename default-directory))))
    (cl-loop for d in (reqtrace--repos)
             unless (equal (file-truename d) here)
             when (let ((default-directory d))
                    (and (reqtrace--opted-here-p)
                         (cl-some (lambda (r) (equal id (plist-get r :id)))
                                  (reqtrace--all-reqs (reqtrace--opted (reqtrace--worktree-files))))))
             collect d)))

(defun reqtrace-trace (args)
  (let* ((want (car args))
         (infos (and (reqtrace--root) (reqtrace--opted (reqtrace--worktree-files)))))
    (when (and want (null reqtrace--projects)
               (not (cl-some (lambda (r) (equal want (plist-get r :id))) (reqtrace--all-reqs infos))))
      (let ((hits (reqtrace--projects-with want)))
        (unless hits
          (reqtrace--err "reqtrace: unknown id %s, here or in any project under %s; reqtrace list --all shows the ids"
                         want (abbreviate-file-name (expand-file-name (or (getenv "REQTRACE_REPOS") "~/repos"))))
          (kill-emacs 1))
        (dolist (d hits)
          (reqtrace--out "project: %s" (abbreviate-file-name (directory-file-name d)))
          (let ((default-directory d))
            (reqtrace--trace-in (reqtrace--opted (reqtrace--worktree-files)) want)))
        (kill-emacs 0)))
    (when (null infos)
      (reqtrace--err "reqtrace: no requirements file here has #+REQTRACE_TESTS:; name a project with -p DIR")
      (kill-emacs 0))
    (reqtrace--trace-in infos want)
    (kill-emacs 0)))

(defun reqtrace--trace-in (infos want)
  "Print the trace of INFOS, or of the one requirement WANT, for the repo here."
  (progn
    (let* ((reqs (reqtrace--all-reqs infos))
           (commits (reqtrace--commits))
           (changed (reqtrace--last-changes infos))
           (suspects (reqtrace--suspects reqs changed))
           (addr-of (lambda (r) (reqtrace--test-addresses
                                 (plist-get (cl-find (plist-get r :file) infos
                                                     :key (lambda (i) (plist-get i :file)) :test #'equal)
                                            :tests)))))
      (if want
          (let ((r (cl-find want reqs :key (lambda (x) (plist-get x :id)) :test #'equal)))
            (unless r
              (reqtrace--err "reqtrace: unknown id %s; reqtrace list shows the ids" want)
              (kill-emacs 1))
            (reqtrace--block r reqs (funcall addr-of r) commits suspects t))
        (dolist (r reqs)
          (reqtrace--block r reqs (funcall addr-of r) commits suspects nil)
          (reqtrace--out ""))
        (let* ((named (cl-mapcan (lambda (r) (copy-sequence (plist-get r :verify))) reqs))
               (orphans (cl-loop for info in infos
                                 for res = (reqtrace--test-addresses (plist-get info :tests))
                                 when (car res)
                                 append (cl-remove-if (lambda (a) (member a named)) (cdr res)))))
          (reqtrace--out "Orphan tests: %s" (if orphans "" "none"))
          (dolist (o (delete-dups orphans)) (reqtrace--out "  %s" o)))
        (reqtrace--out "Suspect: %s" (if suspects "" "none"))
        (dolist (s suspects)
          (reqtrace--out "  %s: parent %s changed %s" (nth 0 s) (nth 1 s) (nth 2 s)))))))

;;;; list (RT-13)

(defun reqtrace--group (r)
  (let ((state (plist-get r :state)))
    (cond ((equal state "DONE") "done")
          ((equal state "DROPPED") "dropped")
          ((plist-get r :approved) "approved")
          (t "waiting"))))

(defconst reqtrace--group-names
  '(("waiting" . "Waiting for approval") ("approved" . "Approved and open")
    ("done" . "Done") ("dropped" . "Dropped")))

(defun reqtrace--rows (no-tests)
  "Rows for every listed requirement of the repo here."
  (let ((infos (reqtrace--listed (reqtrace--worktree-files))))
    (cl-loop for info in infos
             for addr = (and (plist-get info :opted) (not no-tests)
                             (reqtrace--test-addresses (plist-get info :tests)))
             append (cl-loop for r in (plist-get info :reqs)
                             collect (let ((v (plist-get r :verify)))
                                       (append r (list :group (reqtrace--group r)
                                                       :check (cond ((null v) "none")
                                                                    ((not (car addr)) "named")
                                                                    ((cl-every (lambda (a) (member a (cdr addr))) v) "found")
                                                                    (t "missing")))))))))

(defun reqtrace--filter (rows opts)
  (cl-remove-if-not
   (lambda (r)
     (and (or (null (plist-get opts :state))
              (equal (downcase (or (plist-get r :state) "")) (plist-get opts :state)))
          (or (null (plist-get opts :section))
              (and (plist-get r :id) (string-prefix-p (concat (plist-get opts :section) "-") (plist-get r :id))))
          (or (not (plist-get opts :unchecked))
              (and (equal (plist-get r :state) "DONE") (member (plist-get r :check) '("none" "missing"))))
          (or (not (plist-get opts :ready))
              (and (equal (plist-get r :state) "OPEN") (plist-get r :approved)))))
   rows))

(defun reqtrace--trunc (s n) (if (> (length s) n) (concat (substring s 0 (1- n)) "…") s))

(defun reqtrace--print-table (rows)
  (dolist (g reqtrace--group-names)
    (let ((in (cl-remove-if-not (lambda (r) (equal (plist-get r :group) (car g))) rows)))
      (when in
        (reqtrace--out "%s (%d)" (cdr g) (length in))
        (dolist (r in)
          (reqtrace--out "  %-22s %-7s %-8s %-7s %-60s %s:%d"
                         (or (plist-get r :id) "(no id)") (or (plist-get r :state) "-")
                         (if (plist-get r :approved) "approved" "-")
                         (plist-get r :check) (reqtrace--trunc (plist-get r :title) 60)
                         (plist-get r :file) (plist-get r :line))))))
  (let ((noid (cl-count-if (lambda (r) (null (plist-get r :id))) rows)))
    (when (> noid 0) (reqtrace--out "No id: %d" noid))))

(defun reqtrace--json-row (r repo)
  (append
   (and repo (list (cons 'repo repo)))
   (list (cons 'id (or (plist-get r :id) :null))
            (cons 'state (or (plist-get r :state) :null))
            (cons 'group (plist-get r :group))
            (cons 'approved (or (plist-get r :approved) :null))
            (cons 'verify (vconcat (plist-get r :verify)))
            (cons 'check (plist-get r :check))
            (cons 'needs (vconcat (plist-get r :needs)))
            (cons 'title (plist-get r :title))
            (cons 'file (plist-get r :file))
            (cons 'line (plist-get r :line)))))

(defun reqtrace--list-opts (args)
  (let (opts)
    (while args
      (let ((a (pop args)))
        (pcase a
          ("--state" (let ((v (pop args)))
                       (unless (member v '("open" "done" "dropped"))
                         (reqtrace--err "reqtrace: --state takes open, done or dropped") (kill-emacs 1))
                       (setq opts (plist-put opts :state v))))
          ("--section" (let ((v (pop args)))
                         (unless (and v (string-match-p "\\`[A-Z]+\\'" v))
                           (reqtrace--err "reqtrace: --section takes capital letters, as M") (kill-emacs 1))
                         (setq opts (plist-put opts :section v))))
          ("--unchecked" (setq opts (plist-put opts :unchecked t)))
          ("--ready" (setq opts (plist-put opts :ready t)))
          ("--all" (setq opts (plist-put opts :all t)))
          ("--json" (setq opts (plist-put opts :json t)))
          ("--no-tests" (setq opts (plist-put opts :no-tests t)))
          (_ (reqtrace--err "reqtrace: unknown option %s; see reqtrace list --help" a) (kill-emacs 1)))))
    opts))

(defun reqtrace--repos ()
  (let ((base (expand-file-name (or (getenv "REQTRACE_REPOS") "~/repos"))))
    (cl-loop for d in (directory-files base t "\\`[^.]")
             when (and (file-directory-p d) (file-exists-p (expand-file-name ".git" d)))
             collect (file-name-as-directory d))))

(defun reqtrace-list (args)
  (let* ((opts (reqtrace--list-opts args))
         (many (or (plist-get opts :all) reqtrace--projects))
         (per (if many
                  (cl-loop for d in (delete-dups (append reqtrace--projects
                                                         (and (plist-get opts :all) (reqtrace--repos))))
                           for rows = (let ((default-directory d)) (reqtrace--rows (plist-get opts :no-tests)))
                           when rows collect (cons (file-name-nondirectory (directory-file-name d)) rows))
                (list (cons nil (reqtrace--rows (plist-get opts :no-tests)))))))
    (setq per (mapcar (lambda (p) (cons (car p) (reqtrace--filter (cdr p) opts))) per))
    (when many (setq per (cl-remove-if-not #'cdr per)))
    (if (plist-get opts :json)
        (princ (concat (json-encode (vconcat (cl-loop for (repo . rows) in per
                                                       append (mapcar (lambda (r) (reqtrace--json-row r repo)) rows))))
                       "\n"))
      (dolist (p per)
        (when (car p) (reqtrace--out "== %s" (car p)))
        (reqtrace--print-table (cdr p))
        (when (car p) (reqtrace--out "")))
      (let ((all (cl-mapcan (lambda (p) (copy-sequence (cdr p))) per)))
        (reqtrace--out "Total: %d requirement%s%s: %d open, %d done, %d dropped"
                       (length all) (if (= 1 (length all)) "" "s")
                       (if many (let ((n (length per))) (format " in %d repo%s" n (if (= n 1) "" "s"))) "")
                       (cl-count-if (lambda (r) (equal (plist-get r :state) "OPEN")) all)
                       (cl-count-if (lambda (r) (equal (plist-get r :state) "DONE")) all)
                       (cl-count-if (lambda (r) (equal (plist-get r :state) "DROPPED")) all))))
    (kill-emacs 0)))

;;;; next-id (RT-14)

(defun reqtrace-next-id (args)
  (let ((letter (car args)))
    (unless (and letter (= (length args) 1) (string-match-p "\\`[A-Z]+\\'" letter))
      (reqtrace--err "reqtrace: next-id takes one section letter, as M; see reqtrace next-id --help")
      (kill-emacs 1))
    (let ((top 0) (re (concat "\\`" (regexp-quote letter) "-\\([0-9]+\\)\\'")))
      (dolist (r (reqtrace--all-reqs (reqtrace--listed (reqtrace--worktree-files))))
        (let ((id (plist-get r :id)))
          (when (and id (string-match re id))
            (setq top (max top (string-to-number (match-string 1 id)))))))
      (reqtrace--out "%s-%d" letter (1+ top))
      (kill-emacs 0))))

;;;; Help (RT-2)

(defconst reqtrace--help
  '((main
     "usage: reqtrace COMMAND [ARGS]
Lint, trace and list a repo's org requirements.
Commands: lint, commit-msg, trace, list, next-id, help
Run it inside a git repo, or name one with --project DIR (-p DIR).
It reads, and never writes a file.
example: reqtrace list --ready -p ~/repos/arcadia_docs"
     "Commands:
  lint [--staged] [--no-tests] [FILE...]  refuse what requirements.org forbids
  commit-msg MSGFILE                      refuse a code commit that names no id
  trace [ID]                              each requirement's links, tests and commits
  list [filters] [--all] [--json]         every requirement in a table
  next-id LETTER                          the next free id, as M-15
  help                                    this text
Each command takes -h, --help and help.
Each command takes --project DIR (-p DIR): run on the git repo that holds DIR,
instead of the one here. list takes it more than once: one table each.
lint, commit-msg and trace read files whose header has #+REQTRACE_TESTS:.
list and next-id read every requirements file: requirements.org, files under
a requirements/ folder, and files whose #+TODO names OPEN.
A finding is one line on stderr: reqtrace: <file>:<line>: <id>: <why>; <fix>
Exit 0 when clean, 1 on any finding or failure.")
    (lint
     "usage: reqtrace lint [--project DIR] [--staged] [--no-tests] [FILE...]
Refuse what requirements.org forbids, in files with #+REQTRACE_TESTS:.
example: reqtrace lint --staged --no-tests"
     "--staged    read the staged copies and refuse changes against HEAD:
            a DONE requirement whose text changed, :LAST_EDITED: not today,
            a new requirement not dated today, a DONE one not :IMPLEMENTED: today
--no-tests  skip the test command and the :VERIFY: rule
FILE...     report findings for these files only
REQTRACE_TEST_SECONDS sets the test command's time (60 s); REQTRACE_TODAY sets today.")
    (commit-msg
     "usage: reqtrace commit-msg [--project DIR] MSGFILE
Refuse a commit that changes code under #+REQTRACE_CODE: and names no requirement id.
example: reqtrace commit-msg .git/COMMIT_EDITMSG"
     "The ids come from the staged requirements files, so one commit may add a
requirement and name it. Comment lines (#) do not count. An id matches as a
whole word: RF-3 is not RF-30.")
    (trace
     "usage: reqtrace trace [--project DIR] [ID]
Print each requirement's parents, children, tests and commits.
example: reqtrace trace RT-3"
     "With no ID: one block per requirement, then the orphan tests, which no
:VERIFY: names, then the suspect children: DONE requirements whose parent's
text changed in git after their :IMPLEMENTED: or :REVIEWED: day.
With an ID: that one block, and the files each of its commits touched.
An ID not in this project is looked for in every project under ~/repos,
and shown under a project: line.")
    (list
     "usage: reqtrace list [--project DIR]... [--state open|done|dropped] [--section L] [--unchecked] [--ready] [--all] [--json] [--no-tests]
Print every requirement in a table, grouped by state and approval.
example: reqtrace list --section M --ready"
     "Columns: id, state, approved, check (found, missing, named, none), title, file:line.
Groups: waiting for approval, approved and open, done, dropped.
--state S     only that state
--section L   only ids that start with L-
--unchecked   DONE ones whose :VERIFY: is empty or names a test that is missing
--ready       approved and still OPEN
--project DIR the git repo that holds DIR; give it again for more, one table each
--all         every git repo under ~/repos (REQTRACE_REPOS sets the folder)
--json        the rows as a JSON array
--no-tests    skip the test command; the check column says named")
    (next-id
     "usage: reqtrace next-id [--project DIR] LETTER
Print the next free id for a section: one more than the highest in use.
example: reqtrace next-id M"
     "A gap is never filled, so an id is never reused. A letter with no id yet prints L-1.")))

(defun reqtrace--help-for (cmd long)
  (let ((h (cdr (assq cmd reqtrace--help))))
    (reqtrace--out "%s" (car h))
    (when long (reqtrace--out "\n%s" (cadr h)))
    (kill-emacs 0)))

;;;; Main

(defvar reqtrace--projects nil "Git roots named by --project, in order.")

(defun reqtrace--take-projects (args)
  "ARGS without --project DIR and -p DIR; each DIR's git root goes to `reqtrace--projects'."
  (let (out)
    (while args
      (let ((a (pop args)))
        (if (not (member a '("--project" "-p")))
            (push a out)
          (let* ((dir (pop args))
                 (path (and dir (expand-file-name dir))))
            (unless (and path (file-directory-p path))
              (reqtrace--err "reqtrace: %s: no such folder" (or dir "--project needs a folder"))
              (kill-emacs 1))
            (let ((root (let ((default-directory (file-name-as-directory path))) (reqtrace--root))))
              (unless root
                (reqtrace--err "reqtrace: %s: not inside a git repo" dir)
                (kill-emacs 1))
              (setq reqtrace--projects (append reqtrace--projects (list root))))))))
    (nreverse out)))

(defun reqtrace-main (args)
  (setq case-fold-search nil)
  (when (equal (car args) "--") (setq args (cdr args)))
  (let* ((cmd (car args))
         (rest (if (member cmd '(nil "-h" "--help" "help")) (cdr args) (reqtrace--take-projects (cdr args)))))
    (when (and (cdr reqtrace--projects) (not (equal cmd "list")))
      (reqtrace--err "reqtrace: %s takes one --project; list takes several" cmd)
      (kill-emacs 1))
    (cond
     ((or (null cmd) (member cmd '("-h" "--help"))) (reqtrace--help-for 'main nil))
     ((equal cmd "help") (reqtrace--help-for 'main t))
     ((not (assq (intern cmd) reqtrace--help))
      (reqtrace--err "reqtrace: unknown command %s; see reqtrace --help" cmd)
      (kill-emacs 1))
     ((member (car rest) '("-h" "--help")) (reqtrace--help-for (intern cmd) nil))
     ((equal (car rest) "help") (reqtrace--help-for (intern cmd) t))
     (t
      (let ((root (if (and reqtrace--projects (not (equal cmd "list")))
                      (car reqtrace--projects)
                    (reqtrace--root))))
        (when (and (equal cmd "list") reqtrace--projects (not root))
          (setq root default-directory))
        (unless (or root (equal cmd "list") (and (equal cmd "trace") rest))
          (reqtrace--err "reqtrace: not inside a git repo") (kill-emacs 1))
        (let ((default-directory (or root default-directory)))
          (if (and (null root) (not (member "--all" rest)) (null reqtrace--projects)
                   (not (and (equal cmd "trace") rest)))
              (progn (reqtrace--err "reqtrace: not inside a git repo; use --all") (kill-emacs 1))
            (pcase cmd
              ("lint" (reqtrace-lint rest))
              ("commit-msg" (reqtrace-commit-msg rest))
              ("trace" (reqtrace-trace rest))
              ("list" (reqtrace-list rest))
              ("next-id" (reqtrace-next-id rest))
              (_ (reqtrace--help-for 'main nil))))))))))

(when noninteractive
  (condition-case err
      (reqtrace-main (prog1 command-line-args-left (setq command-line-args-left nil)))
    (error (reqtrace--err "reqtrace: %s" (error-message-string err)) (kill-emacs 1))))

;;; reqtrace.el ends here
