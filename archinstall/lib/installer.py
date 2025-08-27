import glob
import os
import platform
import re
import shlex
import shutil
import subprocess
import textwrap
import time
from collections.abc import Callable
from pathlib import Path
from subprocess import CalledProcessError
from types import TracebackType
from typing import Any

from archinstall.lib.disk.device_handler import device_handler
from archinstall.lib.disk.fido import Fido2
from archinstall.lib.disk.utils import get_lsblk_by_mountpoint, get_lsblk_info
from archinstall.lib.models.device import (
	DiskEncryption,
	DiskLayoutConfiguration,
	EncryptionType,
	FilesystemType,
	LvmVolume,
	PartitionModification,
	SectorSize,
	Size,
	SnapshotType,
	SubvolumeModification,
	Unit,
)
from archinstall.lib.models.packages import Repository
from archinstall.lib.packages import installed_package
from archinstall.lib.translationhandler import tr
from archinstall.tui.curses_menu import Tui

from .args import arch_config_handler
from .exceptions import DiskError, HardwareIncompatibilityError, RequirementError, ServiceException, SysCallError
from .general import SysCommand, run
from .hardware import SysInfo
from .locale.utils import verify_keyboard_layout, verify_x11_keyboard_layout
from .luks import Luks2
from .models.bootloader import Bootloader
from .models.locale import LocaleConfiguration
from .models.mirrors import MirrorConfiguration
from .models.network import Nic
from .models.users import User
from .output import debug, error, info, log, logger, warn
from .pacman import Pacman
from .pacman.config import PacmanConfig
from .plugins import plugins
from .storage import storage

# Any package that the Installer() is responsible for (optional and the default ones)
__packages__ = ['base', 'base-devel', 'linux-firmware', 'linux', 'linux-lts', 'linux-zen', 'linux-hardened']

# Additional packages that are installed if the user is running the Live ISO with accessibility tools enabled
__accessibility_packages__ = ['brltty', 'espeakup', 'alsa-utils']


