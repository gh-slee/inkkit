# Tickets and the parallel agent workflow

This directory is the single tracked backlog for this project. Any coding agent
(Codex, Claude Code, opencode with DeepSeek or another model, or a human) can pick
up any ticket, including one another agent started and could not finish. Several
agents can work on different tickets at the same time.

Nothing here depends on a particular vendor. The protocol is Markdown files, Git
branches and worktrees, and one standard-library script:
[`scripts/tickets.py`](../scripts/tickets.py). The project's AGENTS.md stays the
authority for safety and publication rules; a ticket never widens them.

- [ROADMAP.md](ROADMAP.md) has the end-to-end plan, phases and parallel lanes.
- `python3 scripts/tickets.py list` shows the live board.
- `python3 scripts/tickets.py next --tier <tier>` lists the tickets you may claim.

## Quick start for an agent

Start in the primary checkout. The script finds the shared Git directory itself,
so it also works from any worktree.

```bash
git fetch origin
python3 scripts/tickets.py next --tier standard
python3 scripts/tickets.py resume INK-P0-010
python3 scripts/tickets.py claim INK-P0-010 --agent codex/gpt-5.5 --worktree
```

`claim` creates or attaches `work/worktrees/<ticket-id>` on the ticket branch. Do
all work there, never in the primary checkout. Then:

1. Read the ticket's **Handoff** section first, then Goal and Acceptance criteria.
   Read only the docs the ticket links, plus AGENTS.md.
2. Set `status: in_progress` and `updated:`, add a Log line, and commit.
3. Work through the Plan checkboxes. After each meaningful step, update Handoff,
   commit (WIP commits are fine on a ticket branch), push the branch and run
   `python3 scripts/tickets.py heartbeat <ID> --note "<one line>"`.
4. Before you stop for any reason, write the Handoff (see below), commit and push.
   Assume a usage limit can cut you off at any moment.
5. When the acceptance criteria pass and any required independent review is
   recorded, set `status: done` and `pr:` in the PR's final commit and open the PR.
   Only the owner merges, so the ticket reads `done` on the default branch only after
   the merge. If review asks for changes, set `status: in_review` until the repair is pushed.
6. After the merge, run `python3 scripts/tickets.py release <ID>`. If the PR is
   closed without merging, set the ticket back to `ready` with a Log line.

## Capability tiers

Each ticket has an `agent_tier`. Pass your own tier to `next`; it shows tickets at
or below it.

| Tier | Typical agents | Tickets |
|---|---|---|
| `any` | fast or small models, for example DeepSeek Flash | Low-risk, well-specified chores, docs and tests |
| `standard` | mid-size coding models | Normal features with clear contracts; medium risk |
| `frontier` | the strongest available models | Security, money, data migration, concurrency, auth, anything critical |

A smaller model may review or write tests for a higher-tier ticket only if a
`review` ticket says so. It must not implement one.

## Running several agents at once

1. **One ticket, one writer.** `claim` creates
   `<git-common-dir>/agent-tickets/claims/<ID>.json` with an atomic exclusive
   create. A second claim on the same ticket fails, from any worktree and any
   agent product on the same machine.
2. **Exclusive resources.** A ticket lists `resources:`, for example `db-schema` or
   `frontend-shell`. Claiming locks each one atomically, so tickets sharing a
   resource cannot run at the same time.
3. **One worktree and branch per ticket.** Never share a worktree. Never write on
   another ticket's branch.
4. **Isolated runtime resources.** Worktrees do not isolate Docker, databases or
   ports. Each claim records an `isolation_id` and a `port_base`. Use the isolation
   ID as a prefix for container, Compose project, database and temp names, and
   use ports from `port_base` to `port_base + 99`.

Claims are local to one machine. Across machines, the pushed ticket branch is the
shared record: after `git fetch`, if `origin/<branch>` has commits not on the
default branch, treat the ticket as owned elsewhere unless the owner says otherwise.

## Picking up interrupted work

A claim carries a heartbeat. If it is older than `TICKETS_STALE_MINUTES` (default
120), the previous agent is presumed stopped, for example by a usage limit.

```bash
python3 scripts/tickets.py resume INK-P0-010
python3 scripts/tickets.py takeover INK-P0-010 --agent claude/opus-5.5 --worktree --reason "previous agent hit usage limit"
```

