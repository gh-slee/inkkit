#!/usr/bin/env python3
"""Generate the pinned configuration reference; CI rejects stale coverage docs."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import inkkit_schema as schema
from crossink_profile import BASE_FIELDS, MEMBER_DEFAULTS

# Audited locations in the pinned upstream tree; these are source coordinates,
# not firmware code. Re-audit the source before changing the profile pin.
SOURCE_LINES = {'autoBackupStats': ('src/SettingsList.cpp', 254),
 'clockFormat': ('src/SettingsList.cpp', 363),
 'clockHasBeenSynced': ('src/SettingsList.cpp', 378),
 'clockUtcOffsetQ': ('src/SettingsList.cpp', 361),
 'customBootscreenEnabled': ('src/SettingsList.cpp', 242),
 'dateFormat': ('src/SettingsList.cpp', 371),
 'dateSeparator': ('src/SettingsList.cpp', 375),
 'deviceName': ('src/SettingsList.cpp', 235),
 'dictionaryFont': ('src/CrossPointSettings.cpp', 497),
 'dictionaryFontSize': ('src/CrossPointSettings.cpp', 498),
 'disableReaderTouchscreen': ('src/SettingsList.cpp', 120),
 'displayStatusBar': ('src/CrossPointSettings.cpp', 463),
 'embeddedStyle': ('src/SettingsList.cpp', 108),
 'extraParagraphSpacing': ('src/SettingsList.cpp', 122),
 'fadingFix': ('src/SettingsList.cpp', 54),
 'fileBrowserDisplay': ('src/SettingsList.cpp', 249),
 'focusReadingEnabled': ('src/SettingsList.cpp', 125),
 'fontFamily': ('src/SettingsList.cpp', 73),
 'fontSize': ('src/SettingsList.h', 35),
 'forceParagraphIndents': ('src/SettingsList.cpp', 124),
 'frontButtonBack': ('src/CrossPointSettings.cpp', 486),
 'frontButtonConfirm': ('src/CrossPointSettings.cpp', 487),
 'frontButtonLeft': ('src/CrossPointSettings.cpp', 488),
 'frontButtonOrientationAware': ('src/SettingsList.cpp', 192),
 'frontButtonRight': ('src/CrossPointSettings.cpp', 489),
 'frontlightBrightness': ('src/SettingsList.cpp', 273),
 'frontlightOn': ('src/SettingsList.cpp', 275),
 'frontlightRestoreOnWake': ('src/SettingsList.cpp', 57),
 'frontlightScheduleEnabled': ('src/SettingsList.cpp', 61),
 'frontlightScheduleEnd': ('src/SettingsList.cpp', 66),
 'frontlightScheduleStart': ('src/SettingsList.cpp', 63),
 'frontlightWarmth': ('src/SettingsList.cpp', 274),
 'guideReadingEnabled': ('src/SettingsList.cpp', 127),
 'hideBatteryPercentage': ('src/SettingsList.cpp', 21),
 'hideClock': ('src/SettingsList.cpp', 24),
 'hideFileExtension': ('src/SettingsList.cpp', 245),
 'homeButtonDoubleTapAction': ('src/SettingsList.cpp', 214),
 'homeButtonInReaderEnabled': ('src/SettingsList.cpp', 208),
 'homeButtonLongPressAction': ('src/SettingsList.cpp', 216),
 'homeButtonTapAction': ('src/SettingsList.cpp', 212),
 'hyphenationEnabled': ('src/SettingsList.cpp', 110),
 'imageRendering': ('src/SettingsList.cpp', 116),
 'indexingMethod': ('src/SettingsList.cpp', 130),
 'keyboardLayouts': ('src/CrossPointSettings.cpp', 505),
 'language': ('src/CrossPointSettings.cpp', 504),
 'leftEdgeDown': ('src/SettingsList.cpp', 171),
 'leftEdgeUp': ('src/SettingsList.cpp', 167),
 'libraryHideFinishedBooks': ('src/CrossPointSettings.cpp', 484),
 'libraryListExpanded': ('src/CrossPointSettings.cpp', 476),
 'libraryShowEpub': ('src/CrossPointSettings.cpp', 480),
 'libraryShowGenre': ('src/CrossPointSettings.cpp', 479),
 'libraryShowMarkdown': ('src/CrossPointSettings.cpp', 483),
 'libraryShowSeries': ('src/CrossPointSettings.cpp', 478),
 'libraryShowTxt': ('src/CrossPointSettings.cpp', 482),
 'libraryShowXtc': ('src/CrossPointSettings.cpp', 481),
 'librarySortDescending': ('src/CrossPointSettings.cpp', 475),
 'librarySortMethod': ('src/CrossPointSettings.cpp', 474),
 'libraryUseMetadata': ('src/SettingsList.cpp', 53),
 'lineHeightPercent': ('src/SettingsList.cpp', 84),
 'longPressBackAction': ('src/SettingsList.cpp', 220),
 'longPressButtonBehavior': ('src/SettingsList.cpp', 196),
 'longPressMenuAction': ('src/SettingsList.cpp', 218),
 'longPwrBtn': ('src/SettingsList.cpp', 201),
 'moveFinishedToReadFolder': ('src/SettingsList.cpp', 253),
 'nearbyReceiveFolder': ('src/SettingsList.cpp', 262),
 'opdsDownloadFolder': ('src/SettingsList.cpp', 259),
 'orientation': ('src/SettingsList.cpp', 90),
 'pageTurnGesture': ('src/SettingsList.cpp', 226),
 'paragraphAlignment': ('src/SettingsList.cpp', 107),
 'pinchFontResizeEnabled': ('src/SettingsList.cpp', 135),
 'powerChordAction': ('src/SettingsList.cpp', 203),
 'previousPageGesture': ('src/SettingsList.cpp', 230),
 'publisherPageNumbers': ('src/SettingsList.cpp', 103),
 'pwrBtnFootnoteBack': ('src/SettingsList.cpp', 222),
 'quickActionSlots': ('src/CrossPointSettings.cpp', 499),
 'quickActionsTrigger': ('src/CrossPointSettings.cpp', 503),
 'quickResumeSleepScreen': ('src/SettingsList.cpp', 19),
 'readerFrontButtonBack': ('src/CrossPointSettings.cpp', 491),
 'readerFrontButtonConfirm': ('src/CrossPointSettings.cpp', 492),
 'readerFrontButtonLeft': ('src/CrossPointSettings.cpp', 493),
 'readerFrontButtonRight': ('src/CrossPointSettings.cpp', 494),
 'readerFrontButtonsEnabled': ('src/CrossPointSettings.cpp', 490),
 'readerStatusBars': ('src/util/ReaderStatusBarJson.h', 20),
 'readingIdleTimeThresholdUnits': ('src/SettingsList.cpp', 266),
 'recentBooksView': ('src/CrossPointSettings.cpp', 477),
 'refreshFrequency': ('src/SettingsList.cpp', 31),
 'removeReadBooksFromRecents': ('src/SettingsList.cpp', 251),
 'rightEdgeDown': ('src/SettingsList.cpp', 177),
 'rightEdgeUp': ('src/SettingsList.cpp', 174),
 'screenInverted': ('src/SettingsList.cpp', 35),
 'screenMarginHorizontal': ('src/SettingsList.cpp', 101),
 'screenMarginVertical': ('src/SettingsList.cpp', 97),
 'sdFontFamilyName': ('src/CrossPointSettings.cpp', 496),
 'sdFontSizeRange': ('src/SettingsList.cpp', 78),
 'shortPwrBtn': ('src/SettingsList.cpp', 199),
 'showHiddenFiles': ('src/SettingsList.cpp', 243),
 'sideButtonChordAction': ('src/SettingsList.cpp', 206),
 'sideButtonDownLong': ('src/SettingsList.cpp', 189),
 'sideButtonDownShort': ('src/SettingsList.cpp', 187),
 'sideButtonOrientationAware': ('src/SettingsList.cpp', 181),
 'sideButtonUpLong': ('src/SettingsList.cpp', 185),
 'sideButtonUpShort': ('src/SettingsList.cpp', 183),
 'sleepScreen': ('src/SettingsList.h', 338),
 'sleepScreenCoverFilter': ('src/SettingsList.cpp', 17),
 'sleepScreenCoverMode': ('src/SettingsList.cpp', 14),
 'sleepTimeoutMinutes': ('src/SettingsList.cpp', 240),
 'swapLibraryFileBrowser': ('src/SettingsList.cpp', 48),
 'tapToHideStatusBar': ('src/SettingsList.cpp', 232),
 'textAntiAliasing': ('src/SettingsList.cpp', 112),
 'tiltPageTurn': ('src/SettingsList.cpp', 387),
 'tiltPageTurnDirection': ('src/SettingsList.cpp', 400),
 'touchReaderControls': ('src/SettingsList.cpp', 118),
 'trackReadingStats': ('src/SettingsList.cpp', 267),
 'twoFingerRotationEnabled': ('src/SettingsList.cpp', 137),
 'twoFingerSwipeDown': ('src/SettingsList.cpp', 158),
 'twoFingerSwipeLeft': ('src/SettingsList.cpp', 161),
 'twoFingerSwipeRight': ('src/SettingsList.cpp', 164),
 'twoFingerSwipeUp': ('src/SettingsList.cpp', 155),
 'uiScale': ('src/SettingsList.cpp', 50),
 'uiTheme': ('src/SettingsList.cpp', 41),
 'wordSpacing': ('src/SettingsList.cpp', 86)}

START = '<!-- configuration-summary:start -->'
END = '<!-- configuration-summary:end -->'


def summary():
    counts = {model: sum(not f.get('readonly') for f in schema.main_fields(model, {})) for model in schema.MODELS}
    return (START + '\nDevelopment source includes a native macOS configuration app for **CrossInk v' + schema.FIRMWARE_VERSION + '**.\n'
            'It opens an explicitly selected current SD card and supports **148 main-setting controls**,\n'
            'plus up to **8 Wi-Fi networks, 8 OPDS servers, reading-sync preferences, 24 TTF profiles\n'
            'and the global dictionary selection**. Controls follow the selected model: ' +
            ', '.join(model + ' ' + str(count) for model, count in counts.items()) +
            ' editable main controls in a fresh profile. Older tilt schemas require firmware migration first.\n\n'
            'Review, complete six-store Mac-side backups, verified apply, guarded restore and safe eject\n'
            'are implemented. Backups supports Backup now, newest-first history, reviewed restore and confirmed deletion.\n'
            'New or retained plaintext passwords require explicit consent for each write.\n'
            'The app is a **development build with limited owner-reported X3 settings acceptance**.\n'
            'Restore, safe eject and tested preferences including Sleep Screen worked on X3; other settings/models remain unvalidated.\n'
            'There is no signed/notarized app download; v1.0.0 remains the migration CLI release.\n\n'
            'See the [configuration reference](docs/configuration-reference.md) for every control and limitation,\n'
            'and [build/use instructions](docs/macos-preview.md). The app does not format cards, flash firmware,\n'
            'execute sync/network operations or install font/dictionary assets.\n' + END)


def cell(value):
    return str(value).replace('|', r'\|').replace('\n', ' ')


def field_type(field, variants):
    kind = field['kind']
    if kind == 'enum':
        choices = {}
        for model, candidate in variants:
            for raw, label in candidate['choices']:
                choices.setdefault((raw, label), []).append(model)
        return '; '.join('`' + str(raw) + '` ' + cell(label) +
                         (' (' + ', '.join(models) + ')' if len(models) != 4 else '')
                         for (raw, label), models in choices.items())
    if kind == 'text': return 'UTF-8 text, ' + str(field['maximum']) + ' bytes max'
    if kind == 'secret': return 'Write-only password, ' + str(field['maximum']) + ' UTF-8 bytes max; consent required'
    if kind == 'bool': return 'JSON boolean'
    if kind == 'toggle': return 'Numeric 0/1'
    if kind == 'time': return '0–1439 local minutes; 65535 unset'
    if kind == 'timezone': return '0–104; UTC quarter-hours biased by 48'
    if kind == 'flags': return 'Bit mask 0–511; 0 follows language; ' + '; '.join(str(v) + ' ' + label for v, label in field['choices'])
    return str(field['minimum']) + '–' + str(field['maximum']) + ('; step ' + str(field['step']) if field.get('step', 1) != 1 else '') + ('; 31 = Never' if field['key'] == 'sleepTimeoutMinutes' else '; each unit = 10 seconds' if field['key'] == 'readingIdleTimeThresholdUnits' else '')


def reference():
    base = 'https://github.com/uxjulia/CrossInk/blob/' + schema.UPSTREAM_COMMIT + '/'
    lines = ['# CrossInk configuration reference', '',
             'Generated by `python3 scripts/check_configuration_docs.py --write`. CI checks this file and the README summary.', '',
             '## Version and evidence', '',
             'The app implements the global offline configuration contract in CrossInk v' + schema.FIRMWARE_VERSION + ', commit `' + schema.UPSTREAM_COMMIT + '`.',
             'The user selects X3, X4, X4 Classic or X4 Pro and confirms this firmware version. Neither model nor running firmware can be inferred reliably from the SD layout.',
             'These are source-backed settings. Limited owner-reported X3 acceptance covers restore, safe eject and tested preferences including Sleep Screen; it is not validation of every control or other models.',
             'See the [validation evidence and X3 acceptance gates](configuration-validation.md). Every main control below links to its pinned upstream definition or serializer.', '',
             'Primary sources:', '',
             '- [Resident settings and serialization](' + base + 'src/CrossPointSettings.cpp), [limits/defaults](' + base + 'src/CrossPointSettings.h), [setting catalog](' + base + 'src/SettingsList.cpp).',
             '- [Status bars](' + base + 'src/util/ReaderStatusBarJson.h), [shortcut ownership](' + base + 'src/QuickActions.h), [library sort IDs](' + base + 'src/activities/library/LibraryActivity.h).',
             '- [Wi-Fi](' + base + 'src/WifiCredentialStore.cpp), [OPDS](' + base + 'src/OpdsServerStore.cpp), [sync](' + base + 'lib/KOReaderSync/KOReaderCredentialStore.cpp), [TTF profiles](' + base + 'src/TtfRenderProfileStore.cpp), [dictionary](' + base + 'src/util/Dictionary.cpp).',
             '- [Pinned board capabilities](https://github.com/Free-Ink/freeink-sdk/blob/699370183fa3a0e33c9cb83a36f701bbb6022095/libs/hardware/BoardConfig/include/BoardConfig.h).', '',
             '## Main settings: `.crosspoint/crossink-settings.json`', '',
             '148 controls, including structured status-bar/shortcut slots. Availability follows the selected model, not detected hardware. Existing unsupported values are preserved; they are not silently clamped.',
             'Choice IDs below are actual stored values, not picker indexes. Reading-stat shortcuts/sleep choices are also unavailable when tracking is disabled.', '',
             '| Stored key | Control | Editable models | Accepted values | Source |', '| --- | --- | --- | --- | --- |']
    models = {m: {f['key']: f for f in schema.main_fields(m, {})} for m in schema.MODELS}
    for key, field in models['X3'].items():
        variants = [(m, rows[key]) for m, rows in models.items() if not rows[key].get('readonly')]
        available = ', '.join(m for m, _ in variants) or 'Read only for this profile'
        lines.append('| `' + key + '` | ' + cell(field['label']) + ' | ' + available + ' | ' + field_type(field, variants) + ' | [definition](' + base + SOURCE_LINES[key.split('.')[0]][0] + '#L' + str(SOURCE_LINES[key.split('.')[0]][1]) + ') |')
    lines += ['', '## Other stores', '',
              'All paths below are inside `.crosspoint/`. `*.enabled` and `*.clearPassword` are app controls, not serialized keys. Collection indexes compact after removal; review includes shifted entries.', '']
    for store in ('wifi', 'opds', 'koreader', 'ttf', 'dictionary'):
        filename, label = schema.STORES[store]
        lines += ['### ' + label + ': `' + filename + '`', '', '| Stored path / app control | Meaning | Accepted values |', '| --- | --- | --- |']
        for field in schema.store_fields(store, 'X3', {}):
            parts = field['key'].split('.')
            if len(parts) == 3:
                if parts[1] != '0': continue
                parts[1] = '*'
            lines.append('| `' + '.'.join(parts) + '` | ' + cell(field['label']) + ' | ' + field_type(field, [(m, field) for m in schema.MODELS]) + ' |')
    lines += ['', '## Preservation and dependent behavior', '',
              '- A persisted control can be inactive in the current context: swapLibraryFileBrowser applies only to Minimal/Dashboard themes, reader-specific front-button maps require readerFrontButtonsEnabled, and format-specific rendering choices only affect relevant books. Successful file readback does not prove the current screen will visibly change.',
              '- Main settings use numeric 0/1; sync metadata and TTF stem darkening use JSON booleans. Front-button maps must be permutations; nonempty two-finger swipe actions must be unique. Enabled frontlight schedules need two different valid times.',
              '- Built-in font selection takes effect only when sdFontFamilyName is empty. A nonempty SD family wins; InkKit labels that priority and does not silently clear it. Clear the SD family explicitly to return to the selected built-in font.',
              '- Conditional defaults follow the firmware loader: previous-page gesture can inherit next-page gesture; legacy dark-mode/clock/browser keys and the Minimal theme can supply missing modern values. Missing displayStatusBar keeps its battery slot regardless of the battery-percentage preference. These effective values are not automatically written.',
              '- Quick Actions has one owner. Choosing a trigger resets competing shortcut mappings, and every resulting change appears in review.',
              '- Existing obfuscated passwords stay byte-for-byte opaque. Blank password input keeps the old password; Clear removes it. New passwords use the firmware-supported plaintext fallback after per-write consent; this is not encryption. Any rewritten or restored file that contains plaintext also requires consent. Firmware must load and successfully resave the relevant store; boot alone is not a guarantee. Private backups can retain plaintext.',
              '- Wi-Fi supports at most 8 entries, with 32-byte SSIDs and 64-byte passwords. Renaming/removing the last-connected SSID clears its stale marker; InkKit does not claim a successful connection.',
              '- OPDS supports 8 servers. Name/username limits (255 bytes), URL/password limits (2048 bytes), and dictionary path limit (1023 bytes) are conservative app limits. New server URLs need HTTP(S) and cannot contain embedded credentials. This app does not test connectivity.',
              '- Existing sync `cfgVersion` and absent/default `serverUrl` semantics are preserved. Pre-v2 accounts with no URL keep the legacy server. A fresh empty configuration gets cfgVersion 2; no account creation or progress synchronization runs on the Mac.',
              '- TTF supports 24 profiles. A non-default interpreter requires Native hinting. A profile references an installed SD font family; it does not install or validate the font binary. Built-in scalable reader sizes are 8–22 pt; larger sizes require an installed SD family that provides them. Dictionary size 0 follows the reader. Enter exact installed font-family names; the app does not enumerate/download font assets.',
              '- `dictionary.bin` is a raw UTF-8 base path without the `.idx/.dict/.ifo` extension, not a binary settings structure. Empty selects no global dictionary; selecting a path does not install its files or override per-book selections.',
              '- Unknown fields survive patches. Missing defaults are used only for display. Editing nested bars may materialize the containing structured payload, preserving unknown members. Original files restore as exact bytes; restoring a newly created store removes it.', '',
              '## Serialized fields that are not separate controls', '',
              '| Keys | Handling |', '| --- | --- |',
              '| `statusBarChapterPageCount`, `stablePageNumbers`, `statusBarBookProgressPercentage`, `statusBarTitle`, `statusBarTimeLeft`, `statusBarBattery`, `statusBarBookPercentageFormat`, `statusBarProgressBar`, `statusBarProgressBarThickness`, `xtcStatusBarMode` | Legacy mirrors preserved. Modern readerStatusBars slots/layout control the v1.6.1 bars; missing modern bars are derived from legacy state. |',
              '| `clockHasBeenSynced`, `clockDateHasBeenSynced` | The upstream-exposed sync flag is editable on RTC models, but does not set the hardware clock. The date-sync observation is preserved, not a user control. |',
              '| `tiltPageTurnDirectionSchema`, `readerStatusBars.version` | Format metadata. New direction edits use schema 2. Existing older direction schemas block that control until firmware migration. |',
              '| `dictionaryFontPointSize` | In-memory C++ member serialized as dictionaryFontSize; not an extra JSON key. |',
              '| `password_obf`, `lastConnectedSsid`, `cfgVersion` | Credential/status/format metadata; preserved or updated only by the explicit rules above. Saved password material is redacted from UI/helper state and diffs; private file backups retain original credential bytes. |', '',
              '## Outside offline global configuration', '',
              'RTC time-setting, tilt calibration, immediate frontlight switching, scanning/joining Wi-Fi, account login, sync, hotspot/web server, library reindexing, statistics backup execution, font/dictionary installation, reading progress, per-book metadata/dictionaries and firmware updates are runtime actions or separate assets/state. A shortcut can be configured to invoke supported actions on the reader; the Mac app does not execute them or modify their binary state.', '',
              'Legacy aliases, malformed types/layouts and firmware recovery `.tmp`/`.bak` files block editing. Unsupported firmware versions need a new reviewed profile. No cross-model conversion or guarantee of identical behavior on untested devices is claimed.', '']
    return '\n'.join(lines)


def check(write=False):
    readme = ROOT / 'README.md'
    text = readme.read_text()
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError('README configuration markers are missing or duplicated.')
    before, rest = text.split(START)
    _, after = rest.split(END)
    expected = {readme: before + summary() + after, ROOT / 'docs/configuration-reference.md': reference()}
    stale = []
    for path, content in expected.items():
        if not path.exists() or path.read_text() != content:
            stale.append(str(path.relative_to(ROOT)))
            if write: path.write_text(content, encoding='utf-8')
    return [] if write else stale


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    stale = check(args.write)
    if stale:
        print('Stale configuration documentation: ' + ', '.join(stale))
        return 1
    print('Configuration documentation matches the implemented profile.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
