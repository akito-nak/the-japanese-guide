#!/usr/bin/env bash
#
# build-pdf.sh — Assemble the entire Japanese Guide into a single PDF with pandoc.
#
# Reads scripts/pages.txt (written by generate-nav.py) so the PDF follows the
# exact same reading order as the on-page navigation. Per-page nav footers are
# stripped before conversion, since their relative links are meaningless inside
# one combined document.
#
# PDF engine is auto-detected: xelatex (best CJK/Japanese typography) is
# preferred, then wkhtmltopdf, then weasyprint. Override with PDF_ENGINE=...
#
# Usage:
#   ./scripts/build-pdf.sh                 # -> the-japanese-guide.pdf
#   ./scripts/build-pdf.sh my-output.pdf   # custom output path
#   PDF_ENGINE=weasyprint ./scripts/build-pdf.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$SCRIPT_DIR/pages.txt"
OUTPUT="${1:-$REPO_ROOT/the-japanese-guide.pdf}"

cd "$REPO_ROOT"

# --- preflight ------------------------------------------------------------
if ! command -v pandoc >/dev/null 2>&1; then
  echo "error: pandoc is not installed." >&2
  echo "  macOS:  brew install pandoc" >&2
  echo "  Debian: sudo apt-get install pandoc" >&2
  exit 1
fi

if [[ ! -f "$MANIFEST" ]]; then
  echo "error: $MANIFEST not found. Run: python3 scripts/generate-nav.py" >&2
  exit 1
fi

# --- pick a PDF engine ----------------------------------------------------
pick_engine() {
  if [[ -n "${PDF_ENGINE:-}" ]]; then echo "$PDF_ENGINE"; return; fi
  for e in xelatex wkhtmltopdf weasyprint; do
    if command -v "$e" >/dev/null 2>&1; then echo "$e"; return; fi
  done
  return 1
}

if ! ENGINE="$(pick_engine)"; then
  echo "error: no PDF engine found. Install one of:" >&2
  echo "  xelatex     -> brew install --cask mactex   (best for Japanese text)" >&2
  echo "  wkhtmltopdf -> brew install wkhtmltopdf" >&2
  echo "  weasyprint  -> pip install weasyprint" >&2
  exit 1
fi
echo "Using PDF engine: $ENGINE"

# --- pick a font that covers BOTH Japanese and macron romaji (ō, ū) ---------
# A single Unicode-wide font avoids needing the xeCJK LaTeX package. Override
# with PDF_MAINFONT=...  Only used by the xelatex engine; HTML engines fall
# back to system/CSS fonts.
pick_font() {
  if [[ -n "${PDF_MAINFONT:-}" ]]; then echo "$PDF_MAINFONT"; return; fi
  for font in "Arial Unicode MS" "Hiragino Sans" "Noto Sans CJK JP"; do
    if fc-list 2>/dev/null | grep -qi "$font"; then echo "$font"; return; fi
  done
  echo "Arial Unicode MS"  # last-resort default; pandoc will warn if absent
}
MAINFONT="$(pick_font)"
echo "Using main font: $MAINFONT"

# --- assemble a combined markdown source ----------------------------------
# Strip the generated nav-footer blocks from each page, then concatenate in
# manifest order with page breaks between sections.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
COMBINED="$WORK/combined.md"
: > "$COMBINED"

# Title page metadata (consumed by pandoc).
cat > "$COMBINED" <<'EOF'
---
title: "The Japanese Guide"
subtitle: "Fun. Comprehensive. Yours."
date: ""
lang: en
mainfont: "MAINFONT_PLACEHOLDER"
monofont: "MAINFONT_PLACEHOLDER"
geometry: margin=1in
toc: true
toc-depth: 2
---

EOF

# Substitute the detected main font into the metadata block.
TMP_HEADER="$WORK/header.md"
sed "s/MAINFONT_PLACEHOLDER/${MAINFONT//\//\\/}/" "$COMBINED" > "$TMP_HEADER"
mv "$TMP_HEADER" "$COMBINED"

count=0
while IFS= read -r page; do
  [[ -z "$page" ]] && continue
  if [[ ! -f "$page" ]]; then
    echo "warning: listed page not found, skipping: $page" >&2
    continue
  fi
  # Drop everything from the nav-footer marker onward, then strip color emoji
  # (the PDF font has no emoji glyphs and xelatex can't embed Apple's color
  # bitmap emoji). Emoji stay in the source .md files for web/GitHub rendering;
  # box-drawing (─━│) and circled numbers (①②) are intentionally NOT stripped.
  awk '/<!-- nav-footer:start -->/{exit} {print}' "$page" \
    | perl -CSD -pe 's/[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{FE0F}]//g' \
    >> "$COMBINED"
  # Force a page break between top-level sections.
  printf '\n\n\\newpage\n\n' >> "$COMBINED"
  count=$((count + 1))
done < "$MANIFEST"

echo "Combined $count pages."

# --- convert --------------------------------------------------------------
PANDOC_ARGS=(
  "$COMBINED"
  -o "$OUTPUT"
  --pdf-engine="$ENGINE"
  --from=gfm
  --standalone
)

# CJK font handling differs per engine. For xelatex, a Japanese-capable main
# font is set via the YAML metadata above (Hiragino Sans ships with macOS).
echo "Building: $OUTPUT"
if pandoc "${PANDOC_ARGS[@]}"; then
  echo "✓ Done: $OUTPUT"
else
  echo "error: pandoc failed. If this is a font error with xelatex, install a" >&2
  echo "Japanese font or set one via: --metadata mainfont='Noto Sans CJK JP'." >&2
  exit 1
fi
