#!/usr/bin/env bash
# Download all monthly QuakeScope XL pick files (2012-06 .. 2016-06), ~3-4 MB each.
set -uo pipefail
cd "$(dirname "$0")/../data/reference/quakescope" 2>/dev/null || { mkdir -p "$(dirname "$0")/../data/reference/quakescope"; cd "$(dirname "$0")/../data/reference/quakescope"; }
for y in 2012 2013 2014 2015 2016; do for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
  ym="$y$m"; [ "$ym" -lt 201206 ] || [ "$ym" -gt 201606 ] && continue
  f="XL_${y}_${m}.parquet"; [ -s "$f" ] && continue
  code=$(curl -sL -m 600 -o "$f.part" -w "%{http_code}" "https://dasway.ess.washington.edu/quakescope/data/picks/network=XL/year=$y/month=$m/docdb2025-XL.parquet")
  if [ "$code" = "200" ]; then mv "$f.part" "$f"; echo "$f ok"; else rm -f "$f.part"; echo "$f HTTP $code"; fi
done; done
