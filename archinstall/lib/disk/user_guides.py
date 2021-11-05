import logging
from .helpers import sort_block_devices_based_on_performance, select_largest_device, select_disk_larger_than_or_close_to
from ..output import log

def suggest_single_disk_layout(block_device, default_filesystem=None):
	if not default_filesystem:
		from ..user_interaction import ask_for_main_filesystem_format
		default_filesystem = ask_for_main_filesystem_format()
		
	MIN_SIZE_TO_ALLOW_HOME_PART = 40 # Gb

	layout = {
		block_device.path : {
			"wipe" : True,
			"partitions" : []
		}
	}

	layout[block_device.path]['partitions'].append({
		# Boot
		"type" : "primary",
		"start" : "1MiB",
		"size" : "513MiB",
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
		"start" : "513MiB",
		"encrypted" : False,
		"format" : True,
		"size" : "100%" if block_device.size < MIN_SIZE_TO_ALLOW_HOME_PART else f"{min(block_device.size, 20)*1024}MiB",
		"mountpoint" : "/",
		"filesystem" : {
			"format" : default_filesystem
		}
	})

	if default_filesystem == 'btrfs' and input('Would you like to use BTRFS subvolumes? (Y/n): ').strip().lower() in ('', 'y', 'yes'):
		if input('Do you want to use a recommended structure? (Y/n): ').strip().lower() in ('', 'y', 'yes'):
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
		else:
			pass # ... implement a guided setup

	elif block_device.size >= MIN_SIZE_TO_ALLOW_HOME_PART:
		# If we don't want to use subvolumes,
		# But we want to be able to re-use data between re-installs..
		# A second partition for /home would be nice if we have the space for it
		layout[block_device.path]['partitions'].append({
			# Home
			"type" : "primary",
			"encrypted" : False,
			"format" : True,
			"start" : f"{min(block_device.size*0.2, 20)*1024}MiB",
			"size" : "100%",
			"mountpoint" : "/home",
			"filesystem" : {
				"format" : default_filesystem
			}
		})

	return layout


def suggest_multi_disk_layout(block_devices, default_filesystem=None):
	if not default_filesystem:
		from ..user_interaction import ask_for_main_filesystem_format
		default_filesystem = ask_for_main_filesystem_format()

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
		"start" : "1MiB",
		"size" : "513MiB",
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
		"start" : "513MiB",
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
		"start" : "4MiB",
		"size" : "100%",
		"mountpoint" : "/home",
		"filesystem" : {
			"format" : default_filesystem
		}
	})

	return layout
