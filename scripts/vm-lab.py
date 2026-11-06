#!/usr/bin/env python3
"""Manage only the named FontLab guest; keep its pristine restore clone untouched."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
VM = 'fontlab-tahoe'
PRISTINE = 'fontlab-tahoe-pristine'
ARTIFACTS = ROOT/'artifacts/vm-setup'
PAYLOAD = ROOT/'artifacts/vm-payload'
TART = '/opt/homebrew/bin/tart'


def run(*args, **kwargs):
    return subprocess.run([TART, *args], check=True, **kwargs)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['status','clone','start','stop','bootstrap','collect','recovery','checkpoint'])
    a = p.parse_args()
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    if a.action == 'status':
        run('list'); return
    if a.action == 'clone':
        env=dict(os.environ,TART_NO_AUTO_PRUNE='1')
        run('clone',PRISTINE,VM,env=env)
        run('set',VM,'--cpu','4','--memory','6144','--display','1280x800px','--no-display-refit');return
    if a.action == 'checkpoint':
        # Tart refuses cloning a running VM. Caller first shuts down the guest.
        run('clone',VM,'fontlab-tahoe-protected',env=dict(os.environ,TART_NO_AUTO_PRUNE='1'));return
    if a.action in ['start','recovery']:
        rows=json.loads(subprocess.check_output([TART,'list','--source','local','--format','json']))
        if any(row['Name']==VM and row['Running'] for row in rows):
            if a.action=='recovery':
                raise RuntimeError('Stop the test VM before starting its Recovery environment')
            print('fontlab-tahoe 已在运行，请切换到 Tart 窗口。');return
        args=[TART,'run',VM,'--net-host','--no-clipboard','--no-audio','--no-usb-accessories',
              '--dir',f'fontlab:{PAYLOAD}:ro']
        if a.action=='recovery':args.append('--recovery')
        log=ARTIFACTS/(a.action+'.log')
        with log.open('ab') as stream:
            process=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        (ARTIFACTS/'run-process.json').write_text(json.dumps({'pid':process.pid,'vm':VM,'recovery':a.action=='recovery','argv':args}))
        time.sleep(2)
        if process.poll() is not None:
            raise RuntimeError('Tart did not remain running: '+log.read_text()[-2000:])
        print('Started PID',process.pid,'log:',log);return
    if a.action=='stop':
        run('stop',VM);return
    if a.action=='bootstrap':
        with (ROOT/'scripts/vm-bootstrap.sh').open('rb') as source:
            run('exec','-i',VM,'/bin/zsh','-s',stdin=source)
        return
    if a.action=='collect':
        target=ARTIFACTS/'guest-results.tar.gz'
        with target.open('wb') as dest:
            run('exec',VM,'/usr/bin/tar','-czf','-','-C','/Users/admin/FontLab','results',stdout=dest)
        print(target)


if __name__=='__main__':main()
