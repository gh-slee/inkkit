"""One bounded JSON request per process, over stdin/stdout. No real-card actions."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import inkkit_config as config

PROTOCOL = 1


def dispatch(request):
    if type(request.get('protocol')) is not int or request['protocol'] != PROTOCOL:
        raise config.ConfigError('protocol', 'This helper protocol version is unsupported.')
    action = request.get('action')
    keys = {
        'demo.create': set(),
        'config.read': {'root'},
        'config.preview': {'root', 'expected', 'changes'},
        'config.apply': {'root', 'expected', 'changes'},
        'backups.list': {'root'},
        'config.restore_preview': {'root', 'expected', 'backup_id'},
        'config.restore': {'root', 'expected', 'backup_id'},
    }
    if type(action) is not str or action not in keys or set(request) != keys[action] | {'protocol', 'action'}:
        raise config.ConfigError('request', 'The helper action or request fields are unsupported.')
    if 'root' in request and (type(request['root']) is not str or len(request['root']) > 4096):
        raise config.ConfigError('request', 'The workspace reference is invalid.')
    if action == 'demo.create':
        root = config.create_demo()
        return dict(root=root, snapshot=config.read_settings(root))
    root = request['root']
    if action == 'config.read':
        return config.read_settings(root)
    if action == 'backups.list':
        return config.list_backups(root)
    if action == 'config.preview':
        return config.preview_changes(root, request['expected'], request['changes'])
    if action == 'config.apply':
        return config.apply_changes(root, request['expected'], request['changes'])
    if action == 'config.restore_preview':
        return config.preview_restore(root, request['expected'], request['backup_id'])
    return config.restore_backup(root, request['expected'], request['backup_id'])


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
        return dict(synthetic_roundtrip=True, snapshot=before, differences=differences,
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
        response = dict(protocol=PROTOCOL, ok=False, error=dict(code='io_error', message='The operation failed. Reload the synthetic workspace and review its backups.'))
        status = 1
    print(json.dumps(response, ensure_ascii=True, allow_nan=False))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
