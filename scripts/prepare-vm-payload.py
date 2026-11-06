#!/usr/bin/env python3
"""Prepare only FontLab artifacts for a read-only VM share, with offline fontTools."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import fontTools

root = Path(__file__).resolve().parent.parent
dest = root/'artifacts/vm-payload'
dest.mkdir(parents=True, exist_ok=True)
shutil.copytree(root/'dist/Fontscape.app', dest/'Fontscape.app', dirs_exist_ok=True)
# Use the newly built probe with the direct-file decoder.
shutil.copy2(root/'dist/Fontscape.app/Contents/MacOS/fontlab-probe', dest/'fontlab-probe')
shutil.copytree(root/'scripts', dest/'scripts', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
source = Path(sys.argv[1]).resolve()
shutil.copy2(source, dest/'HanNewsSerif-Medium.ttf')
vendor = dest/'python/fontTools'
shutil.copytree(Path(fontTools.__file__).parent, vendor, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns('*.so', '*.pyc', '__pycache__'))
manifest = {'purpose': 'FontLab disposable macOS VM tests', 'fontSHA256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'fontTools': fontTools.__version__, 'shareMode': 'read-only', 'hostHomeShared': False}
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print(dest)
