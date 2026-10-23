"""Pure configuration transforms. No filesystem, network or device operations."""
from copy import deepcopy
from urllib.parse import urlsplit

import inkkit_schema as schema


def validate(field, value):
    kind = field['kind']
    if kind in ('text', 'secret'):
        if type(value) is not str:
            raise ValueError('A text setting has an invalid type.')
        try:
            length = len(value.encode('utf-8'))
        except UnicodeError:
            raise ValueError('Text must be valid UTF-8.') from None
        if length > field.get('maximum', 2048) or '\0' in value:
            raise ValueError('Text exceeds its UTF-8 byte limit or contains a null character.')
        if kind != 'secret' and any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('Text settings must not contain control characters.')
        if field['key'] == 'deviceName' and length == 1:
            raise ValueError('Device name must be empty or 2–20 UTF-8 bytes.')
        if field['key'] in ('sdFontFamilyName', 'dictionaryFont') and ('/' in value or '\\' in value or value in ('.', '..')):
            raise ValueError('Font selection requires a family name, not a path.')
        if field['key'] in ('opdsDownloadFolder', 'nearbyReceiveFolder', 'path'):
            if value and (not value.startswith('/') or '..' in value.split('/') or '\\' in value):
                raise ValueError('Use an absolute SD-card path without parent traversal.')
    elif kind == 'bool':
        if type(value) is not bool:
            raise ValueError('This setting requires a JSON boolean.')
    elif kind == 'enum':
        if not any(type(value) is type(raw) and raw == value for raw, _ in field['choices']):
            raise ValueError('Choose a supported value for this reader model.')
    else:
        maximum = 1 if kind == 'toggle' else field.get('maximum', 255)
        if type(value) is not int or not field.get('minimum', 0) <= value <= maximum:
            raise ValueError('A numeric setting is outside its supported range or type.')
        if kind == 'time' and value != 65535 and not 0 <= value < 1440:
            raise ValueError('Schedule times must be minutes since midnight or unset.')
        if field.get('step', 1) > 1 and value % field['step']:
            raise ValueError('The numeric setting does not match its supported step.')


