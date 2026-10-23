"""Storage-aware, model-aware forms for the pinned CrossInk configuration stores."""
from copy import deepcopy
import re

from crossink_profile import ACTION_VALUES, BASE_FIELDS, FIRMWARE_VERSION, LANGUAGES, MEMBER_DEFAULTS, UPSTREAM_COMMIT

MODELS = {
    'X3': {'rtc', 'tilt', 'front_buttons'},
    'X4': {'front_buttons'},
    'X4 Classic': {'rtc', 'tilt', 'front_buttons', 'side_chord', 'psram'},
    'X4 Pro': {'rtc', 'touch', 'multitouch', 'frontlight', 'warmth', 'home', 'side_chord', 'psram'},
}
STORES = {
    'settings': ('crossink-settings.json', 'Reader settings'),
    'wifi': ('wifi.json', 'Wi-Fi'),
    'opds': ('opds.json', 'OPDS servers'),
    'koreader': ('koreader.json', 'Reading sync'),
    'ttf': ('ttf-rendering.json', 'Font rendering'),
    'dictionary': ('dictionary.bin', 'Dictionary'),
}
STATUS_ITEMS = ('Empty', 'Clock', 'Battery', 'Time left in book', 'Time left in chapter',
                'Chapter page count', 'Stable page number', 'Book progress percentage',
                'Book title', 'Chapter title', 'Date')
TRIGGERS = (
    (1, 'shortPwrBtn', 27, 0), (2, 'longPwrBtn', 27, 0),
    (3, 'longPressBackAction', 22, 0), (4, 'longPressMenuAction', 22, 0),
    (5, 'powerChordAction', 26, 4), (6, 'homeButtonTapAction', 27, 23),
    (7, 'homeButtonLongPressAction', 27, 25), (8, 'homeButtonDoubleTapAction', 27, 24),
    (9, 'sideButtonChordAction', 26, 4), (10, 'sideButtonUpShort', 27, 0),
    (11, 'sideButtonUpLong', 27, 0), (12, 'sideButtonDownShort', 27, 0),
    (13, 'sideButtonDownLong', 27, 0),
)


def title(key):
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', key).replace('_', ' ').capitalize()


def row(key, label, group='device', kind='toggle', default=0, **kwargs):
    return dict(key=key, label=label, group=group, kind=kind, default=default,
                minimum=0, maximum=1, **kwargs)


def choice(key, label, values, default=0, group='device'):
    return dict(key=key, label=label, group=group, kind='enum', default=default,
                minimum=0, maximum=65535, choices=list(values))


def path_get(doc, path, default=None):
    value = doc
    try:
        for part in path.split('.'):
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value
    except (KeyError, IndexError, TypeError, ValueError):
        return deepcopy(default)


def path_set(doc, path, value, template=None):
    parts = path.split('.')
    target = doc
    prefix = []
    for part in parts[:-1]:
        prefix.append(part)
        key = int(part) if isinstance(target, list) else part
        try:
            child = target[key]
        except (KeyError, IndexError):
            child = path_get(template or {}, '.'.join(prefix), {})
            if isinstance(target, list):
                while len(target) <= key:
                    target.append(None)
            target[key] = child
        target = child
    last = int(parts[-1]) if isinstance(target, list) else parts[-1]
    target[last] = value


