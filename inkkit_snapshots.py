"""Complete six-store configuration snapshots. Private host IO only; no formatter.

Restore is reviewed against fresh tokens and writes each file atomically, but six
files cannot be one filesystem transaction. A complete original snapshot and an
interruption record are retained before any writes. Never inject faults on media.
"""
from contextlib import contextmanager, ExitStack
import fcntl
import json
import math
import os
from pathlib import Path
import re
import stat
import time
import uuid

import inkkit_config as config
import inkkit_codec as codec
import inkkit_schema as schema
import inkkit_volume as volume

FORMAT = 'inkkit-configuration-snapshot-v1'
OPERATION = 'inkkit-configuration-restore-v1'
NAMES = {store: store + '.bin' for store in schema.STORES}
PENDING = {'prepared', 'writing', 'failed'}


def error(code, message):
    return config.ConfigError(code, message)


def _id(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{32}', value):
        raise error('snapshot', 'Choose a valid local configuration backup.')
    return value


def _location(root=None, create=False):
    if root is not None and not str(root).startswith('card:'):
        with config._Workspace(root) as workspace:
            return volume._private_child(workspace.root, 'ConfigurationBackups', create)
    return volume._private_child(volume._host_root(create), 'ConfigurationBackups', create)


@contextmanager
def _collection(root=None, create=False):
    location = _location(root, create)
    fd = config._open_directory(location)
    lock = None
    try:
        lock = os.open('.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        info = os.fstat(lock)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_dev != os.fstat(fd).st_dev):
            raise error('snapshot', 'The local backup lock is unsafe.')
        if root is not None and str(root).startswith('card:'):
            with config._Workspace(root) as workspace:
                volume.ensure_separate_storage(os.fstat(workspace.fd), os.fstat(fd))
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise error('busy', 'Another backup operation is running. Try again after it finishes.') from None
        yield fd, fd
    finally:
        if lock is not None:
            os.close(lock)
        os.close(fd)


@contextmanager
def _directory(location, name, create=False):
    name = _id(name)
    if create:
        os.mkdir(name, 0o700, dir_fd=location)
        os.fsync(location)
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=location)
    try:
        info = os.fstat(fd)
        if (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700
                or info.st_dev != os.fstat(location).st_dev):
            raise error('snapshot', 'The backup directory identity or permissions are unsafe.')
        yield fd
    finally:
        os.close(fd)


def _owner(workspace):
    return workspace.context['identity'] if not workspace.synthetic else config.digest(json.dumps(workspace.identity).encode())


@contextmanager
def _workspaces(root):
    with ExitStack() as stack:
        primary = stack.enter_context(config._Workspace(root))
        stack.enter_context(primary.lock())
        workspaces = {'settings': primary}
        for store in schema.STORES:
            if store != 'settings':
                workspaces[store] = stack.enter_context(config._Workspace(root, store))
        yield workspaces


def _read_all(workspaces):
    result = {store: workspace.snapshot() for store, workspace in workspaces.items()}
    for store, workspace in workspaces.items():
        workspace.require(result[store][2])
    return result


def _load(location, identifier):
    with _directory(location, identifier) as fd:
        raw = config._read_at(fd, 'manifest.json')[0]
        manifest = config.parse_object(raw)
        if (manifest.get('format') != FORMAT or manifest.get('id') != identifier
                or manifest.get('profile') != config.PROFILE
                or not schema.supports_configuration(manifest.get('model'), manifest.get('firmware'))
                or type(manifest.get('created')) not in (int, float)
                or not math.isfinite(manifest['created']) or manifest['created'] <= 0
                or manifest.get('reason') not in ('manual', 'before_apply', 'before_restore')
                or type(manifest.get('synthetic')) is not bool
                or type(manifest.get('owner')) is not str
                or not re.fullmatch('[0-9a-f]{64}', manifest['owner'])
                or type(manifest.get('files')) is not dict or set(manifest['files']) != set(NAMES)):
            raise error('snapshot', 'This configuration backup has invalid or unsupported metadata.')
        content = {}
        for store, name in NAMES.items():
            record = manifest['files'][store]
            if type(record) is not dict or type(record.get('exists')) is not bool:
                raise error('snapshot', 'The configuration backup file inventory is invalid.')
            if not record['exists']:
                if record != dict(exists=False, sha256=None, size=0):
                    raise error('snapshot', 'The absent-file backup record is invalid.')
                try:
                    os.stat(name, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise error('snapshot', 'An absent backup file unexpectedly exists.')
                content[store] = None
            else:
                data = config._read_at(fd, name)[0]
                if (type(record.get('size')) is not int or len(data) != record['size']
                        or config.digest(data) != record.get('sha256')):
                    raise error('snapshot', 'A configuration backup failed its checksum check.')
                config._document(data, store)
                content[store] = data
        if content['settings'] is None:
            raise error('snapshot', 'The complete backup is missing its main settings file.')
        return manifest, content, config.digest(raw)


def _capture(location, workspaces, reason):
    values = _read_all(workspaces)
    identifier = uuid.uuid4().hex
    primary = workspaces['settings']
    manifest = dict(format=FORMAT, id=identifier, created=time.time(), reason=reason,
                    model=primary.model, firmware=schema.FIRMWARE_VERSION, profile=config.PROFILE,
                    owner=_owner(primary), synthetic=primary.synthetic,
                    files={store: dict(exists=raw is not None, sha256=config.digest(raw) if raw is not None else None,
                                       size=len(raw) if raw is not None else 0)
                           for store, (raw, _, _) in values.items()})
    with _directory(location, identifier, True) as fd:
        for store, (raw, _, _) in values.items():
            if raw is not None:
                config._write_new(fd, NAMES[store], raw)
        config._write_new(fd, 'manifest.json', config._json_bytes(manifest))
        os.fsync(fd)
    _load(location, identifier)
    for store, workspace in workspaces.items():
        workspace.require(values[store][2])
    return manifest


def create_snapshot(root, reason='manual'):
    if reason not in ('manual', 'before_apply'):
        raise error('snapshot', 'This backup reason is unsupported.')
    with _workspaces(root) as workspaces, _collection(root, True) as (location, _):
        manifest = _capture(location, workspaces, reason)
    return dict(created=True, backup_id=manifest['id'])


def _operation_directory(workspace, create=False):
    parent = workspace.root if workspace.synthetic else Path(workspace.context['storage'])
    return volume._private_child(parent, 'ConfigurationRestore', create)


def ensure_no_pending(root):
    with config._Workspace(root) as workspace:
        try:
            fd = config._open_directory(_operation_directory(workspace))
        except FileNotFoundError:
            return
        try:
            record = config.parse_object(config._read_at(fd, 'record.json')[0])
        finally:
            os.close(fd)
        if record.get('format') != OPERATION or record.get('state') != 'completed':
            raise error('snapshot_pending', 'A complete-settings restore needs attention. Open Backups and review a complete backup restore before applying individual settings.')


def _operations(location):
    for name in os.listdir(location):
        if not re.fullmatch('[0-9a-f]{32}', name):
            continue
        with _directory(location, name) as fd:
            try:
                record = config.parse_object(config._read_at(fd, 'record.json')[0])
            except FileNotFoundError:
                continue
            if record.get('format') != OPERATION or record.get('state') not in PENDING | {'completed', 'resolved'}:
                raise error('snapshot', 'A backup recovery record is invalid. Preserve local backups for inspection.')
            yield name, record


def list_snapshots(root=None):
    selected = None
    if root is not None:
        with config._Workspace(root) as workspace:
            selected = (workspace.model, schema.FIRMWARE_VERSION, workspace.synthetic)
    try:
        with _collection(root) as (location, _):
            protected = set()
            for identifier, operation in _operations(location):
                if operation['state'] in PENDING:
                    protected.update((identifier, operation['target']))
            result = []
            for name in os.listdir(location):
                if not re.fullmatch('[0-9a-f]{32}', name):
                    continue
                try:
                    manifest, _, token = _load(location, name)
                except (config.ConfigError, OSError):
                    result.append(dict(id=name, created=0, state='unavailable', kind='complete', model='Unknown',
                                       reason='manual', can_restore=False, can_delete=False, checksum=''))
                    continue
                compatible = selected == (manifest['model'], manifest['firmware'], manifest['synthetic'])
                result.append(dict(id=name, created=manifest['created'], state='verified', kind='complete',
                                   model=manifest['model'], firmware=manifest['firmware'], reason=manifest['reason'],
                                   can_restore=compatible, can_delete=name not in protected, checksum=token))
            return sorted(result, key=lambda entry: (entry['created'], entry['id']), reverse=True)
    except FileNotFoundError:
        return []


def _compatible(manifest, primary):
    if (manifest['model'] != primary.model or manifest['firmware'] != schema.FIRMWARE_VERSION
            or manifest['synthetic'] != primary.synthetic):
        raise error('snapshot_profile', 'Open a card or demo with the same reviewed reader model and firmware as this backup. Restore is for the same original reader, not a different device.')


def _needs_recovery(location, workspace):
    owner = _owner(workspace)
    pending = any(record.get('owner') == owner and record['state'] in PENDING
                  for _, record in _operations(location))
    try:
        fd = config._open_directory(_operation_directory(workspace))
    except FileNotFoundError:
        return pending
    try:
        record = config.parse_object(config._read_at(fd, 'record.json')[0])
    finally:
        os.close(fd)
    if (record.get('format') != OPERATION or record.get('owner') != owner
            or record.get('state') not in PENDING | {'completed'}):
        raise error('snapshot', 'The active recovery record is invalid. Preserve local backups for inspection.')
    return pending or record['state'] in PENDING


def _plan(workspaces, manifest, content, fingerprint, recovery=False):
    _compatible(manifest, workspaces['settings'])
    current = _read_all(workspaces)
    differences, fields = [], []
    for store, workspace in workspaces.items():
        raw, before, _ = current[store]
        after = config._document(content[store], store)
        descriptors = [field.public() for field in workspace.fields(before)]
        rows = codec.differences(before, after, store, descriptors)
        for field in descriptors:
            field = dict(field)
            field['key'] = store + '.' + field['key']
            fields.append(field)
        for row in rows:
            row['key'] = store + '.' + row['key']
            row['label'] = schema.STORES[store][1] + ' — ' + row['label']
        if raw != content[store]:
            # A separate row makes unknown data and absent/empty distinctions
            # explicit without exposing arbitrary stored values or credentials.
            rows.append(dict(key=store + '.__file__', label=schema.STORES[store][1] + ' — exact saved file',
                             before='Current file' if raw is not None else 'File absent',
                             after='File from backup' if content[store] is not None else 'File absent'))
        differences.extend(rows)
    if recovery:
        differences.append(dict(key='__recovery__', label='Interrupted complete restore',
                                before='Completion needs verification', after='Verify all files and finish recovery'))
    plaintext = any(config._has_plaintext(config._document(raw, store))
                    for store, raw in content.items() if raw is not None)
    return dict(differences=differences, fields=fields, requires_plaintext=plaintext,
                expected={store: value[2] for store, value in current.items()}, backup_sha256=fingerprint)


def preview_restore(root, identifier):
    with _workspaces(root) as workspaces, _collection(root) as (location, _):
        manifest, content, token = _load(location, _id(identifier))
        return _plan(workspaces, manifest, content, token, _needs_recovery(location, workspaces['settings']))


def _replace(workspace, raw, expected):
    workspace.require(expected)
    if raw is None:
        if expected['file'] is not None:
            os.unlink(workspace.filename, dir_fd=workspace.config)
    else:
        temporary = '.inkkit-restore-' + uuid.uuid4().hex
        try:
            config._write_new(workspace.config, temporary, raw)
            workspace.require(expected)
            os.replace(temporary, workspace.filename, src_dir_fd=workspace.config, dst_dir_fd=workspace.config)
        finally:
            try:
                os.unlink(temporary, dir_fd=workspace.config)
            except FileNotFoundError:
                pass
    os.fsync(workspace.config)
    if workspace.snapshot()[0] != raw:
        raise error('snapshot_verify', 'A restored configuration failed readback verification.')


def restore_snapshot(root, identifier, expected, backup_sha256, allow_plaintext=False):
    with _workspaces(root) as workspaces, _collection(root) as (location, _):
        manifest, content, token = _load(location, _id(identifier))
        plan = _plan(workspaces, manifest, content, token, _needs_recovery(location, workspaces['settings']))
        if expected != plan['expected'] or backup_sha256 != token:
            raise error('external_change', 'Configurations or the selected backup changed after review. Reload and review the complete restore again.')
        if plan['requires_plaintext'] and allow_plaintext is not True:
            raise error('plaintext_consent', 'Explicit consent is required to restore plaintext credentials.')
        if not plan['differences']:
            return dict(changed=False, backup_id=None)
        before = _capture(location, workspaces, 'before_restore')
        # The backup scan can take time. Recheck every reviewed file before the
        # first replacement, including files which will not need a write.
        for store, workspace in workspaces.items():
            workspace.require(expected[store])
        operation = dict(format=OPERATION, owner=_owner(workspaces['settings']), state='prepared',
                         target=identifier, before=before['id'], written=[], current=None)
        with _directory(location, before['id']) as before_fd:
            active_fd = config._open_directory(_operation_directory(workspaces['settings'], True))
            try:
                config._atomic_record(before_fd, operation)
                config._atomic_record(active_fd, operation)
                try:
                    for store, workspace in workspaces.items():
                        if workspace.snapshot()[0] == content[store]:
                            continue
                        operation.update(state='writing', current=store)
                        config._atomic_record(before_fd, operation)
                        config._atomic_record(active_fd, operation)
                        _replace(workspace, content[store], expected[store])
                        operation['written'].append(store)
                        config._atomic_record(before_fd, operation)
                        config._atomic_record(active_fd, operation)
                    if any(workspace.snapshot()[0] != content[store] for store, workspace in workspaces.items()):
                        raise error('snapshot_verify', 'Complete configuration readback did not match the backup.')
                    operation.update(state='completed', current=None)
                    config._atomic_record(before_fd, operation)
                    config._atomic_record(active_fd, operation)
                    for name, old in list(_operations(location)):
                        if old.get('owner') == operation['owner'] and old['state'] in PENDING:
                            old['state'] = 'resolved'
                            with _directory(location, name) as fd:
                                config._atomic_record(fd, old)
                except Exception:
                    operation['state'] = 'failed'
                    try:
                        config._atomic_record(before_fd, operation)
                        config._atomic_record(active_fd, operation)
                    except OSError:
                        pass
                    raise error('snapshot_interrupted', 'The complete restore stopped; some files may already be restored. The original complete backup is retained and protected. Open Backups, review the pre-restore backup to recover, or review the selected backup again to retry.') from None
            finally:
                os.close(active_fd)
        return dict(changed=True, backup_id=before['id'])


def delete_snapshot(identifier, checksum, root=None):
    identifier = _id(identifier)
    with _collection(root) as (location, parent):
        protected = set()
        for name, operation in _operations(location):
            if operation['state'] in PENDING:
                protected.update((name, operation['target']))
        if identifier in protected:
            raise error('snapshot_pending', 'This backup protects an interrupted restore. Complete a reviewed recovery restore before deleting it.')
        _, _, actual = _load(location, identifier)
        if checksum != actual:
            raise error('external_change', 'The selected backup changed. Reload Backups before deleting it.')
        with _directory(location, identifier) as fd:
            names = set(os.listdir(fd))
            if names - (set(NAMES.values()) | {'manifest.json', 'record.json'}):
                raise error('snapshot', 'Unexpected backup files were found. Nothing was deleted.')
            for name in names:
                config._read_at(fd, name)
            for name in names:
                os.unlink(name, dir_fd=fd)
            os.fsync(fd)
        os.rmdir(identifier, dir_fd=parent)
        os.fsync(parent)
    return dict(deleted=True)


def backup_catalogue(root=None):
    """Complete backups globally; legacy single-file records for this session."""
    result = list_snapshots(root)
    if root is not None:
        with config._Workspace(root) as primary:
            model = primary.model
        for store in schema.STORES:
            for entry in config.list_backups(root, store):
                checksum = ''
                deletable = False
                restorable = False
                if entry['state'] != 'unavailable':
                    with config._Workspace(root, store) as workspace, workspace.record(entry['id']) as (fd, record):
                        checksum = config.digest(config._read_at(fd, 'record.json')[0])
                        deletable = record['state'] in ('written', 'restored')
                    try:
                        snap = config.read_settings(root, store)
                        config.preview_restore(root, snap['token'], entry['id'], store)
                        restorable = True
                    except (config.ConfigError, OSError):
                        pass
                result.append(dict(entry, kind='legacy', model=model, firmware=schema.FIRMWARE_VERSION,
                                   reason='legacy', store=store, scope=schema.STORES[store][1],
                                   can_restore=restorable, can_delete=deletable, checksum=checksum))
    return sorted(result, key=lambda entry: (entry['created'], entry['id']), reverse=True)


def delete_legacy(root, store, identifier, checksum):
    with config._Workspace(root, store) as workspace, workspace.lock(), workspace.record(identifier) as (fd, record):
        if record['state'] not in ('written', 'restored'):
            raise error('snapshot_pending', 'This single-file backup is recovery evidence and cannot be deleted yet.')
        if config.digest(config._read_at(fd, 'record.json')[0]) != checksum:
            raise error('external_change', 'This backup changed. Reload Backups before deleting it.')
        if set(os.listdir(fd)) != {'before.bin', 'record.json'}:
            raise error('snapshot', 'Unexpected backup files were found. Nothing was deleted.')
        original = config._read_at(fd, 'before.bin')[0]
        if config.digest(original) != record['before_sha256']:
            raise error('snapshot', 'This backup failed verification. Preserve it for inspection.')
        parent = workspace.backups()
        try:
            os.unlink('before.bin', dir_fd=fd)
            os.unlink('record.json', dir_fd=fd)
            os.fsync(fd)
            os.rmdir(identifier, dir_fd=parent)
            os.fsync(parent)
        finally:
            os.close(parent)
    return dict(deleted=True)


def backup_location(root=None):
    try:
        return str(_location(root))
    except FileNotFoundError:
        if root is None:
            raise error('snapshot', 'Create a complete configuration backup first.') from None
        with config._Workspace(root) as workspace:
            return str(workspace.root if workspace.synthetic else workspace.context['storage'])
