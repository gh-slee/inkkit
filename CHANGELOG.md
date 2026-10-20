# Changelog

## 0.1.0-beta.3 (unreleased)

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
  No new hardware validation or release publication.

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
