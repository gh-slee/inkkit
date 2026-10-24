"""Mock macOS identity queries; all files are invented temporary fixtures."""
import copy
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import inkkit_config as config
import inkkit_volume as volume


class VolumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.mounts = self.base / 'Volumes'
        self.mounts.mkdir()
        self.card = self.mounts / 'EXAMPLE'
        self.card.mkdir()
        (self.card / '.crosspoint').mkdir()
        self.settings = self.card / '.crosspoint' / 'crossink-settings.json'
        self.settings.write_bytes(b'{"deviceName":"Example reader","future":42}\n')
        self.host = self.base / 'ApplicationSupport'
        self.host.mkdir()
        self.info = dict(DeviceIdentifier='disk77', WholeDisk=True, TotalSize=16_000_000_000,
                         Internal=False, RemovableMedia=True, Writable=True, ReadOnlyMedia=False,
                         BusProtocol='USB', VirtualOrPhysical='Physical', MediaUUID='example-media')
        self.part = dict(DeviceIdentifier='disk77s1', ParentWholeDisk='disk77',
                         MountPoint=str(self.card), FilesystemName='MS-DOS FAT32', VolumeName='EXAMPLE',
                         VolumeUUID='example-volume', DiskUUID='example-partition', FreeSpace=1_000_000)
        self.layout = dict(AllDisksAndPartitions=[dict(DeviceIdentifier='disk77', Partitions=[dict(DeviceIdentifier='disk77s1')])])
        self.patches = [patch.object(volume, '_mount_parent', return_value=self.mounts),
                        patch.object(volume, '_is_mount', return_value=True),
                        patch.object(volume, '_support_parent', return_value=self.host),
                        patch.object(volume, '_query', side_effect=self.query)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(self.temp.cleanup)

    def query(self, operation, target):
        if operation == 'list':
            return copy.deepcopy(self.layout)
        return copy.deepcopy(self.info if target == 'disk77' else self.part)

    def open(self):
        # Temporary fixtures share one host device. Mock only this separation
        # boundary for positive tests; its fail-closed policy is tested below.
        return volume.open_card(str(self.card), 'X3', '1.6.1', True)

    def test_explicit_open_preview_apply_restore_and_targeted_eject(self):
        with patch.object(volume, 'ensure_separate_storage'):
            before = self.settings.read_bytes()
            ref = self.open()
            self.assertTrue(ref.startswith('card:'))
            self.assertEqual(self.settings.read_bytes(), before)
            self.assertEqual(set(self.card.iterdir()), {self.card / '.crosspoint'})
            snap = config.read_settings(ref)
            self.assertFalse(snap['synthetic'])
            self.assertEqual(snap['model'], 'X3')
            result = config.apply_changes(ref, snap['token'], {'deviceName': 'Example changed'})
            backups = Path(volume.backup_location(ref))
            self.assertEqual((backups / 'backups' / result['backup_id'] / 'before.bin').read_bytes(), before)
            self.assertEqual(stat.S_IMODE(backups.stat().st_mode), 0o700)
            config.restore_backup(ref, result['snapshot']['token'], result['backup_id'])
            self.assertEqual(self.settings.read_bytes(), before)
            self.part['FreeSpace'] -= 1000
            self.assertEqual(config.read_settings(ref)['values']['deviceName'], 'Example reader')
            with patch.object(volume, '_eject_command') as eject:
                self.assertTrue(volume.eject_card(ref)['ejected'])
                eject.assert_called_once_with('disk77')

    def test_eject_releases_card_handles_while_retaining_host_lock(self):
        with patch.object(volume, 'ensure_separate_storage'):
            reference = self.open()
            storage = Path(volume.backup_location(reference))
            original_workspace = config._Workspace
            created = []

            def workspace(*args, **kwargs):
                item = original_workspace(*args, **kwargs)
                created.append(item)
                return item

            def eject(disk):
                self.assertEqual(disk, 'disk77')
                self.assertTrue(created)
                for item in created:
                    self.assertIsNone(item.fd)
                    self.assertIsNone(item.config)
                fd = os.open(storage / '.inkkit-lock', os.O_RDWR)
                try:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                finally:
                    os.close(fd)

            with patch.object(config, '_Workspace', side_effect=workspace), patch.object(volume, '_eject_command', side_effect=eject) as command:
                self.assertTrue(volume.eject_card(reference)['ejected'])
                command.assert_called_once_with('disk77')
            fd = os.open(storage / '.inkkit-lock', os.O_RDWR)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(fd)

    def test_eject_failure_preserves_readable_session_and_allows_retry(self):
        with patch.object(volume, 'ensure_separate_storage'):
            reference = self.open()
            before = self.settings.read_bytes()
            with patch.object(volume, '_eject_command', side_effect=[config.ConfigError('eject', 'Example busy card'), None]) as command:
                with self.assertRaises(config.ConfigError) as error:
                    volume.eject_card(reference)
                self.assertEqual(error.exception.code, 'eject')
                self.assertFalse(config.read_settings(reference)['synthetic'])
                self.assertTrue(volume.eject_card(reference)['ejected'])
                self.assertEqual(command.call_count, 2)
            self.assertEqual(self.settings.read_bytes(), before)

    def test_eject_rechecks_card_identity_after_closing_handles(self):
        with patch.object(volume, 'ensure_separate_storage'):
            reference = self.open()
            original_workspace = config._Workspace
            original_context = volume.session_context
            created = []

            def workspace(*args, **kwargs):
                item = original_workspace(*args, **kwargs)
                created.append(item)
                return item

            def context(ref):
                if created and created[0].context is not None and created[0].fd is None:
                    self.part['VolumeUUID'] = 'example-replacement'
                return original_context(ref)

            with patch.object(config, '_Workspace', side_effect=workspace), patch.object(volume, 'session_context', side_effect=context), patch.object(volume, '_eject_command') as command:
                with self.assertRaises(config.ConfigError) as error:
                    volume.eject_card(reference)
                self.assertEqual(error.exception.code, 'card_changed')
                command.assert_not_called()

    def test_explicit_mounted_true_remains_supported(self):
        self.part['Mounted'] = True
        self.assertEqual(volume._inspect(self.card, 'X3')['root'], str(self.card))

    def test_explicit_unmounted_or_malformed_mounted_flags_are_rejected(self):
        for value in (False, None, 0, 1, 'true', {}, []):
            with self.subTest(value=value):
                self.part['Mounted'] = value
                with self.assertRaises(config.ConfigError) as error:
                    self.open()
                self.assertEqual(error.exception.code, 'mount')
                self.assertFalse((self.host / 'InkKit').exists())

    def test_missing_mounted_flag_does_not_allow_an_ordinary_directory(self):
        with patch.object(volume, '_is_mount', return_value=False), patch.object(volume, '_query') as query:
            with self.assertRaises(config.ConfigError) as error:
                self.open()
            self.assertEqual(error.exception.code, 'mount')
            query.assert_not_called()
        self.assertFalse((self.host / 'InkKit').exists())

    def test_missing_mounted_flag_still_rechecks_mount_before_apply(self):
        with patch.object(volume, 'ensure_separate_storage'):
            before = self.settings.read_bytes()
            reference = self.open()
            snapshot = config.read_settings(reference)
            storage = Path(volume.backup_location(reference))
            for change in ({'MountPoint': None}, {'MountPoint': str(self.mounts / 'OTHER')}, {'Mounted': False}):
                original = self.part.copy()
                self.part.update(change)
                with self.subTest(change=change), self.assertRaises(config.ConfigError) as error:
                    config.apply_changes(reference, snapshot['token'], {'deviceName': 'Example changed'})
                self.assertEqual(error.exception.code, 'mount')
                self.assertEqual(self.settings.read_bytes(), before)
                self.assertFalse((storage / 'backups').exists())
                self.part = original

    def test_unknown_firmware_model_and_absent_explicit_confirmation(self):
        for model, firmware, confirmed in (('X3', 'latest', True), ('X4 Pro', '1.6.1', False), ('Sticky', '1.6.1', True), ('X3', '1.6.1', 1)):
            with self.assertRaises(config.ConfigError):
                volume.open_card(str(self.card), model, firmware, confirmed)
        self.assertFalse((self.host / 'InkKit').exists())

    def test_unknown_future_firmware_and_devices_fail_before_disk_queries(self):
        for model, firmware in [('X3', '1.6.2'), ('X3', '2.0.0'), ('X3', 'nightly'), ('Future reader', '1.6.1')]:
            with self.subTest(model=model, firmware=firmware), patch.object(volume, '_query') as query:
                with self.assertRaises(config.ConfigError) as error:
                    volume.open_card(str(self.card), model, firmware, True)
                self.assertEqual(error.exception.code, 'profile')
                query.assert_not_called()
        self.assertFalse((self.host / 'InkKit').exists())

    def test_internal_virtual_fixed_unknown_readonly_and_nonfat_are_rejected(self):
        original_info, original_part = self.info.copy(), self.part.copy()
        changes = [('info', 'Internal', True), ('info', 'Internal', None), ('info', 'Virtual', True),
                   ('info', 'VirtualOrPhysical', 'Virtual'), ('info', 'RemovableMedia', False),
                   ('info', 'Writable', False), ('info', 'BusProtocol', 'Apple Fabric'),
                   ('part', 'ReadOnlyVolume', True), ('part', 'FilesystemName', 'APFS'),
                   ('part', 'VolumeUUID', ''), ('part', 'VolumeName', 'Time Machine Backup')]
        for container, key, value in changes:
            self.info, self.part = original_info.copy(), original_part.copy()
            if key == 'VolumeUUID': self.part.pop('DiskUUID')
            getattr(self, container)[key] = value
            with self.subTest(container=container, key=key), self.assertRaises(config.ConfigError):
                volume._inspect(self.card, 'X3')
        self.assertFalse((self.host / 'InkKit').exists())

    def test_layout_mount_symlink_and_firmware_recovery_are_blocked(self):
        self.layout['AllDisksAndPartitions'][0]['Partitions'].append(dict(DeviceIdentifier='disk77s2'))
        with self.assertRaises(config.ConfigError): volume._inspect(self.card, 'X3')
        self.layout['AllDisksAndPartitions'][0]['Partitions'].pop()
        self.part['MountPoint'] = '/Volumes/EXAMPLE_OTHER'
        with self.assertRaises(config.ConfigError): volume._inspect(self.card, 'X3')
        self.part['MountPoint'] = str(self.card)
        alias = self.mounts / 'ALIAS'
        alias.symlink_to(self.card, target_is_directory=True)
        with self.assertRaises(config.ConfigError): volume._inspect(alias, 'X3')
        (self.card / '.crosspoint' / 'crossink-settings.json.bak').write_bytes(b'{}')
        with patch.object(volume, 'ensure_separate_storage'):
            ref = self.open()
            with self.assertRaises(config.ConfigError): config.read_settings(ref)
        self.assertEqual(self.settings.read_bytes(), b'{"deviceName":"Example reader","future":42}\n')

    def test_same_device_host_storage_fails_before_creating_records(self):
        with self.assertRaises(config.ConfigError) as error:
            self.open()
        self.assertEqual(error.exception.code, 'unsafe_backup')
        self.assertFalse((self.host / 'InkKit').exists())
        volume.ensure_separate_storage(SimpleNamespace(st_dev=1), SimpleNamespace(st_dev=2))
        with self.assertRaises(config.ConfigError):
            volume.ensure_separate_storage(SimpleNamespace(st_dev=2), SimpleNamespace(st_dev=2))

    def test_card_replaced_reused_disk_id_and_session_tamper_refused(self):
        with patch.object(volume, 'ensure_separate_storage'):
            ref = self.open()
            snapshot = config.read_settings(ref)
            original_uuid = self.part['VolumeUUID']
            self.part['VolumeUUID'] = 'example-replacement'
            with self.assertRaises(config.ConfigError):
                config.apply_changes(ref, snapshot['token'], {'deviceName': 'Example changed'})
            self.part['VolumeUUID'] = original_uuid
            session = self.host / 'InkKit' / 'Sessions' / (ref[5:] + '.json')
            record = json.loads(session.read_bytes())
            record['storage'] = str(self.card)
            session.write_text(json.dumps(record))
            with self.assertRaises(config.ConfigError): config.read_settings(ref)
            with self.assertRaises(config.ConfigError): volume.session_context('card:../../example')

    def test_unsafe_host_directory_symlink_and_permissions_rejected(self):
        target = self.base / 'elsewhere'
        target.mkdir()
        link = self.host / 'InkKit'
        link.symlink_to(target, target_is_directory=True)
        with patch.object(volume, 'ensure_separate_storage'), self.assertRaises(OSError): self.open()
        link.unlink()
        link.mkdir(mode=0o755)
        with patch.object(volume, 'ensure_separate_storage'), self.assertRaises(config.ConfigError): self.open()

    def test_testing_guard_prevents_actual_queries_and_eject_subprocesses(self):
        # Bypass this fixture's mock and call the real guarded implementations.
        self.patches[-1].stop()
        with patch.dict(os.environ, XTEINK_TESTING='1'), patch.object(volume.subprocess, 'run') as run:
            with self.assertRaises(config.ConfigError): volume._query('info', 'disk77')
            with self.assertRaises(config.ConfigError): volume._eject_command('disk77')
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
