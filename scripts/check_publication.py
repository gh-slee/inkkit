#!/usr/bin/env python3
"""Audit public source, the full index, and reachable history without reading backups."""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

PUBLIC_PATHS = {
    '.gitignore', 'README.md', 'LICENSE', 'CONTRIBUTING.md', 'SECURITY.md',
    'AGENTS.md', 'CHANGELOG.md', 'xteink_sd_migrate.py', 'disk_safety.py',
    '.github/workflows/tests.yml', '.github/ISSUE_TEMPLATE/bug_report.md',
    '.github/pull_request_template.md', '.githooks/pre-commit', '.githooks/pre-push',
    'docs/safety.md', 'docs/troubleshooting.md', 'docs/compatibility.md',
    'docs/development.md', 'docs/publishing.md',
    'assets/readme/xteink-mark.svg', 'assets/readme/README.md',
    'scripts/check_publication.py', 'scripts/install_git_hooks.py',
    'tests/test_xteink_sd_migrate.py', 'tests/test_safety.py', 'tests/test_publication.py',
}
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
        commits = git(root, 'rev-list', *(revisions or ['--all', 'HEAD'])).decode().splitlines()
        if not commits:
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
    modes.add_argument('--pre-push', action='store_true')
    args = parser.parse_args(argv)
    try:
        revisions = None
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
        mode = 'worktree' if args.worktree else 'staged' if args.staged else 'history'
        count, errors = audit(args.root, mode, revisions)
        if errors:
            for error in errors:
                print('BLOCKED: ' + error, file=sys.stderr)
            return 1
        print(f'Publication audit PASS: {count} public file revisions checked ({mode}).')
        return 0
    except (AuditError, OSError, ValueError):
        print('Publication audit could not complete; private details withheld.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