def validate_document(doc, store):
    if type(doc) is not dict:
        raise ValueError('Configuration must be an object.')
    if store == 'dictionary':
        validate(schema.store_fields(store, 'X3', doc)[0], doc.get('path'))
        return
    if store in ('wifi', 'opds', 'ttf'):
        array, limit = {'wifi': ('credentials', 8), 'opds': ('servers', 8), 'ttf': ('profiles', 24)}[store]
        entries = doc.get(array, [])
        if type(entries) is not list or len(entries) > limit or any(type(entry) is not dict for entry in entries):
            raise ValueError('The configuration collection has an invalid structure or exceeds its limit.')
    # Validate saved types, including raw enum types, without rejecting a value
    # solely because this model cannot offer it. Unknown fields are opaque.
    fields = schema.store_fields(store, 'X4 Pro', doc)
    for field in fields:
        key = field['key']
        if key.endswith(('.enabled', '.clearPassword')) or key == 'clearPassword':
            continue
        # path_get deep-copies fallbacks; a separate existence traversal avoids
        # confusing absent values with invalid explicit JSON nulls.
        parts, current, found = key.split('.'), doc, True
        for part in parts:
            try:
                current = current[int(part)] if type(current) is list else current[part]
            except (KeyError, IndexError, TypeError, ValueError):
                found = False
                break
        if not found:
            continue
        value = current
        kind = field['kind']
        if kind == 'enum':
            expected_type = type(field['choices'][0][0])
        else:
            expected_type = str if kind in ('text', 'secret') else bool if kind == 'bool' else int
        if type(value) is not expected_type:
            raise ValueError('A saved setting has an invalid type.')
        if kind in ('text', 'secret', 'bool', 'toggle'):
            validate(field, value)
    if store in ('wifi', 'opds', 'koreader'):
        entries = doc.get('credentials' if store == 'wifi' else 'servers', []) if store != 'koreader' else [doc]
        for entry in entries:
            if 'password_obf' in entry and type(entry['password_obf']) is not str:
                raise ValueError('Saved password material has an invalid type.')
        if store == 'wifi' and 'lastConnectedSsid' in doc and type(doc['lastConnectedSsid']) is not str:
            raise ValueError('The saved network marker has an invalid type.')
    if store == 'settings':
        if any(key in doc for key in ('lineSpacing', 'screenMargin', 'sleepTimeout')):
            raise ValueError('Legacy settings need firmware migration before editing.')
        if 'fontSize' in doc and type(doc['fontSize']) is int and doc['fontSize'] < 8:
            raise ValueError('Legacy reader font-size IDs need firmware migration first.')
        # Legacy choices can affect missing modern defaults. Let the firmware
        # migrate them first rather than silently inventing a different mapping.
        for old, modern in (('frontButtonLayout', 'frontButtonBack'), ('sideButtonLayout', 'sideButtonUpShort'),
                            ('sideButtonLongPress', 'sideButtonUpLong'), ('tiltPageTurn', 'tiltPageTurnDirection')):
            if old in doc and modern not in doc:
                raise ValueError('Legacy button or tilt mappings need firmware migration first.')
        bars = doc.get('readerStatusBars')
        if bars is not None:
            if type(bars) is not dict or type(bars.get('version')) is not int or bars.get('version') != 1:
                raise ValueError('The status-bar format version is unsupported.')
            for position in ('top', 'bottom'):
                bar = bars.get(position)
                if type(bar) is not dict or type(bar.get('slots')) is not list or len(bar['slots']) != 7:
                    raise ValueError('Status bars need seven slots; let the firmware migrate older layouts first.')
                if any(type(v) is not int or v not in range(11) for v in bar['slots']):
                    raise ValueError('A status-bar slot is invalid.')
                for key in ('percentageFormat', 'progressBar', 'thickness'):
                    if type(bar.get(key)) is not int or bar[key] not in range(3):
                        raise ValueError('A status-bar choice is invalid.')
            if type(bars.get('xtcMode')) is not int or bars['xtcMode'] not in range(4):
                raise ValueError('The XTC status-bar mode is invalid.')
        for key, count, allowed in (('quickActionSlots', 5, tuple(range(23)) + (26, 28, 29, 31, 32, 33)),
                                    ('displayStatusBar', 3, (0, 1, 2, 10))):
            if key in doc and (type(doc[key]) is not list or len(doc[key]) != count or
                               any(type(v) is not int or v not in allowed for v in doc[key])):
                raise ValueError('A shortcut or display status-bar array is invalid.')


def values(doc, store, fields):
    effective = schema.effective_settings(doc) if store == 'settings' else doc
    result = {}
    for field in fields:
        key = field['key']
        if field['kind'] == 'secret':
            value = ''  # Never return existing plaintext or obfuscated material.
        elif key.endswith('.enabled'):
            array, index, _ = key.split('.')
            value = int(int(index) < len(doc.get(array, [])))
        elif key.endswith('.clearPassword') or key == 'clearPassword':
            value = 0
        else:
            value = schema.path_get(effective, key, field['default'])
            if value is None:
                value = field['default']
        result[key] = value
    return result


def _credential(entry, patch, prefix, allow_plaintext):
    secret = patch.get(prefix + 'password', '')
    clear = patch.get(prefix + 'clearPassword', 0)
    if clear and secret:
        raise ValueError('Choose either a new password or clear password, not both.')
    if secret:
        if not allow_plaintext:
            raise ValueError('Explicit plaintext-handoff consent is required for a new password.')
        entry.pop('password_obf', None)
        entry['password'] = secret
        return True
    if clear:
        entry.pop('password', None)
        entry['password_obf'] = ''
    elif 'password' not in entry and 'password_obf' not in entry:
        entry['password_obf'] = ''
    return False


