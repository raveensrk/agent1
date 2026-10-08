.PHONY: html

html: dist/agent1.html

dist/agent1.html: model_and_harness.yaml publish.lua publish.css publish_check.sh
	@mkdir -p $(@D)
	pandoc -f markdown -t html5 -s --embed-resources --css publish.css \
	  --metadata-file model_and_harness.yaml --lua-filter publish.lua /dev/null -o $@
	./publish_check.sh $@
