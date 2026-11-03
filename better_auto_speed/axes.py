# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.
#
# Pure helpers for parsing and formatting axis selections.


def parse_axis(raw_axes, valid_axes):
    axes = [axis.strip().lower() for axis in raw_axes.split(',')]
    if not axes or any(axis not in valid_axes for axis in axes):
        raise ValueError("AXIS must be a nonempty comma-separated selection of: "
                         + ", ".join(valid_axes))
    return list(dict.fromkeys(axes))


SUPPORTED_KINEMATICS = frozenset((
    'cartesian', 'corexy', 'corexz', 'hybrid_corexy', 'hybrid_corexz',
    'markforged', 'markforged_kinematics',
))


def axis_to_str(axes):
    result = ""
    for axis in axes:
        result += f"{axis},"
    return result[:-1]
