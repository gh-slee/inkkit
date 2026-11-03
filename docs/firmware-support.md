# Ongoing CrossInk and XTEINK compatibility

InkKit aims to keep supporting new CrossInk releases and XTEINK devices. A version
number in the app identifies a **reviewed storage contract**, not a permanent
limit on the project and not a guarantee that unknown future firmware works.

## Pinned releases

`crossink_contracts.py` lists every release the app accepts. **Edit** means the
audited schema/codec is implemented. **Backup only** means exact-byte complete
configuration backups and same-reader, same-release restore; settings are not
interpreted, shown or edited. Models follow the release that first shipped their
firmware. Physical evidence is separate from both.

| Firmware | Source pin | Access | Models | Physical evidence |
| --- | --- | --- | --- | --- |
| CrossInk 1.6.1 | `9914146eeae7b46b300f475a16c32426fc02ec1f` | Edit | X3, X4, X4 Classic, X4 Pro | Selected owner-reported X3 preferences/Restore/eject; other settings/models pending |
| CrossInk 1.6.0 | `b25beb13761d5851f98e7eada09aa5e7d430df48` | Edit (selected settings) | X3, X4, X4 Classic, X4 Pro | None |
| CrossInk 1.5.1 | `4f2da6b7777b9a38fdf2606796d6da34caa7d2cb` | Edit (selected settings) | X3, X4, X4 Classic, X4 Pro | None |
| CrossInk 1.5.0 | `0de623ed24acd94ae2301e8e1f4a42e32613110b` | Backup only | X3, X4 | None |
| CrossInk 1.4.0.1 | `54ba245fe8b6dbfcc566edfd175eb36d76c644ad` | Backup only | X3, X4 | None |
| CrossInk 1.4.0 | `b7f6708f96d05e5851f8bcfaaf57bc0e91dc0567` | Backup only | X3, X4 | None |
| CrossInk 1.3.4 | `994fb4b9fa7703d38efa0ef8b0ec8319595bd9b2` | Backup only | X3, X4 | None |
| CrossInk 1.3.3 | `26dc77513c2e277f03458e00d335867140d1e89f` | Backup only | X3, X4 | None |
| Newer than 1.6.1 (unreviewed) | None | Backup only | X3, X4, X4 Classic, X4 Pro | None |

Releases before 1.3.3 keep reader settings in `settings.json`, a name other
firmware also uses, so they are not listed. The storage history that shaped these
eras: v1.2.7 moved OPDS servers to `opds.json`; v1.3.3 moved settings to
`crossink-settings.json`; v1.4.0 adopted freeink-sdk; v1.5.0 greatly expanded
settings; v1.5.1 shipped X4 Classic/X4 Pro firmware; v1.6.1 added
`ttf-rendering.json`. Backup-only releases export no hardware capabilities.

### CrossInk 1.6.0 and 1.5.1 selected settings

v1.6.0 exposes the 82 main settings whose upstream declaration, persisted raw
values and default match the audited v1.6.1 contract, plus Wi-Fi, OPDS, reading
sync and dictionary (their store sources did not change). Cover Grid (`uiTheme` 7)
is not offered. Font rendering is hidden because `ttf-rendering.json` starts in
v1.6.1. Everything else in a v1.6.0 file stays opaque and is preserved unchanged:

- Shortcut actions (power, chords, Home, long-press) and Quick Actions: v1.6.1
  added action values and changed chord sleep rules.
- Reader font size: v1.6.0 offers four fixed built-in sizes, not 8–22 pt.
- Reading-stats tracking: only a debug-build option in v1.6.0.
- Side-button layout/long-press and the individual status-bar keys: current in
  v1.6.0 but replaced in v1.6.1; they need their own reviewed editors.
- Language and keyboard layouts: translation catalogues changed and are unreviewed.

v1.5.1 has the same declarations except two-finger rotation, which arrived in
v1.6.0, so it exposes 81 main settings; its store sources match v1.6.0 apart from
the firmware's new atomic JSON writer. The editable lists are
`inkkit_schema.RELEASE_SETTINGS`. Between the v1.5.1/v1.6.0 and v1.6.1 freeink-sdk
pins, board changes add non-XTEINK boards and an IMU axis fix; RTC, tilt, touch,
frontlight, Home and PSRAM capabilities for XTEINK readers are unchanged.

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

The engine implements the audited v1.6.1 provider and a reviewed subset of it
for v1.6.0. Adding a release to the registry only enables backup-only access; an
editable release also needs `RELEASE_SETTINGS`/`RELEASE_STORES` entries, release-
aware codec validation and tests (an import-time check enforces this). Unlisted
firmware/models fail before disk queries or writes. A future
provider needs its schema, codecs, store paths, migration/default behavior and
explicit dispatch, with catalogue entries matching what is actually implemented.
No remote executable/profile downloads, nearest-version fallback or nightly
compatibility promise are implemented.

## Adding a firmware release or reader

1. Pin the official release/tag and commit plus SDK/submodule commits. Run
   `scripts/extract_crossink_contract.py --repo <checkout> --compare` against a
   local CrossInk clone for a first summary of store paths, settings keys, build
   environments and SDK changes. It is a heuristic aid, not a schema. Review the
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

Do not confirm a false version to bypass the app's gate. For a release newer than
v1.6.1, choose **Newer than CrossInk v1.6.1 (unreviewed)** to keep complete
backups; settings editing remains blocked until the contract is reviewed and
implemented. That option assumes the newer release still keeps
`crossink-settings.json`; opening fails closed otherwise. The separate opaque-file
migration CLI can still diagnose/back up a layout-compatible card when its own
safety/layout checks pass; these operations do not claim to understand the newer
settings schema. Keep the original card and backups. Do not downgrade firmware or
reformat a card merely to make it open in InkKit.

This is a maintenance policy, not an automatic monitor or update service. New
compatibility is delivered through reviewed source/app updates. Public Mac binary
signing, notarization, clean-Mac/Intel tests and an updater remain separate work.
