# Hardware acceptance and reports

The [compatibility matrix](compatibility.md#evidence-matrix) separates file-level
scope from physical evidence. Current hardware evidence is an author-reported X3/Mac
migration with the internal v1.6 predecessor. This guide and its report template add
no new hardware result. Public beta.3 and X4/other combinations remain unvalidated
until actual reports are reviewed.

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

## Review and stable release criteria

Maintainers review a report for its exact software revision, firmware, card and
reader combination. A complete physical result needs both file-level completion
and the applicable reader checks above, with omissions explicit. Record accepted
evidence in the compatibility matrix with a link, date and tool version; keep
read-only/partial results labeled separately. A successful X3 report does not
validate X4, other firmware or every capacity. Historical v1.6 evidence cannot stand
in for validation of a public candidate.

Before proposing `v0.1.0` stable:

1. Obtain reviewed physical migration and reader-state evidence for the public
   implementation on X3 and X4 if both remain within the stable hardware claim.
   Keep Classic/Pro/other untested combinations visibly pending; do not describe
   them as physically validated. Otherwise narrow the stable claim to the evidence.
2. Resolve known data-loss, incorrect-target, integrity and recovery blockers.
   Record any untested recovery scenario as a limitation; physical fault injection
   is not a release requirement. Fixes that affect prior evidence require a fresh
   review and relevant validation.
3. Verify the exact release candidate has successful macOS/Python 3.9 and 3.12 CI,
   synthetic fault coverage, CLI/version checks and publication audits. Link the
   candidate SHA and run; earlier green runs do not validate a later candidate.
4. Update compatibility, limitations, changelog and release notes to match reviewed
   evidence. Follow the [manual publication review](publishing.md#manual-prerelease-preparation)
   and obtain separate approval for the exact stable tag, SHA, notes and assets.

These are review criteria, not an automatic promotion rule. There is no release
automation. Passing CI or merging these documents alone does not make beta.3 stable.
