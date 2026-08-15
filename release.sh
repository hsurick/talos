#!/bin/sh
# Builds dist/Talos.zip, the download for a GitHub release: standalone app, ad-hoc signed (no Apple developer account).
set -e
cd "$(dirname "$0")"
rm -rf build dist
.venv/bin/python setup.py py2app > build.log
app=dist/Talos.app
chmod -R u+w "$app"
# py2app copies Pillow's liblzma over Python's and its edit breaks that file's signature; put Python's own back.
# shortcut: Homebrew's Python path; change it if you build with another Python.
cp -f /opt/homebrew/opt/xz/lib/liblzma.5.dylib "$app/Contents/Frameworks/"
chmod u+w "$app/Contents/Frameworks/liblzma.5.dylib"
# Homebrew rewrites library IDs to its own path and drops build-machine Cellar search paths when it installs the app,
# which would break the signature. Write what it would write, so it finds nothing to change. (IDs aren't used to load.)
find "$app" -type f \( -name "*.dylib" -o -name "*.so" -o -path "*/Python.framework/Versions/*/Python" \) |
while read -r f; do
  if [ -n "$(otool -D "$f" | sed -n 2p)" ]; then
    install_name_tool -id "/opt/homebrew/opt/talos/${f#dist/}" "$f" 2>/dev/null
  fi
  otool -l "$f" | awk '/LC_RPATH/ {getline; getline; print $2}' | grep /Cellar/ |
    while read -r path; do install_name_tool -delete_rpath "$path" "$f" 2>/dev/null; done
  codesign --force -s - "$f"  # the edit voids its signature, and --deep below skips libraries under Resources
done
codesign --force --deep -s - "$app"
codesign --verify --deep --strict "$app"  # an invalid signature makes macOS call a downloaded app "damaged"
# No resource forks or extended attributes: plain unzip (Homebrew's) writes them out as ._ files, breaking the signature.
ditto -c -k --norsrc --noextattr --keepParent "$app" dist/Talos.zip
echo "dist/Talos.zip ready. sha256 for the Homebrew formula: $(shasum -a 256 dist/Talos.zip | cut -d' ' -f1)"
