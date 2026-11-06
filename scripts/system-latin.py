"""Fit donor letters/numbers into the native metric grid; preserve native symbols."""
import sys,json,unicodedata,hashlib
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib.tables.otBase import ValueRecord
from fontTools.ttLib.tables import otTables
from fontTools.otlLib.builder import buildLookup,buildPairPosGlyphsSubtable
import copy
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
src=Path(sys.argv[2]);f=TTFont(src);d=TTFont(sys.argv[1]); ds=d.getGlyphSet();dc=d.getBestCmap(); cmap=f.getBestCmap();order=f.getGlyphOrder()[:];metrics=f['hmtx'].metrics.copy()
byname={}
for cp,name in cmap.items():byname.setdefault(name,[]).append(cp)
mapping={name:dc[cps[0]] for name,cps in byname.items() if all(unicodedata.category(chr(cp))[0] in 'LNPM' and cp in dc for cp in cps)}
# Explicitly limited derived forms: canonical single-scalar aliases and
# superscript/subscript glyphs fitted to the native reference ink box.
derived={}
for name,cps in byname.items():
 if name in mapping or not all(unicodedata.category(chr(cp))[0] in 'LNPM' for cp in cps):continue
 for cp in cps:
  text=unicodedata.normalize('NFD',chr(cp));kind='canonical_alias'
  if len(text)!=1 or ord(text) not in dc:
   if not unicodedata.name(chr(cp),'').startswith(('SUPERSCRIPT','SUBSCRIPT')):continue
   text=unicodedata.normalize('NFKD',chr(cp));kind='derived_script_position'
  if len(text)==1 and ord(text) in dc:
   mapping[name]=dc[ord(text)];derived[name]=kind;break
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
nativeBoxes={n:(f['glyf'][n].xMin,f['glyf'][n].yMin,f['glyf'][n].xMax,f['glyf'][n].yMax) for n in set(mapping)|hybrids if hasattr(f['glyf'][n],'xMin')}
hybridComponents={n:copy.deepcopy(f['glyf'][n].components) for n in hybrids}
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
 dy=0;ys=sy
 if derived.get(name)=='derived_script_position' and bounds.bounds and name in nativeBoxes:
  xmin,ymin,xmax,ymax=bounds.bounds;nl,nb,nr,nt=nativeBoxes[name]
  if xmax>xmin and ymax>ymin:sx=(nr-nl)/(xmax-xmin);ys=(nt-nb)/(ymax-ymin);tx=nl-xmin*sx;dy=nb-ymin*ys
 p.replay(TransformPen(q,(sx,0,0,ys,tx,dy)));f['glyf'][name]=q.glyph();f['gvar'].variations[name]=[]
 changes.append({'glyph':name,'horizontalScale':sx,'verticalScale':sy})
# Decompose after bases are fitted; preserve original native accent locations.
hybridFits=[]
for name in hybrids:
 q=TTGlyphPen(None);glyphset=f.getGlyphSet();nl,nb,nr,nt=nativeBoxes[name]
 for component in hybridComponents[name]:
  cname,transform=component.getComponentInfo();raw=DecomposingRecordingPen(glyphset);glyphset[cname].draw(raw)
  positioned=DecomposingRecordingPen(glyphset);raw.replay(TransformPen(positioned,transform))
  bounds=BoundsPen(None);positioned.replay(bounds)
  if cname in mapping and bounds.bounds:
   left,bottom,right,top=bounds.bounds
   if left<nl or right>nr:
    width=right-left;scale=min(1,(nr-nl)/width) if width else 1
    offset=max(nl,min(left,nr-width*scale))-left*scale
    positioned.replay(TransformPen(q,(scale,0,0,1,offset,0)));hybridFits.append(name);continue
  positioned.replay(q)
 f['glyf'][name]=q.glyph();f['gvar'].variations[name]=[]
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
# Import only static horizontal donor kerning for safely mapped ASCII pairs.
def pair_adjust(lookup,left,right):
 for wrapper in lookup.SubTable:
  sub=wrapper.ExtSubTable if lookup.LookupType==9 else wrapper
  typ=wrapper.ExtensionLookupType if lookup.LookupType==9 else lookup.LookupType
  if typ!=2 or left not in sub.Coverage.glyphs:continue
  if sub.Format==1:
   records=sub.PairSet[sub.Coverage.glyphs.index(left)].PairValueRecord
   for record in records:
    if record.SecondGlyph==right:return getattr(record.Value1,'XAdvance',0) if record.Value1 else 0
  elif sub.Format==2:
   record=sub.Class1Record[sub.ClassDef1.classDefs.get(left,0)].Class2Record[sub.ClassDef2.classDefs.get(right,0)]
   return getattr(record.Value1,'XAdvance',0) if record.Value1 else 0
 return None
