#!/bin/zsh
set -eu
cd "${0:A:h:h}"
zsh scripts/check-system-engine.sh
for arch in arm64 x86_64; do
  swift build -c release --triple "$arch-apple-macosx14.0"
done
mkdir -p dist
stage=$(mktemp -d "$PWD/dist/.package.XXXXXX")
trap 'rm -rf "$stage"' EXIT
app="$stage/Fontscape.app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
for binary in Fontscape fontlab-probe fontscape-system; do
  lipo -create ".build/arm64-apple-macosx/release/$binary" ".build/x86_64-apple-macosx/release/$binary" -output "$app/Contents/MacOS/$binary"
done
mkdir -p "$app/Contents/Resources/Tools"
cp scripts/system-build.py scripts/system-latin.py "$app/Contents/Resources/Tools/"
cp docs/SYSTEM_GUIDE.md "$app/Contents/Resources/"
python3 scripts/bundle-runtime.py "$app/Contents/Resources/Runtime"
swift scripts/make-icon.swift "$stage/AppIcon.iconset"
iconutil -c icns "$stage/AppIcon.iconset" -o "$app/Contents/Resources/AppIcon.icns"
cat > "$app/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>Fontscape</string>
<key>CFBundleIdentifier</key><string>com.carlos0902.fontscape</string>
<key>CFBundleName</key><string>Fontscape</string>
<key>CFBundleDisplayName</key><string>Fontscape</string>
<key>CFBundleIconFile</key><string>AppIcon</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>0.3.0</string>
<key>CFBundleVersion</key><string>2</string>
<key>LSMinimumSystemVersion</key><string>14.0</string>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
codesign --force --sign - --options runtime "$app/Contents/MacOS/fontlab-probe"
codesign --force --sign - --options runtime "$app/Contents/MacOS/fontscape-system"
codesign --force --sign - --options runtime "$app"
codesign --verify --deep --strict "$app"
python3 scripts/verify-app.py "$app"
codesign --verify --deep --strict "$app"
# Copy into a clean destination; no resources from earlier builds survive.
rm -rf "$PWD/dist/Fontscape.app"
mv "$app" "$PWD/dist/Fontscape.app"
archive="Fontscape-0.3.0-beta.1-macos-universal.zip"
rm -f "$PWD/dist/$archive"
ditto -c -k --sequesterRsrc --keepParent "$PWD/dist/Fontscape.app" "$PWD/dist/$archive"
(cd dist && shasum -a 256 "$archive" > SHA256SUMS.txt)
echo "Built: $PWD/dist/$archive"
