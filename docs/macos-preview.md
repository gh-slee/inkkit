# macOS configuration development build

This is **not a released Mac app**. Development source provides native forms for
CrossInk v1.6.1 global settings on an explicitly selected current SD card, as well
as synthetic demos. See [every supported control](configuration-reference.md).
Selected X3 preferences, Restore and safe eject have owner-reported acceptance;
other settings/models and the newer complete-snapshot workflow remain unvalidated.
Test the synthetic demo first.
See [source evidence, X3 acceptance and screenshot gates](configuration-validation.md).
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
are disabled, and the Frontlight page/search group is hidden on models without
that hardware (X3, X4 and X4 Classic). X4 Pro exposes Frontlight. Raw stored
unsupported values are still preserved. Built-in font selection applies when the SD font family is empty;
a nonempty SD family takes precedence. Clear it explicitly to return to a built-in font. Existing unsupported stored values remain visible and unchanged.
Use Add/Remove for collection entries; font/dictionary inputs refer to assets
already installed on the SD card, not Mac paths. Asset installation is not included.

Drafts stay in memory. The selected card/demo is not persisted across app launches; reopen it after relaunch. **Review changes** (Cmd+S) shows all changes, including any
shortcut ownership adjustments. Cancel preserves the draft; Discard clears it.
**Back up & apply** saves the original, writes and reads back before reporting
success. Changing categories with a draft requires discard confirmation. Backups
shows complete configuration snapshots and clearly labeled legacy single-file
backups without a category dropdown. See the complete-backup workflow below.
Demos contain invented data and remain under OS temporary storage until cleanup.
Only the canonical Mac user temporary directory is accepted; if a restricted
environment redirects the system query to a nested/caller-provided folder or
cannot supply a trusted location, demo creation stops without writing there.

## Open a current card (experimental)

Keep a separate verified full backup first. Shut down the reader and put its current
card in a separate SD reader. Choose **Open SD card**, select the mounted volume
itself under `/Volumes`, choose the reader model and confirm CrossInk v1.6.1.
A **Confirm your reader** sheet must show the model selector, firmware checkbox,
Cancel and Open card. Until you confirm, the card has not been opened. If an older
build displays an empty sheet, quit it and rebuild into a fresh output directory.
The app cannot detect this firmware/model from the card; do not guess. Unsupported
versions/layouts, ambiguous devices and pending firmware recovery files are blocked.

The selected root must be a real mount boundary and exactly match the mount path
reported by macOS. Some plist responses omit `Mounted`; its absence alone is not
an error when these independent checks pass. Explicit unmounted/malformed flags,
mount changes and device/partition identity mismatches remain blocked.

Native session tokens preserve full unsigned 64-bit filesystem identifiers.
An existing empty `dictionary.bin` is a valid empty global dictionary selection,
including FAT file identifiers above the signed 64-bit range. Opening it preserves
the original bytes; selecting a path does not install dictionary assets.

Opening creates only private Mac-side session state. Review/apply one category at
a time. Original files are backed up under
`~/Library/Application Support/InkKit/Backups/`, never onto the card or checkout.
These small config backups are separate from the CLI's repo-local full-card ZIPs.
Nothing is uploaded. **Eject** closes InkKit's card-directory handles, retains
the Mac-side operation lock and rechecks the card identity before normal macOS
ejection. It never forces an unmount. If another app still uses the card, close
those files and retry; a failed eject preserves the session. **Eject** must
succeed before removal. Reinsert the card into
the shut-down reader, then verify each changed setting on that reader.

Wi-Fi **Use an open network (clear password)** clears only the selected entry's
saved password when you apply the change; it does not change router security.
Use it for networks that already require no password. Leaving the new-password
field blank keeps the existing password.

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

## Complete configuration backups

**Backup now** stores the exact bytes/existence of all six global stores:
`crossink-settings.json`, `wifi.json`, `opds.json`, `koreader.json`,
`ttf-rendering.json` and `dictionary.bin`, under `.crosspoint` on the card.
A missing optional file and an existing empty dictionary selection are distinct.
Unknown supported-file fields are retained. This is not a full-card backup: books,
font/dictionary assets, per-book state and binary firmware state are excluded.

Complete real-card snapshots live under
`~/Library/Application Support/InkKit/ConfigurationBackups/`, in private directories,
with a versioned manifest and per-file SHA-256. They may contain credentials and
are not encrypted. Synthetic snapshots stay inside their separate demo workspace.
No backup is uploaded or packaged. The migration CLI's repo-local ZIPs are unchanged.

- **Backup now** captures and verifies all six stores without modifying the card.
  Each native Apply also saves a complete snapshot before its original single-file
  transaction; a full restore first saves the current complete state.
- The timestamped list is sorted newest first. Complete real-card backups remain
  visible/deletable without an inserted card. Restore needs an opened compatible
  model/firmware and is intended for the same original reader, not another device.
- **Restore** reviews all affected fields/files, requires fresh consent for any
  restored plaintext credentials and checks both the selected backup checksum and
  current tokens again before writing. Any older compatible complete snapshot can
  be chosen after review; it is not tied to the latest single-file transaction.
- Each file is replaced atomically and read back; **six files are not one atomic
  filesystem transaction**. A journal and complete pre-restore backup are retained
  on interruption. Some files may already be restored. Individual native Apply is
  blocked until a reviewed full restore resolves recovery; select the pre-restore
  backup to recover or review the intended snapshot again to retry. Do not bypass
  stale-token, identity or recovery protections.
- **Delete** requires confirmation and removes only the selected local backup.
  Pending recovery source/target snapshots and prepared/restoring legacy records
  are protected. Unexpected files, corrupt inventories and symlinks are refused.
- Older per-file backups remain labeled **Legacy single file** with their scope;
  they retain the original strict restore checks. They cannot be reconstructed
  into complete historical configurations. Completed legacy records can be deleted.

The app's firmware/model selectors are populated by `profiles.describe`; no remote
code/profile downloads run. The catalogue currently exposes the audited v1.6.1
provider. See [ongoing version/device support](firmware-support.md) for expansion.

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
macOS 14 and full keyboard/VoiceOver checks remain pending. Main-page dark-mode
visual review and synthetic native backup/restore flows passed; see the
[gallery](screenshots.md). Minimum-size and light-mode review remain pending. Physical coverage
is limited to the X3 owner report; the new complete-snapshot workflow and other
settings/models remain pending.
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
