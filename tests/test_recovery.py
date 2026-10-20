"""Synthetic read-only preflight and interruption recovery; no real disk queries."""
from contextlib import contextmanager, redirect_stdout, redirect_stderr
import copy
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import xteink_sd_migrate as m
import restore_recovery as recovery

os.environ['XTEINK_TESTING'] = '1'


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mount = self.root / 'card'
        self.mount.mkdir()
        self.archive = self.root / 'synthetic.zip'
        self.payload = {'.crosspoint/state.json': b'{"page":42}',
                        'books/story.txt': b'synthetic reading bytes for recovery',
                        'empty.txt': b''}
        self.manifest = {
            'format': 'xteink-x3-migrate-v1', 'created_at': '2025-01-01T00:00:00+00:00',
            'source_disk': {'capacity_bytes': 128 * 1024**2, 'filesystem': 'FAT32',
                            'volume_uuid': 'synthetic-source'},
            'files': [dict(path=name, size=len(data), mtime_ns=1,
                           sha256=hashlib.sha256(data).hexdigest()) for name, data in self.payload.items()],
            'directories': ['.crosspoint', 'books', 'empty-dir'],
            'file_count': len(self.payload), 'total_bytes': sum(map(len, self.payload.values())),
        }
        with zipfile.ZipFile(self.archive, 'w') as zf:
            for name in self.manifest['directories']:
                zf.writestr(name + '/', b'')
            for name, data in self.payload.items():
                zf.writestr(name, data)
        self.manifest['zip_sha256'] = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.archive.with_suffix('.manifest.json').write_text(json.dumps(self.manifest))
        self.disk = {
            'id': 'disk9', 'name': 'Synthetic SD', 'size': 256 * 1024**2,
            'identity': ('synthetic',), 'target_filesystem': 'exfat',
            'info': {'DeviceIdentifier': 'disk9', 'WholeDisk': True,
                     'TotalSize': 256 * 1024**2, 'RemovableMedia': True,
                     'VirtualOrPhysical': 'Physical', 'Writable': True, 'BusProtocol': 'USB'},
            'partitions': [{'id': 'disk9s1', 'mount': str(self.mount), 'fstype': 'ExFAT',
                            'info': {'VolumeUUID': 'synthetic-target', 'ParentWholeDisk': 'disk9'}}],
        }
        self.disk['confirmed_identity'] = m.disk_safety.target_identity(self.disk, m.MigrationError)
        self.output = io.StringIO()
        self.quiet = redirect_stdout(self.output)
        self.quiet.__enter__()
        self.addCleanup(self.quiet.__exit__, None, None, None)
        self.backup_before = self.archive.read_bytes()

    def journal(self):
        return recovery.Journal.create(self.archive, self.manifest, 'synthetic-target',
                                       self.disk['size'], 'exfat', m.MigrationError)

    def read_journal(self):
        return recovery.Journal.load(self.archive, self.manifest, m.MigrationError)

    @contextmanager
    def device_queries(self, empty_reader=False):
        layout = [] if empty_reader else [{'DeviceIdentifier': 'disk9', 'Content': 'FDisk_partition_scheme'}]
        with patch.object(m, 'external_disks', return_value=[self.disk]), \
             patch.object(m, 'diskutil_plist', return_value={'AllDisksAndPartitions': layout}), \
             patch.object(m.disk_safety, 'physical_disks', side_effect=lambda path, *a:
                          {'disk9'} if Path(path) == self.mount else {'disk0'}):
            yield

    def cli(self, *args):
        with patch.object(m.sys, 'platform', 'darwin'), patch.object(m.sys, 'argv', ['prog', *map(str, args)]):
            m.main()

    def interrupted(self, name='books/story.txt'):
        journal = self.journal()
        real_read = zipfile.ZipExtFile.read
        def faulty(stream, n=-1):
            if stream.name == name and journal.data['current_file'] == name and stream.tell() >= 4:
                raise OSError('Synthetic interrupted read')
            return real_read(stream, n)
        with patch.object(m, 'CHUNK', 4), patch.object(zipfile.ZipExtFile, 'read', faulty):
            with self.assertRaises(OSError):
                m.restore_archive(self.archive, self.manifest, self.mount, journal=journal)
        self.assertEqual(self.read_journal().data['current_file'], name)
        self.assertEqual((self.mount / name).read_bytes(), self.payload[name][:4])
        return self.read_journal()

    def snapshot(self):
        return {str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.root.rglob('*') if path.is_file() and not path.is_symlink()}

    @contextmanager
    def journal_fault(self, stage):
        """Fail a real local journal save at one of its persistence boundaries."""
        error = OSError(errno.ENOSPC, 'Synthetic journal storage full')
        if stage == 'create':
            with patch.object(recovery.tempfile, 'mkstemp', side_effect=error):
                yield
        elif stage == 'write':
            def fail_write(data, stream, **kwargs):
                stream.write('{"synthetic_partial":')
                raise error
            with patch.object(recovery.json, 'dump', side_effect=fail_write):
                yield
        elif stage == 'replace':
            with patch.object(recovery.os, 'replace', side_effect=error):
                yield
        else:
            real_fsync = os.fsync
            def fail_sync(fd):
                directory = stat.S_ISDIR(os.fstat(fd).st_mode)
                if directory == (stage == 'directory-sync'):
                    raise error
                return real_fsync(fd)
            with patch.object(recovery.os, 'fsync', side_effect=fail_sync):
                yield

    @contextmanager
    def target_write_fault(self, name, budget=6, error=None):
        """Persist only a prefix of a target write, then inject ENOSPC/signal."""
        real_fdopen = os.fdopen
        destination = self.mount / name
        error = error or OSError(errno.ENOSPC, 'Synthetic target storage full')
        class Writer:
            def __init__(self, stream):
                self.stream = stream
                self.remaining = budget
            def __enter__(self):
                self.stream.__enter__()
                return self
            def __exit__(self, *args):
                return self.stream.__exit__(*args)
            def __getattr__(self, key):
                return getattr(self.stream, key)
            def write(self, data):
                count = min(len(data), self.remaining)
                if count:
                    self.stream.write(data[:count])
                    self.stream.flush()
                    self.remaining -= count
                if count < len(data):
                    raise error
                return count
        def open_stream(fd, mode, *args, **kwargs):
            match = (mode in ('w+b', 'r+b') and destination.exists() and
                     os.fstat(fd).st_ino == destination.stat().st_ino)
            stream = real_fdopen(fd, mode, *args, **kwargs)
            return Writer(stream) if match else stream
        with patch.object(m.os, 'fdopen', side_effect=open_stream):
            yield

    def assert_backup_retained(self):
        self.assertEqual(self.archive.read_bytes(), self.backup_before)
        _, manifest = m.load_backup(self.archive)
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(list(self.root.glob('.restore-journal-*.partial')), [])

    def test_initial_journal_failure_prevents_first_copy(self):
        for stage in ('create', 'write', 'file-sync', 'replace', 'directory-sync'):
            with self.subTest(stage=stage), self.device_queries(), patch.object(m, 'erase_target'), \
                 patch.object(m, 'restore_archive') as copy_files, patch.object(m, 'eject') as eject:
                with self.journal_fault(stage):
                    with self.assertRaises(OSError):
                        m.migrate_to_target(self.disk, self.archive, self.manifest)
                copy_files.assert_not_called()
                eject.assert_not_called()
                self.assertEqual(list(self.mount.iterdir()), [])
                self.assert_backup_retained()
                # A failed directory sync can leave a valid new journal visible.
                if recovery.state_path(self.archive).exists():
                    self.read_journal()
                    recovery.state_path(self.archive).unlink()

    def test_failed_active_file_checkpoint_stops_copy_and_can_retry(self):
        for stage in ('create', 'write', 'file-sync', 'replace', 'directory-sync'):
            with self.subTest(stage=stage):
                journal = self.journal()
                with self.journal_fault(stage):
                    with self.assertRaises(OSError):
                        m.restore_archive(self.archive, self.manifest, self.mount, journal=journal)
                self.assertEqual([p for p in self.mount.rglob('*') if p.is_file()], [])
                self.assert_backup_retained()
                fresh = self.read_journal()
                m.restore_archive(self.archive, self.manifest, self.mount, journal=fresh, resume=True)
                m.verify_restored(self.mount, self.manifest)
                # Reset only these disposable fixture files for the next fault.
                shutil.rmtree(self.mount)
                self.mount.mkdir()
                recovery.state_path(self.archive).unlink()

    def test_failed_checkpoint_after_file_fsync_preserves_completed_file(self):
        journal = self.journal()
        real_current = journal.current
        def checkpoint(name):
            if name is None:
                with self.journal_fault('replace'):
                    real_current(name)
            else:
                real_current(name)
        with patch.object(journal, 'current', side_effect=checkpoint):
            with self.assertRaises(OSError):
                m.restore_archive(self.archive, self.manifest, self.mount, journal=journal)
        complete = self.mount / '.crosspoint/state.json'
        before = complete.stat()
        self.assertEqual(complete.read_bytes(), self.payload['.crosspoint/state.json'])
        fresh = self.read_journal()
        self.assertEqual(fresh.data['current_file'], '.crosspoint/state.json')
        m.restore_archive(self.archive, self.manifest, self.mount, journal=fresh, resume=True)
        self.assertEqual((complete.stat().st_ino, complete.stat().st_mtime_ns),
                         (before.st_ino, before.st_mtime_ns))
        m.verify_restored(self.mount, self.manifest)
        self.assert_backup_retained()

    def test_target_enospc_retains_prefix_and_resumes(self):
        journal = self.journal()
        name = 'books/story.txt'
        with self.target_write_fault(name), patch.object(m, 'CHUNK', 4):
            with self.assertRaises(OSError) as exc:
                m.restore_archive(self.archive, self.manifest, self.mount, journal=journal)
        self.assertEqual(exc.exception.errno, errno.ENOSPC)
        self.assertEqual((self.mount / name).read_bytes(), self.payload[name][:6])
        fresh = self.read_journal()
        self.assertEqual(fresh.data['current_file'], name)
        m.restore_archive(self.archive, self.manifest, self.mount, journal=fresh, resume=True)
        m.verify_restored(self.mount, self.manifest)
        self.assert_backup_retained()

    def test_enospc_during_resume_keeps_old_prefix_and_retries(self):
        self.interrupted()
        name = 'books/story.txt'
        completed = self.mount / '.crosspoint/state.json'
        before = completed.stat()
        with self.device_queries(), patch('builtins.input', return_value='RESUME disk9'), \
             self.target_write_fault(name), patch.object(m, 'CHUNK', 4), \
             patch.object(m, 'eject') as eject, patch.object(m, 'erase_target') as erase:
            with self.assertRaises(OSError) as exc:
                self.cli('--resume', self.archive)
            self.assertEqual(exc.exception.errno, errno.ENOSPC)
            eject.assert_not_called()
            erase.assert_not_called()
        self.assertEqual((self.mount / name).read_bytes(), self.payload[name][:10])
        self.assertEqual(self.read_journal().data['current_file'], name)
        with self.device_queries(), patch('builtins.input', return_value='RESUME disk9'), patch.object(m, 'eject'):
            self.cli('--resume', self.archive)
        m.verify_restored(self.mount, self.manifest)
        self.assertEqual((completed.stat().st_ino, completed.stat().st_mtime_ns),
                         (before.st_ino, before.st_mtime_ns))
        self.assertFalse(recovery.state_path(self.archive).exists())
        self.assert_backup_retained()

    def test_keyboard_interrupt_during_write_releases_lock_for_retry(self):
        self.interrupted()
        with self.device_queries(), patch('builtins.input', return_value='RESUME disk9'), \
             self.target_write_fault('books/story.txt', error=KeyboardInterrupt()), \
             patch.object(m, 'eject') as eject:
            with self.assertRaises(KeyboardInterrupt):
                self.cli('--resume', self.archive)
            eject.assert_not_called()
        with recovery.locked(self.archive, m.MigrationError):
            self.assertIsNotNone(self.read_journal())
        with self.device_queries(), patch('builtins.input', return_value='RESUME disk9'), patch.object(m, 'eject'):
            self.cli('--resume', self.archive)
        m.verify_restored(self.mount, self.manifest)
        self.assert_backup_retained()

    def test_target_fsync_failure_retains_checkpoint_for_retry(self):
        journal = self.journal()
        destination = self.mount / 'books/story.txt'
        real_fsync = os.fsync
        def fail_sync(fd):
            if destination.exists() and os.fstat(fd).st_ino == destination.stat().st_ino:
                raise OSError(errno.EIO, 'Synthetic target sync failure')
            real_fsync(fd)
        with patch.object(m.os, 'fsync', side_effect=fail_sync):
            with self.assertRaises(OSError):
                m.restore_archive(self.archive, self.manifest, self.mount, journal=journal)
        fresh = self.read_journal()
        self.assertEqual(fresh.data['current_file'], 'books/story.txt')
        m.restore_archive(self.archive, self.manifest, self.mount, journal=fresh, resume=True)
        m.verify_restored(self.mount, self.manifest)
        self.assert_backup_retained()

    def test_failed_verified_checkpoint_prevents_eject_and_can_retry(self):
        self.interrupted()
        real_verified = recovery.Journal.verified
        def checkpoint(journal):
            with self.journal_fault('replace'):
                real_verified(journal)
        with self.device_queries(), patch('builtins.input', return_value='RESUME disk9'), \
             patch.object(recovery.Journal, 'verified', checkpoint), patch.object(m, 'eject') as eject:
            with self.assertRaises(OSError): self.cli('--resume', self.archive)
            eject.assert_not_called()
        m.verify_restored(self.mount, self.manifest)
        self.read_journal()
        with self.device_queries(), patch('builtins.input', return_value='RESUME disk9'), patch.object(m, 'eject'):
            self.cli('--resume', self.archive)
        self.assertFalse(recovery.state_path(self.archive).exists())
        self.assert_backup_retained()

    def test_failed_journal_cleanup_can_verify_and_eject_again(self):
        self.interrupted()
        def fail_cleanup(journal):
            raise OSError(errno.EACCES, 'Synthetic journal removal denied')
        with self.device_queries(), patch('builtins.input', return_value='RESUME disk9'), \
             patch.object(recovery.Journal, 'complete', fail_cleanup), patch.object(m, 'eject') as eject:
            with self.assertRaises(OSError): self.cli('--resume', self.archive)
            eject.assert_called_once_with('disk9')
        self.assertEqual(self.read_journal().data['phase'], 'verified')
        with self.device_queries(), patch('builtins.input', return_value='RESUME disk9'), patch.object(m, 'eject'):
            self.cli('--resume', self.archive)
        self.assertFalse(recovery.state_path(self.archive).exists())
        self.assert_backup_retained()

    def test_offline_verify_no_disk_or_write_operations(self):
        before = self.snapshot()
        with patch.object(m, 'diskutil_plist', side_effect=AssertionError('No disk query')), \
             patch.object(m, 'external_disks', side_effect=AssertionError('No disk query')), \
             patch.object(m, 'invoke_status', side_effect=AssertionError('No mutation')), \
             patch.object(recovery, 'locked', side_effect=AssertionError('No lock')):
            self.cli('--verify-backup', self.archive)
        self.assertEqual(self.snapshot(), before)
        self.assertIn('BACKUP VERIFIED', self.output.getvalue())

    def test_verify_corrupt_archive_refuses_without_disk_query(self):
        with self.archive.open('ab') as stream:
            stream.write(b'synthetic damage')
        with patch.object(m, 'external_disks', side_effect=AssertionError('No disk query')):
            with self.assertRaises(m.MigrationError):
                self.cli('--verify-backup', self.archive)

    def test_dry_run_runs_guards_without_creating_lock_or_state(self):
        before = self.snapshot()
        with self.device_queries(empty_reader=True), patch('builtins.input', side_effect=['', '']), \
             patch.object(m, 'choose_disk', return_value=self.disk), \
             patch.object(m, 'invoke_status', side_effect=AssertionError('No disk mutation')), \
             patch.object(m, 'restore_archive', side_effect=AssertionError('No copy')), \
             patch.object(m, 'make_backup', side_effect=AssertionError('No backup')), \
             patch.object(recovery, 'locked', side_effect=AssertionError('No lock')):
            self.cli('--restore', self.archive, '--dry-run')
        self.assertEqual(self.snapshot(), before)
        self.assertIn('PREFLIGHT PASSED', self.output.getvalue())

    def test_dry_run_protects_source_like_target(self):
        (self.mount / '.crosspoint').mkdir()
        with self.device_queries(empty_reader=True), patch('builtins.input', side_effect=['', '']), \
             patch.object(m, 'choose_disk', return_value=self.disk), \
             patch.object(m, 'erase_target', side_effect=AssertionError('No erase')):
            with self.assertRaisesRegex(m.MigrationError, 'SOURCE'):
                self.cli('--restore', self.archive, '--dry-run')

    def test_dry_run_checks_protected_storage(self):
        with self.device_queries(empty_reader=True), patch('builtins.input', side_effect=['', '']), \
             patch.object(m, 'choose_disk', return_value=self.disk), \
             patch.object(m.disk_safety, 'physical_disks', return_value={'disk9'}):
            with self.assertRaisesRegex(m.MigrationError, 'contains the backup'):
                self.cli('--restore', self.archive, '--dry-run')

    def test_invalid_mode_combinations_fail_before_actions(self):
        cases = [('--dry-run',), ('--backup-only', '--dry-run'),
                 ('--verify-backup', str(self.archive), '--diagnose'),
                 ('--resume', str(self.archive), '--filesystem', 'fat32')]
        for args in cases:
            with self.subTest(args=args), redirect_stderr(io.StringIO()), \
                 patch.object(m, 'external_disks', side_effect=AssertionError('No action')):
                with self.assertRaises(SystemExit) as exc:
                    self.cli(*args)
                self.assertEqual(exc.exception.code, 2)

    def test_interrupted_resume_appends_only_and_preserves_complete_inode(self):
        journal = self.interrupted()
        existing = self.mount / '.crosspoint/state.json'
        before = existing.stat()
        m.restore_archive(self.archive, self.manifest, self.mount, journal=journal, resume=True)
        m.verify_restored(self.mount, self.manifest)
        after = existing.stat()
        self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))
        self.assertEqual(self.archive.read_bytes(), self.backup_before)
        self.assertIsNone(self.read_journal().data['current_file'])

    def test_inspection_and_resume_dry_run_are_read_only(self):
        self.interrupted()
        before = self.snapshot()
        for args in (('--check-restore',), ('--resume',)):
            with self.device_queries(), patch.object(m, 'invoke_status', side_effect=AssertionError('No mutation')), \
                 patch.object(recovery, 'locked', side_effect=AssertionError('No lock')), \
                 patch.object(recovery.Journal, 'save', side_effect=AssertionError('No journal write')):
                self.cli(*args, self.archive, *(['--dry-run'] if args == ('--resume',) else []))
        self.assertEqual(self.snapshot(), before)
        self.assertIn('partial=1', self.output.getvalue())

    def test_resume_cli_has_no_format_and_retains_backups(self):
        self.interrupted()
        commands = []
        with self.device_queries(), patch('builtins.input', return_value='RESUME disk9'), \
             patch.object(m, 'invoke_status', side_effect=lambda *args: commands.append(args)):
            self.cli('--resume', self.archive)
        self.assertEqual(commands, [('Safely ejecting', 'diskutil', 'eject', '/dev/disk9')])
        self.assertFalse(recovery.state_path(self.archive).exists())
        self.assertEqual(self.archive.read_bytes(), self.backup_before)
        m.verify_restored(self.mount, self.manifest)

    def test_changed_prefix_aborts_before_any_writes(self):
        journal = self.interrupted()
        (self.mount / 'books/story.txt').write_bytes(b'bad!')
        before = self.snapshot()
        with self.assertRaises(m.MigrationError):
            m.restore_archive(self.archive, self.manifest, self.mount, journal=journal, resume=True)
        self.assertEqual(self.snapshot(), before)

    def test_unexpected_data_aborts_before_copy(self):
        journal = self.interrupted()
        (self.mount / 'unrelated.txt').write_text('synthetic unrelated data')
        before = self.snapshot()
        with self.assertRaises(m.MigrationError):
            m.restore_archive(self.archive, self.manifest, self.mount, journal=journal, resume=True)
        self.assertEqual(self.snapshot(), before)

    def test_completed_corrupt_file_is_not_overwritten(self):
        journal = self.interrupted()
        (self.mount / '.crosspoint/state.json').write_bytes(b'X' * len(self.payload['.crosspoint/state.json']))
        before = self.snapshot()
        with self.assertRaises(m.MigrationError):
            m.restore_archive(self.archive, self.manifest, self.mount, journal=journal, resume=True)
        self.assertEqual(self.snapshot(), before)

    def test_partial_requires_exact_current_file_authorization(self):
        journal = self.interrupted()
        journal.current(None)
        before = self.snapshot()
        with self.assertRaises(m.MigrationError):
            m.restore_archive(self.archive, self.manifest, self.mount, journal=journal, resume=True)
        self.assertEqual(self.snapshot(), before)

    def test_partial_recovers_before_other_missing_files(self):
        journal = self.interrupted()
        (self.mount / '.crosspoint/state.json').unlink()
        m.restore_archive(self.archive, self.manifest, self.mount, journal=journal, resume=True)
        m.verify_restored(self.mount, self.manifest)

    def test_missing_journal_never_falls_back_to_format(self):
        with self.device_queries(), patch.object(m, 'erase_target', side_effect=AssertionError('No erase')):
            with self.assertRaisesRegex(m.MigrationError, 'legacy interrupted'):
                self.cli('--resume', self.archive)

    def test_pending_journal_blocks_new_erase(self):
        self.journal()
        with patch.object(m, 'choose_target', side_effect=AssertionError('No selection')), \
             patch.object(m, 'erase_target', side_effect=AssertionError('No erase')):
            with self.assertRaisesRegex(m.MigrationError, 'journal already exists'):
                self.cli('--restore', self.archive)

    def test_wrong_backup_or_manifest_journal_rejected(self):
        self.journal()
        for field in ('zip_sha256', 'created_at'):
            altered = copy.deepcopy(self.manifest)
            altered[field] = 'changed'
            with self.assertRaises(m.MigrationError):
                recovery.Journal.load(self.archive, altered, m.MigrationError)

    def test_journal_validation_duplicate_keys_and_invalid_current_file(self):
        self.journal()
        path = recovery.state_path(self.archive)
        valid = path.read_text()
        for payload in ('{"format":1,"format":2}', '[]',
                        valid.replace('"current_file": null', '"current_file": []')):
            path.write_text(payload)
            with self.assertRaises(m.MigrationError): self.read_journal()

    def test_journal_and_lock_private_permissions_and_lock_contention(self):
        self.journal()
        self.assertEqual(stat.S_IMODE(recovery.state_path(self.archive).stat().st_mode), 0o600)
        with recovery.locked(self.archive, m.MigrationError):
            with self.assertRaises(m.MigrationError):
                with recovery.locked(self.archive, m.MigrationError):
                    self.fail('Concurrent lock allowed')
        self.assertEqual(stat.S_IMODE(self.archive.with_suffix('.restore.lock').stat().st_mode), 0o600)

    def test_journal_symlink_refused(self):
        path = recovery.state_path(self.archive)
        path.symlink_to(self.archive.with_suffix('.manifest.json'))
        with self.assertRaises(m.MigrationError): self.read_journal()

    def test_recovery_source_volume_rejected(self):
        journal = self.journal()
        self.manifest['source_disk']['volume_uuid'] = 'synthetic-target'
        with self.device_queries():
            with self.assertRaisesRegex(m.MigrationError, 'Source volume'):
                m.recovery_target(self.archive, self.manifest, journal)

    def test_recovery_wrong_or_duplicated_uuid_rejected(self):
        journal = self.journal()
        for disks in ([], [self.disk, copy.deepcopy(self.disk)]):
            with patch.object(m, 'external_disks', return_value=disks):
                with self.assertRaises(m.MigrationError):
                    m.recovery_target(self.archive, self.manifest, journal)

    def test_recovery_capacity_or_fs_change_rejected(self):
        journal = self.journal()
        original = copy.deepcopy(self.disk)
        for field in ('capacity', 'filesystem'):
            self.disk = copy.deepcopy(original)
            if field == 'capacity': self.disk['size'] -= 1
            else: self.disk['partitions'][0]['fstype'] = 'MS-DOS FAT32'
            with self.device_queries():
                with self.assertRaises(m.MigrationError):
                    m.recovery_target(self.archive, self.manifest, journal)

    def test_recovery_mount_change_rejected(self):
        journal = self.journal()
        changed = copy.deepcopy(self.disk)
        changed['partitions'][0]['info']['VolumeUUID'] = 'different-target'
        with self.device_queries(), patch.object(m, 'external_disks', side_effect=[[self.disk], [self.disk], [changed]]):
            with self.assertRaises(m.MigrationError):
                m.recovery_target(self.archive, self.manifest, journal)

    def test_recovery_tree_symlink_and_root_swap_rejected(self):
        journal = self.journal()
        (self.mount / 'books').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(m.MigrationError):
            m.inspect_restore(self.archive, self.manifest, self.mount, journal)
        (self.mount / 'books').unlink()
        with self.assertRaises(m.MigrationError):
            m.inspect_restore(self.archive, self.manifest, self.mount, journal, expected_identity=(-1, -1))

    def test_failed_eject_retains_verified_journal_and_retry_succeeds(self):
        self.interrupted()
        with self.device_queries(), patch('builtins.input', return_value='RESUME disk9'), \
             patch.object(m, 'eject', side_effect=OSError('Synthetic eject failure')):
            with self.assertRaises(OSError): self.cli('--resume', self.archive)
        self.assertEqual(self.read_journal().data['phase'], 'verified')
        before = (self.mount / 'books/story.txt').stat().st_mtime_ns
        with self.device_queries(), patch('builtins.input', return_value='RESUME disk9'), patch.object(m, 'eject'):
            self.cli('--resume', self.archive)
        self.assertEqual((self.mount / 'books/story.txt').stat().st_mtime_ns, before)
        self.assertFalse(recovery.state_path(self.archive).exists())

    def test_fresh_migration_creates_journal_before_copy_and_removes_after_eject(self):
        original_restore = m.restore_archive
        def restore(*args, **kwargs):
            self.assertTrue(recovery.state_path(self.archive).exists())
            original_restore(*args, **kwargs)
        def eject(*args):
            self.assertEqual(self.read_journal().data['phase'], 'verified')
        with self.device_queries(), patch.object(m, 'erase_target'), patch.object(m, 'restore_archive', side_effect=restore), \
             patch.object(m, 'eject', side_effect=eject):
            m.migrate_to_target(self.disk, self.archive, self.manifest)
        self.assertFalse(recovery.state_path(self.archive).exists())
        m.verify_restored(self.mount, self.manifest)

    def test_recovery_legacy_manifest_without_source_uuid(self):
        del self.manifest['source_disk']['volume_uuid']
        journal = self.interrupted()
        with self.device_queries():
            m.recovery_target(self.archive, self.manifest, journal)
        m.restore_archive(self.archive, self.manifest, self.mount, journal=journal, resume=True)
        m.verify_restored(self.mount, self.manifest)

    def test_recovery_cancellation_leaves_bytes_and_journal_unchanged(self):
        self.interrupted()
        before = self.snapshot()
        with self.device_queries(), patch('builtins.input', return_value='cancel'), \
             patch.object(m, 'eject', side_effect=AssertionError('No eject')):
            with self.assertRaises(m.MigrationError):
                m.recover_backup(self.archive, self.manifest)
        self.assertEqual(self.snapshot(), before)

    def test_recovery_insufficient_space_never_copies_or_erases(self):
        self.interrupted()
        before = self.snapshot()
        with self.device_queries(), patch('builtins.input', return_value='RESUME disk9'), \
             patch.object(m, 'check_formatted_target_space', side_effect=m.MigrationError('Synthetic space failure')), \
             patch.object(m, 'restore_archive', side_effect=AssertionError('No copy')), \
             patch.object(m, 'erase_target', side_effect=AssertionError('No erase')):
            with self.assertRaises(m.MigrationError): m.recover_backup(self.archive, self.manifest)
        self.assertEqual(self.snapshot(), before)

    def test_completed_job_cannot_recover_after_journal_cleanup(self):
        journal = self.journal()
        m.restore_archive(self.archive, self.manifest, self.mount, journal=journal)
        m.verify_restored(self.mount, self.manifest)
        journal.verified()
        journal.complete()
        with self.assertRaises(m.MigrationError): self.read_journal()

    def test_post_format_change_rejected_before_journal_or_copy(self):
        with self.device_queries(), patch.object(m, 'erase_target'), \
             patch.object(m, 'after_format_volume', return_value=self.root), \
             patch.object(m, 'restore_archive', side_effect=AssertionError('No copy')):
            with self.assertRaises(m.MigrationError):
                m.migrate_to_target(self.disk, self.archive, self.manifest)
        self.assertFalse(recovery.state_path(self.archive).exists())

    def test_hard_link_not_modified_by_recovery(self):
        journal = self.interrupted()
        outside = self.root / 'linked-copy.txt'
        os.link(self.mount / 'books/story.txt', outside)
        before = self.snapshot()
        with self.assertRaises(m.MigrationError):
            m.restore_archive(self.archive, self.manifest, self.mount, journal=journal, resume=True)
        self.assertEqual(self.snapshot(), before)

    def test_verified_full_card_can_retry_eject_without_free_space_reserve(self):
        journal = self.journal()
        m.restore_archive(self.archive, self.manifest, self.mount, journal=journal)
        journal.verified()
        with self.device_queries(), patch('builtins.input', return_value='RESUME disk9'), \
             patch.object(m, 'check_formatted_target_space', side_effect=AssertionError('No new data allocation')), \
             patch.object(m, 'eject') as eject:
            self.cli('--resume', self.archive)
        eject.assert_called_once_with('disk9')
        self.assertFalse(recovery.state_path(self.archive).exists())

    def test_reconnected_target_can_have_a_new_disk_number(self):
        journal = self.journal()
        disk = copy.deepcopy(self.disk)
        disk['id'] = disk['info']['DeviceIdentifier'] = 'disk12'
        disk['partitions'][0]['id'] = 'disk12s1'
        disk['partitions'][0]['info']['ParentWholeDisk'] = 'disk12'
        with patch.object(m, 'external_disks', return_value=[disk]), \
             patch.object(m, 'diskutil_plist', return_value={'AllDisksAndPartitions': [
                 {'DeviceIdentifier': 'disk12', 'Content': 'FDisk_partition_scheme'}]}), \
             patch.object(m.disk_safety, 'physical_disks', side_effect=lambda path, *a:
                          {'disk12'} if Path(path) == self.mount else {'disk0'}):
            selected, root, identity = m.recovery_target(self.archive, self.manifest, journal)
        self.assertEqual(selected['id'], 'disk12')
        self.assertEqual(root, self.mount)


if __name__ == '__main__':
    unittest.main()
