import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock

from better_auto_speed.motion import MotionController
from better_auto_speed.machine import Machine


class MotionTests(unittest.TestCase):
    def make_motion(self):
        th = NS(max_velocity=321., max_accel=2345., square_corner_velocity=7.,
                min_cruise_ratio=.4, requested_accel_to_decel=123.,
                max_accel_to_decel=100., junction_deviation=.02,
                wait_moves=Mock())
        th._calc_junction_deviation = lambda: setattr(th, 'max_accel_to_decel', 999.)
        machine = NS(toolhead=th, th_veloc=100., th_accel=1000., th_scv=5.,
                     gcode=NS(run_script_from_command=Mock()))
        return MotionController(machine, NS())

    def test_empty_axis_selection_does_not_issue_bare_g28(self):
        motion = self.make_motion()
        motion.home(False, False, False)
        motion.machine.gcode.run_script_from_command.assert_not_called()

    def test_roundtrip_all_limits(self):
        motion = self.make_motion()
        state = motion.capture_velocity_limits()
        motion.set_velocity(500, 5000, 10)
        motion.restore_velocity_limits(state)
        self.assertEqual(state, motion.capture_velocity_limits())

    def test_home_restores_on_success_and_failures(self):
        for fail in (None, 'gcode', 'wait', 'set'):
            with self.subTest(fail=fail):
                motion = self.make_motion()
                before = motion.capture_velocity_limits()
                if fail == 'gcode':
                    motion.machine.gcode.run_script_from_command.side_effect = ValueError('home')
                elif fail == 'wait':
                    motion.machine.toolhead.wait_moves.side_effect = ValueError('wait')
                elif fail == 'set':
                    motion.machine.toolhead._calc_junction_deviation = Mock(side_effect=ValueError('set'))
                if fail:
                    with self.assertRaises(ValueError):
                        motion.home()
                else:
                    motion.home()
                self.assertEqual(before, motion.capture_velocity_limits())

    def test_legacy_without_cruise_ratio(self):
        motion = self.make_motion()
        del motion.machine.toolhead.min_cruise_ratio
        before = motion.capture_velocity_limits()
        motion.home()
        self.assertEqual(before, motion.capture_velocity_limits())

    def test_manual_and_invalid_level_api_rejected(self):
        motion = self.make_motion()
        gcmd = NS(get_int=lambda *a, **k: 1, error=ValueError)
        for level in ('STA', 'ZT'):
            motion.machine.level = level
            motion.machine.printer = NS(lookup_object=lambda *a: NS())
            with self.assertRaises(ValueError):
                motion.level(gcmd)
        motion.machine.gcode.run_script_from_command.assert_not_called()

    def test_automatic_level_preferred_to_manual(self):
        motion = self.make_motion()
        objects = {'toolhead': motion.machine.toolhead, 'screws_tilt_adjust': NS(), 'z_tilt': NS()}
        machine = Machine(NS(lookup_object=lambda name, default=None: objects.get(name, default)), None, None, None)
        machine.handle_connect()
        self.assertEqual(machine.level, 'ZT')


if __name__ == '__main__':
    unittest.main()
