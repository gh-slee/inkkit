#!/usr/bin/env python3
"""Audit public source, the full index, and reachable history without reading backups."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

PUBLIC_PATHS = {
    '.gitignore', '.gitattributes', 'README.md', 'LICENSE', 'CONTRIBUTING.md', 'SECURITY.md',
    'AGENTS.md', 'CHANGELOG.md', 'xteink_sd_migrate.py', 'disk_safety.py', 'restore_recovery.py',
    '.github/workflows/tests.yml', '.github/ISSUE_TEMPLATE/bug_report.md',
    '.github/ISSUE_TEMPLATE/hardware_report.md', 'docs/hardware-validation.md',
    '.github/pull_request_template.md', '.githooks/pre-commit', '.githooks/pre-push',
    'docs/safety.md', 'docs/troubleshooting.md', 'docs/compatibility.md',
    'docs/development.md', 'docs/publishing.md', 'docs/agent-development.md',
    'assets/readme/xteink-mark.svg', 'assets/readme/README.md',
    'scripts/check_publication.py', 'scripts/install_git_hooks.py',
    'scripts/check_pr_description.py', 'tests/test_pr_description.py',
    '.github/workflows/pr-description.yml',
    'tests/test_xteink_sd_migrate.py', 'tests/test_safety.py', 'tests/test_publication.py',
    'tests/test_recovery.py',
    'inkkit_config.py', 'inkkit_helper.py', 'macos/InkKitApp.swift', 'macos/Info.plist',
    'scripts/build_macos_preview.py', 'tests/test_config.py', 'tests/test_helper.py',
    'tests/test_macos_build.py', 'PRODUCT.md', 'DESIGN.md',
    'docs/macos-preview.md', 'docs/config-architecture.md',
    'crossink_profile.py', 'inkkit_schema.py', 'inkkit_codec.py', 'inkkit_volume.py',
    'tests/test_config_stores.py', 'tests/test_config_volume.py',
    'scripts/check_configuration_docs.py', 'docs/configuration-reference.md',
    'docs/configuration-validation.md', 'inkkit_snapshots.py', 'tests/test_snapshots.py', 'docs/firmware-support.md',
}
# Exact native captures reviewed with synthetic data only. Keep prior approved
# hashes when replacing an image so reachable history remains auditable. This is
# not a general binary exception; changed bytes need a new image/privacy review.
APPROVED_IMAGES = {
    'assets/macos/backups.jpg': frozenset({'13a614a3cd7df5bd5afaece5d82343169a9455c00261171939930fb8f0627f7a'}),
    'assets/macos/controls.jpg': frozenset({'64b5457788a5215260e584c05414413e3ff20a9542e6e41c4ef56c26ba0dcd91'}),
    'assets/macos/delete-confirmation.jpg': frozenset({'0f98eac541c93612582a116ffa1fd1bb4702fc2796f10db63fb93092ec8e5e53'}),
    'assets/macos/device.jpg': frozenset({'9b62ad98e371274258c9972d4549cb63789a8c9303115589fe4af1a822742508'}),
    'assets/macos/dictionary.jpg': frozenset({'e810b86cead6cd6fb9b8c58c4eb837dc3c8c993c562a53b628894249df30a75e'}),
    'assets/macos/display.jpg': frozenset({'01be76581474b52382a1120214c98482f2dd98b346cdbb82e5ca848a167b4032'}),
    'assets/macos/font-rendering.jpg': frozenset({'22a40f565f76234d3a167cb6502885485a4c25c62fddbed03b2da336c7e53c37'}),
    'assets/macos/frontlight-pro.jpg': frozenset({'fc7addf135b580c28ab61c9cf26005312b8a4f996da2803e94ea343e3938542b'}),
    'assets/macos/library.jpg': frozenset({'302a42892bca1e1f9fb8843009dd628cb67f509e19c88d5153dae36ea672468f'}),
    'assets/macos/opds.jpg': frozenset({'309746df032762efcb91a1a74ea93b20255670d0273d7cdcc1fcdb32b350f0bd'}),
    'assets/macos/overview.jpg': frozenset({'cbf22c530d2c5ff42422108dd958b738c6ad2ddb6aebf73baf68dbf14013def0'}),
    'assets/macos/reading-sync.jpg': frozenset({'6f4947c5d144bbc0ef95042ef484ec452554649981d7dc1c2bc9b998464057f2'}),
    'assets/macos/reading.jpg': frozenset({'a42f3edda873ead5bb9857054b8b7d7ded4cec05ab0674e4d58f57d6224831b7'}),
    'assets/macos/review-changes.jpg': frozenset({'7ad57e4871a36d5f3af1a41b3bd7ccd3b45f055046a8b63ef9b45bf2cc7dd45f'}),
    'assets/macos/status-bars.jpg': frozenset({'4e164c9cab2eaaae245d2fd40fe2b368e5be5e37f0fb6bfcc59d3882bbfe4a1c'}),
    'assets/macos/wifi.jpg': frozenset({'7cc681f848a17aa819dc7cc698b852064ef99a8a9a09d8492d8b705ce31b5748'}),
}
PUBLIC_PATHS.update(APPROVED_IMAGES)
PUBLIC_PATHS.update({'assets/macos/README.md', 'docs/screenshots.md'})

MAX_BYTES = 2 * 1024**2
SECRET_PATTERNS = (
    rb'\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b',
    rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    rb'-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----',
    rb'https?://[^\s/:]+:[^\s/@]+@',
    rb'/(?:Users|home)/[A-Za-z0-9_.-]+/',
)
ASSIGNMENT = re.compile(
    rb'''(?im)^\s*["']?(?:password|api_key|access_token|auth_token|client_secret)["']?\s*[:=]\s*["']([^"'\r\n]{8,})["']'''
)


class AuditError(Exception):
    pass


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True)
    if result.returncode:
        raise AuditError('Git audit query failed; details omitted to protect private paths.')
    return result.stdout


def allowed(path):
    # Private guidance is forbidden at every depth, even after an allowlist mistake.
    if PurePosixPath(path).name.casefold() == 'agents.override.md':
        return False
    return path in PUBLIC_PATHS


def content_issues(data):
    if len(data) > MAX_BYTES or b'\0' in data:
        return ['Binary or oversized public source.']
    try:
        data.decode('utf-8')
    except UnicodeError:
        return ['Public source must be UTF-8 text.']
    issues = []
    if any(re.search(pattern, data) for pattern in SECRET_PATTERNS):
        issues.append('Possible credential or private home path; content withheld.')
    for match in ASSIGNMENT.finditer(data):
        if not match[1].lower().startswith((b'example', b'placeholder', b'your_', b'changeme', b'<')):
            issues.append('Possible literal credential assignment; content withheld.')
            break
    return issues


def index_entries(root):
    for row in git(root, 'ls-files', '--stage', '-z').split(b'\0'):
        if row:
            meta, raw_path = row.split(b'\t', 1)
            mode, oid, stage = meta.decode('ascii').split()
            yield raw_path.decode('utf-8', 'surrogateescape'), mode, oid, stage


def tree_entries(root, revision):
    for row in git(root, 'ls-tree', '-r', '-z', revision).split(b'\0'):
        if row:
            meta, raw_path = row.split(b'\t', 1)
            mode, kind, oid = meta.decode('ascii').split()
            yield raw_path.decode('utf-8', 'surrogateescape'), mode, oid, '0'


def inspect_entry(root, path, mode, oid, stage, *, worktree=False):
    # Reject unknown paths before reading any bytes, including force-added backups.
    if not allowed(path):
        return ['Unapproved public path; private filename withheld.']
    if stage != '0' or mode not in ('100644', '100755'):
        return ['Unresolved merge, symlink, submodule, or unsupported file mode.']
    if worktree:
        current = Path(root)
        for component in PurePosixPath(path).parts:
            current = current / component
            if current.is_symlink():
                return ['Public source must not traverse symlinks.']
        if not current.exists():
            return []  # A tracked deletion is harmless in a worktree scan.
        info = current.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            return ['Non-regular or oversized public source.']
        data = current.read_bytes()
    else:
        size = int(git(root, 'cat-file', '-s', oid))
        if size > MAX_BYTES:
            return ['Oversized public Git blob.']
        data = git(root, 'cat-file', 'blob', oid)
    if path in APPROVED_IMAGES:
        if (len(data) > MAX_BYTES or not data.startswith(b'\xff\xd8')
                or not data.endswith(b'\xff\xd9')
                or hashlib.sha256(data).hexdigest() not in APPROVED_IMAGES[path]):
            return ['Native screenshot differs from its reviewed image hash.']
        return []
    return content_issues(data)


def audit(root, mode, revisions=None):
    errors, checked = [], set()
    if mode == 'worktree':
        entries = list(index_entries(root))
        tracked = {e[0] for e in entries}
        for raw in git(root, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0'):
            if raw:
                path = raw.decode('utf-8', 'surrogateescape')
                if path not in tracked:
                    entries.append((path, '100644', '', '0'))
        groups = [entries]
    elif mode == 'staged':
        groups = [list(index_entries(root))]
    else:
        if git(root, 'rev-parse', '--is-shallow-repository').strip() != b'false':
            raise AuditError('History audit cannot complete with shallow or unknown Git history; no clean result.')
        commits = git(root, 'rev-list', *(revisions or ['--all', 'HEAD'])).decode().splitlines()
        if not commits and mode != 'outgoing':
            raise AuditError('No reachable commits to audit.')
        groups = (tree_entries(root, commit) for commit in commits)
        # Author/committer addresses are public too; keep owner metadata private.
        for commit in commits:
            addresses = git(root, 'show', '-s', '--format=%ae%n%ce', commit).decode().splitlines()
            if len(addresses) != 2 or any(not re.fullmatch(
                    r'(?:[0-9]+\+)?[A-Za-z0-9-]+@users\.noreply\.github\.com|noreply@github\.com',
                    address) for address in addresses):
                errors.append('Commit identity uses a non-noreply email; address withheld.')
            errors.extend(content_issues(git(root, 'show', '-s', '--format=%B', commit)))
    for entries in groups:
        for path, file_mode, oid, stage in entries:
            key = (path, file_mode, oid, stage)
            if key in checked:
                continue
            checked.add(key)
            errors.extend(inspect_entry(root, path, file_mode, oid, stage, worktree=mode == 'worktree'))
    return len(checked), sorted(set(errors))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--worktree', action='store_true')
    modes.add_argument('--staged', action='store_true')
    modes.add_argument('--all-history', action='store_true')
    modes.add_argument('--outgoing', metavar='BASE_REF', help='Audit HEAD commits not reachable from an explicit local base ref')
    modes.add_argument('--pre-push', action='store_true')
    args = parser.parse_args(argv)
    try:
        revisions = None
        if args.outgoing:
            def commit_oid(ref):
                value = git(args.root, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()
                if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', value):
                    raise AuditError('Cannot resolve the outgoing range; no clean result.')
                return value
            revisions = [commit_oid('HEAD'), '^' + commit_oid(args.outgoing)]
        if args.pre_push:
            revisions = []
            for line in sys.stdin:
                fields = line.split()
                if len(fields) != 4 or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', fields[1]):
                    raise AuditError('Malformed pre-push input.')
                if set(fields[1]) != {'0'}:
                    revisions.append(fields[1])
            if not revisions:  # Deleting refs sends no source content.
                print('Publication audit PASS: no outgoing source.')
                return 0
        mode = 'worktree' if args.worktree else 'staged' if args.staged else 'outgoing' if args.outgoing else 'history'
        count, errors = audit(args.root, mode, revisions)
        if errors:
            for error in errors:
                print('BLOCKED: ' + error, file=sys.stderr)
            return 1
        print(f'Publication audit PASS: {count} public file revisions checked ({mode}).')
        return 0
    except AuditError as exc:
        print('Publication audit could not complete: ' + str(exc), file=sys.stderr)
        return 2
    except (OSError, ValueError):
        print('Publication audit could not complete; private details withheld.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
