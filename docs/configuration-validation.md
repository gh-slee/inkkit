# Configuration validation and acceptance

## What is established

InkKit's native editor has real file transactions for an explicitly selected
current SD card. The synthetic demo deliberately uses invented settings and never
opens a card. Both routes use the same schema/patch/backup/verification engine;
the real route additionally requires a confirmed macOS removable-volume session.
It is not a firmware simulator, an official CrossInk app or hardware certification.

A successful Apply proves that the intended configuration bytes were backed up,
written and read back. It does **not** prove that the firmware loaded them, an asset
exists, a network login succeeds, or the reader performs the intended action.
Those are separate acceptance checks on the actual device. Some controls apply
only to a particular theme, book format or installed asset: for example, the
library/file-browser swap is active only in Minimal/Dashboard, and a selected SD
font takes precedence over the stored built-in font. An inactive setting is not
proof that the file writer is a mock; it needs the appropriate firmware context.

| Evidence | Current status | What it proves |
| --- | --- | --- |
| Pinned upstream definitions/serialization/load logic | Source audit completed for CrossInk v1.6.1 | Storage keys, IDs, scalar defaults, ranges and conditional loader behavior have identified upstream sources |
| Python transaction tests | Synthetic fixtures and mocked volume queries | Codec behavior, preservation, backup/recovery, consent and file IO guards |
| Native build and typed IPC | Local ARM64 developer bundle | Swift/helper request/response compatibility, bundled runtime and synthetic store roundtrips |
| X3 settings writes and on-reader behavior | Limited owner-reported acceptance | Restore, safe eject and tested preferences, including Sleep Screen, worked; no exhaustive per-control report |
| X4, X4 Classic, X4 Pro settings | **Not performed** | Expected capability profiles only; no physical acceptance |
| Native UI and screenshots | Main pages visually inspected with synthetic X3/Pro demos | Native form/review/backup UI; not device behavior or full accessibility QA |

Existing X3 migration acceptance is documented separately in
[hardware validation](hardware-validation.md). It does not establish configuration
editor acceptance. Opening a demo is not a real-card test.

## Owner-reported X3 configuration result: 2026-10-23

The maintainer confirmed the reader About page showed **CrossInk 1.6.1**. In the
local ARM64 ad-hoc development app, opening the real card, reading the main pages
and Dictionary, and normal Eject worked after the reported fixes. The maintainer
then reported successful **Restore** and successful tested preference changes,
clarifying that the visible on-reader change was **Sleep Screen**.

This is a maintainer-run report, not an agent-operated media test. The exact
Sleep Screen subfield/value transitions and the full list of other preferences
were not recorded. Do not mark all 121 editable X3 controls, credentials, fonts,
dictionaries or X4-family models as physically validated from this report.
The tested local build's executable SHA-256 was
`de0a951f099af87faff39006c6da1b053dfec16883a1a2584f882762509436d3`;
source input hashes remain in its private BuildInfo evidence. It was not a tagged
GUI release. The later complete-snapshot UI and dynamic catalogue have separate
synthetic/native checks and still need their own physical acceptance.

## Source audit: 2026-10-23

