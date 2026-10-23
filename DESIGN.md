# InkKit macOS design

## Scope and mode

The developer preview is an **Operate** surface: inspect, edit, review and recover
settings. It follows the native sidebar-and-form direction in the approved plan.
This expands InkKit's existing identity; it is not a replacement brand exercise.

## Visual system

- System macOS typography and semantic colors, with native light/dark behavior.
- Native sidebar, toolbar, grouped forms, steppers, toggles, pickers and tables.
- SF Symbols for actions and navigation; no decorative illustrations or metric cards.
- A 190-point preferred sidebar, 960-by-700 default window, 880-by-620 minimum.
- Content padding 24 points, 32 points for the introductory page; related controls
  stay together and secondary descriptions use the semantic secondary foreground.
- Use accent for the main action and active selection. State text accompanies
  error/success information. Color alone never carries meaning.

## Information and interaction

Sidebar: Overview, Reading, Device, Backups. A persistent synthetic-workspace notice
states that real-card access is disabled. The lower sidebar states the software
version and Developer Preview status. A status area reports operations.

Drafts stay in memory. Cmd+S opens review; Cancel leaves data untouched. Apply
backs up before writing and verifies by reading back. Restore has its own review
and refuses files changed since the associated apply. Reload and restore are
disabled while a draft needs attention. Busy states disable conflicting actions.

The review table names the setting, current value and new/restored value. Sleep
sentinel 31 displays as Never. Toggle values display as On/Off. Empty device names
display as Hardware default. Unsupported features do not appear as working actions.

## Accessibility and verification

Use native control labels, keyboard focus, semantic headings and symbol labels.
Decorative symbols are hidden from accessibility. Values use explicit units and
tabular digits where helpful. Readability and window resizing take priority over
decoration. Check the rendered window and review sheet at the supported window
sizes before presenting the preview; source/typechecking alone is not visual QA.

There is no web/CSS detector for this native surface. Physical settings acceptance
and signing/Gatekeeper checks are separate from a visual review.
