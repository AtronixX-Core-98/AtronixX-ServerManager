#!/usr/bin/env bash
# One-line installer for ServerManager.
#
#   sudo bash <(curl -fsSL https://raw.githubusercontent.com/AtronixX-Core-98/AtronixX-ServerManager/main/install.sh)
#
# It downloads the `servermanager` control script, installs it to /usr/local/bin and starts the
# guided installation. Run it from a cloned checkout instead (sudo ./install.sh) to install from
# local files.
set -euo pipefail

SM_REPO="${SM_REPO:-AtronixX-Core-98/AtronixX-ServerManager}"
SM_BRANCH="${SM_BRANCH:-main}"
export SM_REPO SM_BRANCH

[ "$(id -u)" -eq 0 ] || { echo "Please run as root:  sudo bash $0" >&2; exit 1; }

here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$here" ] && [ -f "$here/scripts/servermanager.sh" ]; then
  exec bash "$here/scripts/servermanager.sh" install
fi

command -v curl >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y -qq curl; }

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
curl -fsSL "https://raw.githubusercontent.com/${SM_REPO}/${SM_BRANCH}/scripts/servermanager.sh" -o "$tmp"
bash -n "$tmp" || { echo "Downloaded script is invalid." >&2; exit 1; }
install -m 755 "$tmp" /usr/local/bin/servermanager
exec /usr/local/bin/servermanager install
