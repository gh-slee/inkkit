# macOS developer preview

This local feasibility spike is **not a released Mac app**. It manages invented
settings in its own temporary workspace. It cannot select, edit, format or eject
real SD cards. Wi-Fi/OPDS credentials, asset management and migration are absent.
The existing migration CLI continues to work separately.

## Build locally

Requirements for this spike: macOS, Command Line Tools with a macOS 14+ SDK and
Swift compiler, and the python.org CPython 3.12 framework. No pip dependencies,
Node, Docker or full Xcode project are required. The build targets macOS 14 and
the build host CPU; other architectures/OS versions are not certified.

```bash
XTEINK_TESTING=1 python3 -m unittest discover -s tests -v -b
python3 scripts/build_macos_preview.py --output work/macos-preview
open 'work/macos-preview/InkKit Preview.app'
'work/macos-preview/InkKit Preview.app/Contents/MacOS/InkKit' --self-test
```

Use a fresh output directory per build. The builder never replaces an existing
app. A failed build can leave an incomplete bundle; do not run or distribute it.
The app runs with its bundled runtime and does not require Python from PATH.

Click **Create synthetic demo**, edit Reading or Device, then **Review changes**
(Cmd+S). Cancel leaves the draft; **Back up & apply** backs up and verifies the
write. Backups offers **Review restore**. Use **Reload** after an interrupted
operation and inspect retained backups. Creating a new demo resets the app draft;
previous demos remain in the temporary directory until macOS cleanup. They contain
only invented data. This preview does not persist the selected workspace across
app launches or prevent force termination during a write.

## Packaging boundary

The builder copies only named app/core source files and license text. It does not
copy the checkout, migration backups, local settings, site-packages, user-site
modules, shell configuration or credentials. Runtime source is selected from
CPython's standard-library module names. Only extensions linked entirely to Apple
system libraries are included; this is a purpose-specific runtime, not a complete
Python distribution. Unsupported host-library dependencies are not bundled.

Python's executable and shared library are relocated inside the app, native code
is reduced to the build CPU, and copied Mach-O files plus the app receive ad-hoc
signatures. `BuildInfo.json` records source hashes, Python version and preview
scope. The builder verifies signatures and runs the native-launcher/helper
synthetic roundtrip. It does not install or modify the host Python framework.

Ad-hoc signing is for local development. This spike is **not Developer ID signed,
Hardened Runtime validated, notarized or Gatekeeper-approved for public download**.
The locally installed runtime's patch level is recorded, not security-reviewed
or approved as the future shipping runtime. Do not publish this app as a release.

## Toward a public installer

A self-contained app can be distributed in a drag-to-Applications DMG; a `.pkg`
is unnecessary for ordinary settings management. Before that, choose and maintain
an up-to-date runtime, validate licensing/architecture/OS coverage, sign nested
code using Developer ID, enable/test Hardened Runtime, notarize and staple, then
test a downloaded app on a clean Mac with no Python installation. Validate
removable-volume access and real-card settings separately.

Keep update checks manual initially. No updater, login item, privileged daemon,
automatic publisher, signing secret or real-card integration test is added here.

Official references: [Apple packaging](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution),
[notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution),
[Python runtime flags](https://docs.python.org/3.12/using/cmdline.html).