def effective_settings(doc):
    """Defaults are for display only; patches never serialize this entire object."""
    result = {field['key']: deepcopy(field['default']) for field in BASE_FIELDS}
    result.update({key: value for key, value in MEMBER_DEFAULTS.items() if key != 'dictionaryFontPointSize'})
    result.update(sdFontFamilyName='', dictionaryFont='', dictionaryFontSize=0,
                  language='EN', keyboardLayouts=0, quickActionsTrigger=0,
                  quickActionSlots=[0] * 5, displayStatusBar=[0, 0, 2])
    # Match the firmware loader's conditional defaults before deriving layouts.
    # These are effective display values only; patches still preserve absent keys.
    if 'previousPageGesture' not in doc:
        result['previousPageGesture'] = doc.get('pageTurnGesture', result['pageTurnGesture'])
    if 'screenInverted' not in doc and 'readerDarkMode' in doc:
        result['screenInverted'] = doc['readerDarkMode'] if doc['readerDarkMode'] in (0, 1) else 0
    if 'hideClock' not in doc and 'statusBarClock' in doc:
        result['hideClock'] = 0 if doc['statusBarClock'] in (1, 2) else 2
    if 'fileBrowserDisplay' not in doc:
        if 'fileBrowserPreview' in doc:
            result['fileBrowserDisplay'] = doc['fileBrowserPreview'] if doc['fileBrowserPreview'] in (0, 1) else 0
        elif doc.get('uiTheme', result['uiTheme']) == 5:
            result['fileBrowserDisplay'] = 1
    result['readerStatusBars'] = dict(version=1, xtcMode=doc.get('xtcStatusBarMode', 0),
                                    legacyXtcTopUsesBottom=doc.get('xtcStatusBarMode', 0) == 2,
                                    top=dict(slots=[0] * 7, percentageFormat=0, progressBar=2, thickness=1),
                                    bottom=dict(slots=[2, 0, 0, 9, 5, 7, 0], percentageFormat=0, progressBar=2, thickness=1))
    if 'readerStatusBars' not in doc:
        # Same bounded layout migration used by the firmware: two left and three right legacy items.
        old = {**result, **doc}
        left = ([2] if old['statusBarBattery'] else [])
        if old['statusBarTimeLeft'] in (1, 2):
            left.append(4 if old['statusBarTimeLeft'] == 1 else 3)
        right = ([5] if old['statusBarChapterPageCount'] else [])
        if old['stablePageNumbers']:
            right.append(6)
        if old['statusBarBookProgressPercentage']:
            right.append(7)
        bottom = result['readerStatusBars']['bottom']
        bottom['slots'] = (left + [0] * 3)[:3] + [8 if old['statusBarTitle'] == 0 else 9 if old['statusBarTitle'] == 1 else 0] + (right + [0] * 3)[:3]
        bottom.update(percentageFormat=old['statusBarBookPercentageFormat'], progressBar=old['statusBarProgressBar'],
                      thickness=old['statusBarProgressBarThickness'])
    if 'readerStatusBars' not in doc and doc.get('hideClock', result['hideClock']) == 0:
        result['readerStatusBars']['top']['slots'][3] = 1
    if 'displayStatusBar' not in doc:
        show_clock = bool(doc.get('showClockOutsideReader', doc.get('hideClock', result['hideClock']) != 2))
        result['displayStatusBar'] = [0, 1 if show_clock else 0, 2]
    result.update(deepcopy(doc))
    return result


def _capability(field):
    key = field['key']
    if key.startswith('frontlight'):
        return 'warmth' if key == 'frontlightWarmth' else 'frontlight'
    if key.startswith(('twoFinger', 'pinch')):
        return 'multitouch'
    if key.startswith(('leftEdge', 'rightEdge')) or key in ('touchReaderControls', 'disableReaderTouchscreen', 'pageTurnGesture', 'previousPageGesture', 'tapToHideStatusBar'):
        return 'touch'
    if key.startswith('homeButton'):
        return 'home'
    if key.startswith(('frontButton', 'readerFrontButton')) or key in ('longPressMenuAction', 'longPressBackAction', 'longPressButtonBehavior', 'fadingFix'):
        return 'front_buttons'
    if key.startswith('tilt'):
        return 'tilt'
    if key == 'sideButtonChordAction':
        return 'side_chord'
    if key in ('hideClock', 'clockUtcOffsetQ', 'clockFormat', 'dateFormat', 'dateSeparator', 'autoBackupStats', 'clockHasBeenSynced'):
        return 'rtc'
    return None


def _available_action(name, capabilities, doc):
    return not ((name == 'TOGGLE_TILT_PAGE_TURN' and 'tilt' not in capabilities)
                or (name == 'TOGGLE_FRONTLIGHT' and 'frontlight' not in capabilities)
                or (name == 'TOGGLE_TOUCHSCREEN' and 'touch' not in capabilities)
                or (name == 'TOGGLE_HOME_BUTTON_IN_READER' and 'home' not in capabilities)
                or (name == 'HOME_READER' and 'touch' in capabilities)
                or (name == 'READING_STATS' and doc.get('trackReadingStats', 1) == 0))


