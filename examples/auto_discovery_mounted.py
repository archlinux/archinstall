from pathlib import Path

from archinstall import DiskLayoutConfiguration
from archinstall.lib.disk import device_handler
from archinstall.lib.disk.device_model import DiskLayoutType

root_mount_dir = Path('/mnt/archinstall')

mods = device_handler.detect_pre_mounted_mods(root_mount_dir)

disk_config = DiskLayoutConfiguration(
	DiskLayoutType.Pre_mount,
	device_modifications=mods,
	relative_mountpoint=Path('/mnt/archinstall')
)
