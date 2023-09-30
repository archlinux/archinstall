from pathlib import Path

from archinstall import disk

root_mount_dir = Path('/mnt/archinstall')

mods = disk.device_handler.detect_pre_mounted_mods(root_mount_dir)

disk_config = disk.DiskLayoutConfiguration(
	disk.DiskLayoutType.Pre_mount,
	device_modifications=mods,
)
