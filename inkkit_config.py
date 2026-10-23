"""CrossInk configuration foundation. Writes are restricted to synthetic workspaces.

No device discovery, real-card adapter, formatter or credential editor is exposed.
The migration CLI deliberately does not import this preview module.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import uuid

PROFILE = 'crossink-1.6.1-preview'
UPSTREAM_COMMIT = '9914146eeae7b46b300f475a16c32426fc02ec1f'
MAX_BYTES = 64 * 1024
SETTINGS_FILE = 'crossink-settings.json'
FORMAT = 'inkkit-synthetic-workspace-v1'
RECORD_FORMAT = 'inkkit-config-backup-v1'


class ConfigError(Exception):
    """Only fixed, public-safe descriptions cross the helper boundary."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    group: str
    kind: str
    default: object
    minimum: int = 0
    maximum: int = 1

    def validate(self, value):
        if self.kind == 'text':
            if type(value) is not str:
                raise ConfigError('invalid_value', 'A text setting has an invalid value.')
            try:
                length = len(value.encode('utf-8'))
            except UnicodeError:
                raise ConfigError('invalid_value', 'Text must be valid UTF-8.') from None
            # Empty deviceName uses the hardware name; nonempty names need 2–20 bytes.
            if (length and not 2 <= length <= 20) or any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ConfigError('invalid_value', 'Device name must be empty or 2–20 UTF-8 bytes without control characters.')
        elif type(value) is not int or not self.minimum <= value <= self.maximum:
            raise ConfigError('invalid_value', 'A numeric setting is outside its supported range or type.')

    def public(self):
        return dict(key=self.key, label=self.label, group=self.group, kind=self.kind,
                    default=self.default, minimum=self.minimum, maximum=self.maximum)


