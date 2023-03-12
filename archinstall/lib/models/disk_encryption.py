from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, TYPE_CHECKING, Any

from ..disk.device_handler import PartitionModification
from ..disk.fido import Fido2Device
from ..disk.device_model import DiskLayoutConfiguration

if TYPE_CHECKING:
	_: Any


class EncryptionType(Enum):
	NoEncryption = "no_encryption"
	Partition = "partition"

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
	partitions: List[PartitionModification] = field(default_factory=list)
	hsm_device: Optional[Fido2Device] = None

	def should_generate_encryption_file(self, part_mod: PartitionModification) -> bool:
		return part_mod in self.partitions and part_mod.mountpoint != Path('/')

	def json(self) -> Dict[str, Any]:
		obj = {
			'encryption_type': self.encryption_type.value,
			'partitions': [str(p._obj_id) for p in self.partitions]
		}

		if self.hsm_device:
			obj['hsm_device'] = self.hsm_device.json()

		return obj

	@classmethod
	def parse_arg(
		cls,
		disk_config: DiskLayoutConfiguration,
		arg: Dict[str, Any],
		password: str = ''
	) -> 'DiskEncryption':
		enc_partitions = []
		for mod in disk_config.device_modifications:
			for part in mod.partitions:
				if part._obj_id in arg.get('partitions', []):
					enc_partitions.append(part)

		enc = DiskEncryption(
			EncryptionType(arg['encryption_type']),
			password,
			enc_partitions
		)

		if hsm := arg.get('hsm_device', None):
			enc.hsm_device = Fido2Device.parse_arg(hsm)

		return enc
