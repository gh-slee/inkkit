# Hardware acceptance and reports

The [compatibility matrix](compatibility.md#evidence-matrix) separates file-level
scope from physical evidence. The [reviewed X3 result](#reviewed-x3-result-2026-10-22)
records a maintainer-run backup and restore on an unreleased APFS-fix revision,
followed by owner-confirmed reader acceptance. It supplements the historical
internal v1.6 report. The beta.3 tag predates this fix and was not the tested
revision. X4 and other model combinations remain physically unvalidated.

## Scope and consent

Reports can describe an existing migration or read-only observation; a full migration
is not required to contribute. Do not run a destructive workflow merely to fill in
this checklist. Any voluntary physical migration is a separate supervised session,
with an explicitly designated disposable target, the original card retained, and a
verified backup on separate protected storage. Read the [safety guide](safety.md)
first. Normal migration/restore erases the selected target after confirmations.

Development agents and CI must continue using temporary synthetic data and mocked
disks with `XTEINK_TESTING=1`. This document does not authorize real-card operations.
Do not induce power loss, unplug a mounted card, exhaust physical media or inject
write errors to test recovery. Recovery fault coverage belongs in synthetic tests.

## Record the configuration

Use the [hardware report template](https://github.com/gh-slee/xteink-sd-migrator/issues/new?template=hardware_report.md)
for working or partial configurations and the bug template for failures. Record:

- Date, tool `--version`, exact tag or commit, and whether source was modified.
- XTEINK model, firmware project and exact firmware version/build. Record whether
  the firmware stayed the same between the original and replacement cards.
- macOS/Python versions and Mac architecture; SD reader make/model and connection
  type. Distinguish a separate card reader from the device's USB Drive mode.
- Source and target marketed sizes and raw capacities in bytes when available;
  source filesystem, requested policy (`auto`, `fat32`, `exfat` or `source`), actual
  target filesystem/partition scheme, and any smaller-target override.
- Evidence type and workflow used: read-only observation, synthetic test, full
  migration, restore from backup, or journal-bound resume. Distinguish final success
  from a stopped attempt. Do not infer a value that was not observed.

Every result must be **pass**, **fail**, **not run**, or **not applicable** with a
reason. A skipped check is not a pass. Give a sanitized description of errors and
the last completed stage rather than an unedited terminal transcript.

## Acceptance checklist

| Stage | Evidence needed for a pass | What it establishes |
| --- | --- | --- |
| Backup | Backup creation/verification completed; required ZIP and matching manifest retained privately | Captured files passed the tool's integrity checks |
| Read-only preflight, if used | Record the exact mode and whether target eligibility/capacity checks passed | The inspected configuration passed preflight at that time |
| Target restore | Copy, full tree/hash readback and safe eject completed without error; actual format recorded | File-level restoration completed for this card/reader combination |
| Reader startup | Reader starts from the replacement card with the expected firmware | The firmware can use that card sufficiently to start |
| Books and paths | Representative books at unchanged relative paths open and display correctly | Reader access beyond the filesystem copy |
| Fonts and settings | Relevant custom fonts and previously recorded settings behave as expected | Checked configuration survives in the reader |
| State and persistence | Locally recorded bookmark/progress/history checks agree; after a normal shutdown/restart, the checked state is still usable | Checked reader state survives replacement and restart |
| Original and backup | Original retained and untouched by the tool; backup remains available and verifies | Recovery sources remain available |
| Resume, only if actually used | Matching journal accepted, resumed readback/eject completed, then device checks above passed | Recovery succeeded for that observed interruption/configuration |

Use invented test content where possible. If a personal migration was already
performed, compare titles, settings and progress locally; publish only outcome
summaries. A missing font, unused bookmark feature or unchecked history must be
marked not applicable or not run with its reason. Do not invent results to complete
the table. File hashes do not prove that firmware settings work in the reader.

`--verify-backup` validates the local archive/manifest without inspecting a disk.
`--restore BACKUP.zip --dry-run` checks a prospective restore without formatting or
copying. `--check-restore` and `--resume BACKUP.zip --dry-run` inspect an existing
matching recovery job; they are not a new-restore preflight. See
[troubleshooting](troubleshooting.md) for their prerequisites. Passing any of these
modes alone is not a completed physical migration.

Do not deliberately interrupt a physical job to obtain resume evidence. If an
ordinary job was interrupted, follow the recovery guide; preserve its private
journal, archive and original card. If no recovery was needed, mark resume not run.
Never weaken a guard, fabricate a journal or repeat a destructive restore merely
to obtain a passing report.

## Privacy before submitting

Submit a text summary only. Do not attach ZIPs, manifests, checksums, recovery
journals/locks, directory listings, raw `diskutil` output, complete logs or screenshots.
They can reveal private paths, volume names, book titles, serial numbers, UUIDs,
Wi-Fi/OPDS/sync settings or credentials. Report format/capacity outcomes as sanitized
values; do not include hardware serials or disk/volume UUIDs. Use placeholders for
names and paths and keep detailed evidence locally. If a failure cannot be explained
without sensitive data, consult [SECURITY.md](../SECURITY.md) before posting.

## X3-first v1.0.0 validation

The initial stable hardware evidence target is **X3**, using the same reader and
firmware before and after card replacement. X4, Classic, Pro and other compatible
models remain within the model-independent implementation scope, with physical
validation pending. **Only X3 full physical acceptance is required for v1.0.0.**
X4 and other models' reports are welcome but do not block that release; no additional
device purchase or model-specific code gate is required. The result below is scoped
to its recorded configuration, not every supported device or a future candidate.

### Prepare and record

Record the exact source revision as well as `--version`: development main may still
report the last beta version while containing unreleased fixes. The chosen revision
must include the ZIP64 and root-dot safety fixes and have successful CI. The published
beta.3 tag predates those fixes and is not the validation candidate for this plan.
Keep all runtime helpers from the same checkout/source export. Do not upgrade source
files or firmware midway through a migration or recovery job.

Before any physical session, record firmware name/build, macOS/Python, card reader,
source/target capacities and target contents/disposability. If no separate expendable
target exists, stop at preparation; the original is never the target. Privately note
representative books at their existing paths, fonts/settings, bookmarks/progress and
history that can be checked after replacement. Unknown values remain unknown.

### Observe in stages

1. **Read-only discovery:** in a separately arranged physical session, identify the
   original through a separate card reader with the X3 shut down. `--diagnose` does
   not write/eject, but its private output must stay local. Stop on ambiguous media.
2. **Backup:** if authorized for that session, `--backup-only` creates local private
   backups and ejects the original. Confirm full verification, retain ZIP/manifest/
   checksum and an off-device copy, then remove and preserve the original card.
3. **Archive-only check:** `--verify-backup BACKUP.zip` checks the paired ZIP/manifest
   with no disk query or write. Do not submit the files or their contents publicly.
4. **Replacement preflight:** `--restore BACKUP.zip --dry-run` observes the empty
   reader before the replacement is inserted and checks the target without erasing,
   copying or ejecting. It does not guarantee post-format space or firmware support.
5. **Physical migration:** proceed only in a separate authorized session with an
   explicitly identified expendable replacement. Follow the normal restore workflow
   and both erase confirmations. Record full tree/hash verification and safe eject;
   stop on failure and preserve recovery evidence. Never bypass a guard.
6. **X3 checks:** insert the replacement with the reader shut down, then verify
   startup, representative books, applicable fonts/settings and saved reader state.
   Use a normal shutdown/restart and check the state again. Keep the original until
   all applicable checks pass. A CLI success alone does not pass this stage.
7. **Report:** fill the hardware template using sanitized outcomes only. Record any
   skipped features or failed stage. Mark resume not run unless an ordinary job
   actually needed it; never create a physical interruption for this checklist.

One complete report establishes only its X3/firmware/reader/card/filesystem
combination. If it uses FAT32, exFAT remains physically unverified, and vice versa.
Use additional voluntary reports to expand evidence; do not generalize from a
single card to every capacity or Mac. A source/target size or filesystem that has
not been observed must not be recorded as a pass.

If the replacement is physically smaller, default preflight must refuse it even if
the files appear to fit. An intentional smaller-target session must record that
choice and use `--restore BACKUP.zip --dry-run --allow-smaller-target` for its
read-only preflight. A later separately authorized restore needs the same explicit
override; preflight does not authorize it. The override relaxes only raw capacity,
not source protection, allocation overhead, FAT32 limits or post-format usable-space
checks. Do not swap card roles just to pass a guard or erase a needed backup card.

## Reviewed X3 result (2026-10-22)

This sanitized report was reviewed from the maintainer's Terminal output and their
subsequent reader-use confirmation. The development agent did not access private
archives or operate the physical cards. Automated tests and CI remain synthetic.

| Configuration | Observed value or limitation |
| --- | --- |
| Tool | `0.1.0-beta.3` banner; exact tested revision `505c1c5a9d2d421a1ca2bac9789a4c1dd1309769` (unreleased APFS fix, not the beta.3 tag) |
| Device / firmware | XTEINK X3 / CrossInk; owner reported latest, exact installed firmware build not recorded |
| Host / card reader | macOS, Python 3, separate USB SD reader; exact OS/Python versions and reader make/model not recorded |
| Cards | Marketed 32 GB source (29.7 GiB reported) to expendable 16 GB target (14.6 GiB reported); rounded sizes, not exact byte capacities |
| Filesystem / options | FAT32 source; `auto` selected FAT32/MBR target; explicit `--allow-smaller-target` |
| Backup | Backup-only creation and complete ZIP/file verification passed; 227 files, 37 directories, 148.4 MiB; original safely ejected |
| Target preflight | Read-only preflight passed identity, source/protected-storage, capacity and filesystem checks |
| Restore / post-format checks | Format and restore passed; 14.5 GiB available versus 425.0 MiB estimated including overhead/reserve |
| Target readback / eject | 227 SHA-256 matches, 37 directories verified; `MIGRATION SUCCESSFUL` and safe eject completed |
| Reader acceptance | Owner replied fully working to the startup, books, applicable fonts/settings, saved state and normal restart checklist; aggregate confirmation, no separate per-item logs or direct agent observation |
| Not exercised / not recorded | exFAT, X4/other models, real-card interruption/resume; independent off-device backup copy not confirmed |

An initial backup attempt stopped before archive creation because the host's APFS
physical store reported an unknown label. The tested fix accepts only the narrowly
confirmed internal Apple Fabric store; target eligibility remains unchanged. An
earlier target preflight rejected source-like contents without writing. After the
owner separately prepared the explicitly expendable replacement, normal guarded
preflight and restore completed with both erase confirmations. No guard was removed.

The hardware-tested revision has 166 passing local synthetic tests; exact-candidate
macOS/Python 3.9 and 3.12 CI is still required before release. This report is evidence
for the recorded configuration, not firmware certification, coverage of all reader
features, or proof that a later SHA was physically tested. If subsequent edits only
change documentation/version, compare runtime sources with the tested revision and
retain both SHAs. The v1.0.0 preparation changes only the version constant and
module description in runtime sources; it does not physically retest a new SHA.
Runtime behavior changes require relevant renewed validation.

## Review and stable release criteria

Maintainers review a report for its exact software revision, firmware, card and
reader combination. A complete physical result needs both file-level completion
and the applicable reader checks above, with omissions explicit. Record accepted
evidence in the compatibility matrix with a link, date and tool version; keep
read-only/partial results labeled separately. A successful X3 report does not
validate X4, other firmware or every capacity. Historical v1.6 evidence cannot stand
in for validation of a public candidate.

Before proposing `v1.0.0` stable:

1. Obtain reviewed physical migration and reader-state evidence for the public
   implementation on X3, following the plan above. Limit the initial stable physical
   evidence claim to the reviewed configuration. X4, Classic, Pro and other untested
   combinations stay pending; implementation support is not physical validation.
2. Resolve known data-loss, incorrect-target, integrity and recovery blockers.
   Record any untested recovery scenario as a limitation; physical fault injection
   is not a release requirement. Fixes that affect prior evidence require a fresh
   review and relevant validation.
3. Verify the exact release candidate has successful macOS/Python 3.9 and 3.12 CI,
   synthetic fault coverage, CLI/version checks and publication audits. Link the
   candidate SHA and run; earlier green runs do not validate a later candidate.
4. Review the [v1 compatibility commitment](compatibility.md#v1-compatibility-commitment),
   then update compatibility, limitations, changelog and release notes to match
   evidence. Follow the [stable release review](publishing.md#manual-stable-release-preparation)
   and obtain separate approval for the exact stable tag, SHA, notes and assets.

These are review criteria, not an automatic promotion rule. There is no release
automation. Passing CI or merging these documents alone does not make beta.3 stable.
