;;; emacs.el --- One agenda line for scripts/todo doing -*- lexical-binding: t; -*-

;; The skill picks the task. This file only draws it.
;; Today is the skill's today, midnight IST, not `org-extend-today-until'.
;; ~/dot loads this when the repo is present. A shell `agenda2` loads it directly.

(require 'cl-lib)
(require 'org-agenda)

(defconst todo-emacs-root
  (file-name-directory (or load-file-name buffer-file-name))
  "Directory of this file, the todo skill root.")

(setq org-agenda-window-setup 'only-window
      org-agenda-restore-windows-after-quit t)

(defvar todo-doing-rebuilding nil)
(defvar-local todo-doing-marker nil)
(defvar-local todo-doing-stamp nil)

(defun todo-doing-task ()
  "The task `scripts/todo doing --json' returns, or nil."
  (let* ((cli (expand-file-name "scripts/todo" todo-emacs-root))
         (buf (generate-new-buffer " *doing*"))
         (err (make-temp-file "doing-err"))
         status)
    (unwind-protect
        (progn
          (setq status (call-process cli nil (list buf err) nil "--warm" "doing" "--json"))
          (with-current-buffer buf
            (if (not (eq status 0))
                (error "%s" (string-trim
                             (concat (buffer-string)
                                     (with-temp-buffer
                                       (insert-file-contents err)
                                       (buffer-string)))))
              (let ((parsed (json-parse-string (buffer-string)
                                               :object-type 'alist
                                               :null-object nil
                                               :false-object nil)))
                (and (consp parsed) parsed)))))
      (delete-file err)
      (kill-buffer buf))))

(defun todo-doing-item (task)
  "One agenda item string for TASK."
  (let* ((file (alist-get 'path task))
         (title (alist-get 'title task))
         (deadline (alist-get 'deadline task))
         (day (calendar-gregorian-from-absolute (org-time-string-to-absolute deadline))))
    (let ((org-agenda-buffer (and (buffer-live-p org-agenda-buffer) org-agenda-buffer)))
      (org-compile-prefix-format 'agenda))
    (let ((item (cl-find-if
                 (lambda (text)
                   (let ((marker (get-text-property 0 'org-hd-marker text)))
                     (and marker
                          (equal title (org-with-point-at marker
                                         (org-get-heading t t t t))))))
                 (org-agenda-get-day-entries file day :deadline))))
      (unless item (error "No agenda line for %s" title))
      item)))

(defun todo-doing-stamp (marker)
  "Heading, state, deadline, and tags at MARKER, or nil."
  (when (and marker (marker-buffer marker))
    (org-with-point-at marker
      (list (org-get-todo-state)
            (org-entry-get nil "DEADLINE")
            (org-get-tags nil t)
            (buffer-substring-no-properties (line-beginning-position) (line-end-position))))))

(defun todo-doing-watch ()
  "Rebuild Doing when the shown heading changes."
  (when (and (not todo-doing-rebuilding)
             todo-doing-stamp
             (not (equal (todo-doing-stamp todo-doing-marker) todo-doing-stamp)))
    (agenda2)))

(defun todo-doing-show (task)
  "Show TASK in *Doing*. TASK is an alist, nil, or (error . MESSAGE)."
  (let ((org-agenda-sticky nil)
        (buf (get-buffer-create "*Doing*")))
    (org-agenda-prepare-window buf nil)
    (with-current-buffer buf
      (let ((inhibit-read-only t))
        (erase-buffer)
        (org-agenda-mode)
        (setq org-agenda-buffer buf)
        (setq-local org-agenda-name "Doing")
        (setq-local org-agenda-type 'agenda)
        (setq-local org-agenda-redo-command '(agenda2))
        (cond
         ((eq (car-safe task) 'error)
          (insert (cdr task) "\n"))
         ((null task)
          (insert "No main quest\n"))
         (t
          (insert (todo-doing-item task) "\n")
          (org-agenda-finalize)))
        (goto-char (point-min))
        (add-text-properties (point-min) (line-end-position)
                             (list 'org-redo-cmd '(agenda2)))
        (setq buffer-read-only t)
        (setq-local todo-doing-marker (org-get-at-bol 'org-hd-marker))
        (setq-local todo-doing-stamp (todo-doing-stamp todo-doing-marker))
        (add-hook 'post-command-hook #'todo-doing-watch nil t)))))

(defun agenda2 ()
  "Show the task `scripts/todo doing' picks, as one agenda line."
  (interactive)
  (let ((todo-doing-rebuilding t))
    (todo-doing-show
     (condition-case err
         (todo-doing-task)
       (error (cons 'error (error-message-string err)))))))

(provide 'todo-emacs)
;;; emacs.el ends here
