# Device and firmware compatibility

## Model-independent migration

The tool supports file-level card replacement for **CrossInk-compatible XTEINK
readers**, including X3, X4, X4 Classic and X4 Pro, and other CrossInk-supported
XTEINK models that use the same mounted SD layout and pass all disk-safety checks.
The selection workflow recognizes `.crosspoint/`; it does not parse a device model
or transform firmware-specific settings. Unknown hidden reader data is preserved.

Upstream evidence, checked 2026-10-19:

- [CrossInk installation](https://crossink.dev/installation.html) lists X3, X4,
  X4 Classic and X4 Pro among its supported devices.
- [CrossInk data cache](https://crossink.dev/data-cache.html) describes the shared
  `.crosspoint` layout for persistent settings, caches, history and progress.
- [CrossInk source](https://github.com/uxjulia/CrossInk) is the firmware project;
  it is independent of this migration utility.

These are firmware/layout facts, not evidence that this utility has migrated every
listed reader. CrossPoint or downstream firmware using the same layout may qualify;
firmware versions with different layouts require separate investigation. Stock firmware,
non-XTEINK hardware and Linux/Windows hosts are outside the supported workflow.

## Evidence matrix

| Device | File-level scope | Physical migration evidence |
| --- | --- | --- |
| X3 / CrossInk | Supported | One author-reported successful X3/Mac migration with internal v1.6 |
| X4 / CrossInk | Supported | Pending |
| X4 Classic / CrossInk | Supported | Pending |
| X4 Pro / CrossInk | Supported | Pending |
| Other CrossInk-supported XTEINK model with the shared layout | In scope subject to all guards | Pending model/firmware/card/reader validation |

Synthetic tests exercise hidden-data backup/restore with X3, X4, Classic, Pro and
an invented future model label. They show that model labels do not gate byte copying;
they do not execute firmware or establish a physical migration result.

## Boundaries

Use this tool to replace a card for a reader. It does not promise cross-model or
cross-firmware settings/cache portability. It never flashes firmware and cannot
identify an XTEINK model from SD data alone. Keep the same book paths so path-based
reader state can remain associated with its books.

Use a separate SD reader with the device shut down. A reader's own USB Drive mode
has not been validated for destructive whole-disk operations and may be rejected by
the removability/identity checks. Firmware USB-transfer support alone does not make
that mode safe for this utility.

Target policy remains <=32 GiB FAT32 + MBR and >32 GiB exFAT + MBR, with explicit
filesystem overrides. That default is not a universal firmware guarantee. Targets
require one mounted FAT32/exFAT volume with readable identity and confirmed writable
removable media; no model selection bypasses these constraints.

Historical `xteink-x3-backup/`, `xteink-x3_<timestamp>` and
`xteink-x3-migrate-v1` strings remain unchanged for backup compatibility. They work
for the model-neutral workflow. Newly formatted target volumes use the neutral
`XTEINK` label; the label does not control restoration or device detection.

## Reporting a configuration

Use the issue template with tool/macOS/Python/firmware versions, reader type,
source/target raw capacities, filesystem policy and sanitized result. Never post a
backup, books, credentials or private paths. State whether the result is read-only
detection, synthetic testing or an actual completed migration. Hardware tests require
an explicitly designated disposable target card in a separate supervised session.