indices=sorted({i for record in d['GPOS'].table.FeatureList.FeatureRecord if record.FeatureTag=='kern' for i in record.Feature.LookupListIndex}) if 'GPOS' in d else []
ascii_names={cp:cmap[cp] for cp in range(32,127) if cp in cmap and cp in dc and cmap[cp] in mapping}
pairs={};clamped=0
for cp,left in ascii_names.items():
 for rp,right in ascii_names.items():
  adjust=sum(pair_adjust(d['GPOS'].table.LookupList.Lookup[i],dc[cp],dc[rp]) or 0 for i in indices)
  if not adjust:continue
  scale=next(x['horizontalScale'] for x in changes if x['glyph']==left)
  amount=round(adjust*scale)
  f['glyf'][left].recalcBounds(f['glyf']);f['glyf'][right].recalcBounds(f['glyf'])
  if hasattr(f['glyf'][left],'xMax') and hasattr(f['glyf'][right],'xMin'):
   gap=metrics[left][0]+f['glyf'][right].xMin-f['glyf'][left].xMax
   safe=max(round(f['head'].unitsPerEm*.015)-gap,min(amount,round(f['head'].unitsPerEm*.08)))
   if safe!=amount:clamped+=1
   amount=safe
  if amount:
   record=ValueRecord();record.XAdvance=amount;pairs[(left,right)]=(record,None)
if pairs and '--experimental-kern' in sys.argv:
 sub=buildPairPosGlyphsSubtable(pairs,f.getReverseGlyphMap());lookup=buildLookup([sub],table='GPOS')
 index=len(f['GPOS'].table.LookupList.Lookup);f['GPOS'].table.LookupList.Lookup.append(lookup);f['GPOS'].table.LookupList.LookupCount=index+1
 for record in f['GPOS'].table.FeatureList.FeatureRecord:
  if record.FeatureTag=='kern':record.Feature.LookupListIndex.append(index);record.Feature.LookupCount=len(record.Feature.LookupListIndex)
# Static donor outlines must not retain unrelated native HVAR width changes.
h=f['HVAR'].table;v=h.VarStore.VarData[0];zero=len(v.Item);v.Item.append([0]*v.VarRegionCount);v.ItemCount=len(v.Item)
for name in replaced:h.AdvWidthMap.mapping[name]=zero
out=Path(sys.argv[3]);f.save(out)
c=TTFont(out);assert c['hmtx'].metrics==metrics and c.getGlyphOrder()==order and c.getBestCmap()==cmap
r={'replacedGlyphs':len(replaced),'derivedForms':derived,'hybridBaseEnvelopeFits':sorted(set(hybridFits)),'directDonorGlyphs':len(mapping)-len(derived),'derivedDonorGlyphs':len(derived),'importedAsciiKernPairs':len(pairs) if '--experimental-kern' in sys.argv else 0,'evaluatedAsciiKernPairs':len(pairs),'clampedAsciiKernPairs':clamped,'hybridAccentGlyphs':len(hybrids),'classPairSubtablesIsolated':class_subtables,'matchedLigatureOutputs':ligature_count,'coveragePolicy':'Letters, numbers, punctuation, combining marks; all Symbol/PUA aliases excluded','nativeSymbolPolicy':'Symbol and PUA aliases preserved; untouched composites frozen before transplant','frozenComposites':len(frozen),'metricsUnchanged':True,'replacedHVARNeutralized':True,'changes':changes,'sourceSHA256':hashlib.sha256(src.read_bytes()).hexdigest(),'candidateSHA256':hashlib.sha256(out.read_bytes()).hexdigest(),'nativePairRecordsNeutralized':removed,'remainingKerningLimitation':'Only static ASCII donor kerning imported; other scripts/contextual adjustments remain incomplete','weightLimitation':'Medium only; no genuine interpolated weights supplied'}
out.with_suffix('.json').write_text(json.dumps(r,indent=2));print({k:v for k,v in r.items() if k!='changes'})
