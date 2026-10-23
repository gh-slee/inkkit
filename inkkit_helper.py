"""One bounded JSON request per process, over stdin/stdout. Allowlisted card settings and synthetic tests only."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import inkkit_config as config

PROTOCOL = 2


def dispatch(request):
    if type(request.get('protocol')) is not int or request['protocol'] != PROTOCOL:
        raise config.ConfigError('protocol', 'This helper protocol version is unsupported.')
    action = request.get('action')
    required = {
        'demo.create': set(), 'volume.open': {'root', 'model', 'firmware', 'confirmed'},
        'volume.eject': {'root'}, 'volume.backup_location': {'root'},
        'config.read': {'root'}, 'config.preview': {'root', 'expected', 'changes'},
        'config.apply': {'root', 'expected', 'changes'}, 'backups.list': {'root'},
        'config.restore_preview': {'root', 'expected', 'backup_id'},
        'config.restore': {'root', 'expected', 'backup_id'},
    }
    optional = {'demo.create': {'model'}, 'config.apply': {'store', 'allow_plaintext'},
                'config.restore': {'store', 'allow_plaintext'}}
    if type(action) is not str or action not in required:
        raise config.ConfigError('request', 'The helper action is unsupported.')
    extras = optional.get(action, {'store'} if action.startswith('config.') or action == 'backups.list' else set())
    keys = set(request) - {'protocol', 'action'}
    if not required[action] <= keys or keys - required[action] - extras:
        raise config.ConfigError('request', 'The helper request fields are unsupported.')
    if 'root' in request and (type(request['root']) is not str or len(request['root']) > 4096):
        raise config.ConfigError('request', 'The workspace reference is invalid.')
    if action == 'demo.create':
        root = config.create_demo(request.get('model', 'X3'))
        return dict(root=root, snapshot=config.read_settings(root))
    root = request['root']
    if action.startswith('volume.'):
        import inkkit_volume
        if action == 'volume.open':
            root = inkkit_volume.open_card(root, request['model'], request['firmware'], request['confirmed'])
            return dict(root=root, snapshot=config.read_settings(root))
        if action == 'volume.eject':
            return inkkit_volume.eject_card(root)
        return dict(path=inkkit_volume.backup_location(root))
    store = request.get('store', 'settings')
    if type(store) is not str or store not in config.schema.STORES:
        raise config.ConfigError('store', 'Choose a supported configuration category.')
    if action == 'config.read':
        return config.read_settings(root, store)
    if action == 'backups.list':
        return config.list_backups(root, store)
    if action == 'config.preview':
        return config.preview_plan(root, request['expected'], request['changes'], store)
    if action == 'config.apply':
        return config.apply_changes(root, request['expected'], request['changes'], store,
                                    allow_plaintext=request.get('allow_plaintext', False))
    if action == 'config.restore_preview':
        return dict(differences=config.preview_restore(root, request['expected'], request['backup_id'], store),
                    requires_plaintext=config.restore_requires_plaintext(root, request['expected'], request['backup_id'], store))
    return config.restore_backup(root, request['expected'], request['backup_id'], store,
                                 allow_plaintext=request.get('allow_plaintext', False))


def self_test():
    """Bundled-runtime integration check; temporary synthetic files only."""
    root = config.create_demo()
    try:
        before = config.read_settings(root)
        differences = config.preview_changes(root, before['token'], {'lineHeightPercent': 115})
        result = config.apply_changes(root, before['token'], {'lineHeightPercent': 115})
        restored = config.restore_backup(root, result['snapshot']['token'], result['backup_id'])
        if restored['snapshot']['values'] != before['values']:
            raise config.ConfigError('self_test', 'The synthetic roundtrip failed.')
        stores = []
        for store, changes in (
                ('wifi', {'credentials.0.enabled': 1, 'credentials.0.ssid': 'Example network', 'credentials.0.password': 'example-selftest-password'}),
                ('opds', {'servers.0.enabled': 1, 'servers.0.name': 'Example catalog', 'servers.0.url': 'https://example.org/opds'}),
                ('koreader', {'username': 'example-reader', 'sendMetadata': True}),
                ('ttf', {'profiles.0.enabled': 1, 'profiles.0.family': 'Example Serif', 'profiles.0.stemDarkening': True}),
                ('dictionary', {'path': '/dict/example'})):
            original = config.read_settings(root, store)
            config.preview_changes(root, original['token'], changes, store)
            written = config.apply_changes(root, original['token'], changes, store, allow_plaintext=True)
            stores.append(written['snapshot'])
            config.restore_backup(root, written['snapshot']['token'], written['backup_id'], store)
            if config.read_settings(root, store)['token']['file'] is not None:
                raise config.ConfigError('self_test', 'A newly created synthetic store did not restore its absent state.')
        return dict(synthetic_roundtrip=True, store_snapshots=stores, snapshot=before, differences=differences,
                    profile=config.PROFILE, python=sys.version.split()[0],
                    prefix=sys.prefix, isolated_site=('site' not in sys.modules),
                    runtime_paths_contained=all(Path(sys.prefix).resolve().parent == Path(path).resolve()
                                                or Path(sys.prefix).resolve().parent in Path(path).resolve().parents
                                                for path in sys.path if path))
    finally:
        # Root was created locally above; never accept a cleanup path from a request.
        shutil.rmtree(root)


def main(argv=None):
    try:
        argv = sys.argv[1:] if argv is None else argv
        if argv == ['--self-test']:
            data = self_test()
        elif argv:
            raise config.ConfigError('request', 'Use a JSON request on stdin.')
        else:
            data = dispatch(config.parse_object(sys.stdin.buffer.read(config.MAX_BYTES + 1)))
        response = dict(protocol=PROTOCOL, ok=True, data=data)
        status = 0
    except config.ConfigError as error:
        response = dict(protocol=PROTOCOL, ok=False, error=dict(code=error.code, message=str(error)))
        status = 1
    except Exception:
        response = dict(protocol=PROTOCOL, ok=False, error=dict(code='io_error', message='The operation failed. Reopen the card or demo and review its backups.'))
        status = 1
    print(json.dumps(response, ensure_ascii=True, allow_nan=False))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
