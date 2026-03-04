#!/usr/bin/env bash
set -euo pipefail

##############################################################################
# One-time cleanup: Remove duplicate per-user assistants and smoke-test junk.
#
# For each "librechat-user-*" name that appears more than once, keeps
# the NEWEST (by created_at) and deletes the rest.
# Also removes any "smoke-*" assistants left over from testing.
#
# IMPORTANT: This is the ONLY place we ever delete assistants.
# After running, no production code should call DELETE /assistants.
##############################################################################

BB_URL="${BACKBOARD_BASE_URL:-https://app.backboard.io/api}"
BB_KEY="${BACKBOARD_API_KEY:?Set BACKBOARD_API_KEY}"

echo "=== Backboard assistant cleanup ==="

ASSISTANTS=$(curl -sS -H "X-API-Key: ${BB_KEY}" "${BB_URL}/assistants")

python3 - "${BB_URL}" "${BB_KEY}" <<'PYEOF' "${ASSISTANTS}"
import json, sys, subprocess
from collections import defaultdict

bb_url = sys.argv[1]
bb_key = sys.argv[2]
data = json.loads(sys.argv[3])

by_name = defaultdict(list)
smoke = []

for a in data:
    name = a.get("name", "")
    aid = a["assistant_id"]
    created = a.get("created_at", "")

    if name.startswith("smoke-"):
        smoke.append((aid, name))
        continue

    if name.startswith("librechat-user-[object"):
        smoke.append((aid, name))
        continue

    by_name[name].append({"id": aid, "created": created, "name": name})

to_delete = []

# For duplicates, keep newest, queue rest for deletion
for name, assistants in by_name.items():
    if len(assistants) <= 1:
        continue
    assistants.sort(key=lambda x: x["created"], reverse=True)
    keep = assistants[0]
    dupes = assistants[1:]
    print(f"  {name}: keeping {keep['id']} ({keep['created']}), removing {len(dupes)} older")
    for d in dupes:
        to_delete.append((d["id"], name))

for aid, name in smoke:
    to_delete.append((aid, name))
    print(f"  Smoke/junk: {aid} ({name})")

if not to_delete:
    print("\n  No duplicates or junk found. All clean!")
    sys.exit(0)

import os
auto_yes = os.environ.get("AUTO_YES", "").lower() == "1"
print(f"\n  Total to remove: {len(to_delete)}")
if not auto_yes:
    confirm = input("  Proceed? [y/N] ").strip().lower()
    if confirm != "y":
        print("  Aborted.")
        sys.exit(0)

deleted = 0
for aid, name in to_delete:
    try:
        r = subprocess.run(
            ["curl", "-sS", "-X", "DELETE",
             "-H", f"X-API-Key: {bb_key}",
             f"{bb_url}/assistants/{aid}"],
            capture_output=True, text=True, timeout=10
        )
        deleted += 1
        print(f"    Deleted {aid} ({name})")
    except Exception as e:
        print(f"    FAILED {aid}: {e}")

print(f"\n  Done. Deleted {deleted}/{len(to_delete)} assistants.")
PYEOF
