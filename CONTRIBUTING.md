# Contributing

Contributions are welcome for safe disk detection, archive/integrity regressions,
compatibility reports and clear documentation. Discuss changes to erasure policy,
backup schemas or firmware assumptions before implementation.

## Development setup

Clone the repository and use Python 3.9+ on macOS. No package install or virtual
environment is required; there are no third-party runtime or test dependencies.

```bash
python3 scripts/install_git_hooks.py
XTEINK_TESTING=1 python3 -m unittest discover -s tests -v -b
python3 -m compileall -q xteink_sd_migrate.py disk_safety.py scripts tests
```

Hook installation changes only this checkout's `core.hooksPath` and refuses to
silently replace an existing custom path. See [development](docs/development.md).

## Change expectations

- Follow [AGENTS.md](AGENTS.md); keep canonical documentation and code in English.
- Preserve the stable filename, single version source, stdlib-only operation,
  existing migration behavior and legacy manifests/backups.
- Treat reader data as opaque bytes; keep the workflow model-independent.
  X4 support does not establish a tested X4 migration. Update
  [compatibility evidence](docs/compatibility.md) only with actual results.
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
history guard checks it without printing private identities.

Additional public files require a reviewed addition to the publication allowlist.
Keep `scripts/check_publication.py`, its tests and affected docs aligned. Pattern
checks do not replace manual inspection. Report real hardware evidence separately
from synthetic tests, and sanitize reports using the issue template.

Code, documentation and artwork contributions must be compatible with the MIT license.
