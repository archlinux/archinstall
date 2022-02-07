import pathlib
import logging
import json
from dataclasses import dataclass
from typing import Optional
from ..exceptions import SysCallError
from ..general import SysCommand
from ..output import log
from .mapperdev import MapperDev

@dataclass
class DMCryptDev:
	dev_path :pathlib.Path

	@property
	def name(self):
		with open(f"/sys/devices/virtual/block/{pathlib.Path(self.path).name}/dm/name", "r") as fh:
			return fh.read().strip()

	@property
	def path(self):
		return f"/dev/mapper/{self.dev_path}"

	@property
	def blockdev(self):
		pass

	@property
	def MapperDev(self):
		return MapperDev(mappername=self.name)

	@property
	def mountpoint(self) -> Optional[str]:
		try:
			data = json.loads(SysCommand(f"findmnt --json -R {self.dev_path}").decode())
			for filesystem in data['filesystems']:
				return filesystem.get('target')

		except SysCallError as error:
			# Not mounted anywhere most likely
			log(f"Could not locate mount information for {self.dev_path}: {error}", level=logging.WARNING, fg="yellow")
			pass

		return None

	@property
	def filesystem(self) -> Optional[str]:
		return self.MapperDev.filesystem