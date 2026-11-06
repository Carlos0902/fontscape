#!/usr/bin/env python3
"""Risk-ordered, journaled experiments. Never writes /Library or /System."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import uuid


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temp.replace(path)


def cli(binary, *args, checked=True):
    try:
        p = subprocess.run([str(binary), *map(str, args)], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        if checked:
            raise RuntimeError('探针超时：' + ' '.join(map(str, args))) from None
        return {'success': False, 'error': 'Probe timed out'}
    if p.returncode:
        if checked:
            raise RuntimeError(p.stderr.strip() or f'probe exit {p.returncode}')
        return {'success': False, 'error': p.stderr.strip(), 'exit': p.returncode}
    return json.loads(p.stdout)


def recover(binary, journal_path):
    journal = json.loads(journal_path.read_text())
    failures = []
    for item in reversed(journal['mutations']):
        if item.get('cleaned'):
            continue
        path = Path(item['path'])
        # Only our own generated font, never a system font or pre-existing file.
        allowed = (path.parent == Path.home() / 'Library/Fonts' and path.name.startswith('FontLab-')) or (path.parent == journal_path.parent and path.name.startswith('alias-'))
        if not allowed:
            failures.append(f'Refusing recovery outside owned paths: {path}')
            continue
        if path.exists() and digest(path) != item['sha256']:
            failures.append(f'Refusing changed font: {path}')
            continue
        if item['kind'] == 'session':
            response = cli(binary, 'unregister', 'session', path, checked=False)
            # May already be absent after logout. Check scope in CLI, not error text.
            if not response.get('success'):
                scope = cli(binary, 'scope', path)['scope']
                if scope != 0:
                    failures.append(response['error'])
                    continue
        elif path.exists():
            # Revoke directory auto-activation before deleting the owned font.
            scope = cli(binary, 'scope', path)['scope']
            if scope != 0:
                response = cli(binary, 'unregister', 'persistent', path, checked=False)
                if not response.get('success') and cli(binary, 'scope', path)['scope'] != 0:
                    failures.append(response['error'])
                    continue
            path.unlink()
        item['cleaned'] = True
        save(journal_path, journal)
    journal['cleanupErrors'] = failures
    journal['clean'] = not failures
    save(journal_path, journal)
    return failures


def alias_font(source, dest, family, postscript, style='Regular'):
    from fontTools.ttLib import TTFont
    f = TTFont(source)
    names = {1: family, 2: style, 3: 'FontLab experiment;' + postscript,
             4: family + ' ' + style, 6: postscript, 16: family, 17: style,
             18: family + ' ' + style, 21: family, 22: style}
    for n in list(f['name'].names):
        if n.nameID in names:
            f['name'].removeNames(nameID=n.nameID)
    for key, value in names.items():
        f['name'].setName(value, key, 3, 1, 0x409)
        # Macintosh Roman cannot represent arbitrary imported names; utf-16 Windows records suffice.
    f['OS/2'].usWeightClass = 400
    f['OS/2'].fsSelection &= ~((1 << 5) | 1)
    f['OS/2'].fsSelection |= 1 << 6
    f['head'].macStyle &= ~3
    f.save(dest)
    f.close()


def summarize(output, report):
    keys = ['appkitSystem', 'appkitBold', 'appkitWeighted', 'coreTextUI', 'chineseFallback', 'latinFallback', 'emojiFallback']
    def signature(s):
        return {k: s.get(k) for k in keys}
    process = json.loads((output / 'process.json').read_text())
    ps = process['font']['postscript']
    hook = json.loads((output / 'hook.json').read_text())
    variants = [json.loads(p.read_text()) for p in output.glob('alias-*.json')]
    control = next(d for d in variants if d['target']['family'].startswith('FontLab Control'))
    target = control['target']['postscript']
    control_ok = all(control[k]['byName'][target]['postscript'] == target and '/System/' not in control[k]['byName'][target]['url']
                     for k in ['sessionFreshProcess', 'userDirectoryFreshProcess'])
    changed = []
    for data in variants:
        for stage in ['sessionFreshProcess', 'userDirectoryFreshProcess']:
            if stage in data and signature(data[stage]) != signature(data['before']):
                changed.append({'target': data['target']['postscript'], 'stage': stage})
        if data['process'].get('registered') and signature(data['process']['registered']) != signature(data['process']['before']):
            changed.append({'target': data['target']['postscript'], 'stage': 'process'})
    aliases_restored = all(d['afterSessionRollback'] == d['before'] and d['afterFileRollback'] == d['before'] for d in variants)
    return {
        'processRegistrationVerified': process['registered']['byName'][ps]['postscript'] == ps,
        'positiveControlVerified': control_ok,
        'systemOverrideObserved': bool(changed), 'changedPaths': changed,
        'hookVerified': all(hook['hook'][k]['postscript'] == ps for k in ['appkitSystem', 'appkitBold', 'appkitWeighted']),
        'coreTextUnaffectedByHook': hook['hook']['coreTextUI'] == hook['registered']['coreTextUI'],
        'hookRollbackVerified': hook['hookRestored'] == hook['registered'],
        'aliasRollbackVerified': aliases_restored,
        'rollbackVerified': aliases_restored and report['baseline'] == report['final'] and not report['cleanupErrors'] and report['sourceUnchanged']}


def run(args):
    from fontTools.ttLib import TTFont
    binary = args.cli.resolve()
    source = args.font.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    journal_path = output / 'journal.json'
    journal = {'version': 1, 'mutations': [], 'clean': False}
    save(journal_path, journal)
    report = {'source': str(source), 'sha256': digest(source), 'stages': [],
              'scope': 'fresh probe processes; no Finder/Dock/Settings/Chrome restart or injection',
              'system': subprocess.check_output(['sw_vers'], text=True),
              'sip': subprocess.check_output(['csrutil', 'status'], text=True),
              'authenticatedRoot': subprocess.check_output(['csrutil', 'authenticated-root', 'status'], text=True)}
    font = TTFont(source)
    cmap = font.getBestCmap()
    report['metadata'] = {'names': {str(i): font['name'].getDebugName(i) for i in [0, 1, 2, 4, 6, 13, 14]},
                          'glyphs': font['maxp'].numGlyphs, 'codepoints': len(cmap),
                          'weight': font['OS/2'].usWeightClass, 'fsType': font['OS/2'].fsType,
                          'sampleMissing': [c for c in '你好，macOS 系统设置 文件 编辑 😀' if ord(c) not in cmap]}
    font.close()
    try:
        print('1/4 进程内注册与系统字体基线', flush=True)
        report['baseline'] = cli(binary, 'snapshot')
        process = cli(binary, 'process', source)
        save(output / 'process.json', process)
        report['stages'].append({'stage': 'process', 'evidence': 'process.json'})
        baseline = report['baseline']
        chinese = baseline['chineseFallback'][0]['font']
        targets = [
            ('control', 'FontLab Control ' + uuid.uuid4().hex[:8], None),
            ('system', baseline['appkitSystem']['family'], baseline['appkitSystem']['postscript']),
            ('chinese', chinese['family'], chinese['postscript']),
            ('public-pingfang', 'PingFang SC', 'PingFangSC-Regular'),
            ('legacy-sf', '.SF NS Text', '.SFNSText-Regular')]
        print('2/4 字体名称覆盖：进程 → 登录会话 → 用户字体目录（逐项回滚）', flush=True)
        for label, family, ps in targets:
            ps = ps or family.replace(' ', '') + '-Regular'
            path = output / f'alias-{label}.ttf'
            alias_font(source, path, family, ps)
            evidence = {'target': {'family': family, 'postscript': ps}, 'before': cli(binary, 'snapshot', ps)}
            evidence['process'] = cli(binary, 'process', path, checked=False)
            entry = {'kind': 'session', 'path': str(path), 'sha256': digest(path), 'cleaned': False}
            journal['mutations'].append(entry)
            journal['clean'] = False
            save(journal_path, journal)  # Write intent before mutation.
            evidence['sessionRegistration'] = cli(binary, 'register', 'session', path, checked=False)
            if evidence['sessionRegistration'].get('success'):
                time.sleep(1)
                evidence['sessionFreshProcess'] = cli(binary, 'snapshot', ps)
            errors = recover(binary, journal_path)
            if errors:
                raise RuntimeError('; '.join(errors))
            journal = json.loads(journal_path.read_text())
            evidence['afterSessionRollback'] = cli(binary, 'snapshot', ps)
            user_dir = Path.home() / 'Library/Fonts'
            user_dir.mkdir(parents=True, exist_ok=True)
            installed = user_dir / f'FontLab-{uuid.uuid4().hex}-{label}.ttf'
            journal['mutations'].append({'kind': 'file', 'path': str(installed), 'sha256': digest(path), 'cleaned': False})
            journal['clean'] = False
            save(journal_path, journal)
            # Exclusive creation: never overwrite an existing font, even on UUID collision.
            with installed.open('xb') as dst, path.open('rb') as src:
                shutil.copyfileobj(src, dst)
            discovery = []
            # fontd discovers ~/Library/Fonts asynchronously. Wait for catalog scope,
            # and require the independent control to actually resolve from our file.
            for attempt in range(15):
                time.sleep(1)
                snap = cli(binary, 'snapshot', ps)
                scope = cli(binary, 'scope', installed)['scope']
                matched = snap['byName'][ps]['postscript'] == ps and Path(snap['byName'][ps]['url']) == installed
                discovery.append({'attempt': attempt + 1, 'scope': scope, 'byNameMatchesInstalledFile': matched})
                evidence['userDirectoryFreshProcess'] = snap
                if (label == 'control' and matched) or (label != 'control' and (scope != 0 or attempt >= 4)):
                    break
            evidence['userDirectoryDiscovery'] = discovery
            errors = recover(binary, journal_path)
            if errors:
                raise RuntimeError('; '.join(errors))
            journal = json.loads(journal_path.read_text())
            for attempt in range(15):
                time.sleep(1)
                evidence['afterFileRollback'] = cli(binary, 'snapshot', ps)
                if label != 'control' or evidence['afterFileRollback']['byName'][ps]['postscript'] != ps:
                    break
            save(output / f'alias-{label}.json', evidence)
            report['stages'].append({'stage': 'alias-' + label, 'evidence': f'alias-{label}.json'})
            print(f'  {label} 已完成并回滚', flush=True)
        print('3/4 可控进程 AppKit Hook 与还原', flush=True)
        save(output / 'hook.json', cli(binary, 'hook', source))
        report['stages'].append({'stage': 'hook', 'evidence': 'hook.json'})
        print('4/4 深度模式只读预检', flush=True)
        report['deepMode'] = {'executed': False, 'reason': 'This runner performs read-only system-volume preflight only. Actual protection states are recorded in sip and authenticatedRoot; boot-volume mutation is a separate VM-only experiment.'}
    except BaseException as exc:
        report['error'] = str(exc)
        raise
    finally:
        errors = recover(binary, journal_path)
        report['cleanupErrors'] = errors
        report['sourceUnchanged'] = source.exists() and digest(source) == report['sha256']
        report['final'] = cli(binary, 'snapshot', checked=False)
        if 'error' not in report:
            try:
                report['conclusions'] = summarize(output, report)
            except Exception as exc:
                report['analysisError'] = str(exc)
        save(output / 'report.json', report)
        print(f'报告：{output / "report.json"}', flush=True)
        if errors:
            print('回滚未完成：' + '; '.join(errors), file=sys.stderr)
    if errors or not report.get('conclusions', {}).get('rollbackVerified'):
        raise RuntimeError('Recovery verification incomplete; inspect report.json')
    conclusions = report['conclusions']
    if not all(conclusions.get(k) for k in ['processRegistrationVerified', 'positiveControlVerified', 'hookVerified', 'hookRollbackVerified']):
        raise RuntimeError('结果不充分：至少一个对照或 Hook 核验未通过。请查看 conclusions 与 discovery 记录。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', type=Path, required=True)
    parser.add_argument('--font', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--recover', type=Path)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    if args.recover:
        failures = recover(args.cli.resolve(), args.recover.resolve())
        print(json.dumps({'clean': not failures, 'errors': failures}, ensure_ascii=False))
        sys.exit(bool(failures))
    if not args.font or not args.output:
        parser.error('--font and --output required')
    run(args)
