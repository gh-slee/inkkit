"""Explicit current-card sessions. No formatting, partitioning or restore runner.

Device queries and ejection are disabled in automated tests unless mocked.
All host state uses private, descriptor-checked directories outside the card.
"""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import plistlib
import pwd
import re
import stat
import subprocess
import uuid

import disk_safety
import inkkit_schema as schema


def _error(code, message):
    from inkkit_config import ConfigError
    return ConfigError(code, message)


def _query(operation, *args):
    if os.environ.get('XTEINK_TESTING') == '1':
        raise _error('test_guard', 'Real disk queries are disabled during automated tests.')
    try:
        result = subprocess.run(['/usr/sbin/diskutil', operation, '-plist', *map(str, args)],
                                capture_output=True, timeout=10, check=True)
        if len(result.stdout) > 1024 * 1024:
            raise ValueError('size')
        value = plistlib.loads(result.stdout)
        if type(value) is not dict:
            raise ValueError('object')
        return value
    except (subprocess.SubprocessError, OSError, ValueError, plistlib.InvalidFileException):
        raise _error('disk_query', 'macOS could not confirm the selected SD card. Check its connection and permissions.') from None


def _mount_parent():
    return Path('/Volumes')


def _is_mount(root):
    return root.stat().st_dev != root.parent.stat().st_dev


def ensure_separate_storage(card_info, host_info):
    if card_info.st_dev == host_info.st_dev:
        raise _error('unsafe_backup', 'Backups must be on the Mac, separate from the SD card.')


def _inspect(root, model):
    if model not in schema.MODELS:
        raise _error('profile', 'Choose a supported XTEINK model.')
    root = Path(root)
    if (not root.is_absolute() or root.parent != _mount_parent() or root.is_symlink()
            or not root.is_dir() or not _is_mount(root)):
        raise _error('mount', 'Select the mounted SD card itself, directly under Volumes.')
    pinfo = _query('info', root)
    if pinfo.get('MountPoint') != str(root):
        raise _error('mount', 'The selected mount does not match macOS volume information. Reopen the mounted SD card itself.')
    # Some diskutil plist responses omit Mounted even for mounted FAT volumes.
    # A real mount boundary above plus an exact MountPoint remains required.
    # If the optional flag is supplied, reject false or malformed evidence.
    if 'Mounted' in pinfo and pinfo['Mounted'] is not True:
        raise _error('mount', 'macOS did not confirm this volume as mounted. Reconnect the SD card and reopen it.')
    whole = pinfo.get('ParentWholeDisk')
    if not isinstance(whole, str) or not re.fullmatch(r'disk\d+', whole):
        raise _error('identity', 'The physical card identity is unavailable.')
    info = _query('info', whole)
    if info.get('Internal') is not False or info.get('Virtual') is True:
        raise _error('unsafe_volume', 'Internal, virtual or unidentified media cannot be edited.')
    layout = _query('list', whole).get('AllDisksAndPartitions', [])
    records = [record for record in layout if record.get('DeviceIdentifier') == whole]
    if len(records) != 1 or len(records[0].get('Partitions', [])) != 1:
        raise _error('layout', 'Settings editing requires a single mounted FAT32/exFAT partition.')
    part = records[0]['Partitions'][0]
    if part.get('DeviceIdentifier') != pinfo.get('DeviceIdentifier'):
        raise _error('identity', 'The selected partition identity changed.')
    if pinfo.get('ReadOnlyVolume') is True or pinfo.get('ReadOnlyMedia') is True:
        raise _error('read_only', 'This SD card is read-only.')
    disk = dict(id=whole, info=info, size=info.get('TotalSize'), partitions=[
        dict(id=pinfo.get('DeviceIdentifier'), mount=str(root), info=pinfo,
             fstype=pinfo.get('FilesystemName') or pinfo.get('FileSystemPersonality') or '')])
    # Reuse confirmed-removable-media, physical bus, FAT, UUID and protected-volume
    # policy without calling any migration source check or destructive entry point.
    disk_safety.target_identity(disk, lambda message: _error('unsafe_volume',
        'This volume does not meet the writable removable USB/SD, FAT32/exFAT and protected-storage policy. No settings were changed.'))
    stable = dict(model=model, volume=pinfo.get('VolumeUUID') or pinfo.get('DiskUUID'),
                  partition_uuid=pinfo.get('DiskUUID'), media_uuid=info.get('MediaUUID'), size=info.get('TotalSize'))
    identity = hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()
    live = dict(stable=stable, disk=whole, partition=pinfo.get('DeviceIdentifier'),
                hardware=list(disk_safety.hardware_identity(disk)), root=list((root.stat().st_dev, root.stat().st_ino)))
    return dict(root=str(root), identity=identity, live=live, model=model,
                label=pinfo.get('VolumeName') if isinstance(pinfo.get('VolumeName'), str) else 'XTEINK SD card')


