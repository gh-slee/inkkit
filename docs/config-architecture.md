# Configuration foundation

This is a synthetic-only development foundation. It is not imported by the
migration CLI and does not weaken its source-card or destructive-operation checks.
No real-card action exists in the helper protocol.

## Source contract

The schema is pinned to CrossInk v1.6.1, commit
`9914146eeae7b46b300f475a16c32426fc02ec1f`:

- [SD settings serialization](https://github.com/uxjulia/CrossInk/blob/9914146eeae7b46b300f475a16c32426fc02ec1f/src/CrossPointSettings.cpp#L438)
- [Defaults and limits](https://github.com/uxjulia/CrossInk/blob/9914146eeae7b46b300f475a16c32426fc02ec1f/src/CrossPointSettings.h#L565)
- [Setting definitions](https://github.com/uxjulia/CrossInk/blob/9914146eeae7b46b300f475a16c32426fc02ec1f/src/SettingsList.cpp)

Supported fields: line height, word spacing, horizontal/vertical margins,
hyphenation, embedded styles, screen inversion, device name, sleep timeout,
hidden-file visibility, extension visibility and statistics collection.
Booleans remain numeric 0/1; integers reject Python bool and float inputs. Empty
device names retain the hardware default; nonempty names need 2–20 UTF-8 bytes.
Sleep value 31 is Never. Font selection, hardware-dependent mappings and credentials
are deliberately excluded from this first schema.

Unknown JSON values are preserved. Only explicit changes to effective values are
written; absent defaults are not added. Original raw bytes are backed up and
restored exactly. Parsing rejects duplicate keys, invalid UTF-8, nonfinite numbers,
oversized files and invalid supported-field types. Legacy aliases require firmware
migration. Existing firmware `.tmp`/`.bak` files block editing and are left intact.

## Boundary and IO

`inkkit_config.py` accepts only a private temporary directory created by
`create_demo`, identified by its marker, inode/device and fixed parent/name policy.
The parent comes from Darwin's user-temp query, ignoring caller-controlled TMPDIR,
and must be on the same device as the host's private temporary storage. Mounted card
paths, arbitrary folders, unsafe ownership and changed identities are refused.
This is a preview restriction, not a completed real-card identity policy.

Directory descriptors and no-follow opens prevent path/symlink traversal. Files
must be bounded, single-linked regular files on the expected device. Snapshot
tokens include root/directory/file identity, hash, modification time and length.
Apply rechecks them under a nonblocking advisory lock and again before replacement.
Noncooperating external writers can still race a POSIX check/replace; no atomic
compare-and-swap or power-loss guarantee is claimed.

Read, preview and backup-list operations create no files. Apply may create its
lock even when values already match; no-op apply creates no backup or settings
rewrite. A changed apply writes a private host backup and prepared record before
replacing the settings file, fsyncs, reads back and marks the record written.
Failures retain recovery evidence. Restore requires current bytes to match the
backup's expected result, or already equal the original; it refuses later edits.

Config backups use `inkkit-config-backup-v1`, not the migration manifest. A backup
directory contains exact `before.bin` bytes and `record.json` with hashes, identity
and prepared/written/restoring/restored state. They are not encrypted. The preview
keeps these entirely synthetic backups within its temporary workspace. Future
real-card backups must live on the Mac, outside the card and signed app bundle;
the proposed GUI default is Application Support/InkKit/Backups. The CLI's existing
script-adjacent backup default remains unchanged.

## Helper protocol

One bounded JSON object on stdin and one response on stdout per process. Protocol
version 1 supports `demo.create`, `config.read`, `config.preview`, `config.apply`,
`backups.list`, `config.restore_preview`, and `config.restore`. Request fields are
explicitly allowlisted; unknown actions, versions and extra fields fail closed.
No subprocess shell, formatter, network API or arbitrary file action is exposed.
The native app clears inherited runtime overrides and passes requests over pipes.
Errors use fixed messages without raw contents, paths or tracebacks.

The helper is a private, bundled interface, not a new supported public CLI.
`--self-test` creates and removes a synthetic workspace, applies a change and
restores it. The native executable's self-test also checks the bundled Python
prefix and absence of site initialization.

## Before real-card support

Add a separately reviewed physical-volume adapter, explicit model/firmware profile
selection, volume permissions/identity checks, Mac-side backups, safe ejection and
failure UX. Reuse appropriate migration safety primitives without calling format
or disabling erase guards. X3 settings need their own authorized manual acceptance;
existing migration acceptance does not cover this new workflow. Other models need
capability filtering and explicit hardware-validation status.

Wi-Fi/OPDS credential writing remains pending. CrossInk's device-MAC obfuscation
and optional legacy plaintext handoff require a separate explicit product choice.
Do not turn a synthetic marker into authorization to edit an actual mounted card.
