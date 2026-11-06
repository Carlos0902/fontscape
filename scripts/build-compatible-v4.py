"""Fit donor letters/numbers into the native metric grid; preserve native symbols."""
import sys,json,unicodedata,hashlib
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib.tables.otBase import ValueRecord
from fontTools.ttLib.tables import otTables
import copy
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
src=Path('/System/Library/Fonts/SFNS.ttf');f=TTFont(src);d=TTFont(sys.argv[1]); ds=d.getGlyphSet();dc=d.getBestCmap(); cmap=f.getBestCmap();order=f.getGlyphOrder()[:];metrics=f['hmtx'].metrics.copy()
byname={}
for cp,name in cmap.items():byname.setdefault(name,[]).append(cp)
mapping={name:dc[cps[0]] for name,cps in byname.items() if all(unicodedata.category(chr(cp))[0] in 'LNPM' and cp in dc for cp in cps)}
# Expand encoded coverage to matching donor ligature outputs (fi/ffi etc.).
def ligatures(font):
 result={}
 if 'GSUB' not in font:return result
 for lookup in font['GSUB'].table.LookupList.Lookup:
  for wrapper in lookup.SubTable:
   sub=wrapper.ExtSubTable if lookup.LookupType==7 else wrapper
   typ=wrapper.ExtensionLookupType if lookup.LookupType==7 else lookup.LookupType
   if typ==4:
    for first,records in sub.ligatures.items():
     for item in records:result[(first,*item.Component)]=item.LigGlyph
 return result
donor_ligatures=ligatures(d);ligature_count=0
for sequence,target in ligatures(f).items():
 if all(n in mapping for n in sequence) and target not in byname:
  equivalent=donor_ligatures.get(tuple(mapping[n] for n in sequence))
  if equivalent and target not in mapping:mapping[target]=equivalent;ligature_count+=1
# Preserve native accent placement while adopting fitted donor base components.
hybrids=set()
for name,cps in byname.items():
 if name in mapping or not f['glyf'][name].isComposite():continue
 if not all(unicodedata.category(chr(cp))[0] in 'LNPM' for cp in cps):continue
 if not any(unicodedata.normalize('NFD',chr(cp))!=chr(cp) and all(ord(c) in dc for c in unicodedata.normalize('NFD',chr(cp))) for cp in cps):continue
 components=[c.glyphName for c in f['glyf'][name].components]
 if any(n in mapping for n in components):hybrids.add(name)
# Composite symbols may reference text glyphs. Freeze their original decomposed
# outline first so changing a letter cannot mutate an untouched symbol indirectly.
original=f.getGlyphSet();frozen={}
for name in order:
 if name not in mapping and name not in hybrids and f['glyf'][name].isComposite():
  p=DecomposingRecordingPen(original);original[name].draw(p);q=TTGlyphPen(None);p.replay(q);frozen[name]=q.glyph()
for name,glyph in frozen.items():
 f['glyf'][name]=glyph
 if 'gvar' in f:f['gvar'].variations[name]=[]
changes=[];sy=f['head'].unitsPerEm/d['head'].unitsPerEm
for name,donor in mapping.items():
 adv,lsb=metrics[name];da,dl=d['hmtx'].metrics[donor];sx=adv/da if da else sy
 p=DecomposingRecordingPen(ds);ds[donor].draw(p);q=TTGlyphPen(None)
 bounds=BoundsPen(ds);ds[donor].draw(bounds)
 tx=lsb-dl*sx
 if bounds.bounds and adv>0:
  xmin,ymin,xmax,ymax=bounds.bounds
  if xmax>xmin:
   left=max(0,min(lsb,adv*0.08));right=max(1,adv*0.03)
   sx=min(sx,max(1,adv-left-right)/(xmax-xmin))
   tx=max(left, min(tx+xmin*sx,adv-right-(xmax-xmin)*sx))-xmin*sx
 p.replay(TransformPen(q,(sx,0,0,sy,tx,0)));f['glyf'][name]=q.glyph();f['gvar'].variations[name]=[]
 changes.append({'glyph':name,'horizontalScale':sx,'verticalScale':sy})
