#!/usr/bin/env python3
"""VM-only SFNS single-glyph experiment. Default is a read-only installation plan."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import uuid

LAB = Path('/Users/admin/FontLab')
FONT = Path('/System/Library/Fonts/SFNS.ttf')
MOUNT = Path('/private/tmp/fontlab-system-mount')


def run(*args):
    try:
        return subprocess.check_output(list(map(str,args)),text=True,stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f'{args[0]} exited {error.returncode}: {error.output.strip()}') from None


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2))
    temporary.replace(path)


def guest_only():
    model=run('/usr/sbin/sysctl','-n','hw.model').strip()
    if not model.startswith('VirtualMac'):
        raise RuntimeError('REFUSED: system-font operations are restricted to an Apple virtual Mac')
    marker=json.loads((LAB/'.fontlab-disposable.json').read_text())
    if marker.get('purpose')!='FontLab disposable guest':
        raise RuntimeError('REFUSED: disposable FontLab marker missing')
    return model


def system_volume():
    root=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/']))
    layout=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','apfs','list','-plist']))
    identifier=root['DeviceIdentifier']
    matches=[]
    for container in layout['Containers']:
        for volume in container['Volumes']:
            dev=volume['DeviceIdentifier']
            if 'System' in volume.get('Roles',[]) and (identifier==dev or identifier.startswith(dev+'s')):
                matches.append(volume)
    if len(matches)!=1:raise RuntimeError('Cannot uniquely identify the booted System volume')
    return root,matches[0]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply',action='store_true')
    p.add_argument('--restore',action='store_true')
    args=p.parse_args()
    model=guest_only() # Must run before any attempt to mount, write or elevate.
    root,volume=system_volume()
    candidate=LAB/'results/SFNS-outline-a.ttf'
    receipt=json.loads(candidate.with_suffix('.ttf.json').read_text())
    if receipt.get('kind')!='offline-single-glyph-probe' or [x.get('character') for x in receipt.get('replaced',[])]!=['a']:
        raise RuntimeError('This installer is restricted to the reviewed single a-glyph probe')
    assert sha(candidate)==receipt['candidateSHA256']
    sip=run('/usr/bin/csrutil','status').strip()
    authenticated=run('/usr/bin/csrutil','authenticated-root','status').strip()
    plan={'model':model,'rootSnapshot':root['DeviceIdentifier'],'systemVolume':volume['DeviceIdentifier'],
          'sip':sip,'authenticatedRoot':authenticated,'target':str(FONT),'candidate':str(candidate),
          'sourceSHA256':receipt['sourceSHA256'],'candidateSHA256':receipt['candidateSHA256'],
          'changes':receipt['replaced'],'dryRun':not args.apply}
    print(json.dumps(plan,indent=2))
    if not args.apply:return
    if os.geteuid()!=0:raise RuntimeError('Run inside the disposable guest with sudo')
    if 'disabled' not in sip.lower() or 'disabled' not in authenticated.lower():
        raise RuntimeError('Guest SIP and authenticated-root must both be disabled in guest Recovery first')
    backup=LAB/'backups/SFNS.ttf.original'
    backup.parent.mkdir(exist_ok=True)
    if backup.exists():
        if sha(backup)!=receipt['sourceSHA256']:raise RuntimeError('Backup hash mismatch')
    else:
        if sha(FONT)!=receipt['sourceSHA256']:raise RuntimeError('Booted original differs from candidate source')
        with backup.open('xb') as dest:dest.write(FONT.read_bytes())
        if sha(backup)!=receipt['sourceSHA256']:raise RuntimeError('Backup verification failed')
    # APFS list may omit MountPoint even when Update has mounted the underlying
    # System volume. Query that device directly before attempting another mount.
    details=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/dev/'+volume['DeviceIdentifier']]))
    existing=details.get('MountPoint') or volume.get('MountPoint')
    mount=Path(existing) if existing else MOUNT
    if not existing:
        if mount.is_symlink():raise RuntimeError('Refusing symlink mountpoint')
        mount.mkdir(mode=0o700,exist_ok=True)
        run('/sbin/mount_apfs','-o','nobrowse','/dev/'+volume['DeviceIdentifier'],mount)
    mounted=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist',str(mount)]))
    if mounted['DeviceIdentifier']!=volume['DeviceIdentifier']:
        raise RuntimeError('Mounted device does not match the guest boot System volume')
    run('/sbin/mount','-uw',mount)
    target=mount/'System/Library/Fonts/SFNS.ttf'
    if target.is_symlink():raise RuntimeError('Refusing a symlink system-font target')
    before=sha(target)
    allowed={receipt['sourceSHA256'],receipt['candidateSHA256']}
    if before not in allowed:raise RuntimeError('Underlying System font differs from both recorded states')
    source=backup if args.restore else candidate
    state=LAB/('results/system-mutation-'+uuid.uuid4().hex[:8]+'.json')
    mutation={**plan,'targetOnMount':str(target),'beforeSHA256':before,'afterSHA256':sha(source),'snapshotCreated':False,'restore':args.restore}
    save(state,mutation)
    try:
        with target.open('wb') as stream:
            stream.write(source.read_bytes());stream.flush();os.fsync(stream.fileno())
        os.chown(target,0,0);os.chmod(target,0o644)
        if sha(target)!=sha(source):raise RuntimeError('Written font hash mismatch')
        # Mount mode needs --bootefi to copy the required boot objects. --setBoot
        # is not supported on Apple Silicon; snapshot selection is handled by
        # --create-snapshot itself (see the local bless(8) manual).
        mutation['blessOutput']=run('/usr/sbin/bless','--mount',mount,'--bootefi','--create-snapshot','--verbose')
        mutation['snapshotCreated']=True
        # bless --info is unsupported for internal volumes on Apple Silicon.
        # diskutil is usable here and must not turn a committed snapshot into a
        # spurious transaction failure merely because inspection is unavailable.
        try:
            mutation['snapshotsAfter']=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','apfs','listSnapshots','-plist','/dev/'+volume['DeviceIdentifier']]))
        except Exception as inspect_error:
            mutation['inspectionError']=str(inspect_error)
        save(state,mutation)
    except BaseException as error:
        mutation['error']=str(error)
        try:
            with target.open('wb') as stream:
                stream.write(backup.read_bytes());stream.flush();os.fsync(stream.fileno())
            mutation['originalFileRestoredAfterError']=sha(target)==receipt['sourceSHA256']
        except Exception as restore_error:
            mutation['restoreError']=str(restore_error)
        save(state,mutation)
        raise
    print('Snapshot prepared in guest. Reboot the guest, verify rendering, then restore and reboot again.')


if __name__=='__main__':main()
