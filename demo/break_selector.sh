#!/usr/bin/env bash
# Demo: the site "changes its layout" (we simulate it by breaking one CSS selector in a COPY of the
# config), and the scraper says so instead of quietly returning nothing.
#   demo/break_selector.sh list    breaks the selector for the meeting list  (default)
#   demo/break_selector.sh page    breaks the selector for agenda items on a meeting page
set -euo pipefail
cd "$(dirname "$0")/.."
KV=".venv/bin/kildevagt"
WHAT="${1:-list}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp sources/*.yaml "$TMP"/

if [ "$WHAT" = "list" ]; then
  sed -i 's/^item_link: .*/item_link: a.list__link-REDESIGNED/' "$TMP/hedensted.yaml"
else
  sed -i 's/agenda_item: \.accordion__item/agenda_item: .accordion__item-REDESIGNED/' "$TMP/hedensted.yaml"
fi

echo "== 1. Normal run (real config)"
$KV run --source hedensted
echo
echo "== 2. The site changes: '$WHAT' selector no longer matches"
$KV --sources-dir "$TMP" run --source hedensted --force --max-requests 30 || echo "(exit code $?: a script or cron job would notice this)"
echo
echo "== 3. Status"
$KV status || true
echo
echo "== 4. Selector fixed again"
$KV run --source hedensted