def shortcut_choices(catalog, capabilities, doc):
    values = ACTION_VALUES['SHORT_PWRBTN']
    choices = []
    for name, value in values.items():
        if name.endswith('_COUNT') or not _available_action(name, capabilities, doc):
            continue
        if catalog not in ('PowerButton',) and name in ('SLEEP_ONLY', 'WAKE_ONLY'):
            continue
        if catalog == 'HomeButton' and name in ('TOGGLE_TILT_PAGE_TURN', 'TOGGLE_HOME_BUTTON_IN_READER', 'TOGGLE_FRONTLIGHT', 'HOME_READER'):
            continue
        if catalog in ('ButtonChord', 'LongPress'):
            prefix = 'CHORD_' if catalog == 'ButtonChord' else 'LONG_MENU_'
            aliases = {'IGNORE': 'DISABLED' if catalog == 'ButtonChord' else 'OFF',
                       'TOGGLE_HOME_BUTTON_IN_READER': 'TOGGLE_HOME_BUTTON',
                       'TOGGLE_FONT': 'TOGGLE_FONT' if catalog == 'ButtonChord' else 'CHANGE_FONT',
                       'TOGGLE_FOCUS_READING': 'TOGGLE_FOCUS_READING' if catalog == 'ButtonChord' else 'TOGGLE_FOCUS',
                       'FORCE_REFRESH': 'FORCE_REFRESH' if catalog == 'ButtonChord' else 'REFRESH_SCREEN'}
            mapped = prefix + aliases.get(name, name)
            table = ACTION_VALUES['POWER_CHORD_ACTION' if catalog == 'ButtonChord' else 'LONG_PRESS_MENU_ACTION']
            if mapped not in table:
                continue
            value = table[mapped]
        choices.append((value, name.replace('_', ' ').capitalize()))
    if catalog == 'HomeButton':
        choices = [(23, 'Back to Home'), (25, 'Reader menu')] + ([(24, 'Toggle frontlight')] if 'frontlight' in capabilities else []) + choices
    if catalog == 'SideButton':
        choices += [(value, name.removeprefix('SIDE_').replace('_', ' ').capitalize()) for name, value in ACTION_VALUES['SIDE_BUTTON_ACTION'].items() if not name.endswith('_COUNT')]
    return choices


