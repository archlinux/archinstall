from enum import StrEnum, auto
from typing import Final


class Kernel(StrEnum):
	LINUX = auto()
	LINUX_LTS = 'linux-lts'
	LINUX_ZEN = 'linux-zen'
	LINUX_HARDENED = 'linux-hardened'
	LINUX_RT = 'linux-rt'
	LINUX_RT_LTS = 'linux-rt-lts'


DEFAULT_KERNEL: Final = Kernel.LINUX


class FirmwareOptdep(StrEnum):
	"""
	The optional dependencies of linux-firmware.

	The metapackage installs its hard dependencies only, so these blobs are
	never present on the target unless they are requested explicitly.
	"""

	LIQUIDIO = 'linux-firmware-liquidio'
	MARVELL = 'linux-firmware-marvell'
	MELLANOX = 'linux-firmware-mellanox'
	NFP = 'linux-firmware-nfp'
	QCOM = 'linux-firmware-qcom'
	QLOGIC = 'linux-firmware-qlogic'
