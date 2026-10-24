"""CrossInk configuration transactions for explicit card sessions or synthetic demos.

Only allowlisted configuration stores are editable; there is no formatting entry point.
The migration CLI deliberately does not import this preview module.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

import inkkit_schema as schema
import inkkit_codec as codec
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

PROFILE = schema.PROFILE_ID
UPSTREAM_COMMIT = schema.UPSTREAM_COMMIT
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
    maximum: int = 255
    choices: object = ()
    readonly: str = ''
    section: str = ''
    step: int = 1

    def validate(self, value):
        try:
            codec.validate(self.public(), value)
        except ValueError as error:
            raise ConfigError('invalid_value', str(error)) from None

    def public(self):
        return dict(key=self.key, label=self.label, group=self.group, kind=self.kind,
                    default=self.default, minimum=self.minimum, maximum=self.maximum,
                    choices=self.choices, readonly=self.readonly, section=self.section or self.group.capitalize(),
                    step=self.step)


FIELDS = tuple(Field(**field) for field in schema.main_fields('X3', {}))
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


def _document(data, store='settings'):
    if data is None:
        doc = {'path': ''} if store == 'dictionary' else {}
    elif store == 'dictionary':
        try:
            doc = {'path': data.decode('utf-8')}
        except UnicodeError:
            raise ConfigError('invalid_json', 'The dictionary path is not valid UTF-8.') from None
    else:
        doc = parse_object(data)
    if store == 'settings' and any(key in doc for key in ('lineSpacing', 'screenMargin', 'sleepTimeout')):
        raise ConfigError('legacy_settings', 'Legacy settings need firmware migration before editing.')
    try:
        codec.validate_document(doc, store)
    except (ValueError, TypeError, KeyError, IndexError):
        raise ConfigError('invalid_value', 'This saved configuration has an unsupported structure or field type. Preserve it and let the firmware migrate it before editing.') from None
    return doc


def _encoded(doc, store):
    return doc['path'].encode('utf-8') if store == 'dictionary' else _json_bytes(doc)


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
    # _CS_DARWIN_USER_TEMP_DIR is 65537 in the macOS SDK's unistd.h.
    # Restricted environments may return TMPDIR instead of the OS user directory.
    # Accept only the canonical user-temp layout, never an arbitrary nested path.
    if sys.platform != 'darwin':
        raise ConfigError('platform', 'This configuration preview requires macOS.')
    try:
        raw = os.confstr(65537)
        if not raw:
            raise ValueError('missing')
        temp = Path(raw).resolve()
        parts = temp.relative_to('/private/var/folders').parts
        if (len(parts) != 3 or len(parts[0]) != 2 or parts[-1] != 'T'
                or temp.stat().st_uid != os.getuid()
                or temp.stat().st_dev != Path('/private/tmp').stat().st_dev):
            raise ValueError('location')
    except (OSError, ValueError):
        raise ConfigError('unsafe_workspace', 'The system temporary directory is unavailable or is not on the expected host storage.') from None
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


def _read_at(directory, name, require_owner=True):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        info = os.fstat(fd)
        parent = os.fstat(directory)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_dev != parent.st_dev
                or (require_owner and info.st_uid != os.getuid()) or info.st_size > MAX_BYTES):
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
    def __init__(self, root, store='settings', model=None):
        self.reference = str(root)
        self.root = Path(root)
        self.store = store
        self.model = model
        self.fd = self.config = self.hostfd = None
        self.synthetic = not self.reference.startswith('card:')
        self.context = None

    def __enter__(self):
        try:
            if self.store not in schema.STORES:
                raise ConfigError('store', 'Choose a supported configuration category.')
            if self.synthetic:
                temp = _host_temp()
                if self.root.parent != temp or not re.fullmatch(r'inkkit-preview-[a-z0-9_]{8}', self.root.name):
                    raise ConfigError('synthetic_only', 'Open an SD card explicitly, or choose a synthetic demo created by this app.')
                self.fd = _open_directory(self.root)
                info = os.fstat(self.fd)
                if info.st_dev != temp.stat().st_dev or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                    raise ConfigError('unsafe_workspace', 'The synthetic workspace identity or permissions changed.')
                marker = parse_object(_read_at(self.fd, '.inkkit-preview.json')[0])
                expected = dict(format=FORMAT, identity=_identity(info), profile=PROFILE)
                if {key: marker.get(key) for key in expected} != expected:
                    raise ConfigError('unsafe_workspace', 'The synthetic workspace identity or profile changed.')
                self.model = self.model or marker.get('model', 'X3')
                self.hostfd = self.fd
                self.record_identity = _identity(info)
            else:
                import inkkit_volume
                self.context = inkkit_volume.session_context(self.reference)
                if self.model is not None and self.model != self.context['model']:
                    raise ConfigError('profile', 'The selected model differs from this card session.')
                self.model = self.context['model']
                self.root = Path(self.context['root'])
                self.fd = _open_directory(self.root)
                info = os.fstat(self.fd)
                self.hostfd = _open_directory(self.context['storage'])
                self.record_identity = self.context['identity']
                inkkit_volume.ensure_separate_storage(info, os.fstat(self.hostfd))
            if self.model not in schema.MODELS:
                raise ConfigError('profile', 'Choose a supported XTEINK model.')
            self.filename = schema.STORES[self.store][0]
            self.config = os.open('.crosspoint', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.fd)
            config_info = os.fstat(self.config)
            if config_info.st_dev != info.st_dev or (self.synthetic and config_info.st_uid != os.getuid()):
                raise ConfigError('unsafe_workspace', 'The configuration directory identity changed.')
            self.identity = _identity(info)
            self.config_identity = _identity(config_info)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        for fd in {fd for fd in (self.config, self.fd, self.hostfd) if fd is not None}:
            os.close(fd)
        self.config = self.fd = self.hostfd = None

    def live(self):
        with _Workspace(self.reference, self.store, self.model) as current:
            if current.identity != self.identity or current.config_identity != self.config_identity or current.record_identity != self.record_identity:
                raise ConfigError('external_change', 'The card or workspace changed. Reload before continuing.')

    def fields(self, doc):
        return tuple(Field(**field) for field in schema.store_fields(self.store, self.model, doc))

    @contextmanager
    def lock(self):
        fd = os.open('.inkkit-lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=self.hostfd)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_dev != os.fstat(self.hostfd).st_dev or info.st_uid != os.getuid()):
                raise ConfigError('unsafe_workspace', 'The configuration lock is unsafe.')
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
        try:
            raw, info = _read_at(self.config, self.filename, require_owner=self.synthetic)
        except FileNotFoundError:
            if self.store == 'settings':
                raise ConfigError('missing_settings', 'Run CrossInk once to create its namespaced settings file before editing.') from None
            raw, info = None, None
        # Existing firmware recovery evidence is never consumed or overwritten.
        for name in (self.filename + '.tmp', self.filename + '.bak'):
            try:
                os.stat(name, dir_fd=self.config, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise ConfigError('recovery_pending', 'Firmware recovery files exist. Resolve them before editing settings.')
        doc = _document(raw, self.store)
        token = dict(root=self.identity, directory=self.config_identity, file=_identity(info) if info else None,
                     sha256=digest(raw) if raw is not None else None, mtime_ns=info.st_mtime_ns if info else None, size=info.st_size if info else 0, store=self.store)
        return raw, doc, token

    def require(self, expected):
        raw, doc, token = self.snapshot()
        if expected != token:
            raise ConfigError('external_change', 'Settings changed after loading. Reload and review your changes again.')
        return raw, doc, token

    def backups(self, create=False):
        name = 'backups' if self.store == 'settings' else 'backups-' + self.store
        if create:
            try:
                os.mkdir(name, 0o700, dir_fd=self.hostfd)
                os.fsync(self.hostfd)
            except FileExistsError:
                pass
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.hostfd)
        info = os.fstat(fd)
        if info.st_dev != os.fstat(self.hostfd).st_dev or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid():
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
            record = dict(format=RECORD_FORMAT, profile=PROFILE, identity=self.record_identity, store=self.store, before_exists=raw is not None,
                          id=backup_id, created=int(time.time()), state='prepared',
                          before_sha256=digest(raw or b''), after_sha256=digest(updated or b''))
            _write_new(fd, 'before.bin', raw or b'')
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
                    or record.get('identity') != self.record_identity or record.get('store', 'settings') != self.store or record.get('id') != backup_id
                    or record.get('state') not in ('prepared', 'written', 'restoring', 'restored')
                    or type(record.get('created')) is not int
                    or type(record.get('before_exists', True)) is not bool
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
            if updated is not None:
                _write_new(self.config, name, updated)
            self.require(expected)
            if updated is None:
                os.unlink(self.filename, dir_fd=self.config)
            else:
                os.replace(name, self.filename, src_dir_fd=self.config, dst_dir_fd=self.config)
            os.fsync(self.config)
            try:
                actual = _read_at(self.config, self.filename, require_owner=self.synthetic)[0]
            except FileNotFoundError:
                actual = None
            if actual != updated:
                raise ConfigError('verification_failed', 'The written settings did not verify. Review the retained backup.')
            self.live()
        finally:
            try:
                os.unlink(name, dir_fd=self.config)
            except FileNotFoundError:
                pass


def create_demo(model='X3'):
    if model not in schema.MODELS:
        raise ConfigError('profile', 'Choose a supported XTEINK model.')
    root = Path(tempfile.mkdtemp(prefix='inkkit-preview-', dir=_host_temp())).resolve()
    os.chmod(root, 0o700)
    marker = dict(format=FORMAT, identity=_identity(root.stat()), profile=PROFILE, model=model)
    with os.fdopen(os.open(root / '.inkkit-preview.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
        handle.write(_json_bytes(marker))
    (root / '.crosspoint').mkdir(mode=0o700)
    # Firmware-like defaults, including structured bars and schema stamps.
    doc = schema.effective_settings({})
    doc['uiScale'] = 1 if 'touch' in schema.MODELS[model] else 0
    doc['deviceName'] = 'Example Reader'
    doc['tiltPageTurnDirectionSchema'] = 2
    doc['futureOption'] = dict(enabled=True, password_obf='example-opaque-preserved')
    with os.fdopen(os.open(root / '.crosspoint' / SETTINGS_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
        handle.write(_json_bytes(doc))
    return str(root)


def read_settings(root, store='settings', model=None):
    with _Workspace(root, store, model) as workspace:
        _, doc, token = workspace.snapshot()
        fields = [field.public() for field in workspace.fields(doc)]
        return dict(profile=PROFILE, firmware=schema.FIRMWARE_VERSION, synthetic=workspace.synthetic,
                    model=workspace.model, capabilities=sorted(schema.MODELS[workspace.model]), store=store, stores=[dict(id=key, label=value[1]) for key, value in schema.STORES.items()],
                    fields=fields, values=codec.values(doc, store, fields), token=token,
                    has_plaintext=_has_plaintext(doc), label='Synthetic demo' if workspace.synthetic else workspace.context['label'])


def _has_plaintext(value):
    if isinstance(value, dict):
        return bool(value.get('password')) or any(_has_plaintext(child) for key, child in value.items() if key != 'password')
    return isinstance(value, list) and any(_has_plaintext(child) for child in value)


def _plan(workspace, doc, changes, allow_plaintext=True):
    fields = [field.public() for field in workspace.fields(doc)]
    if type(changes) is not dict or any(key not in {field['key'] for field in fields} for key in changes):
        raise ConfigError('unsupported_field', 'Only supported configuration fields can be changed.')
    try:
        updated, secret = codec.patch_document(doc, workspace.store, fields, changes, allow_plaintext)
        diff = codec.differences(doc, updated, workspace.store, fields, changes)
    except (ValueError, TypeError, KeyError, IndexError) as error:
        # Codec errors are fixed public descriptions, never interpolated input.
        message = str(error) if isinstance(error, ValueError) else 'This configuration has an unsupported structure.'
        raise ConfigError('invalid_value', message) from None
    return updated, diff, secret


def preview_plan(root, expected, changes, store='settings', model=None):
    with _Workspace(root, store, model) as workspace:
        _, doc, _ = workspace.require(expected)
        updated, diff, _ = _plan(workspace, doc, changes)
        return dict(differences=diff, requires_plaintext=bool(_has_plaintext(updated)))


def preview_changes(root, expected, changes, store='settings', model=None):
    return preview_plan(root, expected, changes, store, model)['differences']


def apply_changes(root, expected, changes, store='settings', model=None, allow_plaintext=False):
    if type(allow_plaintext) is not bool:
        raise ConfigError('consent', 'Plaintext handoff requires explicit boolean consent for this apply.')
    with _Workspace(root, store, model) as workspace, workspace.lock():
        raw, doc, _ = workspace.require(expected)
        updated_doc, diff, _ = _plan(workspace, doc, changes, allow_plaintext)
        if updated_doc == doc:
            return dict(changed=False, backup_id=None, snapshot=read_settings(root, store, model))
        if _has_plaintext(updated_doc) and not allow_plaintext:
            raise ConfigError('consent', 'Explicit plaintext-handoff consent is required whenever the resulting file contains passwords.')
        updated = _encoded(updated_doc, store)
        backup_id, record = workspace.backup(raw, updated)
        try:
            workspace.replace(updated, expected)
            with workspace.record(backup_id) as (fd, record):
                record['state'] = 'written'
                _atomic_record(fd, record)
        except (OSError, ConfigError):
            raise ConfigError('apply_incomplete', 'Apply did not finish. Reload and review the retained backup before retrying.') from None
        return dict(changed=True, backup_id=backup_id, snapshot=read_settings(root, store, model))


def list_backups(root, store='settings', model=None):
    with _Workspace(root, store, model) as workspace:
        try:
            parent = workspace.backups()
        except FileNotFoundError:
            return []
        try:
            names = os.listdir(parent)
            if len(names) > 500:
                raise ConfigError('backup_limit', 'There are too many recovery records. Preserve and archive older Mac-side backups before reopening.')
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


def _restore_source(workspace, current, backup_id):
    with workspace.record(backup_id) as (fd, record):
        raw = _read_at(fd, 'before.bin')[0]
        if digest(raw) != record['before_sha256']:
            raise ConfigError('invalid_backup', 'The original configuration backup failed its integrity check.')
        original = raw if record.get('before_exists', True) else None
        doc = _document(original, workspace.store)
        if digest(current or b'') not in (record['before_sha256'], record['after_sha256']):
            raise ConfigError('external_change', 'Configuration no longer matches this backup. No files were restored.')
        return original, doc, record


def restore_requires_plaintext(root, expected, backup_id, store='settings'):
    with _Workspace(root, store) as workspace:
        current, _, _ = workspace.require(expected)
        original, before, _ = _restore_source(workspace, current, backup_id)
        return current != original and _has_plaintext(before)


def preview_restore(root, expected, backup_id, store='settings', model=None):
    with _Workspace(root, store, model) as workspace:
        current, doc, _ = workspace.require(expected)
        original, before, record = _restore_source(workspace, current, backup_id)
        fields = [field.public() for field in workspace.fields(doc)]
        diff = codec.differences(doc, before, store, fields)
        if not diff and current != original:
            diff.append(dict(key='file', label='Configuration file', before='Current file', after='Original file bytes'))
        return diff


def restore_backup(root, expected, backup_id, store='settings', model=None, allow_plaintext=False):
    if type(allow_plaintext) is not bool:
        raise ConfigError('consent', 'Plaintext handoff requires explicit boolean consent for this restore.')
    with _Workspace(root, store, model) as workspace, workspace.lock():
        current, _, _ = workspace.require(expected)
        raw, before, record = _restore_source(workspace, current, backup_id)
        if current == raw:
            return dict(changed=False, snapshot=read_settings(root, store, model))
        if _has_plaintext(before) and not allow_plaintext:
            raise ConfigError('consent', 'Explicit plaintext-handoff consent is required to restore plaintext credentials.')
        with workspace.record(backup_id) as (fd, record):
            record['state'] = 'restoring'
            _atomic_record(fd, record)
            try:
                workspace.replace(raw, expected)
                record['state'] = 'restored'
                _atomic_record(fd, record)
            except (OSError, ConfigError):
                raise ConfigError('restore_incomplete', 'Restore did not finish. Reload and review the retained backup.') from None
        return dict(changed=True, snapshot=read_settings(root, store, model))
