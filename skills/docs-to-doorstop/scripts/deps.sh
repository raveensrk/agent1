#!/usr/bin/env bash
# Check the tools docs-to-doorstop needs. Installs nothing.
# Usage: deps.sh
# Prints one line per tool: ok, or MISSING with the install command for this
# computer. Exit 0 when every required tool is there, 1 when one is missing.
# Required: git, python3, doorstop, PyYAML (for check.py).
# Optional (diagrams only): d2, mmdc with a headless Chrome, xmllint.
set -uo pipefail
case "${1:-}" in
  -h|--help) sed -n '2s/^# \{0,1\}//p' "$0"; exit 0;;
  help) sed -n '2,/^[^#]/s/^# \{0,1\}//p' "$0"; exit 0;;
esac

os=$(uname -s)
pm=none
if [ "$os" = Darwin ] && command -v brew >/dev/null; then pm=brew
elif command -v apt-get >/dev/null; then pm=apt
elif command -v dnf >/dev/null; then pm=dnf
elif command -v pacman >/dev/null; then pm=pacman
fi

# how TOOL -> install command for this computer
how() {
  case "$1:$pm" in
    git:brew) echo "brew install git";;
    git:apt) echo "sudo apt-get install -y git";;
    git:dnf) echo "sudo dnf install -y git";;
    git:pacman) echo "sudo pacman -S git";;
    python3:brew) echo "brew install python";;
    python3:apt) echo "sudo apt-get install -y python3 python3-venv pipx";;
    python3:dnf) echo "sudo dnf install -y python3 pipx";;
    python3:pacman) echo "sudo pacman -S python python-pipx";;
    doorstop:*) echo "pipx install doorstop   (no pipx: python3 -m pip install --user doorstop)";;
    pyyaml:*) echo "python3 -m pip install --user pyyaml   (or install doorstop, which brings it)";;
    d2:brew) echo "brew install d2";;
    d2:*) echo "curl -fsSL https://d2lang.com/install.sh | sh -s --";;
    mmdc:*) echo "npm install -g @mermaid-js/mermaid-cli && npx puppeteer browsers install chrome-headless-shell";;
    xmllint:brew) echo "brew install libxml2";;
    xmllint:apt) echo "sudo apt-get install -y libxml2-utils";;
    xmllint:dnf) echo "sudo dnf install -y libxml2";;
    xmllint:pacman) echo "sudo pacman -S libxml2";;
    *) echo "install $1 with this computer's package manager";;
  esac
}

missing=0
line() { # line required|optional TOOL OK?
  if [ "$3" = yes ]; then echo "ok        $2"
  else
    echo "MISSING   $2 ($1): $(how "$2")"
    [ "$1" = required ] && missing=1
  fi
}
has() { command -v "$1" >/dev/null && echo yes || echo no; }

line required git "$(has git)"
line required python3 "$(has python3)"
line required doorstop "$(has doorstop)"
here=$(cd "$(dirname "$0")" && pwd)
if [ "$(has python3)" = yes ] && python3 "$here/check.py" -h >/dev/null 2>&1; then
  line required pyyaml yes
else
  line required pyyaml no
fi
line optional d2 "$(has d2)"
mmdc_ok=no
if command -v mmdc >/dev/null; then
  t=$(mktemp -d)
  printf 'graph LR\n a-->b\n' >"$t/a.mmd"
  mmdc -q -i "$t/a.mmd" -o "$t/a.svg" >/dev/null 2>&1 && mmdc_ok=yes
  rm -rf "$t"
fi
line optional mmdc "$mmdc_ok"
line optional xmllint "$(has xmllint)"

[ "$pm" = none ] && echo "note: no known package manager found; install by hand."
exit $missing
