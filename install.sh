#!/bin/bash
# Install the package link without restarting a printer unless explicitly requested.
set -euo pipefail

SRCDIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
KLIPPER_PATH="${KLIPPER_PATH:-${HOME}/klipper}"
KLIPPY_ENV="${KLIPPY_ENV:-${HOME}/klippy-env}"
KLIPPER_SERVICE="${KLIPPER_SERVICE:-}"
EXTRA_PATH="${KLIPPER_PATH}/klippy/extras/better_auto_speed"

if [[ "${1:-}" == --help ]]; then
    echo 'Usage: [KLIPPER_PATH=...] [KLIPPY_ENV=...] [KLIPPER_SERVICE=klipper.service] [INSTALL_PLOTTING=1] ./install.sh'
    echo 'No service is restarted by default. INSTALL_PLOTTING=1 installs optional matplotlib.'
    exit 0
fi
[[ $# == 0 ]] || { echo 'Unknown argument; use --help' >&2; exit 1; }
[[ -d "${KLIPPER_PATH}/klippy/extras" ]] || { echo 'Klipper extras directory not found' >&2; exit 1; }
[[ -x "${KLIPPY_ENV}/bin/python" ]] || { echo 'Klipper Python environment not found' >&2; exit 1; }
[[ -z "$KLIPPER_SERVICE" || "$KLIPPER_SERVICE" =~ ^klipper(-[a-zA-Z0-9_-]+)?\.service$ ]] || {
    echo 'KLIPPER_SERVICE must name one klipper service' >&2; exit 1;
}
"${KLIPPY_ENV}/bin/python" -c 'import sys; assert sys.version_info >= (3, 8), "Python 3.8+ is required"'

# Install one directory symlink so modules added by future updates are found
# without re-running this script (Moonraker no longer runs install_script).
PACKAGE="$SRCDIR/better_auto_speed"
if [[ -L "$EXTRA_PATH" ]]; then
    [[ "$(readlink -f -- "$EXTRA_PATH")" == "$PACKAGE" ]] || {
        echo "Refusing to replace unrelated symlink: $EXTRA_PATH" >&2; exit 1;
    }
    echo "Already linked: $EXTRA_PATH -> $PACKAGE"
else
    if [[ -e "$EXTRA_PATH" ]]; then
        # Migrate the legacy per-file layout only if it holds nothing but links
        # into this checkout and Python caches.
        [[ -d "$EXTRA_PATH" ]] || { echo "Refusing to replace unrelated file: $EXTRA_PATH" >&2; exit 1; }
        shopt -s dotglob nullglob
        for target in "$EXTRA_PATH"/*; do
            name="$(basename -- "$target")"
            if [[ "$name" == __pycache__ && -d "$target" && ! -L "$target" ]]; then
                continue
            fi
            [[ -L "$target" && "$(readlink -- "$target")" == "$PACKAGE/$name" ]] || {
                echo "Refusing to migrate $EXTRA_PATH: it contains unrelated file $target" >&2
                echo 'Move it away (or remove the directory) and re-run install.sh.' >&2
                exit 1
            }
        done
        for target in "$EXTRA_PATH"/*; do
            if [[ -L "$target" ]]; then unlink -- "$target"; fi
        done
        shopt -u dotglob nullglob
        # __pycache__ holds only compiled copies of this package's modules.
        rm -rf -- "$EXTRA_PATH/__pycache__"
        rmdir -- "$EXTRA_PATH"
        echo "Migrated legacy per-file links in $EXTRA_PATH to a directory link."
    fi
    ln -s -- "$PACKAGE" "$EXTRA_PATH"
fi

if [[ "${INSTALL_PLOTTING:-0}" == 1 ]]; then
    "${KLIPPY_ENV}/bin/python" -m pip install matplotlib
fi
if [[ -n "$KLIPPER_SERVICE" ]]; then
    echo "Restarting explicitly selected service: $KLIPPER_SERVICE"
    systemctl restart "$KLIPPER_SERVICE"
else
    echo 'Installed. Restart your selected Klipper service manually when the printer is idle.'
fi
