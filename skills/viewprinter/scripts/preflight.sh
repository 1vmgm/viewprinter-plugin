#!/usr/bin/env bash
# Exercises the documented path: prove the server this skill drives is reachable,
# speaks MCP, and offers the sign-in the user will be sent through. A check that
# does not call the endpoint cannot catch the outage that breaks the first post.
#
# Read-only. It never schedules, uploads or deletes anything, and it needs no
# credentials — an unauthenticated client can list tools, which is the property
# the directories scan for.
set -uo pipefail
FAIL=0
ok()  { printf "  \033[32m✓\033[0m %s\n" "$1"; }
bad() { printf "  \033[31m✗\033[0m %s\n" "$1"; FAIL=1; }

# The endpoint is declared once, in the manifest, so this cannot drift from what
# the plugin actually installs.
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
MCP_URL=$(python3 -c "import json;print(json.load(open('$ROOT/.mcp.json'))['mcpServers']['viewprinter']['url'])" 2>/dev/null)
[ -n "$MCP_URL" ] && ok "endpoint: $MCP_URL" || { bad "no endpoint in .mcp.json"; echo; exit 1; }

for t in curl python3; do
  command -v "$t" >/dev/null && ok "$t on PATH" || bad "$t missing"
done

# tools/list with no credentials. Unauthenticated discovery is deliberate: it is
# how mcp.so, Smithery and Glama scan the server, and losing it silently delists
# us from all three.
body='{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
resp=$(curl -sS --max-time 20 -X POST "$MCP_URL" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d "$body" 2>/dev/null) || resp=''
if [ -z "$resp" ]; then
  bad "no response from $MCP_URL"
else
  count=$(printf '%s' "$resp" | python3 -c "
import json,sys
raw = sys.stdin.read()
for line in raw.splitlines():
    line = line[5:].strip() if line.startswith('data:') else line
    if not line.strip().startswith('{'): continue
    try: d = json.loads(line)
    except Exception: continue
    tools = d.get('result', {}).get('tools')
    if tools is not None: print(len(tools)); break
else: print(0)
" 2>/dev/null)
  [ "${count:-0}" -gt 0 ] && ok "tools/list returned $count tools, unauthenticated" \
                          || bad "tools/list returned no tools — discovery is broken"
fi

# The sign-in the user completes themselves. Without this the connect flow in
# references/connecting.md has nowhere to send them.
origin=$(python3 -c "
from urllib.parse import urlparse
u = urlparse('$MCP_URL'); print(f'{u.scheme}://{u.netloc}')" 2>/dev/null)
code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
  "$origin/.well-known/oauth-protected-resource" 2>/dev/null || echo 000)
case "$code" in
  2*) ok "OAuth metadata published ($code)" ;;
  *)  bad "OAuth metadata unavailable at $origin/.well-known/oauth-protected-resource ($code)" ;;
esac

echo
[ $FAIL -eq 0 ] && echo "  preflight PASSED" || { echo "  preflight FAILED"; exit 1; }