def main_fields(model, doc):
    capabilities = MODELS[model]
    fields = deepcopy(list(BASE_FIELDS))
    # Legacy serialized mirrors are superseded by the modern Status bars editor.
    fields = [field for field in fields if field['group'] != 'legacy']
    for field in fields:
        key = field['key']
        field.setdefault('minimum', 0)
        field.setdefault('maximum', 255)
        field.setdefault('section', field['group'].capitalize())
        if field['kind'] == 'shortcut':
            field['choices'] = shortcut_choices(field.pop('catalog'), capabilities, doc)
            field['kind'] = 'enum'
            field['label'] = title(key)
        if field['default'] is None:
            field['default'] = 1 if 'touch' in capabilities else 0
        if key.startswith('frontlightSchedule') and key.endswith(('Start', 'End')):
            field['kind'] = 'time'
        if key == 'fontFamily':
            field['label'] = 'Built-in font (used when SD font family is empty)'
        if key == 'clockHasBeenSynced':
            field['label'] = 'Clock sync flag (does not set the hardware clock)'
        if key == 'clockUtcOffsetQ':
            field['kind'] = 'timezone'
        if key == 'uiTheme':
            field['choices'] = [(v, label) for v, label in field['choices']
                                if not (v in (0, 3) and 'touch' in capabilities)
                                and not (v == 7 and 'psram' not in capabilities)]
        if key == 'sleepScreen':
            field['choices'] = [(v, label) for v, label in field['choices']
                                if not (v == 10 and model != 'X3')
                                and not (v in (7, 10) and doc.get('trackReadingStats', 1) == 0)]
        if key == 'refreshFrequency' and 'frontlight' not in capabilities:
            field['choices'] = [(v, label) for v, label in field['choices'] if v != 5]
        if key in ('twoFingerSwipeUp', 'twoFingerSwipeDown', 'twoFingerSwipeLeft', 'twoFingerSwipeRight', 'leftEdgeUp', 'leftEdgeDown', 'rightEdgeUp', 'rightEdgeDown'):
            field['choices'] = [(v, label) for v, label in field['choices'] if not (v in (1, 2) and 'frontlight' not in capabilities) and not (v in (3, 4) and 'warmth' not in capabilities)]
        cap = _capability(field)
        if cap and cap not in capabilities:
            field['readonly'] = 'This reader model does not provide this capability.'
        if key == 'tiltPageTurnDirection' and model == 'X4 Classic':
            field['choices'][0], field['choices'][1] = (0, 'Left/right inverted'), (1, 'Left/right')
        if key == 'tiltPageTurnDirection' and 'tiltPageTurnDirection' in doc and doc.get('tiltPageTurnDirectionSchema', 1) != 2:
            field['readonly'] = 'Run this firmware once to migrate its tilt-direction schema.'
    for key, default in MEMBER_DEFAULTS.items():
        if key == 'clockDateHasBeenSynced':
            continue  # Firmware observation, not a user configuration.
        if key == 'dictionaryFontPointSize':
            continue  # Serialized under dictionaryFontSize below.
        if key.startswith(('frontButton', 'readerFrontButton')):
            field = row(key, title(key), 'controls', default=default)
            if key != 'readerFrontButtonsEnabled':
                field = choice(key, title(key), enumerate(('Back', 'Confirm', 'Left', 'Right')), default, 'controls')
            if 'front_buttons' not in capabilities:
                field['readonly'] = 'This model has no front-button cluster.'
        elif key == 'librarySortMethod':
            field = choice(key, 'Library sort', enumerate(('Date added', 'Title', 'Author last name', 'Author first name', 'Last opened', 'Series', 'Genre')), default, 'library')
        elif key == 'recentBooksView':
            field = choice(key, 'Recent books view', enumerate(('List', 'Grid')), default, 'library')
        else:
            field = row(key, title(key), 'library', default=default)
        fields.append(field)
    fields += [dict(key='sdFontFamilyName', label='SD font family', group='reading', kind='text', default='', minimum=0, maximum=63),
               dict(key='dictionaryFont', label='Dictionary font family', group='reading', kind='text', default='', minimum=0, maximum=63),
               dict(key='dictionaryFontSize', label='Dictionary font size (pt; 0 = reader)', group='reading', kind='integer', default=0, minimum=0, maximum=255),
               choice('language', 'Language', LANGUAGES, 'EN', 'device'),
               dict(key='keyboardLayouts', label='Keyboard layouts (0 = automatic)', group='device', kind='flags', default=0, minimum=0, maximum=511,
                    choices=[(1 << i, label) for i, label in enumerate(('English', 'French', 'German', 'Spanish', 'Russian', 'Ukrainian', 'Belarusian', 'Kazakh', 'Hebrew'))])]
    # Quick Actions owns exactly one shortcut; backend synchronization is previewed.
    trigger_options = [(0, 'None')] + [(number, title(key)) for number, key, _, _ in TRIGGERS
                                      if not ((key.startswith('homeButton') and 'home' not in capabilities)
                                              or (key == 'sideButtonChordAction' and 'side_chord' not in capabilities)
                                              or (key in ('longPressMenuAction', 'longPressBackAction') and 'front_buttons' not in capabilities))]
    fields.append(choice('quickActionsTrigger', 'Quick Actions shortcut', trigger_options, 0, 'controls'))
    for i in range(5):
        options = [(v, name.replace('_', ' ').capitalize()) for name, v in ACTION_VALUES['SHORT_PWRBTN'].items()
                   if v in tuple(range(23)) + (26, 28, 29, 31, 32, 33) and _available_action(name, capabilities, doc)]
        fields.append(choice('quickActionSlots.' + str(i), 'Quick Action ' + str(i + 1), options, 0, 'controls'))
    for i in range(3):
        options = [(v, STATUS_ITEMS[v]) for v in (0, 1, 2, 10) if 'rtc' in capabilities or v not in (1, 10)]
        fields.append(choice('displayStatusBar.' + str(i), 'Display bar — ' + ('left', 'center', 'right')[i], options, (0, 0, 2)[i], 'status'))
    effective = effective_settings(doc)
    for position in ('top', 'bottom'):
        prefix = 'readerStatusBars.' + position + '.'
        for i in range(7):
            options = [(v, label) for v, label in enumerate(STATUS_ITEMS) if 'rtc' in capabilities or v not in (1, 10)]
            fields.append(choice(prefix + 'slots.' + str(i), position.capitalize() + ' slot ' + str(i + 1), options,
                                 path_get(effective, prefix + 'slots.' + str(i)), 'status'))
        for key, label, options, default in (
                ('percentageFormat', 'Percentage precision', ('Whole', 'One decimal', 'Two decimals'), 0),
                ('progressBar', 'Progress bar', ('Book', 'Chapter', 'Hidden'), 2),
                ('thickness', 'Bar thickness', ('Thin', 'Normal', 'Thick'), 1)):
            fields.append(choice(prefix + key, position.capitalize() + ' — ' + label, enumerate(options), default, 'status'))
    fields += [choice('readerStatusBars.xtcMode', 'XTC status bars', enumerate(('Hidden', 'Bottom', 'Top', 'Both')), effective['readerStatusBars']['xtcMode'], 'status'),
               row('readerStatusBars.legacyXtcTopUsesBottom', 'XTC top uses bottom layout (legacy)', 'status', 'bool', False)]
    return fields


