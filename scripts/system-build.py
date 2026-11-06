"""Unprivileged, offline replacement-package builder. Never writes system files."""
import gc, hashlib, json, os, pathlib, subprocess, sys, unicodedata
from fontTools.ttLib import TTFont, TTCollection, newTable
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.cu2quPen import Cu2QuPen

P = pathlib.Path
TARGETS = ['/System/Library/Fonts/SFNS.ttf', '/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc']
HASHES = ['2bfd40dc72e6759e248f82a52a40d551338979fffc9b5c070e685b4b7ad19e66', '13b201d63324db59de86956c11c46d1f0ad9ac0aeaa0b9d035c012a794062db7']
def sha(p): return hashlib.sha256(P(p).read_bytes()).hexdigest()
def require(test, reason):
    if not test: raise RuntimeError(reason)
def han(cp):
    return unicodedata.name(chr(cp), '').startswith(('CJK UNIFIED IDEOGRAPH', 'CJK COMPATIBILITY IDEOGRAPH', 'CJK RADICAL', 'KANGXI RADICAL')) or cp == 0x3007

def main():
    donor_path, output, spacing, probe = P(sys.argv[1]), P(sys.argv[2]), float(sys.argv[3]), P(sys.argv[4])
    require(os.geteuid() != 0, '字体构建必须以普通用户运行。')
    require(0 <= spacing <= .10, '汉字间距只允许 0–10%。')
    require(subprocess.check_output(['/usr/bin/sw_vers', '-buildVersion'], text=True).strip() == '25G83', '只支持 macOS 26.6.2 (25G83)。')
    require(all(sha(p) == h for p,h in zip(TARGETS,HASHES)), '系统字体不是支持的原始版本，请先回滚。')
    require(not output.exists(), '输出目录已存在。')
    donor = TTFont(donor_path)
    require('glyf' in donor, '系统替换目前需要包含 TrueType 轮廓的单字体 TTF，尚不支持 CFF/字体集合。')
    require(all(ord(c) in donor.getBestCmap() for c in '文Aa0'), '请选择同时包含中文、西文字母与数字的字体。')
    output.mkdir(parents=True, mode=0o700)
    print('正在生成西文字体，保留系统符号与字宽…', flush=True)
    subprocess.run([sys.executable, "-B", str(P(__file__).with_name('system-latin.py')), str(donor_path), TARGETS[0], str(output/'SFNS.ttf')], check=True)
    print('正在导出本机中文回退轮廓…', flush=True)
    outlines = output/'fallback.jsonl'
    subprocess.run([str(probe), 'export-chinese-outlines', str(outlines)], check=True, stdout=subprocess.DEVNULL)
    with outlines.open() as stream:
        header = json.loads(next(stream)); fallback = [json.loads(line)['commands'] for line in stream]
    require(header['sourceSHA256'] == HASHES[1], '回退轮廓来源不匹配。')
    source = TTCollection(TARGETS[1], lazy=True)
    require(len(source.fonts) == 32, '中文字体面数量不符合已验证配置。')
    ds, dc = donor.getGlyphSet(), donor.getBestCmap()
    cache, common, reports = {}, {}, []
    def recorded(name):
        if name not in cache:
            p = DecomposingRecordingPen(ds); ds[name].draw(p); cache[name] = p
        return cache[name]
    for index, font in enumerate(source.fonts):
        order, cmap, units = font.getGlyphOrder(), font.getBestCmap(), font['head'].unitsPerEm
        require(len(order) == len(fallback), '字体与轮廓 glyph 数量不一致。')
        mapping = {}
        for cp,name in sorted(cmap.items()):
            if cp in dc and name not in mapping: mapping[name] = dc[cp]
        key = (units, tuple(order), tuple(sorted(mapping.items())))
        if key not in common:
            glyf = newTable('glyf'); glyf.glyphs = {}; glyf.glyphOrder = order
            for i,name in enumerate(order):
                pen = TTGlyphPen(None)
                if name in mapping:
                    scale = units / donor['head'].unitsPerEm
                    recorded(mapping[name]).replay(TransformPen(pen, (scale,0,0,scale,0,0)))
                else:
                    q = Cu2QuPen(pen, max_err=1.0); scale = units/header['unitsPerEm']
                    for cmd in fallback[i]:
                        k, v = int(cmd[0]), [x*scale for x in cmd[1:]]
                        if k == 0: q.moveTo(tuple(v))
                        elif k == 1: q.lineTo(tuple(v))
                        elif k == 2: q.qCurveTo(tuple(v[:2]),tuple(v[2:]))
                        elif k == 3: q.curveTo(tuple(v[:2]),tuple(v[2:4]),tuple(v[4:]))
                        elif k == 4: q.closePath()
                glyf.glyphs[name] = pen.glyph()
            common[key] = glyf
        font['glyf'] = common[key]; font['loca'] = newTable('loca')
        if 'hvgl' in font: del font['hvgl']
        if 'DSIG' in font: del font['DSIG']
        maxp = newTable('maxp'); maxp.tableVersion = 0x10000; maxp.numGlyphs = len(order)
        for k in ['maxPoints','maxContours','maxCompositePoints','maxCompositeContours','maxTwilightPoints','maxStorage','maxFunctionDefs','maxInstructionDefs','maxStackElements','maxSizeOfInstructions','maxComponentElements','maxComponentDepth']: setattr(maxp,k,0)
        maxp.maxZones=1; font['maxp']=maxp
        gvar = newTable('gvar'); gvar.version=1; gvar.reserved=0; gvar.variations={name:[] for name in order}; font['gvar']=gvar
        groups={}
        for cp,name in cmap.items(): groups.setdefault(name,[]).append(cp)
        selected = {name for name,cps in groups.items() if all(han(cp) for cp in cps)}
        step = round(units*spacing)
        for name in selected:
            width,lsb=font['hmtx'].metrics[name]; require(width+step<=65535, '汉字字宽超出范围。');font['hmtx'].metrics[name]=(width+step,lsb)
        reports.append({'face':index, 'postscript':font['name'].getDebugName(6), 'replacedGlyphs':len(mapping), 'hanGlyphs':len(selected), 'addedUnits':step})
        print(f'中文字体面 {index+1}/32 已准备', flush=True)
    destination=output/'PingFangUI.ttc'
    print('正在保存中文字体集合…', flush=True);source.save(destination)
    check=TTCollection(destination,lazy=True)
    require(len(check.fonts)==32, '生成后的集合不完整。')
    for old,new in zip(source.fonts,check.fonts):
        require(old.getBestCmap()==new.getBestCmap() and old.getGlyphOrder()==new.getGlyphOrder(), '生成后的字形映射不一致。')
    check.close();source.close();outlines.unlink();gc.collect()
    files=[{'target':p,'candidate':P(p).name,'sourceSHA256':h,'candidateSHA256':sha(output/P(p).name)} for p,h in zip(TARGETS,HASHES)]
    report={'format':1,'osBuild':'25G83','architecture':'arm64','hanSpacing':spacing,'donorSHA256':sha(donor_path),'donorPostScript':donor['name'].getDebugName(6) or donor_path.name,'files':files,'faces':reports,
      'limitations':'Static donor outlines for all weights; unmapped CJK glyphs use exported SC Regular; not every app uses these system fonts.'}
    (output/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('替换包已生成；尚未修改系统字体。',flush=True)
if __name__=='__main__':
    try: main()
    except Exception as e: print(str(e),file=sys.stderr);sys.exit(1)