def _url(value):
    if not value:
        return
    try:
        parts = urlsplit(value)
    except ValueError:
        raise ValueError('Use a valid HTTP(S) URL without embedded credentials.') from None
    if parts.scheme not in ('http', 'https') or not parts.netloc or parts.username or parts.password:
        raise ValueError('Use an HTTP(S) URL without embedded credentials.')


def _quick_actions(doc, changes):
    by_key = {key: (number, action, reset) for number, key, action, reset in schema.TRIGGERS}
    if 'quickActionsTrigger' in changes:
        owner = changes['quickActionsTrigger']
        for number, key, action, reset in schema.TRIGGERS:
            if doc.get(key) == action:
                doc[key] = reset
        for number, key, action, _ in schema.TRIGGERS:
            if number == owner:
                doc[key] = action
    elif any(key in by_key for key in changes):
        owners = [by_key[key][0] for key, value in changes.items() if key in by_key and value == by_key[key][1]]
        if len(owners) > 1:
            raise ValueError('Quick Actions can own only one physical shortcut.')
        owner = owners[0] if owners else doc.get('quickActionsTrigger', 0)
        mapping = {number: (key, action) for number, key, action, _ in schema.TRIGGERS}
        if owner in mapping and doc.get(mapping[owner][0]) != mapping[owner][1]:
            owner = 0
        for number, key, action, reset in schema.TRIGGERS:
            if number != owner and doc.get(key) == action:
                doc[key] = reset
        doc['quickActionsTrigger'] = owner


