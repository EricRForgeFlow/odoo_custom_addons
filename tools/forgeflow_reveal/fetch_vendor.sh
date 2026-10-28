#!/bin/bash
# Download the pinned third-party files of the template into vendor/:
# reveal.js (MIT) and the Inter font (SIL Open Font License), so a deck works
# offline (presenting, printing to PDF, recording a video).
#
#   tools/forgeflow_reveal/fetch_vendor.sh
set -e
cd "$(dirname "$0")"
REVEAL=5.1.0
FONTSOURCE=5.1.0
CDN=https://cdn.jsdelivr.net/npm
mkdir -p vendor/reveal.js/plugin/notes vendor/inter
for f in dist/reveal.js dist/reveal.css dist/reset.css plugin/notes/notes.js LICENSE; do
  mkdir -p "vendor/reveal.js/$(dirname "$f")"
  curl -fsSL "$CDN/reveal.js@$REVEAL/$f" -o "vendor/reveal.js/$f"
done
for w in 400 500 600 700 800; do
  curl -fsSL "$CDN/@fontsource/inter@$FONTSOURCE/files/inter-latin-$w-normal.woff2" \
    -o "vendor/inter/inter-latin-$w-normal.woff2"
done
curl -fsSL "$CDN/@fontsource/inter@$FONTSOURCE/LICENSE" -o vendor/inter/LICENSE
echo "reveal.js $REVEAL and Inter ($FONTSOURCE) in $(pwd)/vendor"
