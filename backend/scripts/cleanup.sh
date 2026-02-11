#!/bin/bash
# Remove stale items from the feed pool.
#
# Usage: ./scripts/cleanup.sh [max_age_hours]
#   e.g. ./scripts/cleanup.sh 48

set -e

API_URL="${API_URL:-http://localhost:8000}"
MAX_AGE_HOURS="${1:-48}"

echo "Cleaning up items older than ${MAX_AGE_HOURS}h via $API_URL..."
curl -s -X POST "$API_URL/admin/cleanup?max_age_hours=$MAX_AGE_HOURS" | python3 -m json.tool
