from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, TYPE_CHECKING, Any

from ..hsm.fido import Fido2Device

if TYPE_CHECKING:
	_: Any


class EncryptionType(Enum):
	Partition = auto()
	# FullDiskEncryption = auto()

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
	partitions: List[str] = field(default_factory=list)
	hsm_device: Optional[Fido2Device] = None

	def generate_encryption_file(self, partition) -> bool:
		return partition in self.partitions and partition['mountpoint'] != '/'
	
