"""Pinned CPython + pure-Python fontTools. Build-time downloads only; no user network setup."""
import hashlib, pathlib, shutil, subprocess, sys, tarfile, urllib.request, zipfile
P=pathlib.Path
root=P(__file__).resolve().parent.parent
cache=root/'artifacts/runtime'; cache.mkdir(parents=True,exist_ok=True)
name='cpython-3.12.16+20261026-aarch64-apple-darwin-install_only_stripped.tar.gz'
url='https://github.com/astral-sh/python-build-standalone/releases/download/20261026/'+name.replace('+','%2B')
expected='353d5f1b4fd2715e7053f12f068435d5bbad16b91e057006b5d01e0925709a7e'
archive=cache/name
if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:
    subprocess.run(['curl','-fsSL','--retry','3','--retry-all-errors','-o',str(archive),url],check=True)
if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected: raise RuntimeError('CPython checksum mismatch')
python=cache/'aarch64/python'
if not (python/'bin/python3').exists():
    with tarfile.open(archive) as t:
        # All archive paths must stay in python/. Symlinks may only point inside the extraction tree.
        for m in t.getmembers():
            if not m.name.startswith('python/') or '..' in P(m.name).parts: raise RuntimeError('Unexpected runtime archive path')
            if (m.issym() or m.islnk()) and (P(m.linkname).is_absolute() or '..' in P(m.linkname).parts): raise RuntimeError('Unexpected runtime link')
        t.extractall(cache/'aarch64')
fonttools=cache/'fonttools'
wheel=cache/'fonttools-4.60.2-py3-none-any.whl'
wheel_url='https://files.pythonhosted.org/packages/79/6c/10280af05b44fafd1dff69422805061fa1af29270bc52dce031ac69540bf/fonttools-4.60.2-py3-none-any.whl'
wheel_sha='73cf92eeda67cf6ff10c8af56fc8f4f07c1647d989a979be9e388a49be26552a'
if not wheel.exists() or hashlib.sha256(wheel.read_bytes()).hexdigest()!=wheel_sha:
    urllib.request.urlretrieve(wheel_url,wheel)
if hashlib.sha256(wheel.read_bytes()).hexdigest()!=wheel_sha: raise RuntimeError('fontTools checksum mismatch')
if fonttools.exists(): shutil.rmtree(fonttools)
with zipfile.ZipFile(wheel) as z:
    for n in z.namelist():
        if pathlib.PurePosixPath(n).is_absolute() or '..' in pathlib.PurePosixPath(n).parts: raise RuntimeError('Unexpected wheel path')
    z.extractall(fonttools)
destination=P(sys.argv[1]);destination.mkdir(parents=True,exist_ok=True)
shutil.copytree(python,destination/'aarch64',symlinks=True)
shutil.copytree(root/'docs/runtime-licenses',destination/'LICENSES')
# Keep standard-library and third-party licenses. Pip is build-only, so remove its package and command wrappers.
shutil.rmtree(destination/'aarch64/lib/python3.12/site-packages',ignore_errors=True)
for f in (destination/'aarch64/bin').iterdir():
    if f.name.startswith(('pip','idle','2to3','pydoc')): f.unlink()
shutil.copytree(fonttools,destination/'fonttools',ignore=shutil.ignore_patterns('__pycache__','*.pyc','bin'))
# Re-sign nested runtime Mach-O code; Python is a child process with its own ordinary runtime policy.
for f in (destination/'aarch64').rglob('*'):
    if f.is_file() and not f.is_symlink():
        with f.open('rb') as stream: magic=stream.read(4)
        if magic in [b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe',b'\xca\xfe\xba\xbe']:
            subprocess.run(['codesign','--force','--sign','-',str(f)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print('Bundled pinned CPython 3.12.16 arm64 and fontTools 4.60.2; licenses retained')
