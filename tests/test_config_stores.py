"""Synthetic store transactions and source-contract regressions. No real cards."""
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import inkkit_codec as codec
import inkkit_config as config
import inkkit_helper as helper
import inkkit_schema as schema


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(config.create_demo('X4 Pro'))

    def tearDown(self):
        shutil.rmtree(self.root)

    def path(self, store):
        return self.root / '.crosspoint' / schema.STORES[store][0]

    def seed(self, store, doc):
        self.path(store).write_bytes(config._encoded(doc, store))

    def read(self, store):
        return config.read_settings(self.root, store)

    def apply(self, store, changes, consent=False):
        return config.apply_changes(self.root, self.read(store)['token'], changes, store, allow_plaintext=consent)

    def test_every_store_create_apply_exact_restore_or_delete(self):
        patches = {
            'settings': {'screenInverted': 1},
            'wifi': {'credentials.0.enabled': 1, 'credentials.0.ssid': 'Example network'},
            'opds': {'servers.0.enabled': 1, 'servers.0.name': 'Example catalog', 'servers.0.url': 'https://example.org/opds'},
            'koreader': {'username': 'example-reader', 'sendMetadata': True},
            'ttf': {'profiles.0.enabled': 1, 'profiles.0.family': 'Example Serif', 'profiles.0.stemDarkening': True},
            'dictionary': {'path': '/dict/example'},
        }
        for store, changes in patches.items():
            with self.subTest(store=store):
                original = self.path(store).read_bytes() if self.path(store).exists() else None
                snapshot = self.read(store)
                before = set(self.root.rglob('*'))
                self.assertTrue(config.preview_changes(self.root, snapshot['token'], changes, store))
                self.assertEqual(set(self.root.rglob('*')), before)
                result = self.apply(store, changes)
                self.assertTrue(result['changed'])
                self.assertTrue(config.preview_restore(self.root, result['snapshot']['token'], result['backup_id'], store))
                config.restore_backup(self.root, result['snapshot']['token'], result['backup_id'], store)
                if original is None:
                    self.assertFalse(self.path(store).exists())
                else:
                    self.assertEqual(self.path(store).read_bytes(), original)

    def test_empty_dictionary_preserves_full_width_file_identity_without_writes(self):
        self.path('dictionary').write_bytes(b'')
        read_at = config._read_at

        def read_with_full_width_inode(directory, name, **kwargs):
            raw, info = read_at(directory, name, **kwargs)
            if name == 'dictionary.bin':
                info = SimpleNamespace(st_dev=info.st_dev, st_ino=2 ** 64 - 1,
                                       st_mtime_ns=info.st_mtime_ns, st_size=info.st_size)
            return raw, info

        with patch.object(config, '_read_at', side_effect=read_with_full_width_inode):
            snapshot = helper.dispatch(dict(protocol=2, action='config.read', root=str(self.root), store='dictionary'))
            self.assertEqual(snapshot['values']['path'], '')
            self.assertEqual(snapshot['token']['file'][1], 2 ** 64 - 1)
            self.assertEqual(snapshot['token']['size'], 0)
            self.assertEqual(snapshot['token']['sha256'], config.digest(b''))
            self.assertFalse(self.apply('dictionary', {'path': ''})['changed'])
            self.assertEqual(config.list_backups(self.root, 'dictionary'), [])
        self.assertEqual(self.path('dictionary').read_bytes(), b'')

    def test_firmware_fallbacks_are_displayed_without_noop_rewrites(self):
        cases = [
            ({'pageTurnGesture': 3}, 'previousPageGesture', 3),
            ({'readerDarkMode': 1}, 'screenInverted', 1),
            ({'statusBarClock': 1}, 'hideClock', 0),
            ({'uiTheme': 5}, 'fileBrowserDisplay', 1),
            ({'fileBrowserPreview': 1}, 'fileBrowserDisplay', 1),
            ({'hideBatteryPercentage': 2}, 'displayStatusBar.2', 2),
        ]
        for doc, key, value in cases:
            with self.subTest(key=key):
                self.seed('settings', doc)
                original = self.path('settings').read_bytes()
                before = self.read('settings')
                self.assertEqual(before['values'][key], value)
                self.assertEqual(config.preview_changes(self.root, before['token'], {key: value}), [])
                result = self.apply('settings', {key: value})
                self.assertFalse(result['changed'])
                self.assertEqual(self.path('settings').read_bytes(), original)
                self.assertEqual(config.list_backups(self.root), [])

    def test_opaque_passwords_unknown_fields_and_cfg_version_are_preserved(self):
        examples = {
            'wifi': ({'credentials': [{'ssid': 'Example', 'password_obf': 'example-opaque', 'future': 7}], 'lastConnectedSsid': 'Example', 'futureRoot': [1]}, {'credentials.0.ssid': 'Example renamed'}),
            'opds': ({'servers': [{'name': 'Example', 'url': 'https://example.org', 'password_obf': 'example-opaque', 'future': 7}]}, {'servers.0.name': 'Example renamed'}),
            'koreader': ({'username': 'example', 'password_obf': 'example-opaque', 'future': 7}, {'sendMetadata': True}),
            'ttf': ({'profiles': [{'family': 'Example', 'hinting': 1, 'interpreter': 2, 'future': 7}], 'future': 7}, {'profiles.0.weight': 3}),
        }
        for store, (doc, changes) in examples.items():
            with self.subTest(store=store):
                self.seed(store, doc)
                before = self.path(store).read_bytes()
                result = self.apply(store, changes)
                updated = json.loads(self.path(store).read_bytes())
                if store == 'koreader':
                    self.assertNotIn('serverUrl', updated)
                    self.assertNotIn('cfgVersion', updated)
                    self.assertEqual(updated['password_obf'], 'example-opaque')
                elif store in ('wifi', 'opds'):
                    entry = updated['credentials' if store == 'wifi' else 'servers'][0]
                    self.assertEqual(entry['password_obf'], 'example-opaque')
                    self.assertEqual(entry['future'], 7)
                else:
                    self.assertEqual(updated['profiles'][0]['future'], 7)
                config.restore_backup(self.root, result['snapshot']['token'], result['backup_id'], store)
                self.assertEqual(self.path(store).read_bytes(), before)
        self.assertEqual(self.read('wifi')['values']['credentials.0.password'], '')

    def test_plaintext_requires_consent_each_apply_and_restore_and_never_leaks(self):
        self.seed('wifi', {'credentials': [{'ssid': 'Example', 'password_obf': 'example-opaque'}]})
        request = dict(protocol=2, root=str(self.root), store='wifi', expected=self.read('wifi')['token'], changes={'credentials.0.password': 'example-new-password'})
        planned = helper.dispatch(dict(request, action='config.preview'))
        self.assertTrue(planned['requires_plaintext'])
        self.assertNotIn('example-new-password', json.dumps(planned))
        self.assertNotIn('example-opaque', json.dumps(self.read('wifi')))
        original = self.path('wifi').read_bytes()
        for consent in (False, 1, 'yes'):
            with self.assertRaises(config.ConfigError):
                self.apply('wifi', request['changes'], consent)
            self.assertEqual(self.path('wifi').read_bytes(), original)
        first = self.apply('wifi', request['changes'], True)
        self.assertNotIn('example-new-password', json.dumps(first))
        saved = json.loads(self.path('wifi').read_bytes())['credentials'][0]
        self.assertNotIn('password_obf', saved)
        self.assertEqual(saved['password'], 'example-new-password')
        with self.assertRaises(config.ConfigError):
            self.apply('wifi', {'credentials.0.ssid': 'Example renamed'})
        clear = dict(request, expected=first['snapshot']['token'], changes={'credentials.0.clearPassword': 1}, action='config.preview')
        self.assertFalse(helper.dispatch(clear)['requires_plaintext'])
        second = self.apply('wifi', {'credentials.0.clearPassword': 1})
        restore = dict(protocol=2, action='config.restore_preview', root=str(self.root), store='wifi', expected=second['snapshot']['token'], backup_id=second['backup_id'])
        self.assertTrue(helper.dispatch(restore)['requires_plaintext'])
        with self.assertRaises(config.ConfigError):
            config.restore_backup(self.root, second['snapshot']['token'], second['backup_id'], 'wifi')
        restore.update(action='config.restore', allow_plaintext=True)
        self.assertTrue(helper.dispatch(restore)['snapshot']['has_plaintext'])
        config.restore_backup(self.root, self.read('wifi')['token'], first['backup_id'], 'wifi')
        self.assertEqual(self.path('wifi').read_bytes(), original)

    def test_connection_remove_shift_and_last_connected_marker(self):
        self.seed('wifi', {'credentials': [{'ssid': 'Example A', 'password_obf': 'example-A'}, {'ssid': 'Example B', 'password_obf': 'example-B'}], 'lastConnectedSsid': 'Example A'})
        result = self.apply('wifi', {'credentials.0.enabled': 0})
        saved = json.loads(self.path('wifi').read_bytes())
        self.assertEqual(saved['credentials'], [{'ssid': 'Example B', 'password_obf': 'example-B'}])
        self.assertEqual(saved['lastConnectedSsid'], '')
        self.assertEqual(result['snapshot']['values']['credentials.1.enabled'], 0)
        self.assertNotIn('example-B', json.dumps(result))

    def test_limits_duplicates_invalid_urls_and_utf8_bytes(self):
        for store, array, count in (('wifi', 'credentials', 8), ('opds', 'servers', 8), ('ttf', 'profiles', 24)):
            self.seed(store, {array: [{}] * (count + 1)})
            with self.assertRaises(config.ConfigError):
                self.read(store)
            self.path(store).unlink()
        invalid = [
            ('wifi', {'credentials.0.enabled': 1, 'credentials.0.ssid': '閱' * 11}),
            ('wifi', {'credentials.0.enabled': 1, 'credentials.0.ssid': 'Example', 'credentials.0.password': 'x' * 65}),
            ('wifi', {'credentials.0.enabled': 1, 'credentials.0.ssid': 'Example', 'credentials.1.enabled': 1, 'credentials.1.ssid': 'Example'}),
            ('opds', {'servers.0.enabled': 1, 'servers.0.name': 'Example', 'servers.0.url': 'file:///etc/passwd'}),
            ('opds', {'servers.0.enabled': 1, 'servers.0.name': 'Example', 'servers.0.url': 'https://' + 'example:example-password@example.org'}),
            ('koreader', {'serverUrl': 'https://[bad'}),
            ('ttf', {'profiles.0.enabled': 1, 'profiles.0.family': 'Example', 'profiles.0.interpreter': 1}),
            ('ttf', {'profiles.0.enabled': 1, 'profiles.0.family': '../Example'}),
            ('dictionary', {'path': '/dict/../example'}),
        ]
        for store, changes in invalid:
            with self.subTest(store=store, changes=list(changes)):
                with self.assertRaises(config.ConfigError) as error:
                    self.apply(store, changes, True)
                self.assertNotIn('example-password', str(error.exception))
                self.assertFalse(self.path(store).exists())

    def test_strict_saved_types_nested_layouts_and_missing_default_noop(self):
        invalid = [('settings', {'orientation': True}), ('settings', {'readerStatusBars': []}),
                   ('settings', {'quickActionSlots': [True, 0, 0, 0, 0]}), ('settings', {'frontButtonLayout': 2}), ('settings', {'fontSize': 2}),
                   ('settings', {'sideButtonLayout': 1, 'sideButtonUpShort': 2}),
                   ('settings', {'sideButtonLongPress': 1, 'sideButtonUpLong': 66}),
                   ('koreader', {'sendMetadata': 1}), ('wifi', {'credentials': [{'ssid': 'Example', 'password_obf': 4}]}),
                   ('ttf', {'profiles': [{'family': 'Example', 'stemDarkening': 1}]}), ('opds', {'servers': [{'name': None}]})]
        original = self.path('settings').read_bytes()
        for store, doc in invalid:
            with self.subTest(store=store, doc=doc):
                self.seed(store, doc)
                before = self.path(store).read_bytes()
                with self.assertRaises(config.ConfigError):
                    self.read(store)
                self.assertEqual(self.path(store).read_bytes(), before)
        self.path('settings').write_bytes(original)
        for store in schema.STORES:
            if store != 'settings':
                self.path(store).unlink(missing_ok=True)
                self.assertFalse(self.apply(store, {})['changed'])
                self.assertFalse(self.path(store).exists())

    def test_store_token_backup_isolation_and_failed_new_file_write(self):
        wifi = self.read('wifi')
        with self.assertRaises(config.ConfigError):
            config.preview_changes(self.root, wifi['token'], {'username': 'example'}, 'koreader')
        replace = config.os.replace
        def fail_target(source, destination, **kwargs):
            if destination == 'wifi.json':
                raise OSError('synthetic failure')
            return replace(source, destination, **kwargs)
        with patch.object(config.os, 'replace', side_effect=fail_target):
            with self.assertRaises(config.ConfigError):
                self.apply('wifi', {'credentials.0.enabled': 1, 'credentials.0.ssid': 'Example'})
        self.assertFalse(self.path('wifi').exists())
        backup = config.list_backups(self.root, 'wifi')[0]
        self.assertEqual(backup['state'], 'prepared')
        self.assertFalse(config.restore_backup(self.root, self.read('wifi')['token'], backup['id'], 'wifi')['changed'])
        with self.assertRaises(FileNotFoundError):
            config.preview_restore(self.root, self.read('koreader')['token'], backup['id'], 'koreader')


