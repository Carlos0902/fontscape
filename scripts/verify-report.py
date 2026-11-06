#!/usr/bin/env python3
"""Validate behavioral evidence and post-experiment recovery, rather than API return codes."""
from pathlib import Path
import json
import sys

directory = Path(sys.argv[1])
report = json.loads((directory / 'report.json').read_text())
journal = json.loads((directory / 'journal.json').read_text())
assert 'error' not in report, report.get('error')
assert report['sourceUnchanged']
assert report['baseline'] == report['final'], 'System font baseline did not recover'
assert journal['clean'] and all(x['cleaned'] for x in journal['mutations'])
assert not report['cleanupErrors']
for item in journal['mutations']:
    if item['kind'] == 'file':
        assert not Path(item['path']).exists(), 'Installed font remains'
control = json.loads((directory / 'alias-control.json').read_text())
name = control['target']['postscript']
for stage in ['sessionFreshProcess', 'userDirectoryFreshProcess']:
    assert control[stage]['byName'][name]['postscript'] == name, 'Positive control not loaded'
    assert '/System/' not in control[stage]['byName'][name]['url']
for stage in ['afterSessionRollback', 'afterFileRollback']:
    assert control[stage]['byName'][name]['postscript'] != name, 'Control registration remains'
h = json.loads((directory / 'hook.json').read_text())
for key in ['appkitSystem', 'appkitBold', 'appkitWeighted']:
    assert h['hook'][key]['postscript'] == h['font']['postscript']
    assert h['hook'][key]['renderSHA256'] != h['registered'][key]['renderSHA256'], 'Hook did not change rendered glyphs'
assert h['registered']['coreTextUI'] == h['hook']['coreTextUI']
assert h['registered'] == h['hookRestored']
print('PASS: positive controls, rendered hook change, Core Text boundary, exact rollback, source integrity')
