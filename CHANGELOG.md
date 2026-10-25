# Changelog

## Unreleased

- Present the native macOS app first in the README, with build/use instructions,
  existing native screenshots, device scope and SwiftUI/AppKit/Python stack.
  Align contributor, security and architecture docs with complete configuration
  backups, current helper actions and the separate published migration CLI.

- Add actual native app screenshots with synthetic example data, current UI
  validation notes and exact-path/hash image publication checks.

- Add complete six-store configuration snapshots: Backup now, newest-first local
  history, reviewed older-snapshot restore and confirmed deletion. Retain a complete
  pre-restore state, per-file interruption journals and protected recovery evidence;
  keep legacy single-file backups with explicit scope and original restore checks.
- Load firmware/model choices and hardware capabilities from the backend catalogue;
  hide Frontlight navigation/search for X3, X4 and X4 Classic. Preserve unsupported
  stored data. Document ongoing future-version/device support through audited
  providers/tests rather than accepting unknown versions automatically.
- Record limited owner-reported X3 Restore, safe-eject and Sleep Screen acceptance;
  distinguish this from exhaustive control/model or new complete-snapshot validation.

- Close SD-card directory handles before normal ejection, retain the independent
  Mac-side operation lock and recheck card identity before the command. Preserve
  the session on failure so users can close other files and retry without forcing.

- Preserve full unsigned 64-bit filesystem identities in the native helper
  protocol. Fix Dictionary loading for empty FAT files with high-bit inode IDs;
  test lossless Python/Swift identity roundtrips and distinguish decoding errors.

- Reject unavailable or redirected system temporary directories in synthetic demos,
  including restricted environments that fall back to caller-provided `TMPDIR`.

- Support mounted FAT volumes whose macOS plist omits the optional `Mounted`
  flag. Require a real mount boundary and exact mount path, retain all media and
  session identity checks, and reject explicit unmounted or malformed flags.

- Present the reader-profile confirmation using the selected card as the sheet
  item. Avoid a blank first-open sheet caused by separate presentation/path state.
  Opening still requires model and firmware confirmation before any card reads.

- Re-audit pinned CrossInk sources and correct effective defaults for inherited
  previous-page gestures, legacy dark-mode/clock/browser preferences, Minimal-theme
  browser layout and display-bar battery fallback. Reject partially migrated legacy
  side-button pairs; preserve absent keys on no-op.
  Clarify SD-font precedence, link every main control to its upstream definition
  and document source/synthetic/native/physical evidence separately. Update the
  README tech stack and gate screenshots on real X3 settings acceptance.

- Add a native SwiftUI configuration development app with 148 model-aware main
  controls, Wi-Fi/OPDS CRUD, reading sync, 24 TTF profiles and global dictionary
  selection, pinned to CrossInk v1.6.1. Explicit current-card sessions use removable
  volume checks, private Mac backups, reviewed/verified apply, guarded exact restore
  and safe eject; synthetic demos remain available. Selected X3 settings now have limited owner-reported acceptance; other settings
  and models remain pending, separate from existing X3 migration validation.
- Preserve opaque passwords; require fresh explicit plaintext-handoff consent for
  every write/restore containing plaintext. Preserve legacy sync server semantics,
  unknown fields and missing defaults; enforce model capabilities and persisted IDs.
- Generate a complete field/storage reference and README summary from the schema;
  CI rejects documentation drift. Add synthetic field/store/fault/privacy regressions
  and mocked disk-session tests. Keep migration runtime and release tags unchanged.
  The local app is ad-hoc signed, not notarized or approved for public distribution.
- Rename the project and repository to InkKit (`gh-slee/inkkit`). Update project
  identity, CLI branding and repository links; preserve the published v1.0.0 tag,
  stable `xteink_sd_migrate.py` entry point and existing backup/recovery formats.
- List X3, X4, X4 Classic and X4 Pro individually, with only X3 physically validated.
  Keep other compatible XTEINK models conditional on the shared layout and guards.
  CrossInk firmware support for Seeed Studio Sticky is not an InkKit support claim.

## [1.0.0](https://github.com/gh-slee/inkkit/releases/tag/v1.0.0) — 2026-10-22

Published migration CLI release, originally named XTEINK SD Migrator. Native macOS
app changes belong to Unreleased above; this tag does not include the app.

