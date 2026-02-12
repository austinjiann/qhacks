#!/bin/bash
# Populate Firestore feed_pool with YouTube shorts + Kalshi market matches.
# Queries target topics that map to known Kalshi series (sports, crypto, indices).
# Requires the backend to be running on localhost:8000 (or set API_URL).
#
# Usage: ./scripts/populate.sh [max_videos_per_query]
#   e.g. ./scripts/populate.sh 50

set -e

API_URL="${API_URL:-http://localhost:8000}"
MAX_VIDEOS="${1:-50}"

QUERIES=(
  # # ── NFL / Super Bowl ──
  # "nfl highlights today"
  # "super bowl shorts"
  # "nfl best plays this week"
  # "nfl game winning plays"

  # # ── NBA ──
  # "nba highlights tonight"
  # "nba best dunks today"
  # "nba buzzer beaters"
  # "nba playoffs shorts"

  # # ── MLB / NHL / Soccer ──
  # "mlb highlights today"
  # "nhl highlights today"
  # "premier league highlights shorts"
  # "champions league goals shorts"

  # ── Tech / AI ──
  # "ai news today shorts"
  # "chatgpt news shorts"
  # "openai news shorts"
  # "nvidia news today shorts"
  # "apple news today shorts"
  "tesla news today shorts"
  "tech news today shorts"
  "silicon valley news shorts"

  # ── Music / Entertainment ──
  "drake new music shorts"
  "kendrick lamar shorts"
  # ── Music / Entertainment ──
  "travis scott shorts"
  "kanye west news shorts"
  "hip hop news today shorts"
  "rap beef shorts"
  "new music friday shorts"
  "grammys shorts"
  "music industry news shorts"

  # ── Pop Culture / Celebrities ──
  "celebrity news today shorts"
  "trending news today shorts"
  "viral moments shorts"
  "reality tv shorts"
  "movie trailer shorts"

  # ── Politics / World Events ──
  "trump news today shorts"
  "election 2026 shorts"
  "politics today shorts"
  "world news today shorts"
  "breaking news shorts"

  # ── Economy / Business ──
  "inflation news today shorts"
  "fed rate decision shorts"
  "recession news shorts"
  "elon musk news shorts"
  "billionaire news shorts"

  # ── Weather / Climate ──
  "extreme weather shorts"
  "hurricane news shorts"
  "wildfire news shorts"
  "weather report shorts"
  "snowfall shorts"

  # ── Gaming / Internet Culture ──
  "gaming news today shorts"
  "fortnite news shorts"
  "twitch drama shorts"
  "youtube drama shorts"
  "internet drama shorts"

    # ── NFL / Super Bowl ──
  "nfl highlights today"
  "super bowl shorts"
  "nfl best plays this week"
  "nfl game winning plays"

  # ── NBA ──
  "nba highlights tonight"
  "nba best dunks today"
  "nba buzzer beaters"
  "nba playoffs shorts"

  # ── MLB / NHL / Soccer ──
  "mlb highlights today"
  "nhl highlights today"
  "premier league highlights shorts"
  "champions league goals shorts"
)

echo "Populating feed pool via $API_URL..."
echo "Max videos per query: $MAX_VIDEOS"
echo "Queries: ${#QUERIES[@]}"
echo ""

TOTAL=0
for query in "${QUERIES[@]}"; do
  encoded=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$query")
  echo "[$((TOTAL))+ ] Crawling: '$query'..."
  RESULT=$(curl -s -X POST "$API_URL/admin/crawl?query=${encoded}&max_videos=$MAX_VIDEOS")
  ADDED=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('videos_added',0))" 2>/dev/null || echo "0")
  echo "  → Added: $ADDED"
  TOTAL=$((TOTAL + ADDED))
  sleep 1
done

echo ""
echo "Done. Total videos added: $TOTAL"
echo ""
echo "Pool stats:"
curl -s "$API_URL/pool/stats" | python3 -m json.tool
