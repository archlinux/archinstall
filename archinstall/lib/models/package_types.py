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
	"""linux-firmware's optional dependencies.

	The metapackage pulls in its hard deps only, so these blobs never reach the
	target: hardware that needs one (a Marvell wifi card, a Mellanox NIC) comes
	up without firmware and there is nothing in the installer that says so.
	Mirrors `pacman -Si linux-firmware` optdepends.
	"""

	LIQUIDIO = 'linux-firmware-liquidio'
	MARVELL = 'linux-firmware-marvell'
	MELLANOX = 'linux-firmware-mellanox'
	NFP = 'linux-firmware-nfp'
	QCOM = 'linux-firmware-qcom'
	QLOGIC = 'linux-firmware-qlogic'
