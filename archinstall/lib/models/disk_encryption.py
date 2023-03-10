from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, TYPE_CHECKING, Any

from ..hsm.fido import Fido2Device

if TYPE_CHECKING:
	_: Any


class EncryptionType(Enum):
	Partition = 'partition'

	@classmethod
	def _encryption_type_mapper(cls) -> Dict[str, 'EncryptionType']:
		return {
			# str(_('Full disk encryption')): EncryptionType.FullDiskEncryption,
			str(_('Partition encryption')): EncryptionType.Partition
		}

	@classmethod
	def text_to_type(cls, text: str) -> 'EncryptionType':
		mapping = cls._encryption_type_mapper()
		return mapping[text]

	@classmethod
	def type_to_text(cls, type_: 'EncryptionType') -> str:
		mapping = cls._encryption_type_mapper()
		type_to_text = {type_: text for text, type_ in mapping.items()}
		return type_to_text[type_]


@dataclass
class DiskEncryption:
	encryption_type: EncryptionType = EncryptionType.Partition
	encryption_password: str = ''
	partitions: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
	hsm_device: Optional[Fido2Device] = None

	@property
	def all_partitions(self) -> List[Dict[str, Any]]:
		_all: List[Dict[str, Any]] = []
		for parts in self.partitions.values():
			_all += parts
		return _all

	def generate_encryption_file(self, partition) -> bool:
		return partition in self.all_partitions and partition['mountpoint'] != '/'

	def json(self) -> Dict[str, Any]:
		obj = {
			'encryption_type': self.encryption_type.value,
			'partitions': self.partitions
		}

		if self.hsm_device:
			obj['hsm_device'] = self.hsm_device.json()

		return obj

	@classmethod
	def parse_arg(
		cls,
		disk_layout: Dict[str, Any],
		arg: Dict[str, Any],
		password: str = ''
	) -> 'DiskEncryption':
		# we have to map the enc partition config to the disk layout objects
		# they both need to point to the same object as it will get modified
		# during the installation process
		enc_partitions: Dict[str, List[Dict[str, Any]]] = {}

		for path, partitions in disk_layout.items():
			conf_partitions = arg['partitions'].get(path, [])
			for part in partitions['partitions']:
				if part in conf_partitions:
					enc_partitions.setdefault(path, []).append(part)

		enc = DiskEncryption(
			EncryptionType(arg['encryption_type']),
			password,
			enc_partitions
		)

		if hsm := arg.get('hsm_device', None):
			enc.hsm_device = Fido2Device.parse_arg(hsm)

		return enc
