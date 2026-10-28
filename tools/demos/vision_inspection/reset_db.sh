#!/bin/bash
# Recreate the throwaway database of the video (vision_demo) from its prepared
# copy (vision_demo_base), so a validate or record run starts from the same data.
#   tools/demos/vision_inspection/reset_db.sh [../odoo-sandbox-20]
SANDBOX=${1:-$(dirname "$0")/../../../../odoo-sandbox-20}
cd "$SANDBOX" || exit 1
docker compose run --rm odoo odoo db duplicate -f vision_demo_base vision_demo 2>&1 | grep -iE "error|traceback"
echo "vision_demo reset from vision_demo_base"
