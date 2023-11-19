from __future__ import annotations

import signal
import sys
import time
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING, List

from .device_model import (
	DiskLayoutConfiguration, DiskLayoutType, PartitionTable,
	FilesystemType, DiskEncryption, LvmConfiguration, LvmVolumeGroup,
	Size, Unit, SectorSize, PartitionModification
)
from .device_handler import device_handler
from ..hardware import SysInfo
from ..output import debug, info
from ..menu import Menu

if TYPE_CHECKING:
	_: Any


class FilesystemHandler:
	def __init__(
		self,
		disk_config: DiskLayoutConfiguration,
		enc_conf: Optional[DiskEncryption] = None
	):
		self._disk_config = disk_config
		self._enc_config = enc_conf

	def perform_filesystem_operations(self, show_countdown: bool = True):
		if self._disk_config.config_type == DiskLayoutType.Pre_mount:
			debug('Disk layout configuration is set to pre-mount, not performing any operations')
			return

		device_mods = list(filter(lambda x: len(x.partitions) > 0, self._disk_config.device_modifications))

		if not device_mods:
			debug('No modifications required')
			return

		device_paths = ', '.join([str(mod.device.device_info.path) for mod in device_mods])

		# Issue a final warning before we continue with something un-revertable.
		# We mention the drive one last time, and count from 5 to 0.
		print(str(_(' ! Formatting {} in ')).format(device_paths))

		if show_countdown:
			self._do_countdown()

		# Setup the blockdevice, filesystem (and optionally encryption).
		# Once that's done, we'll hand over to perform_installation()
		partition_table = PartitionTable.GPT
		if SysInfo.has_uefi() is False:
			partition_table = PartitionTable.MBR

		for mod in device_mods:
			device_handler.partition(mod, partition_table=partition_table)

		if self._disk_config.lvm_config:
			for mod in device_mods:
				if boot_part := mod.get_boot_partition():
					info(f'Formatting boot partition: {boot_part.dev_path}')
					self.format_partitions(
						[boot_part],
						mod.device_path
					)

			self.setup_lvm(self._disk_config.lvm_config)
		else:
			for mod in device_mods:
				self.format_partitions(
					mod.partitions,
					mod.device_path,
					enc_conf=self._enc_config
				)

				for part_mod in mod.partitions:
					if part_mod.fs_type == FilesystemType.Btrfs:
						device_handler.create_btrfs_volumes(part_mod, enc_conf=self._enc_config)

	def format_partitions(
		self,
		partitions: List[PartitionModification],
		device_path: Path,
		enc_conf: Optional['DiskEncryption'] = None
	):
		"""
		Format can be given an overriding path, for instance /dev/null to test
		the formatting functionality and in essence the support for the given filesystem.
		"""

		# don't touch existing partitions
		filtered_part = [p for p in partitions if not p.exists()]

		self._validate_partitions(filtered_part)

		# make sure all devices are unmounted
		device_handler.umount_all_existing(device_path)

		for part_mod in filtered_part:
			# partition will be encrypted
			if enc_conf is not None and part_mod in enc_conf.partitions:
				device_handler.format_enc(
					part_mod.safe_dev_path,
					part_mod.mapper_name,
					part_mod.safe_fs_type,
					enc_conf
				)
			else:
				device_handler.format(part_mod.safe_fs_type, part_mod.safe_dev_path)

			lsblk_info = device_handler.fetch_part_info(part_mod.safe_dev_path)

			part_mod.partn = lsblk_info.partn
			part_mod.partuuid = lsblk_info.partuuid
			part_mod.uuid = lsblk_info.uuid

	def _validate_partitions(self, partitions: List[PartitionModification]):
		checks = {
			# verify that all partitions have a path set (which implies that they have been created)
			lambda x: x.dev_path is None: ValueError('When formatting, all partitions must have a path set'),
			# crypto luks is not a valid file system type
			lambda x: x.fs_type is FilesystemType.Crypto_luks: ValueError(
				'Crypto luks cannot be set as a filesystem type'),
			# file system type must be set
			lambda x: x.fs_type is None: ValueError('File system type must be set for modification')
		}

		for check, exc in checks.items():
			found = next(filter(check, partitions), None)
			if found is not None:
				raise exc

	def setup_lvm(
		self,
		lvm_config: LvmConfiguration,
		enc_conf: Optional['DiskEncryption'] = None
	):
		info('Setting up LVM config')

		if not enc_conf:
			for vol_gp in lvm_config.vol_groups:
				device_handler.lvm_pv_create(vol_gp.pvs)
				device_handler.lvm_group_create(vol_gp)

				# figure out what the actual available size in the group is
				lvm_gp_info = device_handler.lvm_group_info(vol_gp.name)

				# the actual available LVM Group size will be smaller than the
				# total PVs size due to reserved metadata storage etc.
				# so we'll have a look at the total avail. size, check the delta
				# to the desired sizes and subtract some equally from the actually
				# created volume
				avail_size = lvm_gp_info.vg_size
				total_lvm_size = sum([vol.length for vol in vol_gp.volumes], Size(0, Unit.B, SectorSize.default()))

				delta = total_lvm_size - avail_size
				offset = delta.convert(Unit.B)
				offset.value = int(offset.value / len(vol_gp.volumes))

				for volume in vol_gp.volumes:
					device_handler.lvm_vol_create(vol_gp.name, volume, offset)

				self._lvm_vol_handle_e2scrub(vol_gp)

				for volume in vol_gp.volumes:
					# wait a bit otherwise the mkfs will fail as it can't
					# find the mapper device yet
					device_handler.format(volume.fs_type, volume.safe_dev_path)

	def _lvm_vol_handle_e2scrub(self, vol_gp: LvmVolumeGroup):
		# from arch wiki:
		# If a logical volume will be formatted with ext4, leave at least 256 MiB
		# free space in the volume group to allow using e2scrub
		if any([vol.fs_type == FilesystemType.Ext4 for vol in vol_gp.volumes]):
			largest_vol = max(vol_gp.volumes, key=lambda x: x.length)
			print(largest_vol.length.convert(Unit.MiB))

			device_handler.lvm_vol_reduce(
				largest_vol.safe_dev_path,
				Size(256, Unit.MiB, SectorSize.default())
			)

	def _do_countdown(self) -> bool:
		SIG_TRIGGER = False

		def kill_handler(sig: int, frame: Any) -> None:
			print()
			exit(0)

		def sig_handler(sig: int, frame: Any) -> None:
			signal.signal(signal.SIGINT, kill_handler)

		original_sigint_handler = signal.getsignal(signal.SIGINT)
		signal.signal(signal.SIGINT, sig_handler)

		for i in range(5, 0, -1):
			print(f"{i}", end='')

			for x in range(4):
				sys.stdout.flush()
				time.sleep(0.25)
				print(".", end='')

			if SIG_TRIGGER:
				prompt = _('Do you really want to abort?')
				choice = Menu(prompt, Menu.yes_no(), skip=False).run()
				if choice.value == Menu.yes():
					exit(0)

				if SIG_TRIGGER is False:
					sys.stdin.read()

				SIG_TRIGGER = False
				signal.signal(signal.SIGINT, sig_handler)

		print()
		signal.signal(signal.SIGINT, original_sigint_handler)

		return True
