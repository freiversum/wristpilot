#!/bin/bash
# Copies the bridge core into Tretlager (tretlager/wristpilot/). Tretlager vendors the core
# instead of depending on a separate package.
# Run after every change to the core, then test and commit in Tretlager.
# Usage: tools/sync-tretlager.sh [TARGET]   (default: ../tretlager/tretlager/wristpilot)
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
dest="${1:-$here/../tretlager/tretlager/wristpilot}"
rsync -a --delete --exclude __pycache__ --exclude __main__.py --exclude firmware/ "$here/bridge/wristpilot_bridge/" "$dest/"
cat > "$dest/VENDORED.md" <<TXT
# Vendored: Wristpilot bridge core

Copied from the Wristpilot project (https://github.com/freiversum/wristpilot, bridge/wristpilot_bridge, version $(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$here/bridge/wristpilot_bridge/__init__.py")).
Do not edit here; change it in Wristpilot and run its tools/sync-tretlager.sh.
License: GPL-3.0-or-later, like Tretlager.
TXT
echo "synced to $dest"
