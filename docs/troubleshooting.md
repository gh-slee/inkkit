# Troubleshooting and recovery

## Detection or macOS permissions

Run `python3 xteink_sd_migrate.py --diagnose`. It only queries disks and CrossPoint markers; it does not back up, eject, format or restore. The correct macOS query is `diskutil info -plist diskN` (the flag precedes the identifier). The tool also checks mounted directories under `/Volumes`, including volume names containing spaces.

Check Finder/Disk Utility and the reader connection, safely reconnect the card, and confirm the source has `.crosspoint/`. Some internal SD readers report `VirtualOrPhysical=Unknown`; read-only discovery supports this. Erasing requires additional fields, including removability, write capability and target volume UUID. If these are missing, try a different reader or investigate the read-only diskutil output. Do not weaken safeguards or treat any external USB disk as an SD card.

macOS may need Files and Folders/Removable Volumes access for Terminal or the application launching Python. A DiskManagement/DiskArbitration framework error can occur in restricted execution sessions; rerun read-only diagnostics in a normal local Terminal. Do not run the whole program with sudo as a routine workaround. Diagnostics may display private volume names/mount paths: redact them before sharing.

## Backup or restore failure

An `Unconfirmed APFS physical store` error during backup scanning means the tool
cannot resolve the host backup location safely; it is not an erase operation. It
stops before creating backup files. Current code handles the narrow internal Apple
Fabric `Unknown` case described in the [storage policy](safety.md), using APFS store
topology plus whole-disk hardware attributes. Preserve the source and existing
backups; do not remove the storage guard or assume every `Unknown` disk is physical.
Other incomplete/virtual store configurations still stop. Share only sanitized
identity flags and bus types when reporting this failure, not full disk plists.

Stop, leave the original card intact and preserve the ZIP, matching `.manifest.json` and `.zip.sha256`. They normally live in `xteink-x3-backup/` beside the script. A `.zip.partial` is not a verified backup and is removed on handled failure; abrupt process termination may leave it behind. A failure while publishing the manifest/checksum can leave an orphan ZIP: never call it verified or erase the source based on that ZIP alone.

Missing/invalid manifest or checksum mismatch: recover the paired files from a trusted copy, or make another backup from the original. Do not edit hashes to silence a failure. `shasum -a 256 -c EXAMPLE.zip.sha256` provides a separate checksum check from inside the backup directory.

Verify an existing backup without connecting a card:

```bash
python3 xteink_sd_migrate.py --verify-backup "$PWD/xteink-x3-backup/EXAMPLE.zip"
```

To preview a new restore, use `--restore BACKUP.zip --dry-run`. This still requires
the source to be removed and the empty reader observed before inserting the target.
It performs the read-only erase-policy checks, with no backup, lock, journal, copy,
format or eject operation. It cannot establish actual post-format usable space.

## Resume a new interrupted restore

New jobs create a `.restore-state.json` beside the ZIP before writing target data.
Keep this private sidecar with the ZIP and manifest. Leave the original disconnected,
connect only the interrupted replacement card, and inspect it first:

```bash
python3 xteink_sd_migrate.py --check-restore "$PWD/xteink-x3-backup/EXAMPLE.zip"
python3 xteink_sd_migrate.py --resume "$PWD/xteink-x3-backup/EXAMPLE.zip" --dry-run
python3 xteink_sd_migrate.py --resume "$PWD/xteink-x3-backup/EXAMPLE.zip"
```

The first two commands are read only. The last requires `RESUME diskN`; it never
formats. The journal must match the verified ZIP/manifest, target volume UUID,
capacity and filesystem. The target must also pass removable-media, protected-storage,
physical-mount and MBR checks. Disk numbers may change after reconnection; the volume
UUID is used to locate the job. Duplicate UUID candidates are refused.

Inspection reports counts without printing book titles or settings paths. Existing
complete files are checked and skipped. Only the journal's active partial file may
be appended, and every existing prefix byte must match the ZIP. Missing files and
directories can be created. Conflicting bytes, unrelated entries, symlinks or nested
mounts stop recovery; nothing is overwritten or deleted to repair a conflict.

After copying, the entire tree and every file hash are checked again. The journal is
removed only after successful verification and eject. An eject failure retains it
so `--resume` can verify and retry eject without rewriting complete files. The empty
private `.restore.lock` may remain; the OS releases its advisory lock on process exit.
Keep the journal and lock alongside the backup during a job; do not edit/delete them
to force another erase or run concurrent restores of the same backup.

