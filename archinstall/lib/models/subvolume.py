from dataclasses import dataclass
from typing import List, Any, Dict


@dataclass
class Subvolume:
	name: str
	mountpoint: str
	compress: bool = False
	nodatacow: bool = False

	def display(self) -> str:
		options_str = ','.join(self.options)
		return f'{_("Subvolume")}: {self.name:15} {_("Mountpoint")}: {self.mountpoint:20} {_("Options")}: {options_str}'

	@property
	def options(self) -> List[str]:
		options = [
			'compress' if self.compress else '',
			'nodatacow' if self.nodatacow else ''
		]
		return [o for o in options if len(o)]

	def json(self) -> Dict[str, Any]:
		return {
			'name': self.name,
			'mountpoint': self.mountpoint,
			'compress': self.compress,
			'nodatacow': self.nodatacow
		}
