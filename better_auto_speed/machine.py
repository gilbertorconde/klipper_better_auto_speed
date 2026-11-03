# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.
#
# Runtime machine state plus the Klipper introspection (homed axes, stepper
# data, axis limits, kinematics queries) the rest of the addon relies on.


class Machine:
    TMC_DRIVERS = ("tmc2209", "tmc2208", "tmc2240", "tmc5160", "tmc2130", "tmc2660", "tmc2160")

    def __init__(self, printer, gcode, gcode_move, settings):
        self.printer = printer
        self.gcode = gcode
        self.gcode_move = gcode_move
        self.settings = settings

        self.toolhead = None
        self.level = None
        self.steppers = {}
        self.axis_limits = {}

        # Captured at connect time, reduced for positioning moves.
        self.th_accel = None
        self.th_veloc = None
        self.th_scv = None
        self.th_min_cruise_ratio = None

    def handle_connect(self):
        self.toolhead = self.printer.lookup_object('toolhead')
        # Reduce speed/acceleration for positioning movement
        self.th_accel = self.toolhead.max_accel/2
        self.th_veloc = self.toolhead.max_velocity/2
        self.th_scv = self.toolhead.square_corner_velocity
        # Original cruise-ratio limit, restored after a run. Newer Klipper uses
        # min_cruise_ratio; we neutralize it during tests so short moves reach
        # the requested velocity (otherwise accel results are inflated).
        self.th_min_cruise_ratio = getattr(self.toolhead, 'min_cruise_ratio', None)

        # Find and define leveling method
        if self.printer.lookup_object("z_tilt", None) is not None:
            self.level = "ZT"
        elif self.printer.lookup_object("quad_gantry_level", None) is not None:
            self.level = "QGL"
        elif self.printer.lookup_object("screws_tilt_adjust", None) is not None:
            self.level = "STA"
        else:
            self.level = None

    def handle_home_rails_end(self, homing_state, rails):
        # Get axis min/max values
        # Get stepper microsteps
        if not len(self.steppers.keys()) == 3:
            for rail in rails:
                pos_min, pos_max = rail.get_range()
                for stepper in rail.get_steppers():
                    name = stepper._name
                    # microsteps = (stepper._steps_per_rotation / full_steps / gearing)
                    if name in ["stepper_x", "stepper_y", "stepper_z"]:
                        config = self.printer.lookup_object('configfile').status_raw_config[name]
                        microsteps = int(config["microsteps"])

                        homing_retract_dist = config.get("homing_retract_dist", None)
                        if homing_retract_dist is None:
                            homing_retract_dist = 5 # This shouldn't be hardcoded
                        homing_retract_dist = float(homing_retract_dist)
                        second_homing_speed = config.get("second_homing_speed", None)
                        if second_homing_speed is None:
                            second_homing_speed = 5 # This shouldn't be hardcoded
                        second_homing_speed = float(second_homing_speed)
                        self.steppers[name[-1]] = [pos_min, pos_max, microsteps, homing_retract_dist, second_homing_speed]

            self.build_axis_limits()

    def get_homed_axes(self):
        # Authoritative homed state, straight from the kinematics (works on all
        # Klipper versions/kinematics, regardless of how each axis was homed).
        kin = self.toolhead.get_kinematics()
        eventtime = self.printer.get_reactor().monotonic()
        return kin.get_status(eventtime).get("homed_axes", "")

    def check_homed(self, gcmd):
        homed = self.get_homed_axes()
        missing = [axis for axis in ("x", "y", "z") if axis not in homed]
        if missing:
            raise gcmd.error(
                "Printer must be homed first! "
                f"Homed axes: '{homed}', missing: {', '.join(m.upper() for m in missing)}.")
        # Make sure per-axis data exists even if the home event didn't capture it.
        self.ensure_axis_data()

    def ensure_axis_data(self):
        raw_config = self.printer.lookup_object('configfile').status_raw_config
        for axis in ("x", "y", "z"):
            if axis in self.steppers:
                continue
            name = f"stepper_{axis}"
            if name not in raw_config:
                continue
            section = raw_config[name]
            pos_min = float(section.get("position_min", 0.0))
            pos_max = float(section["position_max"])
            microsteps = int(section["microsteps"])
            homing_retract_dist = float(section.get("homing_retract_dist", 5))
            second_homing_speed = float(section.get("second_homing_speed", 5))
            self.steppers[axis] = [pos_min, pos_max, microsteps, homing_retract_dist, second_homing_speed]
        self.build_axis_limits()

    def build_axis_limits(self):
        for index, axis in enumerate(("x", "y", "z")):
            if self.steppers.get(axis, None) is None:
                continue
            pos_min = self.steppers[axis][0]
            pos_max = self.steppers[axis][1]
            self.axis_limits[axis] = {
                "min": pos_min,
                "max": pos_max,
                "center": (pos_min + pos_max) / 2,
                "dist": pos_max - pos_min,
                "home": self.gcode_move.homing_position[index]
            }

    def get_steps(self):
        kin = self.toolhead.get_kinematics()
        steppers = kin.get_steppers()
        pos = {}
        for s in steppers:
            s_name = s.get_name()
            if s_name in ["stepper_x", "stepper_y", "stepper_z"]:
                pos[s_name[-1]] = s.get_mcu_position()
        return pos

    def z_uses_probe(self):
        # True when stepper_z homes via a probe / virtual endstop (e.g. Tap).
        raw_config = self.printer.lookup_object('configfile').status_raw_config
        section = raw_config.get('stepper_z')
        if not section:
            return False
        pin = str(section.get('endstop_pin', '')).lower()
        return 'virtual_endstop' in pin or 'probe:' in pin

    def axis_stepper_names(self, axis):
        # All motors on an axis: stepper_<axis> or stepper_<axis><digits>
        kin = self.toolhead.get_kinematics()
        prefix = f"stepper_{axis}"
        names = []
        for s in kin.get_steppers():
            n = s.get_name()
            if n.startswith(prefix):
                rest = n[len(prefix):]
                if rest == "" or rest.isdigit():
                    names.append(n)
        return names

    def axis_rails(self, axis):
        target = set(self.axis_stepper_names(axis))
        kin = self.toolhead.get_kinematics()
        return [rail for rail in getattr(kin, "rails", [])
                if any(s.get_name() in target for s in rail.get_steppers())]

    def find_tmc(self, stepper_name):
        for drv in self.TMC_DRIVERS:
            obj = self.printer.lookup_object(f"{drv} {stepper_name}", None)
            if obj is not None:
                return obj
        return None
