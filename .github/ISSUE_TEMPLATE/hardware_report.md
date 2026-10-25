---
name: Migration hardware report
about: Share a working or partial card migration using sanitized text only
---

Read the [acceptance criteria](https://github.com/gh-slee/inkkit/blob/main/docs/hardware-validation.md).
Report observations you already have. Do not erase a card or interrupt a physical
job to complete this form. Use the bug report template for failures.

Do not attach backups, manifests, checksums, recovery sidecars, raw disk information,
directory listings, complete logs or screenshots. Omit private paths, volume names,
book titles, serial numbers, disk/volume UUIDs and all credentials/settings values.

## Software and hardware

- Observation date:
- Tool version (`--version`) and exact tag/commit:
- Source snapshot stayed unchanged during the job (yes/no/unknown):
- Any local source changes (yes/no; describe without private data):
- macOS version, Mac architecture and Python version:
- XTEINK model:
- Firmware project and exact version/build:
- Firmware unchanged between cards (yes/no/unknown):
- SD reader make/model and connection (separate USB reader, built-in, or device USB Drive mode):
- Source marketed capacity / raw bytes / filesystem:
- Target marketed capacity / raw bytes:
- Requested filesystem policy / actual target filesystem and partition scheme:
- Smaller-target override used (yes/no):

## Evidence and workflow

- Evidence type (read-only observation, synthetic test, or physical migration):
- Workflow/mode used (omit private arguments/paths):
- Final outcome (completed, stopped, or read-only only):
- Is the original card retained and the verified backup available? (yes/no/not run):

For each row replace **not run** with **pass**, **fail**, or **not applicable** only
when supported by observations. Explain omissions. A read-only pass is not a physical
migration. Keep comparisons of private books/settings/progress local.

| Check | Result | Sanitized observation or reason |
| --- | --- | --- |
| Backup creation and full verification | not run | |
| Read-only preflight (state mode used) | not run | |
| Restore, full tree/hash readback and safe eject | not run | |
| Reader starts from replacement | not run | |
| Representative books open at unchanged paths | not run | |
| Applicable custom fonts and settings | not run | |
| Applicable bookmarks, progress and history | not run | |
| Checked reader state after normal shutdown/restart | not run | |
| Original retained and backup still verifies | not run | |
| Journal-bound resume, only if actually used | not run | |

## Limits and context

- Unchecked features or configuration differences:
- Sanitized warnings or unexpected behavior:
- If an ordinary job was interrupted: stage and recovery outcome, without raw journal/log data:

This report covers only the configuration and revision above. It does not certify
other devices or replace maintainer review of the compatibility matrix.
The initial stable evidence target is X3; reports for X4/other compatible readers
remain welcome. Never infer a second model or filesystem result from this report.
