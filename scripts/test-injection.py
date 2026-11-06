#!/usr/bin/env python3
"""Exercise DYLD only in newly launched FontLab-owned hosts."""
from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
out = root / 'artifacts/injection'
out.mkdir(parents=True, exist_ok=True)
font = Path(sys.argv[1]).resolve()

def run(*args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, capture_output=True, text=True, **kwargs)

run('xcrun', 'clang', '-dynamiclib', '-fobjc-arc', '-framework', 'AppKit', '-framework', 'CoreText',
    '-I', root / 'Sources/FontHook/include', root / 'Sources/FontHook/FontHook.m',
    root / 'experiments/Injector.m', '-o', out / 'libFontLabInjector.dylib')
run('codesign', '--force', '--sign', '-', out / 'libFontLabInjector.dylib')
run('xcrun', 'swiftc', root / 'experiments/InjectionHost.swift', '-o', out / 'host-plain')
run('codesign', '--force', '--sign', '-', out / 'host-plain')
run('cp', out / 'host-plain', out / 'host-hardened')
run('codesign', '--force', '--sign', '-', '--options', 'runtime', out / 'host-hardened')
result = {}
for label in ['plain', 'hardened']:
    host = out / ('host-' + label)
    normal = run(host)
    env = dict(os.environ, FONTLAB_FONT=str(font), DYLD_INSERT_LIBRARIES=str(out / 'libFontLabInjector.dylib'))
    attempt = subprocess.run([str(host)], env=env, capture_output=True, text=True, timeout=60)
    result[label] = {'baseline': json.loads(normal.stdout),
                     'injected': json.loads(attempt.stdout) if attempt.returncode == 0 else None,
                     'stderr': attempt.stderr, 'exit': attempt.returncode,
                     'signature': run('codesign', '-dv', '--verbose=4', host).stderr}
(out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
assert result['plain']['injected']['appkit']['postscript'] == 'HanNewsSerif-Medium'
assert result['plain']['injected']['coreText'] == result['plain']['baseline']['coreText']
assert result['hardened']['injected'] == result['hardened']['baseline']
print(json.dumps(result, ensure_ascii=False, indent=2))
