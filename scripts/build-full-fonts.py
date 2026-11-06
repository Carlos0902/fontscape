#!/usr/bin/env python3
"""Offline full mapped-glyph transplant for SFNS and all PingFangUI faces."""
import sys,json,gc,hashlib,copy
from pathlib import Path
from fontTools.ttLib import TTFont,TTCollection,newTable
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.cu2quPen import Cu2QuPen


root=Path(__file__).resolve().parent.parent
out=root/'artifacts/full-font'
donor=TTFont(sys.argv[1]); ds=donor.getGlyphSet(); dc=donor.getBestCmap()
paths={}
def donor_path(name):
 if name not in paths:
  pen=DecomposingRecordingPen(ds);ds[name].draw(pen);paths[name]=pen
 return paths[name]
def transplant(font, fallback=None):
 order=font.getGlyphOrder();cmap=font.getBestCmap(); mapping={}
 for cp,name in sorted(cmap.items()):
  if cp in dc and name not in mapping:mapping[name]=dc[cp]
 scale=font['head'].unitsPerEm/donor['head'].unitsPerEm
 if fallback is not None:
  glyf=newTable('glyf');glyf.glyphs={};glyf.glyphOrder=order
  for i,name in enumerate(order):
   pen=TTGlyphPen(None)
   if name in mapping:donor_path(mapping[name]).replay(TransformPen(pen,(scale,0,0,scale,0,0)))
   else:
    q=Cu2QuPen(pen,max_err=1.0); fs=font['head'].unitsPerEm/fallback[0]
    for cmd in fallback[1][i]:
     k=int(cmd[0]);v=[x*fs for x in cmd[1:]]
     if k==0:q.moveTo(tuple(v))
     elif k==1:q.lineTo(tuple(v))
     elif k==2:q.qCurveTo(tuple(v[:2]),tuple(v[2:]))
     elif k==3:q.curveTo(tuple(v[:2]),tuple(v[2:4]),tuple(v[4:]))
     elif k==4:q.closePath()
   glyf.glyphs[name]=pen.glyph()
  font['glyf']=glyf;font['loca']=newTable('loca')
  if 'hvgl' in font:del font['hvgl']
  maxp=newTable('maxp');maxp.tableVersion=0x10000;maxp.numGlyphs=len(order)
  for k in ['maxPoints','maxContours','maxCompositePoints','maxCompositeContours','maxTwilightPoints','maxStorage','maxFunctionDefs','maxInstructionDefs','maxStackElements','maxSizeOfInstructions','maxComponentElements','maxComponentDepth']:setattr(maxp,k,0)
  maxp.maxZones=1;font['maxp']=maxp
  g=newTable('gvar');g.version=1;g.reserved=0;g.variations={n:[] for n in order};font['gvar']=g
 else:
  for name,src in mapping.items():
   pen=TTGlyphPen(None);donor_path(src).replay(TransformPen(pen,(scale,0,0,scale,0,0)));font['glyf'][name]=pen.glyph()
   if 'gvar' in font:font['gvar'].variations[name]=[]
 if 'DSIG' in font:del font['DSIG']
 return {'postscript':font['name'].getDebugName(6),'mappedCodepoints':sum(cp in dc for cp in cmap),'totalCodepoints':len(cmap),'replacedGlyphs':len(mapping),'totalGlyphs':len(order),'unmappedGlyphsRetained':len(order)-len(mapping)}
report={'donorSHA256':hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest(),'limitations':'All replacement outlines use donor Medium; no genuine weight interpolation. Unmapped glyphs retain originals or exported SC Regular fallback.','faces':[]}
sf=Path('/System/Library/Fonts/SFNS.ttf'); f=TTFont(sf); report['faces'].append(transplant(f)); f.save(out/'SFNS-full.ttf');del f;gc.collect()
with (root/'artifacts/vm-setup/chinese-text-outlines.jsonl').open() as stream:
 header=json.loads(next(stream));fallback=(header['unitsPerEm'],[json.loads(line)['commands'] for line in stream])
source=Path('/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc')
assert hashlib.sha256(source.read_bytes()).hexdigest()==header['sourceSHA256']
collection=TTCollection(source,lazy=True); files=[]
for i,font in enumerate(collection.fonts):
 info=transplant(font,fallback);report['faces'].append(info)
 path=out/f'face-{i}.ttf';font.save(path);files.append(path)
 collection.fonts[i]=None;del font;gc.collect();print(i,info,flush=True)
result=TTCollection();result.fonts=[TTFont(p,lazy=True) for p in files];result.save(out/'PingFangUI-full.ttc')
for target,path in [(str(sf),out/'SFNS-full.ttf'),(str(source),out/'PingFangUI-full.ttc')]:
 report.setdefault('files',[]).append({'target':target,'sourceSHA256':hashlib.sha256(Path(target).read_bytes()).hexdigest(),'candidate':path.name,'candidateSHA256':hashlib.sha256(path.read_bytes()).hexdigest()})
(out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('COMPLETE',flush=True)
