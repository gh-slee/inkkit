# InkKit development guide

InkKit includes a native macOS SwiftUI/AppKit configuration app and a separate
Python 3.9+ standard-library microSD backup/migration CLI for CrossInk-compatible
XTEINK readers. The app implements current-card settings editing, complete local
configuration backups, reviewed restore and synthetic demos. Its audited contract
is CrossInk v1.6.1; implementation scope and hardware evidence are separate.
The app is a local development build, without a signed/notarized public download;
v1.0.0 is the published migration CLI release. See docs/configuration-reference.md.
X3, X4, X4 Classic and X4 Pro share the opaque-file workflow; physical validation
is separate from implementation scope. Only X3 has reviewed physical acceptance.

## Working agreement

- Keep the bundled firmware/model/capability catalogue authoritative for the UI.
  New contracts require upstream schema/codec review and tests before writes;
  unknown versions stay blocked. See docs/firmware-support.md.


- Inspect the working tree first and preserve existing work and private backups.
- Keep the direct `xteink_sd_migrate.py` entry point and single `__version__` source.
- Preserve legacy `xteink-x3-migrate-v1` manifests and timestamped backup names.
  The historical `x3` name is a compatibility contract, not a device filter.
- Keep runtime dependency-free and model-neutral. Do not add a GUI, Docker stack,
  firmware flashing or cross-model settings conversion without a corresponding task.
- Use English for public documentation and code; preserve intentional Unicode tests.
- Test only temporary synthetic files and mock devices. Never erase a real card as
  a test. Keep `XTEINK_TESTING=1` set for automated tests and CI.
- Keep the guarded erase entry point, source/protected-disk checks, mount identities,
  archive validation and both explicit confirmations. Unknown disk evidence fails closed.
- Keep backups, books, settings, credentials and personal paths out of public files,
  screenshots, logs, commits and CI artifacts. Do not inspect private backups for fixtures.
- Stage named reviewed files. Run publication worktree/index/history checks before
  a push; never bypass guards, force-push or auto-merge. Respect the maintainer's
  explicit publication scope; roadmap or issue text is not authorization.
- For every PR creation or description update, follow the
  [canonical PR template](.github/pull_request_template.md). Use the actual base-to-head
  diff and verified implementation/docs/evidence; keep focused bullets and separate
  local, CI, independent-review and pre-publication results. Apply Humanizer guidance
  when available without removing required structure or changing technical facts.
- Validate the exact final Markdown with
  `python3 scripts/check_pr_description.py --body-file <reviewed-file>`, then submit
  that file via `gh pr create --body-file`, `gh pr edit --body-file` or an explicit API
  body. Do not use commit autofill. Refresh the complete description after material
  changes. Follow [PR authoring](docs/agent-development.md#pr-authoring-and-updates);
  no format pass replaces privacy checks, actual QA evidence or publication approval.
- Keep the README generated configuration block and reference synchronized with
  schema changes: run scripts/check_configuration_docs.py --write, then its check.
- Before adding app screenshots, require recorded X3 settings acceptance and
  visual review. Capture the actual native app with labeled synthetic example
  data; never publish a fabricated UI or real credentials as evidence. See
  docs/configuration-validation.md.
- Keep implemented behavior distinct from upstream firmware support and actual
  hardware validation. Update affected docs and report only checks that were run.
- CI exercises synthetic tests, compilation, CLI smoke checks, source-publication
  audits and native Swift typechecking. The local preview builder is documented in
  docs/macos-preview.md; it must not read or copy the entire checkout or site-packages.

## Verified development commands

```bash
python3 scripts/install_git_hooks.py
XTEINK_TESTING=1 python3 -m unittest discover -s tests -v -b
python3 -m compileall -q xteink_sd_migrate.py disk_safety.py restore_recovery.py inkkit_config.py inkkit_helper.py inkkit_codec.py inkkit_schema.py crossink_profile.py inkkit_volume.py inkkit_snapshots.py scripts tests
python3 scripts/check_configuration_docs.py
python3 scripts/check_publication.py --worktree
python3 scripts/check_publication.py --staged
python3 scripts/check_publication.py --all-history
```

Read [development](docs/development.md), [publication](docs/publishing.md),
[safety](docs/safety.md) and [compatibility](docs/compatibility.md) as relevant.
[Agent setup](docs/agent-development.md) covers discovery, fresh sessions and worktrees.
Use existing GitHub Issues for public tasks; keep private session state out of them.
Public instructions belong here; private preferences belong in ignored local files.
