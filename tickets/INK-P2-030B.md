---
id: INK-P2-030B
title: Research a production Python runtime source for the bundled helper
priority: P2
status: ready
type: research
parent: INK-P2-030
depends_on: []
resources: []
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

# INK-P2-030B: Research a production Python runtime source for the bundled helper

## Goal

The builder relocates the local python.org runtime as a feasibility spike. Find a maintainable, licensed, reproducible runtime source and its architecture coverage.

## Context

- scripts/build_macos_preview.py, docs/macos-preview.md "Packaging and installer status".

## Acceptance criteria

- [ ] Options compared (python.org installer, python-build-standalone, others) for licensing, signing, universal2, update cadence and size.
- [ ] Recommendation recorded in this ticket.

## Plan

- [ ] Read the builder and its tests.
- [ ] Compare options; record findings here only.

## Handoff

- State: Not started.
- Next step: Claim the ticket and start the first Plan item.
- Verify: Not applicable yet.
- Gotchas: Read-only research; do not download runtimes into the repository.
- Open questions: None.

## Log

- 2026-11-06 claude/opus-5.5: created during agent ticket workflow installation.
