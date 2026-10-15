#!/usr/bin/env bash
# Overview of the Doodba sandboxes next to odoo_custom_addons: Odoo version, template
# versions, running state, and every module mounted into src/private with a check that
# its source exists and has a manifest on the branch currently checked out.
#
# Usage: sandbox_status.sh [sandbox-dir ...]   (default: ../odoo-sandbox-* of the repo)
set -euo pipefail

repo_root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
parent=$(dirname "$repo_root")

if (($#)); then
    sandboxes=("$@")
else
    shopt -s nullglob
    sandboxes=("$parent"/odoo-sandbox-*/)
fi
((${#sandboxes[@]})) || { echo "No sandboxes found in $parent (odoo-sandbox-*)"; exit 1; }

answer() { grep -E "^$1:" "$2" 2>/dev/null | head -1 | cut -d' ' -f2- || true; }

for sandbox in "${sandboxes[@]}"; do
    sandbox=$(realpath "$sandbox")
    echo "== $(basename "$sandbox")"
    echo "   odoo_version:    $(answer odoo_version "$sandbox/.copier-answers.yml")"
    echo "   doodba template: $(answer _commit "$sandbox/.copier-answers.yml")"
    echo "   ff overlay:      $(answer _commit "$sandbox/.copier-answers.ff.yml")" \
        "from $(answer _src_path "$sandbox/.copier-answers.ff.yml")"
    for repo in odoo enterprise; do
        if [[ -d $sandbox/odoo/custom/src/$repo/.git ]]; then
            printf '   %-17s%s\n' "src/$repo:" "$(git -C "$sandbox/odoo/custom/src/$repo" log -1 --format='%h %cs')"
        else
            printf '   %-17s%s\n' "src/$repo:" "not aggregated (run invoke git-aggregate)"
        fi
    done
    running=$(cd "$sandbox" && docker compose ps --status running --services 2>/dev/null | xargs || true)
    echo "   running:         ${running:-nothing}"

    echo "   private mounts:"
    (cd "$sandbox" && docker compose config --format json odoo 2>/dev/null) | python3 -c '
import json, os, subprocess, sys
config = json.load(sys.stdin)
mounts = [
    v for v in config["services"]["odoo"].get("volumes", [])
    if v.get("type") == "bind" and v["target"].startswith("/opt/odoo/custom/src/private/")
]
if not mounts:
    print("     (none)")
for v in mounts:
    source, name = v["source"], os.path.basename(v["target"])
    mountpoint = os.path.join(sys.argv[1], "odoo/custom/src/private", name)
    problems = []
    if not os.path.isdir(source):
        problems.append("source missing")
    elif not os.path.isfile(os.path.join(source, "__manifest__.py")):
        problems.append("no __manifest__.py on the checked-out branch")
    if not os.path.isdir(mountpoint):
        problems.append("mount point missing: mkdir " + os.path.relpath(mountpoint, sys.argv[1]))
    branch = subprocess.run(
        ["git", "-C", source, "branch", "--show-current"],
        capture_output=True, text=True,
    ).stdout.strip() if os.path.isdir(source) else "?"
    status = "OK" if not problems else "PROBLEM: " + "; ".join(problems)
    print(f"     {name:<24} <- {source} [{branch or 'detached'}]  {status}")
' "$sandbox" || echo "     (could not read compose config; is SSH_AUTH_SOCK set?)"
done
