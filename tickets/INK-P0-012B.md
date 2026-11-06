---
id: INK-P0-012B
title: Implement the CrossInk v2.0 schema, store and codec provider
priority: P0
status: backlog
type: feature
parent: INK-P0-012
depends_on: [INK-P0-012A, INK-P0-010]
resources: [inkkit-schema, inkkit-codec, crossink-profile]
risk: high
size: L
agent_tier: frontier
gate: none
gate_approval:
review: independent
branch:
pr:
spec:
updated: 2026-11-06
---

# INK-P0-012B: Implement the CrossInk v2.0 schema, store and codec provider

## Goal

Implement release-aware schema, store paths, codecs, defaults and migrations for v2.0 as decided in INK-P0-011.

## Context

- inkkit_schema.py, inkkit_codec.py, crossink_profile.py, inkkit_config.py, tests/test_config*.py.
- docs/firmware-support.md steps 2 and 3; docs/config-architecture.md.

## Acceptance criteria

- [ ] Unknown fields and absent defaults preserved; opaque credentials untouched; invalid input fails closed.
- [ ] Per-store synthetic transactions, preservation, failure and consent tests pass.
- [ ] Model capability checks match the SDK pin.
- [ ] Independent review recorded (INK-P0-012E).

## Plan

- [ ] Groom: if INK-P0-010 finds changes in more than two stores, split into per-store child tickets.
- [ ] Implement and test the provider.
- [ ] Run the full suite and the configuration docs check.

## Handoff

- State: Not started.
- Next step: Claim the ticket and start the first Plan item.
- Verify: Not applicable yet.
- Gotchas: Data-writing code for real cards: synthetic files only, XTEINK_TESTING=1, never a real card.
- Open questions: None.

## Log

- 2026-11-06 claude/opus-5.5: created during agent ticket workflow installation.
