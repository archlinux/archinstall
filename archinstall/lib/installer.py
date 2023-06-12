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
from .mirrors import use_mirrors, MirrorConfiguration, add_custom_mirrors
from .models.bootloader import Bootloader
from .models.network_configuration import NetworkConfiguration
from .models.users import User
from .output import log, error, info, warn, debug
from .pacman import run_pacman
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
		if not base_packages:
			base_packages = __packages__[:3]

		if kernels is None:
			self.kernels = ['linux']
		else:
			self.kernels = kernels

		self._disk_config = disk_config

		if disk_encryption is None:
			self._disk_encryption = disk.DiskEncryption(disk.EncryptionType.NoEncryption)
		else:
			self._disk_encryption = disk_encryption

		self.target: Path = target

		self.init_time = time.strftime('%Y-%m-%d_%H-%M-%S')
		self.milliseconds = int(str(time.time()).split('.')[1])
		self.helper_flags: Dict[str, Any] = {'base': False, 'bootloader': None}
		self.base_packages = base_packages

		for kernel in self.kernels:
			self.base_packages.append(kernel)

		# If using accessibility tools in the live environment, append those to the packages list
		if accessibility_tools_in_use():
			self.base_packages.extend(__accessibility_packages__)

		self.post_base_install: List[Callable] = []

		# TODO: Figure out which one of these two we'll use.. But currently we're mixing them..
		storage['session'] = self
		storage['installation_session'] = self

		self.modules: List[str] = []
		self._binaries: List[str] = []
		self._files: List[str] = []

		# systemd, sd-vconsole and sd-encrypt will be replaced by udev, keymap and encrypt
		# if HSM is not used to encrypt the root volume. Check mkinitcpio() function for that override.
		self._hooks: List[str] = [
			"base", "systemd", "autodetect", "keyboard",
			"sd-vconsole", "modconf", "block", "filesystems", "fsck"
		]
		self._kernel_params: List[str] = []
		self._fstab_entries: List[str] = []

		self._zram_enabled = False

	def __enter__(self) -> 'Installer':
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		if exc_type is not None:
			error(exc_val)

			self.sync_log_to_install_medium()

			# We avoid printing /mnt/<log path> because that might confuse people if they note it down
			# and then reboot, and a identical log file will be found in the ISO medium anyway.
			print(_("[!] A log file has been created here: {}").format(os.path.join(storage['LOG_PATH'], storage['LOG_FILE'])))
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

	def _verify_service_stop(self):
		"""
		Certain services might be running that affects the system during installation.
		One such service is "reflector.service" which updates /etc/pacman.d/mirrorlist
		We need to wait for it before we continue since we opted in to use a custom mirror/region.
		"""
		info('Waiting for time sync (systemd-timesyncd.service) to complete.')
		while SysCommand('timedatectl show --property=NTPSynchronized --value').decode().rstrip() != 'yes':
			time.sleep(1)

		info('Waiting for automatic mirror selection (reflector) to complete.')
		while self._service_state('reflector') not in ('dead', 'failed', 'exited'):
			time.sleep(1)

		# info('Waiting for pacman-init.service to complete.')
		# while self._service_state('pacman-init') not in ('dead', 'failed', 'exited'):
		# 	time.sleep(1)

		info('Waiting for Arch Linux keyring sync (archlinux-keyring-wkd-sync) to complete.')
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
			if lsblk_info[0].size < disk.Size(200, disk.Unit.MiB):
				raise DiskError(
					f'The boot partition mounted at {boot_mount} is not large enough to install a boot loader. '
					f'Please resize it to at least 200MiB and re-run the installation.'
				)

	def sanity_check(self):
		self._verify_boot_part()
		self._verify_service_stop()

	def mount_ordered_layout(self):
		info('Mounting partitions in order')

		for mod in self._disk_config.device_modifications:
			# partitions have to mounted in the right order on btrfs the mountpoint will
			# be empty as the actual subvolumes are getting mounted instead so we'll use
			# '/' just for sorting
			sorted_part_mods = sorted(mod.partitions, key=lambda x: x.mountpoint if x.mountpoint else Path('/'))

			if self._disk_encryption.encryption_type is not disk.EncryptionType.NoEncryption:
				enc_partitions = list(filter(lambda x: x in self._disk_encryption.partitions, sorted_part_mods))
			else:
				enc_partitions = []

			# attempt to decrypt all luks partitions
			luks_handlers = self._prepare_luks_partitions(enc_partitions)

			for part_mod in sorted_part_mods:
				if part_mod not in luks_handlers:  # partition is not encrypted
					self._mount_partition(part_mod)
				else:  # mount encrypted partition
					self._mount_luks_partiton(part_mod, luks_handlers[part_mod])

	def _prepare_luks_partitions(self, partitions: List[disk.PartitionModification]) -> Dict[disk.PartitionModification, Luks2]:
		luks_handlers = {}

		for part_mod in partitions:
			if part_mod.mapper_name and part_mod.dev_path:
				luks_handler = disk.device_handler.unlock_luks2_dev(
					part_mod.dev_path,
					part_mod.mapper_name,
					self._disk_encryption.encryption_password
				)
				luks_handlers[part_mod] = luks_handler

		return luks_handlers

	def _mount_partition(self, part_mod: disk.PartitionModification):
		# it would be none if it's btrfs as the subvolumes will have the mountpoints defined
		if part_mod.mountpoint and part_mod.dev_path:
			target = self.target / part_mod.relative_mountpoint
			disk.device_handler.mount(part_mod.dev_path, target, options=part_mod.mount_options)

		if part_mod.fs_type == disk.FilesystemType.Btrfs and part_mod.dev_path:
			self._mount_btrfs_subvol(part_mod.dev_path, part_mod.btrfs_subvols)

	def _mount_luks_partiton(self, part_mod: disk.PartitionModification, luks_handler: Luks2):
		# it would be none if it's btrfs as the subvolumes will have the mountpoints defined
		if part_mod.mountpoint and luks_handler.mapper_dev:
			target = self.target / part_mod.relative_mountpoint
			disk.device_handler.mount(luks_handler.mapper_dev, target, options=part_mod.mount_options)

		if part_mod.fs_type == disk.FilesystemType.Btrfs and luks_handler.mapper_dev:
			self._mount_btrfs_subvol(luks_handler.mapper_dev, part_mod.btrfs_subvols)

	def _mount_btrfs_subvol(self, dev_path: Path, subvolumes: List[disk.SubvolumeModification]):
		for subvol in subvolumes:
			mountpoint = self.target / subvol.relative_mountpoint
			mount_options = subvol.mount_options + [f'subvol={subvol.name}']
			disk.device_handler.mount(dev_path, mountpoint, options=mount_options)

	def generate_key_files(self):
		for part_mod in self._disk_encryption.partitions:
			gen_enc_file = self._disk_encryption.should_generate_encryption_file(part_mod)

			luks_handler = Luks2(
				part_mod.dev_path,
				mapper_name=part_mod.mapper_name,
				password=self._disk_encryption.encryption_password
			)

			if gen_enc_file and not part_mod.is_root():
				info(f'Creating key-file: {part_mod.dev_path}')
				luks_handler.create_keyfile(self.target)

			if part_mod.is_root() and not gen_enc_file:
				if self._disk_encryption.hsm_device:
					disk.Fido2.fido2_enroll(
						self._disk_encryption.hsm_device,
						part_mod,
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
			resume_uuid = SysCommand(f'findmnt -no UUID -T {self.target}{file}').decode('UTF-8').strip()
			resume_offset = SysCommand(f'/usr/bin/filefrag -v {self.target}{file}').decode('UTF-8').split('0:', 1)[1].split(":", 1)[1].split("..", 1)[0].strip()

			self._hooks.append('resume')
			self._kernel_params.append(f'resume=UUID={resume_uuid}')
			self._kernel_params.append(f'resume_offset={resume_offset}')

	def post_install_check(self, *args :str, **kwargs :str) -> List[str]:
		return [step for step, flag in self.helper_flags.items() if flag is False]

	def enable_multilib_repository(self):
		# Set up a regular expression pattern of a commented line containing 'multilib' within []
		pattern = re.compile(r"^#\s*\[multilib\]$")

		# This is used to track if the previous line is a match, so we end up uncommenting the line after the block.
		matched = False

		# Read in the lines from the original file
		with open("/etc/pacman.conf", "r") as pacman_conf:
			lines = pacman_conf.readlines()

		# Open the file again in write mode, to replace the contents
		with open("/etc/pacman.conf", "w") as pacman_conf:
			for line in lines:
				if pattern.match(line):
					# If this is the [] block containing 'multilib', uncomment it and set the matched tracking boolean.
					pacman_conf.write(line.lstrip('#'))
					matched = True
				elif matched:
					# The previous line was a match for [.*multilib.*].
					# This means we're on a line that looks like '#Include = /etc/pacman.d/mirrorlist'
					pacman_conf.write(line.lstrip('#'))
					matched = False # Reset the state of matched to False.
				else:
					pacman_conf.write(line)

	def enable_testing_repositories(self, enable_multilib_testing=False):
		# Set up a regular expression pattern of a commented line containing 'testing' within []
		pattern = re.compile("^#\\[.*testing.*\\]$")

		# This is used to track if the previous line is a match, so we end up uncommenting the line after the block.
		matched = False

		# Read in the lines from the original file
		with open("/etc/pacman.conf", "r") as pacman_conf:
			lines = pacman_conf.readlines()

		# Open the file again in write mode, to replace the contents
		with open("/etc/pacman.conf", "w") as pacman_conf:
			for line in lines:
				if pattern.match(line) and (enable_multilib_testing or 'multilib' not in line):
					# If this is the [] block containing 'testing', uncomment it and set the matched tracking boolean.
					pacman_conf.write(line.lstrip('#'))
					matched = True
				elif matched:
					# The previous line was a match for [.*testing.*].
					# This means we're on a line that looks like '#Include = /etc/pacman.d/mirrorlist'
					pacman_conf.write(line.lstrip('#'))
					matched = False # Reset the state of matched to False.
				else:
					pacman_conf.write(line)

	def _pacstrap(self, packages: Union[str, List[str]]) -> bool:
		if isinstance(packages, str):
			packages = [packages]

		for plugin in plugins.values():
			if hasattr(plugin, 'on_pacstrap'):
				if (result := plugin.on_pacstrap(packages)):
					packages = result

		info(f'Installing packages: {packages}')

		# TODO: We technically only need to run the -Syy once.
		try:
			run_pacman('-Syy', default_cmd='/usr/bin/pacman')
		except SysCallError as err:
			error(f'Could not sync a new package database: {err}')

			if storage['arguments'].get('silent', False) is False:
				if input('Would you like to re-try this download? (Y/n): ').lower().strip() in ('', 'y'):
					return self._pacstrap(packages)

			raise RequirementError(f'Could not sync mirrors: {err}')

		try:
			SysCommand(f'/usr/bin/pacstrap -C /etc/pacman.conf -K {self.target} {" ".join(packages)} --noconfirm', peek_output=True)
			return True
		except SysCallError as err:
			error(f'Could not strap in packages: {err}')

			if storage['arguments'].get('silent', False) is False:
				if input('Would you like to re-try this download? (Y/n): ').lower().strip() in ('', 'y'):
					return self._pacstrap(packages)

			raise RequirementError("Pacstrap failed. See /var/log/archinstall/install.log or above message for error details.")

	def set_mirrors(self, mirror_config: MirrorConfiguration):
		for plugin in plugins.values():
			if hasattr(plugin, 'on_mirrors'):
				if result := plugin.on_mirrors(mirror_config):
					mirror_config = result

		destination = f'{self.target}/etc/pacman.d/mirrorlist'
		if mirror_config.mirror_regions:
			use_mirrors(mirror_config.mirror_regions, destination)
		if mirror_config.custom_mirrors:
			add_custom_mirrors(mirror_config.custom_mirrors)

	def genfstab(self, flags :str = '-pU'):
		info(f"Updating {self.target}/etc/fstab")

		try:
			gen_fstab = SysCommand(f'/usr/bin/genfstab {flags} {self.target}').decode()
		except SysCallError as err:
			raise RequirementError(f'Could not generate fstab, strapping in packages most likely failed (disk out of space?)\n Error: {err}')

		if not gen_fstab:
			raise RequirementError(f'Genrating fstab returned empty value')

		with open(f"{self.target}/etc/fstab", 'a') as fp:
			fp.write(gen_fstab)

		if not os.path.isfile(f'{self.target}/etc/fstab'):
			raise RequirementError(f'Could not create fstab file')

		for plugin in plugins.values():
			if hasattr(plugin, 'on_genfstab'):
				if plugin.on_genfstab(self) is True:
					break

		with open(f"{self.target}/etc/fstab", 'a') as fp:
			for entry in self._fstab_entries:
				fp.write(f'{entry}\n')

		for mod in self._disk_config.device_modifications:
			for part_mod in mod.partitions:
				if part_mod.fs_type != disk.FilesystemType.Btrfs:
					continue

				fstab_file = Path(f'{self.target}/etc/fstab')

				with fstab_file.open('r') as fp:
					fstab = fp.readlines()

				# Replace the {installation}/etc/fstab with entries
				# using the compress=zstd where the mountpoint has compression set.
				for index, line in enumerate(fstab):
					# So first we grab the mount options by using subvol=.*? as a locator.
					# And we also grab the mountpoint for the entry, for instance /var/log
					subvoldef = re.findall(',.*?subvol=.*?[\t ]', line)
					mountpoint = re.findall('[\t ]/.*?[\t ]', line)

					if not subvoldef or not mountpoint:
						continue

					for sub_vol in part_mod.btrfs_subvols:
						# We then locate the correct subvolume and check if it's compressed,
						# and skip entries where compression is already defined
						# We then sneak in the compress=zstd option if it doesn't already exist:
						if sub_vol.compress and str(sub_vol.mountpoint) == Path(mountpoint[0].strip()) and ',compress=zstd,' not in line:
							fstab[index] = line.replace(subvoldef[0], f',compress=zstd{subvoldef[0]}')
							break

				with fstab_file.open('w') as fp:
					fp.writelines(fstab)

	def set_hostname(self, hostname: str, *args :str, **kwargs :str) -> None:
		with open(f'{self.target}/etc/hostname', 'w') as fh:
			fh.write(hostname + '\n')

	def set_locale(self, locale_config: LocaleConfiguration):
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

		with open(f'{self.target}/etc/locale.gen', 'a') as fh:
			fh.write(f'{lang}.{encoding}{modifier} {encoding}\n')

		with open(f'{self.target}/etc/locale.conf', 'w') as fh:
			fh.write(f'LANG={lang}.{encoding}{modifier}\n')

		try:
			SysCommand(f'/usr/bin/arch-chroot {self.target} locale-gen')
		except SysCallError as e:
			error(f'Failed to run locale-gen on target: {e}')

	def set_timezone(self, zone :str, *args :str, **kwargs :str) -> bool:
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

	def activate_time_syncronization(self) -> None:
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

	def run_command(self, cmd :str, *args :str, **kwargs :str) -> SysCommand:
		return SysCommand(f'/usr/bin/arch-chroot {self.target} {cmd}')

	def arch_chroot(self, cmd :str, run_as :Optional[str] = None) -> SysCommand:
		if run_as:
			cmd = f"su - {run_as} -c {shlex.quote(cmd)}"

		return self.run_command(cmd)

	def drop_to_shell(self) -> None:
		subprocess.check_call(f"/usr/bin/arch-chroot {self.target}", shell=True)

	def configure_nic(self, network_config: NetworkConfiguration) -> None:
		conf = network_config.as_systemd_config()

		for plugin in plugins.values():
			if hasattr(plugin, 'on_configure_nic'):
				new_conf = plugin.on_configure_nic(
					network_config.iface,
					network_config.dhcp,
					network_config.ip,
					network_config.gateway,
					network_config.dns
				)

				if new_conf:
					conf = new_conf

		with open(f"{self.target}/etc/systemd/network/10-{network_config.iface}.network", "a") as netconf:
			netconf.write(str(conf))

	def copy_iso_network_config(self, enable_services :bool = False) -> bool:
		# Copy (if any) iwd password and config files
		if os.path.isdir('/var/lib/iwd/'):
			if psk_files := glob.glob('/var/lib/iwd/*.psk'):
				if not os.path.isdir(f"{self.target}/var/lib/iwd"):
					os.makedirs(f"{self.target}/var/lib/iwd")

				if enable_services:
					# If we haven't installed the base yet (function called pre-maturely)
					if self.helper_flags.get('base', False) is False:
						self.base_packages.append('iwd')

						# This function will be called after minimal_installation()
						# as a hook for post-installs. This hook is only needed if
						# base is not installed yet.
						def post_install_enable_iwd_service(*args :str, **kwargs :str):
							self.enable_service('iwd')

						self.post_base_install.append(post_install_enable_iwd_service)
					# Otherwise, we can go ahead and add the required package
					# and enable it's service:
					else:
						self._pacstrap('iwd')
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

					def post_install_enable_networkd_resolved(*args :str, **kwargs :str):
						self.enable_service(['systemd-networkd', 'systemd-resolved'])

					self.post_base_install.append(post_install_enable_networkd_resolved)
				# Otherwise, we can go ahead and enable the services
				else:
					self.enable_service(['systemd-networkd', 'systemd-resolved'])

		return True

	def mkinitcpio(self, flags: List[str], locale_config: LocaleConfiguration) -> bool:
		for plugin in plugins.values():
			if hasattr(plugin, 'on_mkinitcpio'):
				# Allow plugins to override the usage of mkinitcpio altogether.
				if plugin.on_mkinitcpio(self):
					return True

		# mkinitcpio will error out if there's no vconsole.
		if (vconsole := Path(f"{self.target}/etc/vconsole.conf")).exists() is False:
			with vconsole.open('w') as fh:
				fh.write(f"KEYMAP={locale_config.kb_layout}\n")

		with open(f'{self.target}/etc/mkinitcpio.conf', 'w') as mkinit:
			mkinit.write(f"MODULES=({' '.join(self.modules)})\n")
			mkinit.write(f"BINARIES=({' '.join(self._binaries)})\n")
			mkinit.write(f"FILES=({' '.join(self._files)})\n")

			if not self._disk_encryption.hsm_device:
				# For now, if we don't use HSM we revert to the old
				# way of setting up encryption hooks for mkinitcpio.
				# This is purely for stability reasons, we're going away from this.
				# * systemd -> udev
				# * sd-vconsole -> keymap
				self._hooks = [hook.replace('systemd', 'udev').replace('sd-vconsole', 'keymap') for hook in self._hooks]

			mkinit.write(f"HOOKS=({' '.join(self._hooks)})\n")

		try:
			SysCommand(f'/usr/bin/arch-chroot {self.target} mkinitcpio {" ".join(flags)}')
			return True
		except SysCallError:
			return False

	def minimal_installation(
		self,
		testing: bool = False,
		multilib: bool = False,
		hostname: str = 'archinstall',
		locale_config: LocaleConfiguration = LocaleConfiguration.default()
	):
		for mod in self._disk_config.device_modifications:
			for part in mod.partitions:
				if (pkg := part.fs_type.installation_pkg) is not None:
					self.base_packages.append(pkg)
				if (module := part.fs_type.installation_module) is not None:
					self.modules.append(module)
				if (binary := part.fs_type.installation_binary) is not None:
					self._binaries.append(binary)

				# There is not yet an fsck tool for NTFS. If it's being used for the root filesystem, the hook should be removed.
				if part.fs_type.fs_type_mount == 'ntfs3' and part.mountpoint == self.target:
					if 'fsck' in self._hooks:
						self._hooks.remove('fsck')

				if part in self._disk_encryption.partitions:
					if self._disk_encryption.hsm_device:
						# Required bby mkinitcpio to add support for fido2-device options
						self._pacstrap('libfido2')

						if 'sd-encrypt' not in self._hooks:
							self._hooks.insert(self._hooks.index('filesystems'), 'sd-encrypt')
					else:
						if 'encrypt' not in self._hooks:
							self._hooks.insert(self._hooks.index('filesystems'), 'encrypt')

		if not SysInfo.has_uefi():
			self.base_packages.append('grub')

		if not SysInfo.is_vm():
			vendor = SysInfo.cpu_vendor()
			if vendor == "AuthenticAMD":
				self.base_packages.append("amd-ucode")
				if (ucode := Path(f"{self.target}/boot/amd-ucode.img")).exists():
					ucode.unlink()
			elif vendor == "GenuineIntel":
				self.base_packages.append("intel-ucode")
				if (ucode := Path(f"{self.target}/boot/intel-ucode.img")).exists():
					ucode.unlink()
			else:
				debug(f"Unknown CPU vendor '{vendor}' detected. Archinstall won't install any ucode")

		# Determine whether to enable multilib/testing repositories before running pacstrap if testing flag is set.
		# This action takes place on the host system as pacstrap copies over package repository lists.
		if multilib:
			info("The multilib flag is set. This system will be installed with the multilib repository enabled.")
			self.enable_multilib_repository()
		else:
			info("The multilib flag is not set. This system will be installed without multilib repositories enabled.")

		if testing:
			info("The testing flag is set. This system will be installed with testing repositories enabled.")
			self.enable_testing_repositories(multilib)
		else:
			info("The testing flag is not set. This system will be installed without testing repositories enabled.")

		self._pacstrap(self.base_packages)
		self.helper_flags['base-strapped'] = True

		# This handles making sure that the repositories we enabled persist on the installed system
		if multilib or testing:
			shutil.copy2("/etc/pacman.conf", f"{self.target}/etc/pacman.conf")

		# Periodic TRIM may improve the performance and longevity of SSDs whilst
		# having no adverse effect on other devices. Most distributions enable
		# periodic TRIM by default.
		#
		# https://github.com/archlinux/archinstall/issues/880
		self.enable_periodic_trim()

		# TODO: Support locale and timezone
		# os.remove(f'{self.target}/etc/localtime')
		# sys_command(f'/usr/bin/arch-chroot {self.target} ln -s /usr/share/zoneinfo/{localtime} /etc/localtime')
		# sys_command('/usr/bin/arch-chroot /mnt hwclock --hctosys --localtime')
		self.set_hostname(hostname)
		self.set_locale(locale_config)

		# TODO: Use python functions for this
		SysCommand(f'/usr/bin/arch-chroot {self.target} chmod 700 /root')

		self.mkinitcpio(['-P'], locale_config)

		self.helper_flags['base'] = True

		# Run registered post-install hooks
		for function in self.post_base_install:
			info(f"Running post-installation hook: {function}")
			function(self)

		for plugin in plugins.values():
			if hasattr(plugin, 'on_install'):
				plugin.on_install(self)

	def setup_swap(self, kind :str = 'zram'):
		if kind == 'zram':
			info(f"Setting up swap on zram")
			self._pacstrap('zram-generator')

			# We could use the default example below, but maybe not the best idea: https://github.com/archlinux/archinstall/pull/678#issuecomment-962124813
			# zram_example_location = '/usr/share/doc/zram-generator/zram-generator.conf.example'
			# shutil.copy2(f"{self.target}{zram_example_location}", f"{self.target}/usr/lib/systemd/zram-generator.conf")
			with open(f"{self.target}/etc/systemd/zram-generator.conf", "w") as zram_conf:
				zram_conf.write("[zram0]\n")

			self.enable_service('systemd-zram-setup@zram0.service')

			self._zram_enabled = True
		else:
			raise ValueError(f"Archinstall currently only supports setting up swap on zram")

	def _get_boot_partition(self) -> Optional[disk.PartitionModification]:
		for layout in self._disk_config.device_modifications:
			if boot := layout.get_boot_partition():
				return boot
		return None

	def _get_root_partition(self) -> Optional[disk.PartitionModification]:
		for mod in self._disk_config.device_modifications:
			if root := mod.get_root_partition(self._disk_config.relative_mountpoint):
				return root
		return None

	def _add_systemd_bootloader(self, root_partition: disk.PartitionModification):
		self._pacstrap('efibootmgr')

		if not SysInfo.has_uefi():
			raise HardwareIncompatibilityError

		# TODO: Ideally we would want to check if another config
		# points towards the same disk and/or partition.
		# And in which case we should do some clean up.

		# Install the boot loader
		try:
			SysCommand(f'/usr/bin/arch-chroot {self.target} bootctl --esp-path=/boot install')
		except SysCallError:
			# Fallback, try creating the boot loader without touching the EFI variables
			SysCommand(f'/usr/bin/arch-chroot {self.target} bootctl --no-variables --esp-path=/boot install')

		# Ensure that the /boot/loader directory exists before we try to create files in it
		loader_dir = self.target / 'boot/loader'
		loader_dir.mkdir(parents=True, exist_ok=True)

		# Modify or create a loader.conf
		loader_conf = loader_dir / 'loader.conf'

		try:
			with loader_conf.open() as loader:
				loader_data = loader.read().split('\n')
		except FileNotFoundError:
			loader_data = [
				f"default {self.init_time}",
				"timeout 15"
			]

		with loader_conf.open('w') as loader:
			for line in loader_data:
				if line[:8] == 'default ':
					loader.write(f'default {self.init_time}_{self.kernels[0]}\n')
				elif line[:8] == '#timeout' and 'timeout 15' not in loader_data:
					# We add in the default timeout to support dual-boot
					loader.write(f"{line[1:]}\n")
				else:
					loader.write(f"{line}\n")

		# Ensure that the /boot/loader/entries directory exists before we try to create files in it
		entries_dir = loader_dir / 'entries'
		entries_dir.mkdir(parents=True, exist_ok=True)

		for kernel in self.kernels:
			for variant in ("", "-fallback"):
				# Setup the loader entry
				with open(entries_dir / f'{self.init_time}_{kernel}{variant}.conf', 'w') as entry:
					entry.write('# Created by: archinstall\n')
					entry.write(f'# Created on: {self.init_time}\n')
					entry.write(f'title Arch Linux ({kernel}{variant})\n')
					entry.write(f"linux /vmlinuz-{kernel}\n")
					if not SysInfo.is_vm():
						vendor = SysInfo.cpu_vendor()
						if vendor == "AuthenticAMD":
							entry.write("initrd /amd-ucode.img\n")
						elif vendor == "GenuineIntel":
							entry.write("initrd /intel-ucode.img\n")
						else:
							debug(
								f"Unknown CPU vendor '{vendor}' detected.",
								"Archinstall won't add any ucode to systemd-boot config.",
							)

					entry.write(f"initrd /initramfs-{kernel}{variant}.img\n")
					# blkid doesn't trigger on loopback devices really well,
					# so we'll use the old manual method until we get that sorted out.

					options_entry = f'rw rootfstype={root_partition.fs_type.fs_type_mount} {" ".join(self._kernel_params)}\n'

					for sub_vol in root_partition.btrfs_subvols:
						if sub_vol.is_root():
							options_entry = f"rootflags=subvol={sub_vol.name} " + options_entry

					# Zswap should be disabled when using zram.
					# https://github.com/archlinux/archinstall/issues/881
					if self._zram_enabled:
						options_entry = "zswap.enabled=0 " + options_entry

					if root_partition.fs_type.is_crypto():
						# TODO: We need to detect if the encrypted device is a whole disk encryption,
						#       or simply a partition encryption. Right now we assume it's a partition (and we always have)
						debug('Root partition is an encrypted device, identifying by PARTUUID: {root_partition.partuuid}')

						kernel_options = f"options"

						if self._disk_encryption and self._disk_encryption.hsm_device:
							# Note: lsblk UUID must be used, not PARTUUID for sd-encrypt to work
							kernel_options += f' rd.luks.name={root_partition.uuid}=luksdev'
							# Note: tpm2-device and fido2-device don't play along very well:
							# https://github.com/archlinux/archinstall/pull/1196#issuecomment-1129715645
							kernel_options += f' rd.luks.options=fido2-device=auto,password-echo=no'
						else:
							kernel_options += f' cryptdevice=PARTUUID={root_partition.partuuid}:luksdev'

						entry.write(f'{kernel_options} root=/dev/mapper/luksdev {options_entry}')
					else:
						debug(f'Identifying root partition by PARTUUID: {root_partition.partuuid}')
						entry.write(f'options root=PARTUUID={root_partition.partuuid} {options_entry}')

		self.helper_flags['bootloader'] = 'systemd'

	def _add_grub_bootloader(
		self,
		boot_partition: disk.PartitionModification,
		root_partition: disk.PartitionModification
	):
		self._pacstrap('grub')  # no need?

		_file = "/etc/default/grub"

		if root_partition.fs_type.is_crypto():
			debug(f"Using UUID {root_partition.uuid} as encrypted root identifier")

			cmd_line_linux = f"sed -i 's/GRUB_CMDLINE_LINUX=\"\"/GRUB_CMDLINE_LINUX=\"cryptdevice=UUID={root_partition.uuid}:cryptlvm rootfstype={root_partition.fs_type.value}\"/'"
			enable_cryptdisk = "sed -i 's/#GRUB_ENABLE_CRYPTODISK=y/GRUB_ENABLE_CRYPTODISK=y/'"

			SysCommand(f"/usr/bin/arch-chroot {self.target} {enable_cryptdisk} {_file}")
		else:
			cmd_line_linux = f"sed -i 's/GRUB_CMDLINE_LINUX=\"\"/GRUB_CMDLINE_LINUX=\"rootfstype={root_partition.fs_type.value}\"/'"

		SysCommand(f"/usr/bin/arch-chroot {self.target} {cmd_line_linux} {_file}")

		info(f"GRUB boot partition: {boot_partition.dev_path}")

		if SysInfo.has_uefi():
			self._pacstrap('efibootmgr') # TODO: Do we need? Yes, but remove from minimal_installation() instead?

			try:
				SysCommand(f'/usr/bin/arch-chroot {self.target} grub-install --debug --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB --removable', peek_output=True)
			except SysCallError:
				try:
					SysCommand(f'/usr/bin/arch-chroot {self.target} grub-install --debug --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB --removable', peek_output=True)
				except SysCallError as err:
					raise DiskError(f"Could not install GRUB to {self.target}/boot: {err}")
		else:
			device = disk.device_handler.get_device_by_partition_path(boot_partition.safe_dev_path)

			if not device:
				raise ValueError(f'Can not find block device: {boot_partition.safe_dev_path}')

			try:
				cmd = f'/usr/bin/arch-chroot' \
					f' {self.target}' \
					f' grub-install' \
					f' --debug' \
					f' --target=i386-pc' \
					f' --recheck {device.device_info.path}'

				SysCommand(cmd, peek_output=True)
			except SysCallError as err:
				raise DiskError(f"Failed to install GRUB boot on {boot_partition.dev_path}: {err}")

		try:
			SysCommand(f'/usr/bin/arch-chroot {self.target} grub-mkconfig -o /boot/grub/grub.cfg')
		except SysCallError as err:
			raise DiskError(f"Could not configure GRUB: {err}")

		self.helper_flags['bootloader'] = "grub"

	def _add_efistub_bootloader(
		self,
		boot_partition: disk.PartitionModification,
		root_partition: disk.PartitionModification
	):
		self._pacstrap('efibootmgr')

		if not SysInfo.has_uefi():
			raise HardwareIncompatibilityError

		# TODO: Ideally we would want to check if another config
		# points towards the same disk and/or partition.
		# And in which case we should do some clean up.

		for kernel in self.kernels:
			# Setup the firmware entry
			label = f'Arch Linux ({kernel})'
			loader = f"/vmlinuz-{kernel}"

			kernel_parameters = []

			if not SysInfo.is_vm():
				vendor = SysInfo.cpu_vendor()
				if vendor == "AuthenticAMD":
					kernel_parameters.append("initrd=\\amd-ucode.img")
				elif vendor == "GenuineIntel":
					kernel_parameters.append("initrd=\\intel-ucode.img")
				else:
					debug(f"Unknown CPU vendor '{vendor}' detected. Archinstall won't add any ucode to firmware boot entry.")

			kernel_parameters.append(f"initrd=\\initramfs-{kernel}.img")

			# blkid doesn't trigger on loopback devices really well,
			# so we'll use the old manual method until we get that sorted out.

			if root_partition.fs_type.is_crypto():
				# TODO: We need to detect if the encrypted device is a whole disk encryption,
				#       or simply a partition encryption. Right now we assume it's a partition (and we always have)
				debug(f'Identifying root partition by PARTUUID: {root_partition.partuuid}')
				kernel_parameters.append(f'cryptdevice=PARTUUID={root_partition.partuuid}:luksdev root=/dev/mapper/luksdev rw rootfstype={root_partition.fs_type.value} {" ".join(self._kernel_params)}')
			else:
				debug(f'Root partition is an encrypted device identifying by PARTUUID: {root_partition.partuuid}')
				kernel_parameters.append(f'root=PARTUUID={root_partition.partuuid} rw rootfstype={root_partition.fs_type.value} {" ".join(self._kernel_params)}')

			device = disk.device_handler.get_device_by_partition_path(boot_partition.safe_dev_path)

			if not device:
				raise ValueError(f'Unable to find block device: {boot_partition.safe_dev_path}')

			cmd = f'efibootmgr ' \
				f'--disk {device.device_info.path} ' \
				f'--part {boot_partition.safe_dev_path} ' \
				f'--create ' \
				f'--label "{label}" ' \
				f'--loader {loader} ' \
				f'--unicode \'{" ".join(kernel_parameters)}\' ' \
				f'--verbose'

			SysCommand(cmd)

		self.helper_flags['bootloader'] = "efistub"

	def add_bootloader(self, bootloader: Bootloader):
		"""
		Adds a bootloader to the installation instance.
		Archinstall supports one of three types:
		* systemd-bootctl
		* grub
		* efistub (beta)

		:param bootloader: Type of bootloader to be added
		"""

		for plugin in plugins.values():
			if hasattr(plugin, 'on_add_bootloader'):
				# Allow plugins to override the boot-loader handling.
				# This allows for bot configuring and installing bootloaders.
				if plugin.on_add_bootloader(self):
					return True

		if type(self.target) == str:
			self.target = Path(self.target)

		boot_partition = self._get_boot_partition()
		root_partition = self._get_root_partition()

		if boot_partition is None:
			raise ValueError(f'Could not detect boot at mountpoint {self.target}')

		if root_partition is None:
			raise ValueError(f'Could not detect root at mountpoint {self.target}')

		info(f'Adding bootloader {bootloader.value} to {boot_partition.dev_path}')

		match bootloader:
			case Bootloader.Systemd:
				self._add_systemd_bootloader(root_partition)
			case Bootloader.Grub:
				self._add_grub_bootloader(boot_partition, root_partition)
			case Bootloader.Efistub:
				self._add_efistub_bootloader(boot_partition, root_partition)

	def add_additional_packages(self, packages: Union[str, List[str]]) -> bool:
		return self._pacstrap(packages)

	def _enable_users(self, service: str, users: List[User]):
		for user in users:
			self.arch_chroot(f'systemctl enable --user {service}', run_as=user.username)

	def enable_sudo(self, entity: str, group :bool = False):
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
		file_num_str = "{:02d}".format(num_of_rules_already) # We want 00_user1, 01_user2, etc

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

	def user_create(self, user :str, password :Optional[str] = None, groups :Optional[List[str]] = None, sudo :bool = False) -> None:
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

	def user_set_pw(self, user :str, password :str) -> bool:
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

	def user_set_shell(self, user :str, shell :str) -> bool:
		info(f'Setting shell for {user} to {shell}')

		try:
			SysCommand(f"/usr/bin/arch-chroot {self.target} sh -c \"chsh -s {shell} {user}\"")
			return True
		except SysCallError:
			return False

	def chown(self, owner :str, path :str, options :List[str] = []) -> bool:
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

	def _service_started(self, service_name: str) -> str | None:
		if os.path.splitext(service_name)[1] not in ('.service', '.target', '.timer'):
			service_name += '.service'  # Just to be safe

		last_execution_time = b''.join(SysCommand(f"systemctl show --property=ActiveEnterTimestamp --no-pager {service_name}", environment_vars={'SYSTEMD_COLORS': '0'}))
		last_execution_time = last_execution_time.lstrip(b'ActiveEnterTimestamp=').strip()
		if not last_execution_time:
			return None

		return last_execution_time.decode('UTF-8')

	def _service_state(self, service_name: str) -> str:
		if os.path.splitext(service_name)[1] not in ('.service', '.target', '.timer'):
			service_name += '.service'  # Just to be safe

		state = b''.join(SysCommand(f'systemctl show --no-pager -p SubState --value {service_name}', environment_vars={'SYSTEMD_COLORS': '0'}))

		return state.strip().decode('UTF-8')
