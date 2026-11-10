"""Build orchestration checks using fake tools, never installs a Flatpak."""
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest


class FlatpakBuildTests(unittest.TestCase):
    def test_manifest_exposes_host_bluetooth_without_unrestricted_bus_or_files(self):
        repo = Path(__file__).resolve().parents[1]
        manifest = (repo / 'flatpak/io.github.oneydef.eara.yml').read_text()
        self.assertIn('buildsystem: meson', manifest)
        # AF_BLUETOOTH is unavailable in a separate network namespace.
        for permission in ('--share=network', '--allow=bluetooth', '--system-talk-name=org.bluez'):
            self.assertIn(permission, manifest)
        for permission in ('--socket=system-bus', '--filesystem=host', '--filesystem=home'):
            self.assertNotIn(permission, manifest)

    def test_snapshot_and_manifest_runtime_with_optional_install(self):
        repo = Path(__file__).resolve().parents[1]
        for offline in (True, False):
            with self.subTest(offline=offline), TemporaryDirectory() as tmp:
                root = Path(tmp) / 'project with spaces'
                for name in ('scripts', 'eara', 'packaging', 'flatpak', 'dist', 'bin'):
                    (root / name).mkdir(parents=True, exist_ok=True)
                shutil.copy2(repo / 'scripts/build-flatpak.sh', root / 'scripts/build-flatpak.sh')
                shutil.copy2(repo / 'flatpak/io.github.oneydef.eara.yml', root / 'flatpak/io.github.oneydef.eara.yml')
                shutil.copy2(repo / 'meson.build', root / 'meson.build')
                (root / 'LICENSE').write_text('fixture')
                (root / 'eara/current.py').write_text('current working tree')
                (root / 'dist/not-a-source').write_text('exclude')
                log = root / 'calls'
                for tool in ('flatpak', 'flatpak-builder'):
                    executable = root / 'bin' / tool
                    executable.write_text('#!/bin/sh\nprintf "%s\\n" "$0" "$@" >> "$TEST_CALLS"\n')
                    executable.chmod(0o755)
                args = ['bash', str(root / 'scripts/build-flatpak.sh'), '--no-install']
                if offline:
                    args.append('--offline')
                result = subprocess.run(args, env={**os.environ,
                    'PATH': str(root / 'bin') + os.pathsep + os.environ['PATH'],
                    'TEST_CALLS': str(log)}, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = log.read_text().splitlines()
                self.assertNotIn('--install', calls)
                self.assertEqual('--disable-download' in calls, offline)
                if not offline:
                    self.assertIn('org.gnome.Platform//51', calls)
                    self.assertIn('org.gnome.Sdk//51', calls)
                snapshot = root / 'dist/flatpak-source'
                self.assertEqual((snapshot / 'eara/current.py').read_text(), 'current working tree')
                self.assertTrue((snapshot / 'meson.build').is_file())
                self.assertFalse((snapshot / 'dist').exists())
                manifest = (root / 'dist/flatpak-local.yml').read_text()
                self.assertIn('type: dir', manifest)
                self.assertNotIn('tag: v0.6.1', manifest)
