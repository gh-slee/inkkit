"""Synthetic fixtures only. Never run diskutil against a real device."""
import contextlib
import copy
import hashlib
import io
import json
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import xteink_sd_migrate as m
import disk_safety as safety

os.environ['XTEINK_TESTING'] = '1'


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.mount = self.root / 'card'
        self.mount.mkdir()
        self.archive = self.root / 'legacy.zip'
        # Literal v1 schema and timestamp fields, independent of make_backup.
        self.manifest = {
            'format': 'xteink-x3-migrate-v1', 'created_at': '2025-01-01T00:00:00+00:00',
            'source_disk': {'media_name': 'Synthetic SD', 'capacity_bytes': 128 * 1024**2,
                            'filesystem': 'FAT32', 'disk_identifier_at_backup': 'disk8'},
            'files': [{'path': '.crosspoint/state.json', 'size': 2, 'mtime_ns': 1,
                       'sha256': hashlib.sha256(b'{}').hexdigest()}],
            'directories': ['.crosspoint'], 'file_count': 1, 'total_bytes': 2,
        }
        self.write_zip()
        self.disk = {
            'id': 'disk9', 'name': 'Synthetic SD', 'size': 256 * 1024**2,
            'identity': ('legacy',),
            'info': {'DeviceIdentifier': 'disk9', 'DeviceNode': '/dev/disk9',
                     'WholeDisk': True, 'TotalSize': 256 * 1024**2,
                     'RemovableMedia': True, 'VirtualOrPhysical': 'Unknown',
                     'Writable': True, 'BusProtocol': 'USB', 'Internal': False},
            'partitions': [{'id': 'disk9s1', 'mount': str(self.mount), 'fstype': 'ExFAT',
                            'info': {'VolumeUUID': 'synthetic-target', 'ParentWholeDisk': 'disk9'}}],
            'target_filesystem': 'fat32',
        }
        self.disk['confirmed_identity'] = safety.target_identity(self.disk, m.MigrationError)
        self.quiet = contextlib.redirect_stdout(io.StringIO())
        self.quiet.__enter__()
        self.addCleanup(self.quiet.__exit__, None, None, None)

    def write_zip(self, members=None):
        with zipfile.ZipFile(self.archive, 'w') as zf:
            for name, data in members or [('.crosspoint/', b''), ('.crosspoint/state.json', b'{}')]:
                zf.writestr(name, data)
        self.manifest['zip_sha256'] = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.archive.with_suffix('.manifest.json').write_text(json.dumps(self.manifest))

    def gate(self, disks=None, **kwargs):
        with patch.object(m, 'external_disks', side_effect=disks or [[self.disk], [self.disk]]), \
             patch.object(safety, 'physical_disks', return_value={'disk0'}), \
             patch.object(m, 'invoke_status') as erase:
            m.erase_target(self.disk, self.archive, self.manifest, **kwargs)
            erase.assert_called_once_with('Formatting target SD', 'diskutil', 'eraseDisk',
                                          'FAT32', 'XTEINKX3', 'MBR', '/dev/disk9')

    def test_legacy_backup_roundtrip(self):
        archive, manifest = m.load_backup(self.archive)
        m.restore_archive(archive, manifest, self.mount)
        m.verify_restored(self.mount, manifest)
        self.assertEqual((self.mount / '.crosspoint/state.json').read_bytes(), b'{}')

    def test_guarded_erase_success_only_mock_command(self):
        self.gate()

    def test_fixed_external_hdd_rejected(self):
        self.disk['info']['RemovableMedia'] = False
        with self.assertRaises(m.MigrationError): safety.target_identity(self.disk, m.MigrationError)

    def test_internal_nonremovable_rejected(self):
        self.disk['info'].update(Internal=True, RemovableMedia=False, BusProtocol='PCI-Express')
        with self.assertRaises(m.MigrationError): safety.target_identity(self.disk, m.MigrationError)

    def test_unknown_identity_fields_rejected(self):
        for field in ('WholeDisk', 'Writable', 'BusProtocol', 'VirtualOrPhysical', 'DeviceIdentifier'):
            with self.subTest(field=field):
                disk = copy.deepcopy(self.disk)
                del disk['info'][field]
                with self.assertRaises(m.MigrationError): safety.target_identity(disk, m.MigrationError)

    def test_missing_uuid_rejected(self):
        self.disk['partitions'][0]['info'].clear()
        with self.assertRaises(m.MigrationError): safety.target_identity(self.disk, m.MigrationError)

    def test_unmounted_or_multiple_partitions_rejected(self):
        for parts in ([], self.disk['partitions'] * 2, [dict(self.disk['partitions'][0], mount=None)]):
            disk = dict(self.disk, partitions=parts)
            with self.assertRaises(m.MigrationError): safety.target_identity(disk, m.MigrationError)

    def test_card_ceiling_rejected(self):
        self.disk['size'] = safety.MAX_CARD_BYTES + 1
        with self.assertRaises(m.MigrationError): safety.target_identity(self.disk, m.MigrationError)

    def test_time_machine_rejected(self):
        (self.mount / 'Backups.backupdb').mkdir()
        with self.assertRaises(m.MigrationError): safety.target_identity(self.disk, m.MigrationError)

    def test_apfs_target_rejected(self):
        self.disk['partitions'][0]['fstype'] = 'APFS'
        with self.assertRaises(m.MigrationError): safety.target_identity(self.disk, m.MigrationError)

    def test_protected_storage_on_target_blocks_command(self):
        for protected in (self.archive, self.archive.with_suffix('.manifest.json'), Path(m.__file__), Path.cwd()):
            with self.subTest(protected=protected), \
                 patch.object(m, 'external_disks', return_value=[self.disk]), \
                 patch.object(safety, 'physical_disks', side_effect=lambda path, *a: {'disk9'} if path.resolve() == protected.resolve() else {'disk0'}), \
                 patch.object(m, 'invoke_status') as erase:
                with self.assertRaises(m.MigrationError): m.erase_target(self.disk, self.archive, self.manifest)
                erase.assert_not_called()

    def test_unresolved_protected_storage_blocks_command(self):
        with patch.object(m, 'external_disks', return_value=[self.disk]), \
             patch.object(safety, 'physical_disks', side_effect=m.MigrationError('unresolved')), \
             patch.object(m, 'invoke_status') as erase:
            with self.assertRaises(m.MigrationError): m.erase_target(self.disk, self.archive, self.manifest)
            erase.assert_not_called()

    def test_disk_swap_same_name_size_blocks_command(self):
        swapped = copy.deepcopy(self.disk)
        swapped['partitions'][0]['info']['VolumeUUID'] = 'another-card'
        for snapshots in ([swapped], [self.disk, swapped]):
            with patch.object(m, 'external_disks', side_effect=[[d] for d in snapshots]), \
                 patch.object(safety, 'physical_disks', return_value={'disk0'}), \
                 patch.object(m, 'invoke_status') as erase:
                with self.assertRaises(m.MigrationError): m.erase_target(self.disk, self.archive, self.manifest)
                erase.assert_not_called()

    def test_source_uuid_blocks_command(self):
        self.manifest['source_disk']['volume_uuid'] = 'synthetic-target'
        self.write_zip()
        with patch.object(m, 'external_disks', return_value=[self.disk]), \
             patch.object(safety, 'physical_disks', return_value={'disk0'}), \
             patch.object(m, 'invoke_status') as erase:
            with self.assertRaises(m.MigrationError): m.erase_target(self.disk, self.archive, self.manifest)
            erase.assert_not_called()

    def test_modified_crosspoint_source_still_protected(self):
        (self.mount / '.crosspoint').mkdir()
        (self.mount / '.crosspoint/state.json').write_text('changed')
        self.assertTrue(m.source_like_target(self.disk, self.manifest))

    def test_empty_reader_check_uses_source_id(self):
        with patch('builtins.input', return_value=''), \
             patch.object(m, 'diskutil_plist', return_value={'AllDisksAndPartitions': [{'DeviceIdentifier': 'disk8'}]}), \
             patch.object(m, 'external_disks') as scan:
            with self.assertRaisesRegex(m.MigrationError, 'Source disk is still attached'):
                m.choose_target(self.manifest, 'disk8')
            scan.assert_not_called()

    def test_same_reader_reuses_disk_id_after_empty_check(self):
        with patch('builtins.input', side_effect=['', '', 'ERASE disk9', 'WIPE TARGET']), \
             patch.object(m, 'diskutil_plist', return_value={'AllDisksAndPartitions': []}), \
             patch.object(m, 'external_disks', return_value=[self.disk]), \
             patch.object(m, 'choose_disk', return_value=self.disk):
            chosen = m.choose_target(self.manifest, 'disk9')
            self.assertEqual(chosen['id'], 'disk9')

    def test_erase_revalidates_corrupt_backup_before_disk_scan(self):
        self.archive.write_bytes(b'incomplete')
        with patch.object(m, 'external_disks') as scan, patch.object(m, 'invoke_status') as erase:
            with self.assertRaises(m.MigrationError): m.erase_target(self.disk, self.archive, self.manifest)
            scan.assert_not_called()
            erase.assert_not_called()

    def test_missing_manifest(self):
        self.archive.with_suffix('.manifest.json').unlink()
        with self.assertRaises(m.MigrationError): m.load_backup(self.archive)

    def test_incomplete_zip(self):
        self.archive.write_bytes(b'PK\x03\x04')
        with self.assertRaises(zipfile.BadZipFile): m.verify_archive_contents(self.archive, self.manifest)

    def test_manifest_unsafe_paths(self):
        for name in ('../escape', '/escape', 'a/../b', 'a\\b', 'a//b', 'a/./b', 'C:evil', 'a\x00b', 'a.', 'a '):
            with self.subTest(name=name):
                manifest = copy.deepcopy(self.manifest)
                manifest['files'][0]['path'] = name
                with self.assertRaises(m.MigrationError): m.validate_manifest(manifest)

    def test_manifest_duplicate_case_alias_and_file_directory_conflict(self):
        for dirs in (['.crosspoint', '.CROSSPOINT'], ['.crosspoint', '.crosspoint/state.json']):
            manifest = dict(self.manifest, directories=dirs)
            with self.assertRaises(m.MigrationError): m.validate_manifest(manifest)

    def test_manifest_size_and_count_limits(self):
        with patch.object(m, 'MAX_BACKUP_BYTES', 1):
            with self.assertRaises(m.MigrationError): m.validate_manifest(self.manifest)
        with patch.object(m, 'MAX_ENTRIES', 1):
            with self.assertRaises(m.MigrationError): m.validate_manifest(self.manifest)
        for value in (-1, True, '2'):
            manifest = copy.deepcopy(self.manifest)
            manifest['files'][0]['size'] = value
            with self.assertRaises(m.MigrationError): m.validate_manifest(manifest)

    def test_manifest_malformed_types(self):
        for value in (None, [], {}, {'format': 'unsupported'}):
            with self.assertRaises(m.MigrationError): m.validate_manifest(value)

    def test_duplicate_json_key_rejected(self):
        self.archive.with_suffix('.manifest.json').write_text('{"format":1,"format":2}')
        with self.assertRaises(m.MigrationError): m.load_backup(self.archive)

    def test_manifest_resource_limit_before_read(self):
        with patch.object(m, 'MAX_MANIFEST_BYTES', 1):
            with self.assertRaises(m.MigrationError): m.load_backup(self.archive)

    def test_zip_traversal_duplicate_symlink_special(self):
        for name, mode in (('../escape', stat.S_IFREG), ('.crosspoint/state.json', stat.S_IFLNK),
                           ('.crosspoint/state.json', stat.S_IFIFO)):
            entry = zipfile.ZipInfo(name)
            entry.create_system = 3
            entry.external_attr = (mode | 0o600) << 16
            with zipfile.ZipFile(self.archive, 'w') as zf:
                zf.writestr('.crosspoint/', b'')
                zf.writestr(entry, b'{}')
            with self.assertRaises(m.MigrationError): m.verify_archive_contents(self.archive, self.manifest)
        self.write_zip([('.crosspoint/', b''), ('.crosspoint/', b'')])
        with self.assertRaises(m.MigrationError): m.verify_archive_contents(self.archive, self.manifest)

    def test_zip_declared_size_bomb_rejected_before_stream(self):
        self.write_zip([('.crosspoint/', b''), ('.crosspoint/state.json', b'X' * 1000)])
        with patch.object(zipfile.ZipFile, 'open', side_effect=AssertionError('must not stream')):
            with self.assertRaises(m.MigrationError): m.verify_archive_contents(self.archive, self.manifest)

    def test_archive_checksum_mismatch(self):
        self.manifest['files'][0]['sha256'] = '0' * 64
        with self.assertRaises(m.MigrationError): m.verify_archive_contents(self.archive, self.manifest)

    def test_restore_symlink_parent_cannot_escape(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.mount / '.crosspoint').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(OSError): m.restore_archive(self.archive, self.manifest, self.mount)
        self.assertEqual(list(outside.iterdir()), [])

    def test_restore_interruption_preserves_archive(self):
        original = self.archive.read_bytes()
        with patch.object(m.os, 'fsync', side_effect=OSError('injected interruption')):
            with self.assertRaises(OSError): m.restore_archive(self.archive, self.manifest, self.mount)
        self.assertEqual(original, self.archive.read_bytes())
        m.load_backup(self.archive)

    def test_source_disappears_during_backup(self):
        source = self.root / 'source'
        source.mkdir()
        (source / 'synthetic.txt').write_bytes(b'example')
        with patch.object(m, 'BACKUP_DIR', self.root / 'backup'), \
             patch.object(m.zipfile.ZipInfo, 'from_file', side_effect=OSError('source removed')):
            with self.assertRaises(OSError): m.make_backup(source, {'id':'disk8', 'name':'Synthetic', 'size': 1000})
        self.assertEqual((source / 'synthetic.txt').read_bytes(), b'example')
        self.assertFalse(list((self.root / 'backup').glob('*.partial')))
        self.assertFalse(list((self.root / 'backup').glob('*.zip')))

    def test_backup_files_private_and_repo_relative_default(self):
        self.assertEqual(m.BACKUP_DIR, Path(m.__file__).resolve().parent / 'xteink-x3-backup')
        source = self.root / 'source'
        source.mkdir()
        (source / '.hidden').write_bytes(b'synthetic')
        with patch.object(m, 'BACKUP_DIR', self.root / 'backup'):
            archive, _ = m.make_backup(source, {'id':'disk8', 'name':'Synthetic', 'size': 1000})
        for path in (archive, archive.with_suffix('.manifest.json'), archive.with_suffix('.zip.sha256')):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_diagnose_never_mutates(self):
        with patch.object(m.sys, 'argv', ['prog','--diagnose']), patch.object(m.sys, 'platform', 'darwin'), \
             patch.object(m, 'diskutil_plist', return_value={'AllDisksAndPartitions': []}), \
             patch.object(m.Path, 'iterdir', return_value=[]), patch.object(m, 'invoke_status') as status, \
             patch.object(m, 'make_backup') as backup, patch.object(m, 'erase_target') as erase:
            m.main()
            status.assert_not_called(); backup.assert_not_called(); erase.assert_not_called()

    def test_backup_only_never_formats_or_restores(self):
        with patch.object(m.sys, 'argv', ['prog','--backup-only']), patch.object(m.sys, 'platform', 'darwin'), \
             patch('builtins.input', return_value=''), patch.object(m, 'choose_source', return_value=(self.disk,self.mount)), \
             patch.object(m, 'make_backup', return_value=(self.archive,self.manifest)), patch.object(m, 'eject') as eject, \
             patch.object(m, 'erase_target') as erase, patch.object(m, 'restore_archive') as restore:
            m.main()
            erase.assert_not_called(); restore.assert_not_called(); eject.assert_called_once_with('disk9')

    def test_version_and_help(self):
        for option in ('--version','--help'):
            output = io.StringIO()
            with patch.object(m.sys, 'argv', ['prog',option]), contextlib.redirect_stdout(output):
                with self.assertRaises(SystemExit) as result: m.main()
            self.assertEqual(result.exception.code, 0)
            self.assertIn(m.__version__ if option == '--version' else '--backup-only', output.getvalue())

    def test_progress_mismatch_fails(self):
        p = m.Progress('Synthetic', 10, 1)
        p.advance(9, 1)
        with self.assertRaises(m.MigrationError): p.finish()

    def test_test_environment_blocks_real_disk_mutations(self):
        with patch.object(m.subprocess, 'Popen') as popen:
            with self.assertRaises(m.MigrationError): m.invoke_status('Test', 'diskutil', 'eraseDisk', 'fake')
            popen.assert_not_called()

    def test_physical_path_resolution(self):
        def query(verb, name):
            if verb == 'info' and name == 'disk7': return {'VirtualOrPhysical':'Physical'}
            return {'DeviceIdentifier':'disk7s1','ParentWholeDisk':'disk7'}
        self.assertEqual(safety.physical_disks(self.archive, query, m.MigrationError), {'disk7'})

    def test_apfs_physical_store_resolution(self):
        def query(*args):
            if args == ('apfs','list'):
                return {'Containers':[{'ContainerReference':'disk3', 'PhysicalStores':[{'DeviceIdentifier':'disk0s2'}]}]}
            if args == ('info','disk0'): return {'VirtualOrPhysical':'Physical'}
            if args == ('info','disk3'): return {'VirtualOrPhysical':'Virtual'}
            return {'DeviceIdentifier':'disk3s1','ParentWholeDisk':'disk3'}
        self.assertEqual(safety.physical_disks(self.archive, query, m.MigrationError), {'disk0'})

    def test_physical_resolution_unknown_fails_closed(self):
        with self.assertRaises(m.MigrationError):
            safety.physical_disks(self.archive, lambda *a: {}, m.MigrationError)

    def test_volumes_fallback_with_spaces(self):
        info = dict(self.disk['info'])
        listing = {'AllDisksAndPartitions':[{'DeviceIdentifier':'disk9','Size':self.disk['size'],
                   'Partitions':[{'DeviceIdentifier':'disk9s1'}]}]}
        volume = Path('/Volumes/NO NAME')
        def query(verb, *args):
            if verb == 'list': return listing
            if args == ('disk9',): return info
            if args == ('disk9s1',): return {'FileSystemPersonality':'ExFAT'}
            return {'DeviceIdentifier':'disk9s1','ParentWholeDisk':'disk9','MountPoint':str(volume),
                    'FileSystemPersonality':'ExFAT','VolumeUUID':'synthetic-target'}
        with patch.object(m, 'diskutil_plist', side_effect=query), \
             patch.object(m.Path, 'iterdir', return_value=[volume]), \
             patch.object(m.Path, 'is_dir', return_value=True), \
             patch.object(m.Path, 'is_symlink', return_value=False):
            disks = m.external_disks()
        self.assertEqual(disks[0]['partitions'][0]['mount'], '/Volumes/NO NAME')

    def test_backup_on_source_physical_disk_does_not_create_directory(self):
        source = self.root / 'source'
        source.mkdir()
        (source / 'synthetic.txt').write_text('example')
        destination = self.root / 'absent' / 'backup'
        with patch.object(m, 'BACKUP_DIR', destination), \
             patch.object(safety, 'physical_disks', return_value={'disk8'}):
            with self.assertRaises(m.MigrationError):
                m.make_backup(source, {'id':'disk8', 'info':{'WholeDisk':True}, 'name':'Synthetic','size':1000})
        self.assertFalse(destination.exists())

    def test_central_directory_limit_checked_before_zipfile_parse(self):
        with patch.object(m, 'MAX_ENTRIES', 1), patch.object(zipfile, 'ZipFile') as parse:
            with self.assertRaises(m.MigrationError): m.check_zip_directory_size(self.archive)
            parse.assert_not_called()

    def test_zip64_directory_compatibility(self):
        with patch.object(zipfile, 'ZIP64_LIMIT', 1):
            self.write_zip()
        m.verify_archive_contents(self.archive, self.manifest)

    def test_same_reader_internal_removable_target(self):
        self.disk['info'].update(Internal=True, BusProtocol='Secure Digital')
        self.assertTrue(safety.target_identity(self.disk, m.MigrationError))

    def test_mount_vanishes_before_guard_blocks_command(self):
        self.mount.rmdir()
        with patch.object(m, 'external_disks', return_value=[self.disk]), patch.object(m, 'invoke_status') as erase:
            with self.assertRaises(m.MigrationError): m.erase_target(self.disk, self.archive, self.manifest)
            erase.assert_not_called()

    def test_partition_uuid_changes_after_format_not_hardware_identity(self):
        disk = copy.deepcopy(self.disk)
        disk['info']['DiskUUID'] = 'new-partition-map'
        self.assertEqual(safety.hardware_identity(disk), safety.hardware_identity(self.disk))
        self.assertNotEqual(safety.target_identity(disk, m.MigrationError), self.disk['confirmed_identity'])

    def test_erase_capacity_and_fat_limit_preflight(self):
        self.manifest['source_disk']['capacity_bytes'] = self.disk['size'] + 1
        self.write_zip()
        with patch.object(m, 'external_disks', return_value=[self.disk]), \
             patch.object(safety, 'physical_disks', return_value={'disk0'}), \
             patch.object(m, 'invoke_status') as erase:
            with self.assertRaises(m.MigrationError): m.erase_target(self.disk, self.archive, self.manifest)
            erase.assert_not_called()
        self.gate(allow_smaller=True)

    def test_progress_zero_byte_mismatch(self):
        progress = m.Progress('Synthetic', 0, 1)
        with self.assertRaises(m.MigrationError): progress.finish()



if __name__ == '__main__':
    unittest.main()
