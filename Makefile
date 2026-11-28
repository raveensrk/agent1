.PHONY: html

html: books/model_reviews.html

books/model_reviews.html: docs/notes/model_and_harness.yaml scripts/publish.lua scripts/publish.css scripts/publish_check.sh
	@mkdir -p $(@D)
	pandoc -f markdown -t html5 -s --embed-resources --css scripts/publish.css \
	  --metadata-file docs/notes/model_and_harness.yaml --lua-filter scripts/publish.lua /dev/null -o $@
	scripts/publish_check.sh $@
