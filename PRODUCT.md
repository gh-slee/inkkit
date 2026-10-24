# InkKit product

## Platform

Native macOS SwiftUI preview alongside the existing macOS Python migration CLI.

## Users and purpose

XTEINK owners running CrossInk who want to preserve their reader data and manage
SD-card settings from a Mac. The existing CLI backs up and migrates opaque files.
The development app provides inspectable forms, change previews, local backups,
verified writes and recovery for the current card.

## Stack

SwiftUI with a bundled CPython helper and a standard-library Python core. The
development build edits explicit current-card sessions and synthetic demos; selected X3 settings have owner-reported acceptance; broader coverage is pending.
The direct migration CLI remains dependency-free and retains its stable filename.

## Current capabilities and constraints

- The app implements 148 main-setting controls plus Wi-Fi, OPDS, reading sync,
  TTF profiles and global dictionary selection. See the generated configuration
  reference for actual model availability and excluded runtime actions/assets.
- Real-card opening requires explicit model/firmware selection, confirmed removable
  media and Mac-side recovery storage. Apply/restore use review and verified IO.
- Existing credentials stay opaque; new/retained plaintext needs consent per write.
  The firmware must load and successfully resave it; no network operations run here.
- Intended XTEINK scope is X3, X4, X4 Classic and X4 Pro. X3 migration and selected X3 settings
  have owner-reported evidence; all other physical combinations remain pending.
- Configuration semantics are pinned to CrossInk v1.6.1. Unknown fields are
  preserved, missing defaults are not materialized, and invalid/legacy input fails
  closed. A firmware-version field or model is not inferred from an SD directory.
- The migration entry point, safety policy, backup placement and legacy formats
  remain compatible. Config backups have their own versioned format.
- No user books, credentials, settings or backups may enter public source,
  fixtures, screenshots, logs or CI artifacts. Tests use synthetic files only.

## Brand and voice

InkKit is the project name. Public UI, code and canonical documentation are English.
The existing mark is in `assets/readme/xteink-mark.svg`. Use clear actions and
honest capability labels; distinguish a developer preview from released support.

## Evidence

Existing migration tests and the reviewed X3 result are documented in
`docs/hardware-validation.md`. Configuration source contracts and preview limits
are documented in `docs/config-architecture.md` and `docs/macos-preview.md`.

## Product principles

- Preserve the original data and show the actual change before writing.
- Keep ordinary settings edits separate from destructive card migration.
- Prefer native Mac behavior and a self-contained end-user app.
- State physical-validation and distribution limits explicitly.

## Ongoing compatibility

Track new CrossInk versions and XTEINK models through source-reviewed backend
profiles and compatibility tests. Firmware/model/capability choices come from the
bundled catalogue; do not promise unknown future storage contracts work unchanged.
See `docs/firmware-support.md`.

## Open decisions

X3 settings acceptance, other-device testing, production runtime sourcing,
signing/notarization, Intel/clean-Mac validation, final minimum macOS and updater.
The local spike targets macOS 14+ and the build host's CPU; this is not a public
support commitment. No release or automatic publisher is authorized by this preview.
