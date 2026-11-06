#!/usr/bin/env python3
"""Offline research: replace one PingFang UI glyph using a Core Text outline export.

The first face becomes a static outline instance with retained axis/name interfaces;
other weight outlines in that face are NOT preserved. Never installs a font.
"""
import argparse
import hashlib
import json
from pathlib import Path
from fontTools.ttLib import TTFont, TTCollection, newTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--collection',required=True,type=Path)
    p.add_argument('--outlines',required=True,type=Path)
    p.add_argument('--donor',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--character',default='文')
    args=p.parse_args()
    output=args.output.resolve()
    if output.exists() or any(parent in output.parents for parent in [Path('/System'),Path('/Library/Fonts'),Path.home()/'Library/Fonts']):
        raise ValueError('Output must be a new offline candidate outside installed-font paths')
    collection=TTCollection(args.collection,lazy=True)
    base=collection.fonts[0]
    order=base.getGlyphOrder()[:]
    cmap=base.getBestCmap()
    names=base['name'].compile(base)
    metrics=base['hmtx'].metrics.copy()
    if 'hvgl' not in base:raise ValueError('Expected the proprietary hvgl first face')
    with args.outlines.open() as source:
        header=json.loads(next(source))
        assert header['sourceSHA256']==hashlib.sha256(args.collection.read_bytes()).hexdigest()
        assert header['glyphCount']==len(order) and header['unitsPerEm']==base['head'].unitsPerEm
        for cp,gid in header['validationGlyphs'].items():
            assert order.index(cmap[int(cp)])==gid,'Core Text glyph IDs differ from collection cmap'
        glyf=newTable('glyf');glyf.glyphs={};glyf.glyphOrder=order
        for expected,line in enumerate(source):
            item=json.loads(line)
            assert item['id']==expected and expected<len(order)
            tt=TTGlyphPen(None)
            pen=Cu2QuPen(tt,max_err=1.0)
            for cmd in item['commands']:
                kind=int(cmd[0]);v=cmd[1:]
                if kind==0:pen.moveTo((v[0],v[1]))
                elif kind==1:pen.lineTo((v[0],v[1]))
                elif kind==2:pen.qCurveTo((v[0],v[1]),(v[2],v[3]))
                elif kind==3:pen.curveTo((v[0],v[1]),(v[2],v[3]),(v[4],v[5]))
                elif kind==4:pen.closePath()
                else:raise ValueError('Unknown CGPath command')
            glyf.glyphs[order[expected]]=tt.glyph()
        assert len(glyf.glyphs)==len(order)
    donor=TTFont(args.donor,fontNumber=0)
    if len(args.character)!=1:raise ValueError('Select exactly one character')
    cp=ord(args.character)
    target=cmap[cp]
    donor_name=donor.getBestCmap()[cp]
    donor_set=donor.getGlyphSet()
    recorded=DecomposingRecordingPen(donor_set)
    donor_set[donor_name].draw(recorded)
    tt=TTGlyphPen(None)
    factor=base['head'].unitsPerEm/donor['head'].unitsPerEm
    recorded.replay(TransformPen(tt,(factor,0,0,factor,0,0)))
    glyf.glyphs[target]=tt.glyph()
    del base['hvgl']
    base['glyf']=glyf
    base['loca']=newTable('loca')
    maxp=newTable('maxp');maxp.tableVersion=0x10000;maxp.numGlyphs=len(order)
    for key in ['maxPoints','maxContours','maxCompositePoints','maxCompositeContours','maxTwilightPoints','maxStorage','maxFunctionDefs','maxInstructionDefs','maxStackElements','maxSizeOfInstructions','maxComponentElements','maxComponentDepth']:
        setattr(maxp,key,0)
    maxp.maxZones=1;base['maxp']=maxp
    gvar=newTable('gvar');gvar.version=1;gvar.reserved=0;gvar.variations={name:[] for name in order};base['gvar']=gvar
    if 'DSIG' in base:del base['DSIG']
    output.parent.mkdir(parents=True,exist_ok=True)
    collection.save(output)
    check=TTCollection(output,lazy=True)
    assert len(check.fonts)==len(collection.fonts)
    assert check.fonts[0].getGlyphOrder()==order
    assert check.fonts[0]['name'].compile(check.fonts[0])==names
    assert check.fonts[0].getBestCmap()==cmap
    assert check.fonts[0]['hmtx'].metrics==metrics
    assert 'glyf' in check.fonts[0] and 'hvgl' not in check.fonts[0]
    for a,b in zip(collection.fonts[1:],check.fonts[1:]):
        assert a.getTableData('hvgl')==b.getTableData('hvgl')
        assert a.getGlyphOrder()==b.getGlyphOrder()
    receipt={'kind':'experimental-cjk-static-instance','sourceSHA256':header['sourceSHA256'],
             'candidateSHA256':hashlib.sha256(output.read_bytes()).hexdigest(),
             'character':args.character,'glyphID':order.index(target),'faces':len(collection.fonts),
             'glyphIDsPreserved':True,'namesPreserved':True,'metricsPreserved':True,'otherFacesHVGLUnchanged':True,
             'exportedInstance':header['postscript'],'installed':False,
             'limitation':'Face 0 outlines are frozen to the exported UI instance; other axis/weight outlines are not retained. This is not a production drop-in.'}
    output.with_suffix('.ttc.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
