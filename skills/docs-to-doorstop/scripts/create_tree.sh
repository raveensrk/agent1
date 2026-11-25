#!/usr/bin/env bash
# Create the ASPICE 4.0 Doorstop tree in REQS_DIR. Safe to run once only.
# Usage: create_tree.sh REQS_DIR
set -euo pipefail
case "${1:-}" in
  -h|--help) sed -n '2s/^# \{0,1\}//p' "$0"; exit 0;;
  help) sed -n '2,/^[^#]/s/^# \{0,1\}//p' "$0"; exit 0;;
esac

reqs=${1:?usage: create_tree.sh REQS_DIR}
mkdir -p "$reqs"
cd "$reqs"

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  git init -q
fi
here=$(pwd -P)
root=$(git rev-parse --show-toplevel)
if [ -e SYS1/.doorstop.yml ]; then
  echo "ERROR: tree already exists in $here. This is an update run." >&2
  exit 1
fi
if find "$root" -name .git -prune -o -name .doorstop.yml -not -path "$here/*" -print 2>/dev/null | grep -q .; then
  echo "ERROR: $root already holds a Doorstop tree outside $here." >&2
  echo "Doorstop allows one root document per repo. Ask the user." >&2
  exit 1
fi

# prefix:parent, in creation order (a parent before its children).
docs="SYS1: SYS2:SYS1 SYS3:SYS2 SYS4:SYS3 SYS5:SYS2
HWE1:SYS3 HWE2:HWE1 HWE3:HWE2 HWE4:HWE1
SWE1:SYS3 SWE2:SWE1 SWE3:SWE2 SWE4:SWE3 SWE5:SWE2 SWE6:SWE1"

for d in $docs; do
  prefix=${d%%:*}
  parent=${d#*:}
  # --sep - : prefixes end in a digit; the default empty sep breaks UIDs.
  doorstop create "$prefix" "./$prefix" --sep - ${parent:+--parent "$parent"} >/dev/null
  cat >>"$prefix/.doorstop.yml" <<'EOF'
attributes:
  defaults:
    status: draft
    priority: must
  publish:
  - status
  - priority
  - rationale
  - verification
  - source
EOF
done
echo "created 15 documents in $here (git root: $root)"
