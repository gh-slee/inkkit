# InkKit device and firmware compatibility

## Model-independent migration

The tool supports file-level card replacement for **CrossInk-compatible XTEINK
readers**, including X3, X4, X4 Classic and X4 Pro, and other CrossInk-supported
XTEINK models that use the same mounted SD layout and pass all disk-safety checks.
The selection workflow recognizes `.crosspoint/`; it does not parse a device model
or transform firmware-specific settings. Unknown hidden reader data is preserved.

Upstream evidence, checked 2026-10-22:

- [CrossInk installation](https://crossink.dev/installation.html) lists X3, X4,
  X4 Classic and X4 Pro among its supported devices.
- [CrossInk data cache](https://crossink.dev/data-cache.html) describes the shared
  `.crosspoint` layout for persistent settings, caches, history and progress.
- [CrossInk source](https://github.com/uxjulia/CrossInk) is the firmware project;
  it is independent of this migration utility.

CrossInk also lists Seeed Studio Sticky. That non-XTEINK device is outside InkKit's
current supported workflow. These are firmware/layout facts, not evidence that
InkKit has migrated every listed reader. CrossPoint or downstream firmware using
the same layout may qualify;
firmware versions with different layouts require separate investigation. Stock firmware,
non-XTEINK hardware and Linux/Windows hosts are outside the supported workflow.

## Configuration app in development

The [native app](macos-preview.md) implements current-card editing for CrossInk
v1.6.1 on explicitly selected X3, X4, X4 Classic and X4 Pro profiles. See the
[complete generated reference](configuration-reference.md). Expected capabilities
filter controls; neither model nor firmware is auto-detected. Only removable
single-partition FAT32/exFAT cards meeting identity/host-backup guards are opened.
CrossPoint and other firmware versions retain the opaque migration workflow but
are not configuration-editor profiles. Configuration writes have synthetic tests
and limited owner-reported X3 configuration acceptance; other settings/models and the new complete-snapshot workflow remain pending. X3 migration evidence is separate.
The stable script, legacy backups, names/default directory and recovery journals
are unchanged. No signed/notarized Mac app release is available.

## Evidence matrix

| Device | File-level scope | Physical migration evidence |
| --- | --- | --- |
| X3 / CrossInk | Supported | [Reviewed 2026-10-22 report](hardware-validation.md#reviewed-x3-result-2026-10-22): 32 GB to 16 GB, FAT32/MBR; unreleased APFS-fix revision |
| X4 / CrossInk | Supported | Pending |
| X4 Classic / CrossInk | Supported | Pending |
| X4 Pro / CrossInk | Supported | Pending |
| Other CrossInk-supported XTEINK model with the shared layout | In scope subject to all guards | Pending model/firmware/card/reader validation |

Synthetic tests exercise hidden-data backup/restore with X3, X4, Classic, Pro and
an invented future model label. They show that model labels do not gate byte copying;
they do not execute firmware or establish a physical migration result.

## Initial stable evidence scope

The v1.0.0 readiness plan starts with [X3 acceptance](hardware-validation.md#x3-first-v100-validation).
The physical evidence claim for the initial stable release will cover only a reviewed
X3 configuration. X4, Classic, Pro and other shared-layout readers remain in the
implementation scope, with physical results pending. No model filter is added.
The [reviewed X3 report](hardware-validation.md#reviewed-x3-result-2026-10-22)
provides migration and owner-confirmed reader evidence for the recorded unreleased
revision. It does not validate the beta.3 tag, a later runtime change, or an exact
firmware build that was not recorded. X4 and other models' physical reports are not
required for v1.0.0; their matrix entries remain pending until reviewed evidence exists.

## V1 compatibility commitment

The following compatibility commitment defines v1.0.0 and its v1.x updates.
Publication of the stable tag and release requires separate approval and exact
candidate checks; a source version change does not publish a release.

| Interface | V1 commitment |
| --- | --- |
| Entry point and dependencies | Keep `xteink_sd_migrate.py`, startup/`--version` reporting and a standard-library-only CLI |
| Existing backups | Continue reading valid legacy `xteink-x3-migrate-v1` ZIP/manifest pairs, including internal v1.6 backups; retain the checksum sidecar for independent checks |
| Backup placement and names | Keep the default `xteink-x3-backup/` beside the script and historical timestamped names; do not move, rename, rewrite or delete existing backups during an upgrade |
| CLI | Keep documented flags and meanings, including read-only verify/preflight, destructive new restore and no-format journal-bound resume; document any compatible additions |
| Exit status | Keep 0 success, 1 operational failure, 2 invalid CLI arguments and 130 interruption |
| Reader data | Preserve opaque file bytes and paths subject to the documented macOS-service exclusions; no cross-model/firmware settings conversion or flashing |
| Host requirements | Document supported macOS/Python requirements per release; the current baseline is macOS with `diskutil` and Python 3.9+, tested in CI on macOS/Python 3.9 and 3.12, not every macOS/Python combination |

Safety fixes may reject malformed archives, ambiguous devices or unsafe layouts
that an older version accepted; record such tightening in the changelog. V1 backup
compatibility does not promise acceptance of corrupt or unsupported inputs. Changes
that remove documented CLI behavior, legacy backup reading or the supported runtime
baseline require a new major release, apart from documented safety restrictions.

Recovery journals are private job state, not the portable backup format. Keep the
ZIP, manifest, sidecars and exact tool revision together until a job finishes; do
not upgrade mid-job. A future journal change must be versioned and either supported
explicitly or rejected without erasing/rewriting the target. Never delete a pending
journal to permit a new erase. No automatic conversion of private jobs is promised.

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

Use the [hardware report template](https://github.com/gh-slee/inkkit/issues/new?template=hardware_report.md)
and [acceptance criteria](hardware-validation.md) for successful or partial results;
use the bug template for failures. Include tool/macOS/Python/firmware versions,
reader type, source/target raw capacities, filesystem policy and sanitized result.
Never post a backup, books, credentials or private paths. Record read-only detection,
synthetic testing, completed migration and device-side checks separately. Hardware
tests require an explicitly designated disposable target card in a separate
supervised session. A report changes this matrix only after maintainer review;
pending entries stay pending until supported by actual evidence.
