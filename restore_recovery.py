"""Private local restore journals; never part of the legacy backup manifest."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


def state_path(archive):
    return Path(archive).with_suffix('.restore-state.json')


def manifest_digest(manifest):
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode('utf-8')).hexdigest()


@contextmanager
def locked(archive, error):
    # Keep the lock inode: unlinking it could let another process lock a new inode.
    import fcntl
    fd = os.open(Path(archive).with_suffix('.restore.lock'),
                 os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise error('Restore lock is not a private regular file.')
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise error('Another restore is using this backup; no target action taken.') from exc
        yield
    finally:
        os.close(fd)


def require_new(archive, error):
    path = state_path(archive)
    if path.exists() or path.is_symlink():
        raise error('A restore journal already exists. Use --check-restore / --resume; '
                    'preserve the journal and target. No new erase is allowed for this job.')


class Journal:
    def __init__(self, archive, data):
        self.path = state_path(archive)
        self.data = data

    @classmethod
    def create(cls, archive, manifest, volume_uuid, capacity, filesystem, error):
        require_new(archive, error)
        job = cls(archive, {
            'format': 'xteink-sd-restore-v1', 'manifest_sha256': manifest_digest(manifest),
            'zip_sha256': manifest['zip_sha256'], 'volume_uuid': volume_uuid,
            'capacity_bytes': capacity, 'filesystem': filesystem,
            'phase': 'restoring', 'current_file': None,
        })
        job.save()
        return job

    @classmethod
    def load(cls, archive, manifest, error):
        path = state_path(archive)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
                    raise error('Restore journal is not a bounded regular file.')
                def unique(pairs):
                    result = {}
                    for key, value in pairs:
                        if key in result:
                            raise ValueError('Duplicate journal key')
                        result[key] = value
                    return result
                data = json.loads(stream.read(65537), object_pairs_hook=unique)
        except (OSError, ValueError) as exc:
            raise error('Missing or invalid local restore journal. Preserve the target '
                        'and backup; legacy interrupted restores cannot be resumed automatically.') from exc
        if (not isinstance(data, dict) or data.get('format') != 'xteink-sd-restore-v1' or
                data.get('manifest_sha256') != manifest_digest(manifest) or
                data.get('zip_sha256') != manifest['zip_sha256'] or
                not isinstance(data.get('volume_uuid'), str) or not data['volume_uuid'] or
                type(data.get('capacity_bytes')) is not int or data['capacity_bytes'] <= 0 or
                data.get('filesystem') not in ('fat32', 'exfat') or
                data.get('phase') not in ('restoring', 'verified') or
                'current_file' not in data or
                (data['current_file'] is not None and
                 (not isinstance(data['current_file'], str) or
                  data['current_file'] not in {item['path'] for item in manifest['files']}))):
            raise error('Restore journal does not match the verified backup or has invalid fields.')
        return cls(archive, data)

    def save(self):
        # fsync the new contents and parent before permitting the associated SD write.
        fd, name = tempfile.mkstemp(prefix='.restore-journal-', suffix='.partial', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(self.data, stream, sort_keys=True)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            parent_fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        finally:
            try:
                os.unlink(name)
            except FileNotFoundError:
                pass

    def current(self, name):
        self.data['current_file'] = name
        self.save()

    def verified(self):
        self.data.update(phase='verified', current_file=None)
        self.save()

    def complete(self):
        self.path.unlink()  # Called only after complete readback and successful eject.
