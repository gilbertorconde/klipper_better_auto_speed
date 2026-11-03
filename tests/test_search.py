"""Search regressions with fake motion; never contact a printer."""
import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from better_auto_speed.search import SpeedSearch
from better_auto_speed.wrappers import AttemptWrapper


def make_search():
    limits = {a: {'min': 0.0, 'max': 300.0, 'dist': 300.0, 'home': 0.0}
              for a in ('x', 'y', 'z')}
    machine = SimpleNamespace(axis_limits=limits, gcode=SimpleNamespace(respond_info=Mock()))
    motion = SimpleNamespace(prehome=Mock(return_value=(0, 0.0)))
    settings = SimpleNamespace(cfg_accel_min=None, cfg_accel_max=None,
                               cfg_veloc_min=None, cfg_veloc_max=None, isolate_xy=True)
    return SpeedSearch(machine, motion, settings)


def gcmd(**values):
    return SimpleNamespace(get_float=lambda name, default, **kwargs: values.get(name, default))


class SearchTests(unittest.TestCase):
    def wrapper(self, search, lower=100.0, upper=1000.0, kind='accel'):
        aw = AttemptWrapper()
        aw.type, aw.min, aw.max = kind, lower, upper
        aw.accuracy, aw.margin = .01, 20.0
        aw.veloc, aw.accel = 1.0, 1.0
        search.init_axis(aw, 'x')
        return aw

    def run_search(self, threshold, lower=100.0, upper=1000.0, accuracy=.01, kind='accel'):
        search = make_search()
        aw = self.wrapper(search, lower, upper, kind)
        aw.accuracy = accuracy
        measured = []

        def attempt(aw):
            value = aw.veloc if kind == 'velocity' else aw.accel
            measured.append(value)
            aw.missed = {'x': 0, 'y': 0, 'z': 0}
            aw.move_dist = aw.move.dist
            self.assertLessEqual(aw.veloc ** 2 / aw.accel, aw.move.dist * (1 + 1e-12))
            return value <= threshold

        search.attempt = attempt
        result = search.binary_search(aw)
        passing = [v for v in measured if v <= threshold]
        self.assertEqual(result, max(passing) if passing else None)
        self.assertEqual(result, aw.valid_max)
        self.assertEqual(measured[0], lower)
        self.assertEqual(len(measured), len(set(measured)))
        self.assertLessEqual(len(measured), 66)
        return result, measured

    def test_all_fail(self):
        self.assertEqual(self.run_search(0), (None, [100.0]))

    def test_all_pass_returns_tested_upper(self):
        self.assertEqual(self.run_search(1000), (1000.0, [100.0, 1000.0]))

    def test_highest_measured_pass_not_next_midpoint(self):
        for kind in ('accel', 'graph', 'velocity'):
            result, _ = self.run_search(637.5, kind=kind)
            self.assertLessEqual(result, 637.5)
            self.assertGreaterEqual(result, 637.5 / 1.01)

    def test_only_lower_passes(self):
        result, _ = self.run_search(100)
        self.assertEqual(result, 100)

    def test_equal_and_fractional_bounds(self):
        self.assertEqual(self.run_search(100, 100, 100), (100, [100]))
        self.assertEqual(self.run_search(0, 100, 100), (None, [100]))
        result, _ = self.run_search(100.125, 100.0, 100.25, .00001)
        self.assertEqual(result, 100.125)

    def test_termination_at_float_resolution(self):
        self.run_search(637.5, accuracy=5e-324)
        self.run_search(100, 100, math.nextafter(100, math.inf), 5e-324)

    def test_invalid_search_rejected_before_homing(self):
        for lower, upper, accuracy in [(200, 100, .1), (0, 100, .1),
                                      (100, float('inf'), .1), (float('nan'), 100, .1),
                                      (100, 200, 0), (100, 200, 1), (100, 200, float('nan'))]:
            search = make_search()
            aw = self.wrapper(search, lower, upper)
            aw.accuracy = accuracy
            with self.assertRaises(ValueError):
                search.binary_search(aw)
            search.motion.prehome.assert_not_called()

    def test_fixed_companion_unreachable_before_homing(self):
        for kind in ('accel', 'velocity'):
            search = make_search()
            aw = self.wrapper(search, kind=kind)
            if kind == 'accel':
                aw.veloc = 1000
            else:
                aw.accel = 100
            with self.assertRaises(ValueError):
                search.binary_search(aw)
            search.motion.prehome.assert_not_called()

    def test_fixed_velocity_full_travel_is_reached(self):
        search = make_search()
        aw = self.wrapper(search, 100, 200)
        aw.veloc = math.sqrt(100 * aw.move.max_dist)
        aw.full_dist = True

        def attempt(aw):
            self.assertAlmostEqual(aw.move.dist, aw.move.max_dist)
            self.assertLessEqual(aw.veloc ** 2 / aw.accel, aw.move.dist * (1 + 1e-12))
            aw.missed = {'x': 0, 'y': 0, 'z': 0}
            return True

        search.attempt = attempt
        self.assertEqual(search.binary_search(aw), 200)

    def test_bounds_defaults_and_reachability(self):
        search = make_search()
        self.assertEqual(search.resolve_accel_bounds(gcmd(), 100, 200), (400, 100000))
        self.assertEqual(search.resolve_veloc_bounds(gcmd(), 100, 400), (50, 200))
        self.assertEqual(search.resolve_veloc_bounds(gcmd(), 1, 100), (10, 10))
        for values in ({'ACCEL_MIN': 200}, {'ACCEL_MAX': 300}, {'ACCEL_MIN': 0}, {'ACCEL_MAX': float('inf')}):
            with self.assertRaises(ValueError):
                search.resolve_accel_bounds(gcmd(**values), 100, 200)
        for values in ({'VELOCITY_MAX': 201}, {'VELOCITY_MIN': 201}, {'VELOCITY_MIN': 0}, {'VELOCITY_MAX': float('nan')}):
            with self.assertRaises(ValueError):
                search.resolve_veloc_bounds(gcmd(**values), 100, 400)
        for travel in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                search.resolve_accel_bounds(gcmd(), travel, None)
            with self.assertRaises(ValueError):
                search.resolve_veloc_bounds(gcmd(), travel, 400)

    def test_configured_bounds_are_not_silently_clamped(self):
        search = make_search()
        search.settings.cfg_accel_min = 1
        with self.assertRaises(ValueError):
            search.resolve_accel_bounds(gcmd(), 100, 200)
        search.settings.cfg_veloc_max = 201
        with self.assertRaises(ValueError):
            search.resolve_veloc_bounds(gcmd(), 100, 400)


if __name__ == '__main__':
    unittest.main()
