#!/bin/bash
# Install links without restarting a printer unless explicitly requested.
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

# Keep manual directory-symlink installations intact; reject unrelated targets.
if [[ -L "$EXTRA_PATH" ]]; then
    [[ "$(readlink -f -- "$EXTRA_PATH")" == "$SRCDIR/better_auto_speed" ]] || {
        echo "Refusing to replace unrelated symlink: $EXTRA_PATH" >&2; exit 1;
    }
else
    # Preflight every destination before changing any link.
    for source in "$SRCDIR"/better_auto_speed/*.py; do
        target="$EXTRA_PATH/$(basename -- "$source")"
        if [[ -e "$target" || -L "$target" ]]; then
            [[ -L "$target" && "$(readlink -- "$target")" == "$source" ]] || {
                echo "Refusing to overwrite unrelated file: $target" >&2; exit 1;
            }
        fi
    done
    mkdir -p -- "$EXTRA_PATH"
    for source in "$SRCDIR"/better_auto_speed/*.py; do
        ln -sfn -- "$source" "$EXTRA_PATH/$(basename -- "$source")"
    done
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
