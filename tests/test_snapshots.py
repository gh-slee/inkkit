"""Complete configuration snapshots on invented temporary data only."""
import json
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

import inkkit_config as config
import inkkit_helper as helper
import inkkit_snapshots as snapshots


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(config.create_demo())
        self.paths = {store: self.root / '.crosspoint' / item[0] for store, item in config.schema.STORES.items()}

    def tearDown(self):
        shutil.rmtree(self.root)

    def data(self):
        return {store: path.read_bytes() if path.exists() else None for store, path in self.paths.items()}

    def change(self, store, changes):
        before = config.read_settings(self.root, store)
        return config.apply_changes(self.root, before['token'], changes, store, allow_plaintext=True)

    def restore(self, identifier, consent=False):
        plan = snapshots.preview_restore(self.root, identifier)
        return snapshots.restore_snapshot(self.root, identifier, plan['expected'], plan['backup_sha256'], consent)

    def test_older_complete_backup_restores_exact_files_and_absent_empty_distinction(self):
        self.paths['dictionary'].write_bytes(b'')
        self.paths['settings'].write_bytes(b'{ "deviceName":"Example reader", "unknown":{"value":42} }\n')
        original = self.data()
        first = snapshots.create_snapshot(self.root)['backup_id']
        for store, changes in (
                ('settings', {'showHiddenFiles': 1}),
                ('wifi', {'credentials.0.enabled': 1, 'credentials.0.ssid': 'Example network'}),
                ('opds', {'servers.0.enabled': 1, 'servers.0.name': 'Example catalog', 'servers.0.url': 'https://example.org'}),
                ('koreader', {'username': 'example'}),
                ('ttf', {'profiles.0.enabled': 1, 'profiles.0.family': 'Example Serif'}),
                ('dictionary', {'path': '/dictionary/example/data'})):
            self.change(store, changes)
        snapshots.create_snapshot(self.root)
        self.change('settings', {'deviceName': 'Example changed'})
        current = self.data()
        result = self.restore(first)
        self.assertTrue(result['changed'])
        self.assertEqual(self.data(), original)
        self.assertIsNone(original['wifi'])
        self.assertEqual(original['dictionary'], b'')
        # The automatically captured pre-restore snapshot restores the later state.
        self.restore(result['backup_id'])
        self.assertEqual(self.data(), current)
        snapshots.ensure_no_pending(self.root)

    def test_sorted_catalogue_metadata_and_review_do_not_expose_passwords(self):
        self.paths['wifi'].write_bytes(b'{"credentials":[{"ssid":"Example","password":"example-private-pass"}]}')
        with patch.object(snapshots.time, 'time', return_value=1000):
            first = snapshots.create_snapshot(self.root)['backup_id']
        with patch.object(snapshots.time, 'time', return_value=2000):
            last = snapshots.create_snapshot(self.root)['backup_id']
        entries = snapshots.backup_catalogue(self.root)
        self.assertEqual([e['id'] for e in entries], [last, first])
        public = json.dumps(entries) + json.dumps(snapshots.preview_restore(self.root, first))
        self.assertNotIn('example-private-pass', public)
        self.assertNotIn(str(self.root), public)
        self.change('wifi', {'credentials.0.password': 'example-new-pass'})
        plan = snapshots.preview_restore(self.root, first)
        self.assertTrue(plan['requires_plaintext'])
        with self.assertRaises(config.ConfigError):
            snapshots.restore_snapshot(self.root, first, plan['expected'], plan['backup_sha256'])
        self.assertNotIn('example-new-pass', json.dumps(plan))
        self.restore(first, True)

    def test_stale_current_tokens_or_replaced_backup_require_fresh_review(self):
        identifier = snapshots.create_snapshot(self.root)['backup_id']
        self.change('settings', {'showHiddenFiles': 1})
        plan = snapshots.preview_restore(self.root, identifier)
        self.change('dictionary', {'path': '/dictionary/example'})
        current = self.data()
        with self.assertRaises(config.ConfigError) as error:
            snapshots.restore_snapshot(self.root, identifier, plan['expected'], plan['backup_sha256'])
        self.assertEqual(error.exception.code, 'external_change')
        self.assertEqual(self.data(), current)
        plan = snapshots.preview_restore(self.root, identifier)
        manifest = snapshots._location(self.root) / identifier / 'manifest.json'
        value = json.loads(manifest.read_bytes())
        value['created'] += 1
        manifest.write_text(json.dumps(value))
        with self.assertRaises(config.ConfigError):
            snapshots.restore_snapshot(self.root, identifier, plan['expected'], plan['backup_sha256'])
        self.assertEqual(self.data(), current)

    def test_corrupt_backup_symlinks_and_wrong_models_are_rejected(self):
        identifier = snapshots.create_snapshot(self.root)['backup_id']
        directory = snapshots._location(self.root) / identifier
        data = directory / 'settings.bin'
        original = data.read_bytes()
        data.write_bytes(b'{}')
        with self.assertRaises(config.ConfigError):
            snapshots.preview_restore(self.root, identifier)
        data.write_bytes(original)
        safe = directory / 'safe.bin'
        data.rename(safe)
        data.symlink_to(safe)
        with self.assertRaises((config.ConfigError, OSError)):
            snapshots.preview_restore(self.root, identifier)
        data.unlink()
        safe.rename(data)
        manifest = directory / 'manifest.json'
        record = json.loads(manifest.read_bytes())
        record['model'] = 'X4 Pro'
        manifest.write_text(json.dumps(record))
        with self.assertRaises(config.ConfigError) as error:
            snapshots.preview_restore(self.root, identifier)
        self.assertEqual(error.exception.code, 'snapshot_profile')

    def test_interrupted_restore_protects_recovery_backups_and_can_be_retried(self):
        original = self.data()
        target = snapshots.create_snapshot(self.root)['backup_id']
        self.change('settings', {'showHiddenFiles': 1})
        self.change('wifi', {'credentials.0.enabled': 1, 'credentials.0.ssid': 'Example network'})
        replace = snapshots._replace

        def fail(workspace, raw, expected):
            if workspace.store == 'wifi':
                raise OSError('synthetic write failure')
            return replace(workspace, raw, expected)

        with patch.object(snapshots, '_replace', side_effect=fail), self.assertRaises(config.ConfigError) as error:
            self.restore(target)
        self.assertEqual(error.exception.code, 'snapshot_interrupted')
        with self.assertRaises(config.ConfigError):
            snapshots.ensure_no_pending(self.root)
        entries = snapshots.list_snapshots(self.root)
        protected = [e for e in entries if not e['can_delete']]
        self.assertEqual(len(protected), 2)
        for entry in protected:
            with self.assertRaises(config.ConfigError):
                snapshots.delete_snapshot(entry['id'], entry['checksum'], self.root)
        self.restore(target)
        self.assertEqual(self.data(), original)
        snapshots.ensure_no_pending(self.root)
        self.assertTrue(all(e['can_delete'] for e in snapshots.list_snapshots(self.root)))

    def test_all_current_files_are_rechecked_after_pre_restore_capture(self):
        target = snapshots.create_snapshot(self.root)['backup_id']
        self.change('settings', {'showHiddenFiles': 1})
        capture = snapshots._capture
        before_main = self.paths['settings'].read_bytes()

        def capture_then_external_change(*args):
            result = capture(*args)
            self.paths['dictionary'].write_bytes(b'/dictionary/external')
            return result

        with patch.object(snapshots, '_capture', side_effect=capture_then_external_change), self.assertRaises(config.ConfigError):
            self.restore(target)
        self.assertEqual(self.paths['settings'].read_bytes(), before_main)
        self.assertEqual(self.paths['dictionary'].read_bytes(), b'/dictionary/external')

    def test_completed_bytes_with_pending_journal_can_finish_reviewed_recovery(self):
        target = snapshots.create_snapshot(self.root)['backup_id']
        self.change('settings', {'showHiddenFiles': 1})
        self.restore(target)
        with config._Workspace(self.root) as workspace:
            active = snapshots._operation_directory(workspace) / 'record.json'
            record = json.loads(active.read_bytes())
            # Simulate loss of power between the two completion journal writes:
            # all files and the backup-side record are complete, active is not.
            record['state'] = 'writing'
            active.write_text(json.dumps(record))
        with self.assertRaises(config.ConfigError):
            snapshots.ensure_no_pending(self.root)
        plan = snapshots.preview_restore(self.root, target)
        self.assertEqual([row['key'] for row in plan['differences']], ['__recovery__'])
        original = self.data()
        with patch.object(snapshots, '_replace', side_effect=AssertionError('No file needs rewriting')):
            result = self.restore(target)
        self.assertTrue(result['changed'])
        self.assertEqual(self.data(), original)
        snapshots.ensure_no_pending(self.root)

    def test_delete_only_reviewed_backup_and_refuse_unexpected_files(self):
        identifier = snapshots.create_snapshot(self.root)['backup_id']
        entry = snapshots.list_snapshots(self.root)[0]
        directory = snapshots._location(self.root) / identifier
        with self.assertRaises(config.ConfigError):
            snapshots.delete_snapshot('../outside', entry['checksum'], self.root)
        with self.assertRaises(config.ConfigError):
            snapshots.delete_snapshot(identifier, 'stale', self.root)
        extra = directory / 'unexpected'
        extra.write_bytes(b'synthetic')
        before = set(os.listdir(directory))
        with self.assertRaises(config.ConfigError):
            snapshots.delete_snapshot(identifier, entry['checksum'], self.root)
        self.assertEqual(set(os.listdir(directory)), before)
        extra.unlink()
        snapshots.delete_snapshot(identifier, entry['checksum'], self.root)
        self.assertFalse(directory.exists())
        self.assertEqual(snapshots.list_snapshots(self.root), [])

    def test_global_list_and_delete_work_without_a_selected_card(self):
        location = self.root / 'SyntheticGlobalBackups'
        location.mkdir(mode=0o700)
        with patch.object(snapshots, '_location', return_value=location):
            identifier = snapshots.create_snapshot(self.root)['backup_id']
            entries = snapshots.list_snapshots()
            self.assertEqual(entries[0]['id'], identifier)
            self.assertFalse(entries[0]['can_restore'])
            snapshots.delete_snapshot(identifier, entries[0]['checksum'])
            self.assertEqual(snapshots.list_snapshots(), [])

    def test_native_apply_creates_complete_backup_and_legacy_backups_remain_accessible(self):
        before = config.read_settings(self.root)
        helper.dispatch(dict(protocol=2, action='config.apply', root=str(self.root), expected=before['token'], changes={'showHiddenFiles': 1}))
        entries = helper.dispatch(dict(protocol=2, action='snapshots.list', root=str(self.root)))
        complete = [e for e in entries if e['kind'] == 'complete']
        legacy = [e for e in entries if e['kind'] == 'legacy']
        self.assertEqual(len(complete), 1)
        self.assertEqual(complete[0]['reason'], 'before_apply')
        self.assertEqual(len(legacy), 1)
        self.assertEqual(legacy[0]['scope'], 'Reader settings')
        entry = legacy[0]
        snapshots.delete_legacy(str(self.root), 'settings', entry['id'], entry['checksum'])
        self.assertEqual(config.list_backups(self.root), [])
        self.assertEqual(len(snapshots.list_snapshots(self.root)), 1)


if __name__ == '__main__':
    unittest.main()
