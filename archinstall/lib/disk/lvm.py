import json
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Literal, overload

from archinstall.lib.command import SysCommand, SysCommandWorker
from archinstall.lib.disk.utils import udev_sync
from archinstall.lib.exceptions import SysCallError
from archinstall.lib.models.device import (
	LvmGroupInfo,
	LvmPVInfo,
	LvmVolume,
	LvmVolumeGroup,
	LvmVolumeInfo,
	SectorSize,
	Size,
	Unit,
)
from archinstall.lib.output import debug


def _lvm_info(
	cmd: str,
	info_type: Literal['lv', 'vg', 'pvseg'],
) -> LvmVolumeInfo | LvmGroupInfo | LvmPVInfo | None:
	raw_info = SysCommand(cmd).decode().split('\n')

	# for whatever reason the output sometimes contains
	# "File descriptor X leaked leaked on vgs invocation
	data = '\n'.join(raw for raw in raw_info if 'File descriptor' not in raw)

	debug(f'LVM info: {data}')

	reports = json.loads(data)

	for report in reports['report']:
		if len(report[info_type]) != 1:
			raise ValueError('Report does not contain any entry')

		entry = report[info_type][0]

		match info_type:
			case 'pvseg':
				return LvmPVInfo(
					pv_name=Path(entry['pv_name']),
					lv_name=entry['lv_name'],
					vg_name=entry['vg_name'],
				)
			case 'lv':
				return LvmVolumeInfo(
					lv_name=entry['lv_name'],
					vg_name=entry['vg_name'],
					lv_size=Size(int(entry['lv_size'][:-1]), Unit.B, SectorSize.default()),
				)
			case 'vg':
				return LvmGroupInfo(
					vg_uuid=entry['vg_uuid'],
					vg_size=Size(int(entry['vg_size'][:-1]), Unit.B, SectorSize.default()),
				)

	return None


@overload
def _lvm_info_with_retry(cmd: str, info_type: Literal['lv']) -> LvmVolumeInfo | None: ...


@overload
def _lvm_info_with_retry(cmd: str, info_type: Literal['vg']) -> LvmGroupInfo | None: ...


@overload
def _lvm_info_with_retry(cmd: str, info_type: Literal['pvseg']) -> LvmPVInfo | None: ...


def _lvm_info_with_retry(
	cmd: str,
	info_type: Literal['lv', 'vg', 'pvseg'],
) -> LvmVolumeInfo | LvmGroupInfo | LvmPVInfo | None:
	# Retry for up to 5 mins
	max_retries = 100
	for attempt in range(max_retries):
		try:
			return _lvm_info(cmd, info_type)
		except ValueError:
			if attempt < max_retries - 1:
				debug(f'LVM info query failed (attempt {attempt + 1}/{max_retries}), retrying in 3 seconds...')
				time.sleep(3)

	debug(f'LVM info query failed after {max_retries} attempts')
	return None


def lvm_vol_info(lv_name: str) -> LvmVolumeInfo | None:
	cmd = f'lvs --reportformat json --unit B -S lv_name={lv_name}'

	return _lvm_info_with_retry(cmd, 'lv')


def lvm_group_info(vg_name: str) -> LvmGroupInfo | None:
	cmd = f'vgs --reportformat json --unit B -o vg_name,vg_uuid,vg_size -S vg_name={vg_name}'

	return _lvm_info_with_retry(cmd, 'vg')


def lvm_pvseg_info(vg_name: str, lv_name: str) -> LvmPVInfo | None:
	cmd = f'pvs --segments -o+lv_name,vg_name -S vg_name={vg_name},lv_name={lv_name} --reportformat json '

	return _lvm_info_with_retry(cmd, 'pvseg')


def lvm_vol_change(vol: LvmVolume, activate: bool) -> None:
	active_flag = 'y' if activate else 'n'
	cmd = f'lvchange -a {active_flag} {vol.safe_dev_path}'

	debug(f'lvchange volume: {cmd}')
	SysCommand(cmd)


def lvm_export_vg(vg: LvmVolumeGroup) -> None:
	cmd = f'vgexport {vg.name}'

	debug(f'vgexport: {cmd}')
	SysCommand(cmd)


def lvm_import_vg(vg: LvmVolumeGroup) -> None:
	# Check if the VG is actually exported before trying to import it
	check_cmd = f'vgs --noheadings -o vg_exported {vg.name}'

	try:
		result = SysCommand(check_cmd)
		is_exported = result.decode().strip() == 'exported'
	except SysCallError:
		# VG might not exist yet, skip import
		debug(f'Volume group {vg.name} not found, skipping import')
		return

	if not is_exported:
		debug(f'Volume group {vg.name} is already active (not exported), skipping import')
		return

	cmd = f'vgimport {vg.name}'
	debug(f'vgimport: {cmd}')
	SysCommand(cmd)


def lvm_vol_reduce(vol_path: Path, amount: Size) -> None:
	val = amount.format_size(Unit.B, include_unit=False)
	cmd = f'lvreduce -L -{val}B {vol_path}'

	debug(f'Reducing LVM volume size: {cmd}')
	SysCommand(cmd)


def lvm_pv_create(pvs: Iterable[Path]) -> None:
	pvs_str = ' '.join(str(pv) for pv in pvs)
	# Signatures are already wiped by wipefs, -f is just for safety
	cmd = f'pvcreate -f --yes {pvs_str}'
	# note flags used in scripting
	debug(f'Creating LVM PVS: {cmd}')
	SysCommand(cmd)

	# Sync with udev to ensure the PVs are visible
	udev_sync()


def lvm_vg_create(pvs: Iterable[Path], vg_name: str) -> None:
	pvs_str = ' '.join(str(pv) for pv in pvs)
	cmd = f'vgcreate --yes --force {vg_name} {pvs_str}'

	debug(f'Creating LVM group: {cmd}')
	SysCommand(cmd)

	# Sync with udev to ensure the VG is visible
	udev_sync()


def lvm_vol_create(vg_name: str, volume: LvmVolume, offset: Size | None = None) -> None:
	if offset is not None:
		length = volume.length - offset
	else:
		length = volume.length

	length_str = length.format_size(Unit.B, include_unit=False)
	cmd = f'lvcreate --yes -L {length_str}B {vg_name} -n {volume.name}'

	debug(f'Creating volume: {cmd}')

	worker = SysCommandWorker(cmd)
	worker.poll()
	worker.write(b'y\n', line_ending=False)

	volume.vg_name = vg_name
	volume.dev_path = Path(f'/dev/{vg_name}/{volume.name}')
