# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.
#
# Low-level motion: toolhead velocity limits, moves, homing, missed-step
# measurement, the validation pattern, and leveling.

from time import perf_counter


class MotionController:
    def __init__(self, machine, settings):
        self.machine = machine
        self.settings = settings

    def set_velocity(self, velocity: float, accel: float, scv: float, cruise_ratio: float = 0.0):
        #self.gcode.respond_info(f"BETTER AUTO SPEED setting limits to VELOCITY={velocity} ACCEL={accel}")
        toolhead = self.machine.toolhead
        toolhead.max_velocity = velocity
        toolhead.max_accel = accel
        # Disable accel-to-decel / minimum-cruise-ratio limiting so short test
        # moves actually reach the requested velocity. Klipper changed this API:
        # newer builds use min_cruise_ratio, older ones requested_accel_to_decel.
        if hasattr(toolhead, 'min_cruise_ratio'):
            toolhead.min_cruise_ratio = cruise_ratio
        if hasattr(toolhead, 'requested_accel_to_decel'):
            toolhead.requested_accel_to_decel = accel
        toolhead.square_corner_velocity = scv
        if hasattr(toolhead, '_calc_junction_deviation'):
            toolhead._calc_junction_deviation()

    def capture_velocity_limits(self):
        """Snapshot runtime limits, including Klipper's derived legacy fields."""
        toolhead = self.machine.toolhead
        names = ('max_velocity', 'max_accel', 'square_corner_velocity',
                 'min_cruise_ratio', 'requested_accel_to_decel',
                 'max_accel_to_decel', 'accel_to_decel', 'junction_deviation')
        return {name: getattr(toolhead, name) for name in names
                if hasattr(toolhead, name)}

    def restore_velocity_limits(self, state):
        # Restore derived values too: recalculation can clamp legacy limits.
        for name, value in state.items():
            setattr(self.machine.toolhead, name, value)

    def move(self, coord, speed):
        self.machine.toolhead.manual_move(coord, speed)

    def position_speed(self, coord, speed):
        # Cap positioning moves that change Z to z_position_speed so a belted/
        # Trident Z doesn't slam after leveling. Test moves call move directly.
        if len(coord) > 2 and coord[2] is not None:
            return min(speed, self.settings.z_position_speed)
        return speed

    def home(self, x=True, y=True, z=True):
        if not any((x, y, z)):
            return  # Bare G28 would unexpectedly home every axis.
        toolhead = self.machine.toolhead
        state = self.capture_velocity_limits()
        command = ["G28"]
        if x:
            command[-1] += " X0"
        if y:
            command[-1] += " Y0"
        if z:
            command[-1] += " Z0"
        try:
            self.set_velocity(self.machine.th_veloc, self.machine.th_accel, self.machine.th_scv)
            self.machine.gcode.run_script_from_command(command[0])
            toolhead.wait_moves()
        finally:
            self.restore_velocity_limits(state)

    def prehome(self, home: list):
        self.machine.toolhead.wait_moves()
        dur = perf_counter()
        self.home(home[0], home[1], home[2])
        self.machine.toolhead.wait_moves()
        dur = perf_counter() - dur

        home_steps = self.machine.get_steps()
        return home_steps, dur

    def posttest(self, start_steps, max_missed, home: list):
        self.machine.toolhead.wait_moves()
        dur = perf_counter()
        self.home(home[0], home[1], home[2])
        self.machine.toolhead.wait_moves()
        dur = perf_counter() - dur

        valid = True
        stop_steps = self.machine.get_steps()
        step_dif = {}
        missed = {}
        if home[0]:
            step_dif["x"] = abs(start_steps["x"] - stop_steps["x"])
            missed["x"] = step_dif['x']/self.machine.steppers['x'][2]
            if missed["x"] > max_missed:
                valid = False
        if home[1]:
            step_dif["y"] = abs(start_steps["y"] - stop_steps["y"])
            missed["y"] = step_dif['y']/self.machine.steppers['y'][2]
            if missed["y"] > max_missed:
                valid = False
        if home[2]:
            step_dif["z"] = abs(start_steps["z"] - stop_steps["z"])
            missed["z"] = step_dif['z']/self.machine.steppers['z'][2]
            if missed["z"] > max_missed:
                valid = False

        return valid, stop_steps, missed, dur

    def endstop_variance(self, samples: int, x=True, y=True):
        variance = {
            "x": [],
            "y": [],
            "steps": {
                "x": None,
                "y": None
            }
        }
        for _ in range(0, samples):
            self.machine.toolhead.wait_moves()
            self.home(x, y, False)
            steps = self.machine.get_steps()

            if x:
                if variance["steps"]["x"] is not None:
                    x_dif = abs(variance["steps"]["x"] - steps["x"])
                    missed_x = x_dif/self.machine.steppers['x'][2]
                    variance["x"].append(missed_x)
                variance["steps"]["x"] = steps["x"]
            if y:
                if variance["steps"]["y"] is not None:
                    y_dif = abs(variance["steps"]["y"] - steps["y"])
                    missed_y = y_dif/self.machine.steppers['y'][2]
                    variance["y"].append(missed_y)
                variance["steps"]["y"] = steps["y"]
        return variance

    def validate(self, speed, iterations, margin, small_margin, max_missed):
        axis_limits = self.machine.axis_limits
        pos = {
            "x": {
                "min": axis_limits["x"]["min"] + margin,
                "max": axis_limits["x"]["max"] - margin,
                "center_min": axis_limits["x"]["center"] - (small_margin/2),
                "center_max": axis_limits["x"]["center"] + (small_margin/2),
            },
            "y": {
                "min": axis_limits["y"]["min"] + margin,
                "max": axis_limits["y"]["max"] - margin,
                "center_min": axis_limits["y"]["center"] - (small_margin/2),
                "center_max": axis_limits["y"]["center"] + (small_margin/2),
            }
        }
        self.machine.toolhead.wait_moves()
        self.home(True, True, False)
        start_steps = self.machine.get_steps()
        start = perf_counter()
        for _ in range(iterations):
            self.move([pos["x"]["min"], pos["y"]["min"], None], speed)
            self.move([pos["x"]["max"], pos["y"]["max"], None], speed)
            self.move([pos["x"]["min"], pos["y"]["min"], None], speed)
            self.move([pos["x"]["max"], pos["y"]["min"], None], speed)
            self.move([pos["x"]["min"], pos["y"]["max"], None], speed)
            self.move([pos["x"]["max"], pos["y"]["min"], None], speed)

            # Large pattern box
            self.move([pos["x"]["min"], pos["y"]["min"], None], speed)
            self.move([pos["x"]["min"], pos["y"]["max"], None], speed)
            self.move([pos["x"]["max"], pos["y"]["max"], None], speed)
            self.move([pos["x"]["max"], pos["y"]["min"], None], speed)

            # Small pattern diagonals
            self.move([pos["x"]["center_min"], pos["y"]["center_min"], None], speed)
            self.move([pos["x"]["center_max"], pos["y"]["center_max"], None], speed)
            self.move([pos["x"]["center_min"], pos["y"]["center_min"], None], speed)
            self.move([pos["x"]["center_max"], pos["y"]["center_min"], None], speed)
            self.move([pos["x"]["center_min"], pos["y"]["center_max"], None], speed)
            self.move([pos["x"]["center_max"], pos["y"]["center_min"], None], speed)

            # Small pattern box
            self.move([pos["x"]["center_min"], pos["y"]["center_min"], None], speed)
            self.move([pos["x"]["center_min"], pos["y"]["center_max"], None], speed)
            self.move([pos["x"]["center_max"], pos["y"]["center_max"], None], speed)
            self.move([pos["x"]["center_max"], pos["y"]["center_min"], None], speed)

        self.machine.toolhead.wait_moves()
        duration = perf_counter() - start

        self.home(True, True, False)
        stop_steps = self.machine.get_steps()


        step_dif = {
            "x": abs(start_steps["x"] - stop_steps["x"]),
            "y": abs(start_steps["y"] - stop_steps["y"])
        }

        missed_x = step_dif['x']/self.machine.steppers['x'][2]
        missed_y = step_dif['y']/self.machine.steppers['y'][2]
        valid = True
        if missed_x > max_missed:
            valid = False
        if missed_y > max_missed:
            valid = False
        return valid, duration, missed_x, missed_y

    def level(self, gcmd):
        level = gcmd.get_int('LEVEL', 1, minval=0, maxval=1)

        if level == 0:
            return
        if self.machine.level is None:
            return

        lookup = None
        name = None
        if self.machine.level == "STA":
            raise gcmd.error("screws_tilt_adjust is manual; level the bed manually "
                             "and use LEVEL=0.")
        elif self.machine.level == "ZT":
            lookup = "z_tilt"
            name = "Z_TILT_ADJUST"
        elif self.machine.level == "QGL":
            lookup = "quad_gantry_level"
            name = "QUAD_GANTRY_LEVEL"
        else:
            raise gcmd.error(f"Unknown leveling method '{self.machine.level}'.")
        lm = self.machine.printer.lookup_object(lookup, None)
        status = getattr(lm, 'z_status', None)
        if not isinstance(getattr(status, 'applied', None), bool):
            raise gcmd.error(f"Unsupported leveling status API for {lookup}.")
        if not status.applied:
            self.machine.gcode.respond_info(f"BETTER AUTO SPEED leveling with {name}...")
            self.machine.gcode.run_script_from_command(name)
            if not status.applied:
                raise gcmd.error(f"Failed to level printer! Please manually ensure your printer is level.")
