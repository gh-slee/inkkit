# Safety model and remaining limits

The following sections describe the migration CLI; the separate configuration editor is covered below.

The original source is read only. No raw cloning or firmware changes occur. Full migration backs up and verifies before ejecting it. The source must be removed and the reader observed empty before a target is inserted. A reused disk number alone is neither proof of a new card nor a permanent source blacklist. New manifests add an optional source volume UUID inside the existing v1 format; legacy manifests remain readable. Targets with any `.crosspoint` entry or a matching sampled source checksum are blocked, even if the metadata was modified.

Read-only discovery deliberately accommodates more readers than destructive operations. Erase requires an explicitly writable, removable USB/SD whole device, a single mounted FAT32/exFAT volume with UUID, known capacity <=2 TiB, and no recognized Time Machine markers. Fixed external disks, ambiguous topology, virtual disks, unknown attributes and unreadable identities fail closed. Device reporting is not hardware attestation: a device can misreport itself as removable. The user must still physically identify the target.

The only `eraseDisk` call is in `erase_target`. It reloads and hashes the ZIP, validates the complete manifest and archive, checks raw/allocation capacity and FAT32 limits, resolves the physical backing of protected paths and compares the confirmed snapshot again immediately before invoking diskutil. Protected paths include the ZIP and manifest, program and safety module, current checkout/working directory, home and system root. APFS paths resolve through container physical stores. Unresolvable protected storage blocks erase. Paths are resolved through their actual mount and diskutil topology, including symlinks, rather than by matching `/Volumes` strings.

Some internal Apple Fabric SSDs report `VirtualOrPhysical=Unknown`. APFS storage
resolution accepts that case only when the container names the store partition and
the queried whole disk has the matching identifier, `WholeDisk=True`, `Internal=True`,
`RemovableMedia=False` and `BusProtocol=Apple Fabric`, with no contradictory virtual
or removable evidence. Every store must be confirmed. This identifies protected
host storage and checks that backups are off the source; it does not make the
internal SSD an eligible erase target or accept unknown external media generally.

Snapshots include whole-device attributes, partition UUID and attributes, mount path and `st_dev`. They reduce hotplug risk but cannot eliminate the interval between a query and a diskutil action. Some cards expose no stable hardware serial. Cloned UUIDs and a device swapped with identical reported properties cannot always be distinguished. Keep all other external storage disconnected and never swap devices during confirmation, formatting or restore. The target mount must resolve back to the selected physical disk. After format, hardware attributes, MBR, filesystem, mount identity and usable space are checked before writing. Restore checks the opened directory handle against the captured mount identity before any write.

Restore validates archives again and uses open directory descriptors with no-follow and exclusive file creation, so path symlinks cannot redirect writes and an old mount path does not become a new host destination if media disappears. Nested mounts are blocked. Interrupted restores leave the target incomplete; they do not consume or modify the backup. Backups are not deleted after success.

`--verify-backup` performs the existing full archive/manifest validation without disk
queries. `--restore ... --dry-run` shares the read-only erase-policy preflight and
does not create a backup, lock or journal, copy, format or eject. It estimates fit;
it cannot guarantee the usable space/filesystem a future format will create. A real
restore revalidates everything and requires both erase confirmations again.

New restores persist a private local `.restore-state.json` alongside the backup
before copying. It binds the ZIP and canonical manifest digest to the post-format
volume UUID, raw capacity and filesystem, and records the active file before writing.
Atomic journal updates are fsynced before corresponding target writes. A per-backup
local advisory lock serializes writing jobs; the lock inode is retained. Pending
journals block a new erase. Neither sidecar changes the legacy v1 backup schema.
Locks coordinate jobs using the same backup, not different backups or other disk
utilities. Run only one migration/restore/recovery writer at a time and keep other
disk tools closed; the CLI does not reserve physical media against other processes.

`--check-restore` and `--resume ... --dry-run` inspect without writes or eject.
Actual `--resume` is a separate no-format path with a matching journal and explicit
`RESUME diskN` confirmation. It retains target eligibility, source UUID, protected
storage, physical mount, filesystem/MBR and refreshed identity checks. The normal
erase path still refuses every `.crosspoint` target; recovery does not bypass it.
Every existing file is checked through anchored no-follow descriptors. Only the
recorded active partial file can receive an append after its entire prefix matches
the ZIP. Complete files are read and skipped, missing files are created exclusively,
and unexpected/mismatching data stops recovery without repair or overwrite. All
files/tree are verified again before eject and journal cleanup.

