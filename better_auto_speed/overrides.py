# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.
#
# Temporary per-axis motor-current and homing-speed overrides applied during a
# run and restored afterwards. Mixed into BetterAutoSpeed.


class OverridesMixin:
    TMC_DRIVERS = ("tmc2209", "tmc2208", "tmc2240", "tmc5160", "tmc2130", "tmc2660", "tmc2160")

    def _axis_stepper_names(self, axis):
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

    def _axis_rails(self, axis):
        target = set(self._axis_stepper_names(axis))
        kin = self.toolhead.get_kinematics()
        return [rail for rail in getattr(kin, "rails", [])
                if any(s.get_name() in target for s in rail.get_steppers())]

    def _find_tmc(self, stepper_name):
        for drv in self.TMC_DRIVERS:
            obj = self.printer.lookup_object(f"{drv} {stepper_name}", None)
            if obj is not None:
                return obj
        return None

    def _xy_coupled(self):
        return self.printer_kinematics in ("corexy", "hybrid_corexy", "markforged")

    def _apply_overrides(self, gcmd):
        state = {"currents": [], "rails": []}
        applied = []

        # Resolve current per axis, with CoreXY A/B coupling.
        xc = gcmd.get_float("X_CURRENT", None, above=0.0)
        yc = gcmd.get_float("Y_CURRENT", None, above=0.0)
        zc = gcmd.get_float("Z_CURRENT", None, above=0.0)
        current_by_axis = {}
        if self._xy_coupled():
            if xc is not None and yc is not None and abs(xc - yc) > 1e-9:
                self.gcode.respond_info(
                    "BETTER AUTO SPEED warning: CoreXY A/B motors normally share current; "
                    "applying X_CURRENT to stepper_x and Y_CURRENT to stepper_y as given")
                current_by_axis["x"], current_by_axis["y"] = xc, yc
            else:
                val = xc if xc is not None else yc
                if val is not None:
                    current_by_axis["x"] = current_by_axis["y"] = val
        else:
            if xc is not None:
                current_by_axis["x"] = xc
            if yc is not None:
                current_by_axis["y"] = yc
        if zc is not None:
            current_by_axis["z"] = zc

        for axis, cur in current_by_axis.items():
            for name in self._axis_stepper_names(axis):
                tmc = self._find_tmc(name)
                if tmc is None:
                    self.gcode.respond_info(f"BETTER AUTO SPEED: no TMC driver for {name}, skipping current")
                    continue
                orig = tmc.get_status(self.printer.get_reactor().monotonic())["run_current"]
                state["currents"].append((name, orig))
                self.gcode.run_script_from_command(f"SET_TMC_CURRENT STEPPER={name} CURRENT={cur:.3f}")
                applied.append(f"{name} I={cur:.2f}A")

        # Homing speed is always per-axis / independent.
        for axis in ("x", "y", "z"):
            hs = gcmd.get_float(f"{axis.upper()}_HOMING_SPEED", None, above=0.0)
            if hs is not None:
                for rail in self._axis_rails(axis):
                    state["rails"].append((rail, rail.homing_speed, getattr(rail, "homing_retract_speed", None)))
                    rail.homing_speed = hs
                    if hasattr(rail, "homing_retract_speed"):
                        rail.homing_retract_speed = hs
                    applied.append(f"{axis} home={hs:.0f}mm/s")

        if not state["currents"] and not state["rails"]:
            return None
        self.gcode.respond_info("BETTER AUTO SPEED applied overrides: " + ", ".join(applied))
        return state

    def _restore_overrides(self, state):
        if not state:
            return
        for name, orig in state["currents"]:
            self.gcode.run_script_from_command(f"SET_TMC_CURRENT STEPPER={name} CURRENT={orig:.3f}")
        for rail, homing_speed, homing_retract_speed in state["rails"]:
            rail.homing_speed = homing_speed
            if homing_retract_speed is not None:
                rail.homing_retract_speed = homing_retract_speed
