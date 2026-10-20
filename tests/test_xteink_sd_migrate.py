import importlib.util
import os
os.environ["XTEINK_TESTING"] = "1"
import json
import tempfile
import unittest
from pathlib import Path
import plistlib
from unittest.mock import patch
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('migrate', str(Path(__file__).resolve().parents[1] / 'xteink_sd_migrate.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.object(m, 'diskutil_plist', return_value={'AllDisksAndPartitions': []}).start()
        patch.object(m.disk_safety, 'target_identity', return_value=('test', 'uuid')).start()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old = self.root / 'old'
        self.new = self.root / 'new'
        self.old.mkdir(); self.new.mkdir()
        (self.old/'.crosspoint').mkdir()
        (self.old/'.crosspoint'/'crossink-settings.json').write_text('{"reader":"CrossInk"}')
        (self.old/'.crosspoint'/'epub_42').mkdir()
        (self.old/'.crosspoint'/'epub_42'/'progress.bin').write_bytes(b'\x00\x12')
        (self.old/'.crossink-stats-backup').mkdir()
        (self.old/'.crossink-stats-backup'/'backup.bin').write_bytes(b'123')
        (self.old/'.fonts'/'NotoSansTC').mkdir(parents=True)
        (self.old/'.fonts'/'NotoSansTC'/'NotoSansTC_14.cpfont').write_bytes(b'\x10fontdata')
        (self.old/'Books').mkdir()
        (self.old/'Books'/'合成測試.epub').write_bytes(b'PK\x00book')
        (self.old/'Books'/'EMPTY').mkdir()
        (self.old/'.DS_Store').write_text('mac junk')
        (self.old/'.Spotlight-V100').mkdir()
        (self.old/'.Spotlight-V100'/'index').write_bytes(b'junk')
        self.addCleanup(setattr, m, 'BACKUP_DIR', m.BACKUP_DIR)
        m.BACKUP_DIR = self.root/'xteink-x3-backup'
        self.disk = { 'id':'disk8', 'name':'TestSD', 'size':4*1024**3, 'partitions':[] }
    def tearDown(self): self.tmp.cleanup()
    def test_complete(self):
        self.assertTrue(m.source_signature(self.old))
        archive, manifest = m.make_backup(self.old,self.disk)
        self.assertEqual(manifest['file_count'], 5)
        self.assertFalse(any('.DS_Store' in f['path'] for f in manifest['files']))
        archive, reloaded = m.load_backup(archive)
        m.restore_archive(archive,reloaded,self.new)
        m.verify_restored(self.new,reloaded)
        self.assertEqual((self.new/'Books'/'合成測試.epub').read_bytes(), b'PK\x00book')
        self.assertTrue((self.new/'Books'/'EMPTY').is_dir())
        (self.new/'Books'/'合成測試.epub').write_bytes(b'wrong')
        with self.assertRaises(m.MigrationError): m.verify_restored(self.new,reloaded)
    def test_large_file_progress_and_restore(self):
        # Exercise more than one CHUNK while preserving hidden files & Unicode paths.
        payload = bytes(range(256)) * (m.CHUNK // 256 + 3)
        (self.old/'Books'/'測試 Large.epub').write_bytes(payload)
        archive, manifest = m.make_backup(self.old, self.disk)
        archive, loaded = m.load_backup(archive)
        m.restore_archive(archive, loaded, self.new)
        m.verify_restored(self.new, loaded)
        self.assertEqual((self.new/'Books'/'測試 Large.epub').read_bytes(), payload)
        self.assertEqual(loaded['total_bytes'], len(payload) + 42)

    def test_zero_byte_file_roundtrip(self):
        (self.old/'Books'/'empty.epub').write_bytes(b'')
        archive, manifest = m.make_backup(self.old, self.disk)
        m.restore_archive(archive, manifest, self.new)
        m.verify_restored(self.new, manifest)
        self.assertEqual((self.new/'Books'/'empty.epub').stat().st_size, 0)

    def test_byte_progress_counts_all_bytes(self):
        with patch.object(m.sys.stdout, 'isatty', return_value=False):
            p = m.Progress('Mock read', 1024, 2)
            p.advance(512, 1)
            p.advance(512, 1)
            p.finish()
        self.assertEqual(p.bytes, 1024)
        self.assertEqual(p.files, 2)

    def test_corrupt_backup_rejected(self):
        archive, manifest = m.make_backup(self.old,self.disk)
        with archive.open('ab') as f: f.write(b'hello')
        with self.assertRaises(m.MigrationError): m.load_backup(archive)
    def test_symlink_rejected(self):
        (self.old/'Books'/'link.epub').symlink_to('/etc/hosts')
        with self.assertRaises(m.MigrationError): m.iter_source(self.old)
    def test_space_calculation_includes_fat32_cluster_slack(self):
        manifest = {
            'total_bytes': 5,
            'files': [{'size': 1}, {'size': 4}],
            'directories': ['a'],
        }
        self.assertEqual(m.required_allocated_space(manifest),
                         3 * 65536 + 32 * 1024 * 1024)

    def test_post_format_space_check_fails_closed(self):
        manifest = {'total_bytes': 1024,
                    'files': [{'size': 1024}], 'directories': []}
        with patch.object(m.os, 'statvfs', return_value=SimpleNamespace(f_frsize=4096, f_bsize=4096)), \
             patch.object(m.shutil, 'disk_usage', return_value=SimpleNamespace(free=1000)):
            with self.assertRaisesRegex(m.MigrationError, 'Not enough usable space'):
                m.check_formatted_target_space(self.new, manifest)

    def test_post_format_space_check_accepts_sufficient_space(self):
        manifest = {'total_bytes': 1024,
                    'files': [{'size': 1024}], 'directories': []}
        with patch.object(m.os, 'statvfs', return_value=SimpleNamespace(f_frsize=4096, f_bsize=4096)), \
             patch.object(m.shutil, 'disk_usage', return_value=SimpleNamespace(free=100*1024*1024)):
            m.check_formatted_target_space(self.new, manifest)

    def test_target_rejects_smaller_physical_card_by_default(self):
        manifest = {'total_bytes': 1000, 'files': [{'size': 1000}], 'directories': [],
                    'source_disk': {'capacity_bytes': 64 * 1024**3}}
        target = {'id':'disk8', 'size':32 * 1024**3, 'name':'Target',
                  'partitions':[], 'identity': ('Target',32 * 1024**3,'USB','External')}
        with patch.object(m, 'external_disks', return_value=[target]), \
             patch.object(m, 'choose_disk', return_value=target), \
             patch.object(m, 'source_like_target', return_value=False), \
             patch('builtins.input', return_value=''):
            with self.assertRaisesRegex(m.MigrationError, 'smaller than source'):
                m.choose_target(manifest, None)

    def test_probe_same_source(self):
        archive, manifest = m.make_backup(self.old,self.disk)
        disk = {'id':'disk8', 'partitions':[{'mount':str(self.old)}]}
        self.assertTrue(m.source_like_target(disk,manifest))

class FormatTests(unittest.TestCase):
    def test_normalized_filesystem_not_confused(self):
        self.assertEqual(m.normalized_fs('ExFAT'), 'exfat')
        self.assertEqual(m.normalized_fs('MS-DOS FAT32'), 'fat32')
        self.assertEqual(m.normalized_fs('Windows_FAT_32'), 'fat32')
        self.assertIsNone(m.normalized_fs('APFS'))

    def test_preserve_source_and_legacy_archive(self):
        self.assertEqual(m.resolve_target_fs('source', {'source_disk': {'filesystem': 'ExFAT'}}), 'exfat')
        self.assertEqual(m.resolve_target_fs('source', {'source_disk': {'filesystem': 'MS-DOS FAT32'}}), 'fat32')
        with self.assertRaises(m.MigrationError):
            m.resolve_target_fs('source', {'source_disk': {}})

    def test_fat32_rejects_large_file_exfat_allows(self):
        manifest = {'files': [{'path': 'huge.epub', 'size': 2**32}]}
        with self.assertRaises(m.MigrationError):
            m.check_fs_file_limits(manifest, 'fat32')
        m.check_fs_file_limits(manifest, 'exfat')
        manifest['files'][0]['size'] = 2**32 - 1
        m.check_fs_file_limits(manifest, 'fat32')

    def test_formatted_target_requires_exact_fs_and_mbr(self):
        from unittest.mock import patch
        disks = [{'id': 'disk5', 'partitions': [{'mount': '/Volumes/XTEINKX3', 'fstype': 'ExFAT'}]}]
        layout = {'AllDisksAndPartitions': [{'DeviceIdentifier': 'disk5', 'Content': 'FDisk_partition_scheme'}]}
        with patch.object(m, 'external_disks', return_value=disks), patch.object(m, 'diskutil_plist', return_value=layout):
            self.assertEqual(m.after_format_volume('disk5', 'exfat').as_posix(), '/Volumes/XTEINKX3')
            with self.assertRaises(m.MigrationError):
                m.after_format_volume('disk5', 'fat32')
        with patch.object(m, 'external_disks', return_value=disks), patch.object(m, 'diskutil_plist', return_value={'AllDisksAndPartitions':[{'DeviceIdentifier':'disk5', 'Content':'GUID_partition_scheme'}]}):
            with self.assertRaises(m.MigrationError):
                m.after_format_volume('disk5', 'exfat')


class AutoFormatPolicyTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.object(m, 'diskutil_plist', return_value={'AllDisksAndPartitions': []}).start()
        patch.object(m.disk_safety, 'target_identity', return_value=('test', 'uuid')).start()

    def test_boundary_and_different_card_sizes(self):
        small32 = 32 * 1024**3
        manifest = {'source_disk': {'filesystem': 'ExFAT'}}
        self.assertEqual(m.resolve_target_fs('auto', manifest, 16 * 10**9), 'fat32')
        self.assertEqual(m.resolve_target_fs('auto', manifest, 32 * 10**9 + 80_000_000), 'fat32')
        self.assertEqual(m.resolve_target_fs('auto', manifest, small32), 'fat32')
        self.assertEqual(m.resolve_target_fs('auto', manifest, small32 + 1), 'exfat')
        self.assertEqual(m.resolve_target_fs('auto', manifest, 64 * 10**9), 'exfat')
        self.assertEqual(m.resolve_target_fs('auto', manifest, 256 * 10**9), 'exfat')

    def test_requires_target_size_and_manual_source_overrides(self):
        manifest = {'source_disk': {'filesystem': 'ExFAT'}}
        with self.assertRaises(m.MigrationError):
            m.resolve_target_fs('auto', manifest)
        with self.assertRaises(m.MigrationError):
            m.resolve_target_fs('auto', manifest, 0)
        self.assertEqual(m.resolve_target_fs('fat32', manifest, 64 * 10**9), 'fat32')
        self.assertEqual(m.resolve_target_fs('exfat', manifest, 16 * 10**9), 'exfat')
        self.assertEqual(m.resolve_target_fs('source', manifest, 16 * 10**9), 'exfat')

    def test_selected_card_is_used_for_format_and_confirmations(self):
        capacity = 64 * 10**9
        source_capacity = 16 * 10**9
        target = {'id': 'disk9', 'size': capacity, 'name': 'Test card',
                  'partitions': [], 'identity': ('Test card', capacity, 'USB', 'External')}
        manifest = {'total_bytes': 42, 'files': [{'path': 'book.epub', 'size': 42}],
                    'directories': [], 'source_disk': {'capacity_bytes': source_capacity,
                                                        'filesystem': 'FAT32'}}
        with patch.object(m, 'external_disks', return_value=[target]), \
             patch.object(m, 'choose_disk', return_value=target), \
             patch.object(m, 'source_like_target', return_value=False), \
             patch('builtins.input', side_effect=['', '', 'ERASE disk9', 'WIPE TARGET']):
            chosen = m.choose_target(manifest, 'disk8', filesystem='auto')
        self.assertEqual(chosen['target_filesystem'], 'exfat')
        self.assertEqual(chosen['size'], capacity)

    def test_auto_fat32_rejects_large_file_before_wipe(self):
        capacity = 32 * 10**9
        target = {'id': 'disk9', 'size': capacity, 'name': 'Test card',
                  'partitions': [], 'identity': ('Test card', capacity, 'USB', 'External')}
        manifest = {'total_bytes': 2**32, 'files': [{'path': 'huge.bin', 'size': 2**32}],
                    'directories': [], 'source_disk': {'capacity_bytes': capacity,
                                                        'filesystem': 'ExFAT'}}
        with patch.object(m, 'external_disks', return_value=[target]), \
             patch.object(m, 'choose_disk', return_value=target), \
             patch.object(m, 'source_like_target', return_value=False), \
             patch('builtins.input', side_effect=['', '']):
            with self.assertRaisesRegex(m.MigrationError, 'larger than 4 GiB'):
                m.choose_target(manifest, 'disk8', filesystem='auto')

    def test_main_formats_with_actual_selected_auto_fs(self):
        # Test wiring through main without touching a disk.
        manifest = {'total_bytes': 0, 'files': [], 'directories': [],
                    'source_disk': {'capacity_bytes': 0, 'filesystem': 'FAT32'}}
        archive = Path('/tmp/fake-x3-backup.zip')
        for resolved in ('fat32', 'exfat'):
            with self.subTest(resolved=resolved), \
                 patch.object(m.sys, 'platform', 'darwin'), \
                 patch.object(m.sys, 'argv', ['prog', '--restore', str(archive)]), \
                 patch.object(m, 'load_backup', return_value=(archive, manifest)), \
                 patch.object(m, 'choose_target', return_value={'id': 'disk9', 'target_filesystem': resolved}) as chooser, \
                 patch.object(m, 'erase_target') as gate, \
                 patch.object(m, 'external_disks', return_value=[{'id':'disk9'}]), \
                 patch.object(m, 'after_format_volume', return_value=Path('/tmp')), \
                 patch.object(m, 'check_formatted_target_space'), \
                 patch.object(m, 'restore_archive'), \
                 patch.object(m, 'verify_restored'), \
                 patch.object(m, 'eject'):
                m.main()
                self.assertEqual(chooser.call_args.kwargs['filesystem'], 'auto')
                self.assertEqual(gate.call_args.args[0]['target_filesystem'], resolved)


class DetectionRegressionTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.object(m.Path, 'iterdir', return_value=iter(())).start()

    def test_removable_internal_reader_with_unknown_physical_is_eligible(self):
        self.assertTrue(m.valid_external({'WholeDisk':True, 'Internal':True,
                                          'RemovableMedia':True, 'VirtualOrPhysical':'Unknown',
                                          'BusProtocol':'Secure Digital'}))

    def test_internal_ssd_still_rejected(self):
        self.assertFalse(m.valid_external({'WholeDisk':True, 'Internal':True,
                                           'RemovableMedia':False, 'VirtualOrPhysical':'Unknown',
                                           'BusProtocol':'PCI-Express'}))

    def test_virtual_disk_image_rejected_even_if_external(self):
        self.assertFalse(m.valid_external({'WholeDisk':True, 'Internal':False,
                                           'RemovableMedia':True, 'VirtualOrPhysical':'Virtual'}))

    def test_removable_string_values(self):
        self.assertTrue(m.removable_media({'RemovableMedia':'Removable'}))
        self.assertFalse(m.removable_media({'RemovableMedia':'Fixed'}))

    def test_missing_virtual_field_for_usb_reader(self):
        self.assertTrue(m.valid_external({'Internal':False, 'WholeDisk':True,
                                          'BusProtocol':'USB'}))

    def test_empty_crosspoint_is_possible_source_after_manual_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'.crosspoint').mkdir()
            self.assertIn('Possible CrossInk', m.source_signature(Path(temp)))

    def test_partitions_in_diskutil_list_are_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            vol = str(Path(temp))
            disk_list = {'AllDisksAndPartitions':[
                {'DeviceIdentifier':'disk0','Size':1_000_000_000,'Partitions':[]},
                {'DeviceIdentifier':'disk8','Size':16_000_000_000,
                 'Partitions':[{'DeviceIdentifier':'disk8s1','MountPoint':vol,'Content':'Microsoft Basic Data'}]}
            ]}
            info = {
                'disk0': {'WholeDisk':True, 'Internal':True, 'RemovableMedia':False,
                          'VirtualOrPhysical':'Unknown','BusProtocol':'PCI-Express'},
                'disk8': {'WholeDisk':True, 'Internal':True, 'RemovableMedia':True,
                          'VirtualOrPhysical':'Unknown','BusProtocol':'Secure Digital',
                          'MediaName':'Card','TotalSize':16_000_000_000},
                'disk8s1': {'MountPoint':vol,'FileSystemPersonality':'ExFAT'}
            }
            def fake(verb, *args):
                return disk_list if verb == 'list' else info[args[0]]
            with patch.object(m, 'diskutil_plist', side_effect=fake), \
                 patch.object(m,'valid_mount_path',side_effect=lambda value: value if value == vol else None):
                result = m.external_disks()
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['id'],'disk8')
            self.assertEqual(result[0]['partitions'][0]['mount'], vol)



class MacOSDiskutilArgOrderTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.object(m.Path, 'iterdir', return_value=iter(())).start()

    def test_info_plist_flag_before_identifier(self):
        expected = {"DeviceIdentifier": "disk6", "Internal": False}
        with patch.object(m, "invoke", return_value=plistlib.dumps(expected)) as call:
            result = m.diskutil_plist("info", "disk6")
        self.assertEqual(result, expected)
        call.assert_called_once_with("diskutil", "info", "-plist", "disk6")

    def test_info_plist_flag_before_volume_path_with_spaces(self):
        with patch.object(m, "invoke", return_value=plistlib.dumps({"DeviceIdentifier":"disk6s1"})) as call:
            m.diskutil_plist("info", "/Volumes/NO NAME")
        call.assert_called_once_with("diskutil", "info", "-plist", "/Volumes/NO NAME")

    def test_list_plist_flag_works_in_subcommand_position(self):
        with patch.object(m, "invoke", return_value=plistlib.dumps({"AllDisksAndPartitions":[]})) as call:
            self.assertEqual(m.diskutil_plist("list"), {"AllDisksAndPartitions":[]})
        call.assert_called_once_with("diskutil", "list", "-plist")

    def test_disk_scan_uses_valid_info_argument_order(self):
        def fake_invoke(*args):
            self.assertEqual(args[:3], ("diskutil", args[1], "-plist"))
            if args[1] == "list":
                return plistlib.dumps({"AllDisksAndPartitions": [
                    {"DeviceIdentifier":"disk0", "Size": 1_000_000_000, "Partitions":[]},
                    {"DeviceIdentifier":"disk6", "Size": 64_000_000_000, "Partitions":[]},
                ]})
            if args[1] == "info" and args[3] == "disk0":
                return plistlib.dumps({"WholeDisk": True, "Internal": True, "RemovableMedia": False})
            if args[1] == "info" and args[3] == "disk6":
                return plistlib.dumps({"WholeDisk": True, "Internal": False, "RemovableMedia": True,
                                       "MediaName":"USB SD Reader", "TotalSize":64_000_000_000})
            raise AssertionError(args)
        with patch.object(m, "invoke", side_effect=fake_invoke):
            disks = m.external_disks()
        self.assertEqual([d["id"] for d in disks], ["disk6"])

if __name__ == '__main__': unittest.main()
