#!/usr/bin/env python3
"""XTEINK X3 / CrossInk microSD file-level migration for macOS.

Creates and verifies a timestamped ZIP before ejecting the source card,
then formats a confirmed external target card as MBR/FAT32 or MBR/exFAT, restores all
non-macOS service files, and verifies each restored file with SHA-256.
No third-party packages required. Python 3.9+.
Public beta based on the internal v1.6 implementation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import plistlib
import re
import shutil
import stat
import struct
import subprocess
import sys
import time
import tempfile
import zipfile
import unicodedata

import disk_safety
from pathlib import Path, PurePosixPath

__version__ = "0.1.0-beta.1"
BACKUP_DIR = Path(__file__).resolve().parent / "xteink-x3-backup"
MAX_ENTRIES = 200_000
MAX_BACKUP_BYTES = 2 * 1024**4
MAX_MANIFEST_BYTES = 128 * 1024**2
CHUNK = 2 * 1024 * 1024
# 32 GiB boundary covers cards marketed as "32 GB" despite manufacturer capacity variation.
FAT32_MAX_AUTO_BYTES = 32 * 1024**3
APPLE_DIRS = {
    ".Trashes", ".Spotlight-V100", ".fseventsd", ".TemporaryItems",
    ".DocumentRevisions-V100", ".apdisk", ".PKInstallSandboxManager-SystemSoftware",
}
APPLE_FILES = {".DS_Store", ".VolumeIcon.icns", ".com.apple.timemachine.donotpresent"}
X3_FILES = (
    ".crosspoint/crossink-settings.json", ".crosspoint/settings.json",
    ".crosspoint/state.json", ".crosspoint/global_stats.bin",
    ".crosspoint/wifi.json", ".crosspoint/opds.json",
)


class MigrationError(Exception):
    pass


class Progress:
    """Byte-based progress (not fake file-count percentages). Supports redirected output."""

    def __init__(self, label: str, total_bytes: int, total_files: int = 0):
        self.label = label
        self.total = max(0, int(total_bytes))
        self.total_files = max(0, int(total_files))
        self.bytes = 0
        self.files = 0
        self.started = time.monotonic()
        self.last_draw = 0.0
        self.last_bucket = -1
        self.tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
        self.draw(force=True)

    def advance(self, size: int = 0, files: int = 0):
        self.bytes += size
        self.files += files
        self.draw()

    def draw(self, force=False):
        now = time.monotonic()
        elapsed = max(now - self.started, 0.001)
        pct = min(100, int(100 * min(self.bytes, self.total) / self.total)) if self.total else 100
        bucket = pct // 10
        if not force:
            if self.tty and now - self.last_draw < 0.12:
                return
            if not self.tty and bucket == self.last_bucket and now - self.last_draw < 15:
                return
        self.last_draw = now
        self.last_bucket = bucket
        rate = self.bytes / elapsed
        count = f" | {self.files:,}/{self.total_files:,} files" if self.total_files else ""
        if self.tty:
            bar_width = 24
            filled = (bar_width * pct) // 100
            bar = "#" * filled + "-" * (bar_width - filled)
            line = (f"{self.label}: [{bar}] {pct:3d}% "
                    f"({human(self.bytes)}/{human(self.total)})"
                    f"{count} | {human(rate)}/s")
            print("\r\033[2K" + line, end="", flush=True)
        else:
            print(f"{self.label}: {pct:3d}% "
                  f"({human(self.bytes)}/{human(self.total)})"
                  f"{count} | {human(rate)}/s", flush=True)

    def finish(self):
        if self.bytes != self.total or (self.total_files and self.files != self.total_files):
            if self.tty:
                print(flush=True)
            raise MigrationError(f"{self.label}: expected {self.total} bytes; processed {self.bytes}.")
        self.draw(force=True)
        if self.tty:
            print(flush=True)


def invoke_status(label: str, *cmd: str):
    """Show elapsed-time spinner for diskutil operations with no percent API."""
    if os.environ.get("XTEINK_TESTING") == "1":
        raise MigrationError("Disk mutations are disabled in the test environment.")
    tty = bool(getattr(sys.stdout, 'isatty', lambda: False)())
    frames = '|/-\\'
    started = time.monotonic()
    say(f"{label} (diskutil does not report a trustworthy percent)...")
    try:
        # Temporary file avoids pipe deadlocks while diskutil runs.
        with tempfile.TemporaryFile(mode='w+b') as log:
            proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
            tick = 0
            while proc.poll() is None:
                elapsed = int(time.monotonic() - started)
                if tty:
                    print(f"\r\033[2K  {frames[tick % len(frames)]} {label}: {elapsed}s elapsed",
                          end='', flush=True)
                elif tick % 40 == 0:
                    say(f"  {label}: {elapsed}s elapsed")
                tick += 1
                time.sleep(0.25)
            if tty:
                print("\r\033[2K", end='', flush=True)
            log.seek(0)
            output = log.read().decode('utf-8', 'replace').strip()
            if proc.returncode:
                raise MigrationError(f"{label} failed (exit {proc.returncode}); keep original and backup.")
            say(f"{label}: done ({time.monotonic() - started:.1f}s)")
    except (KeyboardInterrupt, EOFError):
        if "proc" in locals() and proc.poll() is None:
            proc.terminate()
            proc.wait()
        raise
    except FileNotFoundError as exc:
        raise MigrationError(f"Command not found: {cmd[0]}") from exc


def say(message=""):
    print(message, flush=True)


def invoke(*cmd):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except FileNotFoundError as exc:
        raise MigrationError(f"Command not found: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise MigrationError("macOS diskutil command failed; check disk access and run --diagnose.") from exc


def diskutil_plist(*args):
    """Return parsed diskutil plist output using macOS-compatible option order.

    On macOS, `diskutil info -plist diskN` is accepted, while
    `diskutil info diskN -plist` prints usage and exits nonzero. Placing the
    flag immediately after the subcommand also works for `diskutil list`.
    """
    if args[:2] == ("apfs", "list"):
        return plistlib.loads(invoke("diskutil", "apfs", "list", "-plist"))
    if not args or args[0] not in ("list", "info"):
        raise MigrationError("Unsupported diskutil plist operation")
    try:
        return plistlib.loads(invoke("diskutil", args[0], "-plist", *args[1:]))
    except (ValueError, plistlib.InvalidFileException) as exc:
        raise MigrationError(f"Could not parse diskutil output: {exc}") from exc


def removable_media(info):
    """macOS plist may report removal as a boolean or as a string enum."""
    for key in ("RemovableMedia", "Removable"):
        value = info.get(key)
        if value is True or str(value).strip().lower() in ("true", "yes", "removable", "1"):
            return True
    return False


def eligibility(info):
    """Return (eligible, explanation) for a *whole* user-removable disk.

    Excludes boot/internal non-removable drives and disk images. Some macOS/reader
    combinations label a real SD device as Internal=True or VirtualOrPhysical=Unknown.
    """
    if info.get("WholeDisk") is False:
        return False, "partition, not whole disk"
    vop = str(info.get("VirtualOrPhysical") or "").lower()
    protocol = str(info.get("BusProtocol") or info.get("Protocol") or "").lower()
    if vop == "virtual" or any(term in protocol for term in ("disk image", "file-backed", "diskimage")):
        return False, "virtual disk/disk image"
    internal = info.get("Internal")
    loc = str(info.get("DeviceLocation") or "").lower()
    removable = removable_media(info)
    # Removable cards can be on an internal SD reader. Do not treat 'Internal'
    # as an unconditional rejection, but never accept a fixed internal SSD.
    if removable:
        return True, "removable media"
    if internal is False or loc == "external":
        return True, "external device"
    if any(term in protocol for term in ("usb", "secure digital", "sd card")) and internal is not True:
        return True, "USB/SD reader"
    return False, "non-removable internal or unknown device"


def valid_external(info):
    return eligibility(info)[0]


def valid_mount_path(value):
    if not isinstance(value, str) or not value.startswith("/Volumes/"):
        return None
    # Exact path must remain within the mounted volume hierarchy; no '/' volume.
    path = Path(value)
    return value if path.is_dir() else None


def get_mount(part_record, pinfo):
    return valid_mount_path(pinfo.get("MountPoint") or part_record.get("MountPoint"))


def normalized_fs(value: str) -> str | None:
    """Map macOS diskutil filesystem personality strings to a supported name.

    Never treat exFAT as FAT32 just because the word contains 'FAT'.
    """
    text = str(value or "").upper().replace("_", " ").replace("-", " ")
    if "EXFAT" in text or "EX FAT" in text:
        return "exfat"
    if "FAT32" in text or "FAT 32" in text:
        return "fat32"
    if "FAT16" in text or "FAT 16" in text:
        return "fat16"
    return None


def resolve_target_fs(requested: str, manifest: dict, target_size_bytes: int | None = None) -> str:
    """Resolve a filesystem policy using TARGET physical capacity, not source size.

    auto: FAT32 on cards <=32 GiB (incl. marketed 32 GB cards), exFAT above.
    source: retain source's FAT32/exFAT (opt-in only).
    fat32/exfat: explicit user overrides.
    """
    if requested == "auto":
        if target_size_bytes is None or target_size_bytes <= 0:
            raise MigrationError("Cannot automatically select filesystem: target capacity is unknown.")
        return "fat32" if target_size_bytes <= FAT32_MAX_AUTO_BYTES else "exfat"
    if requested in ("fat32", "exfat"):
        return requested
    if requested != "source":
        raise MigrationError(f"Unknown filesystem policy: {requested!r}")
    source_fs = normalized_fs(manifest.get("source_disk", {}).get("filesystem", ""))
    if source_fs not in ("fat32", "exfat"):
        raise MigrationError(
            "Cannot automatically preserve source filesystem: backup does not have a "
            "recognized FAT32/exFAT source format. Use --filesystem fat32 or exfat."
        )
    return source_fs


def check_fs_file_limits(manifest: dict, dest_fs: str) -> None:
    """FAT32 cannot store an individual file larger than 4 GiB minus 1 byte."""
    if dest_fs == "fat32":
        oversized = next((f for f in manifest["files"] if int(f["size"]) > 0xFFFFFFFF), None)
        if oversized:
            raise MigrationError(
                f"Cannot restore to FAT32: file is larger than 4 GiB - 1 byte: "
                "Use --filesystem exfat instead. (Private filename omitted.)"
            )


def external_disks():
    """Find removable physical disks, using both partition records and mount paths.

    diskutil plist contents vary by macOS release and USB/SD reader hardware.
    Do not silently discard an otherwise valid card just because a field is
    absent or VirtualOrPhysical == 'Unknown'.
    """
    all_disks = diskutil_plist("list").get("AllDisksAndPartitions", [])
    found = []
    for disk in all_disks:
        name = disk.get("DeviceIdentifier", "")
        if not re.fullmatch(r"disk\d+", name):
            continue
        try:
            info = diskutil_plist("info", name)
        except MigrationError:
            continue
        if not valid_external(info):
            continue
        parts = list(disk.get("Partitions") or [])
        # Some 'superfloppy' / unpartitioned SD media mount the whole disk.
        if not parts:
            parts = [{"DeviceIdentifier": name, "MountPoint": disk.get("MountPoint")}]
        partitions = []
        for part in parts:
            identifier = part.get("DeviceIdentifier", "")
            if not re.fullmatch(r"disk\d+(?:s\d+)?", identifier):
                continue
            try:
                pinfo = diskutil_plist("info", identifier)
            except MigrationError:
                # A partition might disappear while probing. Use list record
                # as a fallback for mounted volume discovery.
                pinfo = {}
            mp = get_mount(part, pinfo)
            fs = (pinfo.get("FileSystemPersonality") or pinfo.get("FilesystemName")
                  or part.get("VolumeName") or part.get("Content") or "unknown")
            partitions.append({"id": identifier, "mount": mp, "fstype": fs, "info": pinfo})
        found.append({
            "id": name,
            "info": info,
            "name": info.get("MediaName") or info.get("DeviceMediaName") or "Removable media",
            "size": int(info.get("TotalSize") or disk.get("Size") or 0),
            "partitions": partitions,
            "identity": (info.get("MediaName"), info.get("TotalSize"),
                         info.get("BusProtocol"), info.get("DeviceLocation")),
        })

    # Cross-check physically mounted /Volumes paths. Sometimes diskutil's
    # list reports no mount point while 'info <mounted path>' does.
    disks_by_id = {d["id"]: d for d in found}
    try:
        paths = sorted(Path("/Volumes").iterdir())
    except OSError:
        paths = []
    for path in paths:
        if not path.is_dir() or path.is_symlink():
            continue
        try:
            pinfo = diskutil_plist("info", str(path))
        except MigrationError:
            continue
        ident = str(pinfo.get("DeviceIdentifier") or "")
        parent = str(pinfo.get("ParentWholeDisk") or "")
        match = re.fullmatch(r"(disk\d+)(?:s\d+)?", ident)
        disk_id = parent or (match.group(1) if match else "")
        disk = disks_by_id.get(disk_id)
        if not disk:
            continue   # Never bypass the safe whole-disk eligibility filter.
        mounted = valid_mount_path(pinfo.get("MountPoint") or str(path))
        if not mounted:
            continue
        part = next((v for v in disk["partitions"] if v["id"] == ident), None)
        if part:
            part["info"] = pinfo
            part["mount"] = mounted
            if not normalized_fs(part["fstype"]):
                part["fstype"] = (pinfo.get("FileSystemPersonality") or
                                  pinfo.get("FilesystemName") or part["fstype"])
        elif ident and re.fullmatch(r"disk\d+(?:s\d+)?", ident):
            disk["partitions"].append({
                "id": ident, "mount": mounted, "info": pinfo,
                "fstype": pinfo.get("FileSystemPersonality") or pinfo.get("FilesystemName") or "unknown",
            })
    return sorted(found, key=lambda x: int(x["id"][4:]))


def diagnose_disks():
    """Read-only diagnostics: no personal book metadata, no write operations."""
    say("\nDisk detection diagnostics (read-only):")
    records = diskutil_plist("list").get("AllDisksAndPartitions", [])
    for record in records:
        disk_id = record.get("DeviceIdentifier", "")
        if not re.fullmatch(r"disk\d+", disk_id):
            continue
        try:
            inf = diskutil_plist("info", disk_id)
        except MigrationError as exc:
            say(f"  {disk_id}: diskutil info failed: {exc}")
            continue
        allowed, reason = eligibility(inf)
        say(f"  /dev/{disk_id}: {'CANDIDATE' if allowed else 'excluded'} ({reason})"
            f" | name={inf.get('MediaName', '?')!r}"
            f" | size={human(int(inf.get('TotalSize') or 0))}"
            f" | Internal={inf.get('Internal', '?')}"
            f" | Location={inf.get('DeviceLocation', '?')}"
            f" | Removable={inf.get('Removable', inf.get('RemovableMedia', '?'))}"
            f" | VirtualOrPhysical={inf.get('VirtualOrPhysical', '?')}"
            f" | BusProtocol={inf.get('BusProtocol', inf.get('Protocol', '?'))}")
        for p in record.get('Partitions') or []:
            say(f"      {p.get('DeviceIdentifier', '?')}: "
                f"{p.get('MountPoint') or '(mount not reported by diskutil list)'}")
    say("\nMounts scanned under /Volumes:")
    try:
        for path in sorted(Path('/Volumes').iterdir()):
            if path.is_dir() and not path.is_symlink():
                sig = source_signature(path)
                say(f"  {path} — {'CrossInk signature: '+sig if sig else 'no recognized CrossInk signature'}")
    except OSError as exc:
        say(f"  Error reading /Volumes: {exc}")
    show_disks(external_disks())


def human(num):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(num) < 1024 or unit == "TiB":
            return f"{num:.1f} {unit}"
        num /= 1024
    return str(num)


def show_disks(disks):
    say("\nMounted/available external physical disks (NOT necessarily SD cards):")
    for idx, disk in enumerate(disks, 1):
        vols = ", ".join(
            f"{p['id']} at {p['mount'] or '(not mounted)'} [{p['fstype']}]"
            for p in disk["partitions"]
        ) or "No readable partitions"
        say(f"  {idx}. /dev/{disk['id']}: {disk['name']} ({human(disk['size'])})")
        say(f"     {vols}")


def choose_disk(disks, purpose):
    if not disks:
        raise MigrationError("No external physical disks detected. Insert an SD card into a reader.")
    show_disks(disks)
    while True:
        answer = input(f"Choose the {purpose} disk number (or q to cancel): ").strip()
        if answer.lower() == "q":
            raise MigrationError("Cancelled; nothing was erased.")
        if answer.isdigit() and 1 <= int(answer) <= len(disks):
            return disks[int(answer) - 1]
        say("Invalid selection.")


def ignore_path(relative: str, is_dir=False):
    parts = PurePosixPath(relative).parts
    if not parts:
        return False
    if parts[0] in APPLE_DIRS:
        return True
    return any(p in APPLE_FILES or p.startswith("._") for p in parts)


def source_signature(root: Path):
    cp = root / ".crosspoint"
    if not cp.is_dir() or cp.is_symlink():
        return None
    recognized = [p for p in X3_FILES if (root / p).is_file()]
    if recognized:
        return f"CrossInk/CrossPoint (.crosspoint + {', '.join(recognized[:3])})"
    try:
        if any(p.name.startswith(("epub_", "txt_", "xtc_")) for p in cp.iterdir()):
            return "CrossInk/CrossPoint (.crosspoint reader cache; settings marker absent)"
    except OSError:
        pass
    # A real CrossInk card can have an empty/fresh .crosspoint folder. Since
    # source selection is read-only, permit explicit human confirmation.
    return "Possible CrossInk/CrossPoint (.crosspoint directory present; no recognized markers)"


def choose_source():
    disks = external_disks()
    options = []
    for disk in disks:
        for p in disk["partitions"]:
            if p["mount"] and source_signature(Path(p["mount"])):
                options.append((disk, p))
    if not options:
        diagnose_disks()
        raise MigrationError(
            "No mounted SD volume with a recognizable .crosspoint directory was found.\n"
            "Please verify that this is your CrossInk/CrossPoint SD card. "
            "The card cannot be identified as a specific X3 model from its data alone."
        )
    say("\nRecognized CrossInk/CrossPoint volume(s):")
    for i, (disk, p) in enumerate(options, 1):
        say(f"  {i}. /dev/{disk['id']} {p['mount']} "
            f"[{p['fstype']}] ({source_signature(Path(p['mount']))})")
    while True:
        choice = input("Select SOURCE volume number (or q to cancel): ").strip()
        if choice.lower() == "q":
            raise MigrationError("Cancelled.")
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            disk, part = options[int(choice) - 1]
            say("NOTE: CrossInk/CrossPoint metadata does not conclusively identify X3 vs X4.")
            if input("Confirm this is the ORIGINAL XTEINK X3 SD card? [yes/N]: ").strip() != "yes":
                raise MigrationError("Source not confirmed.")
            # Record source filesystem without changing the existing return contract.
            disk["source_filesystem"] = part["fstype"]
            disk["source_volume_uuid"] = part.get("info", {}).get("VolumeUUID")
            return disk, Path(part["mount"])
        say("Invalid selection.")


def iter_source(root: Path):
    files, dirs = [], []

    def walk_error(exc):
        raise exc

    last_scan = time.monotonic()
    for directory, subdirs, filenames in os.walk(root, topdown=True, followlinks=False,
                                                  onerror=walk_error):
        if time.monotonic() - last_scan >= 1:
            say(f"  Scanning: {len(files):,} files, {len(dirs):,} directories discovered...")
            last_scan = time.monotonic()
        base = Path(directory)
        rel_base = base.relative_to(root)
        for name in list(subdirs):
            child = base / name
            relative = (rel_base / name).as_posix()
            if ignore_path(relative, is_dir=True):
                subdirs.remove(name)
                continue
            mode = child.lstat().st_mode
            if not stat.S_ISDIR(mode):
                raise MigrationError("File integrity/path validation failed; private filename omitted.")
            dirs.append(relative)
        for name in filenames:
            child = base / name
            relative = (rel_base / name).as_posix()
            if ignore_path(relative):
                continue
            s = child.lstat()
            if not stat.S_ISREG(s.st_mode):
                raise MigrationError("File integrity/path validation failed; private filename omitted.")
            files.append({"path": relative, "size": s.st_size, "mtime_ns": s.st_mtime_ns})
    files.sort(key=lambda f: f["path"])
    dirs.sort()
    if not files:
        raise MigrationError("Source has no files after filtering macOS service files.")
    return files, dirs


def file_sha256(path: Path, progress: Progress | None = None):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(CHUNK):
            h.update(block)
            if progress is not None:
                progress.advance(len(block))
    return h.hexdigest()


def check_space(directory: Path, bytes_needed: int):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if shutil.disk_usage(directory).free < bytes_needed:
        raise MigrationError(
            f"Not enough free space for safe backup in {directory}. "
            f"Recommended at least {human(bytes_needed)} free."
        )


def make_backup(root: Path, source_disk: dict):
    say("\n[1/5] Scanning ALL X3 files, including hidden files...")
    root_device = root.stat().st_dev
    files, dirs = iter_source(root)
    total = sum(f["size"] for f in files)
    say(f"Source: {len(files)} files, {len(dirs)} directories, {human(total)}")
    say("Only macOS-generated service files are excluded (.DS_Store, ._*, .Trashes, etc.).")
    if os.path.commonpath((str(root.resolve()), str(BACKUP_DIR.resolve()))) == str(root.resolve()):
        raise MigrationError("Backup directory resolves INSIDE source SD card. Refusing to back up onto the source.")
    if source_disk.get("info"):
        existing = BACKUP_DIR
        while not existing.exists():
            existing = existing.parent
        if source_disk["id"] in disk_safety.physical_disks(existing, diskutil_plist, MigrationError):
            raise MigrationError("Backup storage is on the source disk; refusing to write.")
    check_space(BACKUP_DIR, total + 128 * 1024 * 1024)
    now = dt.datetime.now().astimezone()
    stamp = now.strftime("%Y-%m-%d_%H-%M-%S-%f")
    base = f"xteink-x3_{stamp}"
    final_zip = BACKUP_DIR / f"{base}.zip"
    tmp_zip = BACKUP_DIR / f"{base}.zip.partial"
    manifest_path = BACKUP_DIR / f"{base}.manifest.json"
    sum_path = BACKUP_DIR / f"{base}.zip.sha256"
    say("\n[2/5] Creating private backup...")
    tmp_zip.touch(mode=0o600, exist_ok=False)
    try:
        archived = Progress("ZIP create", total, len(files))
        with zipfile.ZipFile(tmp_zip, "w", allowZip64=True,
                             compression=zipfile.ZIP_DEFLATED, compresslevel=3) as zf:
            for name in dirs:
                zf.writestr(name + "/", b"")
            for number, entry in enumerate(files, 1):
                src = root / entry["path"]
                if root.stat().st_dev != root_device:
                    raise MigrationError("Source mount identity changed during backup.")
                before = src.lstat()
                if not stat.S_ISREG(before.st_mode):
                    raise MigrationError("Source file type changed during backup.")
                if before.st_size != entry["size"] or before.st_mtime_ns != entry["mtime_ns"]:
                    raise MigrationError("File integrity/path validation failed; private filename omitted.")
                info = zipfile.ZipInfo.from_file(src, arcname=entry["path"])
                info.compress_type = zipfile.ZIP_DEFLATED
                h = hashlib.sha256()
                with os.fdopen(os.open(src, os.O_RDONLY | os.O_NOFOLLOW), "rb") as sf, zf.open(info, "w", force_zip64=True) as df:
                    while block := sf.read(CHUNK):
                        h.update(block)
                        df.write(block)
                        archived.advance(len(block))
                after = src.lstat()
                if (after.st_size != before.st_size or after.st_mtime_ns != before.st_mtime_ns):
                    raise MigrationError("File integrity/path validation failed; private filename omitted.")
                entry["sha256"] = h.hexdigest()
                archived.advance(files=1)
        archived.finish()
        current_files, current_dirs = iter_source(root)
        if (root.stat().st_dev != root_device or current_dirs != dirs or
                [{k: f[k] for k in ("path", "size", "mtime_ns")} for f in files] != current_files):
            raise MigrationError("Source tree changed during backup; original and target preserved.")
        manifest = {
            "format": "xteink-x3-migrate-v1",
            "created_at": now.isoformat(),
            "source_disk": {"media_name": source_disk["name"],
                            "capacity_bytes": source_disk["size"],
                            "filesystem": source_disk.get("source_filesystem", "unknown"),
                            "disk_identifier_at_backup": source_disk["id"],
                            "volume_uuid": source_disk.get("source_volume_uuid")},
            "files": files, "directories": dirs,
            "file_count": len(files), "total_bytes": total,
            "excluded": "macOS service files/directories only",
        }
        say("\n[3/5] Reading back ZIP and verifying SHA-256 for EVERY file...")
        verify_archive_contents(tmp_zip, manifest)
        tmp_zip.replace(final_zip)
        hash_progress = Progress("ZIP SHA-256", final_zip.stat().st_size)
        zip_sha = file_sha256(final_zip, hash_progress)
        hash_progress.finish()
        manifest["zip_sha256"] = zip_sha
        manifest_path.touch(mode=0o600, exist_ok=False)
        sum_path.touch(mode=0o600, exist_ok=False)
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
        sum_path.write_text(f"{zip_sha}  {final_zip.name}\n", encoding="utf-8")
        for item in (final_zip, manifest_path, sum_path):
            os.chmod(item, 0o600)  # The archive may contain Wi-Fi/OPDS credentials.
        say("BACKUP VERIFIED")
        say(f"  ZIP:      {final_zip} ({human(final_zip.stat().st_size)})")
        say(f"  Manifest: {manifest_path}")
        say(f"  SHA-256:  {zip_sha}")
        return final_zip, manifest
    finally:
        if tmp_zip.exists():
            tmp_zip.unlink()


def safe_member(name: str):
    if not isinstance(name, str) or not name or len(name) > 4096:
        return False
    p = PurePosixPath(name)
    return (not name.startswith("/") and "\\" not in name
            and all(component not in ("", ".", "..") and
                    not any(ord(c) < 32 or c in ':*?"<>|' for c in component) and
                    component == component.rstrip(" .") for component in p.parts)
            and p.as_posix() + ("/" if name.endswith("/") else "") == name)


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise MigrationError("Duplicate JSON key in manifest.")
        obj[key] = value
    return obj


def validate_manifest(manifest):
    try:
        if not isinstance(manifest, dict) or manifest.get("format") != "xteink-x3-migrate-v1":
            raise ValueError
        files, dirs = manifest["files"], manifest["directories"]
        if (not isinstance(files, list) or not isinstance(dirs, list) or not files or
                len(files) + len(dirs) > MAX_ENTRIES or
                not isinstance(manifest.get("source_disk"), dict)):
            raise ValueError
        paths = []
        for item in files:
            if (not isinstance(item, dict) or not safe_member(item.get("path")) or
                    item["path"].endswith("/") or type(item.get("size")) is not int or
                    not 0 <= item["size"] <= MAX_BACKUP_BYTES or
                    type(item.get("mtime_ns")) is not int or item["mtime_ns"] < 0 or
                    not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", "")))):
                raise ValueError
            paths.append(item["path"])
        if not all(safe_member(n) and not n.endswith("/") for n in dirs):
            raise ValueError
        all_paths = paths + dirs
        folded = [unicodedata.normalize("NFD", n).casefold() for n in all_paths]
        if len(set(folded)) != len(folded):
            raise ValueError
        directories = set(dirs)
        for name in all_paths:
            if any(str(parent) not in directories for parent in PurePosixPath(name).parents if str(parent) != "."):
                raise ValueError
        total = sum(f["size"] for f in files)
        if (type(manifest.get("file_count")) is not int or manifest["file_count"] != len(files) or
                type(manifest.get("total_bytes")) is not int or manifest["total_bytes"] != total or
                total > MAX_BACKUP_BYTES):
            raise ValueError
        capacity = manifest["source_disk"].get("capacity_bytes", 0)
        if type(capacity) is not int or capacity < 0:
            raise ValueError
    except (KeyError, TypeError, ValueError, AttributeError):
        raise MigrationError("Unsafe or inconsistent backup manifest.") from None


def check_zip_directory_size(archive):
    """Bound central-directory allocation before ZipFile parses untrusted entries."""
    with Path(archive).open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(max(0, size - 65557))
        tail = stream.read()
        offset = tail.rfind(b"PK\x05\x06")
        if offset < 0 or len(tail) - offset < 22:
            raise zipfile.BadZipFile("Incomplete ZIP central directory")
        record = struct.unpack_from("<4s4H2LH", tail, offset)
        entries, directory_bytes = record[4], record[5]
        if record[1] or record[2] or len(tail) - offset != 22 + record[7]:
            raise MigrationError("Split/trailing ZIP data is unsupported.")
        if entries == 0xFFFF or directory_bytes == 0xFFFFFFFF:
            # ZIP64 end record locator directly precedes the normal end record.
            if offset < 20:
                raise MigrationError("Missing ZIP64 directory locator.")
            locator = struct.unpack_from("<4sLQL", tail, offset - 20)
            if locator[0] != b"PK\x06\x07" or locator[1] != 0 or locator[3] != 1:
                raise MigrationError("Invalid ZIP64 directory locator.")
            stream.seek(locator[2])
            header = stream.read(56)
            if len(header) != 56:
                raise MigrationError("Incomplete ZIP64 directory.")
            values = struct.unpack("<4sQ2H2L4Q", header)
            if values[0] != b"PK\x06\x06" or values[4] or values[5]:
                raise MigrationError("Invalid ZIP64 directory.")
            entries, directory_bytes = values[7], values[8]
        if entries > MAX_ENTRIES or directory_bytes > MAX_MANIFEST_BYTES:
            raise MigrationError("ZIP directory exceeds resource limits.")


def verify_archive_contents(archive: Path, manifest: dict):
    validate_manifest(manifest)
    expected_files = {f["path"]: f for f in manifest["files"]}
    expected_dirs = set(manifest["directories"])
    check_zip_directory_size(archive)
    with zipfile.ZipFile(archive, "r") as zf:
        members = zf.infolist()
        if len(members) != len(expected_files) + len(expected_dirs) or len(members) > MAX_ENTRIES:
            raise MigrationError("Unexpected ZIP member count.")
        seen = set()
        for item in members:
            key = item.filename.rstrip("/")
            mode = item.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if (not safe_member(item.filename) or key in seen or item.flag_bits & 1 or
                    kind not in (0, stat.S_IFREG, stat.S_IFDIR) or
                    (kind == stat.S_IFDIR and not item.is_dir()) or
                    (kind == stat.S_IFREG and item.is_dir())):
                raise MigrationError("Unsafe/duplicate/special ZIP entry.")
            seen.add(key)
            if item.is_dir():
                if key not in expected_dirs or item.file_size != 0:
                    raise MigrationError("Unexpected ZIP directory.")
            elif (key not in expected_files or item.file_size != expected_files[key]["size"] or
                  item.file_size > MAX_BACKUP_BYTES or
                  item.file_size > max(1, item.compress_size) * 10000):
                raise MigrationError("ZIP size, expansion limit, or member mismatch.")
        if seen != set(expected_files) | expected_dirs:
            raise MigrationError("ZIP member tree differs from manifest.")
        checked = Progress("ZIP verify", manifest["total_bytes"], len(expected_files))
        for name, item in expected_files.items():
            h = hashlib.sha256()
            size = 0
            with zf.open(name, "r") as f:
                while block := f.read(min(CHUNK, item["size"] - size + 1)):
                    size += len(block)
                    if size > item["size"]:
                        raise MigrationError("ZIP stream exceeds declared size.")
                    h.update(block)
                    checked.advance(len(block))
            if size != item["size"] or h.hexdigest() != item["sha256"]:
                raise MigrationError("ZIP checksum/size mismatch; private filename omitted.")
            checked.advance(files=1)
        checked.finish()


def load_backup(archive: Path):
    archive = archive.expanduser().resolve(strict=True)
    if archive.suffix.lower() != ".zip":
        raise MigrationError("Restore input must be a .zip file produced by this tool.")
    manifest_file = archive.with_suffix(".manifest.json")
    try:
        if manifest_file.stat().st_size > MAX_MANIFEST_BYTES:
            raise MigrationError("Backup manifest exceeds size limit.")
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except (OSError, ValueError) as exc:
        raise MigrationError("File integrity/path validation failed; private filename omitted.") from exc
    validate_manifest(manifest)
    say("Checking archived ZIP SHA-256 (before touching target)...")
    hash_progress = Progress("Backup SHA-256", archive.stat().st_size)
    digest = file_sha256(archive, hash_progress)
    hash_progress.finish()
    if digest != manifest.get("zip_sha256"):
        raise MigrationError("BACKUP ZIP HASH DOES NOT MATCH MANIFEST; target left untouched.")
    say("Checking every archived file...")
    verify_archive_contents(archive, manifest)
    say("ZIP and manifest verification passed.")
    return archive, manifest


def source_like_target(disk: dict, manifest: dict):
    # Treat any CrossPoint card as valuable, including modified source metadata.
    for part in disk["partitions"]:
        if part.get("mount"):
            try:
                cp = Path(part["mount"]) / ".crosspoint"
                cp.lstat()
                return True
            except FileNotFoundError:
                pass
            except OSError:
                return True
    # Refuse a byte-identical copy even if no CrossPoint marker is present.
    expected = {f["path"]: f["sha256"] for f in manifest["files"]}
    probes = [name for name in X3_FILES if name in expected]
    probes.extend(f["path"] for f in manifest["files"] if f["path"].startswith(".crosspoint/epub_")
                  and f["path"].endswith("/progress.bin"))
    if not probes:
        probes = list(expected)[:4]
    for part in disk["partitions"]:
        if not part["mount"]:
            continue
        mount = Path(part["mount"])
        for name in probes[:12]:
            candidate = mount / name
            if candidate.is_file() and not candidate.is_symlink():
                try:
                    if file_sha256(candidate) == expected[name]:
                        return True
                except OSError:
                    return True  # Never wipe if fingerprint reading fails.
    return False


def required_allocated_space(manifest: dict, allocation_unit: int = 65536) -> int:
    """Conservatively estimate allocation overhead for FAT32 or exFAT.

    Count files/directories with at least 64 KiB allocation granularity;
    actual free capacity is verified after formatting.
    """
    unit = max(65536, allocation_unit)
    file_bytes = sum(((int(f["size"]) + unit - 1) // unit) * unit
                     for f in manifest["files"])
    directory_bytes = len(manifest["directories"]) * unit
    reserve = max(32 * 1024 * 1024, int(manifest["total_bytes"]) // 50)
    return file_bytes + directory_bytes + reserve


def check_formatted_target_space(volume: Path, manifest: dict, filesystem: str = "fat32") -> None:
    """Abort *before copying* if the newly formatted volume cannot fit data."""
    stats = os.statvfs(volume)
    allocation_unit = max(stats.f_frsize, stats.f_bsize, 65536)
    needed = required_allocated_space(manifest, allocation_unit)
    free = shutil.disk_usage(volume).free
    say(f"Target free after {filesystem.upper()} format: {human(free)}")
    say(f"Estimated needed incl. cluster overhead and safety margin: {human(needed)}")
    if needed > free:
        raise MigrationError(
            f"Not enough usable space after formatting: need {human(needed)}, "
            f"have {human(free)}. No backup files were written to the target."
        )


def choose_target(manifest: dict, source_disk_id: str | None,
                  allow_smaller_target: bool = False, filesystem: str = "auto"):
    input("\nRemove the ORIGINAL card and leave the reader empty. Press Return... ")
    records = diskutil_plist("list").get("AllDisksAndPartitions", [])
    absent_ids = {r.get("DeviceIdentifier") for r in records}
    if source_disk_id and source_disk_id in absent_ids:
        raise MigrationError("Source disk is still attached. Remove it before continuing.")
    input("Insert the NEW TARGET SD card, then press Return... ")
    disks = external_disks()
    if not disks:
        raise MigrationError("No external disk found. Check the new SD card/reader.")
    target = choose_disk(disks, "TARGET (WILL BE ERASED)")
    if target["id"] in absent_ids:
        raise MigrationError("Target was already attached during the empty-reader check.")
    confirmed_identity = disk_safety.target_identity(target, MigrationError)
    source_uuid = manifest.get("source_disk", {}).get("volume_uuid")
    if source_uuid and source_uuid == confirmed_identity[1]:
        raise MigrationError("Target has the source volume identity; refusing erase.")
    if len(target["partitions"]) > 1:
        raise MigrationError("Target has multiple partitions. Refusing to erase a likely non-SD storage device.")
    if not target["size"]:
        raise MigrationError("Cannot determine target capacity.")
    if source_like_target(target, manifest):
        raise MigrationError("TARGET resembles the SOURCE backup (matching X3 files). Refusing to wipe it. Insert a DIFFERENT card.")
    # Compare *actual* raw byte capacity; cards with the same advertised
    # capacity can differ slightly. By default fail closed for a smaller card.
    source_capacity = int(manifest.get("source_disk", {}).get("capacity_bytes") or 0)
    if source_capacity and target["size"] < source_capacity:
        if not allow_smaller_target:
            raise MigrationError(
                f"Target's actual capacity {human(target['size'])} is smaller than "
                f"source {human(source_capacity)}. Default policy requires target >= source. "
                f"If you intentionally want file-level restore to a smaller card, "
                f"rerun with --allow-smaller-target (space checks still apply)."
            )
        say("WARNING: Target is physically smaller than source; checking DATA fit only.")
    # The default format is based on the TARGET size (not the source size).
    # Resolve after selecting the card, but before destructive confirmation.
    target_fs = resolve_target_fs(filesystem, manifest, target["size"])
    # This checks the raw disk in advance. A second check of *actual usable*
    # capacity runs after filesystem formatting and BEFORE restoring any files.
    # Reject incompatible large files before requesting destructive confirmation.
    check_fs_file_limits(manifest, target_fs)
    required = required_allocated_space(manifest)
    if required > target["size"]:
        raise MigrationError(f"Target too small. Estimated need {human(required)}, capacity {human(target['size'])}.")
    say(f"Source physical capacity: {human(source_capacity)}" if source_capacity else
        "Source physical capacity not available in manifest.")
    say(f"Target physical capacity: {human(target['size'])}")
    say(f"Estimated restore requirement: {human(required)}")
    say(f"Source filesystem: {manifest.get('source_disk', {}).get('filesystem', 'unknown')}")
    say(f"Target filesystem: {target_fs.upper()} / MBR (will be ERASED; policy: {filesystem})")
    say("\n!!! PERMANENT DATA DELETION !!!")
    say(f"TARGET: /dev/{target['id']} — {target['name']} ({human(target['size'])})")
    say("Every partition and file on THIS DISK will be destroyed.")
    say("Keep the original card disconnected and preserve the backup.")
    if input(f"Type exactly 'ERASE {target['id']}' to format the target: ").strip() != f"ERASE {target['id']}":
        raise MigrationError("Wipe not confirmed; target untouched.")
    if input("FINAL confirmation: type 'WIPE TARGET' to continue: ").strip() != "WIPE TARGET":
        raise MigrationError("Wipe not confirmed; target untouched.")
    # Re-check immediately, to reduce risk of changed device identifiers.
    refreshed = next((d for d in external_disks() if d["id"] == target["id"]), None)
    if not refreshed or refreshed["identity"] != target["identity"] or refreshed["size"] != target["size"]:
        raise MigrationError("Target disk identity changed before erase. Aborting.")
    if source_like_target(refreshed, manifest):
        raise MigrationError("Target now resembles source. Aborting erase.")
    # Re-check target size and format selection immediately before diskutil erase.
    # It is critical that the format displayed to the user matches the format used.
    if resolve_target_fs(filesystem, manifest, refreshed["size"]) != target_fs:
        raise MigrationError("Target format selection changed. Aborting erase.")
    if disk_safety.target_identity(refreshed, MigrationError) != confirmed_identity:
        raise MigrationError("Target volume/mount identity changed before erase.")
    refreshed["confirmed_identity"] = confirmed_identity
    refreshed["target_filesystem"] = target_fs
    return refreshed


def erase_target(target, archive, manifest, allow_smaller=False):
    """The only eraseDisk entry point: revalidate data, storage and confirmed media."""
    archive, verified = load_backup(archive)
    if verified != manifest:
        raise MigrationError("Backup manifest changed after target confirmation.")
    current = next((d for d in external_disks() if d['id'] == target['id']), None)
    if not current or disk_safety.target_identity(current, MigrationError) != target.get('confirmed_identity'):
        raise MigrationError("Confirmed target identity changed; refusing erase.")
    protected = [
        archive, archive.with_suffix('.manifest.json'), Path(__file__),
        Path(disk_safety.__file__), Path.cwd(), Path.home(), Path('/')]
    sidecar = archive.with_suffix('.zip.sha256')
    if sidecar.exists() or sidecar.is_symlink():
        protected.append(sidecar)
    disk_safety.protect_locations(current, protected, diskutil_plist, MigrationError)
    if source_like_target(current, verified):
        raise MigrationError("Target matches source data; refusing erase.")
    source_uuid = verified['source_disk'].get('volume_uuid')
    if source_uuid and source_uuid == target['confirmed_identity'][1]:
        raise MigrationError("Source volume is protected; refusing erase.")
    capacity = verified['source_disk'].get('capacity_bytes', 0)
    if ((capacity > current['size'] and not allow_smaller) or
            required_allocated_space(verified) > current['size']):
        raise MigrationError("Target capacity check failed before erase.")
    fs = target['target_filesystem']
    if fs not in ('fat32', 'exfat'):
        raise MigrationError("Unrecognized target filesystem.")
    check_fs_file_limits(verified, fs)
    # Re-query after the potentially slow integrity/protected-storage checks.
    last = next((d for d in external_disks() if d['id'] == target['id']), None)
    if not last or disk_safety.target_identity(last, MigrationError) != target['confirmed_identity']:
        raise MigrationError("Target changed immediately before erase.")
    invoke_status("Formatting target SD", "diskutil", "eraseDisk",
                  "FAT32" if fs == 'fat32' else "ExFAT", "XTEINKX3", "MBR", f"/dev/{target['id']}")


def after_format_volume(target_id: str, expected_fs: str = "fat32"):
    disks = [d for d in external_disks() if d["id"] == target_id]
    if len(disks) != 1:
        raise MigrationError("Formatted target disk disappeared; refusing to write.")
    disk = disks[0]
    vols = [p for p in disk["partitions"] if p["mount"]]
    if len(vols) != 1:
        raise MigrationError("Unable to identify exactly one newly formatted volume.")
    p = vols[0]
    actual_fs = normalized_fs(p["fstype"])
    if actual_fs != expected_fs:
        raise MigrationError(
            f"Target format mismatch: requested {expected_fs.upper()}, "
            f"diskutil reports {p['fstype']!r}. Refusing to restore."
        )
    # diskutil eraseDisk MBR should create an FDisk partition scheme.
    layout = diskutil_plist("list").get("AllDisksAndPartitions", [])
    disk_record = next((record for record in layout
                        if record.get("DeviceIdentifier") == target_id), None)
    if disk_record is None or disk_record.get("Content") not in ("FDisk_partition_scheme", "MBR"):
        raise MigrationError("Target is not confirmed as MBR/FDisk. Refusing to restore.")
    return Path(p["mount"])


def restore_archive(archive: Path, manifest: dict, root: Path):
    say("\n[4/5] Restoring verified backup...")
    verify_archive_contents(archive, manifest)
    # Anchor every write to an open directory descriptor. An unmounted path must
    # never fall back to creating files on the Mac beneath the old mount point.
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_fd = os.open(root, flags)
    root_device = os.fstat(root_fd).st_dev

    def directory_fd(parts):
        fd = os.dup(root_fd)
        try:
            for component in parts:
                try:
                    os.mkdir(component, dir_fd=fd)
                except FileExistsError:
                    pass
                child = os.open(component, flags, dir_fd=fd)
                os.close(fd)
                fd = child
                if os.fstat(fd).st_dev != root_device:
                    raise MigrationError("Nested mount in restore tree; refusing write.")
            return fd
        except BaseException:
            os.close(fd)
            raise

    try:
        written = Progress("SD restore", manifest["total_bytes"], len(manifest["files"]))
        with zipfile.ZipFile(archive, "r") as zf:
            for name in sorted(manifest["directories"], key=lambda n: (n.count("/"), n)):
                os.close(directory_fd(PurePosixPath(name).parts))
            for item in manifest["files"]:
                parts = PurePosixPath(item["path"]).parts
                parent_fd = directory_fd(parts[:-1])
                try:
                    fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=parent_fd)
                    h = hashlib.sha256()
                    with zf.open(item["path"]) as src, os.fdopen(fd, "wb") as dst:
                        size = 0
                        while block := src.read(CHUNK):
                            size += len(block)
                            if size > item["size"]:
                                raise MigrationError("Restore stream exceeds verified size.")
                            dst.write(block)
                            h.update(block)
                            written.advance(len(block))
                        dst.flush()
                        os.fsync(dst.fileno())
                    if size != item["size"] or h.hexdigest() != item["sha256"]:
                        raise MigrationError("Restored file checksum/size mismatch.")
                    try:
                        os.utime(parts[-1], ns=(item["mtime_ns"], item["mtime_ns"]),
                                 dir_fd=parent_fd, follow_symlinks=False)
                    except OSError:
                        say("  WARNING: unable to preserve a modification time.")
                finally:
                    os.close(parent_fd)
                written.advance(files=1)
        written.finish()
    finally:
        os.close(root_fd)
    os.sync() if hasattr(os, "sync") else None


def verify_restored(root: Path, manifest: dict):
    say("\n[5/5] Re-reading EVERY file from target SD card and verifying SHA-256...")
    seen_files, seen_dirs = iter_source(root)
    expected_files = {f["path"]: f for f in manifest["files"]}
    actual_files = {f["path"] for f in seen_files}
    if actual_files != set(expected_files):
        raise MigrationError("File integrity/path validation failed; private filename omitted.")
    if set(seen_dirs) != set(manifest["directories"]):
        raise MigrationError("Directory tree differs from the backup.")
    verified = Progress("SD verify", manifest["total_bytes"], len(seen_files))
    for i, file in enumerate(seen_files, 1):
        expected = expected_files[file["path"]]
        if file["size"] != expected["size"]:
            raise MigrationError("File integrity/path validation failed; private filename omitted.")
        if file_sha256(root / file["path"], verified) != expected["sha256"]:
            raise MigrationError("File integrity/path validation failed; private filename omitted.")
        verified.advance(files=1)
    verified.finish()
    say(f"PASS: {len(seen_files)} SHA-256 matches, {len(seen_dirs)} directories verified.")


def eject(disk_id: str):
    say(f"Safely ejecting /dev/{disk_id}...")
    invoke_status("Safely ejecting", "diskutil", "eject", f"/dev/{disk_id}")
    say("Ejected successfully. You may physically remove the SD card.")


def main():
    parser = argparse.ArgumentParser(description="Verified CrossInk XTEINK X3 SD migration on macOS")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--backup-only", action="store_true", help="Back up & verify source, then eject (no formatting)")
    group.add_argument("--restore", type=Path, metavar="BACKUP.zip", help="Restore an existing backup (after verification)")
    parser.add_argument(
        "--filesystem", choices=("auto", "fat32", "exfat", "source"), default="auto",
        help="Target format (all MBR): auto [default; FAT32 if target <=32 GiB, exFAT otherwise], "
             "fat32, exfat, or source (preserve original)",
    )
    parser.add_argument("--version", action="version", version=f"xteink-sd-migrator {__version__}")
    parser.add_argument("--diagnose", action="store_true", help="Print read-only macOS disk and CrossInk detection details, then exit")
    parser.add_argument("--allow-smaller-target", action="store_true",
                        help="Allow smaller physical card if file-level data fits (still checks usable space)")
    args = parser.parse_args()
    if sys.platform != "darwin":
        raise MigrationError("This tool only supports macOS (requires diskutil).")
    if sys.version_info < (3, 9):
        raise MigrationError("Python 3.9 or newer is required.")
    say("=" * 65)
    say(f" XTEINK SD Migrator v{__version__} — macOS")
    say("=" * 65)
    say("WARNING: Any target disk you confirm will be COMPLETELY ERASED.")
    say("Keep the original card. Shut down X3 before physically removing the card.")
    say("The backup includes settings; protect it as it may contain credentials.")
    if args.diagnose:
        diagnose_disks()
        return
    source_id = None
    if args.restore:
        archive, manifest = load_backup(args.restore)
    else:
        input("Insert ONLY the SOURCE X3 microSD (via card reader), then press Return... ")
        disk, root = choose_source()
        source_id = disk["id"]
        # Volume could become disconnected between selection and traversal.
        archive, manifest = make_backup(root, disk)
        eject(source_id)
        if args.backup_only:
            say("\nBACKUP ONLY complete. Original card not modified.")
            return
    # AUTO requires target capacity, so choose_target resolves & preflights format
    # after examining the physical card, before showing the erase confirmations.
    archive, manifest = load_backup(archive)
    target = choose_target(manifest, source_id, allow_smaller_target=args.allow_smaller_target,
                           filesystem=args.filesystem)
    target_fs = target["target_filesystem"]
    erase_target(target, archive, manifest, args.allow_smaller_target)
    dst = after_format_volume(target["id"], target_fs)
    post_disk = next((d for d in external_disks() if d["id"] == target["id"]), None)
    if not post_disk or disk_safety.hardware_identity(post_disk) != disk_safety.hardware_identity(target):
        raise MigrationError("Target hardware changed after format; refusing restore.")
    # Critical second preflight: physical media size is not usable filesystem size.
    # Verify available space BEFORE creating directories or extracting ZIP contents.
    check_formatted_target_space(dst, manifest, target_fs)
    try:
        restore_archive(archive, manifest, dst)
        verify_restored(dst, manifest)
    except Exception:
        say("RESTORE FAILED. Target may be incomplete. KEEP ORIGINAL CARD AND ZIP BACKUP.")
        raise
    eject(target["id"])
    say("\n" + "=" * 65)
    say("MIGRATION SUCCESSFUL: target SHA-256 verified and safely ejected.")
    say("Next: insert new card into X3 and test books, fonts, bookmarks and reading progress.")
    say(f"Keep backup ZIP: {archive}")
    say("Do NOT wipe the original card until the reader has been fully tested.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        say("\nCancelled. Any existing backup ZIP is retained.")
        sys.exit(130)
    except (MigrationError, OSError, zipfile.BadZipFile, RuntimeError, ValueError) as exc:
        say("\nERROR: " + (str(exc) if isinstance(exc, MigrationError) else
                            "I/O or archive operation failed; private file details omitted."))
        say("Do not erase the original SD card. Preserve the ZIP + manifest if they exist.")
        sys.exit(1)
