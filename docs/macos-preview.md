# macOS configuration development build

This is **not a released Mac app**. Development source provides native forms for
CrossInk v1.6.1 global settings on an explicitly selected current SD card, as well
as synthetic demos. See [every supported control](configuration-reference.md).
No new settings workflow has physical acceptance; test the synthetic demo first.
The separately released migration CLI remains unchanged.

## Build locally

Requirements: macOS, Command Line Tools with a macOS 14+ SDK and Swift compiler,
and the python.org CPython 3.12 framework. No pip packages, Node, Docker or full Xcode
project are required. The build targets macOS 14 and the build host CPU; other
architectures/OS versions are not certified.

```bash
XTEINK_TESTING=1 python3 -m unittest discover -s tests -v -b
python3 scripts/check_configuration_docs.py
python3 scripts/build_macos_preview.py --output work/macos-config
open -n 'work/macos-config/InkKit Preview.app'
'work/macos-config/InkKit Preview.app/Contents/MacOS/InkKit' --self-test
```

Use a fresh output directory. The builder never overwrites old apps. Failed builds
may leave incomplete bundles; do not run/distribute them. The built app includes
its own runtime and does not require Python from PATH or Codex to run.

## Try synthetic settings

Choose a demo model, then **Create synthetic demo**. The sidebar groups Display,
Reading, Library, Controls, Frontlight, Status bars and Device. Separate forms cover
Wi-Fi, OPDS, Reading sync, Font rendering and Dictionary. Unsupported model controls
are disabled. Existing unsupported stored values remain visible and unchanged.
Use Add/Remove for collection entries; font/dictionary inputs refer to assets
already installed on the SD card, not Mac paths. Asset installation is not included.

Drafts stay in memory. The selected card/demo is not persisted across app launches; reopen it after relaunch. **Review changes** (Cmd+S) shows all changes, including any
shortcut ownership adjustments. Cancel preserves the draft; Discard clears it.
**Back up & apply** saves the original, writes and reads back before reporting
success. Changing categories with a draft requires discard confirmation. Backups
lets you choose a category, review a restore or reveal private backup storage.
Demos contain invented data and remain under OS temporary storage until cleanup.

## Open a current card (experimental)

Keep a separate verified full backup first. Shut down the reader and put its current
card in a separate SD reader. Choose **Open SD card**, select the mounted volume
itself under `/Volumes`, choose the reader model and confirm CrossInk v1.6.1.
The app cannot detect this firmware/model from the card; do not guess. Unsupported
versions/layouts, ambiguous devices and pending firmware recovery files are blocked.

Opening creates only private Mac-side session state. Review/apply one category at
a time. Original files are backed up under
`~/Library/Application Support/InkKit/Backups/`, never onto the card or checkout.
These small config backups are separate from the CLI's repo-local full-card ZIPs.
Nothing is uploaded. **Eject** must succeed before removal. Reinsert the card into
the shut-down reader, then verify each changed setting on that reader.

New passwords use an explicit per-write plaintext-handoff checkbox. Existing
passwords stay hidden and unchanged unless replaced/cleared. Rewriting or restoring
a file that still contains plaintext also needs consent. Protect the card/backups:
CrossInk must load and successfully resave the relevant Wi-Fi/OPDS/sync store; boot
alone does not guarantee removal of plaintext. No account login/connectivity test
is performed by the app. See [credential behavior](configuration-reference.md#preservation-and-dependent-behavior).

On an interrupted operation, stop, reconnect/reopen and inspect Backups. External
changes can block restore to avoid overwriting later data. Preserve all recovery
evidence; do not force a write or format the card. See [safety](safety.md) and
[architecture/recovery limits](config-architecture.md).

## Packaging and installer status

The builder copies only named core/app files and licenses, never the checkout,
backups, settings, site-packages, shell config or credentials. It selects stdlib
modules by CPython's module names and includes only extensions linked entirely to
Apple system libraries. The purpose-specific runtime is relocated into the app;
Mach-O code is reduced to the build CPU. BuildInfo records exact inputs/runtime
hashes and that this build includes real-card access. Signature verification and
native synthetic self-test run during build; host Python is not modified.

The local runtime is a feasibility spike, not the approved production runtime.
The app is **ad-hoc signed only**: no Developer ID, validated Hardened Runtime,
notarization or public Gatekeeper/download acceptance. Intel, clean-Mac, actual
macOS 14, visual/keyboard/VoiceOver and physical settings tests remain pending.
No public app/DMG/PKG is included in v1.0.0 or automatically uploaded by CI.

A future self-contained app can use a drag-to-Applications DMG; ordinary settings
management needs no privileged installer. Before public distribution, maintain an
up-to-date runtime, verify licensing/OS/architecture coverage, sign nested code
with Developer ID, test Hardened Runtime, notarize/staple and test a downloaded app
on a clean Mac without Python. An updater, login item, privileged daemon and
publication/signing automation are not implemented.

Official references: [Apple packaging](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution),
[notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution),
[Python runtime flags](https://docs.python.org/3.12/using/cmdline.html).
