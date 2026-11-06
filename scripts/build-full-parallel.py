import sys,json,gc,subprocess,concurrent.futures,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent.parent
code=(root/'scripts/build-full-fonts.py').read_text().split("report={'donorSHA256'")[0]
exec(code)
source=Path('/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc')
if len(sys.argv)>2:
 i=int(sys.argv[2]);font=TTFont(source,fontNumber=i)
 path=out/f'face-{i}.ttf'
 # Rebuild atomically even when an interrupted predecessor left a file.
 with (root/'artifacts/vm-setup/chinese-text-outlines.jsonl').open() as stream:
  header=json.loads(next(stream));fallback=(header['unitsPerEm'],[json.loads(line)['commands'] for line in stream])
 info=transplant(font,fallback);tmp=path.with_suffix('.partial');font.save(tmp);tmp.replace(path)
 (out/f'face-{i}.json').write_text(json.dumps(info));print(i,info,flush=True)
else:
 def worker(i):
  subprocess.run([sys.executable,__file__,sys.argv[1],str(i)],check=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(worker,range(32)))
 collection=TTCollection();collection.fonts=[TTFont(out/f'face-{i}.ttf',lazy=True) for i in range(32)];collection.save(out/'PingFangUI-full.ttc')
 sf=Path('/System/Library/Fonts/SFNS.ttf'); info=transplant(TTFont(sf));faces=[info]+[json.loads((out/f'face-{i}.json').read_text()) for i in range(32)]
 report={'kind':'full-mapped-fonts','faces':faces,'limitations':'Medium outlines for all weights; unmapped glyphs retained, CJK fallback uses SC Regular exported outlines.','files':[]}
 for target,path in [(sf,out/'SFNS-full.ttf'),(source,out/'PingFangUI-full.ttc')]:
  report['files'].append({'target':str(target),'sourceSHA256':hashlib.sha256(target.read_bytes()).hexdigest(),'candidate':path.name,'candidateSHA256':hashlib.sha256(path.read_bytes()).hexdigest()})
 (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('COMPLETE',flush=True)
