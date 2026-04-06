from pathlib import Path
from typing import Final

from archinstall.lib.linux_path import LPath

ARCHISO_MOUNTPOINT: Final = Path('/run/archiso/airootfs')
PACMAN_CONF: Final = LPath('/etc/pacman.conf')
