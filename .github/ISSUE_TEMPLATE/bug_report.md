---
name: Bug report
about: Report a failure using sanitized details only
---

Use this template for native app or migration CLI failures. For a working or
partial migration result, use the migration hardware report instead.

- Workflow (native settings app or migration CLI):
- App version/build or CLI `--version`; source tag/commit if known:
- macOS version and Mac architecture:
- Python version (CLI or app-builder issues; the built app bundles Python):
- XTEINK model and firmware name/build:
- Card capacity; source/target capacities for migration:
- Reader make/type (USB or built-in):
- Card filesystem; selected filesystem policy for migration:
- Operation (open/read, configuration review/apply/backup/restore/eject, or CLI mode):
- Stage of failure and steps to reproduce:
- Sanitized error text:
- Was anything erased? Is the original card/verified backup intact?

Do not attach backups, manifests, books, tokens or reader settings. Redact volume names, personal paths, book titles and credentials from diagnostics. A successful report does not certify other hardware.
