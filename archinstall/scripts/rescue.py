import subprocess
from pathlib import Path

from archinstall.lib.args import arch_config_handler
from archinstall.lib.disk.utils import get_all_lsblk_info
from archinstall.lib.models.device import LsblkInfo, Unit
from archinstall.lib.output import error, info, warn
from archinstall.tui import Tui
from archinstall.tui.curses_menu import SelectMenu
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType
from archinstall.tui.types import Alignment


def find_linux_partitions(lsblk_infos: list[LsblkInfo]) -> list[LsblkInfo]:
	"""
	Find all partitions that might contain a Linux root filesystem.
	Looks for ext4, btrfs, xfs filesystems that are not currently mounted.
	"""
	linux_partitions = []

	def _check_partition(lsblk_info: LsblkInfo) -> None:
		# Check if it's a partition or LVM volume with a Linux filesystem
		if lsblk_info.fstype in ['ext4', 'btrfs', 'xfs', 'ext3', 'ext2', 'f2fs']:
			# Include partitions that are not mounted or mounted elsewhere (not on /mnt or /)
			if not lsblk_info.mountpoints or all(str(mp) not in ['/', '/mnt'] for mp in lsblk_info.mountpoints):
				linux_partitions.append(lsblk_info)

		# Recursively check children (for LVM, etc.)
		for child in lsblk_info.children:
			_check_partition(child)

	for device in lsblk_infos:
		_check_partition(device)

	return linux_partitions


def verify_linux_root(mount_point: Path) -> bool:
	"""
	Verify that the mounted partition contains a Linux root filesystem.
	Checks for the presence of key directories and files.
	"""
	required_paths = [
		mount_point / 'etc',
		mount_point / 'usr',
		mount_point / 'var',
	]

	# Check for required directories
	for path in required_paths:
		if not path.exists():
			return False

	# Check for os-release (standard on most modern Linux distros)
	os_release = mount_point / 'etc' / 'os-release'

	return os_release.exists()


def mount_partition(partition: LsblkInfo, mount_point: Path) -> bool:
	"""Mount a partition to the specified mount point."""
	try:
		info(f'Mounting {partition.path} to {mount_point}...')
		subprocess.run(['mount', str(partition.path), str(mount_point)], check=True, capture_output=True)
		return True
	except subprocess.CalledProcessError as e:
		error(f'Failed to mount {partition.path}: {e.stderr.decode()}')
		return False


def mount_additional_filesystems(mount_point: Path) -> None:
	"""
	Try to mount additional filesystems based on /etc/fstab in the mounted root.
	This includes /boot, /boot/efi, /home, etc.
	"""
	fstab_path = mount_point / 'etc' / 'fstab'

	if not fstab_path.exists():
		warn('No /etc/fstab found, skipping additional mounts')
		return

	info('Reading /etc/fstab to mount additional filesystems...')

	try:
		with open(fstab_path) as f:
			for line in f:
				line = line.strip()

				# Skip comments and empty lines
				if not line or line.startswith('#'):
					continue

				parts = line.split()
				if len(parts) < 3:
					continue

				device, mountpoint, fstype = parts[0], parts[1], parts[2]

				# Skip the root filesystem and special filesystems
				if mountpoint in ['/', 'none', 'swap'] or mountpoint.startswith(('/proc', '/sys', '/dev', '/run')):
					continue

				# Skip swap
				if fstype == 'swap':
					continue

				target_path = mount_point / mountpoint.lstrip('/')

				# Create mount point if it doesn't exist
				if not target_path.exists():
					target_path.mkdir(parents=True, exist_ok=True)

				try:
					# Try to mount the filesystem
					subprocess.run(['mount', device, str(target_path)], check=True, capture_output=True, timeout=5)
					info(f'Mounted {device} to {target_path}')
				except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
					warn(f'Could not mount {device} to {target_path}, skipping...')

	except Exception as e:
		warn(f'Error reading fstab: {e}')


