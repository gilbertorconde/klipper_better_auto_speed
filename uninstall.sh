#!/bin/bash
# Remove only links belonging to this checkout; never recursively delete extras.
set -euo pipefail
SRCDIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
KLIPPER_PATH="${KLIPPER_PATH:-${HOME}/klipper}"
EXTRA_PATH="${KLIPPER_PATH}/klippy/extras/better_auto_speed"

if [[ "${1:-}" == --help ]]; then
    echo 'Usage: [KLIPPER_PATH=...] ./uninstall.sh'
    echo 'Removes only links owned by this checkout. Does not restart Klipper.'
    exit 0
fi
[[ $# == 0 ]] || { echo 'Unknown argument; use --help' >&2; exit 1; }
PACKAGE="$SRCDIR/better_auto_speed"
if [[ -L "$EXTRA_PATH" ]]; then
    # Directory-link layout (default since installs link the whole package).
    [[ "$(readlink -- "$EXTRA_PATH")" == "$PACKAGE" ||
       "$(readlink -f -- "$EXTRA_PATH")" == "$PACKAGE" ]] || {
        echo "Refusing to remove unrelated symlink: $EXTRA_PATH" >&2; exit 1;
    }
    unlink -- "$EXTRA_PATH"
elif [[ -d "$EXTRA_PATH" ]]; then
    # Legacy per-file layout: remove only links into this checkout.
    shopt -s dotglob nullglob
    for target in "$EXTRA_PATH"/*; do
        if [[ -L "$target" && "$(readlink -- "$target")" == "$PACKAGE/$(basename -- "$target")" ]]; then
            unlink -- "$target"
        fi
    done
    shopt -u dotglob nullglob
    # Leave caches and unrelated files intact.
    rmdir -- "$EXTRA_PATH" 2>/dev/null || true
fi
printf '%s\n' 'Links removed. Remove [better_auto_speed] and dependent macros from your config before manually restarting the selected Klipper service.'
