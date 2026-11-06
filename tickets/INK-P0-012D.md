---
id: INK-P0-012D
title: Document CrossInk v2.0 support and regenerate the configuration reference
priority: P0
status: backlog
type: docs
parent: INK-P0-012
depends_on: [INK-P0-012B, INK-P0-012C]
resources: [config-docs, firmware-docs]
risk: low
size: S
agent_tier: any
gate: none
gate_approval:
review: self
branch:
pr:
spec:
updated: 2026-11-06
---

# INK-P0-012D: Document CrossInk v2.0 support and regenerate the configuration reference

## Goal

Keep README, the configuration reference, firmware support, compatibility and CHANGELOG in step with v2.0.

## Context

- python3 scripts/check_configuration_docs.py --write, then the check without --write.

## Acceptance criteria

- [ ] Generated docs match the schema (check passes).
- [ ] Firmware-support table and CHANGELOG updated.
- [ ] Physical evidence for v2.0 stays labeled pending unless recorded.

## Plan

- [ ] Regenerate, review the diff, update prose docs.

## Handoff

- State: Not started.
- Next step: Claim the ticket and start the first Plan item.
- Verify: Not applicable yet.
- Gotchas: None recorded.
- Open questions: None.

## Log

- 2026-11-06 claude/opus-5.5: created during agent ticket workflow installation.
