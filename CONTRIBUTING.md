# Contributing

Use Python 3.9+ and the standard library. Run `XTEINK_TESTING=1 python3 -m unittest discover -s tests -v -b` and `python3 -m compileall -q xteink_sd_migrate.py disk_safety.py tests`.

Keep the direct `python3 xteink_sd_migrate.py` entry point, its single version constant and legacy manifest compatibility. Version changes must not rename scripts. Add synthetic regression tests for safety changes. Disk mutations belong only in the guarded erase entry point; never test them on real storage or in CI. Do not weaken a rejection merely to make an unfamiliar reader pass.

Use the issue template for hardware reports. Share macOS/Python/firmware versions, card capacities, reader type and sanitized errors. Never upload books, backups, manifests, credentials, personal filenames or full unredacted diagnostics. Do not include user data in tests. Before committing, check `git diff --cached --name-only` and `git ls-files`. Never force-add ignored files.
