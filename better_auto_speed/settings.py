# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.
#
# Parsed, immutable-ish view of the [better_auto_speed] config section.

import os
from math import isfinite

from .axes import parse_axis, SUPPORTED_KINEMATICS


class Settings:
    @classmethod
    def from_config(cls, config):
        return cls(config)

    def __init__(self, config):
        printer = config.get_printer()

        self.printer_kinematics = config.getsection("printer").get("kinematics")
        if self.printer_kinematics not in SUPPORTED_KINEMATICS:
            raise config.error('Unsupported kinematics for better_auto_speed: '
                               + self.printer_kinematics)
        self.isolate_xy = self.printer_kinematics in ('cartesian', 'corexz')

        self.valid_axes = ["x", "y", "diag_x", "diag_y", "z"]
        try:
            self.axes = parse_axis(
                config.get('axis', 'x, y' if self.isolate_xy else 'diag_x, diag_y'),
                self.valid_axes)
        except ValueError as exc:
            raise config.error(str(exc))

        self.margin          = config.getfloat(  'margin',          default=20.0, above=0.0)
        self.settling_home   = config.getboolean('settling_home',   default=True)
        self.max_missed      = config.getfloat(  'max_missed',      default=1.0, above=0.0)
        self.endstop_samples = config.getint(    'endstop_samples', default=3, minval=2)

        # None sentinel lets us tell "explicitly configured" from "absent" so
        # size-derived defaults only apply when the user didn't set a value.
        self.cfg_accel_min = config.getfloat('accel_min', None, above=1.0)
        self.cfg_accel_max = config.getfloat('accel_max', None, above=1.0)
        self.accel_min  = self.cfg_accel_min if self.cfg_accel_min is not None else 1000.0
        self.accel_max  = self.cfg_accel_max if self.cfg_accel_max is not None else 100000.0
        self.accel_accu = config.getfloat('accel_accu', default=0.05, above=0.0, below=1.0)
        self.scv        = config.getfloat('scv', default=5, above=1.0, below=50)

        self.cfg_veloc_min = config.getfloat('velocity_min', None, above=1.0)
        self.cfg_veloc_max = config.getfloat('velocity_max', None, above=1.0)
        self.veloc_min  = self.cfg_veloc_min if self.cfg_veloc_min is not None else 50.0
        self.veloc_max  = self.cfg_veloc_max if self.cfg_veloc_max is not None else 5000.0
        self.veloc_accu = config.getfloat('velocity_accu', default=0.05, above=0.0, below=1.0)

        self.derate = config.getfloat('derate', default=0.8, above=0.0, below=1.0)

        # Speed used for positioning moves that change Z (centering, Z= move,
        # per-attempt prep). Keeps belted/Trident Z from slamming after leveling.
        self.z_position_speed = config.getfloat('z_position_speed', default=25.0, above=0.0)
        # Drop motors (M84) once the run finishes.
        self.motor_off = config.getboolean('motor_off', default=False)

        self.validate_margin       = config.getfloat('validate_margin', default=self.margin, above=0.0)
        self.validate_inner_margin = config.getfloat('validate_inner_margin', default=20.0, above=0.0)
        self.validate_iterations   = config.getint(  'validate_iterations', default=50, minval=1)

        for name, value in vars(self).items():
            if isinstance(value, float) and not isfinite(value):
                raise config.error(f'{name} must be finite')
        for name, low, high in (
                ('accel', self.cfg_accel_min, self.cfg_accel_max),
                ('velocity', self.cfg_veloc_min, self.cfg_veloc_max)):
            if low is not None and high is not None and low >= high:
                raise config.error(f'{name}_min must be below {name}_max')

        results_default = os.path.expanduser('~')
        candidate_paths = [os.path.expanduser('~/printer_data/config')]
        # klippy may run without a log file (logs to stdout); guard the lookup.
        log_file = printer.start_args.get('log_file')
        if log_file:
            candidate_paths.insert(0, os.path.dirname(log_file))
        for path in candidate_paths:
            if os.path.exists(path):
                results_default = path
        self.results_dir = os.path.expanduser(config.get('results_dir', default=results_default))
