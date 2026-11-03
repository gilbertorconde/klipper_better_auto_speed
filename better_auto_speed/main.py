# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.
#
# Thin facade: construct the collaborators, register Klipper event handlers and
# the BETTER_AUTO_SPEED* / *_ENDSTOP_ACCURACY gcode commands. All behaviour lives
# in the collaborator classes (see settings.py, machine.py, motion.py, search.py,
# overrides.py, endstop_accuracy.py, plotting.py, commands.py).

from .settings import Settings
from .machine import Machine
from .motion import MotionController
from .search import SpeedSearch
from .overrides import Overrides
from .endstop_accuracy import EndstopAccuracy
from .commands import AutoSpeedCommands


class BetterAutoSpeed:
    def __init__(self, config):
        self.printer = config.get_printer()
        gcode = self.printer.lookup_object('gcode')
        gcode_move = self.printer.load_object(config, 'gcode_move')

        self.settings = Settings.from_config(config)
        self.machine = Machine(self.printer, gcode, gcode_move, self.settings)
        self.motion = MotionController(self.machine, self.settings)
        self.search = SpeedSearch(self.machine, self.motion, self.settings)
        self.overrides = Overrides(self.machine, self.settings)
        self.commands = AutoSpeedCommands(self.machine, self.motion, self.search,
                                          self.overrides, self.settings)
        self.endstop = EndstopAccuracy(self.machine, self.motion)

        self.printer.register_event_handler("klippy:connect", self.machine.handle_connect)
        self.printer.register_event_handler("homing:home_rails_end", self.machine.handle_home_rails_end)

        c = self.commands
        gcode.register_command('BETTER_AUTO_SPEED',
                               c.cmd_BETTER_AUTO_SPEED,
                               desc=c.cmd_BETTER_AUTO_SPEED_help)
        gcode.register_command('BETTER_AUTO_SPEED_VELOCITY',
                               c.cmd_BETTER_AUTO_SPEED_VELOCITY,
                               desc=c.cmd_BETTER_AUTO_SPEED_VELOCITY_help)
        gcode.register_command('BETTER_AUTO_SPEED_ACCEL',
                               c.cmd_BETTER_AUTO_SPEED_ACCEL,
                               desc=c.cmd_BETTER_AUTO_SPEED_ACCEL_help)
        gcode.register_command('BETTER_AUTO_SPEED_VALIDATE',
                               c.cmd_BETTER_AUTO_SPEED_VALIDATE,
                               desc=c.cmd_BETTER_AUTO_SPEED_VALIDATE_help)
        gcode.register_command('BETTER_AUTO_SPEED_GRAPH',
                               c.cmd_BETTER_AUTO_SPEED_GRAPH,
                               desc=c.cmd_BETTER_AUTO_SPEED_GRAPH_help)

        e = self.endstop
        for axis in 'XYZ':
            name = f'{axis}_ENDSTOP_ACCURACY'
            gcode.register_command(name, getattr(e, f'cmd_{name}'),
                                   desc=getattr(e, f'cmd_{name}_help'))