def _support_parent():
    # HOME/PYTHONHOME cannot redirect private recovery records onto a card.
    return Path(pwd.getpwuid(os.getuid()).pw_dir) / 'Library' / 'Application Support'


def _private_child(parent, name, create):
    from inkkit_config import _open_directory
    fd = _open_directory(parent)
    child = None
    try:
        if create:
            try:
                os.mkdir(name, 0o700, dir_fd=fd)
                os.fsync(fd)
            except FileExistsError:
                pass
        child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
        info = os.fstat(child)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise _error('private_storage', 'InkKit recovery storage must be a private directory owned by the current user.')
        return Path(parent) / name
    finally:
        if child is not None:
            os.close(child)
        os.close(fd)


def _host_root(create=False):
    return _private_child(_support_parent(), 'InkKit', create)


def _session_directory(create=False):
    return _private_child(_host_root(create), 'Sessions', create)


def open_card(root, model, firmware, confirmed):
    if not schema.supports_configuration(model, firmware) or confirmed is not True:
        raise _error('profile', 'Confirm the reader model and the supported CrossInk firmware version before opening the card.')
    context = _inspect(root, model)
    from inkkit_config import _Workspace, _document, _json_bytes, _open_directory, _read_at, _write_new
    # Recognize the namespaced CrossInk configuration before creating host state.
    fd = _open_directory(context['root'])
    config = None
    try:
        config = os.open('.crosspoint', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
        if os.fstat(config).st_dev != os.fstat(fd).st_dev:
            raise _error('identity', 'The configuration directory is on an unexpected device.')
        _document(_read_at(config, 'crossink-settings.json', require_owner=False)[0])
    finally:
        if config is not None:
            os.close(config)
        os.close(fd)
    ensure_separate_storage(Path(context['root']).stat(), _support_parent().stat())
    host = _host_root(create=True)
    ensure_separate_storage(Path(context['root']).stat(), host.stat())
    backups = _private_child(host, 'Backups', True)
    storage = _private_child(backups, context['identity'], True)
    context.update(storage=str(storage), firmware=firmware)
    sessions = _session_directory(create=True)
    token = uuid.uuid4().hex
    fd = _open_directory(sessions)
    try:
        _write_new(fd, token + '.json', _json_bytes(context))
        os.fsync(fd)
    finally:
        os.close(fd)
    reference = 'card:' + token
    # Repeat identity confirmation through the same adapter used by later writes.
    with _Workspace(reference):
        pass
    return reference


def session_context(reference):
    from inkkit_config import _open_directory, _read_at, parse_object
    token = reference.removeprefix('card:')
    if not reference.startswith('card:') or not re.fullmatch(r'[0-9a-f]{32}', token):
        raise _error('session', 'Open the card again to create a valid session.')
    fd = _open_directory(_session_directory())
    try:
        saved = parse_object(_read_at(fd, token + '.json')[0])
    finally:
        os.close(fd)
    if not schema.supports_configuration(saved.get('model'), saved.get('firmware')):
        raise _error('profile', 'This card session has an unsupported firmware profile.')
    current = _inspect(saved.get('root', ''), saved['model'])
    if current['live'] != saved.get('live') or current['identity'] != saved.get('identity'):
        raise _error('card_changed', 'The card or its mount changed. Reopen it and review settings again.')
    expected = _host_root() / 'Backups' / current['identity']
    if saved.get('storage') != str(expected):
        raise _error('private_storage', 'The session recovery location is invalid.')
    hostfd = _open_directory(expected)
    try:
        info = os.fstat(hostfd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise _error('private_storage', 'The recovery directory permissions changed.')
        ensure_separate_storage(Path(current['root']).stat(), info)
    finally:
        os.close(hostfd)
    current['storage'] = str(expected)
    return current


def _eject_command(disk):
    if os.environ.get('XTEINK_TESTING') == '1':
        raise _error('test_guard', 'Real ejection is disabled during automated tests.')
    try:
        subprocess.run(['/usr/sbin/diskutil', 'eject', disk], capture_output=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        raise _error('eject', 'macOS could not eject this card. Close files using it and try again.') from None


def eject_card(reference):
    from inkkit_config import _Workspace
    with ExitStack() as host_lock:
        with _Workspace(reference) as workspace:
            if workspace.synthetic:
                raise _error('session', 'Synthetic workspaces are not physical cards.')
            # The lock owns an independent Mac-side descriptor. Keep it while
            # closing ALL workspace handles, including those on the SD card.
            host_lock.enter_context(workspace.lock())
            expected = workspace.context
        # Recheck through metadata queries, without reopening card directories.
        current = session_context(reference)
        if current['live'] != expected['live'] or current['identity'] != expected['identity']:
            raise _error('card_changed', 'The card or its mount changed. Reopen it before ejecting.')
        _eject_command(current['live']['disk'])
    return dict(ejected=True)


def backup_location(reference):
    return str(Path(session_context(reference)['storage']))
