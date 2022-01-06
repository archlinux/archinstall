from __future__ import annotations
import logging
from typing import Optional, Dict, Any, List, TYPE_CHECKING
# https://stackoverflow.com/a/39757388/929999
if TYPE_CHECKING:
	from .blockdevice import BlockDevice
	
from .helpers import sort_block_devices_based_on_performance, select_largest_device, select_disk_larger_than_or_close_to
from ..output import log

def suggest_single_disk_layout(block_device :BlockDevice,
	default_filesystem :Optional[str] = None,
	advanced_options :bool = False) -> Dict[str, Any]:

	if not default_filesystem:
		from ..user_interaction import ask_for_main_filesystem_format
		default_filesystem = ask_for_main_filesystem_format(advanced_options)

	MIN_SIZE_TO_ALLOW_HOME_PART = 40 # Gb
	using_subvolumes = False
	using_home_partition = False

	if default_filesystem == 'btrfs':
		using_subvolumes = input('Would you like to use BTRFS subvolumes with a default structure? (Y/n): ').strip().lower() in ('', 'y', 'yes')

	layout = {
		block_device.path : {
			"wipe" : True,
			"partitions" : []
		}
	}

	layout[block_device.path]['partitions'].append({
		# Boot
		"type" : "primary",
		"start" : "5MB",
		"size" : "513MB",
		"boot" : True,
		"encrypted" : False,
		"format" : True,
		"mountpoint" : "/boot",
		"filesystem" : {
			"format" : "fat32"
		}
	})
	layout[block_device.path]['partitions'].append({
		# Root
		"type" : "primary",
		"start" : "518MB",
		"encrypted" : False,
		"format" : True,
		"mountpoint" : "/",
		"filesystem" : {
			"format" : default_filesystem
		}
	})

	if not using_subvolumes and block_device.size >= MIN_SIZE_TO_ALLOW_HOME_PART:
		using_home_partition = input('Would you like to create a separate partition for /home? (Y/n): ').strip().lower() in ('', 'y', 'yes')

	# Set a size for / (/root)
	if using_subvolumes or block_device.size < MIN_SIZE_TO_ALLOW_HOME_PART or not using_home_partition:
		# We'll use subvolumes
		# Or the disk size is too small to allow for a separate /home
		# Or the user doesn't want to create a separate partition for /home
		layout[block_device.path]['partitions'][-1]['size'] = '100%'
	else:
		layout[block_device.path]['partitions'][-1]['size'] = f"{min(block_device.size, 20)}GB"

	if default_filesystem == 'btrfs' and using_subvolumes:
		# if input('Do you want to use a recommended structure? (Y/n): ').strip().lower() in ('', 'y', 'yes'):
		# https://btrfs.wiki.kernel.org/index.php/FAQ
		# https://unix.stackexchange.com/questions/246976/btrfs-subvolume-uuid-clash
		# https://github.com/classy-giraffe/easy-arch/blob/main/easy-arch.sh
		layout[block_device.path]['partitions'][1]['btrfs'] = {
			"subvolumes" : {
				"@home" : "/home",
				"@log" : "/var/log",
				"@pkgs" : "/var/cache/pacman/pkg",
				"@.snapshots" : "/.snapshots"
			}
		}
		# else:
		# 	pass # ... implement a guided setup

	elif using_home_partition:
		# If we don't want to use subvolumes,
		# But we want to be able to re-use data between re-installs..
		# A second partition for /home would be nice if we have the space for it
		layout[block_device.path]['partitions'].append({
			# Home
			"type" : "primary",
			"encrypted" : False,
			"format" : True,
			"start" : f"{min(block_device.size+0.5, 20.5)}GB",
			"size" : "100%",
			"mountpoint" : "/home",
			"filesystem" : {
				"format" : default_filesystem
			}
		})

	return layout


def suggest_multi_disk_layout(block_devices :List[BlockDevice],
	default_filesystem :Optional[str] = None,
	advanced_options :bool = False
) -> Dict[str, Any]:

	if not default_filesystem:
		from ..user_interaction import ask_for_main_filesystem_format
		default_filesystem = ask_for_main_filesystem_format(advanced_options)

	# Not really a rock solid foundation of information to stand on, but it's a start:
	# https://www.reddit.com/r/btrfs/comments/m287gp/partition_strategy_for_two_physical_disks/
	# https://www.reddit.com/r/btrfs/comments/9us4hr/what_is_your_btrfs_partitionsubvolumes_scheme/

	MIN_SIZE_TO_ALLOW_HOME_PART = 40 # Gb
	ARCH_LINUX_INSTALLED_SIZE = 20 # Gb, rough estimate taking in to account user desktops etc. TODO: Catch user packages to detect size?

	block_devices = sort_block_devices_based_on_performance(block_devices).keys()

	home_device = select_largest_device(block_devices, gigabytes=MIN_SIZE_TO_ALLOW_HOME_PART)
	root_device = select_disk_larger_than_or_close_to(block_devices, gigabytes=ARCH_LINUX_INSTALLED_SIZE, filter_out=[home_device])

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

	layout[root_device.path]['partitions'].append({
		# Boot
		"type" : "primary",
		"start" : "5MB",
		"size" : "513MB",
		"boot" : True,
		"encrypted" : False,
		"format" : True,
		"mountpoint" : "/boot",
		"filesystem" : {
			"format" : "fat32"
		}
	})
	layout[root_device.path]['partitions'].append({
		# Root
		"type" : "primary",
		"start" : "518MB",
		"encrypted" : False,
		"format" : True,
		"size" : "100%",
		"mountpoint" : "/",
		"filesystem" : {
			"format" : default_filesystem
		}
	})

	layout[home_device.path]['partitions'].append({
		# Home
		"type" : "primary",
		"encrypted" : False,
		"format" : True,
		"start" : "5MB",
		"size" : "100%",
		"mountpoint" : "/home",
		"filesystem" : {
			"format" : default_filesystem
		}
	})

	return layout