class SchemaTests(unittest.TestCase):
    def test_catalog_unique_keys_all_models_and_raw_id_contracts(self):
        for model in schema.MODELS:
            for store in schema.STORES:
                fields = schema.store_fields(store, model, {})
                self.assertEqual(len(fields), len({f['key'] for f in fields}))
            fields = {f['key']: f for f in schema.main_fields(model, {})}
            self.assertEqual(len(fields), 148)
            self.assertEqual(fields['orientation']['choices'][2][0], 3)
            self.assertEqual(dict(fields['uiTheme']['choices'])[5], 'Minimal')
            self.assertEqual(fields['sdFontSizeRange']['choices'][-1][0], 4)
            self.assertEqual(fields['librarySortMethod']['choices'][4][1], 'Last opened')
            self.assertIn(33, [v for v, _ in fields['quickActionSlots.0']['choices']])
            self.assertNotIn(27, [v for v, _ in fields['quickActionSlots.0']['choices']])

    def test_every_editable_main_field_can_be_patched_and_others_stay_opaque(self):
        # Exercise each control through the real patch path, using paired values
        # where firmware imposes mapping/schedule constraints.
        for model in schema.MODELS:
            doc = schema.effective_settings({})
            doc.update(uiScale=1 if model == 'X4 Pro' else 0, tiltPageTurnDirectionSchema=2, opaque={'future': [7]})
            fields = schema.main_fields(model, doc)
            for field in fields:
                if field.get('readonly'):
                    continue
                key, kind = field['key'], field['kind']
                current = codec.values(doc, 'settings', fields)[key]
                choices = [v for v, _ in field.get('choices', []) if v != current]
                value = choices[0] if kind == 'enum' and choices else (not current) if kind == 'bool' else 'Example' if kind == 'text' else (1 - current) if kind == 'toggle' else field['minimum'] if current != field['minimum'] else (22 if key == 'fontSize' else field['maximum'])
                if kind == 'time': value = 720
                if kind == 'text' and key.endswith('Folder'): value = '/example'
                changes = {key: value}
                if key == 'frontlightScheduleEnabled': changes.update(frontlightScheduleStart=600, frontlightScheduleEnd=1200)
                if key in [prefix + suffix for prefix in ('frontButton', 'readerFrontButton') for suffix in ('Back', 'Confirm', 'Left', 'Right')]:
                    other = next(f['key'] for f in fields if f['key'] in [('readerFrontButton' if key.startswith('reader') else 'frontButton') + suffix for suffix in ('Back', 'Confirm', 'Left', 'Right')] and f['key'] != key and doc[f['key']] == value)
                    changes[other] = current
                with self.subTest(model=model, key=key):
                    result, _ = codec.patch_document(doc, 'settings', fields, changes)
                    self.assertEqual(schema.path_get(result, key), value)
                    self.assertEqual(result['opaque'], doc['opaque'])

    def test_every_offered_enum_value_is_writable_with_its_storage_id(self):
        for model in schema.MODELS:
            doc = schema.effective_settings({})
            doc.update(uiScale=1 if model == 'X4 Pro' else 0, tiltPageTurnDirectionSchema=2)
            fields = schema.main_fields(model, doc)
            for field in fields:
                key = field['key']
                if field['kind'] != 'enum' or field.get('readonly'):
                    continue
                for value, _ in field['choices']:
                    changes = {key: value}
                    if key in [prefix + suffix for prefix in ('frontButton', 'readerFrontButton') for suffix in ('Back', 'Confirm', 'Left', 'Right')]:
                        prefix = 'readerFrontButton' if key.startswith('reader') else 'frontButton'
                        other = next(prefix + suffix for suffix in ('Back', 'Confirm', 'Left', 'Right') if doc[prefix + suffix] == value)
                        changes[other] = doc[key]
                        changes[key] = value
                    with self.subTest(model=model, key=key, value=value):
                        result, _ = codec.patch_document(doc, 'settings', fields, changes)
                        self.assertEqual(schema.path_get(result, key), value)

    def test_firmware_conditional_defaults_are_effective_not_written(self):
        examples = [
            ({'pageTurnGesture': 3}, 'previousPageGesture', 3),
            ({'readerDarkMode': 1}, 'screenInverted', 1),
            ({'statusBarClock': 1}, 'hideClock', 0),
            ({'uiTheme': 5}, 'fileBrowserDisplay', 1),
            ({'fileBrowserPreview': 1}, 'fileBrowserDisplay', 1),
            ({'hideBatteryPercentage': 2}, 'displayStatusBar', [0, 0, 2]),
            ({'statusBarClock': 2}, 'displayStatusBar', [0, 1, 2]),
        ]
        for doc, key, expected in examples:
            with self.subTest(key=key, doc=doc):
                self.assertEqual(schema.effective_settings(doc)[key], expected)
                fields = schema.main_fields('X3', doc)
                result, _ = codec.patch_document(doc, 'settings', fields, {})
                self.assertEqual(result, doc)
        explicit = {'pageTurnGesture': 3, 'previousPageGesture': 1, 'screenInverted': 0,
                    'readerDarkMode': 1, 'hideClock': 2, 'statusBarClock': 1,
                    'uiTheme': 5, 'fileBrowserDisplay': 0, 'displayStatusBar': [2, 0, 0]}
        values = schema.effective_settings(explicit)
        for key in ('previousPageGesture', 'screenInverted', 'hideClock', 'fileBrowserDisplay', 'displayStatusBar'):
            self.assertEqual(values[key], explicit[key])

    def test_configuration_documentation_matches_schema(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('configuration_docs', Path(__file__).resolve().parents[1] / 'scripts/check_configuration_docs.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.check(), [])
        self.assertEqual(set(module.SOURCE_LINES), {f['key'].split('.')[0] for f in schema.main_fields('X3', {})})
        self.assertTrue(all(path.startswith('src/') and type(line) is int and line > 0
                            for path, line in module.SOURCE_LINES.values()))
        represented = {f['key'].split('.')[0] for f in schema.main_fields('X3', {})}
        catalog = {f['key'] for f in schema.BASE_FIELDS} | set(schema.MEMBER_DEFAULTS)
        legacy = {f['key'] for f in schema.BASE_FIELDS if f['group'] == 'legacy'}
        self.assertEqual(catalog - represented, legacy | {'clockDateHasBeenSynced', 'dictionaryFontPointSize'})

    def test_backend_catalogue_and_every_store_report_model_capabilities(self):
        catalog = helper.dispatch(dict(protocol=2, action='profiles.describe'))
        self.assertEqual(catalog['unknown_policy'], 'settings_blocked_use_cli_backup_diagnostics')
        self.assertEqual(len(catalog['profiles']), 1)
        profile = catalog['profiles'][0]
        self.assertEqual(profile['firmware'], schema.FIRMWARE_VERSION)
        self.assertEqual(profile['upstream_commit'], schema.UPSTREAM_COMMIT)
        self.assertEqual(profile['id'], config.PROFILE)
        self.assertEqual({m['id'] for m in profile['models']}, set(schema.MODELS))
        root = config.create_demo()
        try:
            for model in profile['models']:
                self.assertEqual(model['capabilities'], sorted(schema.MODELS[model['id']]))
                for store in schema.STORES:
                    snapshot = config.read_settings(root, store, model=model['id'])
                    self.assertEqual(snapshot['capabilities'], model['capabilities'])
        finally:
            shutil.rmtree(root)

    def test_unavailable_frontlight_fields_are_locked_and_preserved(self):
        doc = {'frontlightBrightness': 65, 'frontlightOn': 1, 'frontlightWarmth': 45}
        for model in schema.MODELS:
            fields = schema.main_fields(model, doc)
            frontlight = [f for f in fields if f['group'] == 'frontlight']
            self.assertTrue(frontlight)
            self.assertEqual(all(bool(f.get('readonly')) for f in frontlight), model != 'X4 Pro')
            if model != 'X4 Pro':
                for field in frontlight:
                    current = codec.values(doc, 'settings', fields)[field['key']]
                    with self.assertRaisesRegex(ValueError, 'capability'):
                        codec.patch_document(doc, 'settings', fields, {field['key']: 1 if current == 0 else 0})
            updated, _ = codec.patch_document(doc, 'settings', fields, {'showHiddenFiles': 1})
            for key, value in doc.items():
                self.assertEqual(updated[key], value)

    def test_capabilities_and_interdependent_controls_fail_closed(self):
        for model in schema.MODELS:
            fields = schema.main_fields(model, {})
            mapping = {f['key']: f for f in fields}
            self.assertEqual(bool(mapping['frontlightBrightness'].get('readonly')), model != 'X4 Pro')
            self.assertEqual(bool(mapping['tiltPageTurn'].get('readonly')), model not in ('X3', 'X4 Classic'))
            self.assertEqual(bool(mapping['clockHasBeenSynced'].get('readonly')), model == 'X4')
            if model == 'X4':
                with self.assertRaises(ValueError):
                    codec.patch_document({}, 'settings', fields, {'clockHasBeenSynced': 1})
        fields = schema.main_fields('X4 Pro', {})
        for changes in ({'frontlightScheduleEnabled': 1}, {'twoFingerSwipeUp': 5, 'twoFingerSwipeDown': 5},
                        {'shortPwrBtn': 27, 'longPwrBtn': 27}):
            with self.assertRaises(ValueError):
                codec.patch_document({}, 'settings', fields, changes)
        result, _ = codec.patch_document({}, 'settings', fields, {'quickActionsTrigger': 6})
        self.assertEqual(result['homeButtonTapAction'], 27)
        result, _ = codec.patch_document(result, 'settings', fields, {'quickActionsTrigger': 1})
        self.assertEqual(result['homeButtonTapAction'], 23)
        self.assertEqual(result['shortPwrBtn'], 27)


if __name__ == '__main__':
    unittest.main()