- Prepare the first stable version with startup and `--version` reporting 1.0.0.
  Keep the stable script filename, standard-library runtime, existing CLI behavior,
  legacy v1 backup compatibility and private repo-local backup placement.
- Retain verified backups, guarded target formatting/restoration, read-only backup
  verification/preflight and journal-bound no-format recovery from the beta series.
  Update version/security documentation without changing migration logic.

- Record a reviewed X3 32 GB to 16 GB FAT32/MBR backup/restore result on the
  unreleased APFS-fix revision, including complete file/tree verification, safe
  eject and owner-confirmed reader acceptance. Document missing environment/build
  details and untested combinations; do not attribute the result to the beta.3 tag.
- Confirm X3-only full physical acceptance for v1.0.0. X4 and other compatible
  models retain implementation support with physical validation pending and do not
  block the initial stable release. Clarify the planned v1 compatibility commitment.

- Resolve APFS backing storage on internal non-removable Apple Fabric whole disks
  when macOS reports an unknown physical label. Require matching APFS store and
  hardware evidence; keep ambiguous/virtual storage and unsafe targets blocked.
  Add synthetic backup/erase-protection regressions and clarify storage-error text.
- Prepare an X3-first v1.0.0 acceptance plan, a v1 compatibility commitment and
  manual stable-release gates. Keep X4/other shared-layout models in implementation
  scope with physical evidence pending. This planning change itself added no
  hardware result or release; the later reviewed X3 result is recorded above.
- Apply ZIP directory resource limits to the ZIP64 end record used by Python,
  including archives without legacy sentinel values. Reject inconsistent or
  misdirected ZIP64 metadata before central-directory parsing.
- Reject root-dot member paths during manifest validation, before disk queries or
  erase. Preserve ordinary ZIP, tool-created ZIP64 and legacy v1 backup support.
- Add synthetic regressions for resource limits, malformed ZIP64 metadata,
  maximum-length ZIP comments and pre-erase path rejection. No real-card testing.

## [0.1.0-beta.3](https://github.com/gh-slee/inkkit/releases/tag/v0.1.0-beta.3) — 2026-10-20

- Exercise journal creation/write/fsync/atomic-replace/directory-sync failures,
  failed completion checkpoints, mid-write ENOSPC during restore/resume, target
  sync errors, Ctrl-C and journal cleanup failure with synthetic retry tests.
- Document persistence-failure recovery and manual prerelease validation. These
  checks preserve the existing runtime behavior; no new hardware claim is made.
- Add read-only `--verify-backup` using full legacy ZIP/manifest/hash validation.
- Add `--restore BACKUP.zip --dry-run` with shared target/storage/capacity preflight;
  no formatting, copying, backup/journal/lock creation or eject.
- Record private local restore journals; add read-only `--check-restore` and
  `--resume ... --dry-run`, plus confirmed no-format recovery with `--resume`.
  Preserve complete files and append only a verified active-file prefix; stop on
  conflicting/unexpected data. Keep source-card and guarded erase protections.
- Ignore/exclude recovery sidecars from public Git/source exports and add synthetic
  interruption, read-only, identity, concurrency and recovery regression tests.
- Keep v1 manifests, historical backup names and the standard-library runtime.
  No additional real-card testing was performed.

## 0.1.0-beta.2

- Describe and present the tool as model-independent CrossInk/CrossPoint XTEINK
  file-level migration, including X4 and other compatible XTEINK devices.
- Remove X3-only prompts/labels; format replacement volumes with the neutral
  `XTEINK` label. Keep historical backup folder/names and v1 schema compatible.
- Add a device/firmware evidence matrix and synthetic model-neutral roundtrips.
  Actual hardware evidence remains one X3 migration with the internal predecessor.
- Refresh README presentation, icon, badges, quick start, architecture, privacy,
  technology and documentation navigation to match the maintainer's OSS conventions.
- Add security policy, PR template, shared project instructions, contributor guides,
  source-publication guard and repository-local privacy hooks.
- Add full-history publication audits and pinned Actions with non-persistent
  credentials to macOS CI. Runtime remains standard-library only.

## 0.1.0-beta.1

- Initial public beta based on the internal v1.6 implementation.
- Stable script/version entry point, verified ZIP/manifest/checksum backups,
  protected source/backup/system storage, target identity and mount checks,
  safe archive validation and anchored restoration.
- Repo-local ignored backups, MIT license, documentation and synthetic macOS CI.
