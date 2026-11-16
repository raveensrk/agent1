#!/bin/sh
# Render ishikari.d2 to light and dark SVGs with the TALA layout.
set -eu
cd "$(dirname "$0")"
d2 --layout=tala ishikari.d2 "${1:-ishikari.svg}"
tmp=$(mktemp -t ishikari-dark)
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
d2 --layout=tala --theme=200 "$tmp.d2" "${2:-ishikari-dark.svg}"
rm -f "$tmp" "$tmp.d2"
