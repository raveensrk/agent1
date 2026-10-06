.PHONY: html

html: dist/agent1.html

dist/agent1.html: publish.org publish.css publish.el model.org harness.org
	emacs --batch -Q --load publish.el --funcall agent1-publish-export
