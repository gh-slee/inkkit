---
id: INK-P0-012A
title: Pin CrossInk v2.0 in the release registry as backup-only
priority: P0
status: ready
type: feature
parent: INK-P0-012
depends_on: [INK-P0-011]
resources: [crossink-contracts, firmware-docs]
risk: medium
size: S
agent_tier: standard
gate: none
gate_approval:
review: self
branch:
pr:
spec:
updated: 2026-11-06
---

# INK-P0-012A: Pin CrossInk v2.0 in the release registry as backup-only

## Goal

Add the decided v2.0 tag to crossink_contracts.py with its commit and SDK pins and backup-only access, so v2.0 readers get named, pinned backups before editing ships.

## Context

- crossink_contracts.py, tests/test_config*.py, docs/firmware-support.md "Pinned releases".

## Acceptance criteria

- [ ] Registry entry with exact tag, commit and SDK pin; models per the release changelog.
- [ ] "Newer than" option moves past the new release.
- [ ] Synthetic tests cover the new entry; all tests pass.
- [ ] docs/firmware-support.md table updated.

## Plan

- [ ] Add the entry and tests.
- [ ] Update the support table and CHANGELOG Unreleased.

## Handoff

- State: Not started.
- Next step: Claim the ticket and start the first Plan item.
- Verify: Not applicable yet.
- Gotchas: The import-time check forbids an editable entry without RELEASE_SETTINGS/RELEASE_STORES; keep it backup-only here.
- Open questions: None.

## Log

- 2026-11-06 claude/opus-5.5: created during agent ticket workflow installation.
