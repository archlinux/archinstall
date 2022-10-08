from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional, List


class EncryptionType(Enum):
	Partition = auto()
	# FullDiskEncryption = auto()


@dataclass
class DiskEncryption:
	encryption_type: EncryptionType = EncryptionType.Partition
	encryption_password: str = ''
	partitions: List[str] = field(default_factory=list)
	hsm_device: Optional[Path] = None
