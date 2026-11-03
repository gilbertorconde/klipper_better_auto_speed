"""Settings regression tests using only the Python standard library."""
import unittest
from types import SimpleNamespace

from better_auto_speed.settings import Settings


class Config:
    error = ValueError

    def __init__(self, **values):
        self.values = values

    def get_printer(self):
        return SimpleNamespace(start_args={})

    def getsection(self, name):
        return SimpleNamespace(get=lambda key: self.values.get('kinematics', 'cartesian'))

    def get(self, name, default=None):
        return self.values.get(name, default)

    def number(self, name, default, cast, **bounds):
        value = self.values.get(name, default)
        if value is None:
            return None
        value = cast(value)
        for key, bound in bounds.items():
            bad = {'above': value <= bound, 'below': value >= bound,
                   'minval': value < bound, 'maxval': value > bound}[key]
            if bad:
                raise self.error(name)
        return value

    def getfloat(self, name, default=None, **bounds):
        return self.number(name, default, float, **bounds)

    def getint(self, name, default=None, **bounds):
        return self.number(name, default, int, **bounds)

    def getboolean(self, name, default=None):
        return self.values.get(name, default)


class SettingsTests(unittest.TestCase):
    def test_valid_defaults(self):
        settings = Settings(Config())
        self.assertEqual(settings.axes, ['x', 'y'])
        self.assertIsNone(settings.cfg_accel_min)

    def test_invalid_axes(self):
        for axis in ('', 'x,nope', 'x,', ','):
            with self.subTest(axis=axis), self.assertRaises(ValueError):
                Settings(Config(axis=axis))

    def test_unsupported_kinematics(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            Settings(Config(kinematics='delta'))

    def test_contradictory_bounds(self):
        for values in (dict(accel_min=2000, accel_max=1000),
                       dict(velocity_min=100, velocity_max=100)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Settings(Config(**values))

    def test_nonfinite_config(self):
        for field in ('margin', 'max_missed', 'accel_min', 'accel_max',
                      'velocity_min', 'velocity_max', 'accel_accu',
                      'velocity_accu', 'scv', 'derate', 'z_position_speed',
                      'validate_margin', 'validate_inner_margin'):
            for value in ('nan', 'inf', '-inf'):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    Settings(Config(**{field: value}))

    def test_max_missed_must_be_positive(self):
        with self.assertRaises(ValueError):
            Settings(Config(max_missed=0))


if __name__ == '__main__':
    unittest.main()
