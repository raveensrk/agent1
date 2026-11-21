;;; lemmax.el --- lint, trace and list org requirements  -*- lexical-binding: t; -*-

;; Run through the launcher: requirements/scripts/lemmax/lemmax COMMAND ...
;; Requirements: requirements/scripts/lemmax/requirements.org (RT-1 to RT-15).
;; It reads files and git, and never writes a file.

;; lemma: RT-1
(require 'org)
(require 'org-element)
(require 'subr-x)
(require 'cl-lib)
(require 'json)
(require 'time-date)

(defconst lemmax-states '("OPEN" "DONE" "DROPPED"))
(defconst lemmax-dates '("CREATED" "LAST_EDITED" "APPROVED" "IMPLEMENTED" "REVIEWED"))
(defvar lemmax--findings 0)
(defvar lemmax--tests-cache (make-hash-table :test #'equal))

;;;; Output

(defun lemmax--out (fmt &rest args)
  (princ (apply #'format fmt args))
  (princ "\n"))

(defun lemmax--err (fmt &rest args)
  (message "%s" (apply #'format fmt args)))

(defun lemmax--finding (file line id why fix)
  "One finding line on stderr (RT-2)."
  (setq lemmax--findings (1+ lemmax--findings))
  (lemmax--err "lemmax: %s:%s: %s: %s; %s" file line (or id "-") why fix))

;;;; Git

(defun lemmax--git (&rest args)
  "Run git with ARGS in `default-directory'; (EXIT . OUTPUT)."
  (with-temp-buffer
    (let ((code (apply #'call-process "git" nil (list t nil) nil args)))
      (cons code (buffer-string)))))

(defun lemmax--git-out (&rest args)
  (let ((r (apply #'lemmax--git args)))
    (and (zerop (car r)) (cdr r))))

(defun lemmax--lines (s)
  (split-string (or s "") "\n" t))

(defun lemmax--root ()
  (let ((top (lemmax--git-out "rev-parse" "--show-toplevel")))
    (and top (file-name-as-directory (string-trim top)))))

;;;; Parsing

(defun lemmax--entry-text (raw)
  "The text of an entry from RAW, its heading line to the next heading:
heading, body and properties, without its state and the 5 dates."
  (let* ((lines (split-string raw "\n"))
         (head (replace-regexp-in-string
                (concat "\\`\\(\\*+\\) +" (regexp-opt lemmax-states) "\\_>")
                "\\1" (car lines)))
         ;; lemma: 01a2002a-bf93-7475-94c3-d083c65a87d6
         (head (replace-regexp-in-string
                "\\`\\(\\*+\\(?: +\\[#.\\]\\)?\\) +[A-Z]+-[0-9]+ " "\\1 " head))
         (date-re (concat "\\`[ \t]*:" (regexp-opt lemmax-dates) ":")))
    (replace-regexp-in-string
     ;; A link to a heading that starts with an id holds the same text without it.
     "\\(\\[\\[\\(?:[^]\n]*::\\)?\\*\\)[A-Z]+-[0-9]+ " "\\1"
     (string-trim-right
      (string-join (cons (string-trim-right head)
                         (cl-remove-if (lambda (l) (string-match-p date-re l)) (cdr lines)))
                   "\n")))))

;; lemma: RT-17
(defun lemmax--entry-body (raw)
  "The body of an entry from RAW: its lines after the heading, without the
property drawer, trimmed (RT-17)."
  (let ((lines (cdr (split-string raw "\n"))) (in nil) out)
    (dolist (l lines)
      (cond ((string-match-p "\\`[ \t]*:PROPERTIES:[ \t]*\\'" l) (setq in t))
            ((and in (string-match-p "\\`[ \t]*:END:[ \t]*\\'" l)) (setq in nil))
            ((not in) (push l out))))
    (string-trim (string-join (nreverse out) "\n"))))

(defun lemmax--split-headings (content)
  "Each heading of CONTENT with its body, up to the next heading."
  (let ((pos 0) starts)
    (while (string-match "^\\*+ " content pos)
      (push (match-beginning 0) starts)
      (setq pos (match-end 0)))
    (setq starts (nreverse starts))
    (cl-loop for (a b) on starts
             collect (substring content a (or b (length content))))))

(defun lemmax--quick-ids (content)
  "Alist (ID . TEXT) for each heading of CONTENT with an :ID:; headlines only (RT-9)."
  (let (out)
    (dolist (c (lemmax--split-headings content))
      (when (string-match "^[ \t]*:ID:[ \t]+\\(\\S-+\\)" c)
        (push (cons (match-string 1 c) (lemmax--entry-text c)) out)))
    (nreverse out)))

(defun lemmax--parse (content file)
  "Parse org CONTENT named FILE: plist (:file :keywords :opted :listed :reqs)."
  (with-temp-buffer
    (insert content)
    (let ((org-todo-keywords '((sequence "OPEN" "|" "DONE" "DROPPED")))
          (org-element-use-cache nil)
          (org-inhibit-startup t))
      (delay-mode-hooks (org-mode))
      (let* ((kw (org-collect-keywords '("LEMMAX_TESTS" "LEMMAX_CODE" "LEMMAX_TEST_PATHS" "LEMMAX_MARKERS_IN" "TODO"
                                         ;; The names before lemmax, read so older commits still match.
                                         "REQTRACE_TESTS" "REQTRACE_CODE")))
             (todo (cadr (assoc "TODO" kw)))
             reqs)
        (org-map-entries
         (lambda ()
           (let ((state (org-get-todo-state))
                 (id (org-entry-get nil "ID")))
             (when (or (member state lemmax-states) id)
               (let* ((beg (point))
                      (end (save-excursion (outline-next-heading) (point)))
                      (get (lambda (p) (let ((v (org-entry-get nil p)))
                                         (and v (not (string-empty-p (string-trim v)))
                                              (string-trim v))))))
                 (push (list :id (and id (string-trim id))
                             :state (and (member state lemmax-states) state)
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
                             :text (lemmax--entry-text
                                    (buffer-substring-no-properties beg end))
                             :body (lemmax--entry-body
                                    (buffer-substring-no-properties beg end)))
                       reqs))))))
        (let* ((tests-kw (or (assoc "LEMMAX_TESTS" kw) (assoc "REQTRACE_TESTS" kw)))
               (code-kw (or (assoc "LEMMAX_CODE" kw) (assoc "REQTRACE_CODE" kw)))
               (opted (and tests-kw t)))
          (list :file file
                :keywords kw
                :opted opted
                :tests (cadr tests-kw)
                :code (let ((c (cadr code-kw))) (and c (split-string c)))
                :test-paths (let ((c (cadr (assoc "LEMMAX_TEST_PATHS" kw)))) (and c (split-string c)))
                :markers-in (let ((c (cadr (assoc "LEMMAX_MARKERS_IN" kw)))) (and c (split-string c)))
                :listed (or opted
                            (equal (file-name-nondirectory file) "requirements.org")
                            (member "requirements" (split-string (or (file-name-directory file) "") "/" t))
                            (and todo (string-match-p "\\_<OPEN\\_>" todo) t))
                :reqs (nreverse reqs)))))))

(defun lemmax--worktree-files ()
  "Parsed infos of the repo's git-tracked .org files, from the work tree."
  (cl-loop for f in (lemmax--lines (lemmax--git-out "ls-files" "*.org"))
           when (file-readable-p f)
           collect (lemmax--parse (with-temp-buffer (insert-file-contents f) (buffer-string)) f)))

(defun lemmax--rev-files (rev)
  "Parsed infos of the .org files at REV: \"\" for the index, \"HEAD\" for HEAD."
  (let ((names (if (string-empty-p rev)
                   (lemmax--lines (lemmax--git-out "ls-files" "*.org"))
                 (cl-remove-if-not (lambda (f) (string-suffix-p ".org" f))
                                   (lemmax--lines (lemmax--git-out "ls-tree" "-r" "--name-only" rev))))))
    (cl-loop for f in names
             for c = (lemmax--git-out "show" (concat rev ":" f))
             when c collect (lemmax--parse c f))))

(defun lemmax--opted (infos) (cl-remove-if-not (lambda (i) (plist-get i :opted)) infos))
(defun lemmax--listed (infos) (cl-remove-if-not (lambda (i) (plist-get i :listed)) infos))
(defun lemmax--all-reqs (infos) (cl-mapcan (lambda (i) (copy-sequence (plist-get i :reqs))) infos))

;;;; The test command (RT-5)

(defun lemmax--test-addresses (cmd)
  "Run CMD from the repo root: (t . ADDRESSES) or (nil . WHY)."
  (or (gethash cmd lemmax--tests-cache)
      (puthash
       cmd
       (let* ((limit (string-to-number (or (getenv "LEMMAX_TEST_SECONDS") "60")))
              (buf (generate-new-buffer " *lemmax-tests*"))
              (errbuf (generate-new-buffer " *lemmax-tests-err*"))
              (proc (make-process :name "lemmax-tests" :buffer buf :stderr errbuf
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
       lemmax--tests-cache)))

;;;; Dates

(defun lemmax--day-p (s)
  (and s (string-match "\\`\\([0-9]\\{4\\}\\)-\\([0-9]\\{2\\}\\)-\\([0-9]\\{2\\}\\)\\'" s)
       (let ((y (string-to-number (match-string 1 s)))
             (m (string-to-number (match-string 2 s)))
             (d (string-to-number (match-string 3 s))))
         (and (<= 1 m 12) (<= 1 d (date-days-in-month y m))))))

(defun lemmax--today ()
  (or (getenv "LEMMAX_TODAY") (format-time-string "%F")))

;;;; lint (RT-4, RT-5, RT-6)

(defun lemmax--uuid7-p (id)
  "Whether ID is a lower-case UUID v7, as agent1's id rule asks for new requirements."
  (string-match-p "\\`[0-9a-f]\\{8\\}-[0-9a-f]\\{4\\}-7[0-9a-f]\\{3\\}-[89ab][0-9a-f]\\{3\\}-[0-9a-f]\\{12\\}\\'" id))

(defun lemmax--lint-file-rules (infos only)
  "RT-4 over the opted-in INFOS; findings only for files in ONLY, when given."
  (let ((seen (make-hash-table :test #'equal))
        (all (lemmax--all-reqs infos))
        (show (lambda (r) (or (null only) (member (plist-get r :file) only)))))
    (dolist (r all)
      (let ((id (plist-get r :id)) (state (plist-get r :state))
            (f (plist-get r :file)) (l (plist-get r :line)))
        (when (funcall show r)
          (when (string-match-p "\\`[A-Z]+-[0-9]+\\_>" (plist-get r :title))
            (lemmax--finding f l id "the heading text starts with an id"
                               "keep the id in :ID: only"))
          (cond ((null id) (lemmax--finding f l nil "no :ID:" "add :ID: as RF-3"))
                ((not (or (string-match-p "\\`[A-Z]+-[0-9]+\\'" id) (lemmax--uuid7-p id)))
                 (lemmax--finding f l id "the id is neither a UUID v7 nor shaped [A-Z]+-[0-9]+"
                                    "make a new one with python3 -c 'import uuid; print(uuid.uuid7())'")))
          (when (and (member state '("OPEN" "DONE")) (null (plist-get r :approved)))
            (lemmax--finding f l id (format "%s with no :APPROVED:" state)
                               "get the owner's approval, then add :APPROVED: with its day"))
          (unless (plist-get r :created) (lemmax--finding f l id "no :CREATED:" "add :CREATED: YYYY-MM-DD"))
          (unless (plist-get r :last-edited)
            (lemmax--finding f l id "no :LAST_EDITED:" "add :LAST_EDITED: YYYY-MM-DD"))
          (when (and (equal state "DONE") (null (plist-get r :implemented)))
            (lemmax--finding f l id "DONE with no :IMPLEMENTED:" "add :IMPLEMENTED: with the day it was built"))
          (when (and (member state '("OPEN" "DROPPED")) (plist-get r :implemented))
            (lemmax--finding f l id (format "%s with :IMPLEMENTED:" state)
                               "remove :IMPLEMENTED:, or make it DONE"))
          (dolist (p '(:created :last-edited :approved :implemented :reviewed))
            (let ((v (plist-get r p)))
              (when (and v (not (lemmax--day-p v)))
                (lemmax--finding f l id (format "%s is not a real day: %s" (substring (symbol-name p) 1) v)
                                   "write it as YYYY-MM-DD"))))
          (when (and (equal state "DONE") (null (plist-get r :verify)))
            (lemmax--finding f l id "DONE with no :VERIFY:" "name the checks that verify it")))
        (when id
          (if (gethash id seen)
              (when (funcall show r)
                (lemmax--finding f l id (format "the id is used twice, first at %s" (gethash id seen))
                                   "give this one a new id"))
            (puthash id (format "%s:%s" f l) seen)))))
    ;; NEEDS: unknown ids and cycles.
    (dolist (r all)
      (when (funcall show r)
        (dolist (n (plist-get r :needs))
          (unless (gethash n seen)
            (lemmax--finding (plist-get r :file) (plist-get r :line) (plist-get r :id)
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
                (lemmax--finding (plist-get r :file) (plist-get r :line) id
                                   ":NEEDS: makes a cycle back to this id"
                                   "remove one :NEEDS: link of the cycle")))))))))

(defun lemmax--lint-verify (infos only)
  "RT-5: a DONE requirement's :VERIFY: names tests the command prints."
  (dolist (info infos)
    (when (or (null only) (member (plist-get info :file) only))
      (let ((res (lemmax--test-addresses (plist-get info :tests))))
        (if (not (car res))
            (lemmax--finding (plist-get info :file) 1 nil (cdr res)
                               "make the command print one test address a line")
          (dolist (r (plist-get info :reqs))
            (when (equal (plist-get r :state) "DONE")
              (dolist (a (plist-get r :verify))
                (unless (member a (cdr res))
                  (lemmax--finding (plist-get r :file) (plist-get r :line) (plist-get r :id)
                                     (format ":VERIFY: names %s, which the test command does not list" a)
                                     "write the test, or fix the address"))))))))))

(defun lemmax--lint-staged (staged head)
  "RT-6: the change rules, STAGED infos against HEAD infos."
  (let ((before (make-hash-table :test #'equal)) (today (lemmax--today)))
    (dolist (r (lemmax--all-reqs head)) (when (plist-get r :id) (puthash (plist-get r :id) r before)))
    (dolist (r (lemmax--all-reqs staged))
      (let* ((id (plist-get r :id)) (old (and id (gethash id before)))
             (f (plist-get r :file)) (l (plist-get r :line))
             (done (equal (plist-get r :state) "DONE")))
        (when id
          (if old
              (let ((changed (not (equal (plist-get old :text) (plist-get r :text)))))
                (when (and changed done (equal (plist-get old :state) "DONE"))
                  (lemmax--finding f l id "a DONE requirement's text changed"
                                     "make it OPEN until the change is built"))
                (when (and changed (not (equal (plist-get r :last-edited) today)))
                  (lemmax--finding f l id "its text changed and :LAST_EDITED: is not today"
                                     (format "set :LAST_EDITED: %s" today)))
                (when (and done (not (equal (plist-get old :state) "DONE"))
                           (not (equal (plist-get r :implemented) today)))
                  (lemmax--finding f l id "it turned DONE and :IMPLEMENTED: is not today"
                                     (format "set :IMPLEMENTED: %s" today))))
            (unless (and (equal (plist-get r :created) today) (equal (plist-get r :last-edited) today))
              (lemmax--finding f l id "a new requirement whose :CREATED: or :LAST_EDITED: is not today"
                                 (format "set both to %s" today)))
            (when (and done (not (equal (plist-get r :implemented) today)))
              (lemmax--finding f l id "new and DONE, and :IMPLEMENTED: is not today"
                                 (format "set :IMPLEMENTED: %s" today)))))))))

(defun lemmax-lint (args)
  (let ((staged (member "--staged" args))
        (no-tests (member "--no-tests" args))
        (only (cl-remove-if (lambda (a) (string-prefix-p "--" a)) args)))
    (let ((bad (cl-find-if (lambda (a) (and (string-prefix-p "--" a)
                                             (not (member a '("--staged" "--no-tests")))))
                           args)))
      (when bad (lemmax--err "lemmax: unknown option %s; see lemmax lint --help" bad) (kill-emacs 1)))
    (let* ((infos (lemmax--opted (if staged (lemmax--rev-files "") (lemmax--worktree-files))))
           (only (and only (mapcar (lambda (f) (file-relative-name (expand-file-name f) default-directory)) only))))
      (if (null infos)
          (lemmax--err "lemmax: no requirements file here has #+LEMMAX_TESTS:")
        (lemmax--lint-file-rules infos only)
        (lemmax--lint-markers infos only staged)
        (unless no-tests (lemmax--lint-verify infos only))
        (when staged
          ;; lemma: 01a2002d-fb3b-71e3-ac96-5e1dbba8226c
          (let ((names (mapcar (lambda (i) (plist-get i :file)) infos)))
            (lemmax--lint-staged infos (cl-remove-if-not (lambda (i) (member (plist-get i :file) names))
                                                         (lemmax--rev-files "HEAD")))))))
    (kill-emacs (if (> lemmax--findings 0) 1 0))))

;;;; Code markers

;; lemma: 01a20014-e361-7827-b2a8-d3b2ded3e0b1
(defconst lemmax--marker-re
  "\\`[ \t]*\\(?:;+\\|#+\\|//+\\|--+\\|/\\*+\\|\\*+\\|<!--\\|%+\\)[ \t]*lemma:[ \t]+\\(.*\\)\\'"
  "A marker: a comment line whose first words are lemma: and ids.")

(defconst lemmax--default-test-paths
  '("test/" "tests/" "e2e/" "_test." "-test." ".spec." "_tests."))

(defun lemmax--test-paths (infos)
  "The test path patterns: the first #+LEMMAX_TEST_PATHS: in INFOS, else the defaults."
  (or (cl-some (lambda (i) (plist-get i :test-paths)) infos) lemmax--default-test-paths))

(defun lemmax--test-path-p (file patterns)
  (cl-some (lambda (p) (string-match-p (regexp-quote p) file)) patterns))

(defun lemmax--marker-ids (rest)
  "The ids at the start of REST: words that hold a hyphen, until the first that does not."
  (let (ids)
    (catch 'done
      (dolist (w (split-string rest "[ \t,]+" t))
        (if (and (string-match-p "\\`[A-Za-z0-9][A-Za-z0-9-]*\\'" w) (string-match-p "-" w))
            (push w ids)
          (throw 'done nil))))
    (nreverse ids)))

(defun lemmax--markers (patterns &optional cached)
  "Every marker in the tracked files but .org: a list of (ID FILE LINE TEST-P).
With CACHED, read the staged copies."
  (let ((out (apply #'lemmax--git-out
                    (append '("grep" "-n" "-I" "-E") (and cached '("--cached"))
                            '("lemma:[[:space:]]+[A-Za-z0-9]" "--" "." ":(exclude)*.org"))))
        res)
    (dolist (l (lemmax--lines out))
      (when (string-match "\\`\\([^:]+\\):\\([0-9]+\\):\\(.*\\)\\'" l)
        (let ((file (match-string 1 l)) (line (string-to-number (match-string 2 l)))
              (text (match-string 3 l)))
          (when (string-match lemmax--marker-re text)
            (dolist (id (lemmax--marker-ids (match-string 1 text)))
              (push (list id file line (and (lemmax--test-path-p file patterns) t)) res))))))
    (nreverse res)))

(defun lemmax--all-markers (infos &optional cached)
  "The markers of this repo and of every repo #+LEMMAX_MARKERS_IN: names."
  (let ((patterns (lemmax--test-paths infos)))
    (append (lemmax--markers patterns cached)
            (cl-loop for dir in (delete-dups (cl-mapcan (lambda (i) (copy-sequence (plist-get i :markers-in))) infos))
                     for full = (expand-file-name dir default-directory)
                     when (file-directory-p full)
                     append (let ((default-directory (file-name-as-directory full)))
                              (mapcar (lambda (m) (list (nth 0 m) (concat (directory-file-name dir) "/" (nth 1 m))
                                                        (nth 2 m) (nth 3 m)))
                                      (lemmax--markers patterns)))))))

(defun lemmax--lint-markers (infos only cached)
  "Markers that name no lemma or a DROPPED one; DONE lemmas from 2026-11-22 with no code marker."
  (let* ((known (make-hash-table :test #'equal))
         (markers (lemmax--all-markers infos cached))
         (reqs (lemmax--all-reqs infos)))
    (dolist (r (lemmax--all-reqs (lemmax--listed (if cached (lemmax--rev-files "") (lemmax--worktree-files)))))
      (when (plist-get r :id) (puthash (plist-get r :id) r known)))
    (dolist (m markers)
      (let ((r (gethash (nth 0 m) known)))
        (cond ((null r)
               (lemmax--finding (nth 1 m) (nth 2 m) (nth 0 m) "the marker names an id no lemma has"
                                "fix the id, or remove the marker"))
              ((equal (plist-get r :state) "DROPPED")
               (lemmax--finding (nth 1 m) (nth 2 m) (nth 0 m) "the marker names a DROPPED lemma"
                                "remove the marker, or the code it marks")))))
    (dolist (r reqs)
      (when (and (equal (plist-get r :state) "DONE")
                 (or (null only) (member (plist-get r :file) only))
                 (plist-get r :implemented) (not (string< (plist-get r :implemented) "2026-11-22"))
                 (not (cl-some (lambda (m) (and (equal (nth 0 m) (plist-get r :id)) (not (nth 3 m)))) markers)))
        (lemmax--finding (plist-get r :file) (plist-get r :line) (plist-get r :id)
                         "DONE with no code marker"
                         (format "put a comment line \"lemma: %s\" where it is built" (plist-get r :id)))))))

;;;; commit-msg (RT-7)

(defun lemmax--names-id-p (text id)
  (string-match-p (concat "\\(?:\\`\\|[^A-Za-z0-9_-]\\)" (regexp-quote id) "\\(?:\\'\\|[^A-Za-z0-9_-]\\)")
                  text))

(defun lemmax-commit-msg (args)
  (unless (= (length args) 1)
    (lemmax--err "lemmax: commit-msg takes one MSGFILE; see lemmax commit-msg --help")
    (kill-emacs 1))
  (let* ((msgfile (car args))
         (infos (lemmax--opted (lemmax--rev-files "")))
         (code (cl-mapcan (lambda (i) (copy-sequence (plist-get i :code))) infos))
         (paths (lemmax--lines (lemmax--git-out "diff" "--cached" "--name-only")))
         (touches (cl-some (lambda (p) (cl-some (lambda (c) (or (equal p c) (string-prefix-p (file-name-as-directory (directory-file-name c)) p)
                                                                  (and (string-suffix-p "/" c) (string-prefix-p c p))))
                                                  code))
                           paths)))
    (when touches
      (let* ((msg (string-join (cl-remove-if (lambda (l) (string-prefix-p "#" l))
                                             (split-string (with-temp-buffer (insert-file-contents msgfile) (buffer-string)) "\n"))
                               "\n"))
             (ids (delq nil (mapcar (lambda (r) (plist-get r :id)) (lemmax--all-reqs infos)))))
        (unless (cl-some (lambda (id) (lemmax--names-id-p msg id)) ids)
          (lemmax--finding msgfile 1 nil
                             (format "this commit changes code (%s) and names no requirement id" touches)
                             "name one in the message, as (RF-3)"))))
    (kill-emacs (if (> lemmax--findings 0) 1 0))))

;;;; trace (RT-8, RT-9)

(defun lemmax--commits ()
  "List of (HASH SHORT DATE SUBJECT BODY), newest first."
  (let ((out (lemmax--git-out "log" "--format=%H%x1f%h%x1f%cs%x1f%s%x1f%B%x1e")))
    (cl-loop for rec in (split-string (or out "") "\x1e" t)
             for f = (split-string (string-trim-left rec) "\x1f")
             when (>= (length f) 5) collect f)))

(defun lemmax--last-changes (infos)
  "Hash ID -> the last day its text changed in git, walking each file's revisions."
  (let ((changed (make-hash-table :test #'equal)))
    (dolist (info infos)
      (let ((file (plist-get info :file)) (prev (make-hash-table :test #'equal)))
        (dolist (line (lemmax--lines (lemmax--git-out "log" "--reverse" "--format=%H %cs" "--" file)))
          (let* ((parts (split-string line " ")) (rev (car parts)) (day (cadr parts))
                 (content (lemmax--git-out "show" (concat rev ":" file))))
            (when content
              (dolist (pair (lemmax--quick-ids content))
                (unless (equal (gethash (car pair) prev) (cdr pair))
                  (puthash (car pair) day changed)
                  (puthash (car pair) (cdr pair) prev))))))))
    changed))

(defun lemmax--suspects (reqs changed)
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

(defvar lemmax--marks nil "The markers of the repo being traced.")

(defun lemmax--block (r reqs addresses commits suspects one)
  (let* ((id (plist-get r :id))
         (children (cl-loop for c in reqs when (member id (plist-get c :needs)) collect (plist-get c :id))))
    (lemmax--out "%s %s %s" (or id "(no id)") (or (plist-get r :state) "-") (plist-get r :title))
    (lemmax--out "  file: %s:%d" (plist-get r :file) (plist-get r :line))
    (lemmax--out "  parents: %s" (if (plist-get r :needs) (string-join (plist-get r :needs) " ") "none"))
    (lemmax--out "  children: %s" (if children (string-join children " ") "none"))
    (if (plist-get r :verify)
        (dolist (a (plist-get r :verify))
          (lemmax--out "  verify: %s %s" a
                         (cond ((not (car addresses)) "unchecked")
                               ((member a (cdr addresses)) "found")
                               (t "missing"))))
      (lemmax--out "  verify: none"))
    (let ((here (cl-remove-if-not (lambda (m) (equal (nth 0 m) id)) lemmax--marks)))
      (if (null here)
          (lemmax--out "  code: none")
        (dolist (m (cl-remove-if (lambda (m) (nth 3 m)) here))
          (lemmax--out "  code: %s:%d" (nth 1 m) (nth 2 m)))
        (dolist (m (cl-remove-if-not (lambda (m) (nth 3 m)) here))
          (lemmax--out "  test: %s:%d" (nth 1 m) (nth 2 m)))))
    (let ((mine (and id (cl-remove-if-not (lambda (c) (lemmax--names-id-p (nth 4 c) id)) commits))))
      (if (null mine)
          (lemmax--out "  commits: none")
        (dolist (c mine)
          (lemmax--out "  commit: %s %s %s" (nth 1 c) (nth 2 c) (nth 3 c))
          (when one
            (dolist (f (lemmax--lines (lemmax--git-out "show" "--name-only" "--format=" (nth 0 c))))
              (lemmax--out "    %s" f))))))
    (dolist (s suspects)
      (when (equal (car s) id)
        (lemmax--out "  suspect: parent %s changed %s" (nth 1 s) (nth 2 s))))
    (when (and one (not (string-empty-p (or (plist-get r :body) ""))))
      (lemmax--out "  text:")
      (dolist (l (split-string (plist-get r :body) "\n"))
        (lemmax--out "    %s" l)))))

(defun lemmax--opted-here-p ()
  "Whether this repo has an opted-in file; a git grep, so no parse."
  (zerop (car (lemmax--git "grep" "--cached" "-q" "-E" "^#\\+LEMMAX_TESTS:" "--" "*.org"))))

(defun lemmax--projects-with (id)
  "Git roots under ~/repos, other than this one, whose opted-in files hold ID (RT-19)."
  (let ((here (and (lemmax--root) (file-truename default-directory))))
    (cl-loop for d in (lemmax--repos)
             unless (equal (file-truename d) here)
             when (let ((default-directory d))
                    (and (lemmax--opted-here-p)
                         (cl-some (lambda (r) (equal id (plist-get r :id)))
                                  (lemmax--all-reqs (lemmax--opted (lemmax--worktree-files))))))
             collect d)))

(defun lemmax-trace (args)
  (let* ((want (car args))
         (infos (and (lemmax--root) (lemmax--opted (lemmax--worktree-files)))))
    (when (and want (null lemmax--projects)
               (not (cl-some (lambda (r) (equal want (plist-get r :id))) (lemmax--all-reqs infos))))
      (let ((hits (lemmax--projects-with want)))
        (unless hits
          (lemmax--err "lemmax: unknown id %s, here or in any project under %s; lemmax list --all shows the ids"
                         want (abbreviate-file-name (expand-file-name (or (getenv "LEMMAX_REPOS") "~/repos"))))
          (kill-emacs 1))
        (dolist (d hits)
          (lemmax--out "project: %s" (abbreviate-file-name (directory-file-name d)))
          (let ((default-directory d))
            (lemmax--trace-in (lemmax--opted (lemmax--worktree-files)) want)))
        (kill-emacs 0)))
    (when (null infos)
      (lemmax--err "lemmax: no requirements file here has #+LEMMAX_TESTS:; name a project with -p DIR")
      (kill-emacs 0))
    (lemmax--trace-in infos want)
    (kill-emacs 0)))

(defun lemmax--trace-in (infos want)
  "Print the trace of INFOS, or of the one requirement WANT, for the repo here."
  (progn
    (let* ((reqs (lemmax--all-reqs infos))
           (lemmax--marks (lemmax--all-markers infos))
           (commits (lemmax--commits))
           (changed (lemmax--last-changes infos))
           (suspects (lemmax--suspects reqs changed))
           (addr-of (lambda (r) (lemmax--test-addresses
                                 (plist-get (cl-find (plist-get r :file) infos
                                                     :key (lambda (i) (plist-get i :file)) :test #'equal)
                                            :tests)))))
      (if want
          (let ((r (cl-find want reqs :key (lambda (x) (plist-get x :id)) :test #'equal)))
            (unless r
              (lemmax--err "lemmax: unknown id %s; lemmax list shows the ids" want)
              (kill-emacs 1))
            (lemmax--block r reqs (funcall addr-of r) commits suspects t))
        (dolist (r reqs)
          (lemmax--block r reqs (funcall addr-of r) commits suspects nil)
          (lemmax--out ""))
        (let* ((named (cl-mapcan (lambda (r) (copy-sequence (plist-get r :verify))) reqs))
               (orphans (cl-loop for info in infos
                                 for res = (lemmax--test-addresses (plist-get info :tests))
                                 when (car res)
                                 append (cl-remove-if (lambda (a) (member a named)) (cdr res)))))
          (lemmax--out "Orphan tests: %s" (if orphans "" "none"))
          (dolist (o (delete-dups orphans)) (lemmax--out "  %s" o)))
        (lemmax--out "Suspect: %s" (if suspects "" "none"))
        (dolist (s suspects)
          (lemmax--out "  %s: parent %s changed %s" (nth 0 s) (nth 1 s) (nth 2 s)))))))

;;;; list (RT-13)

(defun lemmax--group (r)
  (let ((state (plist-get r :state)))
    (cond ((equal state "DONE") "done")
          ((equal state "DROPPED") "dropped")
          ((plist-get r :approved) "approved")
          (t "waiting"))))

(defconst lemmax--group-names
  '(("waiting" . "Waiting for approval") ("approved" . "Approved and open")
    ("done" . "Done") ("dropped" . "Dropped")))

(defun lemmax--rows (no-tests)
  "Rows for every listed requirement of the repo here."
  (let* ((infos (lemmax--listed (lemmax--worktree-files)))
         (marks (lemmax--all-markers infos)))
    (cl-loop for info in infos
             for addr = (and (plist-get info :opted) (not no-tests)
                             (lemmax--test-addresses (plist-get info :tests)))
             append (cl-loop for r in (plist-get info :reqs)
                             collect (let ((v (plist-get r :verify)))
                                       (append r (list :group (lemmax--group r)
                                                       :markers (cl-loop for m in marks
                                                                         when (equal (nth 0 m) (plist-get r :id))
                                                                         collect m)
                                                       :check (cond ((null v) "none")
                                                                    ((not (car addr)) "named")
                                                                    ((cl-every (lambda (a) (member a (cdr addr))) v) "found")
                                                                    (t "missing")))))))))

(defun lemmax--filter (rows opts)
  (cl-remove-if-not
   (lambda (r)
     (and (or (null (plist-get opts :state))
              (equal (downcase (or (plist-get r :state) "")) (plist-get opts :state)))
          (or (null (plist-get opts :section))
              (and (plist-get r :id) (string-prefix-p (concat (plist-get opts :section) "-") (plist-get r :id))))
          (or (not (plist-get opts :unchecked))
              (and (equal (plist-get r :state) "DONE") (member (plist-get r :check) '("none" "missing"))))
          (or (not (plist-get opts :unmarked))
              (and (equal (plist-get r :state) "DONE")
                   (not (cl-some (lambda (m) (not (nth 3 m))) (plist-get r :markers)))))
          (or (not (plist-get opts :ready))
              (and (equal (plist-get r :state) "OPEN") (plist-get r :approved)))))
   rows))

(defun lemmax--trunc (s n) (if (> (length s) n) (concat (substring s 0 (1- n)) "…") s))

(defun lemmax--print-table (rows)
  (dolist (g lemmax--group-names)
    (let ((in (cl-remove-if-not (lambda (r) (equal (plist-get r :group) (car g))) rows)))
      (when in
        (lemmax--out "%s (%d)" (cdr g) (length in))
        (dolist (r in)
          (lemmax--out "  %-22s %-7s %-8s %-7s %-60s %s:%d  code:%d"
                         (or (plist-get r :id) "(no id)") (or (plist-get r :state) "-")
                         (if (plist-get r :approved) "approved" "-")
                         (plist-get r :check) (lemmax--trunc (plist-get r :title) 60)
                         (plist-get r :file) (plist-get r :line)
                         (cl-count-if-not (lambda (m) (nth 3 m)) (plist-get r :markers)))))))
  (let ((noid (cl-count-if (lambda (r) (null (plist-get r :id))) rows)))
    (when (> noid 0) (lemmax--out "No id: %d" noid))))

(defun lemmax--json-row (r repo)
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
            (cons 'line (plist-get r :line))
            (cons 'markers (vconcat (mapcar (lambda (m) (list (cons 'file (nth 1 m)) (cons 'line (nth 2 m))
                                                               (cons 'test (if (nth 3 m) t :false))))
                                            (plist-get r :markers)))))))

(defun lemmax--list-opts (args)
  (let (opts)
    (while args
      (let ((a (pop args)))
        (pcase a
          ("--state" (let ((v (pop args)))
                       (unless (member v '("open" "done" "dropped"))
                         (lemmax--err "lemmax: --state takes open, done or dropped") (kill-emacs 1))
                       (setq opts (plist-put opts :state v))))
          ("--section" (let ((v (pop args)))
                         (unless (and v (string-match-p "\\`[A-Z]+\\'" v))
                           (lemmax--err "lemmax: --section takes capital letters, as M") (kill-emacs 1))
                         (setq opts (plist-put opts :section v))))
          ("--unchecked" (setq opts (plist-put opts :unchecked t)))
          ("--unmarked" (setq opts (plist-put opts :unmarked t)))
          ("--ready" (setq opts (plist-put opts :ready t)))
          ("--all" (setq opts (plist-put opts :all t)))
          ("--json" (setq opts (plist-put opts :json t)))
          ("--no-tests" (setq opts (plist-put opts :no-tests t)))
          (_ (lemmax--err "lemmax: unknown option %s; see lemmax list --help" a) (kill-emacs 1)))))
    opts))

(defun lemmax--repos ()
  (let ((base (expand-file-name (or (getenv "LEMMAX_REPOS") "~/repos"))))
    (cl-loop for d in (directory-files base t "\\`[^.]")
             when (and (file-directory-p d) (file-exists-p (expand-file-name ".git" d)))
             collect (file-name-as-directory d))))

(defun lemmax-list (args)
  (let* ((opts (lemmax--list-opts args))
         (many (or (plist-get opts :all) lemmax--projects))
         (per (if many
                  (cl-loop for d in (delete-dups (append lemmax--projects
                                                         (and (plist-get opts :all) (lemmax--repos))))
                           for rows = (let ((default-directory d)) (lemmax--rows (plist-get opts :no-tests)))
                           when rows collect (cons (file-name-nondirectory (directory-file-name d)) rows))
                (list (cons nil (lemmax--rows (plist-get opts :no-tests)))))))
    (setq per (mapcar (lambda (p) (cons (car p) (lemmax--filter (cdr p) opts))) per))
    (when many (setq per (cl-remove-if-not #'cdr per)))
    (if (plist-get opts :json)
        (princ (concat (json-encode (vconcat (cl-loop for (repo . rows) in per
                                                       append (mapcar (lambda (r) (lemmax--json-row r repo)) rows))))
                       "\n"))
      (dolist (p per)
        (when (car p) (lemmax--out "== %s" (car p)))
        (lemmax--print-table (cdr p))
        (when (car p) (lemmax--out "")))
      (let ((all (cl-mapcan (lambda (p) (copy-sequence (cdr p))) per)))
        (lemmax--out "Total: %d requirement%s%s: %d open, %d done, %d dropped"
                       (length all) (if (= 1 (length all)) "" "s")
                       (if many (let ((n (length per))) (format " in %d repo%s" n (if (= n 1) "" "s"))) "")
                       (cl-count-if (lambda (r) (equal (plist-get r :state) "OPEN")) all)
                       (cl-count-if (lambda (r) (equal (plist-get r :state) "DONE")) all)
                       (cl-count-if (lambda (r) (equal (plist-get r :state) "DROPPED")) all))))
    (kill-emacs 0)))

;;;; new-id (01a1fe0c-9c5c-7057-8edc-bc68ccfa0490)

;; lemma: 01a1fe0c-9c5c-7057-8edc-bc68ccfa0490
(defun lemmax--random-bytes (n)
  "N bytes from /dev/urandom, as a list of integers."
  (with-temp-buffer
    (set-buffer-multibyte nil)
    (call-process "head" nil t nil "-c" (number-to-string n) "/dev/urandom")
    (append (buffer-string) nil)))

(defun lemmax-uuid7 ()
  "A new UUID v7 (RFC 9562): 48 bits of Unix time in ms, version 7,
74 random bits, variant 10, in lower case with hyphens."
  (let* ((ms (floor (* 1000 (float-time))))
         (ts (format "%012x" ms))
         (b (lemmax--random-bytes 10))
         (rand-a (logand (logior (ash (nth 0 b) 8) (nth 1 b)) #xfff))
         (variant (logior 8 (logand (nth 2 b) 3)))
         (rest (concat (format "%x" (logand (ash (nth 2 b) -4) #xf))
                       (mapconcat (lambda (x) (format "%02x" x)) (nthcdr 3 b) ""))))
    (format "%s-%s-7%03x-%x%s-%s"
            (substring ts 0 8) (substring ts 8 12) rand-a variant
            (substring rest 0 3) (substring rest 3 15))))

(defun lemmax-new-id (args)
  (when args
    (lemmax--err "lemmax: new-id takes no arguments; see lemmax new-id --help")
    (kill-emacs 1))
  (lemmax--out "%s" (lemmax-uuid7))
  (kill-emacs 0))

;;;; next-id (RT-14)

(defun lemmax-next-id (args)
  (let ((letter (car args)))
    (unless (and letter (= (length args) 1) (string-match-p "\\`[A-Z]+\\'" letter))
      (lemmax--err "lemmax: next-id takes one section letter, as M; see lemmax next-id --help")
      (kill-emacs 1))
    (let ((top 0) (re (concat "\\`" (regexp-quote letter) "-\\([0-9]+\\)\\'")))
      (dolist (r (lemmax--all-reqs (lemmax--listed (lemmax--worktree-files))))
        (let ((id (plist-get r :id)))
          (when (and id (string-match re id))
            (setq top (max top (string-to-number (match-string 1 id)))))))
      (lemmax--out "%s-%d" letter (1+ top))
      (kill-emacs 0))))

;;;; Help (RT-2)

(defconst lemmax--help
  '((main
     "usage: lemmax COMMAND [ARGS]
Lint, trace and list a repo's org requirements.
Commands: lint, commit-msg, trace, list, new-id, next-id, help
Run it inside a git repo, or name one with --project DIR (-p DIR).
It reads, and never writes a file.
example: lemmax list --ready -p ~/repos/arcadia_docs"
     "Commands:
  lint [--staged] [--no-tests] [FILE...]  refuse what requirements.org forbids
  commit-msg MSGFILE                      refuse a code commit that names no id
  trace [ID]                              each requirement's links, tests and commits
  list [filters] [--all] [--json]         every requirement in a table
  new-id                                  a new requirement id, a UUID v7
  next-id LETTER                          the next counted id, as M-15, for old projects
  help                                    this text
Each command takes -h, --help and help.
Each command takes --project DIR (-p DIR): run on the git repo that holds DIR,
instead of the one here. list takes it more than once: one table each.
lint, commit-msg and trace read files whose header has #+LEMMAX_TESTS:.
list and next-id read every requirements file: requirements.org, files under
a requirements/ folder, and files whose #+TODO names OPEN.
A finding is one line on stderr: lemmax: <file>:<line>: <id>: <why>; <fix>
Exit 0 when clean, 1 on any finding or failure.")
    (lint
     "usage: lemmax lint [--project DIR] [--staged] [--no-tests] [FILE...]
Refuse what requirements.org forbids, in files with #+LEMMAX_TESTS:.
example: lemmax lint --staged --no-tests"
     "--staged    read the staged copies and refuse changes against HEAD:
            a DONE requirement whose text changed, :LAST_EDITED: not today,
            a new requirement not dated today, a DONE one not :IMPLEMENTED: today
--no-tests  skip the test command and the :VERIFY: rule
FILE...     report findings for these files only
LEMMAX_TEST_SECONDS sets the test command's time (60 s); LEMMAX_TODAY sets today.")
    (commit-msg
     "usage: lemmax commit-msg [--project DIR] MSGFILE
Refuse a commit that changes code under #+LEMMAX_CODE: and names no requirement id.
example: lemmax commit-msg .git/COMMIT_EDITMSG"
     "The ids come from the staged requirements files, so one commit may add a
requirement and name it. Comment lines (#) do not count. An id matches as a
whole word: RF-3 is not RF-30.")
    (trace
     "usage: lemmax trace [--project DIR] [ID]
Print each requirement's parents, children, tests and commits.
example: lemmax trace RT-3"
     "With no ID: one block per requirement, then the orphan tests, which no
:VERIFY: names, then the suspect children: DONE requirements whose parent's
text changed in git after their :IMPLEMENTED: or :REVIEWED: day.
With an ID: that one block, and the files each of its commits touched.
An ID not in this project is looked for in every project under ~/repos,
and shown under a project: line.")
    (list
     "usage: lemmax list [--project DIR]... [--state open|done|dropped] [--section L] [--unchecked] [--unmarked] [--ready] [--all] [--json] [--no-tests]
Print every requirement in a table, grouped by state and approval.
example: lemmax list --section M --ready"
     "Columns: id, state, approved, check (found, missing, named, none), title, file:line, and
code:N, how many code markers name it.
Groups: waiting for approval, approved and open, done, dropped.
--state S     only that state
--section L   only ids that start with L-
--unchecked   DONE ones whose :VERIFY: is empty or names a test that is missing
--unmarked    DONE ones with no code marker: no comment line starting lemma: ID outside tests
--ready       approved and still OPEN
--project DIR the git repo that holds DIR; give it again for more, one table each
--all         every git repo under ~/repos (LEMMAX_REPOS sets the folder)
--json        the rows as a JSON array
--no-tests    skip the test command; the check column says named")
    (new-id
     "usage: lemmax new-id
Print a new requirement id: a UUID v7, lower case, as agent1's id rule asks.
example: lemmax new-id"
     "The first 12 hex digits are the time in milliseconds, so ids sort by age;
the rest is random from /dev/urandom. It needs no check against other ids.
next-id stays for projects whose old ids still count up.")
    (next-id
     "usage: lemmax next-id [--project DIR] LETTER
Print the next free id for a section: one more than the highest in use.
example: lemmax next-id M"
     "A gap is never filled, so an id is never reused. A letter with no id yet prints L-1.")))

(defun lemmax--help-for (cmd long)
  (let ((h (cdr (assq cmd lemmax--help))))
    (lemmax--out "%s" (car h))
    (when long (lemmax--out "\n%s" (cadr h)))
    (kill-emacs 0)))

;;;; Main

(defvar lemmax--projects nil "Git roots named by --project, in order.")

(defun lemmax--take-projects (args)
  "ARGS without --project DIR and -p DIR; each DIR's git root goes to `lemmax--projects'."
  (let (out)
    (while args
      (let ((a (pop args)))
        (if (not (member a '("--project" "-p")))
            (push a out)
          (let* ((dir (pop args))
                 (path (and dir (expand-file-name dir))))
            (unless (and path (file-directory-p path))
              (lemmax--err "lemmax: %s: no such folder" (or dir "--project needs a folder"))
              (kill-emacs 1))
            (let ((root (let ((default-directory (file-name-as-directory path))) (lemmax--root))))
              (unless root
                (lemmax--err "lemmax: %s: not inside a git repo" dir)
                (kill-emacs 1))
              (setq lemmax--projects (append lemmax--projects (list root))))))))
    (nreverse out)))

;; lemma: RT-2
(defun lemmax-main (args)
  (setq case-fold-search nil)
  (when (equal (car args) "--") (setq args (cdr args)))
  (let* ((cmd (car args))
         (rest (if (member cmd '(nil "-h" "--help" "help")) (cdr args) (lemmax--take-projects (cdr args)))))
    (when (and (cdr lemmax--projects) (not (equal cmd "list")))
      (lemmax--err "lemmax: %s takes one --project; list takes several" cmd)
      (kill-emacs 1))
    (cond
     ((or (null cmd) (member cmd '("-h" "--help"))) (lemmax--help-for 'main nil))
     ((equal cmd "help") (lemmax--help-for 'main t))
     ((not (assq (intern cmd) lemmax--help))
      (lemmax--err "lemmax: unknown command %s; see lemmax --help" cmd)
      (kill-emacs 1))
     ((member (car rest) '("-h" "--help")) (lemmax--help-for (intern cmd) nil))
     ((equal (car rest) "help") (lemmax--help-for (intern cmd) t))
     (t
      (let ((root (if (and lemmax--projects (not (equal cmd "list")))
                      (car lemmax--projects)
                    (lemmax--root))))
        (when (and (equal cmd "list") lemmax--projects (not root))
          (setq root default-directory))
        (unless (or root (equal cmd "list") (and (equal cmd "trace") rest))
          (lemmax--err "lemmax: not inside a git repo") (kill-emacs 1))
        (let ((default-directory (or root default-directory)))
          (if (and (null root) (not (member "--all" rest)) (null lemmax--projects)
                   (not (and (equal cmd "trace") rest)))
              (progn (lemmax--err "lemmax: not inside a git repo; use --all") (kill-emacs 1))
            (pcase cmd
              ("lint" (lemmax-lint rest))
              ("commit-msg" (lemmax-commit-msg rest))
              ("trace" (lemmax-trace rest))
              ("list" (lemmax-list rest))
              ("new-id" (lemmax-new-id rest))
              ("next-id" (lemmax-next-id rest))
              (_ (lemmax--help-for 'main nil))))))))))

(when noninteractive
  (condition-case err
      (lemmax-main (prog1 command-line-args-left (setq command-line-args-left nil)))
    (error (lemmax--err "lemmax: %s" (error-message-string err)) (kill-emacs 1))))

;;; lemmax.el ends here