# Raw SD storage values, not Web API display indexes. Expand only with source tests.
FIELDS = (
    Field('lineHeightPercent', 'Line height', 'reading', 'integer', 100, 70, 200),
    Field('wordSpacing', 'Word spacing', 'reading', 'integer', 0, 0, 4),
    Field('screenMarginHorizontal', 'Horizontal margin', 'reading', 'integer', 5, 5, 150),
    Field('screenMarginVertical', 'Vertical margin', 'reading', 'integer', 5, 5, 150),
    Field('hyphenationEnabled', 'Hyphenation', 'reading', 'toggle', 0),
    Field('embeddedStyle', 'Use embedded styles', 'reading', 'toggle', 1),
    Field('screenInverted', 'Invert screen', 'device', 'toggle', 0),
    Field('deviceName', 'Device name', 'device', 'text', ''),
    Field('sleepTimeoutMinutes', 'Sleep after', 'device', 'integer', 10, 1, 31),
    Field('showHiddenFiles', 'Show hidden files', 'device', 'toggle', 0),
    Field('hideFileExtension', 'Hide file extensions', 'device', 'toggle', 0),
    Field('trackReadingStats', 'Track reading statistics', 'device', 'toggle', 1),
)
BY_KEY = {field.key: field for field in FIELDS}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def parse_object(data):
    """Bounded strict JSON; error details never contain raw settings or paths."""
    try:
        if not isinstance(data, bytes) or len(data) > MAX_BYTES:
            raise ValueError('size')
        value = json.loads(data.decode('utf-8'), object_pairs_hook=_pairs,
                           parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite')))
        if type(value) is not dict:
            raise ValueError('object required')
        # Reject unpaired surrogates, including in unknown fields that we preserve.
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
        return value
    except (ValueError, UnicodeError, RecursionError, TypeError):
        raise ConfigError('invalid_json', 'Settings must be a bounded, valid UTF-8 JSON object without duplicate keys.') from None


def _document(data):
    doc = parse_object(data)
    for field in FIELDS:
        if field.key in doc:
            field.validate(doc[field.key])
    # Legacy aliases have different semantics. Do not silently import defaults.
    if any(key in doc for key in ('lineSpacing', 'screenMargin', 'sleepTimeout')):
        raise ConfigError('legacy_settings', 'Legacy settings need firmware migration before this preview can edit them.')
    return doc


def _json_bytes(value):
    try:
        data = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode('utf-8')
        if len(data) > MAX_BYTES:
            raise ValueError('size')
        return data
    except (ValueError, UnicodeError, TypeError, RecursionError):
        raise ConfigError('invalid_json', 'The resulting settings exceed the supported JSON limits.') from None


def _identity(info):
    return [info.st_dev, info.st_ino]


def _host_temp():
    # Darwin's user temp directory comes from the OS, not caller-controlled TMPDIR.
    # _CS_DARWIN_USER_TEMP_DIR is 65537 in the macOS SDK's unistd.h.
    if sys.platform != 'darwin':
        raise ConfigError('platform', 'This configuration preview requires macOS.')
    raw = os.confstr(65537)
    if not raw:
        raise ConfigError('unsafe_workspace', 'The system temporary directory is unavailable.')
    temp = Path(raw).resolve()
    if (not temp.is_relative_to(Path('/private/var/folders'))
            or temp.stat().st_dev != Path('/private/tmp').stat().st_dev):
        raise ConfigError('unsafe_workspace', 'The system temporary directory is not on the expected host storage.')
    return temp


def _open_directory(path):
    """Open each component with O_NOFOLLOW, retaining descriptors across IO."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ConfigError('unsafe_workspace', 'Choose a workspace created by this preview.')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read_at(directory, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        info = os.fstat(fd)
        parent = os.fstat(directory)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_dev != parent.st_dev
                or info.st_uid != os.getuid() or info.st_size > MAX_BYTES):
            raise ConfigError('unsafe_file', 'A configuration or backup file is not a safe regular file.')
        chunks, size = [], 0
        while True:
            chunk = os.read(fd, min(8192, MAX_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_BYTES:
                raise ConfigError('invalid_json', 'A configuration or backup file exceeds its size limit.')
        after = os.fstat(fd)
        if (info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ConfigError('external_change', 'A file changed while being read. Reload the workspace.')
        return b''.join(chunks), after
    finally:
        os.close(fd)


def _write_new(directory, name, data):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        view = memoryview(data)
        while view:
            count = os.write(fd, view)
            if count <= 0:
                raise OSError('short write')
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_record(directory, record):
    name = '.record-' + uuid.uuid4().hex
    try:
        _write_new(directory, name, _json_bytes(record))
        os.replace(name, 'record.json', src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        try:
            os.unlink(name, dir_fd=directory)
        except FileNotFoundError:
            pass


class _Workspace:
    def __init__(self, root):
        self.root = Path(root)
        self.fd = self.config = None

    def __enter__(self):
        try:
            temp = _host_temp()
            if self.root.parent != temp or not re.fullmatch(r'inkkit-preview-[a-z0-9_]{8}', self.root.name):
                raise ConfigError('synthetic_only', 'This developer preview opens only its own synthetic workspaces; SD cards are disabled.')
            self.fd = _open_directory(self.root)
            info = os.fstat(self.fd)
            if (info.st_dev != temp.stat().st_dev or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o700):
                raise ConfigError('unsafe_workspace', 'The synthetic workspace identity or permissions changed.')
            marker = parse_object(_read_at(self.fd, '.inkkit-preview.json')[0])
            if marker != dict(format=FORMAT, identity=_identity(info), profile=PROFILE):
                raise ConfigError('unsafe_workspace', 'The synthetic workspace identity or profile changed.')
            self.config = os.open('.crosspoint', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.fd)
            config_info = os.fstat(self.config)
            if config_info.st_dev != info.st_dev or config_info.st_uid != os.getuid():
                raise ConfigError('unsafe_workspace', 'The configuration directory identity changed.')
            self.identity = _identity(info)
            self.config_identity = _identity(config_info)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        for fd in (self.config, self.fd):
            if fd is not None:
                os.close(fd)

    def live(self):
        with _Workspace(self.root) as current:
            if current.identity != self.identity or current.config_identity != self.config_identity:
                raise ConfigError('external_change', 'The workspace changed. Reload before continuing.')

    @contextmanager
    def lock(self):
        fd = os.open('.inkkit-lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=self.fd)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_dev != os.fstat(self.fd).st_dev
                    or info.st_uid != os.getuid()):
                raise ConfigError('unsafe_workspace', 'The workspace lock is unsafe.')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ConfigError('busy', 'Another configuration operation is running. Try again after it finishes.') from None
            self.live()
            yield
        finally:
            os.close(fd)

    def snapshot(self):
        self.live()
        raw, info = _read_at(self.config, SETTINGS_FILE)
        # Existing firmware recovery evidence is never consumed or overwritten.
        for name in (SETTINGS_FILE + '.tmp', SETTINGS_FILE + '.bak'):
            try:
                os.stat(name, dir_fd=self.config, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise ConfigError('recovery_pending', 'Firmware recovery files exist. Resolve them before editing settings.')
        doc = _document(raw)
        token = dict(root=self.identity, directory=self.config_identity, file=_identity(info),
                     sha256=digest(raw), mtime_ns=info.st_mtime_ns, size=info.st_size)
        return raw, doc, token

    def require(self, expected):
        raw, doc, token = self.snapshot()
        if expected != token:
            raise ConfigError('external_change', 'Settings changed after loading. Reload and review your changes again.')
        return raw, doc, token

    def backups(self, create=False):
        if create:
            try:
                os.mkdir('backups', 0o700, dir_fd=self.fd)
                os.fsync(self.fd)
            except FileExistsError:
                pass
        fd = os.open('backups', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.fd)
        info = os.fstat(fd)
        if info.st_dev != os.fstat(self.fd).st_dev or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid():
            os.close(fd)
            raise ConfigError('unsafe_file', 'The backup directory identity or permissions changed.')
        return fd

    def backup(self, raw, updated):
        parent = self.backups(create=True)
        fd = None
        try:
            backup_id = uuid.uuid4().hex
            os.mkdir(backup_id, 0o700, dir_fd=parent)
            fd = os.open(backup_id, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            record = dict(format=RECORD_FORMAT, profile=PROFILE, identity=self.identity,
                          id=backup_id, created=int(time.time()), state='prepared',
                          before_sha256=digest(raw), after_sha256=digest(updated))
            _write_new(fd, 'before.bin', raw)
            _atomic_record(fd, record)
            if digest(_read_at(fd, 'before.bin')[0]) != record['before_sha256']:
                raise ConfigError('backup_failed', 'The original settings backup did not verify. No settings were changed.')
            os.fsync(parent)
            return backup_id, record
        finally:
            if fd is not None:
                os.close(fd)
            os.close(parent)

    @contextmanager
    def record(self, backup_id):
        if type(backup_id) is not str or not re.fullmatch(r'[0-9a-f]{32}', backup_id):
            raise ConfigError('invalid_backup', 'Choose a backup from this workspace.')
        parent = self.backups()
        fd = None
        try:
            fd = os.open(backup_id, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            info = os.fstat(fd)
            if info.st_dev != os.fstat(parent).st_dev or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise ConfigError('invalid_backup', 'The backup directory is unsafe.')
            record = parse_object(_read_at(fd, 'record.json')[0])
            if (record.get('format') != RECORD_FORMAT or record.get('profile') != PROFILE
                    or record.get('identity') != self.identity or record.get('id') != backup_id
                    or record.get('state') not in ('prepared', 'written', 'restoring', 'restored')
                    or type(record.get('created')) is not int
                    or any(not isinstance(record.get(key), str) or not re.fullmatch(r'[0-9a-f]{64}', record[key])
                           for key in ('before_sha256', 'after_sha256'))):
                raise ConfigError('invalid_backup', 'The backup record is invalid or belongs to another workspace.')
            yield fd, record
        finally:
            if fd is not None:
                os.close(fd)
            os.close(parent)

    def replace(self, updated, expected):
        name = '.inkkit-write-' + uuid.uuid4().hex
        try:
            _write_new(self.config, name, updated)
            self.require(expected)
            os.replace(name, SETTINGS_FILE, src_dir_fd=self.config, dst_dir_fd=self.config)
            os.fsync(self.config)
            if _read_at(self.config, SETTINGS_FILE)[0] != updated:
                raise ConfigError('verification_failed', 'The written settings did not verify. Review the retained backup.')
            self.live()
        finally:
            try:
                os.unlink(name, dir_fd=self.config)
            except FileNotFoundError:
                pass


def create_demo():
    root = Path(tempfile.mkdtemp(prefix='inkkit-preview-', dir=_host_temp())).resolve()
    os.chmod(root, 0o700)
    with os.fdopen(os.open(root / '.inkkit-preview.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
        handle.write(_json_bytes(dict(format=FORMAT, identity=_identity(root.stat()), profile=PROFILE)))
    (root / '.crosspoint').mkdir(mode=0o700)
    doc = {field.key: field.default for field in FIELDS}
    doc['deviceName'] = 'Example Reader'
    doc['futureOption'] = dict(enabled=True, password_obf='example-opaque-preserved')
    with os.fdopen(os.open(root / '.crosspoint' / SETTINGS_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
        handle.write(_json_bytes(doc))
    return str(root)


def read_settings(root):
    with _Workspace(root) as workspace:
        _, doc, token = workspace.snapshot()
        return dict(profile=PROFILE, synthetic=True, fields=[field.public() for field in FIELDS],
                    values={field.key: doc.get(field.key, field.default) for field in FIELDS}, token=token)


def _changes(doc, changes):
    if type(changes) is not dict or any(key not in BY_KEY for key in changes):
        raise ConfigError('unsupported_field', 'Only the supported non-credential settings can be changed.')
    result = []
    for field in FIELDS:
        if field.key not in changes:
            continue
        value = changes[field.key]
        field.validate(value)
        before = doc.get(field.key, field.default)
        if before != value:
            result.append(dict(key=field.key, label=field.label, before=before, after=value))
    return result


def preview_changes(root, expected, changes):
    with _Workspace(root) as workspace:
        _, doc, _ = workspace.require(expected)
        return _changes(doc, changes)


def apply_changes(root, expected, changes):
    with _Workspace(root) as workspace, workspace.lock():
        raw, doc, _ = workspace.require(expected)
        diff = _changes(doc, changes)
        if not diff:
            return dict(changed=False, backup_id=None, snapshot=read_settings(root))
        for entry in diff:
            doc[entry['key']] = entry['after']
        updated = _json_bytes(doc)
        backup_id, record = workspace.backup(raw, updated)
        try:
            workspace.replace(updated, expected)
            with workspace.record(backup_id) as (fd, record):
                record['state'] = 'written'
                _atomic_record(fd, record)
        except (OSError, ConfigError):
            raise ConfigError('apply_incomplete', 'Apply did not finish. Reload and review the retained backup before retrying.') from None
        return dict(changed=True, backup_id=backup_id, snapshot=read_settings(root))


def list_backups(root):
    with _Workspace(root) as workspace:
        try:
            parent = workspace.backups()
        except FileNotFoundError:
            return []
        try:
            names = os.listdir(parent)
            if len(names) > 500:
                raise ConfigError('backup_limit', 'This workspace has too many backup entries. Start a new synthetic demo.')
        finally:
            os.close(parent)
        records = []
        for name in names:
            if not re.fullmatch(r'[0-9a-f]{32}', name):
                continue
            try:
                with workspace.record(name) as (_, record):
                    records.append({key: record[key] for key in ('id', 'created', 'state')})
            except (OSError, ConfigError):
                # A failed backup must not hide other usable recovery records.
                # Never follow unsafe entries or offer to restore incomplete data.
                records.append(dict(id=name, created=0, state='unavailable'))
        return sorted(records, key=lambda record: (record['created'], record['id']), reverse=True)


def preview_restore(root, expected, backup_id):
    with _Workspace(root) as workspace:
        current, doc, _ = workspace.require(expected)
        with workspace.record(backup_id) as (fd, record):
            raw = _read_at(fd, 'before.bin')[0]
            original = _document(raw)
            if digest(raw) != record['before_sha256']:
                raise ConfigError('invalid_backup', 'The original settings backup failed its integrity check.')
            if digest(current) not in (record['before_sha256'], record['after_sha256']):
                raise ConfigError('external_change', 'Settings no longer match this backup. No files were restored.')
            return _changes(doc, {field.key: original.get(field.key, field.default) for field in FIELDS})


def restore_backup(root, expected, backup_id):
    with _Workspace(root) as workspace, workspace.lock():
        current, _, _ = workspace.require(expected)
        with workspace.record(backup_id) as (fd, record):
            raw = _read_at(fd, 'before.bin')[0]
            _document(raw)
            if digest(raw) != record['before_sha256']:
                raise ConfigError('invalid_backup', 'The original settings backup failed its integrity check.')
            if digest(current) == record['before_sha256']:
                return dict(changed=False, snapshot=read_settings(root))
            if digest(current) != record['after_sha256']:
                raise ConfigError('external_change', 'Settings no longer match this backup. No files were restored.')
            record['state'] = 'restoring'
            _atomic_record(fd, record)
            try:
                workspace.replace(raw, expected)
                record['state'] = 'restored'
                _atomic_record(fd, record)
            except (OSError, ConfigError):
                raise ConfigError('restore_incomplete', 'Restore did not finish. Reload and review the retained backup.') from None
        return dict(changed=True, snapshot=read_settings(root))
