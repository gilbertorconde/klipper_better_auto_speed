# Endstop repeatability measured in a fixed MCU reference frame.
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde)
# This file may be distributed under the terms of the MIT license.

import math


class EndstopAccuracy:
    def __init__(self, machine, motion):
        self.machine = machine
        self.motion = motion

    cmd_X_ENDSTOP_ACCURACY_help = "Measure X endstop repeatability using MCU positions"
    cmd_Y_ENDSTOP_ACCURACY_help = "Measure Y endstop repeatability using MCU positions"
    cmd_Z_ENDSTOP_ACCURACY_help = "Measure mechanical Z endstop repeatability (not probes)"

    def cmd_X_ENDSTOP_ACCURACY(self, gcmd):
        self._measure(gcmd, 'x')

    def cmd_Y_ENDSTOP_ACCURACY(self, gcmd):
        self._measure(gcmd, 'y')

    def cmd_Z_ENDSTOP_ACCURACY(self, gcmd):
        self._measure(gcmd, 'z')

    def _measure(self, gcmd, axis):
        self.machine.check_homed(gcmd)
        count = gcmd.get_int('SAMPLES', 10, minval=1)
        if axis == 'z' and self.machine.z_uses_probe():
            raise gcmd.error("Probe-based Z homing is not a reliable endstop test; "
                             "use PROBE_ACCURACY instead.")
        rails = self.machine.axis_rails(axis)
        if len(rails) != 1:
            raise gcmd.error(f"Expected one homing rail for {axis.upper()}.")
        rail = rails[0]
        info = rail.get_homing_info()
        distance, speed = info.retract_dist, info.second_homing_speed
        if not all(math.isfinite(v) and v > 0 for v in (distance, speed)):
            raise gcmd.error("Endstop accuracy requires positive retract distance and speed.")
        low, high = rail.get_range()
        target = info.position_endstop + (-distance if info.positive_dir else distance)
        if not low <= target <= high:
            raise gcmd.error("Endstop retract would exceed the rail travel limits.")

        toolhead = self.machine.toolhead
        kin = toolhead.get_kinematics()
        if not callable(getattr(kin, 'calc_position', None)):
            raise gcmd.error("Kinematics does not support MCU position reconstruction.")
        steppers = kin.get_steppers()
        index = 'xyz'.index(axis)
        home_axes = [i == index for i in range(3)]
        reference = None
        positions = []
        for _ in range(count):
            self.motion.home(*home_axes)
            toolhead.wait_moves()
            # Freeze the commanded-to-MCU offsets after the first home. Later
            # G28 coordinate resets must not erase physical trigger differences.
            if reference is None:
                reference = {s.get_name(): s.get_commanded_position()
                             - s.get_mcu_position() * s.get_step_dist()
                             for s in steppers}
            physical = {s.get_name(): reference[s.get_name()]
                        + s.get_mcu_position() * s.get_step_dist()
                        for s in steppers}
            value = kin.calc_position(physical)[index]
            if not math.isfinite(value):
                raise gcmd.error("Cannot reconstruct a finite endstop position.")
            positions.append(value)
            pos = [None, None, None]
            pos[index] = toolhead.get_position()[index] + (
                -distance if info.positive_dir else distance)
            if not low <= pos[index] <= high:
                raise gcmd.error("Endstop retract would exceed the rail travel limits.")
            toolhead.manual_move(pos, speed=speed)
            toolhead.wait_moves()

        # Relative positions avoid suggesting these are absolute bed coordinates.
        positions = [p - positions[0] for p in positions]
        average = sum(positions) / len(positions)
        sigma = (sum((p - average) ** 2 for p in positions) / len(positions)) ** 0.5
        gcmd.respond_info(
            "%s endstop accuracy results (MCU-relative mm): maximum %.6f, "
            "minimum %.6f, range %.6f, average %.6f, standard deviation %.6f"
            % (axis.upper(), max(positions), min(positions),
               max(positions) - min(positions), average, sigma))
