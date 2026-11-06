#!/usr/bin/env python3
"""Create an orphan session/file transaction, recover twice, and reject a foreign path."""
from pathlib import Path
import importlib.util
import json
import shutil
import sys
import uuid

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('experiment', root / 'scripts/experiment.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
binary = Path(sys.argv[1]).resolve()
source = Path(sys.argv[2]).resolve()
directory = root / 'artifacts' / ('recovery-' + uuid.uuid4().hex[:8])
directory.mkdir(parents=True)
alias = directory / 'alias-orphan.ttf'
name = 'FontLabRecovery' + uuid.uuid4().hex[:8] + '-Regular'
engine.alias_font(source, alias, name, name)
installed = Path.home() / 'Library/Fonts' / ('FontLab-' + uuid.uuid4().hex + '-recovery.ttf')
journal = directory / 'journal.json'
state = {'mutations': [
    {'kind': 'session', 'path': str(alias), 'sha256': engine.digest(alias), 'cleaned': False},
    {'kind': 'file', 'path': str(installed), 'sha256': engine.digest(alias), 'cleaned': False}], 'clean': False}
engine.save(journal, state)
try:
    engine.cli(binary, 'register', 'session', alias)
    with installed.open('xb') as dst, alias.open('rb') as src:
        shutil.copyfileobj(src, dst)
    assert engine.cli(binary, 'snapshot', name)['byName'][name]['postscript'] == name
    assert not engine.recover(binary, journal)
    assert not installed.exists()
    assert engine.cli(binary, 'scope', alias)['scope'] == 0
    assert not engine.recover(binary, journal), 'Recovery must be idempotent'
    assert engine.cli(binary, 'snapshot', name)['byName'][name]['postscript'] != name
finally:
    failures = engine.recover(binary, journal)
    if failures:
        raise RuntimeError(failures)
foreign = directory / 'foreign.json'
engine.save(foreign, {'mutations': [{'kind': 'file', 'path': '/System/Library/Fonts/SFNS.ttf', 'sha256': '', 'cleaned': False}], 'clean': False})
assert engine.recover(binary, foreign), 'Foreign path must be rejected'
print('PASS: orphan session and file recovered; repeated recovery safe; system path refused')
