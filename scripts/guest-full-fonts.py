#!/usr/bin/env python3
import importlib.util,json,os,subprocess
from pathlib import Path
spec=importlib.util.spec_from_file_location('guard',Path(__file__).with_name('guest-system-font.py'));g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
g.guest_only()
assert os.geteuid()==0
assert 'disabled' in g.run('csrutil','status').lower() and 'disabled' in g.run('csrutil','authenticated-root','status').lower()
lab=g.LAB; manifest=json.loads((lab/'full/manifest.json').read_text());root,volume=g.system_volume()
details=g.plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/dev/'+volume['DeviceIdentifier']]))
active=[line.split(' on ',1)[1].rsplit(' (',1)[0] for line in g.run('/sbin/mount').splitlines() if line.startswith('/dev/'+volume['DeviceIdentifier']+' on ')]
mount=Path(active[0] if active else '/private/tmp/fontlab-full-mount')
if not active:
 mount.mkdir(exist_ok=True);g.run('/sbin/mount_apfs','-o','nobrowse','/dev/'+volume['DeviceIdentifier'],mount)
assert g.plistlib.loads(subprocess.check_output(['diskutil','info','-plist',str(mount)]))['DeviceIdentifier']==volume['DeviceIdentifier']
g.run('/sbin/mount','-uw',mount)
back=lab/'backups/full';back.mkdir(parents=True,exist_ok=True)
for f in manifest['files']:
 source=lab/'full'/f['candidate'];target=mount/f['target'].lstrip('/');backup=back/Path(f['target']).name
 assert g.sha(source)==f['candidateSHA256'] and g.sha(target)==f['sourceSHA256']
 if not backup.exists():backup.write_bytes(target.read_bytes())
 assert g.sha(backup)==f['sourceSHA256']
written=[]
try:
 for f in manifest['files']:
  target=mount/f['target'].lstrip('/');source=lab/'full'/f['candidate'];target.write_bytes(source.read_bytes());os.chown(target,0,0);os.chmod(target,0o644);written.append(target)
  assert g.sha(target)==f['candidateSHA256']
 g.run('/bin/sync')
 output=g.run('/usr/sbin/bless','--mount',mount,'--bootefi','--create-snapshot','--verbose')
 g.save(lab/'results/full-install.json',{'files':manifest['files'],'blessOutput':output,'createdSnapshot':True})
 print('Full-font snapshot committed')
except BaseException:
 for target in written:target.write_bytes((back/target.name).read_bytes())
 raise
