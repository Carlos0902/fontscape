#!/bin/zsh
set -eu
model=$(/usr/sbin/sysctl -n hw.model)
[[ "$model" == VirtualMac* ]] || { echo "Refusing to run outside an Apple virtual Mac" >&2; exit 1; }
share="/Volumes/My Shared Files/fontlab"
lab="$HOME/FontLab"
[[ -f "$share/manifest.json" ]] || { echo "Read-only FontLab payload share missing" >&2; exit 1; }
[[ ! -e "$lab" ]] || { echo "Lab already exists; preserve its reports and choose a fresh VM" >&2; exit 1; }
mkdir -p "$lab"
cp -R "$share/" "$lab/"
cd "$lab"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONPATH="$lab/python"
mkdir -p results
python3 - <<'PY'
import json, platform, subprocess, site, shutil
from pathlib import Path
import fontTools
model = subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.model'], text=True).strip()
assert model.startswith('VirtualMac')
Path('.fontlab-disposable.json').write_text(json.dumps({'model':model,'purpose':'FontLab disposable guest','hostSystemMutationAllowed':False}))
# Make the app's Python experiments usable offline, not only this shell session.
user_site=Path(site.getusersitepackages())
user_site.mkdir(parents=True,exist_ok=True)
if not (user_site/'fontTools').exists():
    shutil.copytree(Path('python/fontTools'),user_site/'fontTools')
print('Guest:',platform.mac_ver()[0],model,'fontTools:',fontTools.__version__)
PY
python3 scripts/preflight.py results/preflight.json
/usr/sbin/diskutil apfs list -plist > results/apfs-layout.plist
/usr/sbin/diskutil apfs listSnapshots / -plist > results/startup-snapshots.plist
./fontlab-probe snapshot > results/initial-snapshot.json
./fontlab-probe render-system results/initial-system.png > results/initial-system-render.json
python3 scripts/experiment.py --cli ./fontlab-probe --font HanNewsSerif-Medium.ttf --output results/protected-baseline
python3 scripts/verify-report.py results/protected-baseline
python3 scripts/build-outline-probe.py --system-font /System/Library/Fonts/SFNS.ttf --donor HanNewsSerif-Medium.ttf --output results/SFNS-outline-a.ttf
python3 scripts/verify-outline-probe.py /System/Library/Fonts/SFNS.ttf results/SFNS-outline-a.ttf
./fontlab-probe raw /System/Library/Fonts/SFNS.ttf > results/system-raw.json
./fontlab-probe raw results/SFNS-outline-a.ttf > results/candidate-raw.json
./fontlab-probe render-file results/SFNS-outline-a.ttf results/candidate.png > results/candidate-render.json
python3 - <<'PY'
import json
from pathlib import Path
a=json.loads(Path('results/system-raw.json').read_text())
b=json.loads(Path('results/candidate-raw.json').read_text())
assert a['glyphCount']==b['glyphCount'] and a['postscript']==b['postscript']
assert a['renderSHA256']!=b['renderSHA256']
Path('results/candidate-validation.json').write_text(json.dumps({'namesAndGlyphCountPreserved':True,'renderChanged':True,'systemFontInstalled':False}))
print('PASS: candidate decodes with same identity and different glyph rendering')
PY
echo "Protected baseline and offline candidate ready. No system files modified."
