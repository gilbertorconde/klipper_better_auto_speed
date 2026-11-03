# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.
#
# Per-axis speed search: bounds resolution, the binary search loop, and the
# single measured attempt that drives it.

import math
from time import perf_counter

from .funcs import calculate_accel, calculate_velocity
from .move import MoveX, MoveY, MoveZ, MoveDiagX, MoveDiagY
from .wrappers import AttemptWrapper


class SpeedSearch:
    def __init__(self, machine, motion, settings):
        self.machine = machine
        self.motion = motion
        self.settings = settings

    @staticmethod
    def _validate_bounds(lower, upper):
        if not all(math.isfinite(v) and v > 0 for v in (lower, upper)) or lower > upper:
            raise ValueError("search bounds must be finite, positive, and ordered")

    def resolve_accel_bounds(self, gcmd, max_dist, veloc_stat):
        # Validate travel even for an automatic companion velocity.
        calculate_velocity(1.0, max_dist)
        upper = gcmd.get_float('ACCEL_MAX', None, above=1.0)
        if upper is None:
            upper = self.settings.cfg_accel_max
        if upper is None:
            upper = 100000.0
        floor = calculate_accel(veloc_stat, max_dist) if veloc_stat is not None else None
        lower = gcmd.get_float('ACCEL_MIN', None, above=1.0)
        if lower is None:
            lower = self.settings.cfg_accel_min
        if lower is None:
            lower = floor if floor is not None else 1000.0
        if floor is not None and lower == floor and lower > upper and math.isclose(lower, upper, rel_tol=1e-12):
            lower = upper  # sqrt/square roundoff at the reachable ceiling
        self._validate_bounds(lower, upper)
        if floor is not None and lower < floor and not math.isclose(lower, floor, rel_tol=1e-12):
            raise ValueError("ACCEL_MIN cannot reach the fixed velocity within usable travel")
        return lower, upper

    def resolve_veloc_bounds(self, gcmd, max_dist, accel_max):
        ceiling = calculate_velocity(accel_max, max_dist)
        upper = gcmd.get_float('VELOCITY_MAX', None, above=1.0)
        if upper is None:
            upper = self.settings.cfg_veloc_max
        if upper is None:
            upper = ceiling
        lower = gcmd.get_float('VELOCITY_MIN', None, above=1.0)
        if lower is None:
            lower = self.settings.cfg_veloc_min
        if lower is None:
            lower = min(50.0, upper)
        self._validate_bounds(lower, upper)
        if upper > ceiling and not math.isclose(upper, ceiling, rel_tol=1e-12):
            raise ValueError("VELOCITY_MAX is unreachable within usable travel")
        return lower, upper

    def init_axis(self, aw: AttemptWrapper, axis):
        moves = {"x": MoveX, "y": MoveY, "z": MoveZ,
                 "diag_x": MoveDiagX, "diag_y": MoveDiagY}
        if axis not in moves:
            raise ValueError(f"unsupported search axis: {axis}")
        aw.axis = axis
        aw.move = moves[axis]()
        aw.move.Init(self.machine.axis_limits, aw.margin, self.settings.isolate_xy)

    def binary_search(self, aw: AttemptWrapper):
        """Return the highest tested pass, or None (monotonic pass/fail assumed).

        Test both bounds before bisecting. Limit the number of bisections even
        for subnormal accuracy, and stop when floating-point progress ends.
        Companion values 0 and 1 retain their legacy automatic-mode meaning.
        """
        aw.time_start = perf_counter()
        aw.valid_max = None
        aw.tries = 0
        self._validate_bounds(aw.min, aw.max)
        if not math.isfinite(aw.accuracy) or not 0 < aw.accuracy < 1:
            raise ValueError("search accuracy must be finite and between zero and one")
        if aw.type not in ("accel", "graph", "velocity"):
            raise ValueError(f"unsupported search type: {aw.type}")
        accel_search = aw.type in ("accel", "graph")
        companion = aw.veloc if accel_search else aw.accel
        automatic = companion in (0.0, 1.0)
        fd = aw.move.max_dist if aw.full_dist else None

        def prepare(value):
            if accel_search:
                aw.accel = value
                aw.veloc = (calculate_velocity(value, aw.move.max_dist) / 2.5
                            if automatic else companion)
            else:
                aw.veloc = value
                aw.accel = (calculate_accel(value, aw.move.max_dist)
                            if automatic else companion)
            aw.move.Calc(self.machine.axis_limits, aw.veloc, aw.accel, aw.margin, fd)

        # Reject an unreachable range before any homing or measured motion.
        prepare(aw.max)
        prepare(aw.min)
        aw.home_steps, aw.move_time_prehome = self.motion.prehome(aw.move.home)

        def measure(value):
            prepare(value)
            aw.tries += 1
            valid = self.attempt(aw)
            if valid:
                aw.valid_max = value if aw.valid_max is None else max(value, aw.valid_max)
            missed = ", ".join(f"{axis.upper()} {aw.missed[axis]:.2f}"
                               for axis, home in zip(('x', 'y', 'z'), aw.move.home) if home)
            self.machine.gcode.respond_info(
                f"BETTER AUTO SPEED {aw.type} on {aw.axis} try {aw.tries} ({aw.time_last:.2f}s)\n"
                f"Moved {aw.move_dist:.2f}mm at a{aw.accel:.0f}/v{aw.veloc:.0f} "
                f"after {aw.move_time_prehome:.2f}/{aw.move_time:.2f}/{aw.move_time_posthome:.2f}s\n"
                f"Missed {missed}")
            return valid

        try:
            lower, upper = aw.min, aw.max
            if not measure(lower) or lower == upper:
                return aw.valid_max
            if measure(upper):
                return aw.valid_max
            for _ in range(64):
                if upper - lower <= aw.accuracy * lower:
                    break
                midpoint = lower + (upper - lower) / 2.0
                if not lower < midpoint < upper:
                    break
                if measure(midpoint):
                    lower = midpoint
                else:
                    upper = midpoint
            return aw.valid_max
        finally:
            aw.time_total = perf_counter() - aw.time_start

    def attempt(self, aw: AttemptWrapper):
        timeAttempt = perf_counter()

        self.motion.set_velocity(self.machine.th_veloc, self.machine.th_accel, self.machine.th_scv)
        start_coord = [aw.move.pos["x"][0], aw.move.pos["y"][0], aw.move.pos["z"][0]]
        self.motion.move(start_coord, self.motion.position_speed(start_coord, self.machine.th_veloc))
        self.machine.toolhead.wait_moves()
        self.motion.set_velocity(aw.veloc, aw.accel, aw.scv)
        timeMove = perf_counter()

        self.motion.move([aw.move.pos["x"][1], aw.move.pos["y"][1], aw.move.pos["z"][1]], aw.veloc)
        self.machine.toolhead.wait_moves()
        aw.move_time = perf_counter() - timeMove
        aw.move_dist = aw.move.dist

        valid, aw.home_steps, aw.missed, aw.move_time_posthome = self.motion.posttest(aw.home_steps, aw.max_missed, aw.move.home)
        aw.time_last = perf_counter() - timeAttempt
        return valid
