# Safety model and remaining limits

The original source is read only. No raw cloning or firmware changes occur. Full migration backs up and verifies before ejecting it. The source must be removed and the reader observed empty before a target is inserted. A reused disk number alone is neither proof of a new card nor a permanent source blacklist. New manifests add an optional source volume UUID inside the existing v1 format; legacy manifests remain readable. Targets with any `.crosspoint` entry or a matching sampled source checksum are blocked, even if the metadata was modified.

Read-only discovery deliberately accommodates more readers than destructive operations. Erase requires an explicitly writable, removable USB/SD whole device, a single mounted FAT32/exFAT volume with UUID, known capacity <=2 TiB, and no recognized Time Machine markers. Fixed external disks, ambiguous topology, virtual disks, unknown attributes and unreadable identities fail closed. Device reporting is not hardware attestation: a device can misreport itself as removable. The user must still physically identify the target.

The only `eraseDisk` call is in `erase_target`. It reloads and hashes the ZIP, validates the complete manifest and archive, checks raw/allocation capacity and FAT32 limits, resolves the physical backing of protected paths and compares the confirmed snapshot again immediately before invoking diskutil. Protected paths include the ZIP and manifest, program and safety module, current checkout/working directory, home and system root. APFS paths resolve through container physical stores. Unresolvable protected storage blocks erase. Paths are resolved through their actual mount and diskutil topology, including symlinks, rather than by matching `/Volumes` strings.

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

Resource policy: at most 200,000 files/directories, 2 TiB declared expanded data, 128 MiB manifest/ZIP central directory, expansion ratio <=10,000. Size/count/path/checksum mismatches, duplicate JSON keys, duplicate/case/Unicode aliases, traversal, symlinks/special files, encryption and split archives are rejected. Large ZIP64 backups remain supported. These conservative limits may reject legitimate unusual archives; do not disable them for an untrusted archive.

Source changes detected during scanning/reading abort backup. SHA-256 checks consistency, not original source health or authenticity. Protect both ZIP and manifest from tampering. Unix mode 600 does not encrypt files, and removable FAT filesystems may not enforce those permissions.

The workflow is model-independent for compatible CrossInk XTEINK readers; see
[compatibility](compatibility.md). Model-specific prompts do not change disk policy.

Current evidence: one successful author migration with the internal v1.6 tool; synthetic/macOS CI tests for this public beta. No additional real-card formatting occurred during this refactor. Other physical model/firmware/capacity/card/reader combinations are unverified. This is experimental software, not a production safety certification.
