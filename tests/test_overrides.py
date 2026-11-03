import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock

from better_auto_speed.overrides import Overrides


class OverridesTests(unittest.TestCase):
    def setup_override(self, params):
        self.rail = NS(homing_speed=20., homing_retract_speed=12.)
        self.run = Mock()
        machine = NS(gcode=NS(run_script_from_command=self.run, respond_info=Mock()),
                     printer=NS(get_reactor=lambda: NS(monotonic=lambda: 0)),
                     axis_stepper_names=lambda a: ['stepper_' + a],
                     find_tmc=lambda n: NS(get_status=lambda t: {'run_current': .812345}),
                     axis_rails=lambda a: [self.rail])
        def get_float(name, default, **kwargs):
            value = params.get(name, default)
            if value == 'invalid':
                raise ValueError(name)
            return value
        self.gcmd = NS(get_float=get_float, error=ValueError)
        return Overrides(machine, NS(printer_kinematics='cartesian'))

    def test_prevalidates_late_parameter(self):
        override = self.setup_override({'X_CURRENT': 1., 'Z_HOMING_SPEED': 'invalid'})
        with self.assertRaises(ValueError):
            override.apply(self.gcmd)
        self.run.assert_not_called()

    def test_nonfinite_rejected_before_mutation(self):
        for value in (float('nan'), float('inf')):
            override = self.setup_override({'X_CURRENT': 1., 'Z_HOMING_SPEED': value})
            with self.assertRaises(ValueError):
                override.apply(self.gcmd)
            self.run.assert_not_called()

    def test_failed_apply_rolls_back_including_failed_item(self):
        override = self.setup_override({'X_CURRENT': 1., 'Y_CURRENT': 1.})
        self.run.side_effect = [None, ValueError('apply'), None, None]
        with self.assertRaisesRegex(ValueError, 'apply'):
            override.apply(self.gcmd)
        self.assertEqual(self.run.call_count, 4)
        self.assertIn('stepper_x', self.run.call_args_list[2].args[0])
        self.assertIn('stepper_y', self.run.call_args_list[3].args[0])

    def test_restore_continues_after_current_failure(self):
        override = self.setup_override({})
        self.run.side_effect = [ValueError('restore'), None]
        self.rail.homing_speed = 99
        with self.assertRaisesRegex(ValueError, 'restore'):
            override.restore({'currents': [('x', .8), ('y', .9)],
                              'rails': [(self.rail, 20., 12.)]})
        self.assertEqual(self.run.call_count, 2)
        self.assertEqual(self.rail.homing_speed, 20.)

    def test_roundtrip(self):
        override = self.setup_override({'X_CURRENT': 1., 'X_HOMING_SPEED': 30.})
        state = override.apply(self.gcmd)
        self.assertEqual(self.rail.homing_speed, 30.)
        override.restore(state)
        self.assertEqual((self.rail.homing_speed, self.rail.homing_retract_speed), (20., 12.))


if __name__ == '__main__':
    unittest.main()
