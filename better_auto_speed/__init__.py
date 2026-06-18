# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.

from .funcs import *
from .move import *
from .wrappers import *

from .main import BetterAutoSpeed

def load_config(config): # Called by klipper from [better_auto_speed]
    try:
        from .main import BetterAutoSpeed
    except ImportError as err:
        # Chain the original error so the real cause (missing dependency, broken
        # symlink, etc.) is visible in klippy.log instead of a generic message.
        raise ImportError(
            f"Failed to import better_auto_speed; please re-run "
            f"klipper_auto_speed/install.sh ({err})") from err
    return BetterAutoSpeed(config)
