# Configuration architecture

The SwiftUI app uses a bundled standard-library Python helper. It is separate
from the migration CLI and never calls its formatter or restore runner. See the
[generated configuration reference](configuration-reference.md) for the complete
CrossInk v1.6.1 field/storage/model contract and primary source links.

## Components

- `crossink_profile.py`: audited storage IDs, limits, languages and defaults.
- `inkkit_schema.py`: model capabilities and typed forms for six stores.
- `inkkit_codec.py`: pure validation, explicit patches, shortcut ownership and
  credential-redacted differences. No device, network or filesystem operations.
- `inkkit_config.py`: descriptor-based transactions, private backups and recovery.
- `inkkit_volume.py`: explicit current-card sessions, read-only macOS identity
  queries, private host storage and targeted safe ejection. No formatting API.
- `inkkit_helper.py`: bounded, allowlisted one-request-per-process IPC.
- `macos/InkKitApp.swift`: native forms, in-memory drafts, review and per-write
  plaintext consent. No arbitrary terminal or file editor is exposed.

## Storage boundary

A real card must be selected explicitly, directly under `/Volumes`, and the user
must select X3/X4/X4 Classic/X4 Pro and confirm CrossInk v1.6.1. A directory name
cannot prove the reader model or firmware. The adapter requires a namespaced
CrossInk settings file, external writable removable USB/SD media <=2 TiB, one
mounted FAT32/exFAT partition, a readable UUID and no backup/Time Machine markers.
Internal, virtual, fixed, unknown, read-only and unsupported layouts fail closed.
Migration's source-like-card erase guard remains unchanged: this separate editor
must open a current reader card and has no erase action.

A private `card:<random session>` reference binds the mount, root inode/device,
volume/partition/media UUIDs, reported hardware, model and firmware profile.
Every operation rechecks the session and mount. Free space is intentionally not
part of identity because applying settings changes it. Some media lack unique
hardware serials; cloned identifiers and hotplug races cannot be eliminated.
Never swap cards during an operation. Reopen after any disconnect or external edit.

Real-card recovery data lives under the OS account's home (not an inherited HOME):
`~/Library/Application Support/InkKit/Backups/<card-profile identity>/`.
Session references live in sibling `Sessions/`. Host directories are owned by the
current user, mode 0700 and opened without following symlinks. Backups must be on
a different device from the selected card. The CLI's script-adjacent backup default
and legacy migration manifests/journals are unchanged.

Synthetic demos remain private, helper-created Darwin user-temp directories with
marker/inode/device checks. Caller TMPDIR cannot redirect them to a card. Tests
mock all real volume queries and ejection; `XTEINK_TESTING=1` blocks actual calls.

## Transactions and recovery

Only six allowlisted filenames inside `.crosspoint` can be edited. Dictionary
selection is raw UTF-8; the other stores are bounded strict JSON objects. Unknown
fields survive; absent defaults are for display only. Explicit changes preserve
the source's numeric toggles, JSON booleans and persisted enum IDs. Unsupported
legacy schemas, malformed input and existing firmware `.tmp`/`.bak` evidence block
editing. No firmware migration or recovery file is consumed by the editor.

No-follow directory/file descriptors prevent symlink traversal. Config files must
be single-linked regular files on the expected device, <=64 KiB. FAT ownership is
not treated as Unix ownership; private Mac-side files still require owner checks.
Snapshot tokens bind directory/file identity, SHA-256, mtime, length and store.
Apply rechecks under a host-side advisory lock and immediately before replacement.

Read, change/restore preview and backup-list create no files. Opening a card creates
private Mac-side session/recovery directories, never card markers. Apply can create
a lock on no-op; it creates no backup or settings rewrite if effective data matches.
Before a changed apply, exact original bytes and a prepared record are written,
fsynced and verified on the Mac. The new card file is written through an exclusive
temporary file, rechecked, atomically replaced, fsynced and read back. Only then is
the recovery record marked written. Failures retain evidence and stop the workflow.

Backups use `inkkit-config-backup-v1`, separate from migration backups. Per-store
folders contain random-ID directories with `before.bin` and `record.json` hashes,
card/profile identity, before-file existence and prepared/written/restoring/restored
state. Restore requires the current file to equal the recorded result or original;
later external edits block it. Restoring a newly created store removes that file.
Raw original bytes are restored exactly. Incomplete/invalid records are not silently
used. Backups are not encrypted and can retain old plaintext credentials.

There is no atomic compare-and-swap against noncooperating writers, cross-file
transaction, hardware attestation or power-loss guarantee. Apply one category at a
time, keep the reader shut down while the card is in the Mac, and use Eject before
removal. Force quit/unplug may leave a temporary file or retained recovery record;
review the original backup before further edits. Do not delete recovery evidence
just to bypass a rejection.

## Credentials and IPC

Saved plaintext/obfuscated passwords never appear in snapshots or differences.
Blank input keeps the existing material; explicit Clear removes it. New passwords
use CrossInk's plaintext fallback, only after a fresh review checkbox for each write.
Any resulting or restored file containing plaintext requires that consent. Firmware
must load and successfully resave the store to replace plaintext with MAC-dependent
obfuscation; boot alone is insufficient. Obfuscation is not encryption. No device
MAC guessing, decryption, network login or keychain integration is implemented.

Protocol 2 supports `demo.create`, `volume.open`, `volume.eject`,
`volume.backup_location`, `config.read`, `config.preview`, `config.apply`,
`backups.list`, `config.restore_preview` and `config.restore`. Unknown request
fields/actions/versions are rejected. Inputs are <=64 KiB, native responses <=1 MiB,
and operations time out after 120 seconds. The helper has fixed public-safe errors;
raw contents, diskutil output, secrets and tracebacks are not logged. Requests use
pipes, never shell arguments. The native launcher clears runtime overrides and
uses its purpose-specific bundled Python runtime.

`--self-test` runs only a synthetic transaction and removes its own fixture. Native
self-test also checks typed response decoding and bundled-runtime isolation. The [source audit and acceptance gates](configuration-validation.md) distinguish
file readback from firmware behavior. Actual
X3 settings acceptance, other-device validation and visual/accessibility QA remain
separate gates. Existing X3 migration evidence does not validate this editor.