def store_fields(store, model, doc):
    if store == 'settings':
        return main_fields(model, doc)
    if store == 'dictionary':
        return [dict(key='path', label='Dictionary base path', group='dictionary', kind='text', default='', minimum=0, maximum=1023)]
    if store == 'koreader':
        return [dict(key=key, label=label, group='sync', kind=kind, default=default, minimum=0, maximum=2048)
                for key, label, kind, default in (('username', 'Username', 'text', ''), ('password', 'New password (blank keeps existing)', 'secret', ''),
                                                ('clearPassword', 'Clear saved password', 'toggle', 0), ('serverUrl', 'Sync server URL', 'text', '' ))] + [
                    choice('matchMethod', 'Document matching', enumerate(('Filename', 'Binary')), 0, 'sync'),
                    row('sendMetadata', 'Send metadata', 'sync', 'bool', False),
                    choice('syncBehavior', 'Sync behavior', enumerate(('Ask every time', 'Smart')), 0, 'sync')]
    fields = []
    count, array, label = {'wifi': (8, 'credentials', 'Network'), 'opds': (8, 'servers', 'Server'), 'ttf': (24, 'profiles', 'Family')}[store]
    entries = doc.get(array, [])
    for i in range(count):
        prefix = array + '.' + str(i) + '.'
        section = label + ' ' + str(i + 1)
        fields.append(dict(**row(prefix + 'enabled', 'Include ' + label.lower(), store, default=int(i < len(entries))), section=section))
        if store == 'wifi':
            spec = [('ssid', 'Network name (SSID)', 'text', '', 32), ('password', 'New password (blank keeps existing)', 'secret', '', 64), ('clearPassword', 'Use an open network (clear password)', 'toggle', 0, 1)]
        elif store == 'opds':
            spec = [('name', 'Name', 'text', '', 255), ('url', 'Catalog URL', 'text', '', 2048), ('username', 'Username', 'text', '', 255), ('password', 'New password (blank keeps existing)', 'secret', '', 2048), ('clearPassword', 'Clear saved password', 'toggle', 0, 1)]
        else:
            spec = [('family', 'Installed font family', 'text', '', 63)]
        for key, name, kind, default, maximum in spec:
            fields.append(dict(key=prefix + key, label=name, group=store, kind=kind, default=default, minimum=0, maximum=maximum, section=section))
        if store == 'opds':
            fields.append(dict(**choice(prefix + 'filenameFormat', 'Download filename', [('author_title', 'Author — Title'), ('title_author', 'Title — Author')], 'author_title', store), section=section))
        if store == 'ttf':
            for key, name, options, default in (
                ('hinting', 'Hinting', ('None', 'Native', 'Auto', 'Light'), 2),
                ('raster', 'Raster', ('Grayscale', 'Monochrome'), 0),
                ('interpreter', 'Interpreter', ('Default', 'FreeType 35', 'FreeType 40'), 0),
                ('weight', 'Weight', ('−0.5 px', '−0.25 px', 'Unchanged', '+0.25 px', '+0.5 px', '+0.75 px', '+1 px'), 2),
                ('slant', 'Slant', ('None', 'Gentle', 'Medium', 'Strong'), 0)):
                fields.append(dict(**choice(prefix + key, name, enumerate(options), default, store), section=section))
            fields.append(dict(**row(prefix + 'stemDarkening', 'Stem darkening', store, 'bool', False), section=section))
    return fields
