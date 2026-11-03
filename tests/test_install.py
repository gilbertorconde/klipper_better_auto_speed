"""Installer checks use temporary paths and never touch a real Klipper service."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.klipper = self.base / 'custom klipper'
        self.extras = self.klipper / 'klippy' / 'extras'
        self.extras.mkdir(parents=True)
        venv = self.base / 'custom env'
        (venv / 'bin').mkdir(parents=True)
        (venv / 'bin' / 'python').symlink_to(sys.executable)
        fakebin = self.base / 'bin'
        fakebin.mkdir()
        systemctl = fakebin / 'systemctl'
        systemctl.write_text('#!/bin/sh\necho "$@" >> "$SERVICE_LOG"\n')
        systemctl.chmod(0o755)
        self.log = self.base / 'service.log'
        self.env = dict(os.environ, KLIPPER_PATH=str(self.klipper),
                        KLIPPY_ENV=str(venv), KLIPPER_SERVICE='', INSTALL_PLOTTING='0',
                        SERVICE_LOG=str(self.log), PATH=str(fakebin) + ':' + os.environ['PATH'])

    def run_script(self, name, success=True):
        result = subprocess.run(['bash', str(ROOT / name)], cwd=self.base,
                                env=self.env, capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_external_cwd_custom_paths_idempotence_and_safe_uninstall(self):
        self.run_script('install.sh')
        self.run_script('install.sh')
        package = self.extras / 'better_auto_speed'
        self.assertEqual((package / 'main.py').resolve(), ROOT / 'better_auto_speed/main.py')
        unrelated = package / 'keep.txt'
        unrelated.write_text('user data')
        self.run_script('uninstall.sh')
        self.assertFalse((package / 'main.py').exists())
        self.assertEqual(unrelated.read_text(), 'user data')
        self.assertFalse(self.log.exists())

    def test_refuses_unrelated_file_before_linking(self):
        package = self.extras / 'better_auto_speed'
        package.mkdir()
        (package / 'main.py').write_text('user data')
        self.run_script('install.sh', success=False)
        self.assertEqual((package / 'main.py').read_text(), 'user data')
        self.assertFalse((package / '__init__.py').exists())

    def test_manual_directory_symlink(self):
        package = self.extras / 'better_auto_speed'
        package.symlink_to(ROOT / 'better_auto_speed', target_is_directory=True)
        self.run_script('install.sh')
        self.run_script('uninstall.sh')
        self.assertFalse(package.is_symlink())
        self.assertTrue((ROOT / 'better_auto_speed/main.py').exists())

    def test_explicit_service_only(self):
        self.env['KLIPPER_SERVICE'] = 'klipper-test.service'
        self.run_script('install.sh')
        self.assertEqual(self.log.read_text(), 'restart klipper-test.service\n')

    def test_invalid_service_rejected_before_install(self):
        self.env['KLIPPER_SERVICE'] = '--all'
        self.run_script('install.sh', success=False)
        self.assertFalse((self.extras / 'better_auto_speed').exists())
        self.assertFalse(self.log.exists())
