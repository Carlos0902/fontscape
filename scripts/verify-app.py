"""Check the packaged app without installing fonts or changing user settings."""
import json
import pathlib
import plistlib
import subprocess
import sys

app = pathlib.Path(sys.argv[1]).resolve()
info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
assert info['CFBundleExecutable'] == 'Fontscape'
for name in ('Fontscape', 'fontlab-probe'):
    binary = app / 'Contents/MacOS' / name
    arches = subprocess.check_output(['lipo', '-archs', str(binary)], text=True).split()
    assert {'arm64', 'x86_64'} <= set(arches), arches
cli = str(app / 'Contents/MacOS/fontlab-probe')
result = subprocess.run([cli, 'snapshot'], capture_output=True, text=True, check=True, timeout=30)
assert 'appkitSystem' in json.loads(result.stdout)
result = subprocess.run([cli, 'check', '/nonexistent/fontscape-test.ttf'], capture_output=True, text=True, timeout=30)
assert result.returncode != 0
print('Packaged app: universal binaries, native probe, invalid-font handling verified')