class Installer:
	def __init__(
		self,
		target: Path,
		disk_config: DiskLayoutConfiguration,
		base_packages: list[str] = [],
		kernels: list[str] | None = None,
	):
		"""
		`Installer()` is the wrapper for most basic installation steps.
		It also wraps :py:func:`~archinstall.Installer.pacstrap` among other things.
		"""
		self._base_packages = base_packages or __packages__[:3]
		self.kernels = kernels or ['linux']
		self._disk_config = disk_config

		self._disk_encryption = disk_config.disk_encryption or DiskEncryption(EncryptionType.NoEncryption)
		self.target: Path = target

		self.init_time = time.strftime('%Y-%m-%d_%H-%M-%S')
		self.milliseconds = int(str(time.time()).split('.')[1])
		self._helper_flags: dict[str, str | bool | None] = {
			'base': False,
			'bootloader': None,
		}

		for kernel in self.kernels:
			self._base_packages.append(kernel)

		# If using accessibility tools in the live environment, append those to the packages list
		if accessibility_tools_in_use():
			self._base_packages.extend(__accessibility_packages__)

		self.post_base_install: list[Callable] = []  # type: ignore[type-arg]

		storage['installation_session'] = self

		self._modules: list[str] = []
		self._binaries: list[str] = []
		self._files: list[str] = []

		# systemd, sd-vconsole and sd-encrypt will be replaced by udev, keymap and encrypt
		# if HSM is not used to encrypt the root volume. Check mkinitcpio() function for that override.
		self._hooks: list[str] = [
			'base',
			'systemd',
			'autodetect',
			'microcode',
			'modconf',
			'kms',
			'keyboard',
			'sd-vconsole',
			'block',
			'filesystems',
			'fsck',
		]
		self._kernel_params: list[str] = []
		self._fstab_entries: list[str] = []

		self._zram_enabled = False
		self._disable_fstrim = False

		self.pacman = Pacman(self.target, arch_config_handler.args.silent)

	def __enter__(self) -> 'Installer':
		return self

	def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool | None:
		if exc_type is not None:
			error(str(exc_value))

			self.sync_log_to_install_medium()

			# We avoid printing /mnt/<log path> because that might confuse people if they note it down
			# and then reboot, and a identical log file will be found in the ISO medium anyway.
			Tui.print(str(tr('[!] A log file has been created here: {}').format(logger.path)))
			Tui.print(tr('Please submit this issue (and file) to https://github.com/archlinux/archinstall/issues'))

			# Return None to propagate the exception
			return None

		self.sync()

		if not (missing_steps := self.post_install_check()):
			msg = f'Installation completed without any errors.\nLog files temporarily available at {logger.directory}.\nYou may reboot when ready.\n'
			log(msg, fg='green')
			self.sync_log_to_install_medium()
			return True
		else:
			warn('Some required steps were not successfully installed/configured before leaving the installer:')

			for step in missing_steps:
				warn(f' - {step}')

			warn(f'Detailed error logs can be found at: {logger.directory}')
			warn('Submit this zip file as an issue to https://github.com/archlinux/archinstall/issues')

			self.sync_log_to_install_medium()
			return False

	def sync(self) -> None:
		info(tr('Syncing the system...'))
		SysCommand('sync')

	def remove_mod(self, mod: str) -> None:
		if mod in self._modules:
			self._modules.remove(mod)

	def append_mod(self, mod: str) -> None:
		if mod not in self._modules:
			self._modules.append(mod)

	def _verify_service_stop(self) -> None:
		"""
		Certain services might be running that affects the system during installation.
		One such service is "reflector.service" which updates /etc/pacman.d/mirrorlist
		We need to wait for it before we continue since we opted in to use a custom mirror/region.
		"""

		if not arch_config_handler.args.skip_ntp:
			info(tr('Waiting for time sync (timedatectl show) to complete.'))

			started_wait = time.time()
			notified = False
			while True:
				if not notified and time.time() - started_wait > 5:
					notified = True
					warn(tr('Time synchronization not completing, while you wait - check the docs for workarounds: https://archinstall.readthedocs.io/'))

				time_val = SysCommand('timedatectl show --property=NTPSynchronized --value').decode()
				if time_val and time_val.strip() == 'yes':
					break
				time.sleep(1)
		else:
			info(tr('Skipping waiting for automatic time sync (this can cause issues if time is out of sync during installation)'))

		info('Waiting for automatic mirror selection (reflector) to complete.')
		while self._service_state('reflector') not in ('dead', 'failed', 'exited'):
			time.sleep(1)

		# info('Waiting for pacman-init.service to complete.')
		# while self._service_state('pacman-init') not in ('dead', 'failed', 'exited'):
		# 	time.sleep(1)

		if not arch_config_handler.args.skip_wkd:
			info(tr('Waiting for Arch Linux keyring sync (archlinux-keyring-wkd-sync) to complete.'))
			# Wait for the timer to kick in
			while self._service_started('archlinux-keyring-wkd-sync.timer') is None:
				time.sleep(1)

			# Wait for the service to enter a finished state
			while self._service_state('archlinux-keyring-wkd-sync.service') not in ('dead', 'failed', 'exited'):
				time.sleep(1)

	def _verify_boot_part(self) -> None:
		"""
		Check that mounted /boot device has at minimum size for installation
		The reason this check is here is to catch pre-mounted device configuration and potentially
		configured one that has not gone through any previous checks (e.g. --silence mode)

		NOTE: this function should be run AFTER running the mount_ordered_layout function
		"""
		boot_mount = self.target / 'boot'
		lsblk_info = get_lsblk_by_mountpoint(boot_mount)

		if len(lsblk_info) > 0:
			if lsblk_info[0].size < Size(200, Unit.MiB, SectorSize.default()):
				raise DiskError(
					f'The boot partition mounted at {boot_mount} is not large enough to install a boot loader. '
					f'Please resize it to at least 200MiB and re-run the installation.',
				)

	def sanity_check(self) -> None:
		# self._verify_boot_part()
		self._verify_service_stop()

	def mount_ordered_layout(self) -> None:
		debug('Mounting ordered layout')

		luks_handlers: dict[Any, Luks2] = {}

		match self._disk_encryption.encryption_type:
			case EncryptionType.NoEncryption:
				self._mount_lvm_layout()
			case EncryptionType.Luks:
				luks_handlers = self._prepare_luks_partitions(self._disk_encryption.partitions)
			case EncryptionType.LvmOnLuks:
				luks_handlers = self._prepare_luks_partitions(self._disk_encryption.partitions)
				self._import_lvm()
				self._mount_lvm_layout(luks_handlers)
			case EncryptionType.LuksOnLvm:
				self._import_lvm()
				luks_handlers = self._prepare_luks_lvm(self._disk_encryption.lvm_volumes)
				self._mount_lvm_layout(luks_handlers)

		# mount all regular partitions
		self._mount_partition_layout(luks_handlers)

	def _mount_partition_layout(self, luks_handlers: dict[Any, Luks2]) -> None:
		debug('Mounting partition layout')

		# do not mount any PVs part of the LVM configuration
		pvs = []
		if self._disk_config.lvm_config:
			pvs = self._disk_config.lvm_config.get_all_pvs()

		sorted_device_mods = self._disk_config.device_modifications.copy()

		# move the device with the root partition to the beginning of the list
		for mod in self._disk_config.device_modifications:
			if any(partition.is_root() for partition in mod.partitions):
				sorted_device_mods.remove(mod)
				sorted_device_mods.insert(0, mod)
				break

		for mod in sorted_device_mods:
			not_pv_part_mods = [p for p in mod.partitions if p not in pvs]

			# partitions have to mounted in the right order on btrfs the mountpoint will
			# be empty as the actual subvolumes are getting mounted instead so we'll use
			# '/' just for sorting
			sorted_part_mods = sorted(not_pv_part_mods, key=lambda x: x.mountpoint or Path('/'))

			for part_mod in sorted_part_mods:
				if luks_handler := luks_handlers.get(part_mod):
					self._mount_luks_partition(part_mod, luks_handler)
				else:
					self._mount_partition(part_mod)

	def _mount_lvm_layout(self, luks_handlers: dict[Any, Luks2] = {}) -> None:
		lvm_config = self._disk_config.lvm_config

		if not lvm_config:
			debug('No lvm config defined to be mounted')
			return

		debug('Mounting LVM layout')

		for vg in lvm_config.vol_groups:
			sorted_vol = sorted(vg.volumes, key=lambda x: x.mountpoint or Path('/'))

			for vol in sorted_vol:
				if luks_handler := luks_handlers.get(vol):
					self._mount_luks_volume(vol, luks_handler)
				else:
					self._mount_lvm_vol(vol)

	def _prepare_luks_partitions(
		self,
		partitions: list[PartitionModification],
	) -> dict[PartitionModification, Luks2]:
		return {
			part_mod: device_handler.unlock_luks2_dev(
				part_mod.dev_path,
				part_mod.mapper_name,
				self._disk_encryption.encryption_password,
			)
			for part_mod in partitions
			if part_mod.mapper_name and part_mod.dev_path
		}

	def _import_lvm(self) -> None:
		lvm_config = self._disk_config.lvm_config

		if not lvm_config:
			debug('No lvm config defined to be imported')
			return

		for vg in lvm_config.vol_groups:
			device_handler.lvm_import_vg(vg)

			for vol in vg.volumes:
				device_handler.lvm_vol_change(vol, True)

	def _prepare_luks_lvm(
		self,
		lvm_volumes: list[LvmVolume],
	) -> dict[LvmVolume, Luks2]:
		return {
			vol: device_handler.unlock_luks2_dev(
				vol.dev_path,
				vol.mapper_name,
				self._disk_encryption.encryption_password,
			)
			for vol in lvm_volumes
			if vol.mapper_name and vol.dev_path
		}

	def _mount_partition(self, part_mod: PartitionModification) -> None:
		if not part_mod.dev_path:
			return

		# it would be none if it's btrfs as the subvolumes will have the mountpoints defined
		if part_mod.mountpoint:
			target = self.target / part_mod.relative_mountpoint
			device_handler.mount(part_mod.dev_path, target, options=part_mod.mount_options)
		elif part_mod.fs_type == FilesystemType.Btrfs:
			self._mount_btrfs_subvol(
				part_mod.dev_path,
				part_mod.btrfs_subvols,
				part_mod.mount_options,
			)
		elif part_mod.is_swap():
			device_handler.swapon(part_mod.dev_path)

	def _mount_lvm_vol(self, volume: LvmVolume) -> None:
		if volume.fs_type != FilesystemType.Btrfs:
			if volume.mountpoint and volume.dev_path:
				target = self.target / volume.relative_mountpoint
				device_handler.mount(volume.dev_path, target, options=volume.mount_options)

		if volume.fs_type == FilesystemType.Btrfs and volume.dev_path:
			self._mount_btrfs_subvol(volume.dev_path, volume.btrfs_subvols, volume.mount_options)

	def _mount_luks_partition(self, part_mod: PartitionModification, luks_handler: Luks2) -> None:
		if not luks_handler.mapper_dev:
			return None

		if part_mod.fs_type == FilesystemType.Btrfs and part_mod.btrfs_subvols:
			self._mount_btrfs_subvol(luks_handler.mapper_dev, part_mod.btrfs_subvols, part_mod.mount_options)
		elif part_mod.mountpoint:
			target = self.target / part_mod.relative_mountpoint
			device_handler.mount(luks_handler.mapper_dev, target, options=part_mod.mount_options)

	def _mount_luks_volume(self, volume: LvmVolume, luks_handler: Luks2) -> None:
		if volume.fs_type != FilesystemType.Btrfs:
			if volume.mountpoint and luks_handler.mapper_dev:
				target = self.target / volume.relative_mountpoint
				device_handler.mount(luks_handler.mapper_dev, target, options=volume.mount_options)

		if volume.fs_type == FilesystemType.Btrfs and luks_handler.mapper_dev:
			self._mount_btrfs_subvol(luks_handler.mapper_dev, volume.btrfs_subvols, volume.mount_options)

	def _mount_btrfs_subvol(
		self,
		dev_path: Path,
		subvolumes: list[SubvolumeModification],
		mount_options: list[str] = [],
	) -> None:
		for subvol in sorted(subvolumes, key=lambda x: x.relative_mountpoint):
			mountpoint = self.target / subvol.relative_mountpoint
			options = mount_options + [f'subvol={subvol.name}']
			device_handler.mount(dev_path, mountpoint, options=options)

	def generate_key_files(self) -> None:
		match self._disk_encryption.encryption_type:
			case EncryptionType.Luks:
				self._generate_key_files_partitions()
			case EncryptionType.LuksOnLvm:
				self._generate_key_file_lvm_volumes()
			case EncryptionType.LvmOnLuks:
				# currently LvmOnLuks only supports a single
				# partitioning layout (boot + partition)
				# so we won't need any keyfile generation atm
				pass

	def _generate_key_files_partitions(self) -> None:
		for part_mod in self._disk_encryption.partitions:
			gen_enc_file = self._disk_encryption.should_generate_encryption_file(part_mod)

			luks_handler = Luks2(
				part_mod.safe_dev_path,
				mapper_name=part_mod.mapper_name,
				password=self._disk_encryption.encryption_password,
			)

			if gen_enc_file and not part_mod.is_root():
				debug(f'Creating key-file: {part_mod.dev_path}')
				luks_handler.create_keyfile(self.target)

			if part_mod.is_root() and not gen_enc_file:
				if self._disk_encryption.hsm_device:
					if self._disk_encryption.encryption_password:
						Fido2.fido2_enroll(
							self._disk_encryption.hsm_device,
							part_mod.safe_dev_path,
							self._disk_encryption.encryption_password,
						)

	def _generate_key_file_lvm_volumes(self) -> None:
		for vol in self._disk_encryption.lvm_volumes:
			gen_enc_file = self._disk_encryption.should_generate_encryption_file(vol)

			luks_handler = Luks2(
				vol.safe_dev_path,
				mapper_name=vol.mapper_name,
				password=self._disk_encryption.encryption_password,
			)

			if gen_enc_file and not vol.is_root():
				info(f'Creating key-file: {vol.dev_path}')
				luks_handler.create_keyfile(self.target)

			if vol.is_root() and not gen_enc_file:
				if self._disk_encryption.hsm_device:
					if self._disk_encryption.encryption_password:
						Fido2.fido2_enroll(
							self._disk_encryption.hsm_device,
							vol.safe_dev_path,
							self._disk_encryption.encryption_password,
						)

	def sync_log_to_install_medium(self) -> bool:
		# Copy over the install log (if there is one) to the install medium if
		# at least the base has been strapped in, otherwise we won't have a filesystem/structure to copy to.
		if self._helper_flags.get('base-strapped', False) is True:
			absolute_logfile = logger.path

			if not os.path.isdir(f'{self.target}/{os.path.dirname(absolute_logfile)}'):
				os.makedirs(f'{self.target}/{os.path.dirname(absolute_logfile)}')

			shutil.copy2(absolute_logfile, f'{self.target}/{absolute_logfile}')

		return True

	def add_swapfile(self, size: str = '4G', enable_resume: bool = True, file: str = '/swapfile') -> None:
		if file[:1] != '/':
			file = f'/{file}'
		if len(file.strip()) <= 0 or file == '/':
			raise ValueError(f'The filename for the swap file has to be a valid path, not: {self.target}{file}')

		SysCommand(f'dd if=/dev/zero of={self.target}{file} bs={size} count=1')
		SysCommand(f'chmod 0600 {self.target}{file}')
		SysCommand(f'mkswap {self.target}{file}')

		self._fstab_entries.append(f'{file} none swap defaults 0 0')

		if enable_resume:
			resume_uuid = SysCommand(f'findmnt -no UUID -T {self.target}{file}').decode()
			resume_offset = (
				SysCommand(
					f'filefrag -v {self.target}{file}',
				)
				.decode()
				.split('0:', 1)[1]
				.split(':', 1)[1]
				.split('..', 1)[0]
				.strip()
			)

			self._hooks.append('resume')
			self._kernel_params.append(f'resume=UUID={resume_uuid}')
			self._kernel_params.append(f'resume_offset={resume_offset}')

	def post_install_check(self, *args: str, **kwargs: str) -> list[str]:
		return [step for step, flag in self._helper_flags.items() if flag is False]

	def set_mirrors(
		self,
		mirror_config: MirrorConfiguration,
		on_target: bool = False,
	) -> None:
		"""
		Set the mirror configuration for the installation.

		:param mirror_config: The mirror configuration to use.
		:type mirror_config: MirrorConfiguration

		:on_target: Whether to set the mirrors on the target system or the live system.
		:param on_target: bool
		"""
		debug('Setting mirrors on ' + ('target' if on_target else 'live system'))

		for plugin in plugins.values():
			if hasattr(plugin, 'on_mirrors'):
				if result := plugin.on_mirrors(mirror_config):
					mirror_config = result

		root = self.target if on_target else Path('/')
		mirrorlist_config = root / 'etc/pacman.d/mirrorlist'
		pacman_config = root / 'etc/pacman.conf'

		repositories_config = mirror_config.repositories_config()
		if repositories_config:
			debug(f'Pacman config: {repositories_config}')

			with open(pacman_config, 'a') as fp:
				fp.write(repositories_config)

		regions_config = mirror_config.regions_config(speed_sort=True)
		if regions_config:
			debug(f'Mirrorlist:\n{regions_config}')
			mirrorlist_config.write_text(regions_config)

		custom_servers = mirror_config.custom_servers_config()
		if custom_servers:
			debug(f'Custom servers:\n{custom_servers}')

			content = mirrorlist_config.read_text()
			mirrorlist_config.write_text(f'{custom_servers}\n\n{content}')

	def genfstab(self, flags: str = '-pU') -> None:
		fstab_path = self.target / 'etc' / 'fstab'
		info(f'Updating {fstab_path}')

		try:
			gen_fstab = SysCommand(f'genfstab {flags} {self.target}').output()
		except SysCallError as err:
			raise RequirementError(f'Could not generate fstab, strapping in packages most likely failed (disk out of space?)\n Error: {err}')

		with open(fstab_path, 'ab') as fp:
			fp.write(gen_fstab)

		if not fstab_path.is_file():
			raise RequirementError('Could not create fstab file')

		for plugin in plugins.values():
			if hasattr(plugin, 'on_genfstab'):
				if plugin.on_genfstab(self) is True:
					break

		with open(fstab_path, 'a') as fp:
			for entry in self._fstab_entries:
				fp.write(f'{entry}\n')

	def set_hostname(self, hostname: str) -> None:
		(self.target / 'etc/hostname').write_text(hostname + '\n')

	def set_locale(self, locale_config: LocaleConfiguration) -> bool:
		modifier = ''
		lang = locale_config.sys_lang
		encoding = locale_config.sys_enc

		# This is a temporary patch to fix #1200
		if '.' in locale_config.sys_lang:
			lang, potential_encoding = locale_config.sys_lang.split('.', 1)

			# Override encoding if encoding is set to the default parameter
			# and the "found" encoding differs.
			if locale_config.sys_enc == 'UTF-8' and locale_config.sys_enc != potential_encoding:
				encoding = potential_encoding

		# Make sure we extract the modifier, that way we can put it in if needed.
		if '@' in locale_config.sys_lang:
			lang, modifier = locale_config.sys_lang.split('@', 1)
			modifier = f'@{modifier}'
		# - End patch

		locale_gen = self.target / 'etc/locale.gen'
		locale_gen_lines = locale_gen.read_text().splitlines(True)

		# A locale entry in /etc/locale.gen may or may not contain the encoding
		# in the first column of the entry; check for both cases.
		entry_re = re.compile(rf'#{lang}(\.{encoding})?{modifier} {encoding}')

		lang_value = None
		for index, line in enumerate(locale_gen_lines):
			if entry_re.match(line):
				uncommented_line = line.removeprefix('#')
				locale_gen_lines[index] = uncommented_line
				locale_gen.write_text(''.join(locale_gen_lines))
				lang_value = uncommented_line.split()[0]
				break

		if lang_value is None:
			error(f"Invalid locale: language '{locale_config.sys_lang}', encoding '{locale_config.sys_enc}'")
			return False

		try:
			SysCommand(f'arch-chroot {self.target} locale-gen')
		except SysCallError as e:
			error(f'Failed to run locale-gen on target: {e}')
			return False

		(self.target / 'etc/locale.conf').write_text(f'LANG={lang_value}\n')
		return True

	def set_timezone(self, zone: str) -> bool:
		if not zone:
			return True
		if not len(zone):
			return True  # Redundant

		for plugin in plugins.values():
			if hasattr(plugin, 'on_timezone'):
				if result := plugin.on_timezone(zone):
					zone = result

		if (Path('/usr') / 'share' / 'zoneinfo' / zone).exists():
			(Path(self.target) / 'etc' / 'localtime').unlink(missing_ok=True)
			SysCommand(f'arch-chroot {self.target} ln -s /usr/share/zoneinfo/{zone} /etc/localtime')
			return True

		else:
			warn(f'Time zone {zone} does not exist, continuing with system default')

		return False

	def activate_time_synchronization(self) -> None:
		info('Activating systemd-timesyncd for time synchronization using Arch Linux and ntp.org NTP servers')
		self.enable_service('systemd-timesyncd')

	def enable_espeakup(self) -> None:
		info('Enabling espeakup.service for speech synthesis (accessibility)')
		self.enable_service('espeakup')

	def enable_periodic_trim(self) -> None:
		info('Enabling periodic TRIM')
		# fstrim is owned by util-linux, a dependency of both base and systemd.
		self.enable_service('fstrim.timer')

	def enable_service(self, services: str | list[str]) -> None:
		if isinstance(services, str):
			services = [services]

		for service in services:
			info(f'Enabling service {service}')

			try:
				self.arch_chroot(f'systemctl enable {service}')
			except SysCallError as err:
				raise ServiceException(f'Unable to start service {service}: {err}')

			for plugin in plugins.values():
				if hasattr(plugin, 'on_service'):
					plugin.on_service(service)

	def run_command(self, cmd: str, *args: str, **kwargs: str) -> SysCommand:
		return SysCommand(f'arch-chroot {self.target} {cmd}')

	def arch_chroot(self, cmd: str, run_as: str | None = None) -> SysCommand:
		if run_as:
			cmd = f'su - {run_as} -c {shlex.quote(cmd)}'

		return self.run_command(cmd)

	def drop_to_shell(self) -> None:
		subprocess.check_call(f'arch-chroot {self.target}', shell=True)

	def configure_nic(self, nic: Nic) -> None:
		conf = nic.as_systemd_config()

		for plugin in plugins.values():
			if hasattr(plugin, 'on_configure_nic'):
				conf = (
					plugin.on_configure_nic(
						nic.iface,
						nic.dhcp,
						nic.ip,
						nic.gateway,
						nic.dns,
					)
					or conf
				)

		with open(f'{self.target}/etc/systemd/network/10-{nic.iface}.network', 'a') as netconf:
			netconf.write(str(conf))

	def copy_iso_network_config(self, enable_services: bool = False) -> bool:
		# Copy (if any) iwd password and config files
		if os.path.isdir('/var/lib/iwd/'):
			if psk_files := glob.glob('/var/lib/iwd/*.psk'):
				if not os.path.isdir(f'{self.target}/var/lib/iwd'):
					os.makedirs(f'{self.target}/var/lib/iwd')

				if enable_services:
					# If we haven't installed the base yet (function called pre-maturely)
					if self._helper_flags.get('base', False) is False:
						self._base_packages.append('iwd')

						# This function will be called after minimal_installation()
						# as a hook for post-installs. This hook is only needed if
						# base is not installed yet.
						def post_install_enable_iwd_service(*args: str, **kwargs: str) -> None:
							self.enable_service('iwd')

						self.post_base_install.append(post_install_enable_iwd_service)
					# Otherwise, we can go ahead and add the required package
					# and enable it's service:
					else:
						self.pacman.strap('iwd')
						self.enable_service('iwd')

				for psk in psk_files:
					shutil.copy2(psk, f'{self.target}/var/lib/iwd/{os.path.basename(psk)}')

		# Copy (if any) systemd-networkd config files
		if netconfigurations := glob.glob('/etc/systemd/network/*'):
			if not os.path.isdir(f'{self.target}/etc/systemd/network/'):
				os.makedirs(f'{self.target}/etc/systemd/network/')

			for netconf_file in netconfigurations:
				shutil.copy2(netconf_file, f'{self.target}/etc/systemd/network/{os.path.basename(netconf_file)}')

			if enable_services:
				# If we haven't installed the base yet (function called pre-maturely)
				if self._helper_flags.get('base', False) is False:

					def post_install_enable_networkd_resolved(*args: str, **kwargs: str) -> None:
						self.enable_service(['systemd-networkd', 'systemd-resolved'])

					self.post_base_install.append(post_install_enable_networkd_resolved)
				# Otherwise, we can go ahead and enable the services
				else:
					self.enable_service(['systemd-networkd', 'systemd-resolved'])

		return True

	def mkinitcpio(self, flags: list[str]) -> bool:
		for plugin in plugins.values():
			if hasattr(plugin, 'on_mkinitcpio'):
				# Allow plugins to override the usage of mkinitcpio altogether.
				if plugin.on_mkinitcpio(self):
					return True

		with open(f'{self.target}/etc/mkinitcpio.conf', 'r+') as mkinit:
			content = mkinit.read()
			content = re.sub('\nMODULES=(.*)', f'\nMODULES=({" ".join(self._modules)})', content)
			content = re.sub('\nBINARIES=(.*)', f'\nBINARIES=({" ".join(self._binaries)})', content)
			content = re.sub('\nFILES=(.*)', f'\nFILES=({" ".join(self._files)})', content)

			if not self._disk_encryption.hsm_device:
				# For now, if we don't use HSM we revert to the old
				# way of setting up encryption hooks for mkinitcpio.
				# This is purely for stability reasons, we're going away from this.
				# * systemd -> udev
				# * sd-vconsole -> keymap
				self._hooks = [hook.replace('systemd', 'udev').replace('sd-vconsole', 'keymap consolefont') for hook in self._hooks]

			content = re.sub('\nHOOKS=(.*)', f'\nHOOKS=({" ".join(self._hooks)})', content)
			mkinit.seek(0)
			mkinit.write(content)

		try:
			SysCommand(f'arch-chroot {self.target} mkinitcpio {" ".join(flags)}', peek_output=True)
			return True
		except SysCallError as e:
			if e.worker_log:
				log(e.worker_log.decode())
			return False

	def _get_microcode(self) -> Path | None:
		if not SysInfo.is_vm():
			if vendor := SysInfo.cpu_vendor():
				return vendor.get_ucode()
		return None

	def _prepare_fs_type(
		self,
		fs_type: FilesystemType,
		mountpoint: Path | None,
	) -> None:
		if (pkg := fs_type.installation_pkg) is not None:
			self._base_packages.append(pkg)
		if (module := fs_type.installation_module) is not None:
			self._modules.append(module)
		if (binary := fs_type.installation_binary) is not None:
			self._binaries.append(binary)

		# https://github.com/archlinux/archinstall/issues/1837
		if fs_type.fs_type_mount == 'btrfs':
			self._disable_fstrim = True

		# There is not yet an fsck tool for NTFS. If it's being used for the root filesystem, the hook should be removed.
		if fs_type.fs_type_mount == 'ntfs3' and mountpoint == self.target:
			if 'fsck' in self._hooks:
				self._hooks.remove('fsck')

	def _prepare_encrypt(self, before: str = 'filesystems') -> None:
		if self._disk_encryption.hsm_device:
			# Required by mkinitcpio to add support for fido2-device options
			self.pacman.strap('libfido2')

			if 'sd-encrypt' not in self._hooks:
				self._hooks.insert(self._hooks.index(before), 'sd-encrypt')
		else:
			if 'encrypt' not in self._hooks:
				self._hooks.insert(self._hooks.index(before), 'encrypt')

	def minimal_installation(
		self,
		optional_repositories: list[Repository] = [],
		mkinitcpio: bool = True,
		hostname: str | None = None,
		locale_config: LocaleConfiguration | None = LocaleConfiguration.default(),
	) -> None:
		if self._disk_config.lvm_config:
			lvm = 'lvm2'
			self.add_additional_packages(lvm)
			self._hooks.insert(self._hooks.index('filesystems') - 1, lvm)

			for vg in self._disk_config.lvm_config.vol_groups:
				for vol in vg.volumes:
					if vol.fs_type is not None:
						self._prepare_fs_type(vol.fs_type, vol.mountpoint)

			types = (EncryptionType.LvmOnLuks, EncryptionType.LuksOnLvm)
			if self._disk_encryption.encryption_type in types:
				self._prepare_encrypt(lvm)
		else:
			for mod in self._disk_config.device_modifications:
				for part in mod.partitions:
					if part.fs_type is None:
						continue

					self._prepare_fs_type(part.fs_type, part.mountpoint)

					if part in self._disk_encryption.partitions:
						self._prepare_encrypt()

		if ucode := self._get_microcode():
			(self.target / 'boot' / ucode).unlink(missing_ok=True)
			self._base_packages.append(ucode.stem)
		else:
			debug('Archinstall will not install any ucode.')

		debug(f'Optional repositories: {optional_repositories}')

		# This action takes place on the host system as pacstrap copies over package repository lists.
		pacman_conf = PacmanConfig(self.target)
		pacman_conf.enable(optional_repositories)
		pacman_conf.apply()

		self.pacman.strap(self._base_packages)
		self._helper_flags['base-strapped'] = True

		pacman_conf.persist()

		# Periodic TRIM may improve the performance and longevity of SSDs whilst
		# having no adverse effect on other devices. Most distributions enable
		# periodic TRIM by default.
		#
		# https://github.com/archlinux/archinstall/issues/880
		# https://github.com/archlinux/archinstall/issues/1837
		# https://github.com/archlinux/archinstall/issues/1841
		if not self._disable_fstrim:
			self.enable_periodic_trim()

		# TODO: Support locale and timezone
		# os.remove(f'{self.target}/etc/localtime')
		# sys_command(f'arch-chroot {self.target} ln -s /usr/share/zoneinfo/{localtime} /etc/localtime')
		# sys_command('arch-chroot /mnt hwclock --hctosys --localtime')
		if hostname:
			self.set_hostname(hostname)

		if locale_config:
			self.set_locale(locale_config)
			self.set_keyboard_language(locale_config.kb_layout)

		# TODO: Use python functions for this
		SysCommand(f'arch-chroot {self.target} chmod 700 /root')

		if mkinitcpio and not self.mkinitcpio(['-P']):
			error('Error generating initramfs (continuing anyway)')

		self._helper_flags['base'] = True

		# Run registered post-install hooks
		for function in self.post_base_install:
			info(f'Running post-installation hook: {function}')
			function(self)

		for plugin in plugins.values():
			if hasattr(plugin, 'on_install'):
				plugin.on_install(self)

	def setup_btrfs_snapshot(
		self,
		snapshot_type: SnapshotType,
		bootloader: Bootloader | None = None,
	) -> None:
		if snapshot_type == SnapshotType.Snapper:
			debug('Setting up Btrfs snapper')
			self.pacman.strap('snapper')

			snapper: dict[str, str] = {
				'root': '/',
				'home': '/home',
			}

			for config_name, mountpoint in snapper.items():
				command = [
					'arch-chroot',
					str(self.target),
					'snapper',
					'--no-dbus',
					'-c',
					config_name,
					'create-config',
					mountpoint,
				]

				try:
					SysCommand(command, peek_output=True)
				except SysCallError as err:
					raise DiskError(f'Could not setup Btrfs snapper: {err}')

			self.enable_service('snapper-timeline.timer')
			self.enable_service('snapper-cleanup.timer')
		elif snapshot_type == SnapshotType.Timeshift:
			debug('Setting up Btrfs timeshift')

			self.pacman.strap('cronie')
			self.pacman.strap('timeshift')

			self.enable_service('cronie.service')

			if bootloader and bootloader == Bootloader.Grub:
				self.pacman.strap('grub-btrfs')
				self.pacman.strap('inotify-tools')
				self._configure_grub_btrfsd()
				self.enable_service('grub-btrfsd.service')

	def setup_swap(self, kind: str = 'zram') -> None:
		if kind == 'zram':
			info('Setting up swap on zram')
			self.pacman.strap('zram-generator')

			# We could use the default example below, but maybe not the best idea: https://github.com/archlinux/archinstall/pull/678#issuecomment-962124813
			# zram_example_location = '/usr/share/doc/zram-generator/zram-generator.conf.example'
			# shutil.copy2(f"{self.target}{zram_example_location}", f"{self.target}/usr/lib/systemd/zram-generator.conf")
			with open(f'{self.target}/etc/systemd/zram-generator.conf', 'w') as zram_conf:
				zram_conf.write('[zram0]\n')

			self.enable_service('systemd-zram-setup@zram0.service')

			self._zram_enabled = True
		else:
			raise ValueError('Archinstall currently only supports setting up swap on zram')

	def _get_efi_partition(self) -> PartitionModification | None:
		for layout in self._disk_config.device_modifications:
			if partition := layout.get_efi_partition():
				return partition
		return None

	def _get_boot_partition(self) -> PartitionModification | None:
		for layout in self._disk_config.device_modifications:
			if boot := layout.get_boot_partition():
				return boot
		return None

	def _get_root(self) -> PartitionModification | LvmVolume | None:
		if self._disk_config.lvm_config:
			return self._disk_config.lvm_config.get_root_volume()
		else:
			for mod in self._disk_config.device_modifications:
				if root := mod.get_root_partition():
					return root
		return None

	def _configure_grub_btrfsd(self) -> None:
		# See https://github.com/Antynea/grub-btrfs?tab=readme-ov-file#-using-timeshift-with-systemd
		debug('Configuring grub-btrfsd service')

		# https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html#id-1.14.3
		systemd_dir = self.target / 'etc/systemd/system/grub-btrfsd.service.d'
		systemd_dir.mkdir(parents=True, exist_ok=True)

		override_conf = systemd_dir / 'override.conf'

		config_content = textwrap.dedent(
			"""
			[Service]
			ExecStart=
			ExecStart=/usr/bin/grub-btrfsd --syslog --timeshift-auto
			"""
		)

		override_conf.write_text(config_content)
		override_conf.chmod(0o644)

	def _get_luks_uuid_from_mapper_dev(self, mapper_dev_path: Path) -> str:
		lsblk_info = get_lsblk_info(mapper_dev_path, reverse=True, full_dev_path=True)

		if not lsblk_info.children or not lsblk_info.children[0].uuid:
			raise ValueError('Unable to determine UUID of luks superblock')

		return lsblk_info.children[0].uuid

	def _get_kernel_params_partition(
		self,
		root_partition: PartitionModification,
		id_root: bool = True,
		partuuid: bool = True,
	) -> list[str]:
		kernel_parameters = []

		if root_partition in self._disk_encryption.partitions:
			# TODO: We need to detect if the encrypted device is a whole disk encryption,
			#       or simply a partition encryption. Right now we assume it's a partition (and we always have)

			if self._disk_encryption.hsm_device:
				debug(f'Root partition is an encrypted device, identifying by UUID: {root_partition.uuid}')
				# Note: UUID must be used, not PARTUUID for sd-encrypt to work
				kernel_parameters.append(f'rd.luks.name={root_partition.uuid}=root')
				# Note: tpm2-device and fido2-device don't play along very well:
				# https://github.com/archlinux/archinstall/pull/1196#issuecomment-1129715645
				kernel_parameters.append('rd.luks.options=fido2-device=auto,password-echo=no')
			elif partuuid:
				debug(f'Root partition is an encrypted device, identifying by PARTUUID: {root_partition.partuuid}')
				kernel_parameters.append(f'cryptdevice=PARTUUID={root_partition.partuuid}:root')
			else:
				debug(f'Root partition is an encrypted device, identifying by UUID: {root_partition.uuid}')
				kernel_parameters.append(f'cryptdevice=UUID={root_partition.uuid}:root')

			if id_root:
				kernel_parameters.append('root=/dev/mapper/root')
		elif id_root:
			if partuuid:
				debug(f'Identifying root partition by PARTUUID: {root_partition.partuuid}')
				kernel_parameters.append(f'root=PARTUUID={root_partition.partuuid}')
			else:
				debug(f'Identifying root partition by UUID: {root_partition.uuid}')
				kernel_parameters.append(f'root=UUID={root_partition.uuid}')

		return kernel_parameters

	def _get_kernel_params_lvm(
		self,
		lvm: LvmVolume,
	) -> list[str]:
		kernel_parameters = []

		match self._disk_encryption.encryption_type:
			case EncryptionType.LvmOnLuks:
				if not lvm.vg_name:
					raise ValueError(f'Unable to determine VG name for {lvm.name}')

				pv_seg_info = device_handler.lvm_pvseg_info(lvm.vg_name, lvm.name)

				if not pv_seg_info:
					raise ValueError(f'Unable to determine PV segment info for {lvm.vg_name}/{lvm.name}')

				uuid = self._get_luks_uuid_from_mapper_dev(pv_seg_info.pv_name)

				if self._disk_encryption.hsm_device:
					debug(f'LvmOnLuks, encrypted root partition, HSM, identifying by UUID: {uuid}')
					kernel_parameters.append(f'rd.luks.name={uuid}=cryptlvm root={lvm.safe_dev_path}')
				else:
					debug(f'LvmOnLuks, encrypted root partition, identifying by UUID: {uuid}')
					kernel_parameters.append(f'cryptdevice=UUID={uuid}:cryptlvm root={lvm.safe_dev_path}')
			case EncryptionType.LuksOnLvm:
				uuid = self._get_luks_uuid_from_mapper_dev(lvm.mapper_path)

				if self._disk_encryption.hsm_device:
					debug(f'LuksOnLvm, encrypted root partition, HSM, identifying by UUID: {uuid}')
					kernel_parameters.append(f'rd.luks.name={uuid}=root root=/dev/mapper/root')
				else:
					debug(f'LuksOnLvm, encrypted root partition, identifying by UUID: {uuid}')
					kernel_parameters.append(f'cryptdevice=UUID={uuid}:root root=/dev/mapper/root')
			case EncryptionType.NoEncryption:
				debug(f'Identifying root lvm by mapper device: {lvm.dev_path}')
				kernel_parameters.append(f'root={lvm.safe_dev_path}')

		return kernel_parameters

	def _get_kernel_params(
		self,
		root: PartitionModification | LvmVolume,
		id_root: bool = True,
		partuuid: bool = True,
	) -> list[str]:
		kernel_parameters = []

		if isinstance(root, LvmVolume):
			kernel_parameters = self._get_kernel_params_lvm(root)
		else:
			kernel_parameters = self._get_kernel_params_partition(root, id_root, partuuid)

		# Zswap should be disabled when using zram.
		# https://github.com/archlinux/archinstall/issues/881
		if self._zram_enabled:
			kernel_parameters.append('zswap.enabled=0')

		if id_root:
			for sub_vol in root.btrfs_subvols:
				if sub_vol.is_root():
					kernel_parameters.append(f'rootflags=subvol={sub_vol.name}')
					break

			kernel_parameters.append('rw')

		kernel_parameters.append(f'rootfstype={root.safe_fs_type.fs_type_mount}')
		kernel_parameters.extend(self._kernel_params)

		debug(f'kernel parameters: {" ".join(kernel_parameters)}')

		return kernel_parameters

	def _create_bls_entries(
		self,
		boot_partition: PartitionModification,
		root: PartitionModification | LvmVolume,
		entry_name: str,
	) -> None:
		# Loader entries are stored in $BOOT/loader:
		# https://uapi-group.org/specifications/specs/boot_loader_specification/#mount-points
		entries_dir = self.target / boot_partition.relative_mountpoint / 'loader/entries'
		# Ensure that the $BOOT/loader/entries/ directory exists before trying to create files in it
		entries_dir.mkdir(parents=True, exist_ok=True)

		entry_template = textwrap.dedent(
			f"""\
			# Created by: archinstall
			# Created on: {self.init_time}
			title   Arch Linux ({{kernel}}{{variant}})
			linux   /vmlinuz-{{kernel}}
			initrd  /initramfs-{{kernel}}{{variant}}.img
			options {' '.join(self._get_kernel_params(root))}
			""",
		)

		for kernel in self.kernels:
			for variant in ('', '-fallback'):
				# Setup the loader entry
				name = entry_name.format(kernel=kernel, variant=variant)
				entry_conf = entries_dir / name
				entry_conf.write_text(entry_template.format(kernel=kernel, variant=variant))

	def _add_systemd_bootloader(
		self,
		boot_partition: PartitionModification,
		root: PartitionModification | LvmVolume,
		efi_partition: PartitionModification | None,
		uki_enabled: bool = False,
	) -> None:
		debug('Installing systemd bootloader')

		self.pacman.strap('efibootmgr')

		if not SysInfo.has_uefi():
			raise HardwareIncompatibilityError

		if not efi_partition:
			raise ValueError('Could not detect EFI system partition')
		elif not efi_partition.mountpoint:
			raise ValueError('EFI system partition is not mounted')

		# TODO: Ideally we would want to check if another config
		# points towards the same disk and/or partition.
		# And in which case we should do some clean up.
		bootctl_options = []

		if boot_partition != efi_partition:
			bootctl_options.append(f'--esp-path={efi_partition.mountpoint}')
			bootctl_options.append(f'--boot-path={boot_partition.mountpoint}')

		# TODO: This is a temporary workaround to deal with https://github.com/archlinux/archinstall/pull/3396#issuecomment-2996862019
		# the systemd_version check can be removed once `--variables=BOOL` is merged into systemd.
		systemd_pkg = installed_package('systemd')

		# keep the version as a str as it can be something like 257.8-2
		if systemd_pkg is not None:
			systemd_version = systemd_pkg.version
		else:
			systemd_version = '257'  # This works as a safety workaround for this hot-fix

		try:
			# Force EFI variables since bootctl detects arch-chroot
			# as a container environemnt since v257 and skips them silently.
			# https://github.com/systemd/systemd/issues/36174
			if systemd_version >= '258':
				SysCommand(f'arch-chroot {self.target} bootctl --variables=yes {" ".join(bootctl_options)} install')
			else:
				SysCommand(f'arch-chroot {self.target} bootctl {" ".join(bootctl_options)} install')
		except SysCallError:
			if systemd_version >= '258':
				# Fallback, try creating the boot loader without touching the EFI variables
				SysCommand(f'arch-chroot {self.target} bootctl --variables=no {" ".join(bootctl_options)} install')
			else:
				SysCommand(f'arch-chroot {self.target} bootctl --no-variables {" ".join(bootctl_options)} install')

		# Loader configuration is stored in ESP/loader:
		# https://man.archlinux.org/man/loader.conf.5
		loader_conf = self.target / efi_partition.relative_mountpoint / 'loader/loader.conf'
		# Ensure that the ESP/loader/ directory exists before trying to create a file in it
		loader_conf.parent.mkdir(parents=True, exist_ok=True)

		default_kernel = self.kernels[0]
		if uki_enabled:
			default_entry = f'arch-{default_kernel}.efi'
		else:
			entry_name = self.init_time + '_{kernel}{variant}.conf'
			default_entry = entry_name.format(kernel=default_kernel, variant='')
			self._create_bls_entries(boot_partition, root, entry_name)

		default = f'default {default_entry}'

		# Modify or create a loader.conf
		try:
			loader_data = loader_conf.read_text().splitlines()
		except FileNotFoundError:
			loader_data = [
				default,
				'timeout 15',
			]
		else:
			for index, line in enumerate(loader_data):
				if line.startswith('default'):
					loader_data[index] = default
				elif line.startswith('#timeout'):
					# We add in the default timeout to support dual-boot
					loader_data[index] = line.removeprefix('#')

		loader_conf.write_text('\n'.join(loader_data) + '\n')

		self._helper_flags['bootloader'] = 'systemd'

	def _add_grub_bootloader(
		self,
		boot_partition: PartitionModification,
		root: PartitionModification | LvmVolume,
		efi_partition: PartitionModification | None,
	) -> None:
		debug('Installing grub bootloader')

		self.pacman.strap('grub')

		grub_default = self.target / 'etc/default/grub'
		config = grub_default.read_text()

		kernel_parameters = ' '.join(self._get_kernel_params(root, False, False))
		config = re.sub(r'(GRUB_CMDLINE_LINUX=")("\n)', rf'\1{kernel_parameters}\2', config, count=1)

		grub_default.write_text(config)

		info(f'GRUB boot partition: {boot_partition.dev_path}')

		boot_dir = Path('/boot')

		command = [
			'arch-chroot',
			str(self.target),
			'grub-install',
			'--debug',
		]

		if SysInfo.has_uefi():
			if not efi_partition:
				raise ValueError('Could not detect efi partition')

			info(f'GRUB EFI partition: {efi_partition.dev_path}')

			self.pacman.strap('efibootmgr')  # TODO: Do we need? Yes, but remove from minimal_installation() instead?

			boot_dir_arg = []
			if boot_partition.mountpoint and boot_partition.mountpoint != boot_dir:
				boot_dir_arg.append(f'--boot-directory={boot_partition.mountpoint}')
				boot_dir = boot_partition.mountpoint

			add_options = [
				f'--target={platform.machine()}-efi',
				f'--efi-directory={efi_partition.mountpoint}',
				*boot_dir_arg,
				'--bootloader-id=GRUB',
				'--removable',
			]

			command.extend(add_options)

			try:
				SysCommand(command, peek_output=True)
			except SysCallError:
				try:
					SysCommand(command, peek_output=True)
				except SysCallError as err:
					raise DiskError(f'Could not install GRUB to {self.target}{efi_partition.mountpoint}: {err}')
		else:
			info(f'GRUB boot partition: {boot_partition.dev_path}')

			parent_dev_path = device_handler.get_parent_device_path(boot_partition.safe_dev_path)

			add_options = [
				'--target=i386-pc',
				'--recheck',
				str(parent_dev_path),
			]

			try:
				SysCommand(command + add_options, peek_output=True)
			except SysCallError as err:
				raise DiskError(f'Failed to install GRUB boot on {boot_partition.dev_path}: {err}')

		try:
			SysCommand(
				f'arch-chroot {self.target} grub-mkconfig -o {boot_dir}/grub/grub.cfg',
			)
		except SysCallError as err:
			raise DiskError(f'Could not configure GRUB: {err}')

		self._helper_flags['bootloader'] = 'grub'

	def _add_limine_bootloader(
		self,
		boot_partition: PartitionModification,
		efi_partition: PartitionModification | None,
		root: PartitionModification | LvmVolume,
		uki_enabled: bool = False,
	) -> None:
		debug('Installing Limine bootloader')

		self.pacman.strap('limine')

		info(f'Limine boot partition: {boot_partition.dev_path}')

		limine_path = self.target / 'usr' / 'share' / 'limine'
		config_path = None
		hook_command = None

		if SysInfo.has_uefi():
			self.pacman.strap('efibootmgr')

			if not efi_partition:
				raise ValueError('Could not detect efi partition')
			elif not efi_partition.mountpoint:
				raise ValueError('EFI partition is not mounted')

			info(f'Limine EFI partition: {efi_partition.dev_path}')

			parent_dev_path = device_handler.get_parent_device_path(efi_partition.safe_dev_path)
			is_target_usb = (
				SysCommand(
					f'udevadm info --no-pager --query=property --property=ID_BUS --value --name={parent_dev_path}',
				).decode()
				== 'usb'
			)

			try:
				efi_dir_path = self.target / efi_partition.mountpoint.relative_to('/') / 'EFI'
				efi_dir_path_target = efi_partition.mountpoint / 'EFI'
				if is_target_usb:
					efi_dir_path = efi_dir_path / 'BOOT'
					efi_dir_path_target = efi_dir_path_target / 'BOOT'
				else:
					efi_dir_path = efi_dir_path / 'limine'
					efi_dir_path_target = efi_dir_path_target / 'limine'

				efi_dir_path.mkdir(parents=True, exist_ok=True)

				for file in ('BOOTIA32.EFI', 'BOOTX64.EFI'):
					shutil.copy(limine_path / file, efi_dir_path)
			except Exception as err:
				raise DiskError(f'Failed to install Limine in {self.target}{efi_partition.mountpoint}: {err}')

			config_path = efi_dir_path / 'limine.conf'

			hook_command = (
				f'/usr/bin/cp /usr/share/limine/BOOTIA32.EFI {efi_dir_path_target}/ && /usr/bin/cp /usr/share/limine/BOOTX64.EFI {efi_dir_path_target}/'
			)

			if not is_target_usb:
				# Create EFI boot menu entry for Limine.
				try:
					with open('/sys/firmware/efi/fw_platform_size') as fw_platform_size:
						efi_bitness = fw_platform_size.read().strip()
				except Exception as err:
					raise OSError(f'Could not open or read /sys/firmware/efi/fw_platform_size to determine EFI bitness: {err}')

				if efi_bitness == '64':
					loader_path = '/EFI/limine/BOOTX64.EFI'
				elif efi_bitness == '32':
					loader_path = '/EFI/limine/BOOTIA32.EFI'
				else:
					raise ValueError(f'EFI bitness is neither 32 nor 64 bits. Found "{efi_bitness}".')

				try:
					SysCommand(
						'efibootmgr'
						' --create'
						f' --disk {parent_dev_path}'
						f' --part {efi_partition.partn}'
						' --label "Arch Linux Limine Bootloader"'
						f' --loader {loader_path}'
						' --unicode'
						' --verbose',
					)
				except Exception as err:
					raise ValueError(f'SysCommand for efibootmgr failed: {err}')
		else:
			boot_limine_path = self.target / 'boot' / 'limine'
			boot_limine_path.mkdir(parents=True, exist_ok=True)

			config_path = boot_limine_path / 'limine.conf'

			parent_dev_path = device_handler.get_parent_device_path(boot_partition.safe_dev_path)

			if unique_path := device_handler.get_unique_path_for_device(parent_dev_path):
				parent_dev_path = unique_path

			try:
				# The `limine-bios.sys` file contains stage 3 code.
				shutil.copy(limine_path / 'limine-bios.sys', boot_limine_path)

				# `limine bios-install` deploys the stage 1 and 2 to the
				SysCommand(f'arch-chroot {self.target} limine bios-install {parent_dev_path}', peek_output=True)
			except Exception as err:
				raise DiskError(f'Failed to install Limine on {parent_dev_path}: {err}')

			hook_command = f'/usr/bin/limine bios-install {parent_dev_path} && /usr/bin/cp /usr/share/limine/limine-bios.sys /boot/limine/'

		hook_contents = textwrap.dedent(
			f'''\
			[Trigger]
			Operation = Install
			Operation = Upgrade
			Type = Package
			Target = limine

			[Action]
			Description = Deploying Limine after upgrade...
			When = PostTransaction
			Exec = /bin/sh -c "{hook_command}"
			''',
		)

		hooks_dir = self.target / 'etc' / 'pacman.d' / 'hooks'
		hooks_dir.mkdir(parents=True, exist_ok=True)

		hook_path = hooks_dir / '99-limine.hook'
		hook_path.write_text(hook_contents)

		kernel_params = ' '.join(self._get_kernel_params(root))
		config_contents = 'timeout: 5\n'

		path_root = 'boot()'
		if efi_partition and boot_partition != efi_partition:
			path_root = f'uuid({boot_partition.partuuid})'

		for kernel in self.kernels:
			for variant in ('', '-fallback'):
				if uki_enabled:
					entry = [
						'protocol: efi',
						f'path: boot():/EFI/Linux/arch-{kernel}.efi',
						f'cmdline: {kernel_params}',
					]
				else:
					entry = [
						'protocol: linux',
						f'path: {path_root}:/vmlinuz-{kernel}',
						f'cmdline: {kernel_params}',
						f'module_path: {path_root}:/initramfs-{kernel}{variant}.img',
					]

				config_contents += f'\n/Arch Linux ({kernel}{variant})\n'
				config_contents += '\n'.join([f'    {it}' for it in entry]) + '\n'

		config_path.write_text(config_contents)

		self._helper_flags['bootloader'] = 'limine'

	def _add_efistub_bootloader(
		self,
		boot_partition: PartitionModification,
		root: PartitionModification | LvmVolume,
		uki_enabled: bool = False,
	) -> None:
		debug('Installing efistub bootloader')

		self.pacman.strap('efibootmgr')

		if not SysInfo.has_uefi():
			raise HardwareIncompatibilityError

		# TODO: Ideally we would want to check if another config
		# points towards the same disk and/or partition.
		# And in which case we should do some clean up.

		if not uki_enabled:
			loader = '/vmlinuz-{kernel}'

			entries = (
				'initrd=/initramfs-{kernel}.img',
				*self._get_kernel_params(root),
			)

			cmdline = [' '.join(entries)]
		else:
			loader = '/EFI/Linux/arch-{kernel}.efi'
			cmdline = []

		parent_dev_path = device_handler.get_parent_device_path(boot_partition.safe_dev_path)

		cmd_template = (
			'efibootmgr',
			'--create',
			'--disk',
			str(parent_dev_path),
			'--part',
			str(boot_partition.partn),
			'--label',
			'Arch Linux ({kernel})',
			'--loader',
			loader,
			'--unicode',
			*cmdline,
			'--verbose',
		)

		for kernel in self.kernels:
			# Setup the firmware entry
			cmd = [arg.format(kernel=kernel) for arg in cmd_template]
			SysCommand(cmd)

		self._helper_flags['bootloader'] = 'efistub'

	def _config_uki(
		self,
		root: PartitionModification | LvmVolume,
		efi_partition: PartitionModification | None,
	) -> None:
		if not efi_partition or not efi_partition.mountpoint:
			raise ValueError(f'Could not detect ESP at mountpoint {self.target}')

		# Set up kernel command line
		with open(self.target / 'etc/kernel/cmdline', 'w') as cmdline:
			kernel_parameters = self._get_kernel_params(root)
			cmdline.write(' '.join(kernel_parameters) + '\n')

		diff_mountpoint = None

		if efi_partition.mountpoint != Path('/efi'):
			diff_mountpoint = str(efi_partition.mountpoint)

		image_re = re.compile('(.+_image="/([^"]+).+\n)')
		uki_re = re.compile('#((.+_uki=")/[^/]+(.+\n))')

		# Modify .preset files
		for kernel in self.kernels:
			preset = self.target / 'etc/mkinitcpio.d' / (kernel + '.preset')
			config = preset.read_text().splitlines(True)

			for index, line in enumerate(config):
				# Avoid storing redundant image file
				if m := image_re.match(line):
					image = self.target / m.group(2)
					image.unlink(missing_ok=True)
					config[index] = '#' + m.group(1)
				elif m := uki_re.match(line):
					if diff_mountpoint:
						config[index] = m.group(2) + diff_mountpoint + m.group(3)
					else:
						config[index] = m.group(1)
				elif line.startswith('#default_options='):
					config[index] = line.removeprefix('#')

			preset.write_text(''.join(config))

		# Directory for the UKIs
		uki_dir = self.target / efi_partition.relative_mountpoint / 'EFI/Linux'
		uki_dir.mkdir(parents=True, exist_ok=True)

		# Build the UKIs
		if not self.mkinitcpio(['-P']):
			error('Error generating initramfs (continuing anyway)')

	def add_bootloader(self, bootloader: Bootloader, uki_enabled: bool = False) -> None:
		"""
		Adds a bootloader to the installation instance.
		Archinstall supports one of three types:
		* systemd-bootctl
		* grub
		* limine (beta)
		* efistub (beta)

		:param bootloader: Type of bootloader to be added
		"""

		for plugin in plugins.values():
			if hasattr(plugin, 'on_add_bootloader'):
				# Allow plugins to override the boot-loader handling.
				# This allows for bot configuring and installing bootloaders.
				if plugin.on_add_bootloader(self):
					return

		efi_partition = self._get_efi_partition()
		boot_partition = self._get_boot_partition()
		root = self._get_root()

		if boot_partition is None:
			raise ValueError(f'Could not detect boot at mountpoint {self.target}')

		if root is None:
			raise ValueError(f'Could not detect root at mountpoint {self.target}')

		info(f'Adding bootloader {bootloader.value} to {boot_partition.dev_path}')

		if uki_enabled:
			self._config_uki(root, efi_partition)

		match bootloader:
			case Bootloader.Systemd:
				self._add_systemd_bootloader(boot_partition, root, efi_partition, uki_enabled)
			case Bootloader.Grub:
				self._add_grub_bootloader(boot_partition, root, efi_partition)
			case Bootloader.Efistub:
				self._add_efistub_bootloader(boot_partition, root, uki_enabled)
			case Bootloader.Limine:
				self._add_limine_bootloader(boot_partition, efi_partition, root, uki_enabled)

	def add_additional_packages(self, packages: str | list[str]) -> None:
		return self.pacman.strap(packages)

	def enable_sudo(self, user: User, group: bool = False) -> None:
		info(f'Enabling sudo permissions for {user.username}')

		sudoers_dir = self.target / 'etc/sudoers.d'

		# Creates directory if not exists
		if not sudoers_dir.exists():
			sudoers_dir.mkdir(parents=True)
			# Guarantees sudoer confs directory recommended perms
			sudoers_dir.chmod(0o440)
			# Appends a reference to the sudoers file, because if we are here sudoers.d did not exist yet
			with open(self.target / 'etc/sudoers', 'a') as sudoers:
				sudoers.write('@includedir /etc/sudoers.d\n')

		# We count how many files are there already so we know which number to prefix the file with
		num_of_rules_already = len(os.listdir(sudoers_dir))
		file_num_str = f'{num_of_rules_already:02d}'  # We want 00_user1, 01_user2, etc

		# Guarantees that username str does not contain invalid characters for a linux file name:
		# \ / : * ? " < > |
		safe_username_file_name = re.sub(r'(\\|\/|:|\*|\?|"|<|>|\|)', '', user.username)

		rule_file = sudoers_dir / f'{file_num_str}_{safe_username_file_name}'

		with rule_file.open('a') as sudoers:
			sudoers.write(f'{"%" if group else ""}{user.username} ALL=(ALL) ALL\n')

		# Guarantees sudoer conf file recommended perms
		rule_file.chmod(0o440)

	def create_users(self, users: User | list[User]) -> None:
		if not isinstance(users, list):
			users = [users]

		for user in users:
			self._create_user(user)

	def _create_user(self, user: User) -> None:
		# This plugin hook allows for the plugin to handle the creation of the user.
		# Password and Group management is still handled by user_create()
		handled_by_plugin = False
		for plugin in plugins.values():
			if hasattr(plugin, 'on_user_create'):
				if result := plugin.on_user_create(self, user):
					handled_by_plugin = result

		if not handled_by_plugin:
			info(f'Creating user {user.username}')

			cmd = f'arch-chroot {self.target} useradd -m'

			if user.sudo:
				cmd += ' -G wheel'

			cmd += f' {user.username}'

			try:
				SysCommand(cmd)
			except SysCallError as err:
				raise SystemError(f'Could not create user inside installation: {err}')

		for plugin in plugins.values():
			if hasattr(plugin, 'on_user_created'):
				if result := plugin.on_user_created(self, user):
					handled_by_plugin = result

		self.set_user_password(user)

		for group in user.groups:
			SysCommand(f'arch-chroot {self.target} gpasswd -a {user.username} {group}')

		if user.sudo:
			self.enable_sudo(user)

	def set_user_password(self, user: User) -> bool:
		info(f'Setting password for {user.username}')

		enc_password = user.password.enc_password

		if not enc_password:
			debug('User password is empty')
			return False

		input_data = f'{user.username}:{enc_password}'.encode()
		cmd = ['arch-chroot', str(self.target), 'chpasswd', '--encrypted']

		try:
			run(cmd, input_data=input_data)
			return True
		except CalledProcessError as err:
			debug(f'Error setting user password: {err}')
			return False

	def user_set_shell(self, user: str, shell: str) -> bool:
		info(f'Setting shell for {user} to {shell}')

		try:
			SysCommand(f'arch-chroot {self.target} sh -c "chsh -s {shell} {user}"')
			return True
		except SysCallError:
			return False

	def chown(self, owner: str, path: str, options: list[str] = []) -> bool:
		cleaned_path = path.replace("'", "\\'")
		try:
			SysCommand(f"arch-chroot {self.target} sh -c 'chown {' '.join(options)} {owner} {cleaned_path}'")
			return True
		except SysCallError:
			return False

	def set_keyboard_language(self, language: str) -> bool:
		info(f'Setting keyboard language to {language}')

		if len(language.strip()):
			if not verify_keyboard_layout(language):
				error(f'Invalid keyboard language specified: {language}')
				return False

			# In accordance with https://github.com/archlinux/archinstall/issues/107#issuecomment-841701968
			# Setting an empty keymap first, allows the subsequent call to set layout for both console and x11.
			from .boot import Boot

			with Boot(self) as session:
				os.system('systemd-run --machine=archinstall --pty localectl set-keymap ""')

				try:
					session.SysCommand(['localectl', 'set-keymap', language])
				except SysCallError as err:
					raise ServiceException(f"Unable to set locale '{language}' for console: {err}")

				info(f'Keyboard language for this installation is now set to: {language}')
		else:
			info('Keyboard language was not changed from default (no language specified)')

		return True

	def set_x11_keyboard_language(self, language: str) -> bool:
		"""
		A fallback function to set x11 layout specifically and separately from console layout.
		This isn't strictly necessary since .set_keyboard_language() does this as well.
		"""
		info(f'Setting x11 keyboard language to {language}')

		if len(language.strip()):
			if not verify_x11_keyboard_layout(language):
				error(f'Invalid x11-keyboard language specified: {language}')
				return False

			from .boot import Boot

			with Boot(self) as session:
				session.SysCommand(['localectl', 'set-x11-keymap', '""'])

				try:
					session.SysCommand(['localectl', 'set-x11-keymap', language])
				except SysCallError as err:
					raise ServiceException(f"Unable to set locale '{language}' for X11: {err}")
		else:
			info('X11-Keyboard language was not changed from default (no language specified)')

		return True

	def _service_started(self, service_name: str) -> str | None:
		if os.path.splitext(service_name)[1] not in ('.service', '.target', '.timer'):
			service_name += '.service'  # Just to be safe

		last_execution_time = (
			SysCommand(
				f'systemctl show --property=ActiveEnterTimestamp --no-pager {service_name}',
				environment_vars={'SYSTEMD_COLORS': '0'},
			)
			.decode()
			.removeprefix('ActiveEnterTimestamp=')
		)

		if not last_execution_time:
			return None

		return last_execution_time

	def _service_state(self, service_name: str) -> str:
		if os.path.splitext(service_name)[1] not in ('.service', '.target', '.timer'):
			service_name += '.service'  # Just to be safe

		return SysCommand(
			f'systemctl show --no-pager -p SubState --value {service_name}',
			environment_vars={'SYSTEMD_COLORS': '0'},
		).decode()


def accessibility_tools_in_use() -> bool:
	return os.system('systemctl is-active --quiet espeakup.service') == 0


def run_custom_user_commands(commands: list[str], installation: Installer) -> None:
	for index, command in enumerate(commands):
		script_path = f'/var/tmp/user-command.{index}.sh'
		chroot_path = f'{installation.target}/{script_path}'

		info(f'Executing custom command "{command}" ...')
		with open(chroot_path, 'w') as user_script:
			user_script.write(command)

		SysCommand(f'arch-chroot {installation.target} bash {script_path}')

		os.unlink(chroot_path)
