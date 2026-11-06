#!/usr/bin/env python3
"""Create an offline glyph-transplant candidate; never install a system font."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen


def build(system, donor, output, text):
    system, donor, output = [Path(p).resolve() for p in [system, donor, output]]
    if output == system or output == donor or any(p in output.parents for p in [Path('/System'), Path('/Library/Fonts'), Path.home()/'Library/Fonts']):
        raise ValueError('Output must be a new, uninstalled candidate outside system/font directories')
    if output.exists():
        raise FileExistsError(output)
    base = TTFont(system)
    source = TTFont(donor, fontNumber=0)
    if 'glyf' not in base:
        raise ValueError('This first probe only supports glyf targets; proprietary PingFangUI hvgl is not supported')
    glyph_order = base.getGlyphOrder()[:]
    names = base['name'].compile(base)
    cmap, source_map = base.getBestCmap(), source.getBestCmap()
    glyphs = source.getGlyphSet()
    factor = base['head'].unitsPerEm / source['head'].unitsPerEm
    replaced = []
    # A single ASCII glyph is the initial boot experiment, preserving every glyph ID,
    # all other outlines, metrics, tables, names, and variable-axis interfaces.
    for char in dict.fromkeys(text):
        if ord(char) not in cmap or ord(char) not in source_map:
            raise ValueError(f'Missing glyph in target or donor: U+{ord(char):04X}')
        target_name, source_name = cmap[ord(char)], source_map[ord(char)]
        recording = DecomposingRecordingPen(glyphs)
        glyphs[source_name].draw(recording)
        pen = TTGlyphPen(None)
        recording.replay(TransformPen(pen, (factor, 0, 0, factor, 0, 0)))
        base['glyf'][target_name] = pen.glyph()
        if 'gvar' in base:
            # Original deltas refer to the original point topology. A static outline
            # at this glyph must not inherit incompatible deltas. Other glyphs vary.
            base['gvar'].variations[target_name] = []
        replaced.append({'character': char, 'codepoint': ord(char), 'glyphID': glyph_order.index(target_name),
                         'targetGlyph': target_name, 'donorGlyph': source_name})
    if 'DSIG' in base:
        del base['DSIG']
    output.parent.mkdir(parents=True, exist_ok=True)
    base.recalcTimestamp = False
    base.save(output)
    restored = TTFont(output)
    assert restored.getGlyphOrder() == glyph_order
    assert restored['name'].compile(restored) == names
    assert restored.getBestCmap() == cmap
    assert restored['hmtx'].metrics == base['hmtx'].metrics
    for item in replaced:
        assert not restored['glyf'][item['targetGlyph']].isComposite()
        if 'gvar' in restored:
            assert not restored['gvar'].variations[item['targetGlyph']]
    receipt = {'kind': 'offline-single-glyph-probe', 'systemFont': str(system), 'donor': str(donor),
               'sourceSHA256': sha256(system.read_bytes()).hexdigest(), 'donorSHA256': sha256(donor.read_bytes()).hexdigest(),
               'candidateSHA256': sha256(output.read_bytes()).hexdigest(), 'replaced': replaced,
               'glyphIDsPreserved': True, 'namesPreserved': True, 'cmapPreserved': True, 'metricsPreserved': True,
               'installed': False,
               'limitations': 'Replaced glyphs use a static donor outline for every axis setting; HVAR and original metrics remain. Not a complete system-font conversion.'}
    output.with_suffix(output.suffix+'.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--system-font', required=True)
    p.add_argument('--donor', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--text', default='a')
    a = p.parse_args()
    print(json.dumps(build(a.system_font, a.donor, a.output, a.text), ensure_ascii=False, indent=2))
