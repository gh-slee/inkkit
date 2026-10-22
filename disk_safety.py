"""Fail-closed macOS storage policy. All queries are injected for synthetic tests."""
import re
from pathlib import Path

MAX_CARD_BYTES = 2 * 1024**4  # Conservative beta ceiling, not hardware certification.


def confirmed_apfs_store(info, disk):
    """Confirm a whole disk already named by APFS PhysicalStores topology.

    Some internal Apple Fabric SSDs report Unknown despite being the physical
    store. This narrow fallback is not a removable-target eligibility rule.
    """
    kind = str(info.get('VirtualOrPhysical', '')).lower()
    protocol = str(info.get('BusProtocol') or info.get('Protocol') or '').lower()
    if (kind == 'virtual' or info.get('Virtual') is True or
            any(term in protocol for term in ('disk image', 'diskimage', 'file-backed')) or
            info.get('WholeDisk') is False or info.get('DeviceIdentifier', disk) != disk):
        return False
    if kind == 'physical':
        return True
    removable = info.get('Removable')
    fixed = (removable is None or removable is False or
             isinstance(removable, str) and removable.lower() in ('fixed', 'false', 'no', '0'))
    return (kind in ('', 'unknown') and info.get('DeviceIdentifier') == disk and
            info.get('WholeDisk') is True and info.get('Internal') is True and
            info.get('RemovableMedia') is False and protocol == 'apple fabric' and
            fixed and
            (info.get('Virtual') is None or info.get('Virtual') is False))


def physical_disks(path, query, error):
    """Resolve a path through its mount and APFS physical stores, never by prefix."""
    path = Path(path).expanduser().resolve(strict=True)
    while not path.is_dir():
        path = path.parent
    device = path.stat().st_dev
    while path.parent != path and path.parent.stat().st_dev == device:
        path = path.parent
    info = query('info', str(path))
    identifier = info.get('ParentWholeDisk') or info.get('DeviceIdentifier')
    if not isinstance(identifier, str) or not re.fullmatch(r'disk\d+(?:s\d+)*', identifier):
        raise error('Cannot resolve a protected location to physical storage; refusing disk writes.')
    whole = re.match(r'disk\d+', identifier).group()  # diskN, excluding partition suffixes
    whole_info = query('info', whole)
    if str(whole_info.get('VirtualOrPhysical', '')).lower() == 'physical':
        return {whole}
    containers = query('apfs', 'list').get('Containers', [])
    for container in containers:
        if container.get('ContainerReference') == whole:
            stores = container.get('PhysicalStores', [])
            result = set()
            for store in stores:
                name = store.get('DeviceIdentifier', '')
                if not re.fullmatch(r'disk\d+s\d+', name):
                    raise error('Unrecognized APFS physical store; refusing disk writes.')
                disk = re.match(r'disk\d+', name).group()
                if not confirmed_apfs_store(query('info', disk), disk):
                    raise error('Unconfirmed APFS physical store; refusing disk writes.')
                result.add(disk)
            if result:
                return result
    raise error('Physical storage identity is unavailable for a protected location; refusing disk writes.')


def hardware_identity(disk):
    info = disk.get('info', {})
    return tuple(info.get(k) for k in (
        'DeviceIdentifier', 'DeviceNode', 'TotalSize', 'MediaName', 'DeviceMediaName',
        'BusProtocol', 'Protocol', 'Internal', 'DeviceLocation', 'RemovableMedia',
        'Removable', 'VirtualOrPhysical', 'DeviceTreePath',
        'IORegistryEntryName', 'SolidState', 'Writable', 'ReadOnlyMedia'))


def target_identity(disk, error):
    info = disk.get('info', {})
    protocol = str(info.get('BusProtocol') or info.get('Protocol') or '').lower()
    removable = any(info.get(k) is True or str(info.get(k)).lower() in
                    ('removable', 'true', 'yes', '1') for k in ('RemovableMedia', 'Removable'))
    if (info.get('WholeDisk') is not True or not removable or
            str(info.get('VirtualOrPhysical', '')).lower() not in ('physical', 'unknown') or
            protocol not in ('usb', 'secure digital', 'sd', 'sd card') or
            type(disk.get('size')) is not int or not 0 < disk['size'] <= MAX_CARD_BYTES or
            info.get('Writable') is not True or info.get('ReadOnlyMedia') is True):
        raise error('Target must be confirmed writable removable USB/SD media, <=2 TiB; fixed/unknown disks are blocked.')
    if info.get('DeviceIdentifier') != disk.get('id') or not re.fullmatch(r'disk\d+', disk['id']):
        raise error('Target whole-disk identity is incomplete.')
    parts = disk.get('partitions', [])
    if len(parts) != 1 or not parts[0].get('mount'):
        raise error('Target needs exactly one mounted FAT32/exFAT partition for reliable identification.')
    part = parts[0]
    pinfo = part.get('info', {})
    if pinfo.get('ParentWholeDisk') != disk['id']:
        raise error('Target partition parent changed.')
    fs = str(part.get('fstype', '')).upper().replace('-', '').replace(' ', '').replace('_', '')
    if 'FAT32' not in fs and 'EXFAT' not in fs:
        raise error('Only an existing FAT32/exFAT target is supported in this beta.')
    mount = Path(part['mount'])
    # Neither a reader's name nor its capacity is a unique card identity.
    uuid = pinfo.get('VolumeUUID') or pinfo.get('DiskUUID')
    if not uuid or not mount.is_dir() or mount.is_symlink():
        raise error('Target volume UUID/mount identity unavailable; refusing erase.')
    flags = ' '.join(str(pinfo.get(k, '')) for k in ('APFSVolumeRole', 'Roles', 'Content', 'VolumeName')).lower()
    if ('time machine' in flags or 'backup' in flags or
            any((mount / n).exists() for n in ('Backups.backupdb', '.timemachine'))):
        raise error('Time Machine/backup storage is protected.')
    return (hardware_identity(disk), str(uuid), part.get('id'),
            str(mount.resolve(strict=True)), mount.stat().st_dev,
            tuple(sorted((str(k), repr(v)) for k, v in pinfo.items())),
            tuple(info.get(k) for k in ('MediaUUID', 'DiskUUID', 'Content', 'PartitionMapPartition')))


def protect_locations(target, paths, query, error):
    for path in paths:
        if target['id'] in physical_disks(path, query, error):
            raise error('Target contains the backup, program, working directory, or system; refusing erase.')
