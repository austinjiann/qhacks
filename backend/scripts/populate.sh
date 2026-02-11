#!/bin/bash
# Populate Firestore feed_pool with YouTube shorts + Kalshi market matches.
# Requires the backend to be running on localhost:8000 (or set API_URL).
#
# Usage: ./scripts/populate.sh [max_videos_per_query]
#   e.g. ./scripts/populate.sh 5

set -e

API_URL="${API_URL:-http://localhost:8000}"
MAX_VIDEOS="${1:-5}"

QUERIES=(
  "trending shorts"
  "sports highlights shorts"
  "crypto news shorts"
  "stock market shorts"
  "nfl shorts"
  "nba shorts"
  "weather news shorts"
  "politics shorts"
)

echo "Populating feed pool via $API_URL..."
echo "Max videos per query: $MAX_VIDEOS"
echo ""

TOTAL=0
for query in "${QUERIES[@]}"; do
  encoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$query'))")
  echo "Crawling: '$query'..."
  RESULT=$(curl -s -X POST "$API_URL/admin/crawl?query=${encoded}&max_videos=$MAX_VIDEOS")
  ADDED=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('videos_added',0))" 2>/dev/null || echo "0")
  echo "  Added: $ADDED"
  TOTAL=$((TOTAL + ADDED))
  sleep 2
done

echo ""
echo "Done. Total videos added: $TOTAL"
echo ""
echo "Pool stats:"
curl -s "$API_URL/pool/stats" | python3 -m json.tool
