"""Fit donor letters/numbers into the native metric grid; preserve native symbols."""
import sys,json,unicodedata,hashlib
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
src=Path('/System/Library/Fonts/SFNS.ttf');f=TTFont(src);d=TTFont(sys.argv[1]); ds=d.getGlyphSet();dc=d.getBestCmap(); cmap=f.getBestCmap();order=f.getGlyphOrder()[:];metrics=f['hmtx'].metrics.copy()
byname={}
for cp,name in cmap.items():byname.setdefault(name,[]).append(cp)
mapping={name:dc[cps[0]] for name,cps in byname.items() if all(unicodedata.category(chr(cp))[0] in 'LN' and cp in dc for cp in cps)}
# Composite symbols may reference text glyphs. Freeze their original decomposed
# outline first so changing a letter cannot mutate an untouched symbol indirectly.
original=f.getGlyphSet();frozen={}
for name in order:
 if name not in mapping and f['glyf'][name].isComposite():
  p=DecomposingRecordingPen(original);original[name].draw(p);q=TTGlyphPen(None);p.replay(q);frozen[name]=q.glyph()
for name,glyph in frozen.items():
 f['glyf'][name]=glyph
 if 'gvar' in f:f['gvar'].variations[name]=[]
changes=[];sy=f['head'].unitsPerEm/d['head'].unitsPerEm
for name,donor in mapping.items():
 adv,lsb=metrics[name];da,dl=d['hmtx'].metrics[donor];sx=adv/da if da else sy
 p=DecomposingRecordingPen(ds);ds[donor].draw(p);q=TTGlyphPen(None)
 p.replay(TransformPen(q,(sx,0,0,sy,lsb-dl*sx,0)));f['glyf'][name]=q.glyph();f['gvar'].variations[name]=[]
 changes.append({'glyph':name,'horizontalScale':sx,'verticalScale':sy})
# Static donor outlines must not retain unrelated native HVAR width changes.
h=f['HVAR'].table;v=h.VarStore.VarData[0];zero=len(v.Item);v.Item.append([0]*v.VarRegionCount);v.ItemCount=len(v.Item)
for name in mapping:h.AdvWidthMap.mapping[name]=zero
out=Path('artifacts/compat-v2/SFNS-compatible.ttf');f.save(out)
c=TTFont(out);assert c['hmtx'].metrics==metrics and c.getGlyphOrder()==order and c.getBestCmap()==cmap
r={'replacedLettersNumbers':len(mapping),'nativeSymbolPolicy':'All non-letter/non-number cmap aliases preserved; untouched composites frozen before transplant','frozenComposites':len(frozen),'metricsUnchanged':True,'replacedHVARNeutralized':True,'changes':changes,'sourceSHA256':hashlib.sha256(src.read_bytes()).hexdigest(),'candidateSHA256':hashlib.sha256(out.read_bytes()).hexdigest(),'weightLimitation':'Medium only; no genuine interpolated weights supplied'}
out.with_suffix('.json').write_text(json.dumps(r,indent=2));print({k:v for k,v in r.items() if k!='changes'})
