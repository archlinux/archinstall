from pathlib import Path

from pydantic import BaseModel

from archinstall.lib.command import SysCommand
from archinstall.lib.exceptions import DiskError, SysCallError
from archinstall.lib.models.device import LsblkInfo
from archinstall.lib.output import debug, info, warn


class LsblkOutput(BaseModel):
	blockdevices: list[LsblkInfo]


def _fetch_lsblk_info(
	dev_path: Path | str | None = None,
	reverse: bool = False,
	full_dev_path: bool = False,
) -> LsblkOutput:
	cmd = ['lsblk', '--json', '--bytes', '--output', ','.join(LsblkInfo.fields())]

	if reverse:
		cmd.append('--inverse')

	if full_dev_path:
		cmd.append('--paths')

	if dev_path:
		cmd.append(str(dev_path))

	try:
		worker = SysCommand(cmd)
	except SysCallError as err:
		# Get the output minus the message/info from lsblk if it returns a non-zero exit code.
		if err.worker_log:
			debug(f'Error calling lsblk: {err.worker_log.decode()}')

		if dev_path:
			raise DiskError(f'Failed to read disk "{dev_path}" with lsblk')

		raise err

	output = worker.output(remove_cr=False)
	return LsblkOutput.model_validate_json(output)


def get_lsblk_info(
	dev_path: Path | str,
	reverse: bool = False,
	full_dev_path: bool = False,
) -> LsblkInfo:
	infos = _fetch_lsblk_info(dev_path, reverse=reverse, full_dev_path=full_dev_path)

	if infos.blockdevices:
		return infos.blockdevices[0]

	raise DiskError(f'lsblk failed to retrieve information for "{dev_path}"')


def get_all_lsblk_info() -> list[LsblkInfo]:
	return _fetch_lsblk_info().blockdevices


def get_lsblk_output() -> LsblkOutput:
	return _fetch_lsblk_info()


def find_lsblk_info(
	dev_path: Path | str,
	info_list: list[LsblkInfo],
) -> LsblkInfo | None:
	if isinstance(dev_path, str):
		dev_path = Path(dev_path)

	for lsblk_info in info_list:
		if lsblk_info.path == dev_path:
			return lsblk_info

	return None


def get_lsblk_by_mountpoint(mountpoint: Path, as_prefix: bool = False) -> list[LsblkInfo]:
	def _check(infos: list[LsblkInfo]) -> list[LsblkInfo]:
		devices = []
		for entry in infos:
			if as_prefix:
				matches = [m for m in entry.mountpoints if str(m).startswith(str(mountpoint))]
				if matches:
					devices += [entry]
			elif mountpoint in entry.mountpoints:
				devices += [entry]

			if len(entry.children) > 0:
				if len(match := _check(entry.children)) > 0:
					devices += match

		return devices

	all_info = get_all_lsblk_info()
	return _check(all_info)


def disk_layouts() -> str:
	try:
		lsblk_output = get_lsblk_output()
	except SysCallError as err:
		warn(f'Could not return disk layouts: {err}')
		return ''

	return lsblk_output.model_dump_json(indent=4)


def get_parent_device_path(dev_path: Path) -> Path:
	lsblk = get_lsblk_info(dev_path)
	return Path(f'/dev/{lsblk.pkname}')


def get_unique_path_for_device(dev_path: Path) -> Path | None:
	paths = Path('/dev/disk/by-id').glob('*')
	linked_targets = {p.resolve(): p for p in paths}
	linked_wwn_targets = {p: linked_targets[p] for p in linked_targets if p.name.startswith('wwn-') or p.name.startswith('nvme-eui.')}

	if dev_path in linked_wwn_targets:
		return linked_wwn_targets[dev_path]

	if dev_path in linked_targets:
		return linked_targets[dev_path]

	return None


def mount(
	dev_path: Path,
	target_mountpoint: Path,
	mount_fs: str | None = None,
	create_target_mountpoint: bool = True,
	options: list[str] = [],
) -> None:
	if create_target_mountpoint and not target_mountpoint.exists():
		target_mountpoint.mkdir(parents=True, exist_ok=True)

	if not target_mountpoint.exists():
		raise ValueError('Target mountpoint does not exist')

	lsblk_info = get_lsblk_info(dev_path)
	if target_mountpoint in lsblk_info.mountpoints:
		info(f'Device already mounted at {target_mountpoint}')
		return

	cmd = ['mount']

	if len(options):
		cmd.extend(('-o', ','.join(options)))
	if mount_fs:
		cmd.extend(('-t', mount_fs))

	cmd.extend((str(dev_path), str(target_mountpoint)))

	command = ' '.join(cmd)

	debug(f'Mounting {dev_path}: {command}')

	try:
		SysCommand(command)
	except SysCallError as err:
		raise DiskError(f'Could not mount {dev_path}: {command}\n{err.message}')


def umount(mountpoint: Path, recursive: bool = False) -> None:
	lsblk_info = get_lsblk_info(mountpoint)

	if not lsblk_info.mountpoints:
		return

	debug(f'Partition {mountpoint} is currently mounted at: {[str(m) for m in lsblk_info.mountpoints]}')

	cmd = ['umount']

	if recursive:
		cmd.append('-R')

	for path in lsblk_info.mountpoints:
		debug(f'Unmounting mountpoint: {path}')
		SysCommand(cmd + [str(path)])


def swapon(path: Path) -> None:
	try:
		SysCommand(['swapon', str(path)])
	except SysCallError as err:
		raise DiskError(f'Could not enable swap {path}:\n{err.message}')
