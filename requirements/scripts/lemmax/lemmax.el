;;; lemmax.el --- lint, trace and list org requirements  -*- lexical-binding: t; -*-

;; Run through the launcher: requirements/scripts/lemmax/lemmax COMMAND ...
;; Requirements: requirements/scripts/lemmax/requirements.org (RT-1 to RT-15).
;; It reads files and git, and writes no file but the two hooks install-hooks puts in place.

;; lemma: 01a202f3-85a4-76cd-bf13-05f6e723c5b2
;; The floor is Emacs 29 with its Org 9.6; checked before anything else loads.
(when (< emacs-major-version 29)
  (message "lemmax: needs Emacs 29 or newer; found %s" emacs-version)
  (kill-emacs 2))

;; lemma: RT-1
(require 'org)
(require 'org-element)
(require 'subr-x)
(require 'cl-lib)
(require 'json)
(require 'time-date)

;; lemma: 01a20336-c80d-733a-a251-ad26a0ebf7d3
(defconst lemmax-version "1.0.0" "lemmax's release, semver; CHANGELOG.md names each.")

;; lemma: 01a20369-38d2-7202-8b53-6e296aaac489
;; lemma: 01a2038d-cc5f-7324-8de8-1b067284e640 01a2038d-cc86-72be-b225-eeff9ee2c7a6
(defconst lemmax-states '("OPEN" "DONE" "DROPPED" "CONJECTURE" "LEMMA" "THEOREM" "REFUTED" "PASSED"
                          "TODO" "CANCELLED" "AXIOM")
  "Every state: the old three, a conjecture's four, a proof's PASSED, a task's and AXIOM.")
(defun lemmax--done-p (s) "Whether S is proven: DONE, LEMMA or THEOREM." (and (member s '("DONE" "LEMMA" "THEOREM")) t))
(defun lemmax--open-p (s) "Whether S is not yet proven: OPEN or CONJECTURE." (and (member s '("OPEN" "CONJECTURE")) t))
(defun lemmax--dropped-p (s) "Whether S is given up: DROPPED or REFUTED." (and (member s '("DROPPED" "REFUTED")) t))
(defun lemmax--new-state-p (s) "Whether S is one of the math names of a conjecture."
  (and (member s '("CONJECTURE" "LEMMA" "THEOREM" "REFUTED")) t))
(defun lemmax--proofs-file-p (file) (string-suffix-p ".proofs.org" (or file "")))
;; lemma: 01a2038d-cc5f-7324-8de8-1b067284e640 01a2038d-cc73-7594-9dd3-d758bee5aadc 01a2038d-cc86-72be-b225-eeff9ee2c7a6
(defun lemmax--task-p (r) "Whether R is a task: it lives in a .tasks.org file."
  (string-suffix-p ".tasks.org" (or (plist-get r :file) "")))
(defun lemmax--note-p (r) "Whether R is a note: it lives in a .notes.org file."
  (string-suffix-p ".notes.org" (or (plist-get r :file) "")))
(defun lemmax--axiom-p (r) "Whether R is an axiom." (equal (plist-get r :state) "AXIOM"))
(defun lemmax--unproven-p (r) "Whether R needs no proof: a task, a note or an axiom."
  (or (lemmax--task-p r) (lemmax--note-p r) (lemmax--axiom-p r)))
(defun lemmax--proof-p (r) "Whether R is a proof: it has :PROVES:, or lives in a proofs file."
  (and (or (plist-get r :proves) (lemmax--proofs-file-p (plist-get r :file))) t))
(defconst lemmax-dates '("CREATED" "LAST_EDITED" "APPROVED" "IMPLEMENTED" "REVIEWED"))
(defvar lemmax--findings 0)
;; lemma: 01a202f3-834a-7fcc-9a94-a50f2d1ab85c
(defvar lemmax--run-tests nil
  "Whether list and trace run a repo's test command: only with --run-tests,
since the command is the repo's own code.")
(defvar lemmax--tests-cache (make-hash-table :test #'equal))

;;;; Output

(defun lemmax--out (fmt &rest args)
  (princ (apply #'format fmt args))
  (princ "\n"))

(defun lemmax--err (fmt &rest args)
  (message "%s" (apply #'format fmt args)))

(defun lemmax--finding (file line id why fix)
  "One finding line on stderr (RT-2).
LEMMAX_MUTATE=TEXT drops every finding whose WHY holds TEXT: the mutation
test turns each rule off so, to show a test fails without it."
  ;; lemma: 01a202f3-8822-7602-98a4-67acc268e3b0
  (unless (let ((m (getenv "LEMMAX_MUTATE"))) (and m (string-match-p (regexp-quote m) why)))
    (lemmax--finding-1 file line id why fix)))

;; lemma: 01a20336-ca8d-75bf-bedc-33da69c29468
(defvar lemmax--json-findings nil
  "With lint --json, the findings so far, newest first; else t is never set.")
(defvar lemmax--json-mode nil "Whether lint prints its findings as JSON.")

(defun lemmax--finding-1 (file line id why fix)
  (setq lemmax--findings (1+ lemmax--findings))
  (if lemmax--json-mode
      (push (list (cons 'file file) (cons 'line line) (cons 'id (or id :null)) (cons 'why why) (cons 'fix fix))
            lemmax--json-findings)
    ;; The stable line: lemmax: FILE:LINE: ID: WHY; FIX
    (lemmax--err "lemmax: %s:%s: %s: %s; %s" file line (or id "-") why fix)))

;;;; Git

(defun lemmax--git (&rest args)
  "Run git with ARGS in `default-directory'; (EXIT . OUTPUT).
Git's local dates are UTC, the one clock of lemmax."
  (with-temp-buffer
    (let* ((process-environment (cons "TZ=UTC0" process-environment))
           (code (apply #'call-process "git" nil (list t nil) nil args)))
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
  "The text of an entry from RAW, its heading line to the next heading, in one
form for heading and file lemmas: the title (priority and tags kept, no stars,
state or leading id), the drawer's properties but :STATE: and the 5 dates, one
space after each key, and the trimmed body without #+title:."
  (let* ((lines (split-string raw "\n"))
         (head (replace-regexp-in-string
                (concat "\\`\\*+ +\\(?:" (regexp-opt lemmax-states) "\\_>\\)? *") "" (car lines)))
         ;; lemma: 01a2002a-bf93-7475-94c3-d083c65a87d6
         (head (replace-regexp-in-string "\\`\\(\\[#.\\] +\\)?[A-Z]+-[0-9]+ " "\\1" head))
         ;; lemma: 01a2039c-9e67-74bb-9ac4-63eac14f1e7c
         ;; Tags are not the text.
         (head (replace-regexp-in-string "[ \t]+:[[:alnum:]_@#%:]+:[ \t]*\\'" "" head))
         ;; lemma: 01a20369-38d2-7202-8b53-6e296aaac489
         ;; A proof is not the statement, nor are links: :VERIFY:, :NEEDS: and :USES: are not the text.
         (skip-re (concat "\\`[ \t]*:" (regexp-opt (append '("STATE" "VERIFY" "VERIFY+" "NEEDS" "USES") lemmax-dates)) ":"))
         (in nil) props body)
    ;; lemma: 01a202f3-8216-7a1e-a34c-80c99d7bbf02
    (dolist (l (cdr lines))
      (cond ((string-match-p "\\`[ \t]*:PROPERTIES:[ \t]*\\'" l) (setq in t))
            ((and in (string-match-p "\\`[ \t]*:END:[ \t]*\\'" l)) (setq in nil))
            (in (unless (string-match-p skip-re l)
                  (push (if (string-match "\\`[ \t]*\\(:[^: \t]+:\\)[ \t]*\\(.*?\\)[ \t]*\\'" l)
                            (concat (match-string 1 l) " " (match-string 2 l))
                          (string-trim l))
                        props)))
            ((string-match-p "\\`#\\+[Tt][Ii][Tt][Ll][Ee]:" l))
            (t (push l body))))
    (replace-regexp-in-string
     ;; lemma: 01a202bc-49e2-7dba-94f5-0c0952fc91f0
     ;; The text an id: link shows is not the lemma's text.
     "\\[\\[id:\\([^]\n]+\\)\\]\\[[^]\n]*\\]\\]" "[[id:\\1]]"
     (replace-regexp-in-string
      ;; A link to a heading that starts with an id holds the same text without it.
      "\\(\\[\\[\\(?:[^]\n]*::\\)?\\*\\)[A-Z]+-[0-9]+ " "\\1"
      (concat (string-trim head) "\n" (string-join (nreverse props) "\n") "\n"
              (string-trim (string-join (nreverse body) "\n")))))))

;; lemma: RT-17
(defun lemmax--entry-body (raw)
  "The body of an entry from RAW: its lines after the heading, without the
property drawer, trimmed (RT-17)."
  (let ((lines (cdr (split-string raw "\n"))) (in nil) out)
    (dolist (l lines)
      (cond ((string-match-p "\\`[ \t]*:PROPERTIES:[ \t]*\\'" l) (setq in t))
            ((and in (string-match-p "\\`[ \t]*:END:[ \t]*\\'" l)) (setq in nil))
            ;; A file lemma's #+title: is its title, not its body.
            ((string-match-p "\\`#\\+[Tt][Ii][Tt][Ll][Ee]:" l))
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

;; lemma: 01a202f3-83dc-76e8-b198-68db19d1e4cd
(defvar lemmax--entry-cache (make-hash-table :test #'equal)
  "Entry text -> its (ID . TEXT) pairs, for the history walk of one run.")

;; lemma: 01a202f3-88bb-704d-9ea9-74714f841514
(defun lemmax--quick-ids (content)
  "Alist (ID . TEXT) for each lemma of CONTENT with an :ID: (RT-9), read by
`lemmax--parse', so the history walk and lint never disagree on a lemma.
A heading lemma's record depends on its entry alone, so each entry is parsed
once a run, however many revisions hold it."
  (let ((pairs (lambda (text)
                 (or (gethash text lemmax--entry-cache)
                     (puthash text
                              (cl-loop for r in (plist-get (lemmax--parse text "") :reqs)
                                       when (plist-get r :id)
                                       collect (cons (plist-get r :id) (plist-get r :text)))
                              lemmax--entry-cache)))))
    (if (string-match-p "\\`\\(?:#[ \t].*\n\\|#\n\\|[ \t]*\n\\)*[ \t]*:PROPERTIES:" content)
        (funcall pairs content)
      (cl-mapcan (lambda (e) (copy-sequence (funcall pairs e))) (lemmax--split-headings content)))))

;; lemma: 01a203a6-a702-71c0-8239-e0d41380d2dd
(defun lemmax--id-list (v)
  "The ids of V, a link property's value: [[id:X]] and [[id:X][label]] links,
then the bare words left."
  (when v
    (let ((ids nil) (pos 0))
      (while (string-match "\\[\\[id:\\([^]\n]+\\)\\]\\(?:\\[[^]\n]*\\]\\)?\\]" v pos)
        (push (string-trim (match-string 1 v)) ids)
        (setq pos (match-end 0)))
      (append (nreverse ids)
              (split-string (replace-regexp-in-string "\\[\\[id:[^]\n]+\\]\\(?:\\[[^]\n]*\\]\\)?\\]" " " v))))))

(defun lemmax--record (get id state title file line end raw &optional tags-own tags before)
  "A lemma's plist; GET reads one of its properties, RAW is its text;
TAGS-OWN its own tags, TAGS those with the inherited and file tags."
  (list :id id :state state :title title :file file :line line :end end
        :tags-own tags-own :tags tags
        ;; lemma: 01a203a6-a716-738e-a95b-18086050d5eb
        :before before
        :blocker (let ((v (funcall get "BLOCKER"))) (and v (lemmax--id-list v)))
        :created (funcall get "CREATED")
        :last-edited (funcall get "LAST_EDITED")
        :approved (funcall get "APPROVED")
        :implemented (funcall get "IMPLEMENTED")
        :reviewed (funcall get "REVIEWED")
        ;; lemma: 01a20369-38d2-7202-8b53-6e296aaac489
        :needs (append (lemmax--id-list (funcall get "NEEDS")) (lemmax--id-list (funcall get "USES")))
        :proves (lemmax--id-list (funcall get "PROVES"))
        :for (lemmax--id-list (funcall get "FOR"))
        :about (lemmax--id-list (funcall get "ABOUT"))
        :follows (lemmax--id-list (funcall get "FOLLOWS"))
        :own-verify (and (funcall get "VERIFY") t)
        ;; lemma: 01a202bc-4bf0-7fd3-a92c-204eb9fa96f0
        :aliases (let ((v (funcall get "ALIASES"))) (and v (split-string v)))
        ;; lemma: 01a202bc-4cc4-753e-8d51-12d8327dfd9c
        :refs (let ((v (funcall get "REFS"))) (and v (split-string v)))
        :verify (let ((v (or (funcall get "VERIFY") (funcall get "TEST")))) (and v (split-string-and-unquote v)))
        :text (lemmax--entry-text raw)
        :body (lemmax--entry-body raw)))

(defun lemmax--parse (content file)
  "Parse org CONTENT named FILE: plist (:file :keywords :opted :listed :reqs).
A UTF-8 BOM and CRLF line ends are read as the plain form."
  ;; lemma: 01a202f3-8964-7333-8165-dba3d86556b5
  (setq content (replace-regexp-in-string "\r$" "" (string-remove-prefix "\ufeff" content)))
  (with-temp-buffer
    (insert content)
    (let ((org-todo-keywords '((sequence "OPEN" "CONJECTURE" "TODO" "|" "DONE" "DROPPED" "LEMMA" "THEOREM" "REFUTED" "PASSED"
                                         "CANCELLED" "AXIOM")))
          (org-element-use-cache nil)
          (org-inhibit-startup t))
      (delay-mode-hooks (org-mode))
      (let* ((kw (org-collect-keywords '("LEMMAX_TESTS" "LEMMAX_CODE" "LEMMAX_TEST_PATHS" "LEMMAX_MARKERS_IN" "TODO"
                                         ;; The names before lemmax, read so older commits still match.
                                         "REQTRACE_TESTS" "REQTRACE_CODE")))
             (todo (cadr (assoc "TODO" kw)))
             ;; lemma: 01a202bc-4a88-7993-a717-e8022392b801
             ;; lemma: 01a202f3-8475-7f4f-b0e2-5cd8c782e520
             ;; Org's own reading: a drawer is the file's only when it comes
             ;; first, after comment lines at most.
             (one (save-excursion (goto-char (point-min))
                                  (and (not (org-at-heading-p))
                                       (let ((v (org-entry-get nil "ID"))) (and v (string-trim v))))))
             (pre (if (string-match "^\\*+ " content) (substring content 0 (match-beginning 0)) content))
             (misplaced (and (not one)
                             (string-match "^[ \t]*:PROPERTIES:[ \t]*\n\\(?:.*\n\\)*?[ \t]*:ID:" pre)
                             (1+ (cl-count ?\n (substring pre 0 (match-beginning 0))))))
             reqs)
        (if one
            (let ((get (lambda (p) (let ((v (save-excursion (goto-char (point-min)) (org-entry-get nil p))))
                                     (and v (not (string-empty-p (string-trim v))) (string-trim v)))))
                  (title (string-trim (or (cadr (assoc "TITLE" (org-collect-keywords '("TITLE")))) ""))))
              (push (lemmax--record get one (let ((st (funcall get "STATE"))) (and (member st lemmax-states) st))
                                    title file 1 (count-lines (point-min) (point-max))
                                    (concat "* " title "\n" content)
                                    nil (mapcar #'substring-no-properties org-file-tags))
                    reqs))
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
                 (push (lemmax--record get (and id (string-trim id)) (and (member state lemmax-states) state)
                                       (org-get-heading t t t t) file (line-number-at-pos beg)
                                       (save-excursion (goto-char end) (if (bolp) (max (line-number-at-pos beg) (1- (line-number-at-pos end))) (line-number-at-pos end)))
                                       (buffer-substring-no-properties beg end)
                                       ;; lemma: 01a2039c-9e67-74bb-9ac4-63eac14f1e7c
                                       (mapcar #'substring-no-properties (org-get-tags nil t))
                                       (let ((org-use-tag-inheritance t))
                                         (delete-dups (mapcar #'substring-no-properties (org-get-tags))))
                                       (lemmax--ordered-before))
                       reqs)))))))
        (let* ((tests-kw (or (assoc "LEMMAX_TESTS" kw) (assoc "REQTRACE_TESTS" kw)))
               (code-kw (or (assoc "LEMMAX_CODE" kw) (assoc "REQTRACE_CODE" kw)))
               (opted (and tests-kw t)))
          (list :file file
                :misplaced misplaced
                ;; lemma: 01a2039c-9e67-74bb-9ac4-63eac14f1e7c
                :declared (cl-loop for e in org-current-tag-alist
                                   when (stringp (car-safe e)) collect (substring-no-properties (car e)))
                :file-tags (mapcar #'substring-no-properties org-file-tags)
                :tag-groups (mapcar (lambda (g) (mapcar #'substring-no-properties g))
                                    (org-tag-alist-to-groups org-current-tag-alist))
                :keywords kw
                :opted opted
                :tests (cadr tests-kw)
                :code (let ((c (cadr code-kw))) (and c (split-string c)))
                :test-paths (let ((c (cadr (assoc "LEMMAX_TEST_PATHS" kw)))) (and c (split-string c)))
                :markers-in (let ((c (cadr (assoc "LEMMAX_MARKERS_IN" kw)))) (and c (split-string c)))
                :listed (or opted
                            (equal (file-name-nondirectory file) "requirements.org")
                            (member "requirements" (split-string (or (file-name-directory file) "") "/" t))
                            (and todo (string-match-p "\\_<\\(?:OPEN\\|CONJECTURE\\)\\_>" todo) t))
                :reqs (nreverse reqs)))))))

;; lemma: 01a203a6-a716-738e-a95b-18086050d5eb
(defun lemmax--ordered-before ()
  "At a heading whose parent has :ORDERED: t, its earlier siblings as (ID . STATE)."
  (save-excursion
    (when (and (save-excursion (and (org-up-heading-safe)
                                    (let ((v (org-entry-get nil "ORDERED"))) (and v (not (member v '("nil" "")))))))
               t)
      (let (out)
        (while (org-get-last-sibling)
          (push (cons (let ((v (org-entry-get nil "ID"))) (and v (string-trim v))) (org-get-todo-state)) out))
        out))))

;;;; Config (01a202b0-1d09-75f3-99dc-677a4b2ec0be)

;; lemma: 01a202b0-1d09-75f3-99dc-677a4b2ec0be
(defconst lemmax-config-file "lemmax/config.eld")
(defconst lemmax--config-keys '(:tests :code :test-paths :markers-in))

(defun lemmax--config-text (rev)
  "The config's text: from the work tree when REV is nil, else at REV
\(\"\" for the index, \"HEAD\" for HEAD); nil when there is none."
  (if rev
      (lemmax--git-out "show" (concat rev ":" lemmax-config-file))
    (and (file-readable-p lemmax-config-file)
         (with-temp-buffer (insert-file-contents lemmax-config-file) (buffer-string)))))

(defun lemmax--config-read (text)
  "Read TEXT, the config, as data: (FOLDERS . PROBLEMS).
FOLDERS is a list of (FOLDER . PLIST), FOLDER ending in / or \"\" for the root.
It is read with `read' and `read-eval' off, so nothing in it ever runs."
  (let (data problems folders)
    (condition-case err
        (let ((read-eval nil))
          (setq data (car (read-from-string text)))
          (let ((rest (string-trim (substring text (cdr (read-from-string text))))))
            (unless (or (string-empty-p rest) (string-prefix-p ";" rest))
              (push "more than one form; the config is one (:folders ...) list" problems))))
      (error (push (format "it does not read: %s" (error-message-string err)) problems)
             (setq data nil)))
    (when (and data (not problems))
      (if (not (and (listp data) (cl-evenp (length data)) (keywordp (car data))))
          (push "it is not a (:folders ...) list" problems)
        ;; lemma: 01a20336-c611-73c8-bb70-4a8e70e675d1
        (cl-loop for (k v) on data by #'cddr
                 do (pcase k
                      (:folders nil)
                      (:markers-required-from
                       (unless (and (stringp v) (lemmax--day-p v))
                         (push ":markers-required-from is not a day, YYYY-MM-DD" problems)))
                      (:repos (unless (stringp v) (push ":repos is not a folder name" problems)))
                      (_ (push (format "unknown key %S" k) problems))))
        (dolist (e (plist-get data :folders))
          (if (not (and (consp e) (stringp (car e)) (cl-evenp (length (cdr e)))))
              (push (format "a folder entry is not (\"FOLDER\" :key value ...): %S" e) problems)
            (let ((folder (string-remove-prefix "./" (car e))) (plist (cdr e)) ok)
              (setq folder (if (member folder '("" ".")) "" (file-name-as-directory folder)))
              (setq ok t)
              (cl-loop for (k v) on plist by #'cddr
                       do (cond ((not (memq k lemmax--config-keys))
                                 (setq ok nil)
                                 (push (format "%s: unknown key %S" (car e) k) problems))
                                ((eq k :tests)
                                 (cond ((not (stringp v))
                                        (setq ok nil)
                                        (push (format "%s: :tests is not a string" (car e)) problems))
                                       ;; lemma: 01a20336-cbc7-70a7-9473-18325683fba6
                                       ((string-empty-p (string-trim v))
                                        (setq ok nil)
                                        (push (format "%s: :tests is empty; name the command that lists test addresses" (car e))
                                              problems))))
                                ((not (and (listp v) (cl-every #'stringp v)))
                                 (setq ok nil)
                                 (push (format "%s: %S is not a list of strings" (car e) k) problems))))
              (when ok (push (cons folder plist) folders)))))))
    (cons (nreverse folders) (nreverse problems))))

(defun lemmax--config-setting (key)
  "The top-level setting KEY of the work tree's config, or nil."
  (let ((text (lemmax--config-text nil)))
    (and text (null (cdr (lemmax--config-read text)))
         (let ((read-eval nil)) (plist-get (car (read-from-string text)) key)))))

(defun lemmax--config (rev)
  "The config's folder entries at REV (see `lemmax--config-text'); nil when none."
  (let ((text (lemmax--config-text rev)))
    (and text (car (lemmax--config-read text)))))

(defun lemmax--own-settings-p (info)
  "Whether INFO's file has any #+LEMMAX_* (or older #+REQTRACE_*) line."
  (cl-some (lambda (k) (string-match-p "\\`\\(?:LEMMAX\\|REQTRACE\\)_" (car k)))
           (plist-get info :keywords)))

(defun lemmax--apply-config (infos folders)
  "INFOS, each file with no header of its own taking the entry of FOLDERS
whose folder is the longest that holds it."
  (mapcar
   (lambda (info)
     (let* ((file (plist-get info :file))
            (best (and folders (not (lemmax--own-settings-p info))
                       (car (sort (cl-remove-if-not (lambda (f) (string-prefix-p (car f) file))
                                                    (copy-sequence folders))
                                  (lambda (a b) (> (length (car a)) (length (car b)))))))))
       (if (not best)
           info
         (let ((s (cdr best)) (out (copy-sequence info)))
           (setq out (plist-put out :tests (plist-get s :tests)))
           (setq out (plist-put out :opted (and (plist-get s :tests) t)))
           (setq out (plist-put out :code (plist-get s :code)))
           (setq out (plist-put out :test-paths (plist-get s :test-paths)))
           (setq out (plist-put out :markers-in (plist-get s :markers-in)))
           (plist-put out :listed t)))))
   infos))

(defun lemmax--lint-config (staged)
  "Findings for the config itself: one that does not read, an unknown key,
a FOLDER that holds no tracked file."
  (let ((text (lemmax--config-text (and staged ""))))
    (when text
      (let ((res (lemmax--config-read text))
            (tracked (lemmax--lines (lemmax--git-out "ls-files"))))
        (dolist (p (cdr res))
          (lemmax--finding lemmax-config-file 1 nil p "see lemmax help for the config's form"))
        (dolist (f (car res))
          (unless (or (string-empty-p (car f))
                      (cl-some (lambda (p) (string-prefix-p (car f) p)) tracked))
            (lemmax--finding lemmax-config-file 1 nil
                             (format "the folder %s holds no tracked file" (car f))
                             "fix the folder, or remove its entry"))
          (dolist (c (plist-get (cdr f) :code))
            (unless (cl-some (lambda (p) (or (equal p c) (string-prefix-p (file-name-as-directory (directory-file-name c)) p)))
                             tracked)
              (lemmax--finding lemmax-config-file 1 nil
                               (format "%s: :code names %s, which holds no tracked file" (car f) c)
                               "fix the path, or remove it")))
          (dolist (tp (plist-get (cdr f) :test-paths))
            (unless (cl-some (lambda (p) (string-search tp p)) tracked)
              (lemmax--finding lemmax-config-file 1 nil
                               (format "%s: :test-paths names %s, which no tracked file matches" (car f) tp)
                               "fix the pattern, or remove it"))))))))

;; lemma: 01a20336-c4d6-73d3-a429-0a755d277123
(defconst lemmax--candidate-re
  "^(\\*+ +(OPEN|DONE|DROPPED|CONJECTURE|LEMMA|THEOREM|REFUTED|PASSED|AXIOM)\\b|[ \t]*:STATE:[ \t]+(OPEN|DONE|DROPPED|CONJECTURE|LEMMA|THEOREM|REFUTED)\\b|#\\+(LEMMAX|REQTRACE)_|#\\+TODO:.*\\b(OPEN|CONJECTURE)\\b)"
  "A line only a file that may hold lemmas has, for git grep -E.")

(defvar lemmax--files-cache (make-hash-table :test #'equal)
  "(REPO . REV), REV nil for the work tree -> its parsed infos, once a run.")

;; lemma: RT-3
(defun lemmax--candidates (rev)
  "The .org files at REV that may hold lemmas: requirements files by name or
folder, files under a config folder, and files git grep finds a state, a
lemmax keyword or an OPEN #+TODO: in. No other .org file is read."
  (let* ((all (lemmax--lines (cond ((null rev) (lemmax--git-out "ls-files" "*.org"))
                                   ((string-empty-p rev) (lemmax--git-out "ls-files" "*.org"))
                                   (t (mapconcat #'identity
                                                 (cl-remove-if-not (lambda (f) (string-suffix-p ".org" f))
                                                                   (lemmax--lines (lemmax--git-out "ls-tree" "-r" "--name-only" rev)))
                                                 "\n")))))
         (folders (mapcar #'car (lemmax--config rev)))
         (hits (mapcar (lambda (l) (if (and rev (not (string-empty-p rev))) (string-remove-prefix (concat rev ":") l) l))
                       (lemmax--lines (apply #'lemmax--git-out
                                             (append '("grep" "-l" "-I" "-E")
                                                     (cond ((null rev) nil) ((string-empty-p rev) '("--cached")))
                                                     (list lemmax--candidate-re)
                                                     (and rev (not (string-empty-p rev)) (list rev))
                                                     '("--" "*.org")))))))
    (cl-remove-if-not
     (lambda (f) (or (member f hits)
                     (string-suffix-p ".tasks.org" f) (string-suffix-p ".notes.org" f)
                     (equal (file-name-nondirectory f) "requirements.org")
                     (member "requirements" (split-string (or (file-name-directory f) "") "/" t))
                     (cl-some (lambda (d) (string-prefix-p d f)) folders)))
     all)))

(defun lemmax--worktree-files ()
  "Parsed infos of the repo's candidate .org files, from the work tree; once a run."
  (or (gethash (cons default-directory nil) lemmax--files-cache)
      (puthash (cons default-directory nil)
               (lemmax--apply-config
                (cl-loop for f in (lemmax--candidates nil)
                         when (file-readable-p f)
                         collect (lemmax--parse (with-temp-buffer (insert-file-contents f) (buffer-string)) f))
                (lemmax--config nil))
               lemmax--files-cache)))

(defun lemmax--rev-files (rev)
  "Parsed infos of the candidate .org files at REV: \"\" for the index, \"HEAD\"
for HEAD; read by one git process, once a run."
  (or (gethash (cons default-directory rev) lemmax--files-cache)
      (puthash (cons default-directory rev)
               (let ((names (lemmax--candidates rev)))
                 (lemmax--apply-config
                  (cl-loop for f in names
                           for b in (lemmax--blobs (mapcar (lambda (f) (concat rev ":" f)) names))
                           when b collect (lemmax--parse (cdr b) f))
                  (lemmax--config rev)))
               lemmax--files-cache)))

(defun lemmax--opted (infos) (cl-remove-if-not (lambda (i) (plist-get i :opted)) infos))
(defun lemmax--listed (infos) (cl-remove-if-not (lambda (i) (plist-get i :listed)) infos))
(defun lemmax--all-reqs (infos)
  "Every lemma of INFOS, its :NEEDS: naming each parent by its :ID:, never an alias;
each conjecture with :proofs, its proofs' (ID . STATE), and their tests as :verify."
  (lemmax--attach-proofs (lemmax--canon-reqs infos)))

;; lemma: 01a20369-38d2-7202-8b53-6e296aaac489
(defun lemmax--attach-proofs (reqs)
  "REQS, each conjecture that a proof names given :proofs and, with no :VERIFY:
of its own, the :TEST: addresses of its proofs as :verify."
  (let ((by (make-hash-table :test #'equal)))
    (dolist (r reqs)
      (when (lemmax--proof-p r)
        (dolist (id (plist-get r :proves)) (push r (gethash id by)))))
    (if (zerop (hash-table-count by))
        reqs
      (mapcar (lambda (r)
                (let ((ps (and (plist-get r :id) (not (lemmax--proof-p r)) (reverse (gethash (plist-get r :id) by)))))
                  (if (null ps)
                      r
                    (let ((out (plist-put (copy-sequence r) :proofs
                                          (mapcar (lambda (p) (cons (plist-get p :id) (plist-get p :state))) ps))))
                      (if (plist-get r :own-verify)
                          out
                        (plist-put out :verify (delete-dups (cl-mapcan (lambda (p) (copy-sequence (plist-get p :verify))) ps))))))))
              reqs))))

(defun lemmax--canon-reqs (infos)
  "Every lemma of INFOS, :NEEDS: and :PROVES: naming each id by its :ID:, never an alias."
  (let* ((reqs (cl-mapcan (lambda (i) (copy-sequence (plist-get i :reqs))) infos))
         (canon (make-hash-table :test #'equal)))
    (dolist (r reqs)
      (dolist (a (plist-get r :aliases)) (puthash a (plist-get r :id) canon)))
    (if (zerop (hash-table-count canon))
        reqs
      (mapcar (lambda (r)
                (let ((fix (lambda (ids) (mapcar (lambda (n) (or (and (not (cl-find n reqs :key (lambda (x) (plist-get x :id)) :test #'equal))
                                                                      (gethash n canon))
                                                                 n))
                                                 ids)))
                      (out r))
                  (when (plist-get r :needs)
                    (setq out (plist-put (copy-sequence out) :needs (funcall fix (plist-get r :needs)))))
                  (when (plist-get r :proves)
                    (setq out (plist-put (copy-sequence out) :proves (funcall fix (plist-get r :proves)))))
                  out))
              reqs))))

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
                                  ;; No sentinel: the default one writes "Process ... finished"
                                  ;; into the output, read as a test address.
                                  :sentinel #'ignore
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
  ;; lemma: 01a202f3-850b-7e3f-93f9-655397189d53
  (or (getenv "LEMMAX_TODAY") (format-time-string "%F" nil t)))

;;;; lint (RT-4, RT-5, RT-6)

(defun lemmax--uuid7-p (id)
  "Whether ID is a lower-case UUID v7, the id lemmax new-id makes."
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
          (cond ((null id) (lemmax--finding f l nil "no :ID:" "add :ID:, as RQ-1 or a UUID v7 from lemmax new-id"))
                ((string-match-p "[ \t]" id)
                 (lemmax--finding f l id "an id has no spaces" "keep the id one word, as RQ-1 or a UUID v7"))
                ((not (or (string-match-p "\\`[A-Z]+-[0-9]+\\'" id) (lemmax--uuid7-p id)))
                 (lemmax--finding f l id "the id is neither a UUID v7 nor shaped [A-Z]+-[0-9]+"
                                    "make a new one with python3 -c 'import uuid; print(uuid.uuid7())'")))
          ;; lemma: RT-4
          (when (and (lemmax--done-p state) (not (lemmax--proof-p r)) (not (lemmax--unproven-p r)) (null (plist-get r :approved)))
            (lemmax--finding f l id (format "%s with no :APPROVED:" state)
                               "get the owner's approval, then add :APPROVED: with its day"))
          (unless (or (plist-get r :created) (lemmax--note-p r)) (lemmax--finding f l id "no :CREATED:" "add :CREATED: YYYY-MM-DD"))
          (unless (or (plist-get r :last-edited) (lemmax--note-p r))
            (lemmax--finding f l id "no :LAST_EDITED:" "add :LAST_EDITED: YYYY-MM-DD"))
          (when (and (lemmax--done-p state) (not (lemmax--proof-p r)) (not (lemmax--unproven-p r)) (null (plist-get r :implemented)))
            (lemmax--finding f l id (format "%s with no :IMPLEMENTED:" state) "add :IMPLEMENTED: with the day it was built"))
          (when (and (or (lemmax--open-p state) (lemmax--dropped-p state)) (not (lemmax--proof-p r))
                     (plist-get r :implemented))
            (lemmax--finding f l id (format "%s with :IMPLEMENTED:" state)
                               (if (lemmax--new-state-p state) "remove :IMPLEMENTED:, or prove it a LEMMA"
                                 "remove :IMPLEMENTED:, or make it DONE")))
          (dolist (p '(:created :last-edited :approved :implemented :reviewed))
            (let ((v (plist-get r p)))
              (when (and v (not (lemmax--day-p v)))
                (lemmax--finding f l id (format "%s is not a real day: %s" (substring (symbol-name p) 1) v)
                                   "write it as YYYY-MM-DD"))))
          (when (and (equal state "DONE") (not (lemmax--task-p r)) (null (plist-get r :verify)))
            (lemmax--finding f l id "DONE with no :VERIFY:" "name the checks that verify it"))
          ;; lemma: 01a203a6-a716-738e-a95b-18086050d5eb
          (when (lemmax--done-p state)
            (dolist (b (plist-get r :before))
              (unless (or (lemmax--done-p (cdr b)) (lemmax--dropped-p (cdr b)) (equal (cdr b) "PASSED"))
                (lemmax--finding f l id (format "ORDERED: proven before its earlier sibling %s, which is %s"
                                                (or (car b) "(no id)") (or (cdr b) "no state"))
                                 "prove the earlier sibling first, or drop :ORDERED:"))))
          (when (and (plist-get r :blocker)
                     (not (equal (sort (copy-sequence (remove "previous-sibling" (plist-get r :blocker))) #'string<)
                                 (sort (copy-sequence (plist-get r :needs)) #'string<))))
            (lemmax--finding f l id ":BLOCKER: and :USES: name different ids"
                             "make :BLOCKER: name the ids :USES: names"))
          (if (lemmax--unproven-p r)
              (lemmax--lint-unproven r all f l id state)
            (lemmax--lint-math r all f l id state)))
        (when id
          (if (gethash id seen)
              (when (funcall show r)
                (lemmax--finding f l id (format "the id is used twice, first at %s" (gethash id seen))
                                   "give this one a new id"))
            (puthash id (format "%s:%s" f l) seen)))))
    (dolist (r all)
      (when (funcall show r)
        (dolist (u (plist-get r :refs))
          (unless (string-match-p "\\`https?://[^ \t]+\\'" u)
            (lemmax--finding (plist-get r :file) (plist-get r :line) (plist-get r :id)
                             (format ":REFS: names %s, which is not an http(s) URL" u)
                             "write it as https://...")))))
    ;; lemma: 01a202bc-4bf0-7fd3-a92c-204eb9fa96f0
    (let ((owner (make-hash-table :test #'equal)))
      (dolist (r all)
        (dolist (a (plist-get r :aliases))
          (let ((f (plist-get r :file)) (l (plist-get r :line)) (id (plist-get r :id)))
            (when (funcall show r)
              (cond ((gethash a seen)
                     (lemmax--finding f l id (format "the alias %s is also the :ID: at %s" a (gethash a seen))
                                      "remove the alias"))
                    ((gethash a owner)
                     (lemmax--finding f l id (format "the alias %s is also an alias of %s" a (gethash a owner))
                                      "keep it on one lemma"))))
            (unless (gethash a owner) (puthash a id owner)))))
      (maphash (lambda (a id) (puthash a (format "alias of %s" id) seen)) owner))
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

;; lemma: 01a2038d-cc5f-7324-8de8-1b067284e640 01a2038d-cc73-7594-9dd3-d758bee5aadc 01a2038d-cc86-72be-b225-eeff9ee2c7a6
(defun lemmax--lint-unproven (r all f l id state)
  "The rules of a task, a note or an axiom R, one of ALL, at F:L."
  (let ((known (lambda (x) (cl-find x all :key (lambda (y) (plist-get y :id)) :test #'equal))))
    (cond ((lemmax--task-p r)
           (unless (member state '("TODO" "DONE" "CANCELLED"))
             (lemmax--finding f l id (format "a task's state is TODO, DONE or CANCELLED, not %s" (or state "none"))
                              "give it one of those"))
           (dolist (x (plist-get r :for))
             (unless (funcall known x)
               (lemmax--finding f l id (format ":FOR: names %s, which no record has" x) "fix the id, or remove it"))))
          ((lemmax--note-p r)
           (when state
             (lemmax--finding f l id (format "a note has no state, not %s" state) "remove the state"))
           (dolist (x (plist-get r :about))
             (unless (funcall known x)
               (lemmax--finding f l id (format ":ABOUT: names %s, which no record has" x) "fix the id, or remove it")))))))

;; lemma: 01a20369-38f7-7229-8232-1b8cbb98e6bc
(defun lemmax--lint-math (r all f l id state)
  "The rules of conjectures and proofs for R, one of ALL, at F:L."
  (let ((known (lambda (x) (cl-find x all :key (lambda (y) (plist-get y :id)) :test #'equal))))
    (if (lemmax--proof-p r)
        (progn
          (unless (lemmax--proofs-file-p f)
            (lemmax--finding f l id "a proof outside a .proofs.org file" "move it to FILE.proofs.org beside its conjectures"))
          (unless (member state '("OPEN" "PASSED"))
            (lemmax--finding f l id (format "a proof's state is OPEN or PASSED, not %s" (or state "none"))
                             "make it OPEN, or PASSED once its tests pass"))
          (when (plist-get r :implemented)
            (lemmax--finding f l id "a proof with :IMPLEMENTED:" "remove it; the conjecture it proves holds the day"))
          (if (null (plist-get r :proves))
              (lemmax--finding f l id "a proof with no :PROVES:" "name the conjectures it proves in :PROVES:")
            (dolist (c (plist-get r :proves))
              (let ((x (funcall known c)))
                (cond ((and x (lemmax--axiom-p x))
                       ;; lemma: 01a2038d-cc86-72be-b225-eeff9ee2c7a6
                       (lemmax--finding f l id (format ":PROVES: names the axiom %s; an axiom is accepted without proof" c)
                                        "remove it from :PROVES:"))
                      ((or (null x) (lemmax--proof-p x) (lemmax--unproven-p x))
                       (lemmax--finding f l id (format ":PROVES: names %s, which no conjecture has" c)
                                        "fix the id, or remove it"))))))
          (when (and (equal state "PASSED") (null (plist-get r :verify)))
            (lemmax--finding f l id "a PASSED proof with no :TEST:" "name the tests that prove it in :TEST:")))
      (when (equal state "PASSED")
        (lemmax--finding f l id "PASSED is a proof's state" "make it LEMMA, or move the proof to a .proofs.org file"))
      (when (and (lemmax--new-state-p state) (plist-get r :own-verify))
        (lemmax--finding f l id (format "a %s has no :VERIFY:; its tests are in its proofs" state)
                         "move the addresses to a proof's :TEST:; lemmax migrate does it"))
      (when (member state '("LEMMA" "THEOREM"))
        (let ((proofs (plist-get r :proofs)))
          (if (null proofs)
              (lemmax--finding f l id (format "a %s with no proof" state)
                               "write a proof whose :PROVES: names it, or make it CONJECTURE")
            (dolist (p proofs)
              (unless (equal (cdr p) "PASSED")
                (lemmax--finding f l id (format "a %s whose proof %s is %s, a counterexample until it passes"
                                                state (car p) (or (cdr p) "no state"))
                                 "make the proof pass, or make this CONJECTURE"))))))
      (when (and (equal state "THEOREM") (null (plist-get r :needs)))
        (lemmax--finding f l id "a THEOREM with no :USES:" "name the lemmas it uses, or make it LEMMA"))
      (when (and (equal state "LEMMA") (plist-get r :needs))
        (lemmax--finding f l id "a LEMMA with :USES: is a THEOREM" "make it THEOREM"))
      (when (equal state "THEOREM")
        (dolist (u (plist-get r :needs))
          (let ((x (funcall known u)))
            (when (and x (not (lemmax--done-p (plist-get x :state))) (not (lemmax--axiom-p x)))
              (lemmax--finding f l id (format "a THEOREM that uses %s, which is %s, not proven" u (or (plist-get x :state) "no state"))
                               "prove it first, or make this CONJECTURE"))))))))

;; lemma: RT-5
(defun lemmax--lint-verify (infos only)
  "RT-5: a DONE requirement's :VERIFY: names tests the command prints."
  (dolist (info infos)
    (when (or (null only) (member (plist-get info :file) only))
      (let ((res (lemmax--test-addresses (plist-get info :tests))))
        (if (not (car res))
            (lemmax--finding (plist-get info :file) 1 nil (cdr res)
                               "make the command print one test address a line")
          (dolist (r (plist-get info :reqs))
            ;; lemma: 01a20369-38f7-7229-8232-1b8cbb98e6bc
            (when (if (lemmax--proof-p r) (equal (plist-get r :state) "PASSED")
                    (and (lemmax--done-p (plist-get r :state)) (not (lemmax--unproven-p r))))
              (dolist (a (plist-get r :verify))
                (unless (member a (cdr res))
                  (lemmax--finding (plist-get r :file) (plist-get r :line) (plist-get r :id)
                                     (format "%s names %s, which the test command does not list"
                                             (if (lemmax--proof-p r) ":TEST:" ":VERIFY:") a)
                                     "write the test, or fix the address"))))))))))

;; lemma: RT-6
(defun lemmax--lint-staged (staged head)
  "RT-6: the change rules, STAGED infos against HEAD infos."
  (let ((before (make-hash-table :test #'equal)) (today (lemmax--today)))
    (dolist (r (lemmax--all-reqs head)) (when (plist-get r :id) (puthash (plist-get r :id) r before)))
    (dolist (r (lemmax--all-reqs staged))
      (let* ((id (plist-get r :id)) (old (and id (gethash id before)))
             (f (plist-get r :file)) (l (plist-get r :line))
             (done (and (lemmax--done-p (plist-get r :state)) (not (lemmax--proof-p r)) (not (lemmax--unproven-p r)))))
        (when id
          (if old
              (let ((changed (not (equal (plist-get old :text) (plist-get r :text)))))
                (when (and changed done (lemmax--done-p (plist-get old :state)))
                  (lemmax--finding f l id (format "a %s requirement's text changed" (plist-get r :state))
                                     (if (lemmax--new-state-p (plist-get r :state))
                                         "make it CONJECTURE until the change is proven"
                                       "make it OPEN until the change is built")))
                (when (and changed (not (equal (plist-get r :last-edited) today)))
                  (lemmax--finding f l id "its text changed and :LAST_EDITED: is not today"
                                     (format "set :LAST_EDITED: %s" today)))
                (when (and done (not (lemmax--done-p (plist-get old :state)))
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
  (setq lemmax--json-mode (and (member "--json" args) t))
  (let ((staged (member "--staged" args))
        (no-tests (member "--no-tests" args))
        (only (cl-remove-if (lambda (a) (string-prefix-p "--" a)) args)))
    (let ((bad (cl-find-if (lambda (a) (and (string-prefix-p "--" a)
                                             (not (member a '("--staged" "--no-tests" "--json")))))
                           args)))
      (when bad (lemmax--err "lemmax: unknown option %s; see lemmax lint --help" bad) (kill-emacs 1)))
    (lemmax--lint-config staged)
    (let* ((infos (lemmax--opted (if staged (lemmax--rev-files "") (lemmax--worktree-files))))
           ;; lemma: 01a20336-c583-720a-b661-c9b5a5dec1a4
           ;; FILE is a path from where lemmax was run, and must be a tracked .org file.
           (tracked (lemmax--lines (lemmax--git-out "ls-files" "*.org")))
           (only (and only
                      (mapcar (lambda (f)
                                (let ((rel (file-relative-name (expand-file-name f (or lemmax--cwd default-directory))
                                                               default-directory)))
                                  (unless (member rel tracked)
                                    (lemmax--err "lemmax: %s: not a tracked .org file" f)
                                    (kill-emacs 1))
                                  rel))
                              only))))
      (if (null infos)
          (lemmax--err "lemmax: no requirements file here has #+LEMMAX_TESTS: or an entry in lemmax/config.eld")
        (lemmax--lint-file-rules infos only)
        (lemmax--lint-tags infos only)
        (lemmax--lint-markers infos only staged)
        (lemmax--lint-links infos only staged)
        (lemmax--lint-markers-in infos only)
        (dolist (i infos)
          (when (and (plist-get i :misplaced) (or (null only) (member (plist-get i :file) only)))
            (lemmax--finding (plist-get i :file) (plist-get i :misplaced) nil
                             "a drawer with :ID: below other text is no file lemma; Org reads only a first drawer"
                             "move the drawer to the top of the file")))
        (unless no-tests (lemmax--lint-verify infos only))
        (when staged
          ;; lemma: 01a2002d-fb3b-71e3-ac96-5e1dbba8226c
          ;; lemma: 01a202f3-8216-7a1e-a34c-80c99d7bbf02
          ;; Every HEAD file, opted in then or not: a lemma is matched by :ID:,
          ;; wherever it lived, so a moved lemma is not new.
          (lemmax--lint-staged infos (lemmax--rev-files "HEAD")))))
    (when lemmax--json-mode
      (princ (concat (json-encode (list (cons 'version 1)
                                        (cons 'findings (vconcat (reverse lemmax--json-findings)))))
                     "\n")))
    (kill-emacs (if (> lemmax--findings 0) 1 0))))

;;;; Tags (01a2039c-9e67-74bb-9ac4-63eac14f1e7c)

;; lemma: 01a2039c-9e67-74bb-9ac4-63eac14f1e7c
(defun lemmax--lint-tags (infos only)
  "A tag a file does not declare in #+TAGS:, and a cycle in its tag groups."
  (dolist (i infos)
    (let ((f (plist-get i :file)) (declared (plist-get i :declared)))
      (when (or (null only) (member f only))
        (dolist (tg (plist-get i :file-tags))
          (unless (member tg declared)
            (lemmax--finding f 1 nil (format "the file tag %s is not declared" tg) "add it to #+TAGS:")))
        (dolist (r (plist-get i :reqs))
          (dolist (tg (plist-get r :tags-own))
            (unless (member tg declared)
              (lemmax--finding f (plist-get r :line) (plist-get r :id)
                               (format "the tag %s is not declared" tg) "add it to #+TAGS:, or fix the tag"))))
        (let ((groups (plist-get i :tag-groups)) (reported nil))
          (dolist (g groups)
            (let ((seen nil) (stack (copy-sequence (cdr g))) found)
              (while (and stack (not found))
                (let ((x (pop stack)))
                  (if (equal x (car g)) (setq found t)
                    (unless (member x seen)
                      (push x seen)
                      (dolist (h groups) (when (equal (car h) x) (setq stack (append (cdr h) stack))))))))
              (when (and found (not (member (car g) reported)))
                (push (car g) reported)
                (lemmax--finding f 1 nil (format "the tag group %s holds itself, a cycle" (car g))
                                 "remove one link of the cycle from #+TAGS:")))))))))

;; lemma: 01a2039c-9e67-74bb-9ac4-63eb06d24a3f
(defun lemmax--tag-under (tag infos)
  "TAG and every tag under it, at any depth, in the groups of INFOS."
  (let ((groups (cl-mapcan (lambda (i) (copy-sequence (plist-get i :tag-groups))) infos))
        (out nil) (stack (list tag)))
    (while stack
      (let ((x (pop stack)))
        (unless (member x out)
          (push x out)
          (dolist (g groups) (when (equal (car g) x) (setq stack (append (cdr g) stack)))))))
    out))

(defun lemmax--tags-match-p (r wanted infos)
  "Whether R's tags hold, for each tag of WANTED, it or a tag under it."
  (cl-every (lambda (w) (cl-intersection (plist-get r :tags) (lemmax--tag-under w infos) :test #'equal)) wanted))

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
                    (append '("grep" "-n" "-z" "-I" "-E") (and cached '("--cached"))
                            '("lemma:[[:space:]]+[A-Za-z0-9]" "--" "." ":(exclude)*.org"))))
        res)
    (dolist (l (lemmax--lines out))
      ;; lemma: 01a202f3-82c0-7905-9aa6-cafdcd9235e8
      ;; -z: FILE NUL LINE NUL TEXT, so a path may hold a colon.
      (when (string-match "\\`\\([^\0]+\\)\0\\([0-9]+\\)\0\\(.*\\)\\'" l)
        (let ((file (match-string 1 l)) (line (string-to-number (match-string 2 l)))
              (text (match-string 3 l)))
          (when (string-match lemmax--marker-re text)
            (dolist (id (lemmax--marker-ids (match-string 1 text)))
              (push (list id file line (and (lemmax--test-path-p file patterns) t)) res))))))
    (nreverse res)))

;; lemma: 01a20336-c953-745d-aef4-90ee2141e08d
(defun lemmax--sibling-p (dir)
  "Whether DIR is ../NAME, a folder beside this repo that is a git repo."
  (and (string-match-p "\\`\\.\\./[^/.][^/]*/?\\'" dir)
       (file-exists-p (expand-file-name ".git" (expand-file-name dir default-directory)))))

(defun lemmax--lint-markers-in (infos only)
  "A markers-in folder that is not a sibling git repo; it is not read."
  (dolist (i infos)
    (when (or (null only) (member (plist-get i :file) only))
      (dolist (dir (plist-get i :markers-in))
        (unless (lemmax--sibling-p dir)
          (lemmax--finding (plist-get i :file) 1 nil
                           (format "markers-in names %s, which is not a git repo beside this one" dir)
                           "name a sibling repo as ../NAME, or remove it"))))))

(defun lemmax--all-markers (infos &optional cached)
  "The markers of this repo and of every repo #+LEMMAX_MARKERS_IN: names."
  (let* ((patterns (lemmax--test-paths infos))
         (known (lemmax--known (lemmax--all-reqs infos))))
    (mapcar
     (lambda (m) (let ((r (gethash (car m) known))) (if r (cons (plist-get r :id) (cdr m)) m)))
     (append (lemmax--markers patterns cached)
            (cl-loop for dir in (cl-remove-if-not #'lemmax--sibling-p
                                                  (delete-dups (cl-mapcan (lambda (i) (copy-sequence (plist-get i :markers-in))) infos)))
                     for full = (expand-file-name dir default-directory)
                     when (file-directory-p full)
                     append (let ((default-directory (file-name-as-directory full)))
                              (mapcar (lambda (m) (list (nth 0 m) (concat (directory-file-name dir) "/" (nth 1 m))
                                                        (nth 2 m) (nth 3 m)))
                                      (lemmax--markers patterns))))))))

(defun lemmax--lint-markers (infos only cached)
  "Markers that name no lemma or a DROPPED one; DONE lemmas implemented on or
after the config's :markers-required-from with no code marker."
  (let* ((known (make-hash-table :test #'equal))
         (from (lemmax--config-setting :markers-required-from))
         (markers (lemmax--all-markers infos cached))
         (reqs (lemmax--all-reqs infos)))
    (setq known (lemmax--known (lemmax--all-reqs (lemmax--listed (if cached (lemmax--rev-files "") (lemmax--worktree-files))))))
    (dolist (m markers)
      (let ((r (gethash (nth 0 m) known)))
        (cond ((null r)
               (lemmax--finding (nth 1 m) (nth 2 m) (nth 0 m) "the marker names an id no lemma has"
                                "fix the id, or remove the marker"))
              ((lemmax--dropped-p (plist-get r :state))
               (lemmax--finding (nth 1 m) (nth 2 m) (nth 0 m) (format "the marker names a %s lemma" (plist-get r :state))
                                "remove the marker, or the code it marks")))))
    (dolist (r reqs)
      (when (and (lemmax--done-p (plist-get r :state)) (not (lemmax--proof-p r)) (not (lemmax--unproven-p r))
                 (or (null only) (member (plist-get r :file) only))
                 (plist-get r :implemented) from (not (string< (plist-get r :implemented) from))
                 (not (cl-some (lambda (m) (and (equal (nth 0 m) (plist-get r :id)) (not (nth 3 m)))) markers)))
        (lemmax--finding (plist-get r :file) (plist-get r :line) (plist-get r :id)
                         (format "%s with no code marker" (plist-get r :state))
                         (format "put a comment line \"lemma: %s\" where it is built" (plist-get r :id)))))))

;;;; id: links (01a202bc-49e2-7dba-94f5-0c0952fc91f0)

(defconst lemmax--id-link-re "\\[\\[id:\\([^]\n]+\\)\\]"
  "An org-id link; group 1 is the id.")

;; lemma: 01a202bc-49e2-7dba-94f5-0c0952fc91f0
(defun lemmax--id-links (&optional cached)
  "Every [[id:...]] link in the tracked .org files: a list of (ID FILE LINE).
With CACHED, read the staged copies."
  (let ((out (apply #'lemmax--git-out
                    (append '("grep" "-n" "-z" "-I" "-F") (and cached '("--cached"))
                            '("[[id:" "--" "*.org"))))
        res)
    (dolist (l (lemmax--lines out))
      ;; lemma: 01a202f3-82c0-7905-9aa6-cafdcd9235e8
      ;; -z: FILE NUL LINE NUL TEXT, so a path may hold a colon.
      (when (string-match "\\`\\([^\0]+\\)\0\\([0-9]+\\)\0\\(.*\\)\\'" l)
        (let ((file (match-string 1 l)) (line (string-to-number (match-string 2 l)))
              (text (lemmax--blank-verbatim (match-string 3 l))) (pos 0))
          (while (string-match lemmax--id-link-re text pos)
            (push (list (string-trim (match-string 1 text)) file line) res)
            (setq pos (match-end 0))))))
    (nreverse res)))

(defun lemmax--blank-verbatim (text)
  "TEXT with =verbatim= and ~code~ spans blanked: org shows no link there."
  (replace-regexp-in-string "\\(?:=[^=\n]+=\\|~[^~\n]+~\\)"
                            (lambda (m) (make-string (length m) ?\s)) text t t))

(defun lemmax--known (reqs)
  "Hash: each id of REQS, and each alias, to its lemma."
  (let ((known (make-hash-table :test #'equal)))
    (dolist (r reqs)
      (when (plist-get r :id) (puthash (plist-get r :id) r known)))
    (dolist (r reqs)
      (dolist (a (plist-get r :aliases))
        (unless (gethash a known) (puthash a r known))))
    known))

(defun lemmax--lint-links (infos only cached)
  "An id: link in an opted-in file that names no lemma, or a DROPPED one."
  (let ((known (lemmax--known (lemmax--all-reqs (lemmax--listed (if cached (lemmax--rev-files "") (lemmax--worktree-files))))))
        (files (mapcar (lambda (i) (plist-get i :file)) infos)))
    (dolist (k (lemmax--id-links cached))
      (when (and (member (nth 1 k) files) (or (null only) (member (nth 1 k) only)))
        (let ((r (gethash (nth 0 k) known)))
          (cond ((null r)
                 (lemmax--finding (nth 1 k) (nth 2 k) (nth 0 k) "the id: link names an id no lemma has"
                                  "fix the id, or remove the link"))
                ((lemmax--dropped-p (plist-get r :state))
                 (lemmax--finding (nth 1 k) (nth 2 k) (nth 0 k) (format "the id: link names a %s lemma" (plist-get r :state))
                                  "link the lemma that replaced it, or remove the link"))))))))

;;;; commit-msg (RT-7)

(defun lemmax--names-id-p (text id)
  (string-match-p (concat "\\(?:\\`\\|[^A-Za-z0-9_-]\\)" (regexp-quote id) "\\(?:\\'\\|[^A-Za-z0-9_-]\\)")
                  text))

;; lemma: RT-7
;; lemma: 01a2038d-cc9a-7496-b943-49cb1444826d
;; A task's id counts: the ids come from every record, tasks too.
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
             (ids (delq nil (cl-mapcan (lambda (r) (cons (plist-get r :id) (copy-sequence (plist-get r :aliases))))
                                       (lemmax--all-reqs infos)))))
        (unless (cl-some (lambda (id) (lemmax--names-id-p msg id)) ids)
          (lemmax--finding msgfile 1 nil
                             (format "this commit changes code (%s) and names no requirement id" touches)
                             "name one in the message, as (RQ-1)"))))
    (kill-emacs (if (> lemmax--findings 0) 1 0))))

;;;; trace (RT-8, RT-9)

(defun lemmax--commits ()
  "List of (HASH SHORT DATE SUBJECT BODY), newest first."
  (let ((out (lemmax--git-out "log" "--date=format-local:%Y-%m-%d" "--format=%H%x1f%h%x1f%cd%x1f%s%x1f%B%x1e")))
    (cl-loop for rec in (split-string (or out "") "\x1e" t)
             for f = (split-string (string-trim-left rec) "\x1f")
             when (>= (length f) 5) collect f)))

(defun lemmax--blobs (specs)
  "The contents of SPECS, each REV:PATH, read by one git cat-file --batch:
a list of (BLOB-ID . TEXT), or nil for a spec git does not have."
  (when specs
    (with-temp-buffer
      (set-buffer-multibyte nil)
      (let ((coding-system-for-read 'no-conversion) (coding-system-for-write 'utf-8-unix)
            (process-environment (cons "TZ=UTC0" process-environment)))
        (insert (mapconcat #'identity specs "\n") "\n")
        (call-process-region (point-min) (point-max) "git" t t nil "cat-file" "--batch"))
      (goto-char (point-min))
      (cl-loop for _ in specs
               collect (let ((head (buffer-substring (point) (line-end-position))))
                         (forward-line 1)
                         (if (string-match "\\`\\([0-9a-f]+\\) [a-z]+ \\([0-9]+\\)\\'" head)
                             (let* ((size (string-to-number (match-string 2 head)))
                                    (text (buffer-substring (point) (+ (point) size))))
                               (goto-char (+ (point) size 1))
                               (cons (match-string 1 head) (decode-coding-string text 'utf-8)))
                           nil))))))

;; lemma: 01a202f3-88bb-704d-9ea9-74714f841514
(defun lemmax--last-changes (infos)
  "Hash ID -> the last day its text changed in git, walking each file's revisions.
One git process reads every revision of a file; a blob seen before is skipped."
  (let ((changed (make-hash-table :test #'equal)))
    (dolist (info infos)
      (let* ((file (plist-get info :file)) (prev (make-hash-table :test #'equal))
             (seen (make-hash-table :test #'equal))
             (revs (mapcar (lambda (l) (split-string l " "))
                           (lemmax--lines (lemmax--git-out "log" "--reverse" "--date=format-local:%Y-%m-%d"
                                                           "--format=%H %cd" "--" file))))
             (blobs (lemmax--blobs (mapcar (lambda (r) (concat (car r) ":" file)) revs))))
        (cl-loop for (_rev day) in revs
                 for blob in blobs
                 when (and blob (not (gethash (car blob) seen)))
                 do (puthash (car blob) t seen)
                    (dolist (pair (lemmax--quick-ids (cdr blob)))
                      (unless (equal (gethash (car pair) prev) (cdr pair))
                        (puthash (car pair) day changed)
                        (puthash (car pair) (cdr pair) prev))))))
    changed))

;; lemma: RT-9
(defun lemmax--suspects (reqs changed)
  "List of (CHILD PARENT DAY) for DONE children whose parent changed after them."
  (let (out)
    (dolist (r reqs)
      (when (lemmax--done-p (plist-get r :state))
        (let ((since (car (sort (delq nil (list (plist-get r :implemented) (plist-get r :reviewed)))
                                #'string>))))
          (dolist (p (plist-get r :needs))
            (let ((day (gethash p changed)))
              (when (and day since (string> day since))
                (push (list (plist-get r :id) p day) out)))))))
    (nreverse out)))

(defvar lemmax--marks nil "The markers of the repo being traced.")
(defvar lemmax--links nil "The id: links of the repo being traced, as (ID FILE LINE).")

;; lemma: 01a202bc-4b52-74e6-9d78-591320edcb4f
(defun lemmax--lemma-at (reqs file line)
  "The lemma of REQS in FILE whose lines hold LINE, or nil."
  (cl-find-if (lambda (r) (and (equal (plist-get r :file) file)
                               (<= (plist-get r :line) line (or (plist-get r :end) (plist-get r :line)))))
              reqs))

(defun lemmax--repo-links (reqs)
  "The id: links of the work tree, each id read through REQS' aliases."
  (let ((known (lemmax--known reqs)))
    (mapcar (lambda (k) (let ((r (gethash (car k) known))) (if r (cons (plist-get r :id) (cdr k)) k)))
            (lemmax--id-links))))

(defun lemmax--backlinks (id reqs links)
  "What links to ID: a list of (SOURCE-ID-or-nil FILE LINE), not ID itself."
  (cl-loop for k in links
           for src = (lemmax--lemma-at reqs (nth 1 k) (nth 2 k))
           when (and (equal (car k) id) (not (and src (equal (plist-get src :id) id))))
           collect (list (and src (plist-get src :id)) (nth 1 k) (nth 2 k))))

;; lemma: RT-8
(defun lemmax--block (r reqs addresses commits suspects one)
  (let* ((id (plist-get r :id))
         (children (cl-loop for c in reqs when (member id (plist-get c :needs)) collect (plist-get c :id))))
    (lemmax--out "%s %s %s" (or id "(no id)") (or (plist-get r :state) "-") (plist-get r :title))
    (lemmax--out "  file: %s:%d" (plist-get r :file) (plist-get r :line))
    ;; lemma: 01a20369-38d2-7202-8b53-6e296aaac489
    (let ((math (or (lemmax--new-state-p (plist-get r :state)) (lemmax--proof-p r))))
      (lemmax--out (if math "  uses: %s" "  parents: %s") (if (plist-get r :needs) (string-join (plist-get r :needs) " ") "none"))
      (lemmax--out (if math "  used by: %s" "  children: %s") (if children (string-join children " ") "none")))
    (when (plist-get r :refs) (lemmax--out "  refs: %s" (string-join (plist-get r :refs) " ")))
    ;; lemma: 01a20369-393d-77bf-a35a-a1c03780a751
    (when (plist-get r :proves) (lemmax--out "  proves: %s" (string-join (plist-get r :proves) " ")))
    (when (plist-get r :for) (lemmax--out "  for: %s" (string-join (plist-get r :for) " ")))
    (when (plist-get r :about) (lemmax--out "  about: %s" (string-join (plist-get r :about) " ")))
    (dolist (p (plist-get r :proofs))
      (lemmax--out "  proof: %s %s" (car p) (or (cdr p) "-")))
    (let ((from (and id (lemmax--backlinks id reqs lemmax--links))))
      (if (null from)
          (lemmax--out "  linked from: none")
        (dolist (b from)
          (lemmax--out "  linked from: %s%s:%d" (if (car b) (concat (car b) " ") "") (nth 1 b) (nth 2 b)))))
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
  "Whether this repo has an opted-in file or a config; a git grep, so no parse."
  (or (zerop (car (lemmax--git "grep" "--cached" "-q" "-E" "^#\\+LEMMAX_TESTS:" "--" "*.org")))
      (zerop (car (lemmax--git "cat-file" "-e" (concat ":" lemmax-config-file))))))

;; lemma: RT-19
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


;; lemma: 01a202bc-4e0c-745b-9f61-980ada0f93e5
(defun lemmax--dot-quote (&rest parts)
  "PARTS as one quoted dot string, each escaped, joined by dot's \\n line break."
  (concat "\"" (mapconcat (lambda (s) (replace-regexp-in-string "[\"\\]" (lambda (m) (concat "\\" m)) s t t))
                          parts "\\n")
          "\""))

(defun lemmax--dot (infos)
  "Print the lemmas of INFOS as a Graphviz digraph: :NEEDS: solid, id: links dashed."
  (let* ((reqs (cl-remove-if-not (lambda (r) (plist-get r :id)) (lemmax--all-reqs infos)))
         (links (lemmax--repo-links (lemmax--all-reqs (lemmax--listed (lemmax--worktree-files)))))
         (ids (mapcar (lambda (r) (plist-get r :id)) reqs))
         edges)
    (lemmax--out "digraph lemmax {")
    (lemmax--out "  node [shape=box style=filled fontname=Helvetica];")
    (dolist (r reqs)
      (lemmax--out "  %s [label=%s fillcolor=%s%s];" (lemmax--dot-quote (plist-get r :id))
                   (lemmax--dot-quote (plist-get r :id) (lemmax--trunc (plist-get r :title) 40))
                   (let ((st (plist-get r :state)))
                     (cond ((lemmax--proof-p r) (if (equal st "PASSED") "palegreen" "lightyellow"))
                           ((lemmax--done-p st) "palegreen") ((lemmax--open-p st) "lightyellow")
                           ((lemmax--dropped-p st) "lightgray") (t "white")))
                   ;; lemma: 01a20369-393d-77bf-a35a-a1c03780a751
                   (if (lemmax--proof-p r) " shape=ellipse" "")))
    (dolist (r reqs)
      (dolist (n (plist-get r :needs))
        (when (member n ids)
          (lemmax--out "  %s -> %s;" (lemmax--dot-quote (plist-get r :id)) (lemmax--dot-quote n))))
      (dolist (c (plist-get r :proves))
        (when (member c ids)
          (lemmax--out "  %s -> %s [style=dotted];" (lemmax--dot-quote (plist-get r :id)) (lemmax--dot-quote c)))))
    (dolist (k links)
      (let ((src (lemmax--lemma-at reqs (nth 1 k) (nth 2 k))))
        (when (and src (member (car k) ids) (not (equal (plist-get src :id) (car k))))
          (let ((e (cons (plist-get src :id) (car k))))
            (unless (member e edges)
              (push e edges)
              (lemmax--out "  %s -> %s [style=dashed];" (lemmax--dot-quote (car e)) (lemmax--dot-quote (cdr e))))))))
    (lemmax--out "}")))

(defvar lemmax--trace-tags nil "The --tag values of trace.")

(defun lemmax-trace (args)
  ;; lemma: 01a2039c-9e67-74bb-9ac4-63eb06d24a3f
  (let (rest)
    (while args
      (let ((a (pop args)))
        (if (equal a "--tag")
            (let ((v (pop args)))
              (unless v (lemmax--err "lemmax: --tag takes a tag") (kill-emacs 1))
              (setq lemmax--trace-tags (append lemmax--trace-tags (list v))))
          (push a rest))))
    (setq args (nreverse rest)))
  (when (member "--run-tests" args)
    (setq lemmax--run-tests t args (remove "--run-tests" args)))
  (let ((bad (cl-find-if (lambda (a) (and (string-prefix-p "--" a) (not (equal a "--dot")))) args)))
    (when bad (lemmax--err "lemmax: unknown option %s; see lemmax trace --help" bad) (kill-emacs 1)))
  (when (member "--dot" args)
    (let ((infos (and (lemmax--root) (lemmax--opted (lemmax--worktree-files)))))
      (unless infos
        (lemmax--err "lemmax: no requirements file here has #+LEMMAX_TESTS:; name a project with -p DIR")
        (kill-emacs 1))
      (lemmax--dot infos)
      (kill-emacs 0)))
  (let* ((want (car args))
         (infos (and (lemmax--root) (lemmax--opted (lemmax--worktree-files))))
         (hit (and want (gethash want (lemmax--known (lemmax--all-reqs infos))))))
    (when hit (setq want (plist-get hit :id)))
    (when (and want (null lemmax--projects)
               (not (cl-some (lambda (r) (equal want (plist-get r :id))) (lemmax--all-reqs infos))))
      (let ((hits (lemmax--projects-with want)))
        (unless hits
          (lemmax--err "lemmax: unknown id %s, here or in any project under %s; lemmax list --all shows the ids"
                         want (abbreviate-file-name (expand-file-name (lemmax--repos-dir))))
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
           (lemmax--links (lemmax--repo-links (lemmax--all-reqs (lemmax--listed (lemmax--worktree-files)))))
           (commits (lemmax--commits))
           (changed (lemmax--last-changes infos))
           (suspects (lemmax--suspects reqs changed))
           (addr-of (lambda (r) (if (not lemmax--run-tests) (cons nil "not run") (lemmax--test-addresses
                                 (plist-get (cl-find (plist-get r :file) infos
                                                     :key (lambda (i) (plist-get i :file)) :test #'equal)
                                            :tests))))))
      (if want
          ;; lemma: RT-18
          (let ((all (cl-remove-if-not (lambda (x) (equal want (plist-get x :id))) reqs)))
            (unless all
              (lemmax--err "lemmax: unknown id %s; lemmax list shows the ids" want)
              (kill-emacs 1))
            (dolist (r all) (lemmax--block r reqs (funcall addr-of r) commits suspects t))
            (when (cdr all)
              (lemmax--err "lemmax: %s is used %d times" want (length all))
              (kill-emacs 1)))
        (dolist (r reqs)
          (when (or (null lemmax--trace-tags) (lemmax--tags-match-p r lemmax--trace-tags infos))
            (lemmax--block r reqs (funcall addr-of r) commits suspects nil)
            (lemmax--out "")))
        (let* ((named (cl-mapcan (lambda (r) (copy-sequence (plist-get r :verify))) reqs))
               (orphans (cl-loop for info in (and lemmax--run-tests infos)
                                 for res = (lemmax--test-addresses (plist-get info :tests))
                                 when (car res)
                                 append (cl-remove-if (lambda (a) (member a named)) (cdr res)))))
          (lemmax--out "Orphan tests: %s" (cond ((not lemmax--run-tests) "not checked; --run-tests runs the test command")
                                                (orphans "") (t "none")))
          (dolist (o (delete-dups orphans)) (lemmax--out "  %s" o)))
        (lemmax--out "Suspect: %s" (if suspects "" "none"))
        (dolist (s suspects)
          (lemmax--out "  %s: parent %s changed %s" (nth 0 s) (nth 1 s) (nth 2 s)))))))

;;;; list (RT-13)

(defun lemmax--group (r)
  (let ((state (plist-get r :state)))
    ;; lemma: 01a20369-393d-77bf-a35a-a1c03780a751
    (cond ((lemmax--proof-p r) "proofs")
          ((lemmax--task-p r) "tasks")
          ((lemmax--note-p r) "notes")
          ((lemmax--axiom-p r) "axioms")
          ((lemmax--done-p state) "done")
          ((lemmax--dropped-p state) "dropped")
          ((plist-get r :approved) "approved")
          (t "waiting"))))

(defconst lemmax--group-names
  '(("waiting" . "Waiting for approval") ("approved" . "Approved and open")
    ("done" . "Done") ("dropped" . "Dropped") ("proofs" . "Proofs")
    ("tasks" . "Tasks") ("notes" . "Notes") ("axioms" . "Axioms")))

(defun lemmax--rows (no-tests)
  "Rows for every listed requirement of the repo here."
  (let* ((infos (lemmax--listed (lemmax--worktree-files)))
         (marks (lemmax--all-markers infos))
         (all (lemmax--all-reqs infos))
         (links (lemmax--repo-links all)))
    (cl-loop for info in infos
             for addr = (and (plist-get info :opted) (not no-tests) lemmax--run-tests
                             (lemmax--test-addresses (plist-get info :tests)))
             append (cl-loop for r in (plist-get info :reqs)
                             collect (let ((v (plist-get r :verify)))
                                       (append r (list :group (lemmax--group r)
                                                       :linked-from (lemmax--backlinks (plist-get r :id) all links)
                                                       :markers (cl-loop for m in marks
                                                                         when (equal (nth 0 m) (plist-get r :id))
                                                                         collect m)
                                                       :check (cond ((null v) "none")
                                                                    ((not (car addr)) "named")
                                                                    ((cl-every (lambda (a) (member a (cdr addr))) v) "found")
                                                                    (t "missing")))))))))

(defun lemmax--filter (rows opts)
  (when (plist-get opts :duplicates)
    (setq rows (cl-remove-if-not
                (lambda (r) (and (plist-get r :id)
                                 (< 1 (cl-count (plist-get r :id) rows :key (lambda (x) (plist-get x :id)) :test #'equal))))
                rows)))
  (cl-remove-if-not
   (lambda (r)
     (and (or (null (plist-get opts :state))
              (equal (downcase (or (plist-get r :state) "")) (plist-get opts :state)))
          (or (null (plist-get opts :section))
              (and (plist-get r :id) (string-prefix-p (concat (plist-get opts :section) "-") (plist-get r :id))))
          (or (not (plist-get opts :unchecked))
              (and (lemmax--done-p (plist-get r :state)) (not (lemmax--proof-p r))
                   (member (plist-get r :check) '("none" "missing"))))
          (or (not (plist-get opts :unmarked))
              (and (lemmax--done-p (plist-get r :state)) (not (lemmax--proof-p r))
                   (not (cl-some (lambda (m) (not (nth 3 m))) (plist-get r :markers)))))
          (or (null (plist-get opts :tags))
              (lemmax--tags-match-p r (plist-get opts :tags) (lemmax--listed (lemmax--worktree-files))))
          (or (not (plist-get opts :ready))
              (and (lemmax--open-p (plist-get r :state)) (not (lemmax--proof-p r)) (not (lemmax--unproven-p r))
                   (plist-get r :approved)))))
   rows))

(defun lemmax--trunc (s n) (if (> (length s) n) (concat (substring s 0 (1- n)) "…") s))

(defun lemmax--print-table (rows)
  (dolist (g lemmax--group-names)
    (let ((in (cl-remove-if-not (lambda (r) (equal (plist-get r :group) (car g))) rows)))
      (when in
        (lemmax--out "%s (%d)" (cdr g) (length in))
        (dolist (r in)
          (lemmax--out "  %-22s %-10s %-8s %-7s %-60s %s:%d  code:%d"
                         (or (plist-get r :id) "(no id)") (or (plist-get r :state) "-")
                         (if (plist-get r :approved) "approved" "-")
                         (plist-get r :check) (lemmax--trunc (plist-get r :title) 60)
                         (plist-get r :file) (plist-get r :line)
                         (cl-count-if-not (lambda (m) (nth 3 m)) (plist-get r :markers)))))))
  (let ((noid (cl-count-if (lambda (r) (null (plist-get r :id))) rows)))
    (when (> noid 0) (lemmax--out "No id: %d" noid))))

(defconst lemmax-json-version 1
  "The shape of list --json; a change of any row key or type bumps it.")

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
            (cons 'refs (vconcat (plist-get r :refs)))
            (cons 'linked_from (vconcat (mapcar (lambda (b) (list (cons 'id (or (nth 0 b) :null)) (cons 'file (nth 1 b))
                                                                  (cons 'line (nth 2 b))))
                                                (plist-get r :linked-from))))
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
                       (unless (member v '("open" "done" "dropped" "conjecture" "lemma" "theorem" "refuted" "passed" "todo" "cancelled" "axiom"))
                         (lemmax--err "lemmax: --state takes open, done, dropped, conjecture, lemma, theorem, refuted, passed, todo, cancelled or axiom")
                         (kill-emacs 1))
                       (setq opts (plist-put opts :state v))))
          ("--section" (let ((v (pop args)))
                         (unless (and v (string-match-p "\\`[A-Z]+\\'" v))
                           (lemmax--err "lemmax: --section takes capital letters, as M") (kill-emacs 1))
                         (setq opts (plist-put opts :section v))))
          ("--unchecked" (setq opts (plist-put opts :unchecked t)))
          ("--unmarked" (setq opts (plist-put opts :unmarked t)))
          ("--ready" (setq opts (plist-put opts :ready t)))
          ("--unlinked" (setq opts (plist-put opts :unlinked t)))
          ("--duplicates" (setq opts (plist-put opts :duplicates t)))
          ;; lemma: 01a2039c-9e67-74bb-9ac4-63eb06d24a3f
          ("--tag" (let ((v (pop args)))
                     (unless v (lemmax--err "lemmax: --tag takes a tag") (kill-emacs 1))
                     (setq opts (plist-put opts :tags (append (plist-get opts :tags) (list v))))))
          ("--all" (setq opts (plist-put opts :all t)))
          ("--json" (setq opts (plist-put opts :json t)))
          ("--no-tests" (setq opts (plist-put opts :no-tests t)))
          ("--run-tests" (setq lemmax--run-tests t))
          (_ (lemmax--err "lemmax: unknown option %s; see lemmax list --help" a) (kill-emacs 1)))))
    opts))

(defun lemmax--repos-dir ()
  "The folder of the repos list --all reads: the config's :repos, LEMMAX_REPOS, ~/repos."
  (or (lemmax--config-setting :repos) (getenv "LEMMAX_REPOS") "~/repos"))

(defun lemmax--repos ()
  (let ((base (expand-file-name (lemmax--repos-dir))))
    (cl-loop for d in (directory-files base t "\\`[^.]")
             when (and (file-directory-p d) (file-exists-p (expand-file-name ".git" d)))
             collect (file-name-as-directory d))))


;; lemma: 01a202bc-4d72-7f9e-8e2d-6f8ae9b27ed5
(defun lemmax--unlinked ()
  "Each place in a tracked .org file whose text names a lemma id with no link:
a list of (FILE LINE ID). :ID:, :NEEDS: and :ALIASES: lines and id: links are not text."
  (let* ((reqs (lemmax--all-reqs (lemmax--listed (lemmax--worktree-files))))
         (ids (delete-dups (delq nil (cl-mapcan (lambda (r) (cons (plist-get r :id) (copy-sequence (plist-get r :aliases))))
                                                reqs))))
         (re (and ids (concat "\\(?:\\`\\|[^A-Za-z0-9_-]\\)\\(" (regexp-opt ids) "\\)\\(?:\\'\\|[^A-Za-z0-9_-]\\)")))
         res)
    (when re
      (dolist (f (lemmax--lines (lemmax--git-out "ls-files" "*.org")))
        (when (file-readable-p f)
          (let ((n 0))
            (dolist (l (split-string (with-temp-buffer (insert-file-contents f) (buffer-string)) "\n"))
              (setq n (1+ n))
              (unless (string-match-p "\\`[ \t]*:\\(?:ID\\|NEEDS\\|ALIASES\\):" l)
                (let ((text (replace-regexp-in-string "\\[\\[id:[^]\n]*\\]\\(?:\\[[^]\n]*\\]\\)?\\]" " " l))
                      (pos 0))
                  (while (string-match re text pos)
                    (push (list f n (match-string 1 text)) res)
                    (setq pos (match-end 1))))))))))
    (nreverse res)))

;; lemma: RT-13
(defun lemmax-list (args)
  (let* ((opts (lemmax--list-opts args))
         (_ (when (plist-get opts :unlinked)
              (dolist (u (lemmax--unlinked)) (lemmax--out "%s:%d: %s" (nth 0 u) (nth 1 u) (nth 2 u)))
              (kill-emacs 0)))
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
        ;; lemma: 01a202f3-878b-75cb-98e0-9d7929ef88c1
        (princ (concat (json-encode
                        (list (cons 'version lemmax-json-version)
                              (cons 'rows (vconcat (cl-loop for (repo . rows) in per
                                                            append (mapcar (lambda (r) (lemmax--json-row r repo)) rows))))))
                       "\n"))
      (dolist (p per)
        (when (car p) (lemmax--out "== %s" (car p)))
        (lemmax--print-table (cdr p))
        (when (car p) (lemmax--out "")))
      (let ((all (cl-mapcan (lambda (p) (copy-sequence (cdr p))) per)))
        (let ((proofs (cl-count-if #'lemmax--proof-p all))
              (others (cl-loop for (k . p) in '(("task" . lemmax--task-p) ("note" . lemmax--note-p) ("axiom" . lemmax--axiom-p))
                               for n = (cl-count-if p all)
                               when (> n 0) concat (format "; %d %s%s" n k (if (= n 1) "" "s"))))
              (conj (cl-remove-if (lambda (r) (or (lemmax--proof-p r) (lemmax--unproven-p r))) all)))
          (lemmax--out "Total: %d requirement%s%s: %d open, %d done, %d dropped%s"
                       (length conj) (if (= 1 (length conj)) "" "s")
                       (if many (let ((n (length per))) (format " in %d repo%s" n (if (= n 1) "" "s"))) "")
                       (cl-count-if (lambda (r) (lemmax--open-p (plist-get r :state))) conj)
                       (cl-count-if (lambda (r) (lemmax--done-p (plist-get r :state))) conj)
                       (cl-count-if (lambda (r) (lemmax--dropped-p (plist-get r :state))) conj)
                       (concat (if (> proofs 0) (format "; %d proof%s" proofs (if (= proofs 1) "" "s")) "") others)))))
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

;; lemma: RT-14
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

;;;; install-hooks (01a20336-c6c6-7ac0-aea1-6d5ff12a8fea)

(defconst lemmax--hook-mark "# lemmax install-hooks wrote this hook."
  "The line that marks a hook as lemmax's, so a second install changes nothing.")

(defun lemmax--hook-text (name)
  "The hook NAME (pre-commit or commit-msg): lemmax from PATH, in a repo that
opts in, then the hook that was there before, kept as NAME.local."
  (concat "#!/usr/bin/env bash\n" lemmax--hook-mark "\n"
          "# lemmax " lemmax-version "; the hook that was here first is " name ".local, run after.\n"
          "if git grep --cached -q -E '^#\\+LEMMAX_TESTS:' -- '*.org' 2>/dev/null \\\n"
          "\t|| git cat-file -e :lemmax/config.eld 2>/dev/null; then\n"
          (if (equal name "pre-commit")
              "\tlemmax lint --staged --no-tests || exit 1\n"
            "\tlemmax commit-msg \"$1\" || exit 1\n")
          "fi\n"
          "chained=\"$(dirname \"$0\")/" name ".local\"\n"
          "if [ -x \"$chained\" ]; then exec \"$chained\" \"$@\"; fi\n"))

;; lemma: 01a20336-c6c6-7ac0-aea1-6d5ff12a8fea
(defun lemmax-install-hooks (args)
  "Write .git/hooks/pre-commit and commit-msg; the only lemmax command that writes."
  (when args (lemmax--err "lemmax: install-hooks takes no arguments") (kill-emacs 1))
  (let* ((git-dir (string-trim (or (lemmax--git-out "rev-parse" "--absolute-git-dir") "")))
         (dir (expand-file-name "hooks" git-dir)))
    (make-directory dir t)
    (dolist (name '("pre-commit" "commit-msg"))
      (let* ((file (expand-file-name name dir))
             (old (and (file-exists-p file) (with-temp-buffer (insert-file-contents file) (buffer-string)))))
        (cond
         ((and old (string-search lemmax--hook-mark old))
          (lemmax--out "%s: already lemmax's" name))
         (t
          (when old
            (rename-file file (concat file ".local") t)
            (lemmax--out "%s: kept the old hook as %s.local, run after lemmax" name name))
          (with-temp-file file (insert (lemmax--hook-text name)))
          (set-file-modes file #o755)
          (lemmax--out "%s: written" name)))))
    (let ((hp (lemmax--git-out "config" "core.hooksPath")))
      (when (and hp (not (string-empty-p (string-trim hp))))
        (lemmax--err "lemmax: core.hooksPath is %s, so git runs those hooks, not .git/hooks" (string-trim hp))))
    (kill-emacs 0)))

;;;; migrate (01a20369-391b-768e-8c98-180facc0ff77)

;; lemma: 01a20369-391b-768e-8c98-180facc0ff77
(defconst lemmax--migrate-states '(("OPEN" . "CONJECTURE") ("DROPPED" . "REFUTED")))
;; lemma: 01a203a6-a702-71c0-8239-e0d41380d2dd
(defvar lemmax--migrate-titles nil "With migrate --links, a hash id -> title; else nil.")
(defun lemmax--migrate-ref (id)
  "ID as migrate writes it: a [[id:ID][title]] link with --links, else bare."
  (let ((title (and lemmax--migrate-titles (gethash id lemmax--migrate-titles))))
    (if lemmax--migrate-titles (format "[[id:%s][%s]]" id (or title id)) id)))

(defun lemmax--migrate-chunk (chunk today file-lemma title uses-of)
  "CHUNK, one heading's text (or a file lemma's, with FILE-LEMMA and TITLE), in
the math names: (NEW-TEXT . PROOF), PROOF nil or the proof heading's text.
USES-OF maps an id to the ids that named it in :NEEDS:, its new :USES:."
  (let* ((lines (split-string chunk "\n"))
         (head (if file-lemma nil (car lines)))
         (rest (if file-lemma lines (cdr lines)))
         (id nil) (needs nil) (verify nil) (old-state nil) (in nil) out)
    (dolist (l rest)
      (cond ((string-match-p "\\`[ \t]*:PROPERTIES:[ \t]*\\'" l) (setq in t) (push l out))
            ((and in (string-match-p "\\`[ \t]*:END:[ \t]*\\'" l)) (setq in nil) (push l out))
            ((and in (string-match "\\`[ \t]*:VERIFY\\+?:[ \t]*\\(.*?\\)[ \t]*\\'" l))
             (setq verify (append verify (list (match-string 1 l)))))
            ;; :NEEDS: pointed child to parent; the parent gets :USES: instead.
            ((and in (string-match-p "\\`[ \t]*:NEEDS:" l)))
            ((and in (string-match "\\`[ \t]*:ID:[ \t]*\\(.*?\\)[ \t]*\\'" l))
             (setq id (match-string 1 l)) (push l out)
             (let ((u (gethash id uses-of)))
               (when u (setq needs t) (push (format ":USES:        %s" (mapconcat #'lemmax--migrate-ref u " ")) out))))
            ((and in file-lemma (string-match "\\`\\([ \t]*:STATE:[ \t]*\\)\\([A-Z]+\\)\\(.*\\)\\'" l))
             (setq old-state (match-string 2 l))
             (push (concat (match-string 1 l) "@STATE@" (match-string 3 l)) out))
            (t (push l out))))
    (setq out (nreverse out))
    (when (and head (string-match "\\`\\(\\*+ +\\)\\(OPEN\\|DONE\\|DROPPED\\)\\_>\\(.*\\)\\'" head))
      (setq old-state (match-string 2 head)))
    (if (null old-state)
        (cons chunk nil)
      (let* ((new (or (cdr (assoc old-state lemmax--migrate-states)) (if needs "THEOREM" "LEMMA")))
             (text (if file-lemma
                       (mapconcat (lambda (l) (string-replace "@STATE@" new l)) out "\n")
                     (concat (replace-regexp-in-string "\\`\\(\\*+ +\\)[A-Z]+" (concat "\\1" new) head t)
                             "\n" (mapconcat #'identity out "\n"))))
             (name (or title (and head (string-trim
                                        (replace-regexp-in-string
                                         "[ \t]+:[[:alnum:]_@#%:]+:[ \t]*\\'" ""
                                         (replace-regexp-in-string "\\`\\*+ +[A-Z]+ +\\(\\[#.\\] +\\)?" "" head))))))
             (proof (and verify id
                         (concat "* " (if (equal old-state "DONE") "PASSED" "OPEN") " Proof: " name "\n"
                                 ":PROPERTIES:\n"
                                 (format ":ID:          %s\n" (lemmax-uuid7))
                                 (format ":PROVES:      %s\n" (lemmax--migrate-ref id))
                                 (format ":TEST:        %s\n" (string-join verify " "))
                                 (format ":CREATED:     %s\n" today)
                                 (format ":LAST_EDITED: %s\n" today)
                                 ":END:\n"
                                 "When the tests in :TEST: pass, the conjecture holds.\n"))))
        (when (and verify (not id))
          (lemmax--err "lemmax: a heading with :VERIFY: and no :ID: keeps its :VERIFY:: %s" (or name "")))
        (when (and verify (not id))
          (setq text chunk))
        (cons text proof)))))

(defun lemmax--migrate-uses (chunks)
  "Hash: each parent id named in a :NEEDS: of CHUNKS to its children's ids, in
order; a parent no chunk holds is named on stderr."
  (let ((uses (make-hash-table :test #'equal)) (ids nil) (pairs nil))
    (dolist (c chunks)
      (let ((id (and (string-match "^[ \t]*:ID:[ \t]*\\(.*?\\)[ \t]*$" c) (match-string 1 c))))
        (when id
          (push id ids)
          (when (string-match "^[ \t]*:NEEDS:[ \t]*\\(.*?\\)[ \t]*$" c)
            (dolist (p (split-string (match-string 1 c)))
              (push (cons p id) pairs))))))
    (dolist (pr (nreverse pairs))
      (if (member (car pr) ids)
          (puthash (car pr) (append (gethash (car pr) uses) (list (cdr pr))) uses)
        (lemmax--err "lemmax: %s needs %s, which is not in this file; add :USES: %s to it by hand"
                     (cdr pr) (car pr) (cdr pr))))
    uses))

(defun lemmax--migrate-text (content file today)
  "CONTENT of FILE in the math names: (NEW-CONTENT . PROOFS-TEXT-or-nil)."
  (let* ((first (if (string-match "^\\*+ " content) (match-beginning 0) (length content)))
         (pre (substring content 0 first))
         (file-lemma (string-match-p "\\`\\(?:#[ \t].*\n\\|#\n\\|[ \t]*\n\\)*[ \t]*:PROPERTIES:" pre))
         (title (let ((case-fold-search t))
                  (and (string-match "^#\\+title:[ \t]*\\(.*\\)$" pre) (string-trim (match-string 1 pre)))))
         (proofs nil)
         (heads (lemmax--split-headings (substring content first)))
         (uses-of (lemmax--migrate-uses (if file-lemma (cons pre heads) heads)))
         (_ (when lemmax--migrate-titles
              (dolist (c heads)
                (when (string-match "^[ \t]*:ID:[ \t]*\\(.*?\\)[ \t]*$" c)
                  (let ((id (match-string 1 c)))
                    (puthash id (string-trim
                                 (replace-regexp-in-string
                                  "[ \t]+:[[:alnum:]_@#%:]+:[ \t]*\\'" ""
                                  (replace-regexp-in-string "\\`\\*+ +\\(?:[A-Z]+ +\\)?\\(\\[#.\\] +\\)?" ""
                                                            (car (split-string c "\n")))))
                             lemmax--migrate-titles))))))
         (pre-new (let ((r (if file-lemma (lemmax--migrate-chunk pre today t (or title file) uses-of) (cons pre nil))))
                    (when (cdr r) (push (cdr r) proofs))
                    (car r)))
         (chunks (mapcar (lambda (c) (let ((r (lemmax--migrate-chunk c today nil nil uses-of)))
                                       (when (cdr r) (push (cdr r) proofs))
                                       (car r)))
                         heads))
         (new (concat pre-new (apply #'concat chunks))))
    (setq new (replace-regexp-in-string "^#\\+TODO:.*\\_<OPEN\\_>.*$"
                                        "#+TODO: CONJECTURE(c) | LEMMA(l) THEOREM(t) REFUTED(r)" new t t))
    (cons new
          (and proofs
               (let ((kw (cl-loop for l in (split-string pre "\n")
                                  when (string-match-p "\\`#\\+\\(?:LEMMAX\\|REQTRACE\\)_\\(?:TESTS\\|CODE\\):" l)
                                  collect (concat l "\n"))))
                 (cons (concat "#+title: Proofs of " (or title (file-name-nondirectory file)) "\n"
                               "#+TODO: OPEN(o) | PASSED(p)\n"
                               (apply #'concat kw) "\n")
                       (string-join (nreverse proofs) "\n")))))))

(defun lemmax--diff (label old new)
  "A unified diff of OLD to NEW, both strings, under LABEL; OLD nil for a new file."
  (let ((a (make-temp-file "lemmax-a")) (b (make-temp-file "lemmax-b")))
    (unwind-protect
        (progn
          (with-temp-file a (insert (or old "")))
          (with-temp-file b (insert new))
          (with-temp-buffer
            (call-process "diff" nil t nil "-u" "-L" (if old label "/dev/null") "-L" label a b)
            (buffer-string)))
      (delete-file a) (delete-file b))))

(defun lemmax-migrate (args)
  "Print, or with --write make, FILE in the math names, with FILE.proofs.org."
  (let* ((write (member "--write" args))
         (_ (when (member "--links" args) (setq lemmax--migrate-titles (make-hash-table :test #'equal))))
         (bad (cl-find-if (lambda (a) (and (string-prefix-p "--" a) (not (member a '("--write" "--links"))))) args))
         (files (cl-remove-if (lambda (a) (string-prefix-p "--" a)) args)))
    (when bad (lemmax--err "lemmax: unknown option %s; see lemmax migrate --help" bad) (kill-emacs 1))
    (unless (= 1 (length files))
      (lemmax--err "lemmax: migrate takes one FILE; see lemmax migrate --help") (kill-emacs 1))
    (let* ((path (file-truename (expand-file-name (car files) (or lemmax--cwd default-directory))))
           (rel (file-relative-name path (file-truename default-directory))))
      (unless (and (file-readable-p path) (string-suffix-p ".org" path) (not (lemmax--proofs-file-p path)))
        (lemmax--err "lemmax: %s: not a readable requirements .org file" (car files)) (kill-emacs 1))
      (let* ((old (with-temp-buffer (insert-file-contents path) (buffer-string)))
             (res (lemmax--migrate-text old rel (lemmax--today)))
             (ppath (concat (file-name-sans-extension path) ".proofs.org"))
             (prel (file-relative-name ppath (file-truename default-directory)))
             (pold (and (file-exists-p ppath) (with-temp-buffer (insert-file-contents ppath) (buffer-string))))
             (pnew (and (cdr res) (concat (or pold (car (cdr res))) (if pold "\n" "") (cdr (cdr res))))))
        (if (not write)
            (progn
              (unless (equal old (car res)) (princ (lemmax--diff rel old (car res))))
              (when pnew (princ (lemmax--diff prel pold pnew))))
          (unless (equal old (car res))
            (with-temp-file path (insert (car res)))
            (lemmax--out "wrote %s" rel))
          (when pnew
            (with-temp-file ppath (insert pnew))
            (lemmax--out "wrote %s" prel)))
        (kill-emacs 0)))))

;;;; Help (RT-2)

(defconst lemmax--help
  '((main
     "usage: lemmax COMMAND [ARGS]
Lint, trace and list a repo's org requirements.
Commands: lint, commit-msg, trace, list, new-id, next-id, install-hooks, migrate, help
Run it inside a git repo, or name one with --project DIR (-p DIR).
It reads, and writes no file; install-hooks writes the repo's two hooks and
migrate --write a requirements file and its proofs file.
example: lemmax list --ready -p ~/repos/other-project"
     "Commands:
  lint [--staged] [--no-tests] [FILE...]  check the requirements files' rules
  commit-msg MSGFILE                      refuse a code commit that names no id
  trace [ID]                              each requirement's links, tests and commits
  list [filters] [--all] [--json]         every requirement in a table
  new-id                                  a new requirement id, a UUID v7
  next-id LETTER                          the next counted id, as M-15, for old projects
  install-hooks                           put lemmax in this repo's pre-commit and commit-msg
  migrate [--write] FILE                  move FILE to conjectures, proofs, lemmas and theorems
  help                                    this text
Each command takes -h, --help and help. lemmax --version prints the release.
Each command takes --project DIR (-p DIR): run on the git repo that holds DIR,
instead of the one here. list takes it more than once: one table each.
lint, commit-msg and trace read files whose header has #+LEMMAX_TESTS:, or
that lemmax/config.eld names, by folder:
  (:folders ((\"requirements/\" :tests \"CMD\" :code (\"src/\")
              :test-paths (\"tests/\") :markers-in (\"../code\"))))
A file takes the entry with the longest folder that holds it; a file with a
#+LEMMAX_* line of its own uses only its own header. The config is read as
data and never run. So lemmas may be headings in one file, or one per file.
A file whose top property drawer has :ID: is one lemma: #+title: is its
title and :STATE: its OPEN, DONE or DROPPED, or CONJECTURE, LEMMA, THEOREM or REFUTED.
A conjecture is proven by proofs: headings in FILE.proofs.org, OPEN or PASSED,
with :PROVES: IDS and :TEST: addresses. A LEMMA or THEOREM needs every proof
of it PASSED; a THEOREM's :USES: names the lemmas it uses.
Tasks, in FILE.tasks.org (TODO | DONE CANCELLED, :FOR: IDS), are dev chores;
notes, in FILE.notes.org (no state, :ABOUT: IDS), are text; an AXIOM heading
is a rule accepted without proof. None of the three needs a proof.
list and next-id read every requirements file: requirements.org, files under
a requirements/ folder, and files whose #+TODO names OPEN.
A finding is one line on stderr: lemmax: <file>:<line>: <id>: <why>; <fix>
Exit 0 when clean, 1 on any finding or failure.")
    (lint
     "usage: lemmax lint [--project DIR] [--staged] [--no-tests] [--json] [FILE...]
Check the requirements files' rules, in files that opt in.
example: lemmax lint --staged --no-tests"
     "--staged    read the staged copies and refuse changes against HEAD:
            a DONE requirement whose text changed, :LAST_EDITED: not today,
            a new requirement not dated today, a DONE one not :IMPLEMENTED: today
--no-tests  skip the test command and the :VERIFY: rule
--json      the findings on stdout as {"version": 1, "findings": [{file, line,
            id, why, fix}]}, none on stderr; the same exit code
FILE...     report findings for these files only
LEMMAX_TEST_SECONDS sets the test command's time (60 s); LEMMAX_TODAY sets today.")
    (commit-msg
     "usage: lemmax commit-msg [--project DIR] MSGFILE
Refuse a commit that changes code under #+LEMMAX_CODE: and names no requirement id.
example: lemmax commit-msg .git/COMMIT_EDITMSG"
     "The ids come from the staged requirements files, so one commit may add a
requirement and name it. Comment lines (#) do not count. An id matches as a
whole word: RQ-1 is not RQ-10.")
    (trace
     "usage: lemmax trace [--project DIR] [--run-tests] [--tag T]... [ID | --dot]
Print each requirement's parents, children, tests and commits.
example: lemmax trace RT-3"
     "With no ID: one block per requirement, then the orphan tests, which no
:VERIFY: names, then the suspect children: DONE requirements whose parent's
text changed in git after their :IMPLEMENTED: or :REVIEWED: day.
With an ID: that one block, and the files each of its commits touched.
An ID not in this project is looked for in every project under the repos
folder (the config's :repos, LEMMAX_REPOS, else ~/repos),
and shown under a project: line.
--run-tests: run the repo's test command, to check :VERIFY: and find orphan
tests; without it nothing of the repo's runs, and verify says unchecked.
--dot: the lemma graph in Graphviz's dot language, nodes filled by state,
:NEEDS: edges solid and id: link edges dashed: lemmax trace --dot | dot -Tsvg")
    (list
     "usage: lemmax list [--project DIR]... [--state open|done|dropped] [--section L] [--unchecked] [--unmarked] [--ready] [--duplicates] [--tag T]... [--unlinked] [--all] [--json] [--run-tests]
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
--duplicates  only lemmas whose id another lemma also has, in any file
--tag T       only headings tagged T or a tag under T in a #+TAGS: group;
              again for more, all of them
--unlinked    instead of the table, each FILE:LINE: ID where an .org file's text
              names a lemma id with no [[id:]] link; never a lint finding
--project DIR the git repo that holds DIR; give it again for more, one table each
--all         every git repo in the repos folder: the config's :repos,
              LEMMAX_REPOS, else ~/repos
--json        {"version": 1, "rows": [...]}: one object a row; version
              changes when a key or type of a row does
--run-tests   run the repo's test command for the check column; without it
              nothing of the repo's runs and the column says named
--no-tests    the default; kept so older calls still work")
    (new-id
     "usage: lemmax new-id
Print a new requirement id: a UUID v7, lower case.
example: lemmax new-id"
     "The first 12 hex digits are the time in milliseconds, so ids sort by age;
the rest is random from /dev/urandom. It needs no check against other ids.
next-id stays for projects whose old ids still count up.")
    (install-hooks
     "usage: lemmax install-hooks
Write this repo's .git/hooks/pre-commit and commit-msg to call lemmax from PATH.
example: lemmax install-hooks"
     "In a repo that opts in, pre-commit runs lint --staged --no-tests and
commit-msg runs commit-msg. A hook already there is kept as NAME.local and
run after lemmax's. Run again, it changes nothing. It is the one command
that writes, and it writes only those two files. If core.hooksPath is set,
git runs those hooks instead, and lemmax says so.")
    (migrate
     "usage: lemmax migrate [--project DIR] [--write] [--links] FILE
Move FILE to the math names: conjectures in FILE, proofs in FILE.proofs.org.
example: lemmax migrate requirements.org"
     "Without --write it prints a unified diff and writes nothing.
OPEN becomes CONJECTURE, DROPPED REFUTED, DONE THEOREM when it has children,
else LEMMA. :NEEDS: is inverted: a parent gets :USES: with its former
children, each child drops :NEEDS:, so a parent with children is a THEOREM;
the #+TODO: line names the new states.
Each :VERIFY: moves to a new proof with a UUID v7, :PROVES: the conjecture and
:TEST: the addresses: PASSED when it was DONE, else OPEN, dated today. The
proofs file takes FILE's #+LEMMAX_TESTS: and #+LEMMAX_CODE: lines. A lemma's
text, the statement, does not change, so nothing turns suspect.
--links writes :USES: and :PROVES: as [[id:ID][title]] links, not bare ids.")
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
(defvar lemmax--cwd nil "The folder lemmax was run in, before it moves to the repo root.")

;; lemma: RT-16
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
  (setq lemmax--cwd default-directory)
  (when (equal (car args) "--") (setq args (cdr args)))
  (let* ((cmd (car args))
         (rest (if (member cmd '(nil "-h" "--help" "help")) (cdr args) (lemmax--take-projects (cdr args)))))
    (when (and (cdr lemmax--projects) (not (equal cmd "list")))
      (lemmax--err "lemmax: %s takes one --project; list takes several" cmd)
      (kill-emacs 1))
    (cond
     ((member cmd '("--version" "-V")) (lemmax--out "lemmax %s" lemmax-version) (kill-emacs 0))
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
              ("install-hooks" (lemmax-install-hooks rest))
              ("migrate" (lemmax-migrate rest))
              (_ (lemmax--help-for 'main nil))))))))))

(when (and noninteractive (not (getenv "LEMMAX_LOAD_ONLY")))
  (condition-case err
      (lemmax-main (prog1 command-line-args-left (setq command-line-args-left nil)))
    (error (lemmax--err "lemmax: %s" (error-message-string err)) (kill-emacs 1))))

;;; lemmax.el ends here
