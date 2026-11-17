#!/usr/bin/env bash
# Forking? Point the install URLs, image name and docs at your own GitHub repository.
#   ./scripts/set-repo.sh yourname/your-fork
# The project credit (AtronixX-Core, Telegram channel/support links) is intentionally left untouched.
set -euo pipefail
new="${1:-}"
[[ "$new" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]] || { echo "Usage: $0 owner/repo" >&2; exit 1; }
old="AtronixX-Core/AtronixX-ServerManager"
cd "$(dirname "$0")/.."
grep -rIil --exclude-dir=.git --exclude=set-repo.sh --exclude=CHANGELOG.md "$old" . | while read -r f; do
  sed -i "s#ghcr.io/${old,,}#ghcr.io/${new,,}#g; s#${old}#${new}#g" "$f"
  echo "updated $f"
done
