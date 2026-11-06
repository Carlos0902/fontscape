import json,unicodedata,sys
from pathlib import Path
from collections import Counter
from fontTools.ttLib import TTFont,TTCollection
src=TTFont('/System/Library/Fonts/SFNS.ttf'); donor=TTFont(sys.argv[1]); dc=donor.getBestCmap();cmap=src.getBestCmap();candidate=sys.argv[2] if len(sys.argv)>2 else 'artifacts/compat-v3/SFNS-compatible.json';r=json.load(open(candidate));derived=r.get('derivedForms',{});hybrids={x['glyph'] for x in r['changes'] if x.get('hybridNativeAccent')};changed={x['glyph'] for x in r['changes']}
rows=[]
for cp,n in sorted(cmap.items()):
 cat=unicodedata.category(chr(cp));nfd=unicodedata.normalize('NFD',chr(cp))
 state=derived[n] if n in derived else 'hybrid_native_accent' if n in hybrids else 'replaced' if n in changed else ('protected_symbol_or_control' if cat[0] not in 'LNPM' else 'donor_missing' if cp not in dc else 'shared_alias_protected')
 rows.append({'codepoint':f'U+{cp:04X}','character':chr(cp),'name':unicodedata.name(chr(cp),'UNNAMED'),'glyph':n,'category':cat,'status':state,'nfd':nfd,'nfdAllInDonor':nfd!=chr(cp) and all(ord(c) in dc for c in nfd),'nativeComposite':src['glyf'][n].isComposite()})
report={'counts':dict(Counter(x['status'] for x in rows)),'rows':rows,'unencodedGlyphs':len(set(src.getGlyphOrder())-set(cmap.values()))}
p=Path(sys.argv[3]) if len(sys.argv)>3 else Path('artifacts/compat-v4');(p/'coverage-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(report['counts']);print('NFD candidates',[(x['codepoint'],x['name'],x['nativeComposite']) for x in rows if x['status'] not in ['replaced','hybrid_native_accent'] and x['nfdAllInDonor']][:40])