def unmount_all(mount_point: Path) -> None:
	"""Unmount all filesystems under the mount point."""
	info('Unmounting filesystems...')

	# Unmount in reverse order (important for nested mounts)
	max_attempts = 3
	for attempt in range(max_attempts):
		try:
			subprocess.run(['umount', '--recursive', str(mount_point)], check=True, capture_output=True, timeout=10)
			info('All filesystems unmounted successfully')
			return
		except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
			if attempt < max_attempts - 1:
				warn(f'Unmount attempt {attempt + 1} failed, retrying...')
				import time

				time.sleep(1)
			else:
				error('Failed to unmount all filesystems. You may need to unmount manually.')


def select_partition(partitions: list[LsblkInfo]) -> LsblkInfo | None:
	"""Display a menu for the user to select a partition."""

	def _preview_partition(item: MenuItem) -> str | None:
		partition: LsblkInfo = item.get_value()
		lines = [
			f'Device: {partition.path}',
			f'Name: {partition.name}',
			f'Filesystem: {partition.fstype or "Unknown"}',
			f'Size: {partition.size.format_size(Unit.GiB)}',
			f'UUID: {partition.uuid or "None"}',
		]
		if partition.mountpoints:
			lines.append(f'Currently mounted: {", ".join(str(mp) for mp in partition.mountpoints)}')
		return '\n'.join(lines)

	# Create menu items
	menu_items = []
	for partition in partitions:
		label = f'{partition.name} ({partition.path})'
		if partition.fstype:
			label += f' [{partition.fstype}]'
		label += f' - {partition.size.format_size(Unit.GiB)}'

		item = MenuItem(
			text=label,
			value=partition,
			preview_action=_preview_partition,
		)
		menu_items.append(item)

	group = MenuItemGroup(menu_items, sort_items=False)

	result = SelectMenu[LsblkInfo](
		group,
		alignment=Alignment.CENTER,
		header='Select a partition containing the Linux installation to rescue:',
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case _:
			return None


def rescue() -> None:
	"""Main rescue mode entry point."""
	info('This utility will help you mount and chroot into an existing installation.')

	# Get all block devices
	info('Scanning for block devices...')
	all_devices = get_all_lsblk_info()

	# Find potential Linux partitions
	linux_partitions = find_linux_partitions(all_devices)

	if not linux_partitions:
		error('No Linux partitions found. Make sure your disks are properly connected.')
		return

	info(f'Found {len(linux_partitions)} potential Linux partition(s)')

	# Let user select a partition
	with Tui():
		selected_partition = select_partition(linux_partitions)

	if not selected_partition:
		info('No partition selected. Exiting rescue mode.')
		return

	info(f'Selected partition: {selected_partition.path}')

	# Create temporary mount point
	mount_point = arch_config_handler.args.mountpoint

	# Ensure mount point exists
	mount_point.mkdir(parents=True, exist_ok=True)

	# Mount the root partition
	if not mount_partition(selected_partition, mount_point):
		return

	# Verify it's a Linux root filesystem
	if not verify_linux_root(mount_point):
		error(f'{selected_partition.path} does not appear to contain a valid Linux root filesystem.')
		unmount_all(mount_point)
		return

	info('Linux root filesystem verified!')

	# Mount additional filesystems from fstab
	mount_additional_filesystems(mount_point)

	# Display information
	info('')
	info(f'Installation mounted at: {mount_point}')
	info('Entering chroot environment...')
	info('Note: arch-chroot will automatically mount /dev, /proc, /sys, and handle DNS.')
	info('Type "exit" to leave the chroot and return to the live environment.')
	info('')

	# Chroot into the system
	try:
		subprocess.run(
			['arch-chroot', str(mount_point)],
			check=False,  # Don't raise on non-zero exit, as user might exit normally
		)
	except KeyboardInterrupt:
		info('\nChroot interrupted.')
	except Exception as e:
		error(f'Error during chroot: {e}')

	# Cleanup
	info('')
	unmount_all(mount_point)
	info('Rescue mode completed.')


# Entry point - automatically run when module is loaded
rescue()
