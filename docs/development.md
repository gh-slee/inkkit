# Development

## Layout and setup

InkKit is the project name; `xteink_sd_migrate.py` remains the stable migration entry
point. Development source adds a six-store native current-card configuration app
and synthetic demos, with selected owner-reported X3 settings acceptance; see
[macOS preview](macos-preview.md) and [configuration architecture](config-architecture.md).

`xteink_sd_migrate.py` is the stable CLI and contains the single `__version__`
constant. `disk_safety.py` holds the fail-closed physical-storage/identity policy.
`restore_recovery.py` manages private local restore journals and per-backup locks.
`inkkit_snapshots.py` implements complete six-store configuration snapshots, reviewed
restore journals, deletion protection and legacy backup compatibility.
Tests use the standard library. `scripts/` contains contributor-only publication
and preview-build helpers and is not imported by the migration runtime. No venv, pip, Node or Docker
is required for the migration CLI. Native preview development additionally needs
Swift tools and, for bundling, a local python.org CPython 3.12 framework.

```bash
git clone https://github.com/gh-slee/inkkit.git
cd inkkit
python3 scripts/install_git_hooks.py
XTEINK_TESTING=1 python3 -m unittest discover -s tests -v -b
python3 -m compileall -q xteink_sd_migrate.py disk_safety.py restore_recovery.py inkkit_config.py inkkit_helper.py inkkit_codec.py inkkit_schema.py crossink_profile.py inkkit_volume.py inkkit_snapshots.py scripts tests
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
Persistence fault tests exercise actual temporary-file writes with injected journal
ENOSPC/fsync/rename failures, mid-target-write ENOSPC and target sync errors. They
reload the retained journal and retry, checking full hashes and complete-file
identities/timestamps. Ctrl-C releases the per-backup lock for a later retry;
checkpoint or cleanup failures retain recovery evidence. All failures are synthetic.
All journal and target contents are synthetic. Model-label fixtures verify opaque
file preservation, not hardware support.
ZIP64 regressions use tiny archives and lowered resource limits to check the exact
end record selected by the standard library, including non-sentinel legacy fields,
misdirected locators, invalid metadata and maximum-length comments. Malformed
root-dot file fixtures must fail before disk queries or erase. No large allocation
or physical device is needed to exercise these boundaries.

[Hardware acceptance](hardware-validation.md) is a separate evidence review. Adding
a report or checklist does not authorize a real-card test; automated tests and CI
continue to use synthetic data only. Never inject faults on physical reader media.

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
The Python 3.12 job also typechecks the native SwiftUI source. CI does not package,
sign, notarize or publish an app. There are no backup uploads or test-artifact
uploads. Badge status is tied to `main`.

## PR-description checks

The [canonical template](../.github/pull_request_template.md) and
[authoring guide](agent-development.md#pr-authoring-and-updates) cover creation and
updates. Validate the exact Markdown before sending it with the GitHub CLI/API:

```bash
python3 scripts/check_pr_description.py --body-file work/pr-body.md
XTEINK_TESTING=1 python3 -m unittest discover -s tests -p 'test_pr_description.py' -v
```

The separate `.github/workflows/pr-description.yml` workflow runs on PR open,
reopen, synchronize and edited events. It uses read-only permissions and pinned
Actions, and passes only the trusted event-file path to the checker; PR text is
never shell code. It adds no packages or application dependencies. Existing macOS
unit/Swift/publication jobs retain their current triggers and behavior.

The checker covers required headings/order, summary/file bullets, four evidence
statuses and bounded privacy patterns. Synthetic regressions exercise malformed
bodies/events, fake headings, explicit gaps, secret redaction and event injection.
It cannot certify factual accuracy, independent QA, prose quality or owner consent.
These development-only checks use synthetic Markdown/events and require no real
card or app rebuild.

## Versions and documentation

Use `__version__` as the software version source and record changes in
[CHANGELOG.md](../CHANGELOG.md). Filenames never change with versions. Preserve the
legacy manifest identifier and backup naming. A tag/release must describe actual
validation of its exact commit and distinguish hardware evidence from mocks. Public
releases contain only audited source; never attach private data.

Before a prerelease, follow the [manual preparation steps](publishing.md#manual-prerelease-preparation).
Run the existing workflow on the exact main commit if its push run is unavailable:
`gh workflow run tests.yml --ref main`. This executes the synthetic test matrix;
it does not publish a release. Record the run's head SHA, event, per-job test counts
and completed conclusions. A queued/running job is not a passing matrix, and a run
for an earlier commit is not validation of a new candidate.

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

## Configuration coverage maintenance

After changing field/storage/model metadata, run
`python3 scripts/check_configuration_docs.py --write` and review the README block
and full reference. CI runs the same generator in check mode and rejects drift.
This prevents internal documentation drift, not unreviewed upstream changes:
a new firmware release still needs a pinned source/schema audit and new fixtures.
Update behavior/usage/security docs alongside implementation. When product scope
changes, also review PRODUCT, contributor instructions and GitHub's About/topics:
repository metadata is stored separately and does not change when a README PR
merges. Keep historical release pages accurate for their tagged code rather than
assigning unreleased app features to a CLI release. New profile tests
exercise every editable main control and every enum choice per model, synthetic
store CRUD/recovery, credential redaction/consent and mocked card-session guards.

The configuration reference links every main storage root to its pinned upstream
definition/serializer. When changing the firmware profile, re-audit both save and
load behavior, including conditional defaults; tests generated from the same schema
cannot independently prove that the schema matches firmware. See the dated
[source audit and acceptance gates](configuration-validation.md).
