---
id: INK-P2-030C
title: Build the app with the chosen production runtime and architectures
priority: P2
status: backlog
type: feature
parent: INK-P2-030
depends_on: [INK-P2-030A, INK-P2-030B]
resources: [macos-build]
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

# INK-P2-030C: Build the app with the chosen production runtime and architectures

## Goal

Update the preview builder to the decided runtime and architectures, keeping its copy allowlist and self-test.

## Acceptance criteria

- [ ] tests/test_macos_build.py covers the new runtime path.
- [ ] Builder still never copies the checkout or site-packages.
- [ ] Clean-Mac and Intel checks recorded or marked not run.

## Plan

- [ ] Groom after INK-P2-030A and INK-P2-030B.

## Handoff

- State: Not started.
- Next step: Claim the ticket and start the first Plan item.
- Verify: Not applicable yet.
- Gotchas: None recorded.
- Open questions: None.

## Log

- 2026-11-06 claude/opus-5.5: created during agent ticket workflow installation.
