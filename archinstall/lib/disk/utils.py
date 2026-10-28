from pathlib import Path
from subprocess import CalledProcessError

from pydantic import BaseModel

from archinstall.lib.command import SysCommand, run
from archinstall.lib.exceptions import DiskError, SysCallError
from archinstall.lib.log import debug, info, warn
from archinstall.lib.models.device import LsblkInfo, PartitionGUID


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
		result = run(cmd)
	except CalledProcessError as err:
		# Get the output minus the message/info from lsblk if it returns a non-zero exit code.
		if stdout := err.stdout:
			debug(f'Error calling lsblk: {stdout.decode().rstrip()}')

		if dev_path:
			raise DiskError(f'Failed to read disk "{dev_path}" with lsblk')

		raise err

	return LsblkOutput.model_validate_json(result.stdout)


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


def udev_sync() -> None:
	try:
		SysCommand('udevadm settle')
	except SysCallError as err:
		debug(f'Failed to synchronize with udev: {err}')


def mount(
	dev_path: Path | str,
	target_mountpoint: Path,
	mount_fs: str | None = None,
	create_target_mountpoint: bool = True,
	options: list[str] | None = None,
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

	if options:
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


def active_swaps() -> list[Path]:
	"""
	Currently active swap areas, as reported by the kernel.

	The first column of /proc/swaps is the area itself, either a block device
	(e.g. /dev/dm-0) or a regular file (e.g. /mnt/swapfile). lsblk's '[SWAP]'
	marker is a display convention, not state, and must not be used to decide
	whether swap is active.
	"""
	entries: list[Path] = []
	for line in Path('/proc/swaps').read_text().splitlines()[1:]:
		if not (fields := line.split()):
			continue
		entries.append(Path(fields[0]))

	return entries


def _swap_areas_of(target: Path, mountpoints: list[Path] | None = None) -> list[Path]:
	areas: list[Path] = []

	for area in active_swaps():
		# /proc/swaps reports resolved names (e.g. /dev/dm-0) while callers hold
		# symlinks (e.g. /dev/mapper/root), so compare resolved paths
		if area.exists() and target.exists():
			if area.resolve() == target.resolve():
				areas.append(area)
				continue
		elif area == target:
			areas.append(area)
			continue

		if area.is_absolute():
			for mountpoint in mountpoints or []:
				# lsblk reports '[SWAP]' for an active swap area; that is a display
				# marker, not a path, and nothing can live below it
				if mountpoint.is_absolute() and area.is_relative_to(mountpoint):
					areas.append(area)
					break

	return areas


def umount(mountpoint: Path | str, recursive: bool = False) -> None:
	lsblk_info = get_lsblk_info(mountpoint)

	if not lsblk_info.mountpoints:
		return

	debug(f'Partition {mountpoint} is currently mounted at: {[str(m) for m in lsblk_info.mountpoints]}')

	cmd = ['umount']

	if recursive:
		cmd.append('-R')

	for path in lsblk_info.mountpoints:
		debug(f'Unmounting mountpoint: {path}')
		SysCommand([*cmd, str(path)])


def swapon(path: Path) -> None:
	"""
	Activate the swap area at ``path``, unless the kernel already reports it.

	The layout is mounted into a fresh target, but swap is machine-wide state:
	a previous run of the installer (or the running live system) may have left
	this very area active, in which case ``swapon`` fails with "Device or
	resource busy" and the installation aborts for no reason.
	"""
	if _swap_areas_of(path):
		debug(f'Swap is already active on {path}')
		return

	try:
		SysCommand(['swapon', str(path)])
	except SysCallError as err:
		raise DiskError(f'Could not enable swap {path}:\n{err.message}')

	if not _swap_areas_of(path):
		raise DiskError(f'Swap was not activated on {path}, the kernel reports no swap area for it')


def swapoff(path: Path, mountpoints: list[Path] | None = None) -> None:
	"""
	Deactivate every swap area belonging to ``path``.

	``mountpoints`` lets the caller pass the mountpoints of ``path`` so that a
	swapfile living on it is found as well. A no-op is only correct when the
	kernel reports no swap area for ``path``; if anything is still active
	afterwards this raises instead of leaving the caller to fail later.
	"""
	areas = _swap_areas_of(path, mountpoints)
	if not areas:
		return

	for area in areas:
		debug(f'Disabling swap on: {area}')
		try:
			SysCommand(['swapoff', str(area)])
		except SysCallError as err:
			raise DiskError(f'Could not disable swap {area}:\n{err.message}')

	if remaining := _swap_areas_of(path, mountpoints):
		raise DiskError(f'Swap is still active on {path}: {[str(a) for a in remaining]}')


def linux_root_guid(arch: str | None) -> PartitionGUID:
	if arch == 'aarch64':
		return PartitionGUID.LINUX_ROOT_AARCH64

	return PartitionGUID.LINUX_ROOT_X86_64
