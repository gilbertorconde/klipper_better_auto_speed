#!/bin/bash
# Remove better_auto_speed from your Klipper installation
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.

# Force script to exit if an error occurs
set -e

KLIPPER_PATH="${HOME}/klipper"
EXTRA_PATH="${KLIPPER_PATH}/klippy/extras/better_auto_speed"

# Verify we're running as root
if [ "$(id -u)" -eq 0 ]; then
    echo "This script must not run as root"
    exit -1
fi

# Detect Klipper service(s), matching multi-instance units too.
KLIPPER_SERVICES="$(sudo systemctl list-units --full -all -t service --no-legend \
    | grep -oE 'klipper(-[^. ]+)?\.service' | sort -u)"

# Remove the linked extras package (symlinked dir or per-file links).
if [ -e "${EXTRA_PATH}" ] || [ -L "${EXTRA_PATH}" ]; then
    echo "Removing better_auto_speed from Klipper extras..."
    rm -rf "${EXTRA_PATH}"
else
    echo "better_auto_speed not found in Klipper extras (already removed)."
fi

# Restart klipper (every detected instance)
if [ -n "${KLIPPER_SERVICES}" ]; then
    echo "Restarting Klipper..."
    for service in ${KLIPPER_SERVICES}; do
        echo "  restarting ${service}"
        sudo systemctl restart "${service}"
    done
fi

echo ""
echo "Done. Remember to remove the [better_auto_speed] section (and any"
echo "BETTER_AUTO_SPEED-saved values) from your printer.cfg, then restart Klipper."
