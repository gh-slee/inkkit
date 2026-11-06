---
id: INK-P2-030A
title: Decide distribution scope: signing account, architectures, macOS versions, updates
priority: P2
status: blocked
type: decision
parent: INK-P2-030
depends_on: []
resources: []
risk: medium
size: XS
agent_tier: standard
gate: owner
gate_approval:
review: self
branch:
pr:
spec:
updated: 2026-11-06
---

# INK-P2-030A: Decide distribution scope: signing account, architectures, macOS versions, updates

## Goal

Record the owner choices that public distribution needs before any build or signing work.

## Acceptance criteria

- [ ] Each question answered and recorded in gate_approval and the Log.

## Plan

- [ ] Ask the owner.
- [ ] Update INK-P2-030C and INK-P2-030D to the decided scope.

## Decisions needed

- Apple Developer ID account and notarization credentials: available, and who holds them? Agents never handle the credentials.
- Architectures: Apple silicon only, or universal2 including Intel? Recommendation: universal2 if the runtime research (INK-P2-030B) finds it cheap.
- Minimum macOS: keep 14? Recommendation: 14, after an actual macOS 14 check.
- Updates: manual download page or Sparkle-style updater? Recommendation: manual first.

## Handoff

- State: Waiting on the owner.
- Next step: Ask the owner the questions under Decisions needed.
- Verify: Not applicable yet.
- Gotchas: None recorded.
- Open questions: None.

## Log

- 2026-11-06 claude/opus-5.5: created during agent ticket workflow installation.
