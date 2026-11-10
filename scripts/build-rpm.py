#!/usr/bin/env python3
"""Build an RPM from a clean staging tree without touching the checkout."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def build():
    root = Path(__file__).resolve().parents[1]
    version = os.environ.get('VERSION') or subprocess.check_output(
        ['python3', '-c', 'from eara import __version__; print(__version__)'],
        cwd=root, text=True,
    ).strip()
    nfpm = shutil.which(os.environ.get('NFPM', 'nfpm'))
    if nfpm is None:
        raise SystemExit('nfpm is required to build the RPM')
    target = root / 'dist' / f'eara-{version}-1.noarch.rpm'
    target.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='eara-rpm-') as directory:
        stage = Path(directory)
        for name in ('eara', 'packaging'):
            shutil.copytree(root / name, stage / name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))
        for name in ('nfpm.yaml', 'LICENSE', 'NOTICE'):
            shutil.copy2(root / name, stage / name)
        subprocess.run([nfpm, 'pkg', '--packager', 'rpm', '--target', str(target)],
                       cwd=stage, env={**os.environ, 'VERSION': version}, check=True)


if __name__ == '__main__':
    build()
