"""Synthetic-only configuration safety and persistence regressions."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch

import inkkit_config as config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(config.create_demo())
        self.path = self.root / '.crosspoint' / config.SETTINGS_FILE
        self.original = self.path.read_bytes()

    def tearDown(self):
        shutil.rmtree(self.root)

    def snapshot(self):
        return config.read_settings(self.root)

    def apply(self, changes):
        return config.apply_changes(self.root, self.snapshot()['token'], changes)

    def assertCode(self, code, function, *args):
        with self.assertRaises(config.ConfigError) as caught:
            function(*args)
        self.assertEqual(caught.exception.code, code)
        self.assertNotIn(str(self.root), str(caught.exception))

    def tree(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file()}

    def test_read_preview_and_list_have_no_writes(self):
        before = self.tree()
        snapshot = self.snapshot()
        diff = config.preview_changes(self.root, snapshot['token'], {'lineHeightPercent': 120})
        self.assertEqual(diff[0]['before'], 100)
        self.assertEqual(diff[0]['after'], 120)
        self.assertEqual(config.list_backups(self.root), [])
        self.assertEqual(self.tree(), before)

    def test_restore_preview_is_read_only_and_shows_effective_differences(self):
        result = self.apply({'lineHeightPercent': 120, 'sleepTimeoutMinutes': 31})
        before = self.tree()
        diff = config.preview_restore(self.root, result['snapshot']['token'], result['backup_id'])
        self.assertEqual({d['key']: d['after'] for d in diff}, dict(lineHeightPercent=100, sleepTimeoutMinutes=10))
        self.assertEqual(self.tree(), before)

    def test_apply_backup_exact_restore_and_unknown_values(self):
        result = self.apply({'lineHeightPercent': 123, 'deviceName': 'Example X3'})
        doc = json.loads(self.path.read_bytes())
        self.assertEqual(doc['futureOption'], json.loads(self.original)['futureOption'])
        self.assertEqual(doc['lineHeightPercent'], 123)
        self.assertIs(type(doc['embeddedStyle']), int)
        backup = self.root / 'backups' / result['backup_id']
        self.assertEqual((backup / 'before.bin').read_bytes(), self.original)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((backup / 'before.bin').stat().st_mode), 0o600)
        self.assertEqual(config.list_backups(self.root)[0]['state'], 'written')
        config.restore_backup(self.root, result['snapshot']['token'], result['backup_id'])
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(config.list_backups(self.root)[0]['state'], 'restored')

    def test_noop_preserves_bytes_and_does_not_create_backup(self):
        result = self.apply({'lineHeightPercent': 100})
        self.assertFalse(result['changed'])
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse((self.root / 'backups').exists())

    def test_missing_defaults_are_not_materialized(self):
        self.path.write_bytes(b'{"future":42}\n')
        self.apply({'lineHeightPercent': 100})
        self.assertEqual(self.path.read_bytes(), b'{"future":42}\n')
        self.apply({'lineHeightPercent': 120})
        self.assertEqual(json.loads(self.path.read_bytes()), dict(future=42, lineHeightPercent=120))

    def test_byte_limits_empty_device_name_and_sleep_sentinel(self):
        for name in ('', 'AB', '\u95b1\u8b80\u5668', 'a' * 20):
            self.apply({'deviceName': name})
        for name in ('a', 'a' * 21, '\u95b1' * 7, 'AB\0', 'AB\n', '\ud800'):
            self.assertCode('invalid_value', self.apply, {'deviceName': name})
        self.apply({'sleepTimeoutMinutes': 31})
        self.assertEqual(self.snapshot()['values']['sleepTimeoutMinutes'], 31)

    def test_numeric_bounds_and_bool_float_rejected(self):
        for key, values in {'lineHeightPercent': [69, 201, True, 100.0],
                            'wordSpacing': [-1, 5], 'screenMarginVertical': [4, 151],
                            'sleepTimeoutMinutes': [0, 32], 'embeddedStyle': [True, 2]}.items():
            for value in values:
                self.assertCode('invalid_value', self.apply, {key: value})
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_credentials_and_unknown_updates_refused(self):
        for key in ('password', 'password_obf', 'wifi', 'futureOption', '../outside'):
            self.assertCode('unsupported_field', self.apply, {key: 'example-value'})
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_bad_json_and_existing_bad_field_types_fail_closed(self):
        for raw in (b'[]', b'{', b'{"a":1,"a":2}', b'{"a":NaN}', b'\xff',
                    b'{"deviceName":"\\ud800"}', b'{"embeddedStyle":true}',
                    b'{"lineHeightPercent":100.0}', b' ' * (config.MAX_BYTES + 1)):
            self.path.write_bytes(raw)
            with self.assertRaises(config.ConfigError):
                self.snapshot()
            self.assertEqual(self.path.read_bytes(), raw)
            self.assertFalse((self.root / 'backups').exists())

    def test_legacy_aliases_and_firmware_recovery_evidence_block(self):
        self.path.write_bytes(b'{"screenMargin":5}')
        self.assertCode('legacy_settings', self.snapshot)
        self.path.write_bytes(self.original)
        for suffix in ('.tmp', '.bak'):
            recovery = self.path.with_name(self.path.name + suffix)
            recovery.write_bytes(b'synthetic recovery')
            self.assertCode('recovery_pending', self.snapshot)
            self.assertEqual(recovery.read_bytes(), b'synthetic recovery')
            recovery.unlink()

    def test_stale_hash_and_same_bytes_replaced_inode_refused(self):
        token = self.snapshot()['token']
        self.path.write_bytes(self.original + b' ')
        self.assertCode('external_change', config.apply_changes, self.root, token, {'lineHeightPercent': 120})
        self.path.write_bytes(self.original)
        token = self.snapshot()['token']
        self.path.unlink()
        self.path.write_bytes(self.original)
        self.assertCode('external_change', config.apply_changes, self.root, token, {'lineHeightPercent': 120})
        self.assertFalse((self.root / 'backups').exists())

    def test_directory_swap_refused(self):
        token = self.snapshot()['token']
        old = self.root / '.old-crosspoint'
        self.path.parent.rename(old)
        self.path.parent.mkdir()
        self.path.write_bytes(self.original)
        self.assertCode('external_change', config.apply_changes, self.root, token, {'lineHeightPercent': 120})

    def test_symlink_file_directory_root_and_hardlink_refused(self):
        safe = self.root / 'synthetic-original'
        self.path.rename(safe)
        self.path.symlink_to(safe)
        with self.assertRaises(OSError):
            self.snapshot()
        self.path.unlink()
        os.link(safe, self.path)
        self.assertCode('unsafe_file', self.snapshot)
        self.path.unlink()
        safe.rename(self.path)
        old = self.root / 'original-dir'
        self.path.parent.rename(old)
        self.path.parent.symlink_to(old, target_is_directory=True)
        with self.assertRaises(OSError):
            self.snapshot()

    def test_arbitrary_folder_real_volume_and_marker_mismatch_refused(self):
        for root in ('/Volumes/EXAMPLE', tempfile.gettempdir(), str(self.root / '..' / self.root.name)):
            self.assertCode('synthetic_only', config.read_settings, root)
        marker = self.root / '.inkkit-preview.json'
        marker.write_text('{}')
        self.assertCode('unsafe_workspace', self.snapshot)

    def test_caller_controlled_temp_directory_is_ignored(self):
        with tempfile.TemporaryDirectory() as external:
            with patch.dict(os.environ, TMPDIR=external), patch.object(tempfile, 'tempdir', external):
                root = Path(config.create_demo())
                try:
                    self.assertEqual(root.parent, config._host_temp())
                    self.assertEqual(os.listdir(external), [])
                    self.assertTrue(config.read_settings(root)['synthetic'])
                finally:
                    shutil.rmtree(root)

    def test_injected_mount_identity_mismatch_refused(self):
        # A descriptor on a different device cannot become an approved workspace.
        original_stat = Path.stat
        temp = self.root.parent
        def different(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            if path == temp:
                values = list(result)
                values[2] += 1
                return os.stat_result(values)
            return result
        with patch.object(Path, 'stat', different):
            self.assertCode('unsafe_workspace', self.snapshot)

    def test_existing_lock_contention_refused(self):
        fd = os.open(self.root / '.inkkit-lock', os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertCode('busy', self.apply, {'lineHeightPercent': 120})
        finally:
            os.close(fd)

    def test_backup_failure_never_reaches_target(self):
        original = config._write_new
        def fail(fd, name, data):
            if name == 'before.bin':
                raise OSError('synthetic ENOSPC')
            return original(fd, name, data)
        with patch.object(config, '_write_new', fail):
            with self.assertRaises(OSError):
                self.apply({'lineHeightPercent': 120})
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(config.list_backups(self.root)[0]['state'], 'unavailable')
        self.apply({'lineHeightPercent': 130})
        self.assertEqual({b['state'] for b in config.list_backups(self.root)}, {'unavailable', 'written'})

    def test_failed_replace_retains_prepared_backup_and_original(self):
        original = os.replace
        def fail(src, dst, *args, **kwargs):
            if dst == config.SETTINGS_FILE:
                raise OSError('synthetic replace failure')
            return original(src, dst, *args, **kwargs)
        with patch.object(os, 'replace', fail):
            self.assertCode('apply_incomplete', self.apply, {'lineHeightPercent': 120})
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(config.list_backups(self.root)[0]['state'], 'prepared')
        self.assertFalse(any(p.name.startswith('.inkkit-write-') for p in self.path.parent.iterdir()))

    def test_changed_after_backup_never_overwritten(self):
        original = config._Workspace.backup
        changed = self.original + b'\n'
        def change(workspace, raw, updated):
            result = original(workspace, raw, updated)
            self.path.write_bytes(changed)
            return result
        with patch.object(config._Workspace, 'backup', change):
            self.assertCode('apply_incomplete', self.apply, {'lineHeightPercent': 120})
        self.assertEqual(self.path.read_bytes(), changed)

    def test_journal_failure_after_replace_can_be_recovered(self):
        original = config._atomic_record
        def fail(fd, record):
            if record['state'] == 'written':
                raise OSError('synthetic journal fsync failure')
            return original(fd, record)
        with patch.object(config, '_atomic_record', fail):
            self.assertCode('apply_incomplete', self.apply, {'lineHeightPercent': 120})
        backup = config.list_backups(self.root)[0]
        self.assertEqual(backup['state'], 'prepared')
        self.assertEqual(self.snapshot()['values']['lineHeightPercent'], 120)
        config.restore_backup(self.root, self.snapshot()['token'], backup['id'])
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_restore_refuses_external_edits_corruption_traversal_and_foreign_backup(self):
        result = self.apply({'lineHeightPercent': 120})
        self.path.write_bytes(self.path.read_bytes() + b' ')
        self.assertCode('external_change', config.restore_backup, self.root, self.snapshot()['token'], result['backup_id'])
        result = self.apply({'lineHeightPercent': 130})
        before = self.root / 'backups' / result['backup_id'] / 'before.bin'
        before.write_bytes(before.read_bytes() + b' ')
        self.assertCode('invalid_backup', config.restore_backup, self.root, self.snapshot()['token'], result['backup_id'])
        self.assertCode('invalid_backup', config.restore_backup, self.root, self.snapshot()['token'], '../outside')
        record = self.root / 'backups' / result['backup_id'] / 'record.json'
        doc = json.loads(record.read_bytes())
        doc['identity'][1] += 1
        record.write_text(json.dumps(doc))
        entries = {entry['id']: entry for entry in config.list_backups(self.root)}
        self.assertEqual(entries[result['backup_id']]['state'], 'unavailable')
        self.assertCode('invalid_backup', config.restore_backup, self.root, self.snapshot()['token'], result['backup_id'])

    def test_backup_symlink_never_followed(self):
        result = self.apply({'lineHeightPercent': 120})
        before = self.root / 'backups' / result['backup_id'] / 'before.bin'
        before.unlink()
        before.symlink_to(self.path)
        with self.assertRaises(OSError):
            config.restore_backup(self.root, self.snapshot()['token'], result['backup_id'])
        self.assertEqual(self.snapshot()['values']['lineHeightPercent'], 120)

    def test_fsync_failures_before_and_after_replace_retain_recovery(self):
        original = os.fsync
        config_inode = self.path.parent.stat().st_ino
        def fail(fd):
            if os.fstat(fd).st_ino == config_inode:
                raise OSError('synthetic directory sync failure')
            return original(fd)
        with patch.object(os, 'fsync', fail):
            self.assertCode('apply_incomplete', self.apply, {'lineHeightPercent': 120})
        backup = config.list_backups(self.root)[0]
        self.assertEqual(backup['state'], 'prepared')
        config.restore_backup(self.root, self.snapshot()['token'], backup['id'])
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_injected_verification_failure_keeps_backup_for_recovery(self):
        original = config._read_at
        armed = [False]
        original_replace = os.replace
        def replaced(src, dst, *args, **kwargs):
            result = original_replace(src, dst, *args, **kwargs)
            if dst == config.SETTINGS_FILE:
                armed[0] = True
            return result
        def changed(fd, name):
            raw, info = original(fd, name)
            if armed[0] and name == config.SETTINGS_FILE:
                return raw + b' ', info
            return raw, info
        with patch.object(os, 'replace', replaced), patch.object(config, '_read_at', changed):
            self.assertCode('apply_incomplete', self.apply, {'lineHeightPercent': 120})
        backup = config.list_backups(self.root)[0]
        config.restore_backup(self.root, self.snapshot()['token'], backup['id'])
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_failed_restore_replace_keeps_bytes_and_allows_retry(self):
        result = self.apply({'lineHeightPercent': 120})
        updated = self.path.read_bytes()
        original = os.replace
        def fail(src, dst, *args, **kwargs):
            if dst == config.SETTINGS_FILE:
                raise OSError('synthetic failure')
            return original(src, dst, *args, **kwargs)
        with patch.object(os, 'replace', fail):
            self.assertCode('restore_incomplete', config.restore_backup, self.root, result['snapshot']['token'], result['backup_id'])
        self.assertEqual(self.path.read_bytes(), updated)
        self.assertEqual(config.list_backups(self.root)[0]['state'], 'restoring')
        config.restore_backup(self.root, self.snapshot()['token'], result['backup_id'])
        self.assertEqual(self.path.read_bytes(), self.original)


if __name__ == '__main__':
    unittest.main()
