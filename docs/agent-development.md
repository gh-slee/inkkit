# Agent-assisted development

Agents are optional development tools. The migration CLI runs as reusable Python
code without Codex, an LLM, a skill runtime or network access. Start with the real
repository, working tree, tests and [shared instructions](../AGENTS.md).

## Instruction discovery

Open a **new session with this repository as its project/current directory**.
Changing a shell directory mid-chat does not prove startup discovery. Check any
applicable global/ancestor instructions and existing scoped vendor rules; do not
replace useful settings or create a parallel instruction-memory system.

[Official AGENTS.md discovery](https://developers.openai.com/codex/guides/agents-md)
selects at most one instruction file per directory, preferring
`AGENTS.override.md` to `AGENTS.md`, followed by configured fallback names. A
same-directory override therefore needs to explicitly retain the shared file.
Its first line must be exactly:

```text
Before working, explicitly read ./AGENTS.md.
```

`AGENTS.md` is the concise public project contract. An optional root
`AGENTS.override.md` contains private owner preferences and bounded current-state
notes; it is ignored, never published, and mode 0600 on POSIX. Keep personal paths,
permissions/approval history and session state out of shared guidance and examples.
Account for the installed `project_doc_max_bytes` limit (32 KiB by default); keep
instructions concise instead of changing global configuration. Native discovery
and a later explicit file read are different evidence; report them separately.

## Local checks

```bash
git status --short --branch
git rev-parse HEAD
git check-ignore -v -- AGENTS.override.md docs/AGENTS.override.md
git ls-files -- AGENTS.override.md ':(glob)**/AGENTS.override.md'
python3 scripts/check_publication.py --worktree
python3 scripts/check_publication.py --staged
python3 scripts/check_publication.py --all-history
```

The tracked-file query must print nothing for private guidance. A new ignore rule
does not fix an already-tracked or historical private file. Stop publication and
report it; do not rewrite history, delete data or dump sensitive matches. Read the
private current-state notes only when applicable and reconcile them against Git;
replace stale notes instead of appending transcripts. Public clones must work
without private instructions.

Run appropriate tests from [development](development.md) and report their actual
scope. No lint/type/package build is configured. Setup-only work never requires a
real card migration. Keep existing work and hooks intact; installation already
preserves a custom hooksPath. Language and owner publication boundaries belong in
private guidance, while generic contribution/privacy rules remain public.

## Worktrees and fresh copies

[Official managed-worktree behavior](https://developers.openai.com/codex/app/worktrees)
copies an ignored `AGENTS.override.md` into local Codex-managed worktrees without
requiring `.worktreeinclude`. Source symlinks are skipped and existing destination
files are not overwritten. Verify the destination's actual content, permissions
and freshness; an expected copy is not evidence of a completed copy.

Ordinary clones, manually created Git worktrees and remote worktrees do not have
that guarantee. Provision only the necessary private guidance deliberately through
an authorized private channel; never copy whole settings, backups or data trees.
Do not create a worktree merely to claim verification. Shared/public instructions
remain usable when no private override exists.

## Fresh-session verification prompt

Copy this into a new session opened at the repository root:

> Before modifying anything or reading user data, list instruction files you can
> verify were discovered at startup and those you explicitly read. If discovery
> evidence is unavailable, say so rather than guessing. If a root AGENTS.override.md
> exists, follow its first instruction and explicitly read ./AGENTS.md. Summarize
> the real project stack, one verified test command, conversation language and
> publication approval boundary. Check ignored/untracked status of private guidance.
> Report branch/commit and discrepancies with saved current state. Do not dump
> private instructions, credentials or user data. Make no changes.

File/permission checks cannot prove that another session followed the instructions.
Report a fresh-session or worktree-copy check as pending until actually performed.
Public tasks use the existing [GitHub Issues](https://github.com/gh-slee/inkkit/issues);
private owner/session notes are not a public roadmap. See [contributing](../CONTRIBUTING.md)
and [publication safeguards](publishing.md) before proposing publication.
