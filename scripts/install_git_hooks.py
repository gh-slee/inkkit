#!/usr/bin/env python3
"""Install the project's privacy hooks only in this checkout's Git configuration."""
from pathlib import Path
import subprocess


def main():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'],
                   check=True, capture_output=True)
    result = subprocess.run(['git', '-C', str(root), 'config', '--local', '--get', 'core.hooksPath'],
                            capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise SystemExit('Unable to read local hook configuration.')
    if result.stdout.strip() not in ('', '.githooks'):
        raise SystemExit('A custom local hooksPath exists; inspect it before installing these hooks.')
    for name in ('pre-commit', 'pre-push'):
        path = root / '.githooks' / name
        path.chmod(path.stat().st_mode | 0o111)
    subprocess.run(['git', '-C', str(root), 'config', '--local', 'core.hooksPath', '.githooks'], check=True)
    print('Repository-local privacy hooks enabled. No global Git settings changed.')


if __name__ == '__main__':
    main()
