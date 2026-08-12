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
