import dataclasses
import json
from dataclasses import dataclass, field
from typing import Optional, List

from ..general import SysCommand
from ..exceptions import DiskError

@dataclass
class LsblkInfo:
	size: int = 0
	log_sec: int = 0
	pttype: Optional[str] = None
	rota: bool = False
	tran: Optional[str] = None
	ptuuid: Optional[str] = None
	partuuid: Optional[str] = None
	uuid: Optional[str] = None
	fstype: Optional[str] = None
	type: Optional[str] = None
	mountpoints: List[str] = field(default_factory=list)


def get_lsblk_info(dev_path: str) -> LsblkInfo:
	fields = [f.name for f in dataclasses.fields(LsblkInfo)]
	lsblk_fields = ','.join([f.upper().replace('_', '-') for f in fields])

	output = SysCommand(f'lsblk --json -b -o+{lsblk_fields} {dev_path}').decode('UTF-8')

	if output:
		block_devices = json.loads(output)
		info = block_devices['blockdevices'][0]
		lsblk_info = LsblkInfo()

		for f in fields:
			setattr(lsblk_info, f, info[f.replace('_', '-')])

		return lsblk_info

	raise DiskError(f'Failed to read disk "{dev_path}" with lsblk')