def patch_document(doc, store, fields, changes, allow_plaintext=False):
    by_key = {field['key']: field for field in fields}
    if type(changes) is not dict or any(key not in by_key for key in changes):
        raise ValueError('Only supported configuration fields can be changed.')
    original_values = values(doc, store, fields)
    meaningful = {}
    for key, value in changes.items():
        field = by_key[key]
        if value == original_values[key] and type(value) is type(original_values[key]):
            continue
        if field.get('readonly'):
            raise ValueError(field['readonly'])
        validate(field, value)
        meaningful[key] = value
    result = deepcopy(doc)
    secret_changed = False
    if store in ('settings', 'dictionary'):
        template = schema.effective_settings(doc) if store == 'settings' else doc
        for key, value in meaningful.items():
            schema.path_set(result, key, value, template)
        if store == 'settings':
            _quick_actions(result, meaningful)
            if any(key in meaningful for key in ('fontSize', 'sdFontFamilyName')) and not result.get('sdFontFamilyName') and not 8 <= result.get('fontSize', 14) <= 22:
                raise ValueError('Built-in scalable reader fonts support 8–22 pt; larger sizes require an installed SD font family.')
            if 'tiltPageTurnDirection' in meaningful:
                result['tiltPageTurnDirectionSchema'] = 2
            for prefix in ('frontButton', 'readerFrontButton'):
                keys = [prefix + key for key in ('Back', 'Confirm', 'Left', 'Right')]
                if any(key in meaningful for key in keys) and len({schema.path_get(result, key, schema.MEMBER_DEFAULTS[key]) for key in keys}) != 4:
                    raise ValueError('Each front-button function must use a different physical button.')
            swipe_keys = ['twoFingerSwipe' + direction for direction in ('Up', 'Down', 'Left', 'Right')]
            if any(key in meaningful for key in swipe_keys):
                actions = [result.get(key, 0) for key in swipe_keys if result.get(key, 0)]
                if len(actions) != len(set(actions)):
                    raise ValueError('Each nonempty two-finger swipe action must be assigned only once.')
            if result.get('frontlightScheduleEnabled') and any(key.startswith('frontlightSchedule') for key in meaningful):
                start, end = result.get('frontlightScheduleStart', 65535), result.get('frontlightScheduleEnd', 65535)
                if not 0 <= start < 1440 or not 0 <= end < 1440 or start == end:
                    raise ValueError('An enabled frontlight schedule needs two different valid times.')
    elif store == 'koreader':
        if not doc and meaningful:
            result['cfgVersion'] = 2  # A fresh configuration uses the current default server.
        for key, value in meaningful.items():
            if key not in ('password', 'clearPassword'):
                result[key] = value
        if 'serverUrl' in meaningful:
            _url(result['serverUrl'])
        if 'password' in meaningful or meaningful.get('clearPassword'):
            secret_changed = _credential(result, meaningful, '', allow_plaintext)
        # Do not stamp cfgVersion=2 or change an absent server URL: pre-v2 users
        # implicitly use the legacy server until the firmware migrates them.
    else:
        array, limit = {'wifi': ('credentials', 8), 'opds': ('servers', 8), 'ttf': ('profiles', 24)}[store]
        original_entries = doc.get(array, [])
        entries = []
        for i in range(limit):
            prefix = array + '.' + str(i) + '.'
            enabled = meaningful.get(prefix + 'enabled', int(i < len(original_entries)))
            if not enabled:
                if any(key.startswith(prefix) and key != prefix + 'enabled' for key in meaningful):
                    raise ValueError('Enable the entry before editing it, or discard its draft before removing it.')
                continue
            entry = deepcopy(original_entries[i]) if i < len(original_entries) else {}
            for field in fields:
                key = field['key']
                leaf = key[len(prefix):] if key.startswith(prefix) else None
                if leaf and leaf not in ('enabled', 'password', 'clearPassword'):
                    if key in meaningful:
                        entry[leaf] = meaningful[key]
                    elif i >= len(original_entries):
                        entry[leaf] = field['default']
            if store == 'wifi':
                if not entry.get('ssid'):
                    raise ValueError('Every enabled Wi-Fi entry needs a network name.')
            if store == 'opds':
                if not entry.get('name') or not entry.get('url'):
                    raise ValueError('Every enabled OPDS entry needs a name and catalog URL.')
                _url(entry['url'])
            if store == 'ttf':
                if not entry.get('family') or '/' in entry['family'] or '\\' in entry['family']:
                    raise ValueError('Every enabled font profile needs an installed family name.')
                if entry.get('hinting', 2) != 1 and entry.get('interpreter', 0) != 0:
                    raise ValueError('A non-default interpreter requires Native hinting.')
            elif i >= len(original_entries) or prefix + 'password' in meaningful or meaningful.get(prefix + 'clearPassword'):
                secret_changed |= _credential(entry, meaningful, prefix, allow_plaintext)
            entries.append(entry)
        unique_key = {'wifi': 'ssid', 'opds': None, 'ttf': 'family'}[store]
        if unique_key and len({entry[unique_key] for entry in entries}) != len(entries):
            raise ValueError('Connection names or font families must not be duplicated.')
        if any(key.startswith(array + '.') for key in meaningful):
            result[array] = entries
        if store == 'wifi':
            last = doc.get('lastConnectedSsid', '')
            if last and last not in {entry['ssid'] for entry in entries}:
                result['lastConnectedSsid'] = ''
    validate_document(result, store)
    return result, secret_changed


def differences(before, after, store, fields, changes=None):
    old, new = values(before, store, fields), values(after, store, fields)
    result = []
    for field in fields:
        key = field['key']
        label = (field.get('section', '') + ' — ' if key.startswith(('credentials.', 'servers.', 'profiles.')) else '') + field['label']
        if field['kind'] == 'secret':
            if changes and changes.get(key):
                result.append(dict(key=key, label=label, before='Saved password hidden', after='New password (plaintext handoff)'))
            elif changes is None:
                prefix = key[:-len('password')]
                if any(schema.path_get(before, prefix + name) != schema.path_get(after, prefix + name)
                       for name in ('password', 'password_obf')):
                    result.append(dict(key=key, label=label, before='Saved password hidden', after='Password from backup (hidden)'))
            continue
        if changes and changes.get(key) and key.endswith('clearPassword'):
            result.append(dict(key=key, label=label, before='Saved password hidden', after='Password cleared'))
            continue
        # Collection indexes can shift after a deletion; preview the removed
        # entry and all affected names without exposing credential material.
        if old[key] != new[key] or type(old[key]) is not type(new[key]):
            result.append(dict(key=key, label=label, before=old[key], after=new[key]))
    return result
