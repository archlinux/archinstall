from __future__ import annotations
import logging
from typing import Optional, Dict, Any, List, TYPE_CHECKING

# https://stackoverflow.com/a/39757388/929999
from ..models.subvolume import Subvolume

if TYPE_CHECKING:
	from .blockdevice import BlockDevice
	_: Any

from .helpers import sort_block_devices_based_on_performance, select_largest_device, select_disk_larger_than_or_close_to
from ..hardware import has_uefi
from ..output import log
from ..menu import Menu


def suggest_single_disk_layout(block_device :BlockDevice,
	default_filesystem :Optional[str] = None,
	advanced_options :bool = False) -> Dict[str, Any]:

	if not default_filesystem:
		from ..user_interaction import ask_for_main_filesystem_format
		default_filesystem = ask_for_main_filesystem_format(advanced_options)

	MIN_SIZE_TO_ALLOW_HOME_PART = 40 # GiB
	using_subvolumes = False
	using_home_partition = False
	compression = False

	if default_filesystem == 'btrfs':
		prompt = str(_('Would you like to use BTRFS subvolumes with a default structure?'))
		choice = Menu(prompt, Menu.yes_no(), skip=False, default_option=Menu.yes()).run()
		using_subvolumes = choice.value == Menu.yes()

		prompt = str(_('Would you like to use BTRFS compression?'))
		choice = Menu(prompt, Menu.yes_no(), skip=False, default_option=Menu.yes()).run()
		compression = choice.value == Menu.yes()

	layout = {
		block_device.path : {
			"wipe" : True,
			"partitions" : []
		}
	}

	# Used for reference: https://wiki.archlinux.org/title/partitioning

	# 2 MiB is unallocated for GRUB on BIOS. Potentially unneeded for
	# other bootloaders?

	# TODO: On BIOS, /boot partition is only needed if the drive will
	# be encrypted, otherwise it is not recommended. We should probably
	# add a check for whether the drive will be encrypted or not.
	layout[block_device.path]['partitions'].append({
		# Boot
		"type" : "primary",
		"start" : "3MiB",
		"size" : "203MiB",
		"boot" : True,
		"encrypted" : False,
		"wipe" : True,
		"mountpoint" : "/boot",
		"filesystem" : {
			"format" : "fat32"
		}
	})

	# Increase the UEFI partition if UEFI is detected.
	# Also re-align the start to 1MiB since we don't need the first sectors
	# like we do in MBR layouts where the boot loader is installed traditionally.
	if has_uefi():
		layout[block_device.path]['partitions'][-1]['start'] = '1MiB'
		layout[block_device.path]['partitions'][-1]['size'] = '512MiB'

	layout[block_device.path]['partitions'].append({
		# Root
		"type" : "primary",
		"start" : "206MiB",
		"encrypted" : False,
		"wipe" : True,
		"mountpoint" : "/" if not using_subvolumes else None,
		"filesystem" : {
			"format" : default_filesystem,
			"mount_options" : ["compress=zstd"] if compression else []
		}
	})

	if has_uefi():
		layout[block_device.path]['partitions'][-1]['start'] = '513MiB'

	if not using_subvolumes and block_device.size >= MIN_SIZE_TO_ALLOW_HOME_PART:
		prompt = str(_('Would you like to create a separate partition for /home?'))
		choice = Menu(prompt, Menu.yes_no(), skip=False, default_option=Menu.yes()).run()
		using_home_partition = choice.value == Menu.yes()

	# Set a size for / (/root)
	if using_subvolumes or block_device.size < MIN_SIZE_TO_ALLOW_HOME_PART or not using_home_partition:
		# We'll use subvolumes
		# Or the disk size is too small to allow for a separate /home
		# Or the user doesn't want to create a separate partition for /home
		layout[block_device.path]['partitions'][-1]['size'] = '100%'
	else:
		layout[block_device.path]['partitions'][-1]['size'] = f"{min(block_device.size, 20)}GiB"

	if default_filesystem == 'btrfs' and using_subvolumes:
		# if input('Do you want to use a recommended structure? (Y/n): ').strip().lower() in ('', 'y', 'yes'):
		# https://btrfs.wiki.kernel.org/index.php/FAQ
		# https://unix.stackexchange.com/questions/246976/btrfs-subvolume-uuid-clash
		# https://github.com/classy-giraffe/easy-arch/blob/main/easy-arch.sh
		layout[block_device.path]['partitions'][1]['btrfs'] = {
			'subvolumes': [
				Subvolume('@', '/'),
				Subvolume('@home', '/home'),
				Subvolume('@log', '/var/log'),
				Subvolume('@pkg', '/var/cache/pacman/pkg'),
				Subvolume('@.snapshots', '/.snapshots')
			]
		}
	elif using_home_partition:
		# If we don't want to use subvolumes,
		# But we want to be able to re-use data between re-installs..
		# A second partition for /home would be nice if we have the space for it
		layout[block_device.path]['partitions'].append({
			# Home
			"type" : "primary",
			"start" : f"{min(block_device.size, 20)}GiB",
			"size" : "100%",
			"encrypted" : False,
			"wipe" : True,
			"mountpoint" : "/home",
			"filesystem" : {
				"format" : default_filesystem,
				"mount_options" : ["compress=zstd"] if compression else []
			}
		})

	return layout


