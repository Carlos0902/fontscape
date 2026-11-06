"""Check the packaged app without installing fonts or changing user settings."""
import json
import pathlib
import plistlib
import subprocess
import sys

app = pathlib.Path(sys.argv[1]).resolve()
info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
assert info['CFBundleExecutable'] == 'Fontscape'
for name in ('Fontscape', 'fontlab-probe', 'fontscape-system'):
    binary = app / 'Contents/MacOS' / name
    arches = subprocess.check_output(['lipo', '-archs', str(binary)], text=True).split()
    assert {'arm64', 'x86_64'} <= set(arches), arches
cli = str(app / 'Contents/MacOS/fontlab-probe')
result = subprocess.run([cli, 'snapshot'], capture_output=True, text=True, check=True, timeout=30)
assert 'appkitSystem' in json.loads(result.stdout)
result = subprocess.run([cli, 'check', '/nonexistent/fontscape-test.ttf'], capture_output=True, text=True, timeout=30)
assert result.returncode != 0
print('Packaged app: universal binaries, native probe, invalid-font handling verified')

helper = str(app / 'Contents/MacOS/fontscape-system')
state = json.loads(subprocess.check_output([helper, 'inspect'], timeout=30))
assert 'protectionsReady' in state and 'volumeUUID' in state
assert (app / 'Contents/Resources/SYSTEM_GUIDE.md').is_file()
if state['architecture'] == 'arm64':
    import os
    runtime = app / 'Contents/Resources/Runtime'
    env = dict(os.environ, PYTHONPATH=str(runtime / 'fonttools'), PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
    subprocess.run([str(runtime/'aarch64/bin/python3'), '-B', '-s', '-c', 'import fontTools; from fontTools.ttLib import TTFont; assert fontTools.__version__ == "4.60.2"'], env=env, check=True, timeout=30)
print('System-font helper, offline runtime and bundled guide verified')
