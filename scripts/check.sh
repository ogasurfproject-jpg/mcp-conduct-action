#!/usr/bin/env bash
# MCP conduct check. One POST to the gate, one recompute of the verdict's own hash, then a plain report.
# Runs inside the GitHub Action and also on a laptop:
#   MCP_CONDUCT_ENDPOINT=https://your-server.example/mcp bash scripts/check.sh
# HTTP goes through curl on purpose: the gate is fronted by Cloudflare, which turns away the Python urllib
# user agent with 403 (a known limitation the gate publishes in /spec). curl is measured at 200.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
EP="${MCP_CONDUCT_ENDPOINT:-}"
ALLOW="${MCP_CONDUCT_ALLOW_TOOL_CALL:-true}"
FAIL_ON_NOT_VERIFIED="${MCP_CONDUCT_FAIL_ON_NOT_VERIFIED:-false}"
JOIN="${MCP_CONDUCT_JOIN_REGISTER:-false}"
GATE="${MCP_CONDUCT_GATE:-https://gate.horizonshield.dev}"
GATE="${GATE%/}"
OUT_DIR="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
VERDICT="$OUT_DIR/mcp-conduct-verdict.json"
GITHUB_OUTPUT="${GITHUB_OUTPUT:-/dev/null}"
GITHUB_STEP_SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/null}"

die() { echo "::error::$1"; echo "$1" >&2; exit 1; }

case "$EP" in
  https://*) ;;
  "") die "endpoint is required (https URL of the MCP endpoint this repository deploys)" ;;
  *) die "endpoint must start with https:// (got: $EP)" ;;
esac
command -v curl >/dev/null 2>&1 || die "curl is required"
command -v python3 >/dev/null 2>&1 || die "python3 is required"

# The request body is built by json.dumps so the endpoint is escaped, never interpolated into JSON by hand.
BODY="$(EP="$EP" ALLOW="$ALLOW" python3 -c 'import json,os; print(json.dumps({"endpoint": os.environ["EP"], "allow_tool_call": os.environ["ALLOW"].strip().lower() == "true"}))')"

echo "MCP conduct check"
echo "  gate:     $GATE"
echo "  endpoint: $EP"
echo "  tool call consent asserted: $ALLOW"

# One measurement can take up to a minute when determinism is measured (one tool, twice).
HTTP="$(curl -sS --max-time 180 --retry 1 --retry-delay 5 \
  -H "Content-Type: application/json" -H "Accept: application/json" \
  -H "User-Agent: mcp-conduct-action/1.0 (+https://github.com/ogasurfproject-jpg/mcp-conduct-action)" \
  -X POST "$GATE/check" --data "$BODY" -o "$VERDICT" -w '%{http_code}')" || true

if [ "$HTTP" != "200" ]; then
  MSG="the gate did not return a verdict (HTTP ${HTTP:-000})."
  if [ -s "$VERDICT" ]; then MSG="$MSG body: $(head -c 400 "$VERDICT")"; fi
  die "$MSG This is a failure of the request, not a verdict about $EP."
fi

# report.py parses the verdict, recomputes record_sha256, writes outputs and the step summary,
# and exits 0 (verified or held), 10 (pending), 20 (record does not hash to its own record_sha256).
VERDICT="$VERDICT" GATE="$GATE" EP="$EP" python3 "$HERE/report.py"
RC=$?

if [ "$RC" -eq 20 ]; then
  die "the verdict does not hash to its own record_sha256. The record is not self consistent; do not rely on it."
fi

if [ "$(echo "$JOIN" | tr '[:upper:]' '[:lower:]')" = "true" ]; then
  WBODY="$(EP="$EP" python3 -c 'import json,os; print(json.dumps({"endpoint": os.environ["EP"]}))')"
  WHTTP="$(curl -sS --max-time 60 -H "Content-Type: application/json" \
    -H "User-Agent: mcp-conduct-action/1.0 (+https://github.com/ogasurfproject-jpg/mcp-conduct-action)" \
    -X POST "$GATE/watch" --data "$WBODY" -o "$OUT_DIR/mcp-conduct-watch.json" -w '%{http_code}')" || true
  if [ "$WHTTP" = "200" ]; then
    echo "  register: joined (or already present). Weekly re-measurement; the verdict is the same for every tier."
    echo "  row: $GATE/e/${EP#https://}"
  else
    echo "::warning::POST /watch returned HTTP ${WHTTP:-000}; the endpoint may not have joined the register. Body: $(head -c 300 "$OUT_DIR/mcp-conduct-watch.json" 2>/dev/null)"
  fi
fi

if [ "$RC" -eq 10 ] && [ "$(echo "$FAIL_ON_NOT_VERIFIED" | tr '[:upper:]' '[:lower:]')" = "true" ]; then
  die "status is pending and fail_on_not_verified is true. See the step summary for the condition that did not pass."
fi
exit 0
