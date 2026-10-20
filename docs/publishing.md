# Source publication safeguards

Backups are deliberately local beside the script. `.gitignore` excludes the entire
`xteink-x3-backup/` directory, ZIPs, manifests/checksums, restore journals/locks at
every depth, reader data, private settings, credentials, work files, private owner overrides at every depth, one-time setup
requests and original versioned input scripts. It does not untrack
files already committed, encrypt backups or inspect outgoing Git objects.

## Source-only allowlist

`scripts/check_publication.py` adds a separate deny-by-default public path list.
Unknown staged or historical paths are rejected **before their contents are read**.
Only named source, documentation, workflow, hook and artwork files can pass.
`AGENTS.override.md` is explicitly forbidden at every depth, including after a
force-add or a mistaken public-allowlist change.
Symlinks, submodules, unresolved merges, binary/oversized text, common credential
patterns and private home paths are rejected. History checks also inspect commit
messages and require public GitHub noreply author/committer addresses.

This is a bounded privacy guard, not a comprehensive secret scanner. It cannot
recognize every personal name, book title, credential format or disguised value.
Review every change and maintain the allowlist; never add a broad exception to
publish private data. An optional external scanner can supplement this tool.

```bash
python3 scripts/check_publication.py --worktree
python3 scripts/check_publication.py --staged
python3 scripts/check_publication.py --all-history
python3 scripts/check_publication.py --outgoing origin/main
```

- `--worktree` examines Git-known and non-ignored untracked files without walking
  ignored backup directories. A tracked private path still fails.
- `--staged` inspects the entire index's actual Git blobs, not just the latest diff
  or a cleaned working copy. Unchanged but already tracked private files fail too.
- `--all-history` inspects all locally reachable refs and every historical tree,
  including private files that were subsequently removed or renamed.
- `--outgoing BASE_REF` audits the concrete `BASE_REF..HEAD` commit range using
  an explicit, locally available base ref. It complements, not replaces, complete
  reachable-history review. Missing refs/history fail without automatic fetching.
- `--pre-push` reads Git's outgoing-ref stream and audits complete history reachable
  from each outgoing commit. Deletion-only pushes send no file content.

Exit codes: 0 passed; 1 blocked content/path; 2 audit could not complete. Diagnostics
omit unknown filenames, secret values and Git error text. Tests use synthetic data.
History/range audits reject shallow or unavailable Git history with exit code 2;
partial history is not a clean privacy result. The guard never fetches history.
CI checkout supplies full branch/tag history. CI runs after source upload, so it
cannot prevent a first disclosure; local review and hooks must happen beforehand.

## Local hooks and pre-publication review

Install this checkout's hooks with `python3 scripts/install_git_hooks.py`.
Pre-commit audits the full index; pre-push audits outgoing history. Git settings are
local, and an existing custom hooksPath is not overwritten. Hooks are opt-in for
new clones and can be bypassed technically; CI and manual review remain necessary.

Before publishing:

1. Run relevant synthetic tests and the worktree audit.
2. Stage explicitly named reviewed files. Never `git add .` or force-add ignored data.
3. Inspect `git diff --cached`, `git diff --cached --name-only`, `git ls-files` and
   `git diff --cached --check`; run the staged audit.
4. Inspect the configured author/committer identity without automatically changing it.
   Public commits must satisfy the noreply guard. Before a push, review the actual
   outgoing commits/files and destination, run range and history audits, and obtain
   the applicable explicit maintainer approval. A passing guard is not approval.
5. Verify the pushed commit's CI and remote file list. Never upload backups as release
   assets, Actions artifacts, issue attachments or screenshots.

These are maintenance checks, not part of the reader's migration prompts. The CLI
does not run Git or publish anything. See [SECURITY.md](../SECURITY.md) if data was
exposed: removing the latest copy does not remove historical blobs or downloaded copies.

## Source archives and unsupported packaging

`.gitattributes` marks root/nested private overrides, setup requests, backup and
private/work directories and recovery sidecars at every depth `export-ignore`.
Git source archives include tracked content only; these rules add a second boundary even if private material is
accidentally tracked. Index/history guards must still reject such a repository;
archive exclusion does not remediate a historical disclosure.

This project has no wheel/package, Docker image, frontend build or automatic release
publisher. Do not add one under a local instruction-setup task. Arbitrary recursive
ZIP commands, screenshots, logs and attachments do not honor Git export rules; keep
private guidance and data out of them explicitly. Supported source exports must use
reviewed Git content, never a whole private checkout. Privacy regression tests use
invented root/nested instructions in disposable repositories only.
