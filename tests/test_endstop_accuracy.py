import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock

from better_auto_speed.endstop_accuracy import EndstopAccuracy


class EndstopTests(unittest.TestCase):
    def setup_accuracy(self, axis='x', positive=False, probe=False):
        index = 'xyz'.index(axis)
        self.mcu = 0
        self.coord = 100. if positive else 0.
        self.moves = []
        stepper = NS(get_name=lambda: 'stepper_' + axis,
                     get_mcu_position=lambda: self.mcu,
                     get_commanded_position=lambda: self.coord,
                     get_step_dist=lambda: .01)
        def calc(positions):
            result = [0., 0., 0.]
            result[index] = positions['stepper_' + axis]
            return result
        kin = NS(get_steppers=lambda: [stepper], calc_position=calc)
        pos = [0., 0., 0.]
        pos[index] = self.coord
        th = NS(get_kinematics=lambda: kin, wait_moves=Mock(),
                get_position=lambda: pos[:],
                manual_move=lambda p, speed: self.moves.append(p))
        self.info = NS(retract_dist=5., second_homing_speed=10.,
                       positive_dir=positive, position_endstop=self.coord)
        rail = NS(get_homing_info=lambda: self.info, get_range=lambda: (0., 100.))
        self.machine = NS(check_homed=Mock(), z_uses_probe=lambda: probe,
                          axis_rails=lambda a: [rail], toolhead=th)
        def home(*axes):
            self.assertEqual(axes, tuple(i == index for i in range(3)))
            self.mcu += 2  # G28 resets logical coordinates, not MCU positions.
        self.motion = NS(home=Mock(side_effect=home))
        self.gcmd = NS(get_int=lambda *a, **k: 3, error=ValueError, respond_info=Mock())
        return EndstopAccuracy(self.machine, self.motion)

    def test_mcu_variation_survives_coordinate_reset(self):
        accuracy = self.setup_accuracy()
        accuracy.cmd_X_ENDSTOP_ACCURACY(self.gcmd)
        message = self.gcmd.respond_info.call_args.args[0]
        self.assertIn('range 0.040000', message)
        self.assertIn('average 0.020000', message)

    def test_retract_uses_actual_direction_on_every_axis(self):
        for axis in 'xyz':
            for positive in (False, True):
                with self.subTest(axis=axis, positive=positive):
                    accuracy = self.setup_accuracy(axis, positive)
                    getattr(accuracy, f'cmd_{axis.upper()}_ENDSTOP_ACCURACY')(self.gcmd)
                    self.assertEqual(self.moves[0]['xyz'.index(axis)], 95. if positive else 5.)

    def test_probe_rejected_without_motion(self):
        accuracy = self.setup_accuracy('z', probe=True)
        with self.assertRaisesRegex(ValueError, 'PROBE_ACCURACY'):
            accuracy.cmd_Z_ENDSTOP_ACCURACY(self.gcmd)
        self.motion.home.assert_not_called()

    def test_invalid_retract_rejected_without_motion(self):
        accuracy = self.setup_accuracy()
        self.info.retract_dist = 200.
        with self.assertRaisesRegex(ValueError, 'travel limits'):
            accuracy.cmd_X_ENDSTOP_ACCURACY(self.gcmd)
        self.motion.home.assert_not_called()

    def test_one_sample(self):
        accuracy = self.setup_accuracy()
        self.gcmd.get_int = lambda *a, **k: 1
        accuracy.cmd_X_ENDSTOP_ACCURACY(self.gcmd)
        self.assertIn('range 0.000000', self.gcmd.respond_info.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
