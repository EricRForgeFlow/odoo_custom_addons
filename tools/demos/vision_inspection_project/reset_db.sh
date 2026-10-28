#!/bin/bash
# Recreate the throwaway database of the video (vision_project) from its prepared copy
# (vision_project_base), so every validate or record run starts from the same data.
#   tools/demos/vision_inspection_project/reset_db.sh [../odoo-sandbox-20]
#
# The running server keeps pooled connections to the database it had before; each one
# fails once after the reset. So the script then sends requests until ten in a row
# succeed: the recording never meets a stale connection.
SANDBOX=${1:-$(dirname "$0")/../../../../odoo-sandbox-20}
URL=${DEMO_ODOO:-http://localhost:20069}
cd "$SANDBOX" || exit 1
docker compose run --rm odoo odoo db duplicate -f vision_project_base vision_project 2>&1 | grep -iE "error|traceback"
ok=0
for _ in $(seq 60); do
    if curl -sf -X POST "$URL/web/session/authenticate" -H "Content-Type: application/json" \
        -d '{"jsonrpc": "2.0", "params": {"db": "vision_project", "login": "admin", "password": "admin"}}' \
        | grep -q '"uid"'; then
        ok=$((ok + 1))
        [ "$ok" -ge 10 ] && break
    else
        ok=0
    fi
done
[ "$ok" -ge 10 ] || { echo "the server still fails on vision_project" >&2; exit 1; }
echo "vision_project reset from vision_project_base"