Old interrupted jobs without a matching journal cannot be resumed automatically.
An interruption during formatting or before the first journal is saved has the
same limitation; automatic recovery covers the journaled copy/verify/eject stages.
Likewise, filesystem damage or power loss that corrupts completed bytes needs manual
investigation. Preserve the card, source and backup. A normal `--restore BACKUP.zip`
**erases the selected target** and deliberately blocks partial `.crosspoint` data;
there is no force-wipe override. Use a separate known disposable target only after
the failure is understood. A pending journal blocks starting a new erase with that
backup; do not discard recovery evidence to silence the guard.

## Storage, sync or journal permission errors

An ENOSPC error can come from the target or the local backup/journal storage. A
target write can persist only a prefix before reporting failure. Keep that file
and the journal: after resolving the underlying space problem, inspection checks
the prefix and a confirmed resume can append the rest. An existing complete file
is checked and skipped, including when a previous file-sync or checkpoint update
failed. The full usable-space preflight still applies to remaining data.

Journal creation, write, fsync or rename failures stop copying. Handled failures
remove their temporary journal file and preserve the earlier valid journal. If
rename already completed before a directory-sync failure, the new journal may be
visible; let `--check-restore` validate it. If no journal was ever created, automatic
resume remains unavailable. Preserve the original card and verified backup.

Resolve the storage/permission problem before retrying; do not edit journal fields
or backup hashes. A failed verified checkpoint prevents eject. A failed journal
cleanup after successful eject may leave a valid `verified` journal; reconnect the
same replacement and use `--resume` to verify and retry completion. Ctrl-C releases
the advisory lock, so a later process can retry. An actual power cut or damaged
filesystem may still require manual investigation.

Capacity failure before format leaves the target untouched. Failure after format can leave it empty; use a larger card. Different cards with the same marketed size can have different actual bytes. `--allow-smaller-target` permits an intentional smaller card but never skips usable-space checks.

## The XTEINK reader does not recognize the new card

Keep using the original card. Record macOS, firmware build, reader, card capacities, selected filesystem and redacted error messages. Verify the tool reported MBR and the requested filesystem. Confirm the firmware's actual FAT32/exFAT support and test the card/reader separately without risking your original data. The <=32 GiB FAT32 / >32 GiB exFAT default is a migration policy, not universal firmware support. Do not blindly reformat repeatedly or flash firmware as a troubleshooting shortcut.

## Synthetic restore smoke test

Run `XTEINK_TESTING=1 python3 -m unittest discover -s tests -v -b`. Tests build synthetic ZIPs and legacy manifests in temporary directories, restore hidden files, read back checksums, inject failures and mock every destructive command. No user backup or real disk is needed. Keep test logs local if they include private environment paths. A real hardware smoke test is separate, voluntary, destructive and must use a disposable test card.

## Model scope

X3 is not a required model. X4 and other compatible CrossInk XTEINK models use the
same file-level workflow; see [compatibility](compatibility.md). Legacy `xteink-x3`
backup names identify the historical archive format, not a device restriction.
Use an external SD reader; a running device's USB transfer mode is unverified.

## Native configuration build

- Select the mounted SD root, then confirm the actual model and CrossInk v1.6.1.
  Permission/identity/layout rejections are fail-closed. Reconnect/reopen; do not
  bypass by reformatting or changing the migration erase guard.
- Dirty drafts need Review/Apply or Discard before changing categories/reloading.
  Add network/server/profile before filling a new collection entry. Paired button
  maps and unique swipe actions may need multiple draft changes in one review.
- Existing firmware `.tmp`/`.bak`, legacy schemas or invalid saved types require
  firmware recovery/migration first. Preserve evidence and a full backup.
- After apply/restore failure, stop and review private Mac-side Backups. Complete
  snapshots require a fresh review and recheck of current tokens; legacy single-file
  restore remains bound to its recorded result hash. Preserve recovery journals
  and protected snapshots; do not erase or delete records to force a write. See
  [transaction limitations](config-architecture.md).
- Password fields always look empty. Blank keeps the old value; Clear removes it.
  New or retained plaintext requires the review checkbox on every write. It remains
  until the reader loads and successfully resaves that store; boot alone may not.
- These workflows are development features with limited owner-reported X3 acceptance. Other settings/models and the newer complete-snapshot workflow remain pending.
  See [build/use and packaging limits](macos-preview.md).
