"""Read-only service diagnostics. No reset, reconnect, or module reload."""
import subprocess


def inspect_services():
    result = {}
    for key, command, marker in (
        ('bluetooth', ['bluetoothctl', 'show'], 'Controller '),
        ('audio', ['pactl', 'info'], 'Server Name:'),
    ):
        try:
            response = subprocess.run(command, capture_output=True, text=True, timeout=6,
                                      env={**__import__('os').environ, 'LC_ALL': 'C'}, check=False)
            result[key] = response.returncode == 0 and marker in response.stdout
            if key == 'bluetooth':
                result[key] = result[key] and 'Powered: yes' in response.stdout
        except (OSError, subprocess.SubprocessError):
            result[key] = False
    return result
