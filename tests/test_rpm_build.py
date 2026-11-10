"""Exercise the packaging helper in an isolated checkout, without nFPM."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class RpmBuildTests(unittest.TestCase):
    def test_clean_staging_preserves_sources_and_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            shutil.copy2(Path(__file__).resolve().parents[1] / 'scripts/build-rpm.py',
                         root / 'scripts/build-rpm.py')
            (root / 'eara/__pycache__').mkdir(parents=True)
            (root / 'eara/__init__.py').write_text('__version__ = "1.2.3"\n')
            (root / 'eara/__pycache__/stale.pyc').write_bytes(b'stale')
            (root / 'packaging/ui').mkdir(parents=True)
            (root / 'packaging/ui/icon.svg').write_text('<svg/>')
            for name in ('nfpm.yaml', 'LICENSE', 'NOTICE'):
                (root / name).write_text(name)
            fake = root / 'nfpm'
            fake.write_text('#!' + sys.executable + '\n' + '''
import os, sys
from pathlib import Path
assert os.environ['VERSION'] == '1.2.3'
assert not list(Path('.').rglob('*.pyc'))
assert not list(Path('.').rglob('__pycache__'))
assert Path('eara/__init__.py').read_text() == '__version__ = "1.2.3"\\n'
assert Path('packaging/ui/icon.svg').read_text() == '<svg/>'
Path(sys.argv[-1]).write_text(str(Path.cwd()))
''')
            fake.chmod(0o755)
            env = {**os.environ, 'NFPM': str(fake), 'PYTHONDONTWRITEBYTECODE': '1'}
            env.pop('VERSION', None)
            subprocess.run([sys.executable, str(root / 'scripts/build-rpm.py')],
                           cwd=directory, env=env, check=True)
            stage = Path((root / 'dist/eara-1.2.3-1.noarch.rpm').read_text())
            self.assertFalse(stage.exists())
            self.assertTrue((root / 'eara/__pycache__/stale.pyc').exists())