Profile: [CrossInk v1.6.1](https://github.com/uxjulia/CrossInk/tree/9914146eeae7b46b300f475a16c32426fc02ec1f),
commit `9914146eeae7b46b300f475a16c32426fc02ec1f`. This matched the upstream main
and latest release when checked. The profile remains pinned; later firmware
changes do not automatically become supported.

The audit compared 19 selected upstream files with their Git blob IDs from the
live pinned GitHub tree. It independently inspected serialization and loading,
compiled selected upstream pure C++ functions/scalar initializers on the Mac and
compared their results with InkKit. Board capability inputs were synthetic;
this was **not a full firmware build, firmware boot or physical-device test**.

| Audit | Comparisons | Result |
| --- | --- | --- |
| Scalar defaults from upstream C++ initializers, four model profiles | 496 | Match |
| Shortcut domains and trigger transitions plus legacy reader-bar layouts, using selected upstream pure functions | 1,956 | Match |
| Ordinary catalog enum domains, numeric limits, toggles and text-buffer limits | 85 fields | Match |
| Main form storage roots | 121 roots / 148 controls | Every control has a pinned definition/serializer link in the generated reference |

The remaining catalog entries use shortcut builders or direct serialized fields;
they are covered by the shortcut/source-reference audit rather than the 85 ordinary
catalog-field comparisons. Independent side stores were read separately:
[Wi-Fi](https://github.com/uxjulia/CrossInk/blob/9914146eeae7b46b300f475a16c32426fc02ec1f/src/WifiCredentialStore.cpp),
[OPDS](https://github.com/uxjulia/CrossInk/blob/9914146eeae7b46b300f475a16c32426fc02ec1f/src/OpdsServerStore.cpp),
[sync](https://github.com/uxjulia/CrossInk/blob/9914146eeae7b46b300f475a16c32426fc02ec1f/lib/KOReaderSync/KOReaderCredentialStore.cpp),
[TTF profiles](https://github.com/uxjulia/CrossInk/blob/9914146eeae7b46b300f475a16c32426fc02ec1f/src/TtfRenderProfileStore.cpp)
and [dictionary selection](https://github.com/uxjulia/CrossInk/blob/9914146eeae7b46b300f475a16c32426fc02ec1f/src/util/Dictionary.cpp).
No real settings/backups were used as fixtures.

This review found and corrected effective-value differences for missing modern
keys: inherited previous-page gestures, legacy screen/clock/browser preferences,
the Minimal-theme browser default and the non-reader battery slot. It also made
SD-font precedence explicit in the built-in-font label. Partially migrated legacy side-button pairs are refused until firmware migration.
Regression tests cover
these fallbacks without materializing absent keys. Passing earlier synthetic tests
was not proof that all conditional firmware semantics were already correct.

The [complete reference](configuration-reference.md) distinguishes current global
settings, legacy mirrors, format metadata and excluded runtime/per-book actions.
No claim of 100% hardware behavior or absence of all defects follows from a source
audit or a test count.

The same 19 source blobs, upstream main/latest-release pins and SDK board header
were rechecked on 2026-10-24. The four actual upstream board profiles agree with
the capability map: only X4 Pro has frontlight/touch hardware; X3, X4 and X4 Classic
do not. This source check does not add hardware acceptance.

## X3 acceptance gates

Use a separately backed-up X3 card, a separate SD reader and the exact confirmed
firmware version. Never format a card for this acceptance. Perform one small,
reversible change at a time; retain its backup and restore the original state.
Do not bulk-toggle every option or disable input as an initial test.

1. **Record the environment.** Actual firmware version/build shown by the reader,
   X3, macOS, app build/input hashes, reader/card filesystem and capacity. Do not
   infer the version from the word "latest" or the SD directory name.
2. **Open/read only.** Open the real card, select X3/v1.6.1 and confirm displayed
   known values against the reader. Unsupported touch/frontlight/Home controls
   must remain unavailable. No settings bytes should change merely by opening.
3. **First harmless write.** Change one reversible preference such as hidden-file
   visibility. Review exactly one difference, Apply and confirm verified backup
   and readback. Use Eject. Return the card to the shut-down reader and confirm
   that exact preference changed. This establishes one field, not all fields.
4. **Restore.** Return the card to the Mac, review/restore the matching original
   backup, eject and confirm the original preference on the reader. Later firmware
   resaves may change bytes and intentionally block the guarded restore; stop and
   preserve both versions rather than bypassing protection. For the first test,
   also exercise Apply/Restore before any reader boot, while hashes still match.
5. **Expand in groups.** Record each changed key, expected behavior, on-reader
   observation and restoration result. Reading/layout, display/sleep, library,
   shortcuts, bars, device/clock flags, dictionary/font and connection stores need
   separate observations. An unchanged or untested setting remains pending.
6. **Assets and network behavior.** Use existing known-good SD fonts/dictionaries.
   Verify their selection on the reader. For Wi-Fi/OPDS/sync, use owner-entered
   credentials with per-write consent and verify the relevant connection/login
   and firmware resave; boot alone does not prove removal of plaintext. Do not
   publish SSIDs, URLs, usernames, passwords, book data or before.bin files.
7. **Failure evidence.** Stop on mismatch, verification failure or unexpected
   behavior. Preserve local recovery data. Use only synthetic files for injected
   disk/rename/fsync failures; do not fault-test real media.

Only report fields actually observed. X3 acceptance does not validate X4-family
hardware. The maintainer need not own an X4 to make an X3-first release, but other
model/settings evidence must remain explicitly pending.

## Screenshot publication gate

Add README screenshots only after the X3 settings workflow has real acceptance
evidence and the current build has been visually inspected. Capture the **actual
native app**, not an image-generated mockup or reconstructed UI. Use a fresh
synthetic demo for the published images to protect real reader data; label the
caption "Native app with synthetic example data." Hardware evidence stays in the
acceptance report, not in the screenshot caption.

Suggested captures: Overview with model/status, Reading controls, a reviewed
noncredential change and an invented Wi-Fi entry. Include a useful light/dark
selection, readable scale and window-only capture. Exclude private paths, accounts,
notifications and real credentials. Do not capture or bypass a Computer Use denial.
Review the exact image files, metadata and publication allowlist before a separately
approved image/source push. The [native gallery](screenshots.md) records the current reviewed captures.


## Native UI check: 2026-10-24

The current ARM64 development app was inspected through native UI automation with
fresh synthetic demos. Major sidebar pages, the Wi-Fi/OPDS add/review/Apply flows,
Backup now, newest-first history and an older complete-snapshot restore worked.
The restore removed the later Wi-Fi/OPDS entries and retained the pre-restore full
state. The Delete confirmation was inspected and cancelled. No card was opened,
written, formatted or ejected for this check; backend deletion/fault guards were
exercised in synthetic unit tests. X3 had no Frontlight navigation; the X4 Pro demo
had the expected Frontlight page. These are UI/profile observations, not hardware
results. The [gallery](screenshots.md) contains actual native captures.

Visual review covered the default 1100-by-780-point dark-mode window and native
sheets. Minimum-size, light-mode, full keyboard and VoiceOver coverage remain
pending; no comprehensive accessibility certification is claimed.
