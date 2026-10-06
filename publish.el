;;; publish.el --- Export the model and harness journals as one HTML page -*- lexical-binding: nil; -*-

(require 'ox-html)

(defconst agent1-publish-root
  (file-name-directory (expand-file-name (or load-file-name buffer-file-name))))

(defun agent1-publish--link (link backend _info)
  "Point links between included Org files at anchors in this page."
  (if (not (eq backend 'html))
      link
    (cond
     ((string-match-p "href=\"[^\"]*model\\.html#model-rating-scale\"" link)
      (replace-regexp-in-string "href=\"[^\"]*model\\.html#model-rating-scale\"" "href=\"#model-rating-scale\"" link t t))
     ((string-match-p "href=\"[^\"]*harness\\.html\"" link)
      (replace-regexp-in-string "href=\"[^\"]*harness\\.html\"" "href=\"#harness\"" link t t))
     ((string-match-p "href=\"[^\"]*model\\.html\"" link)
      (replace-regexp-in-string "href=\"[^\"]*model\\.html\"" "href=\"#models\"" link t t))
     (t link))))

(defun agent1-publish--paragraph (paragraph backend _info)
  "Drop the private usage-history link from this export."
  (if (and (eq backend 'html)
           (string-match-p "model_usage_history\\.html" paragraph))
      ""
    paragraph))

(defun agent1-publish-export ()
  "Export publish.org to dist/agent1.html and check the standalone output."
  (interactive)
  (let* ((out (expand-file-name "dist/agent1.html" agent1-publish-root))
         (css (with-temp-buffer
                (insert-file-contents (expand-file-name "publish.css" agent1-publish-root))
                (buffer-string)))
         (org-html-head (concat "<style>\n" css "\n</style>"))
         (org-html-doctype "html5")
         (org-html-html5-fancy t)
         (org-html-head-include-default-style nil)
         (org-html-head-include-scripts nil)
         (org-html-validation-link nil)
         (org-html-preamble nil)
         (org-html-postamble nil)
         (org-html-link-org-files-as-html t)
         (org-export-exclude-tags (cons "publish_hide" org-export-exclude-tags))
         (org-export-with-author nil)
         (org-export-with-email nil)
         (org-export-with-date nil)
         (org-export-with-creator nil)
         (org-export-time-stamp-file nil)
         (org-export-filter-link-functions
          (cons #'agent1-publish--link org-export-filter-link-functions))
         (org-export-filter-paragraph-functions
          (cons #'agent1-publish--paragraph org-export-filter-paragraph-functions)))
    (make-directory (file-name-directory out) t)
    (with-current-buffer (find-file-noselect (expand-file-name "publish.org" agent1-publish-root))
      (org-export-to-file 'html out))
    (with-temp-buffer
      (insert-file-contents out)
      (let ((html (buffer-string)))
        (dolist (needle '("<!DOCTYPE html>" "</html>" "<title>Models &amp; Harness Reviews</title>"
                         "<style>" "--bg: #111416;"
                         "id=\"models\"" "href=\"#models\""
                         "id=\"harness\"" "href=\"#harness\""
                         "id=\"model-rating-scale\"" "href=\"#model-rating-scale\""))
          (unless (string-match-p (regexp-quote needle) html)
            (error "HTML is missing expected content: %s" needle)))
        (when (string-match-p "model_usage_history\\|href=\"[^\"]+\\.html\"" html)
          (error "HTML contains private history or a link to another HTML file"))
        (when (string-match-p "<meta name=\"author\"\\|<link\\b\\|<script\\b\\|@import\\|url(" html)
          (error "HTML contains author metadata or an external asset"))))
    (message "Wrote %s" out)))

(provide 'agent1-publish)
;;; publish.el ends here
