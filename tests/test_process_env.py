"""AppImage host commands must not load bundled Python or shared libraries."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from eara.process_env import HOST_VARIABLES, host_environment


class HostEnvironmentTests(unittest.TestCase):
    def test_normal_launch_preserves_environment(self):
        original = {'PATH': '/usr/bin', 'PYTHONPATH': '/custom', 'LD_LIBRARY_PATH': ''}
        with patch.dict(os.environ, original, clear=True):
            self.assertEqual(host_environment(), original)

    def test_appimage_restores_values_and_unset_variables_without_mutating_parent(self):
        original = {'PATH': '/usr/bin:/bin', 'LD_LIBRARY_PATH': '',
                    'XDG_DATA_DIRS': '/usr/share:/opt/share'}
        bundled = {name: '/tmp/AppDir/usr' for name in HOST_VARIABLES}
        bundled.update({'EARA_APPIMAGE': '1', 'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1000/bus'})
        bundled.update({'EARA_HOST_' + key: value for key, value in original.items()})
        with patch.dict(os.environ, bundled, clear=True):
            restored = host_environment()
            self.assertEqual(os.environ, bundled)
        self.assertEqual(restored, {**original, 'DBUS_SESSION_BUS_ADDRESS': bundled['DBUS_SESSION_BUS_ADDRESS']})

    def test_child_uses_host_executable_and_python_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory)
            fake = fake_bin / 'python3'
            fake.write_text('#!/bin/sh\nexit 79\n')
            fake.chmod(0o755)
            with patch.dict(os.environ, {
                'EARA_APPIMAGE': '1', 'EARA_HOST_PATH': '/usr/bin:/bin',
                'PATH': str(fake_bin), 'PYTHONHOME': '/nonexistent/AppDir/usr',
                'PYTHONPATH': '/nonexistent/AppDir/packages',
            }, clear=True):
                result = subprocess.run(['python3', '-c', 'import sys; print(sys.executable)'],
                                        env=host_environment(), capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), '/usr/bin/python3')

    def test_apprun_captures_host_environment_before_overrides(self):
        source = (Path(__file__).resolve().parents[1] / 'scripts/build-packages.sh').read_text()
        launcher = source.split('cat > "$APPDIR/AppRun" <<\'EOF\'\n', 1)[1].split('\nEOF', 1)[0]
        # Execute the actual snapshot section, without launching bundled Python.
        snapshot = launcher.split('export PATH="$HERE/usr/bin:$PATH"', 1)[0]
        result = subprocess.run(['/bin/sh', '-c', snapshot + '\n/usr/bin/env'],
                                env={'PATH': '/usr/bin:/bin', 'APPDIR': '/tmp/example',
                                     'LD_LIBRARY_PATH': '', 'PYTHONPATH': 'a b:c'},
                                capture_output=True, text=True, check=True)
        env = dict(line.split('=', 1) for line in result.stdout.splitlines())
        self.assertEqual(env['EARA_HOST_PATH'], '/usr/bin:/bin')
        self.assertEqual(env['EARA_HOST_LD_LIBRARY_PATH'], '')
        self.assertEqual(env['EARA_HOST_PYTHONPATH'], 'a b:c')
        self.assertNotIn('EARA_HOST_PYTHONHOME', env)
        self.assertEqual(env['EARA_APPIMAGE'], '1')
