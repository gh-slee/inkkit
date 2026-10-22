# Security and privacy

## Scope and support

This tool can permanently erase a selected physical disk. Safety fixes target the
latest code/release; historical branches have no separate maintenance commitment.
See [the safety model](docs/safety.md) for fail-closed checks and remaining hotplug,
reader-reporting and hardware limitations. Model support is not hardware certification.

## Private data

The migration tool runs locally and makes no network requests. Backups may contain
Wi-Fi/OPDS/synchronization credentials, personal reading history and copyrighted books.
ZIPs and manifests are not encrypted. Private file permissions are not encryption and
may not be enforced by FAT/exFAT. Protect the host, backups and an off-device copy.

Never attach real ZIPs, manifests, settings, books or unredacted disk diagnostics to
issues, pull requests or CI artifacts. Local backups remain Git-ignored. Publication
hooks and index/history allowlists are additional checks, not complete secret detection.
A tracked file or a deleted historical blob can still be public. See
[publication safeguards](docs/publishing.md).

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/gh-slee/inkkit/security/advisories/new)
for disk-safety bypasses, unsafe archive extraction or potential credential exposure.
If that feature is unavailable, contact the maintainer through the GitHub profile to
arrange a private channel before sharing sensitive details. Do not post private data
or an exploitable disk-erasure reproduction in a public issue.

Include version, macOS/Python, reader type, stage of failure and a minimal **synthetic**
reproduction. Never format real media to reproduce a security report. Stop using a
suspect workflow and preserve the original card and verified backup. If credentials
were published, revoke them; deleting a file does not erase Git history or downloaded copies.
