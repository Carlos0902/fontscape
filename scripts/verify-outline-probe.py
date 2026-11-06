#!/usr/bin/env python3
"""Check a transplanted-glyph candidate against the exact original, independently."""
import json
from pathlib import Path
import sys
from fontTools.ttLib import TTFont

original, candidate = map(Path, sys.argv[1:3])
receipt = json.loads(candidate.with_suffix(candidate.suffix+'.json').read_text())
a,b = TTFont(original),TTFont(candidate)
changed = {i['targetGlyph'] for i in receipt['replaced']}
assert a.getGlyphOrder()==b.getGlyphOrder()
assert a['name'].compile(a)==b['name'].compile(b)
assert a.getBestCmap()==b.getBestCmap()
assert a['hmtx'].metrics==b['hmtx'].metrics
allowed={'head','maxp','loca','glyf','gvar','DSIG'}
for tag in a.keys():
    if tag!='GlyphOrder' and tag not in allowed:
        assert a.getTableData(tag)==b.getTableData(tag),f'Unexpected table change: {tag}'
for name in a.getGlyphOrder():
    if name in changed:
        assert a['glyf'][name].compile(a['glyf'])!=b['glyf'][name].compile(b['glyf'])
        if 'gvar' in b:assert not b['gvar'].variations[name]
    elif 'gvar' in a:
        assert a['gvar'].variations.get(name)==b['gvar'].variations.get(name),f'Unexpected deltas: {name}'
print('PASS: glyph IDs, names, cmap, metrics, layout and variation interfaces preserved; selected outline changed')