Journals are local recovery evidence, not signed hardware identity or a transaction
across two devices. Protect them as private data; they can contain a relative reader
filename and volume UUID. A missing journal, changed UUID, cloned UUID, damaged FAT
metadata or corrupted completed file may prevent safe automatic recovery. Only the
current partial file can be resumed; filesystem power-loss effects can exceed that
boundary. Successful preflight/recovery does not prove future card reliability.

Persistence failures stop copying before advancing to the next file. A failed
temporary journal write or rename leaves the previous journal intact; a failed
directory fsync after rename can leave the newer journal visible even though its
durability was not confirmed. Always reload it through the normal recovery flow.
Synthetic tests cover those boundaries and real temporary-file prefix writes that
raise ENOSPC. Successful retries check every file again; they do not establish
power-loss durability of any physical card or filesystem.

Resource policy: at most 200,000 files/directories, 2 TiB declared expanded data, 128 MiB manifest/ZIP central directory, expansion ratio <=10,000. Size/count/path/checksum mismatches, duplicate JSON keys, duplicate/case/Unicode aliases, traversal, symlinks/special files, encryption and split archives are rejected. Large ZIP64 backups remain supported. These conservative limits may reject legitimate unusual archives; do not disable them for an untrusted archive.

ZIP64 limits are checked against the fixed end record adjacent to its locator,
matching the record Python parses even when legacy fields contain no sentinel.
Misdirected locators, inconsistent/split metadata and unsupported extended end
records are rejected before central-directory allocation. Tool-created ZIP64 and
legacy v1 archives remain supported. Root-dot member paths are rejected before
target selection; verification must not accept a file that resolves to the root.

Source changes detected during scanning/reading abort backup. SHA-256 checks consistency, not original source health or authenticity. Protect both ZIP and manifest from tampering. Unix mode 600 does not encrypt files, and removable FAT filesystems may not enforce those permissions.

The workflow is model-independent for compatible CrossInk XTEINK readers; see
[compatibility](compatibility.md). Model-specific prompts do not change disk policy.

Migration evidence and exact revisions are recorded in the
[hardware report](hardware-validation.md#reviewed-x3-result-2026-10-22).
The published v1.0.0 is a migration CLI release, not a native app release.
Implementation scope and automated checks do not certify every physical
model/firmware/card/reader combination or guarantee power-loss safety.

## Current-card configuration editor (development)

Unlike migration's original source, a card explicitly opened in the native editor
can receive reviewed settings writes. This is a separate adapter with no erase API.
It requires a user-confirmed CrossInk v1.6.1 model profile, external removable USB/SD
media, one mounted FAT32/exFAT partition, UUID and rechecked mount/device identities.
It refuses protected/ambiguous storage, malformed/legacy input and firmware recovery
files. All original-file backups and locks stay privately on the Mac, on a separate
device. The unchanged migration erase guard still rejects source-like cards.

Every changed native Apply captures a complete six-store snapshot before its
per-file transaction, which verifies the original and reads back the replacement.
Complete restore can select any compatible older snapshot after fresh review of
all current tokens and the backup checksum; it preserves the complete current
state before writing. Legacy single-file restore still requires its recorded
current-file hash. Restoring an absent store removes that file. Each file is
replaced/read back separately: there is no atomic multi-file transaction,
external-writer exclusion or hardware/power-loss guarantee. Interrupted complete
restore retains its journal and protects both snapshots; a reviewed full restore
must resolve recovery before individual Apply continues.
Do not hotplug or run competing editors. Quit waits while busy; force quit remains
possible. Keep a full backup and use Eject. See [architecture](config-architecture.md)
for interrupted-operation evidence and [configuration usage](macos-preview.md).

Existing password material stays hidden/preserved. Plaintext fallback requires
explicit consent for every resulting/restored plaintext-containing file. Firmware
must load and successfully resave that store; boot alone may not do it. Obfuscation
is not encryption and old backups can retain credentials. All automated tests use
invented files/mock disks. Selected owner-reported X3 settings acceptance is documented separately; it does not certify every control or model.
