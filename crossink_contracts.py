"""Source-pinned CrossInk release contracts known to InkKit.

Each entry records the official release tag, its commit and the freeink-sdk
submodule pin read from uxjulia/CrossInk. `access` states what this bundled
engine implements for that release, not what the firmware itself supports:

- `edit`: the audited schema/codec in crossink_profile.py and inkkit_schema.py.
  Releases older than the audited one expose only the reviewed subset listed in
  inkkit_schema.RELEASE_SETTINGS/RELEASE_STORES.
- `backup`: exact-byte complete configuration backup/restore for the same card
  and reader only. Settings are neither interpreted nor edited.

Readers appear only from the release whose changelog first ships firmware for
them. Releases before 1.3.3 store settings in `settings.json`, a name shared with
other firmware, and remain unsupported. Run scripts/extract_crossink_contract.py
against a local checkout to review a new release before adding it here.
"""

SOURCE = 'https://github.com/uxjulia/CrossInk'
EDGE_READERS = ('X3', 'X4')
ALL_READERS = ('X3', 'X4', 'X4 Classic', 'X4 Pro')

RELEASES = (
    dict(firmware='1.6.1', commit='9914146eeae7b46b300f475a16c32426fc02ec1f',
         sdk='699370183fa3a0e33c9cb83a36f701bbb6022095', access='edit', models=ALL_READERS),
    dict(firmware='1.6.0', commit='b25beb13761d5851f98e7eada09aa5e7d430df48',
         sdk='b784446302c076b4b5a622627867f0c80905cc50', access='edit', models=ALL_READERS),
    dict(firmware='1.5.1', commit='4f2da6b7777b9a38fdf2606796d6da34caa7d2cb',
         sdk='9f4d3f9ca675e64cc9d616081f39a33cdefce57e', access='edit', models=ALL_READERS),
    dict(firmware='1.5.0', commit='0de623ed24acd94ae2301e8e1f4a42e32613110b',
         sdk='1ff020263cd2202ea79ce3eb811f5ac8489b8cde', access='backup', models=EDGE_READERS),
    dict(firmware='1.4.0.1', commit='54ba245fe8b6dbfcc566edfd175eb36d76c644ad',
         sdk='92303ba5e4d4f762bb2f9126a3e31c303d66eb28', access='backup', models=EDGE_READERS),
    dict(firmware='1.4.0', commit='b7f6708f96d05e5851f8bcfaaf57bc0e91dc0567',
         sdk='e93f67a4fb19c75fc6b3cb692f28ac3dec8d9e59', access='backup', models=EDGE_READERS),
    dict(firmware='1.3.4', commit='994fb4b9fa7703d38efa0ef8b0ec8319595bd9b2',
         sdk='', access='backup', models=EDGE_READERS),
    dict(firmware='1.3.3', commit='26dc77513c2e277f03458e00d335867140d1e89f',
         sdk='', access='backup', models=EDGE_READERS),
)

# A release newer than every entry above. The user still confirms it; InkKit
# never guesses a version and never edits settings it has not reviewed.
UNREVIEWED = dict(firmware='unreviewed-newer', commit='', sdk='', access='backup', models=ALL_READERS)
