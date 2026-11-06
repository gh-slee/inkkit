---
id: INK-P2-030D
title: Sign, notarize and package the app as a DMG
priority: P2
status: backlog
type: feature
parent: INK-P2-030
depends_on: [INK-P2-030C]
resources: [macos-build, release-pipeline]
risk: critical
size: M
agent_tier: frontier
gate: owner
gate_approval:
review: independent
branch:
pr:
spec:
updated: 2026-11-06
---

# INK-P2-030D: Sign, notarize and package the app as a DMG

## Goal

Produce a Developer ID signed, hardened-runtime, notarized drag-to-Applications DMG with the owner holding credentials.

## Acceptance criteria

- [ ] Signature, hardened runtime and notarization verified on a clean Mac.
- [ ] No credentials in the repository, logs or CI artifacts.

## Plan

- [ ] Groom after INK-P2-030C; owner approves before work starts.

## Handoff

- State: Not started.
- Next step: Claim the ticket and start the first Plan item.
- Verify: Not applicable yet.
- Gotchas: Agents never enter signing or notarization credentials; the owner runs those steps.
- Open questions: None.

## Log

- 2026-11-06 claude/opus-5.5: created during agent ticket workflow installation.
