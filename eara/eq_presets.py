"""Local EQ preset persistence, independent of hardware application."""
import json
import math
import os
from pathlib import Path
from eara.protocol import GRAPHIC_HZ


def _path():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'eara' / 'eq-preset.json'


def _validate(gains):
    if not isinstance(gains, list) or len(gains) != len(GRAPHIC_HZ):
        raise ValueError('Preset must contain eight gains')
    if any(isinstance(g, bool) or not isinstance(g, (int, float)) or not math.isfinite(g) or not -6 <= g <= 6 for g in gains):
        raise ValueError('Preset gains must be finite values between -6 and +6 dB')
    return [float(g) for g in gains]


def save_preset(gains):
    gains = _validate(gains)
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'version': 1, 'frequencies': list(GRAPHIC_HZ), 'gains': gains}) + '\n')
    temporary.replace(path)


def load_preset():
    path = _path()
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get('version') != 1 or data.get('frequencies') != list(GRAPHIC_HZ):
        raise ValueError('Preset frequency mapping is incompatible')
    return _validate(data.get('gains'))

# Illustrative factory-preset shapes, NOT firmware coefficients or measurements.
# They are display-only: selecting a factory preset still sends its native ID.
PRESET_PREVIEWS = {
    'balanced': (0, 0, 0, 0, 0, 0, 0, 0),
    'more_bass': (4, 3, 2, 1, 0, 0, 0, 0),
    'more_treble': (0, 0, 0, 0, 1, 2, 3, 4),
    'voice': (-2, -1, 0, 2, 3, 2, 0, -1),
    'rock': (3, 2, 0, -1, -1, 1, 2, 3),
    'electronic': (4, 3, 1, 0, -1, 1, 2, 3),
    'pop': (-1, 0, 1, 2, 2, 1, 0, -1),
    'enhance_vocals': (-2, -1, 0, 2, 3, 2, 0, -1),
    'classical': (1, 1, 0, 0, 0, 1, 2, 2),
}


def display_gains(status):
    preset = status.get('eq')
    if preset in PRESET_PREVIEWS:
        return list(PRESET_PREVIEWS[preset]), True
    gains = status.get('graphic_eq')
    return (list(gains), False) if isinstance(gains, list) else (None, False)
