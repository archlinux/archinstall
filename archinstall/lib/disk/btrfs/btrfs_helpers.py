import re
from typing import Dict, Any, Iterator, TYPE_CHECKING

if TYPE_CHECKING:
	from ...installer import Installer

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