def suggest_multi_disk_layout(block_devices :List[BlockDevice], default_filesystem :Optional[str] = None, advanced_options :bool = False):

	if not default_filesystem:
		from ..user_interaction import ask_for_main_filesystem_format
		default_filesystem = ask_for_main_filesystem_format(advanced_options)

	# Not really a rock solid foundation of information to stand on, but it's a start:
	# https://www.reddit.com/r/btrfs/comments/m287gp/partition_strategy_for_two_physical_disks/
	# https://www.reddit.com/r/btrfs/comments/9us4hr/what_is_your_btrfs_partitionsubvolumes_scheme/

	MIN_SIZE_TO_ALLOW_HOME_PART = 40 # GiB
	ARCH_LINUX_INSTALLED_SIZE = 20 # GiB, rough estimate taking in to account user desktops etc. TODO: Catch user packages to detect size?

	block_devices = sort_block_devices_based_on_performance(block_devices).keys()

	home_device = select_largest_device(block_devices, gigabytes=MIN_SIZE_TO_ALLOW_HOME_PART)
	root_device = select_disk_larger_than_or_close_to(block_devices, gigabytes=ARCH_LINUX_INSTALLED_SIZE, filter_out=[home_device])

	if home_device is None or root_device is None:
		text = _('The selected drives do not have the minimum capacity required for an automatic suggestion\n')
		text += _('Minimum capacity for /home partition: {}GB\n').format(MIN_SIZE_TO_ALLOW_HOME_PART)
		text += _('Minimum capacity for Arch Linux partition: {}GB').format(ARCH_LINUX_INSTALLED_SIZE)
		Menu(str(text), [str(_('Continue'))], skip=False).run()
		return None

	compression = False

	if default_filesystem == 'btrfs':
		# prompt = 'Would you like to use BTRFS subvolumes with a default structure?'
		# choice = Menu(prompt, ['yes', 'no'], skip=False, default_option='yes').run()
		# using_subvolumes = choice == 'yes'

		prompt = str(_('Would you like to use BTRFS compression?'))
		choice = Menu(prompt, Menu.yes_no(), skip=False, default_option=Menu.yes()).run()
		compression = choice.value == Menu.yes()

	log(f"Suggesting multi-disk-layout using {len(block_devices)} disks, where {root_device} will be /root and {home_device} will be /home", level=logging.DEBUG)

	layout = {
		root_device.path : {
			"wipe" : True,
			"partitions" : []
		},
		home_device.path : {
			"wipe" : True,
			"partitions" : []
		},
	}

	# TODO: Same deal as with the single disk layout, we should
	# probably check if the drive will be encrypted.
	layout[root_device.path]['partitions'].append({
		# Boot
		"type" : "primary",
		"start" : "3MiB",
		"size" : "203MiB",
		"boot" : True,
		"encrypted" : False,
		"wipe" : True,
		"mountpoint" : "/boot",
		"filesystem" : {
			"format" : "fat32"
		}
	})

	if has_uefi():
		layout[root_device.path]['partitions'][-1]['start'] = '1MiB'
		layout[root_device.path]['partitions'][-1]['size'] = '512MiB'

	layout[root_device.path]['partitions'].append({
		# Root
		"type" : "primary",
		"start" : "206MiB",
		"size" : "100%",
		"encrypted" : False,
		"wipe" : True,
		"mountpoint" : "/",
		"filesystem" : {
			"format" : default_filesystem,
			"mount_options" : ["compress=zstd"] if compression else []
		}
	})
	if has_uefi():
		layout[root_device.path]['partitions'][-1]['start'] = '513MiB'

	layout[home_device.path]['partitions'].append({
		# Home
		"type" : "primary",
		"start" : "1MiB",
		"size" : "100%",
		"encrypted" : False,
		"wipe" : True,
		"mountpoint" : "/home",
		"filesystem" : {
			"format" : default_filesystem,
			"mount_options" : ["compress=zstd"] if compression else []
		}
	})

	return layout
