"""Keep AppImage libraries out of host utilities such as bluetoothctl."""

import os

HOST_VARIABLES = (
    "PATH", "LD_LIBRARY_PATH", "LD_PRELOAD", "PYTHONHOME", "PYTHONPATH",
    "GI_TYPELIB_PATH", "XDG_DATA_DIRS",
)


def host_environment():
    """Restore the pre-AppRun environment without changing the GUI process."""
    env = os.environ.copy()
    if env.pop("EARA_APPIMAGE", None) != "1":
        return env
    for name in HOST_VARIABLES:
        original = env.pop("EARA_HOST_" + name, None)
        if original is None:
            env.pop(name, None)
        else:
            env[name] = original
    return env
