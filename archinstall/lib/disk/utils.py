from pathlib import Path

from pydantic import BaseModel

from archinstall.lib.exceptions import DiskError, SysCallError
from archinstall.lib.general import SysCommand
from archinstall.lib.models.device import LsblkInfo
from archinstall.lib.output import debug, warn


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
	info: list[LsblkInfo],
) -> LsblkInfo | None:
	if isinstance(dev_path, str):
		dev_path = Path(dev_path)

	for lsblk_info in info:
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
