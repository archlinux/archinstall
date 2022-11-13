from __future__ import annotations

import dataclasses
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional, List, Any, Dict, Union

from ..general import SysCommand
from ..exceptions import DiskError, SysCallError
from ..output import log


@dataclass
class LsblkInfo:
	name: str = ""
	path: Path = Path()
	pkname: str = ""
	size: int = 0
	log_sec: int = 0
	pttype: str = ""
	ptuuid: str = ""
	rota: bool = False
	tran: Optional[str] = None
	partuuid: Optional[str] = None
	uuid: Optional[str] = None
	fstype: Optional[str] = None
	fsver: Optional[str] = None
	fsavail: Optional[str] = None
	fsuse_percentage: Optional[str] = None
	type: Optional[str] = None
	mountpoints: List[str] = field(default_factory=list)
	children: List[LsblkInfo] = field(default_factory=list)

	def json(self):
		return dataclasses.asdict(self)

	@classmethod
	def exclude(cls) -> List[str]:
		return ['children']

	@classmethod
	def fields(cls) -> List[str]:
		return [f.name for f in dataclasses.fields(LsblkInfo) if f.name not in cls.exclude()]

	@classmethod
	def from_json(cls, blockdevice: Dict[str, Any]) -> LsblkInfo:
		info = cls()

		for f in cls.fields():
			blk_field = _clean_field(f, CleanType.Blockdevice)
			data_field = _clean_field(f, CleanType.Dataclass)

			if type(getattr(info, data_field)) == Path:
				val = Path(blockdevice[blk_field])
			else:
				val = blockdevice[blk_field]

			setattr(info, data_field, val)

		info.children = [LsblkInfo.from_json(child) for child in blockdevice.get('children', [])]

		# sometimes lsblk returns 'mountpoint': [null]
		info.mountpoints = [mountpoint for mountpoint in info.mountpoints if mountpoint]

		return info


class CleanType(Enum):
	Blockdevice = auto()
	Dataclass = auto()
	Lsblk = auto()


def _clean_field(name: str, clean_type: CleanType) -> str:
	match clean_type:
		case CleanType.Blockdevice:
			return name.replace('_percentage', '%').replace('_', '-')
		case CleanType.Dataclass:
			return name.lower().replace('-', '_').replace('%', '_percentage')
		case CleanType.Lsblk:
			return name.replace('_percentage', '%').replace('_', '-').upper()


def _fetch_lsblk_info(dev_path: Optional[Union[Path, str]] = None, retry: int = 3) -> List[LsblkInfo]:
	fields = [_clean_field(f, CleanType.Lsblk) for f in LsblkInfo.fields()]
	lsblk_fields = ','.join(fields)

	if not dev_path:
		dev_path = ''

	try:
		result = SysCommand(f'lsblk --json -b -o+{lsblk_fields} {dev_path}')
	except SysCallError as error:
		# It appears as if lsblk can return exit codes like 8192 to indicate something.
		# But it does return output so we'll try to catch it.
		if error.worker:
			err = error.worker.decode('UTF-8')
			log(f'Error calling lsblk: {err}', fg="red", level=logging.ERROR)

			if retry > 0:
				log('Retrying fetching info with lsblk...', level=logging.INFO)
				time.sleep(1)
				return _fetch_lsblk_info(dev_path, retry - 1)
		raise error

	if result.exit_code == 0:
		try:
			if decoded := result.decode('utf-8'):
				block_devices = json.loads(decoded)
				blockdevices = block_devices['blockdevices']
				return [LsblkInfo.from_json(device) for device in blockdevices]
		except json.decoder.JSONDecodeError as err:
			log(f"Could not decode lsblk JSON: {result}", fg="red", level=logging.ERROR)
			raise err

	raise DiskError(f'Failed to read disk "{dev_path}" with lsblk')


def get_lsblk_info(dev_path: Union[Path, str]) -> Optional[LsblkInfo]:
	if infos := _fetch_lsblk_info(dev_path):
		info = next(filter(lambda x: x.path == dev_path, infos), None)
		return info

	raise DiskError(f'lsblk failed to retrieve information for "{dev_path}"')


def get_all_lsblk_info() -> List[LsblkInfo]:
	return _fetch_lsblk_info()
