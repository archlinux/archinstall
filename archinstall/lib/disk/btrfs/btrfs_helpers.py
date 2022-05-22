import re
import pathlib
from typing import Dict, Any, Iterator, TYPE_CHECKING, Optional

if TYPE_CHECKING:
	from ...installer import Installer

from ...exceptions import SysCallError
from ...general import SysCommand
from ..helpers import get_mount_info
from .btrfssubvolume import BtrfsSubvolume

def get_subvolumes_from_findmnt(struct :Dict[str, Any], index=0) -> Iterator[BtrfsSubvolume]:
	if '[' in struct['source']:
		subvolume = re.findall(r'\[.*?\]', struct['source'])[0][1:-1]
		struct['source'] = struct['source'].replace(f"[{subvolume}]", "")
		yield BtrfsSubvolume(
			target=struct['target'],
			source=struct['source'],
			fstype=struct['fstype'],
			name=subvolume,
			options=struct['options'],
			root=index == 0
		)
		index += 1

		for child in struct.get('children', []):
			for item in get_subvolumes_from_findmnt(child, index=index):
				yield item
				index += 1

def subvolume_info_from_path(path :pathlib.Path) -> Optional[BtrfsSubvolume]:
	try:
		subvolume_name = None
		result = {}
		for index, line in enumerate(SysCommand(f"btrfs subvolume show {path}")):
			if index == 0:
				subvolume_name = line.strip().decode('UTF-8')
				continue

			if b':' in line:
				key, value = line.strip().decode('UTF-8').split(':', 1)

				# A bit of a hack, until I figure out how @dataclass
				# allows for hooking in a pre-processor to do this we have to do it here:
				result[key.lower().replace(' ', '_').replace('(s)', 's')] = value.strip()

		return BtrfsSubvolume(**{'full_path' : path, **result})

	except SysCallError:
		pass

	return None

def find_parent_subvolume(path :pathlib.Path, filters=[]):
	# A root path cannot have a parent
	if str(path) == '/':
		return None

	if found_mount := get_mount_info(str(path.parent), traverse=True, ignore=filters):
		if not (subvolume := subvolume_info_from_path(found_mount['target'])):
			if found_mount['target'] == '/':
				return None 

			return find_parent_subvolume(path.parent, traverse=True, filters=[*filters, found_mount['target']])

		return subvolume

