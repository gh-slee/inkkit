# InkKit macOS design

## Scope and mode

The developer preview is an **Operate** surface: inspect, edit, review and recover
settings. It follows the native sidebar-and-form direction in the approved plan.
This expands InkKit's existing identity; it is not a replacement brand exercise.

## Visual system

- System macOS typography and semantic colors, with native light/dark behavior.
- Native sidebar, toolbar, grouped forms, steppers, toggles, pickers and tables.
- SF Symbols for actions and navigation; no decorative illustrations or metric cards.
- A 195-point preferred sidebar, 1100-by-780 default window, 980-by-660 minimum.
- Content padding 24 points, 32 points for the introductory page; related controls
  stay together and secondary descriptions use the semantic secondary foreground.
- Use accent for the main action and active selection. State text accompanies
  error/success information. Color alone never carries meaning.

## Information and interaction

Sidebar: Overview; Display, Reading, Library, Controls, Frontlight, Status bars,
Device; Wi-Fi, OPDS, Reading sync, Font rendering, Dictionary; Backups. Search
finds main settings across groups. Collections expose active entries and Add/Remove.
A persistent header identifies the synthetic workspace or user-confirmed card
model/firmware. The sidebar labels the development build; a status area reports work.

Drafts stay in memory. Cmd+S opens review; Cancel leaves data untouched. Apply
backs up before writing and verifies by reading back. Restore has its own review
and refuses files changed since the associated apply. Reload and restore are
disabled while a draft needs attention. Busy states disable conflicting actions.

The review table names the setting, current value and new/restored value. Sleep
sentinel 31 displays as Never. Toggle values display as On/Off. Empty device names
display as Hardware default. Unsupported controls are disabled with a reason; existing unsupported values stay visible.
Credentials use SecureField with blank-means-keep. Every write containing plaintext
needs a fresh explicit checkbox in review, including restore. Opening a card requires
a separate model/firmware profile sheet; ordinary editing never asks to erase.

## Accessibility and verification

Use native control labels, keyboard focus, semantic headings and symbol labels.
Decorative symbols are hidden from accessibility. Values use explicit units and
tabular digits where helpful. Readability and window resizing take priority over
decoration. Check the rendered window and review sheet at the supported window
sizes before presenting the preview; source/typechecking alone is not visual QA.

There is no web/CSS detector for this native surface. Physical settings acceptance
and signing/Gatekeeper checks are separate from a visual review.
