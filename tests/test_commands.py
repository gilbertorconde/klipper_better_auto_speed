"""Command safety regression tests; no Klipper, matplotlib or hardware required."""
import configparser
import glob
import math
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from better_auto_speed.axes import parse_axis
from better_auto_speed.commands import AutoSpeedCommands
from better_auto_speed.plotting import render_graph


class Gcmd:
    error = ValueError

    def __init__(self, **params):
        self._params = params

    def get(self, name, default=None):
        return self._params.get(name, default)

    def _number(self, name, default, convert, **bounds):
        # Like Klipper, defaults bypass constraints and NaN bypasses comparisons.
        if name not in self._params:
            return default
        value = convert(self._params[name])
        for key, bound in bounds.items():
            bad = {'above': value <= bound, 'below': value >= bound,
                   'minval': value < bound, 'maxval': value > bound}[key]
            if bad:
                raise self.error(name)
        return value

    def get_int(self, name, default=None, **bounds):
        return self._number(name, default, int, **bounds)

    def get_float(self, name, default=None, **bounds):
        return self._number(name, default, float, **bounds)


AUTOSAVE_HEADER = """
#*# <---------------------- SAVE_CONFIG ---------------------->
#*# DO NOT EDIT THIS BLOCK OR BELOW. The contents are auto-generated.
#*#
"""


class ConfigFileReader:
    """Fake of Klipper's reader: includes resolve relative to the including file."""

    def read_config_file(self, filename):
        with open(filename) as f:
            return f.read()

    def build_fileconfig_with_includes(self, data, filename):
        fileconfig = configparser.RawConfigParser(strict=False)
        self._parse(data, filename, fileconfig)
        return fileconfig

    def _parse(self, data, filename, fileconfig):
        buf = []
        for line in data.split('\n'):
            line = line.split('#', 1)[0]
            if line.strip().startswith('[include '):
                fileconfig.read_string('\n'.join(buf))
                buf = []
                spec = line.strip()[len('[include '):-1].strip()
                for name in sorted(glob.glob(os.path.join(os.path.dirname(filename), spec))):
                    self._parse(self.read_config_file(name), name, fileconfig)
            else:
                buf.append(line)
        fileconfig.read_string('\n'.join(buf))


class FakeAutosave:
    def _find_autosave_data(self, data):
        pos = data.find(AUTOSAVE_HEADER)
        if pos < 0:
            return data, ''
        lines = data[pos + len(AUTOSAVE_HEADER):].split('\n')
        return data[:pos], '\n'.join(line[4:] for line in lines)


class FakeConfigFile:
    """Klipper's printer 'configfile' object; its module provides ConfigFileReader."""

    def __init__(self):
        self.autosave = FakeAutosave()
        self.set = Mock()


class LegacyConfigFile:
    """Older Klipper/Kalico: parsing helpers live on PrinterConfig itself."""

    def __init__(self):
        self.set = Mock()
        self._reader = ConfigFileReader()
        self._read_config_file = self._reader.read_config_file
        self._find_autosave_data = FakeAutosave()._find_autosave_data

    def _build_config_wrapper(self, data, filename):
        return SimpleNamespace(
            fileconfig=self._reader.build_fileconfig_with_includes(data, filename))


