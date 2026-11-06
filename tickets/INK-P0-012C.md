---
id: INK-P0-012C
title: Expose CrossInk v2.0 settings in the native app
priority: P0
status: backlog
type: feature
parent: INK-P0-012
depends_on: [INK-P0-012B]
resources: [macos-app]
risk: medium
size: M
agent_tier: standard
gate: none
gate_approval:
review: self
branch:
pr:
spec:
updated: 2026-11-06
---

# INK-P0-012C: Expose CrossInk v2.0 settings in the native app

## Goal

Show the new or changed v2.0 settings in the SwiftUI app via the backend catalogue, with no second Swift device list.

## Context

- macos/InkKitApp.swift, inkkit_helper.py IPC, tests/test_helper.py, tests/test_macos_build.py.

## Acceptance criteria

- [ ] Swift typecheck passes (see .github/workflows/tests.yml).
- [ ] Typed IPC tests cover new controls.
- [ ] Hidden hardware pages still follow model capabilities.

## Plan

- [ ] Groom after INK-P0-012B lands.
- [ ] Add controls and IPC tests.

## Handoff

- State: Not started.
- Next step: Claim the ticket and start the first Plan item.
- Verify: Not applicable yet.
- Gotchas: Shares macos-app with INK-P1-022; claims serialize them.
- Open questions: None.

## Log

- 2026-11-06 claude/opus-5.5: created during agent ticket workflow installation.
