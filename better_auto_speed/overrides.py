# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.
#
# Temporary per-axis motor-current and homing-speed overrides applied during a
# run and restored afterwards.


import math


class Overrides:
    def __init__(self, machine, settings):
        self.machine = machine
        self.settings = settings

    def _xy_coupled(self):
        return self.settings.printer_kinematics in ("corexy", "hybrid_corexy", "markforged")

    def apply(self, gcmd):
        state = {"currents": [], "rails": []}
        applied = []
        current_plan = []
        rail_plan = []

        # Resolve current per axis, with CoreXY A/B coupling.
        xc = gcmd.get_float("X_CURRENT", None, above=0.0)
        yc = gcmd.get_float("Y_CURRENT", None, above=0.0)
        zc = gcmd.get_float("Z_CURRENT", None, above=0.0)
        for value in (xc, yc, zc):
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise gcmd.error("Motor currents must be finite and positive.")
        current_by_axis = {}
        if self._xy_coupled():
            if xc is not None and yc is not None and abs(xc - yc) > 1e-9:
                self.machine.gcode.respond_info(
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
            names = self.machine.axis_stepper_names(axis)
            if not names:
                raise gcmd.error(f"No steppers found for {axis.upper()} current override.")
            for name in names:
                tmc = self.machine.find_tmc(name)
                if tmc is None:
                    raise gcmd.error(f"No TMC driver for {name}.")
                orig = tmc.get_status(self.machine.printer.get_reactor().monotonic())["run_current"]
                if not math.isfinite(orig) or orig <= 0:
                    raise gcmd.error(f"Invalid runtime current for {name}.")
                current_plan.append((name, orig, cur))
                applied.append(f"{name} I={cur:.2f}A")

        # Homing speed is always per-axis / independent.
        for axis in ("x", "y", "z"):
            hs = gcmd.get_float(f"{axis.upper()}_HOMING_SPEED", None, above=0.0)
            if hs is not None:
                if not math.isfinite(hs) or hs <= 0:
                    raise gcmd.error("Homing speeds must be finite and positive.")
                rails = self.machine.axis_rails(axis)
                if not rails:
                    raise gcmd.error(f"No rails found for {axis.upper()} homing override.")
                for rail in rails:
                    rail_plan.append((rail, rail.homing_speed,
                                      getattr(rail, "homing_retract_speed", None), hs))
                    applied.append(f"{axis} home={hs:.0f}mm/s")

        # No mutation until every parameter and target has been resolved.
        try:
            for name, orig, cur in current_plan:
                state["currents"].append((name, orig))
                self.machine.gcode.run_script_from_command(
                    f"SET_TMC_CURRENT STEPPER={name} CURRENT={cur:.17g}")
            for rail, speed, retract, hs in rail_plan:
                state["rails"].append((rail, speed, retract))
                rail.homing_speed = hs
                if hasattr(rail, "homing_retract_speed"):
                    rail.homing_retract_speed = hs
            if not state["currents"] and not state["rails"]:
                return None
            self.machine.gcode.respond_info(
                "BETTER AUTO SPEED applied overrides: " + ", ".join(applied))
        except Exception as error:
            try:
                self.restore(state)
            except Exception as cleanup_error:
                raise error from cleanup_error
            raise
        return state

    def restore(self, state):
        if not state:
            return
        errors = []
        for name, orig in state["currents"]:
            try:
                self.machine.gcode.run_script_from_command(
                    f"SET_TMC_CURRENT STEPPER={name} CURRENT={orig:.17g}")
            except Exception as error:
                errors.append(error)
        for rail, homing_speed, homing_retract_speed in state["rails"]:
            for attr, value in (("homing_speed", homing_speed),
                                ("homing_retract_speed", homing_retract_speed)):
                if value is None:
                    continue
                try:
                    setattr(rail, attr, value)
                except Exception as error:
                    errors.append(error)
        if errors:
            raise errors[0]
