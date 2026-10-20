# Source publication safeguards

Backups are deliberately local beside the script. `.gitignore` excludes the entire
`xteink-x3-backup/` directory, ZIPs, manifests/checksums, reader data, private settings,
credentials, work files and original versioned input scripts. It does not untrack
files already committed, encrypt backups or inspect outgoing Git objects.

## Source-only allowlist

`scripts/check_publication.py` adds a separate deny-by-default public path list.
Unknown staged or historical paths are rejected **before their contents are read**.
Only named source, documentation, workflow, hook and artwork files can pass.
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
```

- `--worktree` examines Git-known and non-ignored untracked files without walking
  ignored backup directories. A tracked private path still fails.
- `--staged` inspects the entire index's actual Git blobs, not just the latest diff
  or a cleaned working copy. Unchanged but already tracked private files fail too.
- `--all-history` inspects all locally reachable refs and every historical tree,
  including private files that were subsequently removed or renamed.
- `--pre-push` reads Git's outgoing-ref stream and audits complete history reachable
  from each outgoing commit. Deletion-only pushes send no file content.

Exit codes: 0 passed; 1 blocked content/path; 2 audit could not complete. Diagnostics
omit unknown filenames, secret values and Git error text. Tests use synthetic data.
CI fetches full branch/tag history so its audits are not limited to a shallow checkout.

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
4. Commit with a GitHub noreply identity. Run the history audit before pushing.
5. Verify the pushed commit's CI and remote file list. Never upload backups as release
   assets, Actions artifacts, issue attachments or screenshots.

These are maintenance checks, not part of the reader's migration prompts. The CLI
does not run Git or publish anything. See [SECURITY.md](../SECURITY.md) if data was
exposed: removing the latest copy does not remove historical blobs or downloaded copies.
