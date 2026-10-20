# XTEINK SD Migrator

Verified file-level microSD backup and migration for **CrossInk/CrossPoint on the XTEINK X3, on macOS**. Includes hidden settings, books, fonts, bookmarks and reading progress. Python 3.9+; standard library only; no installation or third-party dependencies.

**Version: 0.1.0-beta.1.** Based on an internal v1.6 tool tested by the project author with **one successful X3/Mac migration**. The public beta's additional safeguards have synthetic tests, not additional hardware validation. Other models, firmware versions and reader configurations are **unverified**. Not affiliated with XTEINK or CrossPoint.

This is a file-level tool, not a raw clone: it does not copy boot sectors, partition geometry, unused sectors or firmware. SD metadata cannot conclusively distinguish X3 from X4.

## Quick start

Clone or download this repository. Open Terminal in the checkout:

```bash
python3 xteink_sd_migrate.py --version
python3 xteink_sd_migrate.py --diagnose
python3 xteink_sd_migrate.py --backup-only
python3 xteink_sd_migrate.py
```

Shut down the reader before removing its card. Insert only the source card when prompted. The tool creates and reads back a ZIP before ejecting the source. Remove the source, confirm the reader is empty, then insert a different target card. Disk numbers may be reused by the same reader.

**The entire confirmed target disk is permanently erased, including every partition.** Check the displayed device, size, bus and mount carefully. The tool asks for both `ERASE diskN` and `WIPE TARGET`. Cancel with `q` at selection or Ctrl-C before formatting. Once formatting starts, cancellation cannot undo deletion. Keep the original card disconnected and intact until you have tested the new card in the X3.

For this conservative beta, a target must have exactly one **mounted FAT32/exFAT volume**, a readable volume UUID, confirmed writable removable USB/SD media and a capacity no larger than 2 TiB. Fixed external HDDs/SSDs, internal non-removable disks, virtual disks, APFS, Time Machine and unknown/unmounted or multi-partition devices are blocked. Some valid readers may be rejected. Do not bypass identity checks or blindly format a rejected device; see [troubleshooting](docs/troubleshooting.md).

## Backups stay local

New backups go to **`xteink-x3-backup/` beside `xteink_sd_migrate.py`**, independent of the Terminal's current directory. Keep all three timestamped files:

| File | Purpose |
| --- | --- |
| `xteink-x3_YYYY-MM-DD_HH-MM-SS-microseconds.zip` | Books, hidden configuration and reader data |
| Same basename `.manifest.json` | Per-file relative paths, sizes, timestamps, SHA-256 and source metadata; required for restore |
| `.zip.sha256` | Independent ZIP checksum, e.g. `shasum -a 256 -c EXAMPLE.zip.sha256` |

ZIP + matching manifest are required to restore. The checksum sidecar should be retained but is not required by the restore loader. The legacy `xteink-x3-migrate-v1` format and backups from internal v1.6 remain supported. Old backups can stay in their existing locations.

Backups can contain Wi-Fi/OPDS credentials and copyrighted books. **They are not encrypted.** Files are created with private permissions; FAT/exFAT may not enforce Unix permissions. Use encrypted local storage when appropriate. The repo's ignore rules exclude the backup folder, ZIPs, manifests and checksum sidecars. Never force-add backups or attach them to issues. Ignore rules do not protect files already tracked by Git: check `git ls-files` before pushing.

## Filesystem and capacity policy

The default `--filesystem auto` uses the **target's actual raw capacity**:

- At most 32 GiB: FAT32 + MBR.
- Greater than 32 GiB: exFAT + MBR.

This is the project's policy, not a guarantee of support by every firmware build. FAT32 files must be at most 4 GiB minus one byte. exFAT avoids that limit, but firmware/card/reader compatibility varies. The tool verifies MBR and the actual filesystem after formatting; GPT is not accepted for restore.

```bash
python3 xteink_sd_migrate.py --filesystem exfat
python3 xteink_sd_migrate.py --filesystem fat32
python3 xteink_sd_migrate.py --filesystem source
python3 xteink_sd_migrate.py --allow-smaller-target
python3 xteink_sd_migrate.py --restore "$PWD/xteink-x3-backup/EXAMPLE.zip"
python3 xteink_sd_migrate.py --restore "$HOME/Downloads/xteink-x3-backup/EXAMPLE.zip"
```

By default the target must be at least as large as the source in actual bytes. `--allow-smaller-target` explicitly overrides that raw-capacity rule; data-fit checks still apply. Allocation overhead and a reserve are estimated before erase. Actual usable space is checked again after formatting, before copying; a failure at that stage leaves an erased target and preserves the original and backup.

## Verification and exclusions

ZIP creation, read-back, archive hashing, restore and target verification show bytes, file counts and rates. Formatting/eject show elapsed time, not invented percentages. Every restored file is read back and SHA-256 checked; directory and file trees must match. Checksums show consistency with the captured source bytes, not that the source was originally healthy or that hardware will remain reliable. SHA-256 is not authentication against someone who can alter both ZIP and manifest.

Only these macOS service entries are excluded:

- Root directories/entries: `.Trashes`, `.Spotlight-V100`, `.fseventsd`, `.TemporaryItems`, `.DocumentRevisions-V100`, `.apdisk`, `.PKInstallSandboxManager-SystemSoftware`.
- Anywhere: `.DS_Store`, `.VolumeIcon.icns`, `.com.apple.timemachine.donotpresent` and names starting `._`.

Other hidden directories are preserved, including `.crosspoint/`, `.fonts/` and unfamiliar reader directories. Links and special files are rejected. Archives with unsafe paths, duplicate/case-colliding names, inconsistent manifests, special entries, excessive declared expansion, or excessive entry/metadata counts are rejected. Limits are 200,000 entries, 2 TiB uncompressed data and 128 MiB manifest/central directory.

See [safety and limitations](docs/safety.md), [recovery and troubleshooting](docs/troubleshooting.md) and [contributing](CONTRIBUTING.md). Exit codes: 0 success; 1 operational error; 2 invalid CLI options; 130 interruption. A failed restore may leave an incomplete target: preserve your original and backup and restart the restore workflow only after resolving the cause.

## Development

```bash
XTEINK_TESTING=1 python3 -m unittest discover -s tests -v -b
python3 -m compileall -q xteink_sd_migrate.py disk_safety.py tests
```

Tests use temporary synthetic data and mocked disk commands. `XTEINK_TESTING=1` blocks the disk mutation runner. CI runs on macOS with that guard set, with Python 3.9 and 3.12. No real SD card is formatted in tests. Real destructive testing requires an explicitly volunteered disposable card and a separate human-supervised session.

MIT licensed. Additional carefully documented hardware configurations are welcome; remove personal paths, volume names, book titles and credentials from reports.
