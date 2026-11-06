#!/usr/bin/env python3
"""Add a small em-based horizontal advance to exclusively Han glyph aliases."""
import argparse,json,unicodedata,hashlib
from pathlib import Path
from fontTools.ttLib import TTCollection
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--em',type=float,default=.02);a=p.parse_args()
assert 0<a.em<=.10 and not a.output.exists()
assert not any(x in a.output.resolve().parents for x in [Path('/System'),Path('/Library/Fonts'),Path.home()/'Library/Fonts'])
def han(cp):
 n=unicodedata.name(chr(cp),'')
 return n.startswith(('CJK UNIFIED IDEOGRAPH','CJK COMPATIBILITY IDEOGRAPH','CJK RADICAL','KANGXI RADICAL')) or cp==0x3007
c=TTCollection(a.source,lazy=True);records=[];before=[]
for i,f in enumerate(c.fonts):
 groups={}
 for cp,name in f.getBestCmap().items():groups.setdefault(name,[]).append(cp)
 selected={name for name,cps in groups.items() if all(han(cp) for cp in cps)}
 step=round(f['head'].unitsPerEm*a.em)
 metrics=f['hmtx'].metrics.copy();before.append(metrics)
 for name in selected:
  advance,lsb=metrics[name];f['hmtx'].metrics[name]=(advance+step,lsb)
 records.append({'face':i,'postscript':f['name'].getDebugName(6),'unitsPerEm':f['head'].unitsPerEm,'addedUnits':step,'glyphsChanged':len(selected)})
a.output.parent.mkdir(parents=True,exist_ok=True);c.save(a.output)
b=TTCollection(a.output,lazy=True);native=TTCollection(a.source,lazy=True)
for i,(f,g) in enumerate(zip(native.fonts,b.fonts)):
 assert f.getGlyphOrder()==g.getGlyphOrder() and f.getBestCmap()==g.getBestCmap()
 assert hashlib.sha256(f.getTableData('glyf')).digest()==hashlib.sha256(g.getTableData('glyf')).digest()
 changed={n for n in before[i] if before[i][n]!=g['hmtx'].metrics[n]}
 for n in changed:assert g['hmtx'].metrics[n]==(before[i][n][0]+records[i]['addedUnits'],before[i][n][1])
 assert len(changed)==records[i]['glyphsChanged']
 for cp in map(ord,'ABCxyz0123，。！？'):
  if cp in f.getBestCmap():
   n=f.getBestCmap()[cp];assert before[i][n]==g['hmtx'].metrics[n]
report={'emAdded':a.em,'faces':records,'outlinesUnchanged':True,'latinDigitsPunctuationMetricsUnchanged':True,'sourceSHA256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'candidateSHA256':hashlib.sha256(a.output.read_bytes()).hexdigest()}
a.output.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('PASS',len(records),'faces, Han advance +',a.em,'em')