class CommandTestBase(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            axes=['x', 'y'], valid_axes=['x', 'y', 'z', 'diag_x', 'diag_y'],
            printer_kinematics='cartesian', isolate_xy=True, motor_off=False,
            margin=20., max_missed=1., scv=5., derate=.8, accel_accu=.05,
            veloc_accu=.05, settling_home=True, endstop_samples=3,
            validate_iterations=1, validate_margin=20., validate_inner_margin=20.,
            cfg_accel_min=None, cfg_accel_max=None, cfg_veloc_min=None,
            cfg_veloc_max=None, results_dir='/unused')
        self.gcode = Mock()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg_dir = self.tmp.name
        self.printer_cfg = self.write_cfg('printer.cfg', '[printer]\nkinematics: cartesian\n')
        self.config = FakeConfigFile()
        self.machine = SimpleNamespace(
            gcode=self.gcode, check_homed=Mock(), steppers={'x': [], 'y': [], 'z': []},
            toolhead=SimpleNamespace(max_accel=3000., max_velocity=200.),
            axis_limits={a: dict(min=0., max=300., center=150., dist=300., home=0.)
                         for a in 'xyz'}, th_veloc=100.,
            printer=SimpleNamespace(lookup_object=lambda name: self.config,
                                    get_start_args=lambda: {'config_file': self.printer_cfg}),
            z_uses_probe=lambda: False)
        self.motion = Mock()
        self.motion.capture_velocity_limits.return_value = {'entry': 'limits'}
        self.motion.validate.return_value = (True, .1, 0., 0.)
        self.overrides = Mock()
        self.overrides.apply.return_value = {'entry': 'overrides'}
        self.search = Mock()
        def init_axis(aw, axis):
            aw.axis = axis
            aw.move = SimpleNamespace(max_dist=260.)
        self.search.init_axis.side_effect = init_axis
        self.search.resolve_accel_bounds.return_value = (1000., 10000.)
        self.search.resolve_veloc_bounds.return_value = (50., 500.)
        self.search.binary_search.return_value = 1000.
        self.commands = AutoSpeedCommands(self.machine, self.motion, self.search,
                                          self.overrides, self.settings)

    def write_cfg(self, name, text):
        path = os.path.join(self.cfg_dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(text)
        return path

    def queued(self):
        return {c.args[1]: c.args[2] for c in self.config.set.call_args_list}

    def responses(self):
        return '\n'.join(str(c.args[0]) for c in self.gcode.respond_info.call_args_list)

    def run_command(self, suffix='', **params):
        return getattr(self.commands, 'cmd_BETTER_AUTO_SPEED' + suffix)(Gcmd(**params))


class CommandTests(CommandTestBase):
    def test_invalid_input_precedes_hardware(self):
        cases = [dict(SAVE=2), dict(VALIDATE=2), dict(MOTOR_OFF='bad'),
                 dict(AXIS=''), dict(AXIS='x,unknown'), dict(AXIS='x,'),
                 dict(MARGIN=150), dict(MARGIN='nan'), dict(ACCEL='inf'),
                 dict(X_CURRENT='nan'), dict(ACCEL_MIN=2000, ACCEL_MAX=1000),
                 dict(VELOCITY_MIN=500, VELOCITY_MAX=100), dict(Z=301),
                 dict(VALIDATE=1, VALIDATE_INNER_MARGIN=280),
                 dict(VALIDATE=1, VALIDATE_MARGIN=150),
                 dict(ENDSTOP_SAMPLES=1), dict(VELOCITY_DIV=1)]
        for suffix in ('', '_ACCEL', '_VELOCITY', '_VALIDATE', '_GRAPH'):
            for params in cases:
                with self.subTest(suffix=suffix, params=params):
                    self.overrides.reset_mock()
                    self.motion.reset_mock()
                    with self.assertRaises(ValueError):
                        self.run_command(suffix, **params)
                    self.overrides.apply.assert_not_called()
                    self.motion.move.assert_not_called()
                    self.motion.restore_velocity_limits.assert_called_once_with({'entry': 'limits'})

    def test_real_search_default_coupled_preflight(self):
        from better_auto_speed.search import SpeedSearch
        self.commands.search = SpeedSearch(self.machine, self.motion, self.settings)
        self.commands._preflight(Gcmd(), 'cmd_BETTER_AUTO_SPEED')
        self.overrides.apply.assert_not_called()

    def test_real_search_graph_bounds_are_reachable(self):
        from better_auto_speed.search import SpeedSearch
        from better_auto_speed.move import MoveX
        self.commands.search = SpeedSearch(self.machine, self.motion, self.settings)
        with patch.dict(sys.modules, {'matplotlib': Mock()}):
            self.commands._preflight(Gcmd(), 'cmd_BETTER_AUTO_SPEED_GRAPH')
        # Graph's lower slope bound must be raised to the physical travel floor.
        move = MoveX()
        move.Init(self.machine.axis_limits, 20., True)
        move.Calc(self.machine.axis_limits, 700., 700. ** 2 / move.max_dist, 20.)
        self.assertAlmostEqual(move.dist, move.max_dist)

    def test_unsupported_kinematics(self):
        self.settings.printer_kinematics = 'delta'
        with self.assertRaises(ValueError):
            self.run_command('_ACCEL')
        self.overrides.apply.assert_not_called()

    def test_apply_failure_still_restores_limits(self):
        self.overrides.apply.side_effect = RuntimeError('apply')
        with self.assertRaisesRegex(RuntimeError, 'apply'):
            self.run_command('_ACCEL')
        self.motion.restore_velocity_limits.assert_called_once_with({'entry': 'limits'})

    def test_restore_failure_still_restores_limits(self):
        self.overrides.restore.side_effect = RuntimeError('restore')
        with self.assertRaisesRegex(RuntimeError, 'restore'):
            self.run_command('_VALIDATE')
        self.motion.restore_velocity_limits.assert_called_once_with({'entry': 'limits'})

    def test_entry_snapshots_are_per_invocation(self):
        self.motion.capture_velocity_limits.side_effect = ['first', 'second']
        self.run_command('_VALIDATE')
        self.run_command('_VALIDATE')
        self.assertEqual([c.args[0] for c in self.motion.restore_velocity_limits.call_args_list],
                         ['first', 'second'])

    def test_validation_gates_all_save_paths(self):
        cases = [('', dict(ACCEL=3000, VELOCITY=200)),
                 ('', dict(ACCEL=3000)), ('', dict(VELOCITY=200)),
                 ('', dict(COUPLE=0)), ('', dict(COUPLE=1)),
                 ('_ACCEL', {}), ('_VELOCITY', {}), ('_VALIDATE', {})]
        for suffix, params in cases:
            for valid in (False, True):
                with self.subTest(suffix=suffix, params=params, valid=valid):
                    self.config.set.reset_mock()
                    self.motion.validate.return_value = (valid, .1, 0., 0.)
                    self.run_command(suffix, SAVE=1, VALIDATE=1, VARIANCE=0, **params)
                    self.assertEqual(self.config.set.called, valid)

    def test_validation_exception_never_queues_save(self):
        self.motion.validate.side_effect = RuntimeError('validation')
        with self.assertRaisesRegex(RuntimeError, 'validation'):
            self.run_command(ACCEL=3000, VELOCITY=200, VALIDATE=1, VARIANCE=0)
        self.config.set.assert_not_called()

    def test_no_passing_axis_never_derates_or_saves(self):
        for suffix in ('_ACCEL', '_VELOCITY'):
            self.search.binary_search.side_effect = [1000., None]
            with self.assertRaisesRegex(ValueError, 'No passing'):
                self.run_command(suffix)
        self.config.set.assert_not_called()

    def test_coupled_uses_return_contract_not_valid_max(self):
        self.run_command(COUPLE=1, VARIANCE=0)
        self.config.set.assert_called()

    def test_no_passing_coupled_pair_does_not_save(self):
        self.search.binary_search.return_value = None
        self.run_command(COUPLE=1, VARIANCE=0)
        self.config.set.assert_not_called()

    def test_nested_preflight_before_preparation(self):
        self.search.resolve_veloc_bounds.side_effect = ValueError('nested bounds')
        with self.assertRaisesRegex(ValueError, 'nested bounds'):
            self.run_command(COUPLE=0)
        self.overrides.apply.assert_not_called()
        self.motion.level.assert_not_called()

    def test_caller_params_unchanged_and_motor_off_once(self):
        cmd = Gcmd(ACCEL=3000, VELOC=200, VALIDATE=1, MOTOR_OFF=1,
                   X_CURRENT=.8, VARIANCE=0)
        original = dict(cmd._params)
        self.commands.cmd_BETTER_AUTO_SPEED(cmd)
        self.assertEqual(cmd._params, original)
        self.gcode.run_script_from_command.assert_called_once_with('M84')

    def test_graph_bounds_fail_before_overrides(self):
        for params in (dict(ACCEL_MIN_SLOPE=0),
                       dict(ACCEL_MIN_SLOPE=100, ACCEL_MAX_SLOPE=100)):
            with self.subTest(params=params), self.assertRaises(ValueError):
                self.run_command('_GRAPH', **params)
        self.overrides.apply.assert_not_called()

    def test_graph_no_passing_search_is_rendered_and_restored(self):
        self.search.binary_search.return_value = None
        with patch.dict(sys.modules, {'matplotlib': Mock()}), \
                patch('better_auto_speed.commands.render_graph') as render:
            self.run_command('_GRAPH')
        self.assertEqual(render.call_count, 2)
        self.assertTrue(all(v is None for v in render.call_args.args[4]))
        self.motion.restore_velocity_limits.assert_called_once_with({'entry': 'limits'})

    def test_single_validation_uses_entry_companion(self):
        def search(aw):
            self.machine.toolhead.max_velocity = 999.
            return 1000.
        self.search.binary_search.side_effect = search
        self.run_command('_ACCEL', VALIDATE=1, SAVE=0)
        self.motion.validate.assert_called_once_with(200., 1, 20., 20., 1.)

    def test_graph_none_is_a_gap(self):
        plt = Mock()
        mpl = Mock()
        mpl.pyplot = plt
        with patch.dict(sys.modules, {'matplotlib': mpl, 'matplotlib.pyplot': plt}), \
                patch('better_auto_speed.plotting.os.makedirs'):
            render_graph('/unused', 'x', .05, [100, 200], [1000, None],
                         [500, 500], [2000, 2000], .8)
        self.assertTrue(math.isnan(plt.plot.call_args_list[0].args[1][1]))
        self.assertTrue(math.isnan(plt.plot.call_args_list[1].args[1][1]))

    def test_axis_parser_rejects_unknown_and_deduplicates(self):
        self.assertEqual(parse_axis(' X, x, y ', ['x', 'y']), ['x', 'y'])
        with self.assertRaises(ValueError):
            parse_axis('x,nope', ['x', 'y'])


if __name__ == '__main__':
    unittest.main()


class SaveConflictTests(CommandTestBase):
    """SAVE must never queue a [printer] option SAVE_CONFIG would reject."""

    def save(self, accel=8123.4, velocity=412.):
        self.commands._save_to_config(Gcmd(), accel=accel, velocity=velocity)

    def test_safe_options_are_queued(self):
        # Only present in the autosave block (or nowhere): safe to queue.
        self.write_cfg('printer.cfg', '[printer]\nkinematics: corexy\n' + AUTOSAVE_HEADER +
                       '#*# [printer]\n#*# max_accel = 5000\n')
        self.save()
        self.assertEqual(self.queued(), {'max_accel': 8123, 'max_velocity': 412})
        self.assertIn('Run SAVE_CONFIG', self.responses())
        self.assertNotIn('did NOT queue', self.responses())

    def test_defined_in_include_is_not_queued(self):
        self.write_cfg('printer.cfg', '[include config/*.cfg]\n[better_auto_speed]\n')
        include = self.write_cfg('config/kinematics.cfg',
                                 '[printer]\nkinematics: corexy\nmax_accel: 5000\n')
        self.save()
        self.assertEqual(self.queued(), {'max_velocity': 412})
        text = self.responses()
        self.assertIn('did NOT queue max_accel', text)
        self.assertIn(os.path.abspath(include), text)
        self.assertIn('  max_accel: 8123\n', text)
        self.assertNotIn('  max_velocity:', text)

    def test_defined_in_main_body_is_queued(self):
        # SAVE_CONFIG comments out main-body values itself, so this is safe.
        self.write_cfg('printer.cfg', '[printer]\nkinematics: corexy\nmax_accel: 5000\n'
                       'max_velocity: 300 # comment\n[include kin.cfg]\n')
        self.write_cfg('kin.cfg', '[stepper_x]\nstep_pin: PA0\n')
        self.save()
        self.assertEqual(self.queued(), {'max_accel': 8123, 'max_velocity': 412})
        self.assertIn('Run SAVE_CONFIG', self.responses())
        self.assertNotIn('did NOT queue', self.responses())

    def test_main_body_and_include_is_not_queued(self):
        # The include still conflicts after SAVE_CONFIG drops the main-body line.
        self.write_cfg('printer.cfg', '[printer]\nmax_accel: 5000\nmax_velocity: 300\n'
                       '[include kin.cfg]\n')
        include = self.write_cfg('kin.cfg', '[printer]\nmax_accel: 6000\n')
        self.save()
        self.assertEqual(self.queued(), {'max_velocity': 412})
        text = self.responses()
        self.assertIn('did NOT queue max_accel', text)
        self.assertIn(f'Edit [printer] in {os.path.abspath(include)} by hand', text)
        self.assertNotIn(os.path.abspath(self.printer_cfg), text)

    def test_unreadable_config_is_never_queued(self):
        os.unlink(self.printer_cfg)
        self.save()
        self.config.set.assert_not_called()
        self.assertIn('could not check', self.responses())

    def test_legacy_klipper_parser(self):
        self.config = LegacyConfigFile()
        self.write_cfg('printer.cfg', '[include kin.cfg]\n')
        self.write_cfg('kin.cfg', '[printer]\nmax_velocity: 300\n')
        self.save()
        self.assertEqual(self.queued(), {'max_accel': 8123})

    def test_every_save_path_honours_conflicts(self):
        self.write_cfg('printer.cfg', '[include kin.cfg]\n')
        self.write_cfg('kin.cfg', '[printer]\nmax_accel: 5000\nmax_velocity: 300\n')
        cases = [('', dict(ACCEL=3000, VELOCITY=200)), ('', dict(COUPLE=0)),
                 ('', dict(COUPLE=1)), ('_ACCEL', {}), ('_VELOCITY', {}),
                 ('_VALIDATE', dict(SAVE=1))]
        for suffix, params in cases:
            with self.subTest(suffix=suffix, params=params):
                self.gcode.respond_info.reset_mock()
                self.run_command(suffix, VALIDATE=1, VARIANCE=0, **params)
                self.config.set.assert_not_called()
                self.assertIn('did NOT queue', self.responses())
