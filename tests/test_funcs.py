# Find your printers max speed before losing steps
#
# Copyright (C) 2026 gilbertorconde (https://github.com/gilbertorconde) - Better Auto Speed fork
#
# This file may be distributed under the terms of the MIT license.
#
# Pure-math tests for better_auto_speed.funcs (no Klipper required).

import math
import unittest

from better_auto_speed.funcs import (
    calculate_velocity,
    calculate_accel,
    calculate_distance,
    calculate_diagonal,
    calculate_graph,
    calculate_move_time,
)


class FunctionTests(unittest.TestCase):
    def test_calculate_velocity(self):
        self.assertAlmostEqual(calculate_velocity(1000.0, 250.0), 500.0)


    def test_calculate_accel(self):
        assert calculate_accel(100.0, 250.0) == 100.0 ** 2 / 250.0


    def test_calculate_distance(self):
        assert calculate_distance(100.0, 1000.0) == 100.0 ** 2 / 1000.0


    def test_velocity_accel_distance_roundtrip(self):
        accel = 2000.0
        travel = 180.0
        veloc = calculate_velocity(accel, travel)
        # The velocity reachable over `travel` ramps back to that same travel.
        assert math.isclose(calculate_distance(veloc, accel), travel)


    def test_calculate_diagonal(self):
        assert calculate_diagonal(3.0, 4.0) == 5.0


    def test_calculate_graph(self):
        assert calculate_graph(200.0, 100) == 10000.0 / (200.0 / 100)


    def test_move_time_trapezoid(self):
        # dist >= veloc^2/accel -> reaches cruise velocity (trapezoid).
        accel, veloc, dist = 1000.0, 100.0, 100.0
        assert math.isclose(calculate_move_time(accel, veloc, dist), veloc / accel + dist / veloc)


    def test_move_time_triangle(self):
        # dist < veloc^2/accel -> never reaches veloc (triangle profile).
        accel, veloc, dist = 1000.0, 100.0, 5.0
        assert math.isclose(calculate_move_time(accel, veloc, dist), 2.0 * math.sqrt(dist / accel))


    def test_move_time_guards(self):
        assert calculate_move_time(1000.0, 100.0, 0.0) == float('inf')
        assert calculate_move_time(0.0, 100.0, 100.0) == float('inf')
        assert calculate_move_time(1000.0, 0.0, 100.0) == float('inf')


    def test_invalid_motion_values(self):
        for fn in (calculate_velocity, calculate_accel, calculate_distance):
            for invalid in (0, -1, float("nan"), float("inf")):
                for args in ((invalid, 100), (100, invalid)):
                    with self.subTest(function=fn.__name__, args=args):
                        with self.assertRaises(ValueError):
                            fn(*args)


if __name__ == "__main__":
    unittest.main()
