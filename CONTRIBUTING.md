# Contributing

Contributions are welcome for native macOS settings workflows, reviewed CrossInk
profiles, configuration backup/recovery, safe migration, compatibility and docs.
Discuss changes to erasure policy, backup schemas or firmware assumptions before
implementation.

## Development setup

Clone the repository on macOS. The Python core, migration CLI and synthetic tests
use Python 3.9+ and the standard library, without pip packages or a required venv.
The native app uses SwiftUI/AppKit. Its local builder additionally requires Swift
and a macOS 14+ SDK plus the python.org CPython 3.12 framework; see
[app build/use instructions](docs/macos-preview.md). A built app bundles its runtime.

```bash
python3 scripts/install_git_hooks.py
XTEINK_TESTING=1 python3 -m unittest discover -s tests -v -b
python3 -m compileall -q xteink_sd_migrate.py disk_safety.py restore_recovery.py inkkit_config.py inkkit_helper.py inkkit_codec.py inkkit_schema.py crossink_profile.py inkkit_volume.py inkkit_snapshots.py scripts tests
python3 scripts/check_configuration_docs.py
```

For agent discovery, private overrides and fresh sessions, see
[agent development](docs/agent-development.md).

Hook installation changes only this checkout's `core.hooksPath` and refuses to
silently replace an existing custom path. See [development](docs/development.md).

## Change expectations

- Follow [AGENTS.md](AGENTS.md); keep canonical documentation and code in English.
- Preserve the stable filename, single version source, standard-library Python core,
  existing migration behavior and legacy manifests/backups.
- Keep migration model-independent and preserve opaque reader files. Configuration
  editing must use reviewed schema/codec/model contracts, preserve unknown data and
  keep credentials redacted in UI responses. Device scope is not hardware
  certification. Update [compatibility evidence](docs/compatibility.md) only with actual results.
- Use minimal invented fixtures and temporary paths. Never read private backups
  to create tests or format real SD cards during automated validation.
- Safety changes need meaningful negative and failure-injection tests. Keep disk
  mutations in the guarded entry point; never weaken checks just to accept a reader.
- Keep private books/settings, credentials, personal paths and agent session state
  out of source, examples, screenshots, commit messages and Actions artifacts.

## Pull requests and publication

Describe the concrete problem, resulting behavior, validation and limits using the
PR template. Run [publication checks](docs/publishing.md) for the full worktree/index
and reachable history. Stage explicit reviewed paths, not `git add .`. Never force-add
backups. Use your GitHub noreply author/committer address for public commits; the
history guard checks it without printing private identities. Inspect existing
identity settings first; do not change contributor/global identity automatically.
A local setup request does not authorize a push, PR, release or deployment. Guards
check content, not owner consent; confirm the exact publication scope separately.

Additional public files require a reviewed addition to the publication allowlist.
Keep `scripts/check_publication.py`, its tests and affected docs aligned. Pattern
checks do not replace manual inspection. Report real hardware evidence separately
from synthetic tests. Use the [hardware report template](https://github.com/gh-slee/inkkit/issues/new?template=hardware_report.md)
with the [acceptance criteria](docs/hardware-validation.md) for working or partial
configurations, and the bug template for failures. Never submit private raw evidence.

Code, documentation and artwork contributions must be compatible with the MIT license.