# Decompose after bases are fitted; preserve original native accent locations.
for name in hybrids:
 pen=DecomposingRecordingPen(f.getGlyphSet());f.getGlyphSet()[name].draw(pen);q=TTGlyphPen(None);pen.replay(q);f['glyf'][name]=q.glyph();f['gvar'].variations[name]=[]
 changes.append({'glyph':name,'hybridNativeAccent':True})
replaced=set(mapping)|hybrids
removed=0;class_subtables=0
if 'GPOS' in f:
 for lookup in f['GPOS'].table.LookupList.Lookup:
  for wrapper in lookup.SubTable:
   sub=wrapper.ExtSubTable if lookup.LookupType==9 else wrapper
   typ=wrapper.ExtensionLookupType if lookup.LookupType==9 else lookup.LookupType
   if typ!=2:continue
   if sub.Format==1:
    for first,pairs in zip(sub.Coverage.glyphs,sub.PairSet):
     for record in pairs.PairValueRecord:
      if first in replaced or record.SecondGlyph in replaced:
       for value in [record.Value1,record.Value2]:
        if value is not None:
         for key in ['XAdvance','XPlacement','YAdvance','YPlacement']:
          if hasattr(value,key):setattr(value,key,0)
         for key in list(vars(value)):
          if key.endswith('Device'):setattr(value,key,None)
       removed+=1
   elif sub.Format==2:
    # Give transplanted glyphs dedicated zero-adjustment classes. Existing
    # native/native class cells remain byte-for-byte equivalent.
    c1=sub.Class1Count;c2=sub.Class2Count
    def blank():
     r=otTables.Class2Record();r.Value1=ValueRecord(sub.ValueFormat1) if sub.ValueFormat1 else None;r.Value2=ValueRecord(sub.ValueFormat2) if sub.ValueFormat2 else None;return r
    for row in sub.Class1Record:row.Class2Record.append(blank())
    row=otTables.Class1Record();row.Class2Record=[blank() for _ in range(c2+1)];sub.Class1Record.append(row)
    for name in sub.Coverage.glyphs:
     if name in replaced:sub.ClassDef1.classDefs[name]=c1
    for name in replaced:sub.ClassDef2.classDefs[name]=c2
    sub.Class1Count=c1+1;sub.Class2Count=c2+1;class_subtables+=1
# Static donor outlines must not retain unrelated native HVAR width changes.
h=f['HVAR'].table;v=h.VarStore.VarData[0];zero=len(v.Item);v.Item.append([0]*v.VarRegionCount);v.ItemCount=len(v.Item)
for name in replaced:h.AdvWidthMap.mapping[name]=zero
out=Path('artifacts/compat-v4/SFNS-compatible.ttf');f.save(out)
c=TTFont(out);assert c['hmtx'].metrics==metrics and c.getGlyphOrder()==order and c.getBestCmap()==cmap
r={'replacedGlyphs':len(replaced),'directDonorGlyphs':len(mapping),'hybridAccentGlyphs':len(hybrids),'classPairSubtablesIsolated':class_subtables,'matchedLigatureOutputs':ligature_count,'coveragePolicy':'Letters, numbers, punctuation, combining marks; all Symbol/PUA aliases excluded','nativeSymbolPolicy':'Symbol and PUA aliases preserved; untouched composites frozen before transplant','frozenComposites':len(frozen),'metricsUnchanged':True,'replacedHVARNeutralized':True,'changes':changes,'sourceSHA256':hashlib.sha256(src.read_bytes()).hexdigest(),'candidateSHA256':hashlib.sha256(out.read_bytes()).hexdigest(),'nativePairRecordsNeutralized':removed,'remainingKerningLimitation':'Native class/explicit adjustments isolated for replaced glyphs; donor kerning not imported','weightLimitation':'Medium only; no genuine interpolated weights supplied'}
out.with_suffix('.json').write_text(json.dumps(r,indent=2));print({k:v for k,v in r.items() if k!='changes'})
