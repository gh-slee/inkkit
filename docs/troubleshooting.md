# Troubleshooting and recovery

## Detection or macOS permissions

Run `python3 xteink_sd_migrate.py --diagnose`. It only queries disks and CrossPoint markers; it does not back up, eject, format or restore. The correct macOS query is `diskutil info -plist diskN` (the flag precedes the identifier). The tool also checks mounted directories under `/Volumes`, including volume names containing spaces.

Check Finder/Disk Utility and the reader connection, safely reconnect the card, and confirm the source has `.crosspoint/`. Some internal SD readers report `VirtualOrPhysical=Unknown`; read-only discovery supports this. Erasing requires additional fields, including removability, write capability and target volume UUID. If these are missing, try a different reader or investigate the read-only diskutil output. Do not weaken safeguards or treat any external USB disk as an SD card.

macOS may need Files and Folders/Removable Volumes access for Terminal or the application launching Python. A DiskManagement/DiskArbitration framework error can occur in restricted execution sessions; rerun read-only diagnostics in a normal local Terminal. Do not run the whole program with sudo as a routine workaround. Diagnostics may display private volume names/mount paths: redact them before sharing.

## Backup or restore failure

Stop, leave the original card intact and preserve the ZIP, matching `.manifest.json` and `.zip.sha256`. They normally live in `xteink-x3-backup/` beside the script. A `.zip.partial` is not a verified backup and is removed on handled failure; abrupt process termination may leave it behind. A failure while publishing the manifest/checksum can leave an orphan ZIP: never call it verified or erase the source based on that ZIP alone.

Missing/invalid manifest or checksum mismatch: recover the paired files from a trusted copy, or make another backup from the original. Do not edit hashes to silence a failure. `shasum -a 256 -c EXAMPLE.zip.sha256` provides a separate checksum check from inside the backup directory.

An interrupted restore may have created some target files. Do not merge a second extraction into it. Once the cause is understood, rerun the full verified restore workflow on a suitable target:

```bash
python3 xteink_sd_migrate.py --restore "$PWD/xteink-x3-backup/EXAMPLE.zip"
```

This command **erases the selected target again**. A target with partial `.crosspoint` data is deliberately blocked. Preserve it for inspection; use a separate known disposable card or inspect/recover manually. There is no force-wipe override for valuable reader data.

Capacity failure before format leaves the target untouched. Failure after format can leave it empty; use a larger card. Different cards with the same marketed size can have different actual bytes. `--allow-smaller-target` permits an intentional smaller card but never skips usable-space checks.

## X3 does not recognize the new card

Keep using the original card. Record macOS, firmware build, reader, card capacities, selected filesystem and redacted error messages. Verify the tool reported MBR and the requested filesystem. Confirm the firmware's actual FAT32/exFAT support and test the card/reader separately without risking your original data. The <=32 GiB FAT32 / >32 GiB exFAT default is a migration policy, not universal firmware support. Do not blindly reformat repeatedly or flash firmware as a troubleshooting shortcut.

## Synthetic restore smoke test

Run `XTEINK_TESTING=1 python3 -m unittest discover -s tests -v -b`. Tests build synthetic ZIPs and legacy manifests in temporary directories, restore hidden files, read back checksums, inject failures and mock every destructive command. No user backup or real disk is needed. Keep test logs local if they include private environment paths. A real hardware smoke test is separate, voluntary, destructive and must use a disposable test card.
