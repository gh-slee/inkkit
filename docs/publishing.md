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
patterns and private home paths are rejected. The only binary exception is the
exact native JPEG paths and reviewed SHA-256 sets in `APPROVED_IMAGES`; modified
image bytes fail closed. Review pixels and metadata before adding a hash, retain
approved historical hashes, and see [screenshot provenance](../assets/macos/README.md).
This is not a general image or binary-file exception. History checks also inspect commit
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

## PR descriptions and explicit submission

Use the [canonical PR template](../.github/pull_request_template.md) and
[authoring workflow](agent-development.md#pr-authoring-and-updates) for every new
PR and description update. Generate the body from the actual full base-to-head
diff, current docs and verified evidence. Group meaningful modules; keep required
sections and separate evidence categories even in a short PR. Conditional risk,
compatibility, visual and Issue sections must reflect the actual change.

Save the complete reviewed Markdown under ignored `work/`, then run:

```bash
python3 scripts/check_pr_description.py --body-file work/pr-body.md
```

Keep local verification distinct from actual push/PR CI, independent reviews and
required InkKit checks. Record unrun/pending/failed checks and skips honestly. Do
not reuse another commit's results as current evidence, invent QA or expose private
backup contents, paths or owner approval records. Humanizer may polish wording;
it cannot remove required structure or alter facts.

After the existing scope/privacy approval, use `gh pr create --body-file` or
`gh pr edit <number> --body-file` with that same file (or an explicit API body).
InkKit has no automatic PR publisher; no commit autofill or implicit template
insertion guarantees compliance. Revalidate the whole body after material changes
and read back remote commit/file/body information. Required pre-PR validation means
InkKit's existing applicable checks and publication audits. The PR-format workflow
adds no packaging or hardware acceptance requirement.

The read-only PR-description workflow checks source and description updates using
its event JSON, without printing the body. Format/pattern checks cannot prove
facts, reviewer independence or publication consent, and run after upload. They
do not authorize a push, merge or release. Repository branch-protection settings
are unchanged; direct manual submission remains the author's responsibility.

## Source archives and local preview packaging

`.gitattributes` marks root/nested private overrides, setup requests, backup and
private/work directories and recovery sidecars at every depth `export-ignore`.
Git source archives include tracked content only; these rules add a second boundary even if private material is
accidentally tracked. Index/history guards must still reject such a repository;
archive exclusion does not remediate a historical disclosure.

This project has no wheel/package, Docker image or automatic release publisher.
The [local macOS preview builder](macos-preview.md) copies named public inputs and
selected standard-library runtime files only; its ad-hoc-signed output is not a
public release. Native build directories, apps and disk images remain ignored and
are not approved source paths. Do not add a publisher under an instruction-setup
task. Arbitrary recursive
ZIP commands, screenshots, logs and attachments do not honor Git export rules; keep
private guidance and data out of them explicitly. Supported source exports must use
reviewed Git content, never a whole private checkout. Privacy regression tests use
invented root/nested instructions in disposable repositories only.

## Manual prerelease preparation

Keep releases separate from source pushes and PR merges. Before creating a beta tag
or release, identify the exact candidate commit and confirm its source tree,
`--version`, changelog and approved release notes agree. Confirm PR integration with
GitHub's explicit merged state and merge commit; a commit title, matching tree or
successful feature CI alone is not proof of PR merge.

Validate the candidate with synthetic tests, compilation, CLI smoke checks and
worktree/index/history publication audits. Inspect a Git source export and run its
CLI from a separate directory, including every runtime helper. Export only reviewed
Git source. GitHub's automatically generated source archives are sufficient for
this dependency-free CLI; do not attach a checkout, backups, logs or private state.

Verify successful macOS/Python 3.9 and 3.12 jobs for the candidate and record the
head SHA, run URL and actual test count. A manual run of the existing test workflow
can supply evidence when no matching push run exists. It does not publish anything
and does not replace validation of a later candidate commit.

Prepare notes describing user-visible changes, legacy backup compatibility,
validation and known recovery/hardware limits. Keep the changelog marked unreleased
while preparing. Obtain explicit approval for the tag name, exact target SHA,
prerelease designation, notes and any assets before publishing. Revalidate the
target SHA and tag availability immediately before the approved operation. A beta
release must be marked prerelease and must not be promoted to stable implicitly.

After publication, verify the tag resolves to the approved commit, release metadata
and source file list match, and no private assets were attached. This is a manual
maintenance procedure; no automatic release workflow is configured.

## Manual stable release preparation

Use the checks above plus the [hardware acceptance gates](hardware-validation.md#review-and-stable-release-criteria)
and [v1 compatibility commitment](compatibility.md#v1-compatibility-commitment).
Only X3 full physical acceptance is required for v1.0.0; X4/other
implementation-compatible readers remain explicitly unvalidated and do not block
that release. The [reviewed X3 result](hardware-validation.md#reviewed-x3-result-2026-10-22)
is tied to its recorded revision, not automatically to the final candidate. Do not
publish stable metadata in advance of reviewed evidence. A documentation merge
alone does not complete hardware acceptance.

1. Select an immutable candidate SHA that includes the reviewed safety fixes. A
   separately approved `v1.0.0-rc.1` prerelease is an optional way to distribute it;
   naming or preparing a candidate does not authorize a tag/release. Record both SHA
   and software version because unreleased main may retain an earlier beta banner.
2. Run synthetic tests, compilation, CLI/version checks, publication audits and an
   isolated source-export smoke check on the candidate. Verify its exact successful
   macOS/Python 3.9 and 3.12 CI run and actual per-job test counts. Keep evidence tied
   to that SHA, not an earlier beta tag or feature branch.
3. Review the sanitized X3 report against that candidate's runtime, firmware, card,
   reader and filesystem. If later changes only update documentation/version,
   record the hardware-tested SHA and confirm runtime changes are limited to the
   version banner; do not claim the final SHA itself was physically tested. Changes
   affecting migration/verification/recovery require relevant renewed validation.
4. Resolve release blockers and reconcile README, compatibility matrix, security/
   safety limitations, changelog and notes with actual evidence. Set the final
   version constant to `1.0.0` in a reviewed change, test the final exact SHA again,
   and confirm the source archive includes every runtime helper and no private data.
5. Obtain separate approval for `v1.0.0`, the final SHA, notes and assets. Only then
   create a stable release with prerelease disabled. Verify the remote tag SHA,
   metadata and generated source archives afterwards. Do not retag an earlier beta
   or silently promote a prerelease; no automatic release publisher is configured.

Keep the original card and verified backup throughout acceptance. All automated
checks remain synthetic; neither release preparation nor CI authorizes real-card
operations or uploading private hardware evidence.
