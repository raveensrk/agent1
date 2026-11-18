#!/bin/sh
# Render ishikari.d2 to light and dark SVGs with the TALA layout.
set -eu
cd "$(dirname "$0")"
tmp=$(mktemp "${TMPDIR:-/tmp}/ishikari-dark.XXXXXX")
pids=""
light=""
trap 'rm -f "$tmp" "$tmp.d2"' EXIT
# On interrupt, stop the background renders too.
trap 'kill $light $pids 2>/dev/null; exit 1' INT TERM HUP
fail=0
# Light render; flow.py reads its output.
d2 --layout=tala ishikari.d2 "${1:-ishikari.svg}" &
light=$!
sed -e 's/plan-fill: "#DBEAFE"/plan-fill: "#172554"/' \
    -e 's/plan-line: "#2563EB"/plan-line: "#60A5FA"/' \
    -e 's/build-fill: "#DCFCE7"/build-fill: "#052E16"/' \
    -e 's/build-line: "#16A34A"/build-line: "#4ADE80"/' \
    -e 's/check-fill: "#FEF3C7"/check-fill: "#451A03"/' \
    -e 's/check-line: "#D97706"/check-line: "#FBBF24"/' \
    -e 's/fix-fill: "#FFE4E6"/fix-fill: "#4C0519"/' \
    -e 's/fix-line: "#E11D48"/fix-line: "#FB7185"/' \
    -e 's/finish-fill: "#EDE9FE"/finish-fill: "#2E1065"/' \
    -e 's/finish-line: "#7C3AED"/finish-line: "#A78BFA"/' \
    -e 's/always-fill: "#F1F5F9"/always-fill: "#1E293B"/' \
    -e 's/always-line: "#64748B"/always-line: "#94A3B8"/' \
    -e 's/node-fill: "#FFFFFF"/node-fill: "#0F172A"/' \
    -e 's/text: "#0F172A"/text: "#E2E8F0"/' \
    -e 's/bug: "#DC2626"/bug: "#F87171"/' \
    -e 's/ok: "#16A34A"/ok: "#4ADE80"/' \
    -e 's/flow: "#475569"/flow: "#CBD5E1"/' \
    ishikari.d2 > "$tmp.d2"
d2 --layout=tala --theme=200 "$tmp.d2" "${2:-ishikari-dark.svg}" &
pids="$pids $!"
if [ $# -eq 0 ]; then
    # Slow animated walk through the stages, 6 s a frame.
    d2 --layout=tala --animate-interval=6000 ishikari-animated.d2 ishikari-animated.svg &
    pids="$pids $!"
    # Full dark animated diagram, hand laid out.
    python3 journey.py &
    pids="$pids $!"
    # Subway map view.
    python3 metro.py &
    pids="$pids $!"
    # Readable subway map view.
    python3 metro-clean.py &
    pids="$pids $!"
fi
wait "$light" || fail=1
if [ $# -eq 0 ] && [ "$fail" -eq 0 ]; then
    # Car tour along the exact path, built from ishikari.svg.
    python3 flow.py &
    pids="$pids $!"
fi
for pid in $pids; do
    wait "$pid" || fail=1
done
exit "$fail"
