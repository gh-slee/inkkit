#!/usr/bin/env python3
"""Summarize CrossInk release storage evidence from a local git checkout.

A maintainer review aid, not a schema generator. It reads tags with read-only
git commands and never fetches, checks out or builds anything. The settings-key
list is a text heuristic over the settings sources; review the actual loaders,
serializers and board definitions before changing crossink_contracts.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

STORE_PATH = re.compile(r'"/\.crosspoint/([A-Za-z0-9_.\-]+)"')
DOC_KEY = re.compile(r'doc\["([A-Za-z0-9_]+)"\]')
LIST_KEY = re.compile(r'"([a-z][A-Za-z0-9]+)"')
ENV = re.compile(r'^\[env:([A-Za-z0-9_.\-]+)\]', re.M)
STORE_SOURCE = re.compile(r'(Store|Settings|State|Dictionary|KOReader)[A-Za-z]*\.(cpp|h)$')
SETTINGS_SOURCES = ('src/SettingsList.cpp', 'src/SettingsList.h', 'src/CrossPointSettings.cpp')
SDK_PATH = 'freeink-sdk'


def git(repo: Path, *args: str) -> str | None:
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def stable_tags(repo: Path) -> list[str]:
    tags = (git(repo, 'tag', '--sort=creatordate') or '').split()
    return [tag for tag in tags if re.fullmatch(r'v\d+(\.\d+)*', tag)]


def describe(repo: Path, tag: str) -> dict:
    commit = git(repo, 'rev-list', '-n1', tag)
    if commit is None:
        raise ValueError('Unknown tag: ' + tag)
    files = (git(repo, 'ls-tree', '-r', '--name-only', tag, 'src', 'lib') or '').split()
    stores = set()
    for name in files:
        if STORE_SOURCE.search(name):
            stores.update(STORE_PATH.findall(git(repo, 'show', tag + ':' + name) or ''))
    keys = set()
    for name in SETTINGS_SOURCES:
        text = git(repo, 'show', tag + ':' + name) or ''
        keys.update(DOC_KEY.findall(text))
        if 'SettingsList' in name:
            keys.update(LIST_KEY.findall(text))
    sdk = (git(repo, 'ls-tree', tag, SDK_PATH) or '').split()
    return dict(tag=tag, firmware=tag[1:], commit=commit.strip(),
                sdk=sdk[2] if len(sdk) > 2 and sdk[1] == 'commit' else '',
                stores=sorted(stores), settings_keys=sorted(keys),
                build_environments=sorted(ENV.findall(git(repo, 'show', tag + ':platformio.ini') or '')))


def compare(before: dict, after: dict) -> dict:
    result = dict(tag=after['tag'], since=before['tag'])
    for field in ('stores', 'settings_keys', 'build_environments'):
        added = sorted(set(after[field]) - set(before[field]))
        removed = sorted(set(before[field]) - set(after[field]))
        if added or removed:
            result[field] = dict(added=added, removed=removed)
    if after['sdk'] != before['sdk']:
        result['sdk'] = dict(before=before['sdk'], after=after['sdk'])
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--repo', required=True, type=Path, help='local CrossInk checkout with tags')
    parser.add_argument('tags', nargs='*', help='release tags (default: every stable vX.Y tag)')
    parser.add_argument('--compare', action='store_true', help='report changes between consecutive tags')
    args = parser.parse_args(argv)
    if git(args.repo, 'rev-parse', '--git-dir') is None:
        print('Not a git checkout: ' + str(args.repo), file=sys.stderr)
        return 2
    try:
        releases = [describe(args.repo, tag) for tag in args.tags or stable_tags(args.repo)]
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    if args.compare:
        output = [dict(releases[0], change='baseline')] if releases else []
        output += [compare(a, b) for a, b in zip(releases, releases[1:])]
    else:
        output = releases
    json.dump(output, sys.stdout, indent=1)
    print()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
