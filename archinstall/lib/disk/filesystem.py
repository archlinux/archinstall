from __future__ import annotations

import math
import time
from pathlib import Path

from archinstall.lib.translationhandler import tr
from archinstall.tui.curses_menu import Tui

from ..interactions.general_conf import ask_abort
from ..luks import Luks2
from ..models.device import (
	DiskEncryption,
	DiskLayoutConfiguration,
	DiskLayoutType,
	EncryptionType,
	FilesystemType,
	LvmConfiguration,
	LvmVolume,
	LvmVolumeGroup,
	PartitionModification,
	SectorSize,
	Size,
	Unit,
)
from ..output import debug, info
from .device_handler import device_handler


class FilesystemHandler:
	def __init__(self, disk_config: DiskLayoutConfiguration):
		self._disk_config = disk_config
		self._enc_config = disk_config.disk_encryption

	def perform_filesystem_operations(self, show_countdown: bool = True) -> None:
		if self._disk_config.config_type == DiskLayoutType.Pre_mount:
			debug('Disk layout configuration is set to pre-mount, not performing any operations')
			return

		device_mods = [d for d in self._disk_config.device_modifications if d.partitions]

		if not device_mods:
			debug('No modifications required')
			return

		device_paths = ', '.join([str(mod.device.device_info.path) for mod in device_mods])

		if show_countdown:
			self._final_warning(device_paths)

		# Setup the blockdevice, filesystem (and optionally encryption).
		# Once that's done, we'll hand over to perform_installation()

		# make sure all devices are unmounted
		for mod in device_mods:
			device_handler.umount_all_existing(mod.device_path)

		for mod in device_mods:
			device_handler.partition(mod)

		device_handler.udev_sync()

		if self._disk_config.lvm_config:
			for mod in device_mods:
				if boot_part := mod.get_boot_partition():
					debug(f'Formatting boot partition: {boot_part.dev_path}')
					self._format_partitions([boot_part])

			self.perform_lvm_operations()
		else:
			for mod in device_mods:
				self._format_partitions(mod.partitions)

				for part_mod in mod.partitions:
					if part_mod.fs_type == FilesystemType.Btrfs and part_mod.is_create_or_modify():
						device_handler.create_btrfs_volumes(part_mod, enc_conf=self._enc_config)

	def _format_partitions(
		self,
		partitions: list[PartitionModification],
	) -> None:
		"""
		Format can be given an overriding path, for instance /dev/null to test
		the formatting functionality and in essence the support for the given filesystem.
		"""

		# don't touch existing partitions
		create_or_modify_parts = [p for p in partitions if p.is_create_or_modify()]

		self._validate_partitions(create_or_modify_parts)

		for part_mod in create_or_modify_parts:
			# partition will be encrypted
			if self._enc_config is not None and part_mod in self._enc_config.partitions:
				device_handler.format_encrypted(
					part_mod.safe_dev_path,
					part_mod.mapper_name,
					part_mod.safe_fs_type,
					self._enc_config,
				)
			else:
				device_handler.format(part_mod.safe_fs_type, part_mod.safe_dev_path)

			# synchronize with udev before using lsblk
			device_handler.udev_sync()

			lsblk_info = device_handler.fetch_part_info(part_mod.safe_dev_path)

			part_mod.partn = lsblk_info.partn
			part_mod.partuuid = lsblk_info.partuuid
			part_mod.uuid = lsblk_info.uuid

	def _validate_partitions(self, partitions: list[PartitionModification]) -> None:
		checks = {
			# verify that all partitions have a path set (which implies that they have been created)
			lambda x: x.dev_path is None: ValueError('When formatting, all partitions must have a path set'),
			# crypto luks is not a valid file system type
			lambda x: x.fs_type is FilesystemType.Crypto_luks: ValueError('Crypto luks cannot be set as a filesystem type'),
			# file system type must be set
			lambda x: x.fs_type is None: ValueError('File system type must be set for modification'),
		}

		for check, exc in checks.items():
			found = next(filter(check, partitions), None)
			if found is not None:
				raise exc

	def perform_lvm_operations(self) -> None:
		info('Setting up LVM config...')

		if not self._disk_config.lvm_config:
			return

		if self._enc_config:
			self._setup_lvm_encrypted(
				self._disk_config.lvm_config,
				self._enc_config,
			)
		else:
			self._setup_lvm(self._disk_config.lvm_config)
			self._format_lvm_vols(self._disk_config.lvm_config)

	def _setup_lvm_encrypted(self, lvm_config: LvmConfiguration, enc_config: DiskEncryption) -> None:
		if enc_config.encryption_type == EncryptionType.LvmOnLuks:
			enc_mods = self._encrypt_partitions(enc_config, lock_after_create=False)

			self._setup_lvm(lvm_config, enc_mods)
			self._format_lvm_vols(lvm_config)

			# export the lvm group safely otherwise the Luks cannot be closed
			self._safely_close_lvm(lvm_config)

			for luks in enc_mods.values():
				luks.lock()
		elif enc_config.encryption_type == EncryptionType.LuksOnLvm:
			self._setup_lvm(lvm_config)
			enc_vols = self._encrypt_lvm_vols(lvm_config, enc_config, False)
			self._format_lvm_vols(lvm_config, enc_vols)

			for luks in enc_vols.values():
				luks.lock()

			self._safely_close_lvm(lvm_config)

	def _safely_close_lvm(self, lvm_config: LvmConfiguration) -> None:
		for vg in lvm_config.vol_groups:
			for vol in vg.volumes:
				device_handler.lvm_vol_change(vol, False)

			device_handler.lvm_export_vg(vg)

	def _setup_lvm(
		self,
		lvm_config: LvmConfiguration,
		enc_mods: dict[PartitionModification, Luks2] = {},
	) -> None:
		self._lvm_create_pvs(lvm_config, enc_mods)

		for vg in lvm_config.vol_groups:
			pv_dev_paths = self._get_all_pv_dev_paths(vg.pvs, enc_mods)

			device_handler.lvm_vg_create(pv_dev_paths, vg.name)

			# figure out what the actual available size in the group is
			vg_info = device_handler.lvm_group_info(vg.name)

			if not vg_info:
				raise ValueError('Unable to fetch VG info')

			# the actual available LVM Group size will be smaller than the
			# total PVs size due to reserved metadata storage etc.
			# so we'll have a look at the total avail. size, check the delta
			# to the desired sizes and subtract some equally from the actually
			# created volume
			avail_size = vg_info.vg_size
			desired_size = sum([vol.length for vol in vg.volumes], Size(0, Unit.B, SectorSize.default()))

			delta = desired_size - avail_size
			delta_bytes = delta.convert(Unit.B)

			# Round the offset up to the next physical extent (PE, 4 MiB by default)
			# to ensure lvcreate`s internal rounding doesn`t consume space reserved
			# for subsequent logical volumes.
			pe_bytes = Size(4, Unit.MiB, SectorSize.default()).convert(Unit.B)
			pe_count = math.ceil(delta_bytes.value / pe_bytes.value)
			rounded_offset = pe_count * pe_bytes.value
			max_vol_offset = Size(rounded_offset, Unit.B, SectorSize.default())

			max_vol = max(vg.volumes, key=lambda x: x.length)

			for lv in vg.volumes:
				offset = max_vol_offset if lv == max_vol else None

				debug(f'vg: {vg.name}, vol: {lv.name}, offset: {offset}')
				device_handler.lvm_vol_create(vg.name, lv, offset)

				while True:
					debug('Fetching LVM volume info')
					lv_info = device_handler.lvm_vol_info(lv.name)
					if lv_info is not None:
						break

					time.sleep(1)

			self._lvm_vol_handle_e2scrub(vg)

	def _format_lvm_vols(
		self,
		lvm_config: LvmConfiguration,
		enc_vols: dict[LvmVolume, Luks2] = {},
	) -> None:
		for vol in lvm_config.get_all_volumes():
			if enc_vol := enc_vols.get(vol, None):
				if not enc_vol.mapper_dev:
					raise ValueError('No mapper device defined')
				path = enc_vol.mapper_dev
			else:
				path = vol.safe_dev_path

			# wait a bit otherwise the mkfs will fail as it can't
			# find the mapper device yet
			device_handler.format(vol.fs_type, path)

			if vol.fs_type == FilesystemType.Btrfs:
				device_handler.create_lvm_btrfs_subvolumes(path, vol.btrfs_subvols, vol.mount_options)

	def _lvm_create_pvs(
		self,
		lvm_config: LvmConfiguration,
		enc_mods: dict[PartitionModification, Luks2] = {},
	) -> None:
		pv_paths: set[Path] = set()

		for vg in lvm_config.vol_groups:
			pv_paths |= self._get_all_pv_dev_paths(vg.pvs, enc_mods)

		device_handler.lvm_pv_create(pv_paths)

	def _get_all_pv_dev_paths(
		self,
		pvs: list[PartitionModification],
		enc_mods: dict[PartitionModification, Luks2] = {},
	) -> set[Path]:
		pv_paths: set[Path] = set()

		for pv in pvs:
			if enc_pv := enc_mods.get(pv, None):
				if mapper := enc_pv.mapper_dev:
					pv_paths.add(mapper)
			else:
				pv_paths.add(pv.safe_dev_path)

		return pv_paths

	def _encrypt_lvm_vols(
		self,
		lvm_config: LvmConfiguration,
		enc_config: DiskEncryption,
		lock_after_create: bool = True,
	) -> dict[LvmVolume, Luks2]:
		enc_vols: dict[LvmVolume, Luks2] = {}

		for vol in lvm_config.get_all_volumes():
			if vol in enc_config.lvm_volumes:
				luks_handler = device_handler.encrypt(
					vol.safe_dev_path,
					vol.mapper_name,
					enc_config.encryption_password,
					lock_after_create,
					iter_time=enc_config.iter_time,
				)

				enc_vols[vol] = luks_handler

		return enc_vols

	def _encrypt_partitions(
		self,
		enc_config: DiskEncryption,
		lock_after_create: bool = True,
	) -> dict[PartitionModification, Luks2]:
		enc_mods: dict[PartitionModification, Luks2] = {}

		for mod in self._disk_config.device_modifications:
			partitions = mod.partitions

			# don't touch existing partitions
			filtered_part = [p for p in partitions if not p.exists()]

			self._validate_partitions(filtered_part)

			enc_mods = {}

			for part_mod in filtered_part:
				if part_mod in enc_config.partitions:
					luks_handler = device_handler.encrypt(
						part_mod.safe_dev_path,
						part_mod.mapper_name,
						enc_config.encryption_password,
						lock_after_create=lock_after_create,
						iter_time=enc_config.iter_time,
					)

					enc_mods[part_mod] = luks_handler

		return enc_mods

	def _lvm_vol_handle_e2scrub(self, vol_gp: LvmVolumeGroup) -> None:
		# from arch wiki:
		# If a logical volume will be formatted with ext4, leave at least 256 MiB
		# free space in the volume group to allow using e2scrub
		if any([vol.fs_type == FilesystemType.Ext4 for vol in vol_gp.volumes]):
			largest_vol = max(vol_gp.volumes, key=lambda x: x.length)

			device_handler.lvm_vol_reduce(
				largest_vol.safe_dev_path,
				Size(256, Unit.MiB, SectorSize.default()),
			)

	def _final_warning(self, device_paths: str) -> bool:
		# Issue a final warning before we continue with something un-revertable.
		# We mention the drive one last time, and count from 5 to 0.
		out = tr(' ! Formatting {} in ').format(device_paths)
		Tui.print(out, row=0, endl='', clear_screen=True)

		try:
			countdown = '\n5...4...3...2...1\n'
			for c in countdown:
				Tui.print(c, row=0, endl='')
				time.sleep(0.25)
		except KeyboardInterrupt:
			with Tui():
				ask_abort()

		return True
