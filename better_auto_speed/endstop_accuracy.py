# Find your printers max speed before losing steps
#
# Copyright (C) 2024 Anonoei <dev@anonoei.com>
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.
#
# Per-axis endstop repeatability checks (X/Y/Z_ENDSTOP_ACCURACY). Mixed into
# BetterAutoSpeed.


class EndstopAccuracyMixin:
    def cmd_X_ENDSTOP_ACCURACY(self, gcmd):

        self._check_homed(gcmd)

        # Number of samples for accuracy check
        sample_count = gcmd.get_int("SAMPLES", 10, minval=1)

        # Retrieve homing parameters for the X axis from the previously stored values
        second_homing_speed = self.steppers['x'][4]
        homing_retract_dist = self.steppers['x'][3]

        # Toolhead object to control the movement
        toolhead = self.printer.lookup_object('toolhead')
        pos = toolhead.get_position()

        # Log the starting position for X
        gcmd.respond_info("X_ENDSTOP_ACCURACY at X:%.3f (samples=%d)\n" % (pos[0], sample_count))
        gcmd.respond_info("Second Homing Speed: %.2f mm/s" % second_homing_speed)
        gcmd.respond_info("Homing Retract Distance: %.2f mm" % homing_retract_dist)


        # Create a dummy gcode command for a single sample
        fo_params = dict(gcmd.get_command_parameters())
        fo_params['SAMPLES'] = '1'
        gcode = self.printer.lookup_object('gcode')
        fo_gcmd = gcode.create_gcode_command("", "", fo_params)

        # List to store the X positions hit during each sample
        positions = []

        # Move to the X endstop sample_count times and collect the X positions
        for _ in range(sample_count):
            self._home(True, False, False)
            pos = toolhead.get_position()  # Get the current X position after homing
            positions.append(pos[0])
            toolhead.manual_move([pos[0] - homing_retract_dist, None, None], speed=second_homing_speed)  # Move away from the endstop

        # Calculate the maximum, minimum, average, and standard deviation for X positions
        max_value = max(positions)
        min_value = min(positions)
        avg_value = sum(positions) / len(positions)
        range_value = max_value - min_value

        deviation_sum = sum([(x - avg_value) ** 2 for x in positions])
        sigma = (deviation_sum / len(positions)) ** 0.5

        # Display results
        gcmd.respond_info(
            "X endstop accuracy results: maximum %.6f, minimum %.6f, range %.6f, "
            "average %.6f, standard deviation %.6f" % (max_value, min_value, range_value, avg_value, sigma))


    def cmd_Y_ENDSTOP_ACCURACY(self, gcmd):

        self._check_homed(gcmd)

        # Number of samples for accuracy check
        sample_count = gcmd.get_int("SAMPLES", 10, minval=1)

        # Retrieve homing parameters for the Y axis from the previously stored values
        second_homing_speed = self.steppers['y'][4]
        homing_retract_dist = self.steppers['y'][3]

        # Toolhead object to control the movement
        toolhead = self.printer.lookup_object('toolhead')
        pos = toolhead.get_position()

        # Log the starting position for Y
        gcmd.respond_info("Y_ENDSTOP_ACCURACY at Y:%.3f (samples=%d)\n" % (pos[1], sample_count))
        gcmd.respond_info("Second Homing Speed: %.2f mm/s" % second_homing_speed)
        gcmd.respond_info("Homing Retract Distance: %.2f mm" % homing_retract_dist)


        # Create a dummy gcode command for a single sample
        fo_params = dict(gcmd.get_command_parameters())
        fo_params['SAMPLES'] = '1'
        gcode = self.printer.lookup_object('gcode')
        fo_gcmd = gcode.create_gcode_command("", "", fo_params)

        # List to store the Y positions hit during each sample
        positions = []

        # Move to the Y endstop sample_count times and collect the Y positions
        for _ in range(sample_count):
            self._home(False, True, False)
            pos = toolhead.get_position()  # Get the current Y position after homing
            positions.append(pos[1])
            toolhead.manual_move([None, pos[1] - homing_retract_dist, None], speed=second_homing_speed)  # Move away from the endstop

        # Calculate the maximum, minimum, average, and standard deviation for Y positions
        max_value = max(positions)
        min_value = min(positions)
        avg_value = sum(positions) / len(positions)
        range_value = max_value - min_value

        deviation_sum = sum([(y - avg_value) ** 2 for y in positions])
        sigma = (deviation_sum / len(positions)) ** 0.5

        # Display results
        gcmd.respond_info(
            "Y endstop accuracy results: maximum %.6f, minimum %.6f, range %.6f, "
            "average %.6f, standard deviation %.6f" % (max_value, min_value, range_value, avg_value, sigma))

    def cmd_Z_ENDSTOP_ACCURACY(self, gcmd):

        self._check_homed(gcmd)

        # Number of samples for accuracy check
        sample_count = gcmd.get_int("SAMPLES", 10, minval=1)

        # Retrieve homing parameters for the Z axis from the previously stored values
        second_homing_speed = self.steppers['z'][4]
        homing_retract_dist = self.steppers['z'][3]

        # Toolhead object to control the movement
        toolhead = self.printer.lookup_object('toolhead')
        pos = toolhead.get_position()

        # Log the starting position for Z
        gcmd.respond_info("Z_ENDSTOP_ACCURACY at Z:%.3f (samples=%d)\n" % (pos[2], sample_count))
        gcmd.respond_info("Second Homing Speed: %.2f mm/s" % second_homing_speed)
        gcmd.respond_info("Homing Retract Distance: %.2f mm" % homing_retract_dist)


        # Create a dummy gcode command for a single sample
        fo_params = dict(gcmd.get_command_parameters())
        fo_params['SAMPLES'] = '1'
        gcode = self.printer.lookup_object('gcode')
        fo_gcmd = gcode.create_gcode_command("", "", fo_params)

        # List to store the Z positions hit during each sample
        positions = []

        # Move to the Z endstop sample_count times and collect the Z positions
        for _ in range(sample_count):
            self._home(False, False, True)
            pos = toolhead.get_position()  # Get the current Z position after homing
            positions.append(pos[2])
            toolhead.manual_move([None, None, pos[2] + homing_retract_dist], speed=second_homing_speed)  # Move away from the endstop

        # Calculate the maximum, minimum, average, and standard deviation for Z positions
        max_value = max(positions)
        min_value = min(positions)
        avg_value = sum(positions) / len(positions)
        range_value = max_value - min_value

        deviation_sum = sum([(z - avg_value) ** 2 for z in positions])
        sigma = (deviation_sum / len(positions)) ** 0.5

        # Display results
        gcmd.respond_info(
            "Z endstop accuracy results: maximum %.6f, minimum %.6f, range %.6f, "
            "average %.6f, standard deviation %.6f" % (max_value, min_value, range_value, avg_value, sigma))
