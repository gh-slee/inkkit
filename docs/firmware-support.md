# Ongoing CrossInk and XTEINK compatibility

InkKit aims to keep supporting new CrossInk releases and XTEINK devices. A version
number in the app identifies a **reviewed storage contract**, not a permanent
limit on the project and not a guarantee that unknown future firmware works.

## Current reviewed contract

| Firmware | Source pin | Intended models | Physical evidence |
| --- | --- | --- | --- |
| CrossInk 1.6.1 | `9914146eeae7b46b300f475a16c32426fc02ec1f` | X3, X4, X4 Classic, X4 Pro | Selected owner-reported X3 preferences/Restore/eject; other settings/models pending |

The SDK capability pin is `699370183fa3a0e33c9cb83a36f701bbb6022095`.
Its board definitions give no frontlight/touch to X3, X4 or X4 Classic; X4 Pro has
both. Other differences (RTC, tilt, Home, buttons, PSRAM and shortcut choices) stay
model-dependent. The full [configuration reference](configuration-reference.md)
links every main control to its source, distinguishes legacy/format metadata and
lists runtime actions, assets and per-book data outside offline global editing.
Do not interpret “all controls listed” as physical validation of every control.

## Implementation and extension boundary

The Python backend exports `profiles.describe`, using `inkkit_schema.profile_catalog`.
The native app obtains firmware/model choices and capabilities from that catalogue;
there is no second Swift device list or hardcoded firmware confirmation. All store
snapshots carry the selected model's capabilities, so changing categories cannot
accidentally expose another model's hardware page.

The current engine implements **one** audited provider. Adding metadata/version
strings alone does not implement another storage contract: `supports_configuration`
continues to reject unknown firmware/models before disk queries or writes. A future
provider needs its schema, codecs, store paths, migration/default behavior and
explicit dispatch, with catalogue entries matching what is actually implemented.
No remote executable/profile downloads, nearest-version fallback or nightly
compatibility promise are implemented.

## Adding a firmware release or reader

1. Pin the official release/tag and commit plus SDK/submodule commits. Review the
   settings catalog, definitions, serializers/loaders, independent stores and real
   board capabilities. Enumerate additions, removals, type/ID/default/path changes,
   hardware predicates and intentional runtime-only exclusions.
2. Implement the appropriate provider/dispatch and migrations where required.
   Preserve unknown fields, absent defaults, opaque credentials, exact backup
   formats and legacy restoration. Never translate a different reader's opaque
   credentials or hardware cache as if it were the same device.
3. Add synthetic per-store transactions, preservation/failure/consent tests and
   model capability checks, then native typed IPC and packaging checks. Keep docs
   generated from the actual schema. A catalogue entry must not outpace its codec.
4. Record targeted owner-run hardware evidence for the available reader. X3-only
   maintainer ownership does not require buying every other device, but untested
   device/settings combinations must stay explicitly labeled. Never format real
   media in automated tests.
5. Review source/privacy/screenshots and the concrete publication scope, run CI
   against the exact outgoing head and publish compatibility notes with the update.
   Do not retag an old release or label the unreleased native app as the CLI release.

## Unlisted firmware or model

Do not confirm a false version to bypass the app's gate. Settings editing remains
blocked until the contract is reviewed and implemented. The separate opaque-file
migration CLI can still diagnose/back up a layout-compatible card when its own
safety/layout checks pass; these operations do not claim to understand the newer
settings schema. Keep the original card and backups. Do not downgrade firmware or
reformat a card merely to make it open in InkKit.

This is a maintenance policy, not an automatic monitor or update service. New
compatibility is delivered through reviewed source/app updates. Public Mac binary
signing, notarization, clean-Mac/Intel tests and an updater remain separate work.