Before taking over, confirm that no process still writes in that worktree. Then
read Handoff and the branch's last commits, keep any uncommitted changes (they are
the previous agent's unfinished step), re-run the Handoff **Verify** commands and
add a Log line naming the former and new agents. Never take a live claim unless
the owner tells you to (`--owner-approved`).

## Ticket file format

File name equals ID, for example `tickets/INK-P0-010.md`. IDs look like
`<PREFIX>-P<0-2>-<3 digits>`, with an optional letter for epic children
(`INK-P0-012A`). The `priority` field is authoritative if it later differs from
the ID. Copy [TEMPLATE.md](TEMPLATE.md) to start.

| Field | Values |
|---|---|
| `priority` | `P0`, `P1`, `P2` |
| `status` | `backlog`, `ready`, `in_progress`, `paused`, `in_review`, `blocked`, `done`, `superseded` |
| `type` | `epic`, `feature`, `bug`, `chore`, `docs`, `review`, `decision`, `research` |
| `depends_on`, `resources` | `[a, b]` lists; resources are lowercase kebab-case |
| `risk` | `low`, `medium`, `high`, `critical` |
| `size` | `XS`, `S`, `M`, `L`, `XL` |
| `agent_tier` | `any`, `standard`, `frontier` |
| `gate` / `gate_approval` | `none` or `owner`; approval text only when the owner actually approved |
| `review` | `self` or `independent` |

Body sections, in order: `## Goal`, optional `## Context`, `## Acceptance criteria`,
`## Plan`, `## Decisions needed` (required when blocked), `## Handoff`, `## Log`.

The Handoff is overwritten at each checkpoint; the Log keeps history:

```markdown
## Handoff
- State: what is done and committed, what is uncommitted and why.
- Next step: the single next action.
- Verify: exact commands that prove the current state.
- Gotchas: traps found so far.
- Open questions: anything waiting on the owner.
```

## Rules that keep the board consistent

- **Edit only your own ticket file** in a ticket branch. File new tickets for
  follow-ups. This keeps parallel PRs from conflicting.
- **Gates:** `gate: owner` tickets need `gate_approval` before work starts. Only the
  owner grants it. Never infer approval from priority, a roadmap or passing tests.
- **Reviews:** `review: independent` means a different agent session reviews the
  diff. A different model name alone does not count.
- **Privacy:** ticket text may be public. No secrets, personal data, home-directory
  paths or private transcripts.
- Agents never merge, force-push, release or deploy unless the owner says so.

## Script reference

| Command | Purpose |
|---|---|
| `check` | Validate every ticket file. Run it in the test suite. |
| `list [--priority P0] [--status ready] [--all]` | Board with live claims. |
| `next [--tier any\|standard\|frontier]` | Claimable or resumable tickets for your tier. |
| `show ID` / `resume ID` | Ticket text (newest copy from its branch), claim and git state. |
| `claim ID --agent NAME [--worktree] [--base origin/main]` | Atomic claim plus resource locks. |
| `heartbeat ID [--note TEXT]` | Refresh the claim from the owning worktree. |
| `takeover ID --agent NAME [--worktree] --reason TEXT` | Take a stale claim; records the previous owner. |
| `release ID` | Drop the claim and its resources. |

Agent names use `tool/model`, for example `codex/gpt-5.5`, `claude/opus-5.5` or
`opencode/deepseek-flash`.

## Gotchas in this project

- **Publication guard.** `scripts/check_publication.py` only accepts ticket files
  named exactly `tickets/<PREFIX>-P<0-2>-<3 digits>[letter].md`. Any other new file
  under `tickets/` fails the commit hooks and CI. Keep notes inside the ticket file.
- **No real cards.** Tests use synthetic files with `XTEINK_TESTING=1`. A ticket never
  authorizes operating a real card; owner-run evidence tickets only record results.
- **Shared recovery storage.** A built preview app keeps its private recovery records
  and operation lock in the current user's Application Support folder, shared by all
  worktrees and intentionally not redirectable. Run real-card sessions from one
  build at a time; agents use the synthetic demo only.
- **Per-worktree build output.** The preview builder writes `work/macos-preview` and
  CI's Swift module cache `work/swift-module-cache` inside each worktree; no ports,
  databases or containers are used, so `port_base` is normally unused here.
- **PRs.** Follow AGENTS.md: the canonical PR template, `scripts/check_pr_description.py`
  on the exact body file, and the publication checks before any push.
