#!/usr/bin/env python3
"""Read-only system-font / process-protection inventory. No root needed."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from fontTools.ttLib import TTFont, TTCollection

output = Path(sys.argv[1])
output.parent.mkdir(parents=True, exist_ok=True)
def command(*args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=30)
    return {'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}

result = {'system': command('sw_vers'), 'sip': command('csrutil', 'status'),
          'authenticatedRoot': command('csrutil', 'authenticated-root', 'status'),
          'rootMount': [s for s in command('mount')['stdout'].splitlines() if ' on / ' in s],
          'fileVault': command('fdesetup', 'status'), 'fonts': {}, 'processes': {},
          'writesPerformed': False, 'backupVerified': False, 'recoveryBootVerified': False}
for path in ['/System/Library/Fonts/SFNS.ttf', '/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc']:
    p = Path(path)
    collection = TTCollection(p, lazy=True) if p.suffix == '.ttc' else None
    fonts = collection.fonts if collection else [TTFont(p, lazy=True)]
    faces = []
    for f in fonts:
        faces.append({'postscript': f['name'].getDebugName(6), 'glyphs': f['maxp'].numGlyphs,
                      'weight': f['OS/2'].usWeightClass,
                      'variableAxes': [{'tag': a.axisTag, 'min': a.minValue, 'default': a.defaultValue, 'max': a.maxValue} for a in f['fvar'].axes] if 'fvar' in f else []})
    if collection:
        collection.close()
    else:
        fonts[0].close()
    result['fonts'][path] = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'size': p.stat().st_size, 'faces': faces}
for label, path in {'Finder': '/System/Library/CoreServices/Finder.app', 'Dock': '/System/Library/CoreServices/Dock.app',
                    'System Settings': '/System/Applications/System Settings.app', 'Chrome': '/Applications/Google Chrome.app'}.items():
    if Path(path).exists():
        result['processes'][label] = {'signature': command('codesign', '-dv', '--verbose=4', path),
                                      'entitlements': command('codesign', '-d', '--entitlements', ':-', path)}
output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(output.resolve())
