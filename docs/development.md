# Development

## Layout and setup

`xteink_sd_migrate.py` is the stable CLI and contains the single `__version__`
constant. `disk_safety.py` holds the fail-closed physical-storage/identity policy.
`restore_recovery.py` manages private local restore journals and per-backup locks.
Tests use the standard library. `scripts/` contains contributor-only publication
helpers and is not imported by the migration runtime. No venv, pip, Node or Docker
is required. No separate lint, type-check or package-build command is configured.

```bash
git clone https://github.com/gh-slee/xteink-sd-migrator.git
cd xteink-sd-migrator
python3 scripts/install_git_hooks.py
XTEINK_TESTING=1 python3 -m unittest discover -s tests -v -b
python3 -m compileall -q xteink_sd_migrate.py disk_safety.py restore_recovery.py scripts tests
python3 xteink_sd_migrate.py --version
python3 xteink_sd_migrate.py --help
```

Use `-p test_safety.py`, `-p test_recovery.py` or `-p test_publication.py` with unittest
discovery for focused work, then run the full suite for code changes. Documentation-only edits need link,
command and publication checks; never run a migration to validate documentation.

## Test contracts

Migration tests use temporary synthetic files, legacy v1 manifests and mocked
`diskutil` calls. Failure cases cover source removal, corrupt/missing backups,
unsafe paths, duplicates, special files, limits, target identity swaps, protected
storage, FAT32 limits, capacity, MBR/filesystem checks and interrupted restore.
`XTEINK_TESTING=1` blocks real calls through the mutation runner; keep it set in CI.
Recovery tests inject mid-file failures, verify read-only modes, match journal/volume
identities, reject conflicting bytes, check lock contention, and retry failed ejects.
All journal and target contents are synthetic. Model-label fixtures verify opaque
file preservation, not hardware support.

Publication tests create independent temporary Git repositories with invented text
and credentials. They verify worktree/index/history audits, forced private staging,
secret patterns, removed historical blobs and hook inputs. They never inspect a
maintainer's backups or change the source repository's Git configuration.

## Git hooks and CI

`python3 scripts/install_git_hooks.py` opts this checkout into `.githooks/` using
local Git configuration. Pre-commit checks the complete staged index. Pre-push
checks every commit reachable from each outgoing ref, including previously deleted
private data. The installer refuses an existing different hooksPath; integrate such
hooks manually after review. To remove only this local setting after review:
`git config --local --unset core.hooksPath`. This does not authorize bypassing a
failed privacy audit.

The macOS matrix keeps Python 3.9 and 3.12 support. Actions are pinned to full commit
IDs, checkout credentials are not persisted, permissions are read-only, full history
is available for audits, and each job has a timeout. The workflow runs publication
worktree/index/history checks, synthetic tests, compilation and CLI smoke checks.
There are no backup uploads or test-artifact uploads. Badge status is tied to `main`.

## Versions and documentation

Use `__version__` as the software version source and record changes in
[CHANGELOG.md](../CHANGELOG.md). Filenames never change with versions. Preserve the
legacy manifest identifier and backup naming. A tag/release must describe actual
validation of its exact commit and distinguish hardware evidence from mocks. Public
releases contain only audited source; never attach private data.

Keep [compatibility](compatibility.md), [safety](safety.md), [recovery](troubleshooting.md)
and [publication](publishing.md) aligned with actual behavior. Shared agent instructions
live in [AGENTS.md](../AGENTS.md); personal session state stays private and ignored.

## Agent setup and local-only maintenance

Follow [agent development](agent-development.md) for native discovery, ignored private
overrides, instruction-size budgets, worktrees and a copyable fresh-session probe.
Public clones run without private guidance. Do not copy personal language preferences,
private paths or session state into shared files. A setup task does not itself
permit publication, releases, deployment or real-data migration.

Preserve the observed branch/checkout and unrelated changes. Local setup patches may
remain unstaged and uncommitted for review; do not manufacture a release/version bump
or create a new public roadmap for instruction maintenance. Use the existing Issues
tracker for substantive public tasks with explicit acceptance conditions. Record
local verification privately and distinguish local checks from pushed CI results.
