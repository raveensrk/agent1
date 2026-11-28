.PHONY: html

html: dist/agent1.html

dist/agent1.html: docs/notes/model_and_harness.yaml script/publish.lua script/publish.css script/publish_check.sh
	@mkdir -p $(@D)
	pandoc -f markdown -t html5 -s --embed-resources --css script/publish.css \
	  --metadata-file docs/notes/model_and_harness.yaml --lua-filter script/publish.lua /dev/null -o $@
	script/publish_check.sh $@
