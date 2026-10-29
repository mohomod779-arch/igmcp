#!/usr/bin/env bash
# Pull freekit2 media + lifetime insights through the igmcp server (read-only).
# Usage: ig_report.sh [N_posts]   Output: one table row per post (TSV-like).
# Needs: run from a container on the same Docker network as the server (Docker DNS), secrets/mcp_auth_token.
set -euo pipefail
cd "$(dirname "$0")/.."
N="${1:-10}"
B="${IGMCP_URL:-http://instagram-mcp:8000/mcp}"
T="$(cat secrets/mcp_auth_token)"
H=(-H "Authorization: Bearer $T" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream')

call() { # $1 = tool name, $2 = arguments json
  curl -s -m 40 "${H[@]}" -X POST "$B" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"$1\",\"arguments\":$2}}" \
    | jq -r '.result.content[0].text // (.error.message // "ERR")'
}

call get_instagram_profile '{}' | jq -r '"account: @\(.username)  followers=\(.followers_count)  following=\(.follows_count)  posts=\(.media_count)"'
printf 'date\ttype\treach\tviews\tlikes\tcomments\tshares\tsaved\tavg_watch_ms\tpermalink\n'
call list_instagram_media "{\"limit\":$N}" | jq -c '.items[]' | while read -r row; do
  id=$(jq -r .id <<<"$row"); type=$(jq -r .media_product_type <<<"$row")
  metrics='["reach","views","likes","comments","shares","saved"]'
  [ "$type" = "REELS" ] && metrics='["reach","views","likes","comments","shares","saved","ig_reels_avg_watch_time"]'
  ins=$(call get_instagram_insights "{\"media_id\":\"$id\",\"metrics\":$metrics,\"period\":\"lifetime\"}" \
        | jq -c '[.items[]?|{(.name):.value}]|add // {}')
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$(jq -r '.timestamp[:10]' <<<"$row")" "$type" \
    "$(jq -r '.reach // "-"' <<<"$ins")" "$(jq -r '.views // "-"' <<<"$ins")" \
    "$(jq -r '.likes // "-"' <<<"$ins")" "$(jq -r '.comments // "-"' <<<"$ins")" \
    "$(jq -r '.shares // "-"' <<<"$ins")" "$(jq -r '.saved // "-"' <<<"$ins")" \
    "$(jq -r '.ig_reels_avg_watch_time // "-"' <<<"$ins")" "$(jq -r .permalink <<<"$row")"
done
