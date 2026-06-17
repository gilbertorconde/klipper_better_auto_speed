# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
#
# This file may be distributed under the terms of the MIT license.

from .funcs import *
from .move import *
from .wrappers import *

from .main import BetterAutoSpeed

def load_config(config): # Called by klipper from [better_auto_speed]
    try:
        from .main import BetterAutoSpeed
    except ImportError:
        raise ImportError("Please re-run klipper_auto_speed/install.sh")
    return BetterAutoSpeed(config)
