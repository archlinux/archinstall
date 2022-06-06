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

	@classmethod
	def _parse(cls, config_subvolumes: List[Dict[str, Any]]) -> List['Subvolume']:
		subvolumes = []
		for entry in config_subvolumes:
			if not entry.get('name', None) or not entry.get('mountpoint', None):
				continue

			subvolumes.append(
				Subvolume(
					entry['name'],
					entry['mountpoint'],
					entry.get('compress', False),
					entry.get('nodatacow', False)
				)
			)

		return subvolumes

	@classmethod
	def _parse_backwards_compatible(cls, config_subvolumes) -> List['Subvolume']:
		subvolumes = []
		for name, mountpoint in config_subvolumes.items():
			if not name or not mountpoint:
				continue

			subvolumes.append(Subvolume(name, mountpoint))

		return subvolumes

	@classmethod
	def parse_arguments(cls, config_subvolumes: Any) -> List['Subvolume']:
		if isinstance(config_subvolumes, list):
			return cls._parse(config_subvolumes)
		elif isinstance(config_subvolumes, dict):
			return cls._parse_backwards_compatible(config_subvolumes)

		raise ValueError('Unknown disk layout btrfs subvolume format')
