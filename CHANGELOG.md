# Changelog

## Unreleased

- Resolve APFS backing storage on internal non-removable Apple Fabric whole disks
  when macOS reports an unknown physical label. Require matching APFS store and
  hardware evidence; keep ambiguous/virtual storage and unsafe targets blocked.
  Add synthetic backup/erase-protection regressions and clarify storage-error text.
- Prepare an X3-first v1.0.0 acceptance plan, a v1 compatibility commitment and
  manual stable-release gates. Keep X4/other shared-layout models in implementation
  scope with physical evidence pending; no new hardware result or release.
- Apply ZIP directory resource limits to the ZIP64 end record used by Python,
  including archives without legacy sentinel values. Reject inconsistent or
  misdirected ZIP64 metadata before central-directory parsing.
- Reject root-dot member paths during manifest validation, before disk queries or
  erase. Preserve ordinary ZIP, tool-created ZIP64 and legacy v1 backup support.
- Add synthetic regressions for resource limits, malformed ZIP64 metadata,
  maximum-length ZIP comments and pre-erase path rejection. No real-card testing.

## [0.1.0-beta.3](https://github.com/gh-slee/xteink-sd-migrator/releases/tag/v0.1.0-beta.3) — 2026-10-20

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
