import glob
import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, List, Optional, TYPE_CHECKING, Union, Dict, Callable

from . import disk
from .exceptions import DiskError, ServiceException, RequirementError, HardwareIncompatibilityError, SysCallError
from .general import SysCommand
from .hardware import SysInfo
from .locale import LocaleConfiguration
from .locale import verify_keyboard_layout, verify_x11_keyboard_layout
from .luks import Luks2
from .mirrors import MirrorConfiguration
from .models.bootloader import Bootloader
from .models.network_configuration import Nic
from .models.users import User
from .output import log, error, info, warn, debug
from . import pacman
from .pacman import Pacman
from .plugins import plugins
from .storage import storage

if TYPE_CHECKING:
	_: Any

# Any package that the Installer() is responsible for (optional and the default ones)
__packages__ = ["base", "base-devel", "linux-firmware", "linux", "linux-lts", "linux-zen", "linux-hardened"]

# Additional packages that are installed if the user is running the Live ISO with accessibility tools enabled
__accessibility_packages__ = ["brltty", "espeakup", "alsa-utils"]


def accessibility_tools_in_use() -> bool:
	return os.system('systemctl is-active --quiet espeakup.service') == 0


class Installer:
	def __init__(
		self,
		target: Path,
		disk_config: disk.DiskLayoutConfiguration,
		disk_encryption: Optional[disk.DiskEncryption] = None,
		base_packages: List[str] = [],
		kernels: Optional[List[str]] = None
	):
		"""
		`Installer()` is the wrapper for most basic installation steps.
		It also wraps :py:func:`~archinstall.Installer.pacstrap` among other things.
		"""
		self._base_packages = base_packages or __packages__[:3]
		self.kernels = kernels or ['linux']
		self._disk_config = disk_config

		self._disk_encryption = disk_encryption or disk.DiskEncryption(disk.EncryptionType.NoEncryption)
		self.target: Path = target

		self.init_time = time.strftime('%Y-%m-%d_%H-%M-%S')
		self.milliseconds = int(str(time.time()).split('.')[1])
		self.helper_flags: Dict[str, Any] = {'base': False, 'bootloader': None}

		for kernel in self.kernels:
			self._base_packages.append(kernel)

		# If using accessibility tools in the live environment, append those to the packages list
		if accessibility_tools_in_use():
			self._base_packages.extend(__accessibility_packages__)

		self.post_base_install: List[Callable] = []

		# TODO: Figure out which one of these two we'll use.. But currently we're mixing them..
		storage['session'] = self
		storage['installation_session'] = self

		self._modules: List[str] = []
		self._binaries: List[str] = []
		self._files: List[str] = []

		# systemd, sd-vconsole and sd-encrypt will be replaced by udev, keymap and encrypt
		# if HSM is not used to encrypt the root volume. Check mkinitcpio() function for that override.
		self._hooks: List[str] = [
			"base", "systemd", "autodetect", "microcode", "modconf", "kms", "keyboard",
			"sd-vconsole", "block", "filesystems", "fsck"
		]
		self._kernel_params: List[str] = []
		self._fstab_entries: List[str] = []

		self._zram_enabled = False
		self._disable_fstrim = False

		self.pacman = Pacman(self.target, storage['arguments'].get('silent', False))

	def __enter__(self) -> 'Installer':
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		if exc_type is not None:
			error(exc_val)

			self.sync_log_to_install_medium()

			# We avoid printing /mnt/<log path> because that might confuse people if they note it down
			# and then reboot, and a identical log file will be found in the ISO medium anyway.
			print(_("[!] A log file has been created here: {}").format(
				os.path.join(storage['LOG_PATH'], storage['LOG_FILE'])))
			print(_("    Please submit this issue (and file) to https://github.com/archlinux/archinstall/issues"))
			raise exc_val

		if not (missing_steps := self.post_install_check()):
			log('Installation completed without any errors. You may now reboot.', fg='green')
			self.sync_log_to_install_medium()
			return True
		else:
			warn('Some required steps were not successfully installed/configured before leaving the installer:')

			for step in missing_steps:
				warn(f' - {step}')

			warn(f"Detailed error logs can be found at: {storage['LOG_PATH']}")
			warn("Submit this zip file as an issue to https://github.com/archlinux/archinstall/issues")

			self.sync_log_to_install_medium()
			return False

	def remove_mod(self, mod: str):
		if mod in self._modules:
			self._modules.remove(mod)

	def append_mod(self, mod: str):
		if mod not in self._modules:
			self._modules.append(mod)

	def _verify_service_stop(self):
		"""
		Certain services might be running that affects the system during installation.
		One such service is "reflector.service" which updates /etc/pacman.d/mirrorlist
		We need to wait for it before we continue since we opted in to use a custom mirror/region.
		"""

		if not storage['arguments'].get('skip_ntp', False):
			info(_('Waiting for time sync (timedatectl show) to complete.'))

			_started_wait = time.time()
			_notified = False
			while True:
				if not _notified and time.time() - _started_wait > 5:
					_notified = True
					warn(
						_("Time synchronization not completing, while you wait - check the docs for workarounds: https://archinstall.readthedocs.io/"))

				time_val = SysCommand('timedatectl show --property=NTPSynchronized --value').decode()
				if time_val and time_val.strip() == 'yes':
					break
				time.sleep(1)
		else:
			info(
				_('Skipping waiting for automatic time sync (this can cause issues if time is out of sync during installation)'))

		info('Waiting for automatic mirror selection (reflector) to complete.')
		while self._service_state('reflector') not in ('dead', 'failed', 'exited'):
			time.sleep(1)

		# info('Waiting for pacman-init.service to complete.')
		# while self._service_state('pacman-init') not in ('dead', 'failed', 'exited'):
		# 	time.sleep(1)

		info(_('Waiting for Arch Linux keyring sync (archlinux-keyring-wkd-sync) to complete.'))
		# Wait for the timer to kick in
		while self._service_started('archlinux-keyring-wkd-sync.timer') is None:
			time.sleep(1)

		# Wait for the service to enter a finished state
		while self._service_state('archlinux-keyring-wkd-sync.service') not in ('dead', 'failed', 'exited'):
			time.sleep(1)

	def _verify_boot_part(self):
		"""
		Check that mounted /boot device has at minimum size for installation
		The reason this check is here is to catch pre-mounted device configuration and potentially
		configured one that has not gone through any previous checks (e.g. --silence mode)

		NOTE: this function should be run AFTER running the mount_ordered_layout function
		"""
		boot_mount = self.target / 'boot'
		lsblk_info = disk.get_lsblk_by_mountpoint(boot_mount)

		if len(lsblk_info) > 0:
			if lsblk_info[0].size < disk.Size(200, disk.Unit.MiB, disk.SectorSize.default()):
				raise DiskError(
					f'The boot partition mounted at {boot_mount} is not large enough to install a boot loader. '
					f'Please resize it to at least 200MiB and re-run the installation.'
				)

	def sanity_check(self) -> None:
		# self._verify_boot_part()
		self._verify_service_stop()

	def mount_ordered_layout(self) -> None:
		debug('Mounting ordered layout')

		luks_handlers: Dict[Any, Luks2] = {}

		match self._disk_encryption.encryption_type:
			case disk.EncryptionType.NoEncryption:
				self._mount_lvm_layout()
			case disk.EncryptionType.Luks:
				luks_handlers = self._prepare_luks_partitions(self._disk_encryption.partitions)
			case disk.EncryptionType.LvmOnLuks:
				luks_handlers = self._prepare_luks_partitions(self._disk_encryption.partitions)
				self._import_lvm()
				self._mount_lvm_layout(luks_handlers)
			case disk.EncryptionType.LuksOnLvm:
				self._import_lvm()
				luks_handlers = self._prepare_luks_lvm(self._disk_encryption.lvm_volumes)
				self._mount_lvm_layout(luks_handlers)

		# mount all regular partitions
		self._mount_partition_layout(luks_handlers)

	def _mount_partition_layout(self, luks_handlers: Dict[Any, Luks2]):
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
			not_pv_part_mods = list(filter(lambda x: x not in pvs, mod.partitions))

			# partitions have to mounted in the right order on btrfs the mountpoint will
			# be empty as the actual subvolumes are getting mounted instead so we'll use
			# '/' just for sorting
			sorted_part_mods = sorted(not_pv_part_mods, key=lambda x: x.mountpoint or Path('/'))

			for part_mod in sorted_part_mods:
				if luks_handler := luks_handlers.get(part_mod):
					self._mount_luks_partition(part_mod, luks_handler)
				else:
					self._mount_partition(part_mod)

	def _mount_lvm_layout(self, luks_handlers: Dict[Any, Luks2] = {}):
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
		partitions: List[disk.PartitionModification]
	) -> Dict[disk.PartitionModification, Luks2]:
		return {
			part_mod: disk.device_handler.unlock_luks2_dev(
				part_mod.dev_path,
				part_mod.mapper_name,
				self._disk_encryption.encryption_password
			)
			for part_mod in partitions
			if part_mod.mapper_name and part_mod.dev_path
		}

	def _import_lvm(self):
		lvm_config = self._disk_config.lvm_config

		if not lvm_config:
			debug('No lvm config defined to be imported')
			return

		for vg in lvm_config.vol_groups:
			disk.device_handler.lvm_import_vg(vg)

			for vol in vg.volumes:
				disk.device_handler.lvm_vol_change(vol, True)

	def _prepare_luks_lvm(
		self,
		lvm_volumes: List[disk.LvmVolume]
	) -> Dict[disk.LvmVolume, Luks2]:
		return {
			vol: disk.device_handler.unlock_luks2_dev(
				vol.dev_path,
				vol.mapper_name,
				self._disk_encryption.encryption_password
			)
			for vol in lvm_volumes
			if vol.mapper_name and vol.dev_path
		}

	def _mount_partition(self, part_mod: disk.PartitionModification):
		# it would be none if it's btrfs as the subvolumes will have the mountpoints defined
		if part_mod.mountpoint and part_mod.dev_path:
			target = self.target / part_mod.relative_mountpoint
			disk.device_handler.mount(part_mod.dev_path, target, options=part_mod.mount_options)

		if part_mod.fs_type == disk.FilesystemType.Btrfs and part_mod.dev_path:
			self._mount_btrfs_subvol(
				part_mod.dev_path,
				part_mod.btrfs_subvols,
				part_mod.mount_options
			)

	def _mount_lvm_vol(self, volume: disk.LvmVolume):
		if volume.fs_type != disk.FilesystemType.Btrfs:
			if volume.mountpoint and volume.dev_path:
				target = self.target / volume.relative_mountpoint
				disk.device_handler.mount(volume.dev_path, target, options=volume.mount_options)

		if volume.fs_type == disk.FilesystemType.Btrfs and volume.dev_path:
			self._mount_btrfs_subvol(volume.dev_path, volume.btrfs_subvols, volume.mount_options)

	def _mount_luks_partition(self, part_mod: disk.PartitionModification, luks_handler: Luks2):
		if part_mod.fs_type != disk.FilesystemType.Btrfs:
			if part_mod.mountpoint and luks_handler.mapper_dev:
				target = self.target / part_mod.relative_mountpoint
				disk.device_handler.mount(luks_handler.mapper_dev, target, options=part_mod.mount_options)

		if part_mod.fs_type == disk.FilesystemType.Btrfs and luks_handler.mapper_dev:
			self._mount_btrfs_subvol(luks_handler.mapper_dev, part_mod.btrfs_subvols, part_mod.mount_options)

	def _mount_luks_volume(self, volume: disk.LvmVolume, luks_handler: Luks2):
		if volume.fs_type != disk.FilesystemType.Btrfs:
			if volume.mountpoint and luks_handler.mapper_dev:
				target = self.target / volume.relative_mountpoint
				disk.device_handler.mount(luks_handler.mapper_dev, target, options=volume.mount_options)

		if volume.fs_type == disk.FilesystemType.Btrfs and luks_handler.mapper_dev:
			self._mount_btrfs_subvol(luks_handler.mapper_dev, volume.btrfs_subvols, volume.mount_options)

	def _mount_btrfs_subvol(
		self,
		dev_path: Path,
		subvolumes: List[disk.SubvolumeModification],
		mount_options: List[str] = []
	):
		for subvol in subvolumes:
			mountpoint = self.target / subvol.relative_mountpoint
			mount_options = mount_options + [f'subvol={subvol.name}']
			disk.device_handler.mount(dev_path, mountpoint, options=mount_options)

	def generate_key_files(self) -> None:
		match self._disk_encryption.encryption_type:
			case disk.EncryptionType.Luks:
				self._generate_key_files_partitions()
			case disk.EncryptionType.LuksOnLvm:
				self._generate_key_file_lvm_volumes()
			case disk.EncryptionType.LvmOnLuks:
				# currently LvmOnLuks only supports a single
				# partitioning layout (boot + partition)
				# so we won't need any keyfile generation atm
				pass

	def _generate_key_files_partitions(self):
		for part_mod in self._disk_encryption.partitions:
			gen_enc_file = self._disk_encryption.should_generate_encryption_file(part_mod)

			luks_handler = Luks2(
				part_mod.safe_dev_path,
				mapper_name=part_mod.mapper_name,
				password=self._disk_encryption.encryption_password
			)

			if gen_enc_file and not part_mod.is_root():
				debug(f'Creating key-file: {part_mod.dev_path}')
				luks_handler.create_keyfile(self.target)

			if part_mod.is_root() and not gen_enc_file:
				if self._disk_encryption.hsm_device:
					disk.Fido2.fido2_enroll(
						self._disk_encryption.hsm_device,
						part_mod.safe_dev_path,
						self._disk_encryption.encryption_password
					)

	def _generate_key_file_lvm_volumes(self):
		for vol in self._disk_encryption.lvm_volumes:
			gen_enc_file = self._disk_encryption.should_generate_encryption_file(vol)

			luks_handler = Luks2(
				vol.safe_dev_path,
				mapper_name=vol.mapper_name,
				password=self._disk_encryption.encryption_password
			)

			if gen_enc_file and not vol.is_root():
				info(f'Creating key-file: {vol.dev_path}')
				luks_handler.create_keyfile(self.target)

			if vol.is_root() and not gen_enc_file:
				if self._disk_encryption.hsm_device:
					disk.Fido2.fido2_enroll(
						self._disk_encryption.hsm_device,
						vol.safe_dev_path,
						self._disk_encryption.encryption_password
					)

	def sync_log_to_install_medium(self) -> bool:
		# Copy over the install log (if there is one) to the install medium if
		# at least the base has been strapped in, otherwise we won't have a filesystem/structure to copy to.
		if self.helper_flags.get('base-strapped', False) is True:
			if filename := storage.get('LOG_FILE', None):
				absolute_logfile = os.path.join(storage.get('LOG_PATH', './'), filename)

				if not os.path.isdir(f"{self.target}/{os.path.dirname(absolute_logfile)}"):
					os.makedirs(f"{self.target}/{os.path.dirname(absolute_logfile)}")

				shutil.copy2(absolute_logfile, f"{self.target}/{absolute_logfile}")

		return True

	def add_swapfile(self, size='4G', enable_resume=True, file='/swapfile'):
		if file[:1] != '/':
			file = f"/{file}"
		if len(file.strip()) <= 0 or file == '/':
			raise ValueError(f"The filename for the swap file has to be a valid path, not: {self.target}{file}")

		SysCommand(f'dd if=/dev/zero of={self.target}{file} bs={size} count=1')
		SysCommand(f'chmod 0600 {self.target}{file}')
		SysCommand(f'mkswap {self.target}{file}')

		self._fstab_entries.append(f'{file} none swap defaults 0 0')

		if enable_resume:
			resume_uuid = SysCommand(f'findmnt -no UUID -T {self.target}{file}').decode()
			resume_offset = SysCommand(
				f'/usr/bin/filefrag -v {self.target}{file}'
			).decode().split('0:', 1)[1].split(":", 1)[1].split("..", 1)[0].strip()

			self._hooks.append('resume')
			self._kernel_params.append(f'resume=UUID={resume_uuid}')
			self._kernel_params.append(f'resume_offset={resume_offset}')

	def post_install_check(self, *args: str, **kwargs: str) -> List[str]:
		return [step for step, flag in self.helper_flags.items() if flag is False]

	def set_mirrors(self, mirror_config: MirrorConfiguration, on_target: bool = False):
		"""
		Set the mirror configuration for the installation.

		:param mirror_config: The mirror configuration to use.
		:type mirror_config: MirrorConfiguration

		:on_target: Whether to set the mirrors on the target system or the live system.
		:param on_target: bool
		"""
		debug('Setting mirrors')

		for plugin in plugins.values():
			if hasattr(plugin, 'on_mirrors'):
				if result := plugin.on_mirrors(mirror_config):
					mirror_config = result

		if on_target:
			local_pacman_conf = Path(f'{self.target}/etc/pacman.conf')
			local_mirrorlist_conf = Path(f'{self.target}/etc/pacman.d/mirrorlist')
		else:
			local_pacman_conf = Path('/etc/pacman.conf')
			local_mirrorlist_conf = Path('/etc/pacman.d/mirrorlist')

		mirrorlist_config = mirror_config.mirrorlist_config()
		pacman_config = mirror_config.pacman_config()

		if pacman_config:
			debug(f'Pacman config: {pacman_config}')

			with local_pacman_conf.open('a') as fp:
				fp.write(pacman_config)

		if mirrorlist_config:
			debug(f'Mirrorlist: {mirrorlist_config}')

			with local_mirrorlist_conf.open('w') as fp:
				fp.write(mirrorlist_config)

	def genfstab(self, flags: str = '-pU'):
		fstab_path = self.target / "etc" / "fstab"
		info(f"Updating {fstab_path}")

		try:
			gen_fstab = SysCommand(f'/usr/bin/genfstab {flags} {self.target}').output()
		except SysCallError as err:
			raise RequirementError(
				f'Could not generate fstab, strapping in packages most likely failed (disk out of space?)\n Error: {err}')

		with open(fstab_path, 'ab') as fp:
			fp.write(gen_fstab)

		if not fstab_path.is_file():
			raise RequirementError(f'Could not create fstab file')

		for plugin in plugins.values():
			if hasattr(plugin, 'on_genfstab'):
				if plugin.on_genfstab(self) is True:
					break

		with open(fstab_path, 'a') as fp:
			for entry in self._fstab_entries:
				fp.write(f'{entry}\n')

	def set_hostname(self, hostname: str):
		with open(f'{self.target}/etc/hostname', 'w') as fh:
			fh.write(hostname + '\n')

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
			modifier = f"@{modifier}"
		# - End patch

		locale_gen = self.target / 'etc/locale.gen'
		locale_gen_lines = locale_gen.read_text().splitlines(True)

		# A locale entry in /etc/locale.gen may or may not contain the encoding
		# in the first column of the entry; check for both cases.
		entry_re = re.compile(rf'#{lang}(\.{encoding})?{modifier} {encoding}')

		for index, line in enumerate(locale_gen_lines):
			if entry_re.match(line):
				uncommented_line = line.removeprefix('#')
				locale_gen_lines[index] = uncommented_line
				locale_gen.write_text(''.join(locale_gen_lines))
				lang_value = uncommented_line.split()[0]
				break
		else:
			error(f"Invalid locale: language '{locale_config.sys_lang}', encoding '{locale_config.sys_enc}'")
			return False

		try:
			SysCommand(f'/usr/bin/arch-chroot {self.target} locale-gen')
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

		if (Path("/usr") / "share" / "zoneinfo" / zone).exists():
			(Path(self.target) / "etc" / "localtime").unlink(missing_ok=True)
			SysCommand(f'/usr/bin/arch-chroot {self.target} ln -s /usr/share/zoneinfo/{zone} /etc/localtime')
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
		info("Enabling periodic TRIM")
		# fstrim is owned by util-linux, a dependency of both base and systemd.
		self.enable_service("fstrim.timer")

	def enable_service(self, services: Union[str, List[str]]) -> None:
		if isinstance(services, str):
			services = [services]

		for service in services:
			info(f'Enabling service {service}')

			try:
				self.arch_chroot(f'systemctl enable {service}')
			except SysCallError as err:
				raise ServiceException(f"Unable to start service {service}: {err}")

			for plugin in plugins.values():
				if hasattr(plugin, 'on_service'):
					plugin.on_service(service)

	def run_command(self, cmd: str, *args: str, **kwargs: str) -> SysCommand:
		return SysCommand(f'/usr/bin/arch-chroot {self.target} {cmd}')

	def arch_chroot(self, cmd: str, run_as: Optional[str] = None) -> SysCommand:
		if run_as:
			cmd = f"su - {run_as} -c {shlex.quote(cmd)}"

		return self.run_command(cmd)

	def drop_to_shell(self) -> None:
		subprocess.check_call(f"/usr/bin/arch-chroot {self.target}", shell=True)

	def configure_nic(self, nic: Nic):
		conf = nic.as_systemd_config()

		for plugin in plugins.values():
			if hasattr(plugin, 'on_configure_nic'):
				conf = plugin.on_configure_nic(
					nic.iface,
					nic.dhcp,
					nic.ip,
					nic.gateway,
					nic.dns
				) or conf

		with open(f"{self.target}/etc/systemd/network/10-{nic.iface}.network", "a") as netconf:
			netconf.write(str(conf))

	def copy_iso_network_config(self, enable_services: bool = False) -> bool:
		# Copy (if any) iwd password and config files
		if os.path.isdir('/var/lib/iwd/'):
			if psk_files := glob.glob('/var/lib/iwd/*.psk'):
				if not os.path.isdir(f"{self.target}/var/lib/iwd"):
					os.makedirs(f"{self.target}/var/lib/iwd")

				if enable_services:
					# If we haven't installed the base yet (function called pre-maturely)
					if self.helper_flags.get('base', False) is False:
						self._base_packages.append('iwd')

						# This function will be called after minimal_installation()
						# as a hook for post-installs. This hook is only needed if
						# base is not installed yet.
						def post_install_enable_iwd_service(*args: str, **kwargs: str):
							self.enable_service('iwd')

						self.post_base_install.append(post_install_enable_iwd_service)
					# Otherwise, we can go ahead and add the required package
					# and enable it's service:
					else:
						self.pacman.strap('iwd')
						self.enable_service('iwd')

				for psk in psk_files:
					shutil.copy2(psk, f"{self.target}/var/lib/iwd/{os.path.basename(psk)}")

		# Copy (if any) systemd-networkd config files
		if netconfigurations := glob.glob('/etc/systemd/network/*'):
			if not os.path.isdir(f"{self.target}/etc/systemd/network/"):
				os.makedirs(f"{self.target}/etc/systemd/network/")

			for netconf_file in netconfigurations:
				shutil.copy2(netconf_file, f"{self.target}/etc/systemd/network/{os.path.basename(netconf_file)}")

			if enable_services:
				# If we haven't installed the base yet (function called pre-maturely)
				if self.helper_flags.get('base', False) is False:

					def post_install_enable_networkd_resolved(*args: str, **kwargs: str):
						self.enable_service(['systemd-networkd', 'systemd-resolved'])

					self.post_base_install.append(post_install_enable_networkd_resolved)
				# Otherwise, we can go ahead and enable the services
				else:
					self.enable_service(['systemd-networkd', 'systemd-resolved'])

		return True

	def mkinitcpio(self, flags: List[str]) -> bool:
		for plugin in plugins.values():
			if hasattr(plugin, 'on_mkinitcpio'):
				# Allow plugins to override the usage of mkinitcpio altogether.
				if plugin.on_mkinitcpio(self):
					return True

		with open(f'{self.target}/etc/mkinitcpio.conf', 'w') as mkinit:
			mkinit.write(f"MODULES=({' '.join(self._modules)})\n")
			mkinit.write(f"BINARIES=({' '.join(self._binaries)})\n")
			mkinit.write(f"FILES=({' '.join(self._files)})\n")

			if not self._disk_encryption.hsm_device:
				# For now, if we don't use HSM we revert to the old
				# way of setting up encryption hooks for mkinitcpio.
				# This is purely for stability reasons, we're going away from this.
				# * systemd -> udev
				# * sd-vconsole -> keymap
				self._hooks = [hook.replace('systemd', 'udev').replace('sd-vconsole', 'keymap consolefont') for hook in self._hooks]

			mkinit.write(f"HOOKS=({' '.join(self._hooks)})\n")

		try:
			SysCommand(f'/usr/bin/arch-chroot {self.target} mkinitcpio {" ".join(flags)}', peek_output=True)
			return True
		except SysCallError as error:
			if error.worker:
				log(error.worker._trace_log.decode())
			return False

	def _get_microcode(self) -> Optional[Path]:
		if not SysInfo.is_vm():
			if vendor := SysInfo.cpu_vendor():
				return vendor.get_ucode()
		return None

	def _handle_partition_installation(self):
		pvs = []
		if self._disk_config.lvm_config:
			pvs = self._disk_config.lvm_config.get_all_pvs()

		for mod in self._disk_config.device_modifications:
			for part in mod.partitions:
				if part in pvs or part.fs_type is None:
					continue

				if (pkg := part.fs_type.installation_pkg) is not None:
					self._base_packages.append(pkg)
				if (module := part.fs_type.installation_module) is not None:
					self._modules.append(module)
				if (binary := part.fs_type.installation_binary) is not None:
					self._binaries.append(binary)

				# https://github.com/archlinux/archinstall/issues/1837
				if part.fs_type.fs_type_mount == 'btrfs':
					self._disable_fstrim = True

				# There is not yet an fsck tool for NTFS. If it's being used for the root filesystem, the hook should be removed.
				if part.fs_type.fs_type_mount == 'ntfs3' and part.mountpoint == self.target:
					if 'fsck' in self._hooks:
						self._hooks.remove('fsck')

				if part in self._disk_encryption.partitions:
					if self._disk_encryption.hsm_device:
						# Required by mkinitcpio to add support for fido2-device options
						self.pacman.strap('libfido2')

						if 'sd-encrypt' not in self._hooks:
							self._hooks.insert(self._hooks.index('filesystems'), 'sd-encrypt')
					else:
						if 'encrypt' not in self._hooks:
							self._hooks.insert(self._hooks.index('filesystems'), 'encrypt')

	def _handle_lvm_installation(self):
		if not self._disk_config.lvm_config:
			return

		self.add_additional_packages('lvm2')
		self._hooks.insert(self._hooks.index('filesystems') - 1, 'lvm2')

		for vg in self._disk_config.lvm_config.vol_groups:
			for vol in vg.volumes:
				if vol.fs_type is not None:
					if (pkg := vol.fs_type.installation_pkg) is not None:
						self._base_packages.append(pkg)
					if (module := vol.fs_type.installation_module) is not None:
						self._modules.append(module)
					if (binary := vol.fs_type.installation_binary) is not None:
						self._binaries.append(binary)

					if vol.fs_type.fs_type_mount == 'btrfs':
						self._disable_fstrim = True

					# There is not yet an fsck tool for NTFS. If it's being used for the root filesystem, the hook should be removed.
					if vol.fs_type.fs_type_mount == 'ntfs3' and vol.mountpoint == self.target:
						if 'fsck' in self._hooks:
							self._hooks.remove('fsck')

		if self._disk_encryption.encryption_type in [disk.EncryptionType.LvmOnLuks, disk.EncryptionType.LuksOnLvm]:
			if self._disk_encryption.hsm_device:
				# Required by mkinitcpio to add support for fido2-device options
				self.pacman.strap('libfido2')

				if 'sd-encrypt' not in self._hooks:
					self._hooks.insert(self._hooks.index('lvm2'), 'sd-encrypt')
			else:
				if 'encrypt' not in self._hooks:
					self._hooks.insert(self._hooks.index('lvm2'), 'encrypt')

	def minimal_installation(
		self,
		testing: bool = False,
		multilib: bool = False,
		mkinitcpio: bool = True,
		hostname: str = 'archinstall',
		locale_config: LocaleConfiguration = LocaleConfiguration.default()
	):
		if self._disk_config.lvm_config:
			self._handle_lvm_installation()
		else:
			self._handle_partition_installation()

		if not SysInfo.has_uefi():
			self._base_packages.append('grub')

		if ucode := self._get_microcode():
			(self.target / 'boot' / ucode).unlink(missing_ok=True)
			self._base_packages.append(ucode.stem)
		else:
			debug('Archinstall will not install any ucode.')

		# Determine whether to enable multilib/testing repositories before running pacstrap if testing flag is set.
		# This action takes place on the host system as pacstrap copies over package repository lists.
		pacman_conf = pacman.Config(self.target)
		if multilib:
			info("The multilib flag is set. This system will be installed with the multilib repository enabled.")
			pacman_conf.enable(pacman.Repo.Multilib)
		else:
			info("The multilib flag is not set. This system will be installed without multilib repositories enabled.")

		if testing:
			info("The testing flag is set. This system will be installed with testing repositories enabled.")
			pacman_conf.enable(pacman.Repo.Testing)
		else:
			info("The testing flag is not set. This system will be installed without testing repositories enabled.")

		pacman_conf.apply()

		self.pacman.strap(self._base_packages)
		self.helper_flags['base-strapped'] = True

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
		# sys_command(f'/usr/bin/arch-chroot {self.target} ln -s /usr/share/zoneinfo/{localtime} /etc/localtime')
		# sys_command('/usr/bin/arch-chroot /mnt hwclock --hctosys --localtime')
		self.set_hostname(hostname)
		self.set_locale(locale_config)
		self.set_keyboard_language(locale_config.kb_layout)

		# TODO: Use python functions for this
		SysCommand(f'/usr/bin/arch-chroot {self.target} chmod 700 /root')

		if mkinitcpio and not self.mkinitcpio(['-P']):
			error('Error generating initramfs (continuing anyway)')

		self.helper_flags['base'] = True

		# Run registered post-install hooks
		for function in self.post_base_install:
			info(f"Running post-installation hook: {function}")
			function(self)

		for plugin in plugins.values():
			if hasattr(plugin, 'on_install'):
				plugin.on_install(self)

	def setup_swap(self, kind: str = 'zram'):
		if kind == 'zram':
			info(f"Setting up swap on zram")
			self.pacman.strap('zram-generator')

			# We could use the default example below, but maybe not the best idea: https://github.com/archlinux/archinstall/pull/678#issuecomment-962124813
			# zram_example_location = '/usr/share/doc/zram-generator/zram-generator.conf.example'
			# shutil.copy2(f"{self.target}{zram_example_location}", f"{self.target}/usr/lib/systemd/zram-generator.conf")
			with open(f"{self.target}/etc/systemd/zram-generator.conf", "w") as zram_conf:
				zram_conf.write("[zram0]\n")

			self.enable_service('systemd-zram-setup@zram0.service')

			self._zram_enabled = True
		else:
			raise ValueError(f"Archinstall currently only supports setting up swap on zram")

	def _get_efi_partition(self) -> Optional[disk.PartitionModification]:
		for layout in self._disk_config.device_modifications:
			if partition := layout.get_efi_partition():
				return partition
		return None

	def _get_boot_partition(self) -> Optional[disk.PartitionModification]:
		for layout in self._disk_config.device_modifications:
			if boot := layout.get_boot_partition():
				return boot
		return None

	def _get_root(self) -> Optional[disk.PartitionModification | disk.LvmVolume]:
		if self._disk_config.lvm_config:
			return self._disk_config.lvm_config.get_root_volume()
		else:
			for mod in self._disk_config.device_modifications:
				if root := mod.get_root_partition():
					return root
		return None

	def _get_luks_uuid_from_mapper_dev(self, mapper_dev_path: Path) -> str:
		lsblk_info = disk.get_lsblk_info(mapper_dev_path, reverse=True, full_dev_path=True)

		if not lsblk_info.children or not lsblk_info.children[0].uuid:
			raise ValueError('Unable to determine UUID of luks superblock')

		return lsblk_info.children[0].uuid

	def _get_kernel_params_partition(
		self,
		root_partition: disk.PartitionModification,
		id_root: bool = True,
		partuuid: bool = True
	) -> List[str]:
		kernel_parameters = []

		if root_partition in self._disk_encryption.partitions:
			# TODO: We need to detect if the encrypted device is a whole disk encryption,
			#       or simply a partition encryption. Right now we assume it's a partition (and we always have)

			if self._disk_encryption and self._disk_encryption.hsm_device:
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
		lvm: disk.LvmVolume
	) -> List[str]:
		kernel_parameters = []

		match self._disk_encryption.encryption_type:
			case disk.EncryptionType.LvmOnLuks:
				if not lvm.vg_name:
					raise ValueError(f'Unable to determine VG name for {lvm.name}')

				pv_seg_info = disk.device_handler.lvm_pvseg_info(lvm.vg_name, lvm.name)

				if not pv_seg_info:
					raise ValueError(f'Unable to determine PV segment info for {lvm.vg_name}/{lvm.name}')

				uuid = self._get_luks_uuid_from_mapper_dev(pv_seg_info.pv_name)

				if self._disk_encryption.hsm_device:
					debug(f'LvmOnLuks, encrypted root partition, HSM, identifying by UUID: {uuid}')
					kernel_parameters.append(f'rd.luks.name={uuid}=cryptlvm root={lvm.safe_dev_path}')
				else:
					debug(f'LvmOnLuks, encrypted root partition, identifying by UUID: {uuid}')
					kernel_parameters.append(f'cryptdevice=UUID={uuid}:cryptlvm root={lvm.safe_dev_path}')
			case disk.EncryptionType.LuksOnLvm:
				uuid = self._get_luks_uuid_from_mapper_dev(lvm.mapper_path)

				if self._disk_encryption.hsm_device:
					debug(f'LuksOnLvm, encrypted root partition, HSM, identifying by UUID: {uuid}')
					kernel_parameters.append(f'rd.luks.name={uuid}=root root=/dev/mapper/root')
				else:
					debug(f'LuksOnLvm, encrypted root partition, identifying by UUID: {uuid}')
					kernel_parameters.append(f'cryptdevice=UUID={uuid}:root root=/dev/mapper/root')
			case disk.EncryptionType.NoEncryption:
				debug(f'Identifying root lvm by mapper device: {lvm.dev_path}')
				kernel_parameters.append(f'root={lvm.safe_dev_path}')

		return kernel_parameters

	def _get_kernel_params(
		self,
		root: disk.PartitionModification | disk.LvmVolume,
		id_root: bool = True,
		partuuid: bool = True
	) -> List[str]:
		kernel_parameters = []

		if isinstance(root, disk.LvmVolume):
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

	def _add_systemd_bootloader(
		self,
		boot_partition: disk.PartitionModification,
		root: disk.PartitionModification | disk.LvmVolume,
		efi_partition: Optional[disk.PartitionModification],
		uki_enabled: bool = False
	):
		debug('Installing systemd bootloader')

		self.pacman.strap('efibootmgr')

		if not SysInfo.has_uefi():
			raise HardwareIncompatibilityError

		# TODO: Ideally we would want to check if another config
		# points towards the same disk and/or partition.
		# And in which case we should do some clean up.
		bootctl_options = []

		if efi_partition and boot_partition != efi_partition:
			bootctl_options.append(f'--esp-path={efi_partition.mountpoint}')
			bootctl_options.append(f'--boot-path={boot_partition.mountpoint}')

		# Install the boot loader
		try:
			SysCommand(f"/usr/bin/arch-chroot {self.target} bootctl {' '.join(bootctl_options)} install")
		except SysCallError:
			# Fallback, try creating the boot loader without touching the EFI variables
			SysCommand(f"/usr/bin/arch-chroot {self.target} bootctl --no-variables {' '.join(bootctl_options)} install")

		# Ensure that the $BOOT/loader/ directory exists before we try to create files in it.
		#
		# As mentioned in https://github.com/archlinux/archinstall/pull/1859 - we store the
		# loader entries in $BOOT/loader/ rather than $ESP/loader/
		# The current reasoning being that $BOOT works in both use cases as well
		# as being tied to the current installation. This may change.
		loader_dir = self.target / 'boot/loader'
		loader_dir.mkdir(parents=True, exist_ok=True)

		default_kernel = self.kernels[0]
		if uki_enabled:
			default_entry = f'arch-{default_kernel}.efi'
		else:
			entry_name = self.init_time + '_{kernel}{variant}.conf'
			default_entry = entry_name.format(kernel=default_kernel, variant='')

		default = f'default {default_entry}'

		# Modify or create a loader.conf
		loader_conf = loader_dir / 'loader.conf'

		try:
			loader_data = loader_conf.read_text().splitlines()
		except FileNotFoundError:
			loader_data = [
				default,
				'timeout 15'
			]
		else:
			for index, line in enumerate(loader_data):
				if line.startswith('default'):
					loader_data[index] = default
				elif line.startswith('#timeout'):
					# We add in the default timeout to support dual-boot
					loader_data[index] = line.removeprefix('#')

		loader_conf.write_text('\n'.join(loader_data) + '\n')

		if uki_enabled:
			return

		# Ensure that the $BOOT/loader/entries/ directory exists before we try to create files in it
		entries_dir = loader_dir / 'entries'
		entries_dir.mkdir(parents=True, exist_ok=True)

		comments = (
			'# Created by: archinstall',
			f'# Created on: {self.init_time}'
		)

		options = 'options ' + ' '.join(self._get_kernel_params(root))

		for kernel in self.kernels:
			for variant in ("", "-fallback"):
				# Setup the loader entry
				entry = [
					*comments,
					f'title   Arch Linux ({kernel}{variant})',
					f'linux   /vmlinuz-{kernel}',
					f'initrd  /initramfs-{kernel}{variant}.img',
					options,
				]

				name = entry_name.format(kernel=kernel, variant=variant)
				entry_conf = entries_dir / name
				entry_conf.write_text('\n'.join(entry) + '\n')

		self.helper_flags['bootloader'] = 'systemd'

	def _add_grub_bootloader(
		self,
		boot_partition: disk.PartitionModification,
		root: disk.PartitionModification | disk.LvmVolume,
		efi_partition: Optional[disk.PartitionModification]
	):
		debug('Installing grub bootloader')

		self.pacman.strap('grub')  # no need?

		grub_default = self.target / 'etc/default/grub'
		config = grub_default.read_text()

		kernel_parameters = ' '.join(self._get_kernel_params(root, False, False))
		config = re.sub(r'(GRUB_CMDLINE_LINUX=")("\n)', rf'\1{kernel_parameters}\2', config, 1)

		grub_default.write_text(config)

		info(f"GRUB boot partition: {boot_partition.dev_path}")

		boot_dir = Path('/boot')

		command = [
			'/usr/bin/arch-chroot',
			str(self.target),
			'grub-install',
			'--debug'
		]

		if SysInfo.has_uefi():
			if not efi_partition:
				raise ValueError('Could not detect efi partition')

			info(f"GRUB EFI partition: {efi_partition.dev_path}")

			self.pacman.strap('efibootmgr')  # TODO: Do we need? Yes, but remove from minimal_installation() instead?

			boot_dir_arg = []
			if boot_partition.mountpoint and boot_partition.mountpoint != boot_dir:
				boot_dir_arg.append(f'--boot-directory={boot_partition.mountpoint}')
				boot_dir = boot_partition.mountpoint

			add_options = [
				'--target=x86_64-efi',
				f'--efi-directory={efi_partition.mountpoint}',
				*boot_dir_arg,
				'--bootloader-id=GRUB',
				'--removable'
			]

			command.extend(add_options)

			try:
				SysCommand(command, peek_output=True)
			except SysCallError:
				try:
					SysCommand(command, peek_output=True)
				except SysCallError as err:
					raise DiskError(f"Could not install GRUB to {self.target}{efi_partition.mountpoint}: {err}")
		else:
			info(f"GRUB boot partition: {boot_partition.dev_path}")

			parent_dev_path = disk.device_handler.get_parent_device_path(boot_partition.safe_dev_path)

			add_options = [
				'--target=i386-pc',
				'--recheck',
				str(parent_dev_path)
			]

			try:
				SysCommand(command + add_options, peek_output=True)
			except SysCallError as err:
				raise DiskError(f"Failed to install GRUB boot on {boot_partition.dev_path}: {err}")

		try:
			SysCommand(
				f'/usr/bin/arch-chroot {self.target} '
				f'grub-mkconfig -o {boot_dir}/grub/grub.cfg'
			)
		except SysCallError as err:
			raise DiskError(f"Could not configure GRUB: {err}")

		self.helper_flags['bootloader'] = "grub"

	def _add_limine_bootloader(
		self,
		boot_partition: disk.PartitionModification,
		efi_partition: Optional[disk.PartitionModification],
		root: disk.PartitionModification | disk.LvmVolume
	):
		debug('Installing limine bootloader')

		self.pacman.strap('limine')

		info(f"Limine boot partition: {boot_partition.dev_path}")

		limine_path = self.target / 'usr' / 'share' / 'limine'
		hook_command = None

		if SysInfo.has_uefi():
			if not efi_partition:
				raise ValueError('Could not detect efi partition')
			elif not efi_partition.mountpoint:
				raise ValueError('EFI partition is not mounted')

			info(f"Limine EFI partition: {efi_partition.dev_path}")

			try:
				efi_dir_path = self.target / efi_partition.mountpoint.relative_to('/') / 'EFI' / 'BOOT'
				efi_dir_path.mkdir(parents=True, exist_ok=True)

				for file in ('BOOTIA32.EFI', 'BOOTX64.EFI'):
					shutil.copy(limine_path / file, efi_dir_path)
			except Exception as err:
				raise DiskError(f'Failed to install Limine in {self.target}{efi_partition.mountpoint}: {err}')

			hook_command = f'/usr/bin/cp /usr/share/limine/BOOTIA32.EFI {efi_partition.mountpoint}/EFI/BOOT/' \
				f' && /usr/bin/cp /usr/share/limine/BOOTX64.EFI {efi_partition.mountpoint}/EFI/BOOT/'
		else:
			parent_dev_path = disk.device_handler.get_parent_device_path(boot_partition.safe_dev_path)

			if unique_path := disk.device_handler.get_unique_path_for_device(parent_dev_path):
				parent_dev_path = unique_path

			try:
				# The `limine-bios.sys` file contains stage 3 code.
				shutil.copy(limine_path / 'limine-bios.sys', self.target / 'boot')

				# `limine bios-install` deploys the stage 1 and 2 to the disk.
				SysCommand(f'/usr/bin/arch-chroot {self.target} limine bios-install {parent_dev_path}', peek_output=True)
			except Exception as err:
				raise DiskError(f'Failed to install Limine on {parent_dev_path}: {err}')

			hook_command = f'/usr/bin/limine bios-install {parent_dev_path}' \
				f' && /usr/bin/cp /usr/share/limine/limine-bios.sys /boot/'

		hook_contents = f'''[Trigger]
Operation = Install
Operation = Upgrade
Type = Package
Target = limine

[Action]
Description = Deploying Limine after upgrade...
When = PostTransaction
Exec = /bin/sh -c "{hook_command}"
'''

		hooks_dir = self.target / 'etc' / 'pacman.d' / 'hooks'
		hooks_dir.mkdir(parents=True, exist_ok=True)

		hook_path = hooks_dir / '99-limine.hook'
		hook_path.write_text(hook_contents)

		kernel_params = ' '.join(self._get_kernel_params(root))
		config_contents = 'timeout: 5\n'

		for kernel in self.kernels:
			for variant in ('', '-fallback'):
				entry = [
					f'protocol: linux',
					f'kernel_path: boot():/vmlinuz-{kernel}',
					f'kernel_cmdline: {kernel_params}',
					f'module_path: boot():/initramfs-{kernel}{variant}.img',
				]

				config_contents += f'\n/Arch Linux ({kernel}{variant})\n'
				config_contents += '\n'.join([f'    {it}' for it in entry]) + '\n'

		config_path = self.target / 'boot' / 'limine.conf'
		config_path.write_text(config_contents)

		self.helper_flags['bootloader'] = "limine"

	def _add_efistub_bootloader(
		self,
		boot_partition: disk.PartitionModification,
		root: disk.PartitionModification | disk.LvmVolume,
		uki_enabled: bool = False
	):
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
				*self._get_kernel_params(root)
			)

			cmdline = [' '.join(entries)]
		else:
			loader = '/EFI/Linux/arch-{kernel}.efi'
			cmdline = []

		parent_dev_path = disk.device_handler.get_parent_device_path(boot_partition.safe_dev_path)

		cmd_template = (
			'efibootmgr',
			'--create',
			'--disk', str(parent_dev_path),
			'--part', str(boot_partition.partn),
			'--label', 'Arch Linux ({kernel})',
			'--loader', loader,
			'--unicode', *cmdline,
			'--verbose'
		)

		for kernel in self.kernels:
			# Setup the firmware entry
			cmd = [arg.format(kernel=kernel) for arg in cmd_template]
			SysCommand(cmd)

		self.helper_flags['bootloader'] = "efistub"

	def _config_uki(
		self,
		root: disk.PartitionModification | disk.LvmVolume,
		efi_partition: Optional[disk.PartitionModification]
	):
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

	def add_bootloader(self, bootloader: Bootloader, uki_enabled: bool = False):
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
					return True

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
				self._add_limine_bootloader(boot_partition, efi_partition, root)

	def add_additional_packages(self, packages: Union[str, List[str]]) -> bool:
		return self.pacman.strap(packages)

	def enable_sudo(self, entity: str, group: bool = False):
		info(f'Enabling sudo permissions for {entity}')

		sudoers_dir = f"{self.target}/etc/sudoers.d"

		# Creates directory if not exists
		if not (sudoers_path := Path(sudoers_dir)).exists():
			sudoers_path.mkdir(parents=True)
			# Guarantees sudoer confs directory recommended perms
			os.chmod(sudoers_dir, 0o440)
			# Appends a reference to the sudoers file, because if we are here sudoers.d did not exist yet
			with open(f'{self.target}/etc/sudoers', 'a') as sudoers:
				sudoers.write('@includedir /etc/sudoers.d\n')

		# We count how many files are there already so we know which number to prefix the file with
		num_of_rules_already = len(os.listdir(sudoers_dir))
		file_num_str = "{:02d}".format(num_of_rules_already)  # We want 00_user1, 01_user2, etc

		# Guarantees that entity str does not contain invalid characters for a linux file name:
		# \ / : * ? " < > |
		safe_entity_file_name = re.sub(r'(\\|\/|:|\*|\?|"|<|>|\|)', '', entity)

		rule_file_name = f"{sudoers_dir}/{file_num_str}_{safe_entity_file_name}"

		with open(rule_file_name, 'a') as sudoers:
			sudoers.write(f'{"%" if group else ""}{entity} ALL=(ALL) ALL\n')

		# Guarantees sudoer conf file recommended perms
		os.chmod(Path(rule_file_name), 0o440)

	def create_users(self, users: Union[User, List[User]]):
		if not isinstance(users, list):
			users = [users]

		for user in users:
			self.user_create(user.username, user.password, user.groups, user.sudo)

	def user_create(self, user: str, password: Optional[str] = None, groups: Optional[List[str]] = None,
					sudo: bool = False) -> None:
		if groups is None:
			groups = []

		# This plugin hook allows for the plugin to handle the creation of the user.
		# Password and Group management is still handled by user_create()
		handled_by_plugin = False
		for plugin in plugins.values():
			if hasattr(plugin, 'on_user_create'):
				if result := plugin.on_user_create(self, user):
					handled_by_plugin = result

		if not handled_by_plugin:
			info(f'Creating user {user}')
			try:
				SysCommand(f'/usr/bin/arch-chroot {self.target} useradd -m -G wheel {user}')
			except SysCallError as err:
				raise SystemError(f"Could not create user inside installation: {err}")

		for plugin in plugins.values():
			if hasattr(plugin, 'on_user_created'):
				if result := plugin.on_user_created(self, user):
					handled_by_plugin = result

		if password:
			self.user_set_pw(user, password)

		if groups:
			for group in groups:
				SysCommand(f'/usr/bin/arch-chroot {self.target} gpasswd -a {user} {group}')

		if sudo and self.enable_sudo(user):
			self.helper_flags['user'] = True

	def user_set_pw(self, user: str, password: str) -> bool:
		info(f'Setting password for {user}')

		if user == 'root':
			# This means the root account isn't locked/disabled with * in /etc/passwd
			self.helper_flags['user'] = True

		combo = f'{user}:{password}'
		echo = shlex.join(['echo', combo])
		sh = shlex.join(['sh', '-c', echo])

		try:
			SysCommand(f"/usr/bin/arch-chroot {self.target} " + sh[:-1] + " | chpasswd'")
			return True
		except SysCallError:
			return False

	def user_set_shell(self, user: str, shell: str) -> bool:
		info(f'Setting shell for {user} to {shell}')

		try:
			SysCommand(f"/usr/bin/arch-chroot {self.target} sh -c \"chsh -s {shell} {user}\"")
			return True
		except SysCallError:
			return False

	def chown(self, owner: str, path: str, options: List[str] = []) -> bool:
		cleaned_path = path.replace('\'', '\\\'')
		try:
			SysCommand(f"/usr/bin/arch-chroot {self.target} sh -c 'chown {' '.join(options)} {owner} {cleaned_path}'")
			return True
		except SysCallError:
			return False

	def set_keyboard_language(self, language: str) -> bool:
		info(f"Setting keyboard language to {language}")

		if len(language.strip()):
			if not verify_keyboard_layout(language):
				error(f"Invalid keyboard language specified: {language}")
				return False

			# In accordance with https://github.com/archlinux/archinstall/issues/107#issuecomment-841701968
			# Setting an empty keymap first, allows the subsequent call to set layout for both console and x11.
			from .boot import Boot
			with Boot(self) as session:
				os.system('/usr/bin/systemd-run --machine=archinstall --pty localectl set-keymap ""')

				try:
					session.SysCommand(["localectl", "set-keymap", language])
				except SysCallError as err:
					raise ServiceException(f"Unable to set locale '{language}' for console: {err}")

				info(f"Keyboard language for this installation is now set to: {language}")
		else:
			info('Keyboard language was not changed from default (no language specified)')

		return True

	def set_x11_keyboard_language(self, language: str) -> bool:
		"""
		A fallback function to set x11 layout specifically and separately from console layout.
		This isn't strictly necessary since .set_keyboard_language() does this as well.
		"""
		info(f"Setting x11 keyboard language to {language}")

		if len(language.strip()):
			if not verify_x11_keyboard_layout(language):
				error(f"Invalid x11-keyboard language specified: {language}")
				return False

			from .boot import Boot
			with Boot(self) as session:
				session.SysCommand(["localectl", "set-x11-keymap", '""'])

				try:
					session.SysCommand(["localectl", "set-x11-keymap", language])
				except SysCallError as err:
					raise ServiceException(f"Unable to set locale '{language}' for X11: {err}")
		else:
			info(f'X11-Keyboard language was not changed from default (no language specified)')

		return True

	def _service_started(self, service_name: str) -> Optional[str]:
		if os.path.splitext(service_name)[1] not in ('.service', '.target', '.timer'):
			service_name += '.service'  # Just to be safe

		last_execution_time = SysCommand(
			f"systemctl show --property=ActiveEnterTimestamp --no-pager {service_name}",
			environment_vars={'SYSTEMD_COLORS': '0'}
		).decode().lstrip('ActiveEnterTimestamp=')

		if not last_execution_time:
			return None

		return last_execution_time

	def _service_state(self, service_name: str) -> str:
		if os.path.splitext(service_name)[1] not in ('.service', '.target', '.timer'):
			service_name += '.service'  # Just to be safe

		return SysCommand(
			f'systemctl show --no-pager -p SubState --value {service_name}',
			environment_vars={'SYSTEMD_COLORS': '0'}
		).decode()
