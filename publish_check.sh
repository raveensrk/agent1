#!/bin/bash
# publish_check.sh - fail when the built page lost a section or gained a leak.
#
#   publish_check.sh PAGE      check PAGE (make html runs it on dist/agent1.html)
#   publish_check.sh -h|--help
#
# The page must be one standalone file: its title, the inlined publish.css, and
# the anchors the table of contents links to; no private usage history, no
# link to another HTML file, no author metadata, no external asset.
set -euo pipefail

case "${1:-}" in
  -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  '') echo "usage: publish_check.sh PAGE" >&2; exit 2 ;;
esac
page=$1

for needle in '<!DOCTYPE html>' '</html>' '<title>Models &amp; Harness Reviews</title>' \
  '<style>' '--bg: #111416;' \
  'id="rating-scale"' 'href="#rating-scale"' \
  'id="models"' 'href="#models"' \
  'id="harness"' 'href="#harness"'; do
  grep -qF -- "$needle" "$page" || { echo "$page: missing: $needle" >&2; exit 1; }
done

leak='model_usage_history|href="[^"#]+\.html"|<meta name="author"|<link[ >]|<script[ >]|@import|url\('
if grep -nE "$leak" "$page" >&2; then
  echo "$page: private history, a link to another HTML file, author metadata or an external asset" >&2
  exit 1
fi
