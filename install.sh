#!/bin/bash
# automatically calculate your printer's maximum acceleration/velocity
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.

# Force script to exit if an error occurs
set -e

KLIPPER_PATH="${HOME}/klipper"
SYSTEMDDIR="/etc/systemd/system"
SRCDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/ && pwd )"

# Verify we're running as root
if [ "$(id -u)" -eq 0 ]; then
    echo "This script must not run as root"
    exit -1
fi

# Check if Klipper is installed. Match the default klipper.service as well as
# multi-instance units like klipper-<name>.service.
KLIPPER_SERVICES="$(sudo systemctl list-units --full -all -t service --no-legend \
    | grep -oE 'klipper(-[^. ]+)?\.service' | sort -u)"
if [ -n "${KLIPPER_SERVICES}" ]; then
    echo "Klipper service(s) found: $(echo ${KLIPPER_SERVICES} | tr '\n' ' ')"
else
    echo "Klipper service not found, please install Klipper first"
    exit -1
fi

# Check for old python
~/klippy-env/bin/python -c 'import sys; assert sys.version_info[0] == 3, "Python 3 is required."'

# Link better auto speed to klipper
echo "Linking better_auto_speed to Klipper..."
mkdir -p "${KLIPPER_PATH}/klippy/extras/better_auto_speed"
for file in `ls better_auto_speed/*.py`; do
    ln -sf "${SRCDIR}/${file}" "${KLIPPER_PATH}/klippy/extras/${file}"
done

# Install matplotlib
echo "Installing matplotlib in klippy..."
~/klippy-env/bin/python -m pip install matplotlib

# Restart klipper (every detected instance)
echo "Restarting Klipper..."
for service in ${KLIPPER_SERVICES}; do
    echo "  restarting ${service}"
    sudo systemctl restart "${service}"
done