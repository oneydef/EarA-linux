"""Linux discovery and read-only health shared by frontends."""
import os
import subprocess
from eara import bluez, operations
from eara.diagnostics import timed
from eara.platforms.base import DiagnosticSection, ServiceHealth


class LinuxPlatformServices:
    @timed("linux.service_health")
    def inspect_services(self) -> ServiceHealth:
        result = {}
        for key, command, marker in (
            ('bluetooth', ['bluetoothctl', 'show'], 'Controller '),
            ('audio', ['pactl', 'info'], 'Server Name:'),
        ):
            try:
                response = subprocess.run(command, capture_output=True, text=True,
                                          timeout=operations.timeout(6),
                                          env={**os.environ, 'LC_ALL': 'C'}, check=False)
                result[key] = response.returncode == 0 and marker in response.stdout
                if key == 'bluetooth':
                    result[key] = result[key] and 'Powered: yes' in response.stdout
            except (OSError, subprocess.SubprocessError):
                operations.check()
                result[key] = False
        return result

    @timed("linux.paired_devices")
    def paired_devices(self):
        return bluez.paired_devices()

    @timed("linux.scan_devices")
    def scan_devices(self, duration, progress=None):
        return bluez.scan_nothing_devices(duration, progress=progress)

    def is_compatible_name(self, name):
        return bluez.looks_like_nothing(name)

    def is_paired(self, address):
        return bluez.is_paired_dbus(address)

    @timed("linux.pair")
    def pair(self, address):
        bluez.pair_device(address)

    def power_off(self):
        bluez.power_off()

    def device_details(self, address):
        info = bluez.device_info(address)
        return [line.strip() for line in info.splitlines()
                if line.strip().partition(':')[0] in ('Trusted', 'ServicesResolved', 'Paired')]

    @timed("linux.audio_diagnostics")
    def audio_diagnostics(self):
        sections = []
        for kind in ('cards', 'sinks', 'sources'):
            try:
                output = subprocess.check_output(
                    ['pactl', 'list', 'short', kind], text=True,
                    stderr=subprocess.PIPE, timeout=operations.timeout(6),
                    env={**os.environ, 'LC_ALL': 'C'},
                )
                sections.append(DiagnosticSection(f'Pulse {kind}', output.strip() or '(empty)', True))
            except (subprocess.SubprocessError, OSError) as exc:
                operations.check()
                sections.append(DiagnosticSection(f'Pulse {kind}', f'unavailable ({exc})', False))
        return sections

    def recovery_hint(self):
        return bluez.recover_hint()
