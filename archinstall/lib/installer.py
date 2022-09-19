import time
import logging
import os
import re
import shutil
import shlex
import pathlib
import subprocess
import glob
from types import ModuleType
from typing import Union, Dict, Any, List, Optional, Iterator, Mapping, TYPE_CHECKING
from .disk import get_partitions_in_use, Partition
from .general import SysCommand, generate_password
from .hardware import has_uefi, is_vm, cpu_vendor
from .locale_helpers import verify_keyboard_layout, verify_x11_keyboard_layout
from .disk.helpers import findmnt
from .mirrors import use_mirrors
from .plugins import plugins
from .storage import storage
# from .user_interaction import *
from .output import log
from .profiles import Profile
from .disk.partition import get_mount_fs_type
from .exceptions import DiskError, ServiceException, RequirementError, HardwareIncompatibilityError, SysCallError
from .hsm import fido2_enroll
from .models.users import User
from .models.subvolume import Subvolume

if TYPE_CHECKING:
	_: Any


# Any package that the Installer() is responsible for (optional and the default ones)
__packages__ = ["base", "base-devel", "linux-firmware", "linux", "linux-lts", "linux-zen", "linux-hardened"]

# Additional packages that are installed if the user is running the Live ISO with accessibility tools enabled
__accessibility_packages__ = ["brltty", "espeakup", "alsa-utils"]

from .pacman import run_pacman
from .models.network_configuration import NetworkConfiguration


class InstallationFile:
	def __init__(self, installation :'Installer', filename :str, owner :str, mode :str = "w"):
		self.installation = installation
		self.filename = filename
		self.owner = owner
		self.mode = mode
		self.fh = None

	def __enter__(self) -> 'InstallationFile':
		self.fh = open(self.filename, self.mode)
		return self

	def __exit__(self, *args :str) -> None:
		self.fh.close()
		self.installation.chown(self.owner, self.filename)

	def write(self, data: Union[str, bytes]) -> int:
		return self.fh.write(data)

	def read(self, *args) -> Union[str, bytes]:
		return self.fh.read(*args)

# 	def poll(self, *args) -> bool:
# 		return self.fh.poll(*args)


def accessibility_tools_in_use() -> bool:
	return os.system('systemctl is-active --quiet espeakup.service') == 0


class Installer:
	"""
	`Installer()` is the wrapper for most basic installation steps.
	It also wraps :py:func:`~archinstall.Installer.pacstrap` among other things.

	:param partition: Requires a partition as the first argument, this is
		so that the installer can mount to `mountpoint` and strap packages there.
	:type partition: class:`archinstall.Partition`

	:param boot_partition: There's two reasons for needing a boot partition argument,
		The first being so that `mkinitcpio` can place the `vmlinuz` kernel at the right place
		during the `pacstrap` or `linux` and the base packages for a minimal installation.
		The second being when :py:func:`~archinstall.Installer.add_bootloader` is called,
		A `boot_partition` must be known to the installer before this is called.
	:type boot_partition: class:`archinstall.Partition`

	:param profile: A profile to install, this is optional and can be called later manually.
		This just simplifies the process by not having to call :py:func:`~archinstall.Installer.install_profile` later on.
	:type profile: str, optional

	:param hostname: The given /etc/hostname for the machine.
	:type hostname: str, optional

	"""

	def __init__(self, target :str, *, base_packages :Optional[List[str]] = None, kernels :Optional[List[str]] = None):
		if base_packages is None:
			base_packages = __packages__[:3]
		if kernels is None:
			self.kernels = ['linux']
		else:
			self.kernels = kernels
		self.target = target
		self.init_time = time.strftime('%Y-%m-%d_%H-%M-%S')
		self.milliseconds = int(str(time.time()).split('.')[1])

		self.helper_flags = {
			'base': False,
			'bootloader': False
		}

		self.base_packages = base_packages.split(' ') if type(base_packages) is str else base_packages
		for kernel in self.kernels:
			self.base_packages.append(kernel)

		# If using accessibility tools in the live environment, append those to the packages list
		if accessibility_tools_in_use():
			self.base_packages.extend(__accessibility_packages__)

		self.post_base_install = []

		# TODO: Figure out which one of these two we'll use.. But currently we're mixing them..
		storage['session'] = self
		storage['installation_session'] = self

		self.MODULES = []
		self.BINARIES = []
		self.FILES = []
		# systemd, sd-vconsole and sd-encrypt will be replaced by udev, keymap and encrypt
		# if HSM is not used to encrypt the root volume. Check mkinitcpio() function for that override.
		self.HOOKS = ["base", "systemd", "autodetect", "keyboard", "sd-vconsole", "modconf", "block", "filesystems", "fsck"]
		self.KERNEL_PARAMS = []

		self._zram_enabled = False

	def log(self, *args :str, level :int = logging.DEBUG, **kwargs :str):
		"""
		installer.log() wraps output.log() mainly to set a default log-level for this install session.
		Any manual override can be done per log() call.
		"""
		log(*args, level=level, **kwargs)

	def __enter__(self, *args :str, **kwargs :str) -> 'Installer':
		return self

	def __exit__(self, *args :str, **kwargs :str) -> None:
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if len(args) >= 2 and args[1]:
			self.log(args[1], level=logging.ERROR, fg='red')

			self.sync_log_to_install_medium()

			# We avoid printing /mnt/<log path> because that might confuse people if they note it down
			# and then reboot, and a identical log file will be found in the ISO medium anyway.
			print(_("[!] A log file has been created here: {}").format(os.path.join(storage['LOG_PATH'], storage['LOG_FILE'])))
			print(_("    Please submit this issue (and file) to https://github.com/archlinux/archinstall/issues"))
			raise args[1]

		if not (missing_steps := self.post_install_check()):
			self.log('Installation completed without any errors. You may now reboot.', fg='green', level=logging.INFO)
			self.sync_log_to_install_medium()

			return True
		else:
			self.log('Some required steps were not successfully installed/configured before leaving the installer:', fg='red', level=logging.WARNING)
			for step in missing_steps:
				self.log(f' - {step}', fg='red', level=logging.WARNING)

			self.log(f"Detailed error logs can be found at: {storage['LOG_PATH']}", level=logging.WARNING)
			self.log("Submit this zip file as an issue to https://github.com/archlinux/archinstall/issues", level=logging.WARNING)

			self.sync_log_to_install_medium()
			return False

	@property
	def partitions(self) -> List[Partition]:
		return get_partitions_in_use(self.target).values()

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

	def _create_keyfile(self,luks_handle , partition :dict, password :str):
		""" roiutine to create keyfiles, so it can be moved elsewhere
		"""
		if partition.get('generate-encryption-key-file'):
			if not (cryptkey_dir := pathlib.Path(f"{self.target}/etc/cryptsetup-keys.d")).exists():
				cryptkey_dir.mkdir(parents=True)
			# Once we store the key as ../xyzloop.key systemd-cryptsetup can automatically load this key
			# if we name the device to "xyzloop".
			if partition.get('mountpoint',None):
				encryption_key_path = f"/etc/cryptsetup-keys.d/{pathlib.Path(partition['mountpoint']).name}loop.key"
			else:
				encryption_key_path = f"/etc/cryptsetup-keys.d/{pathlib.Path(partition['device_instance'].path).name}.key"
			with open(f"{self.target}{encryption_key_path}", "w") as keyfile:
				keyfile.write(generate_password(length=512))

			os.chmod(f"{self.target}{encryption_key_path}", 0o400)

			luks_handle.add_key(pathlib.Path(f"{self.target}{encryption_key_path}"), password=password)
			luks_handle.crypttab(self, encryption_key_path, options=["luks", "key-slot=1"])

	def _has_root(self, partition :dict) -> bool:
		"""
		Determine if an encrypted partition contains root in it
		"""
		if partition.get("mountpoint") is None:
			if (sub_list := partition.get("btrfs",{}).get('subvolumes',{})):
				for mountpoint in [sub_list[subvolume].get("mountpoint") if isinstance(subvolume, dict) else subvolume.mountpoint for subvolume in sub_list]:
					if mountpoint == '/':
						return True
				return False
			else:
				return False
		elif partition.get("mountpoint") == '/':
			return True
		else:
			return False

	def mount_ordered_layout(self, layouts: Dict[str, Any]) -> None:
		from .luks import luks2
		from .disk.btrfs import setup_subvolumes, mount_subvolume

		# set the partitions as a list not part of a tree (which we don't need anymore (i think)
		list_part = []
		list_luks_handles = []
		for blockdevice in layouts:
			list_part.extend(layouts[blockdevice]['partitions'])

		# TODO: Implement a proper mount-queue system that does not depend on return values.
		mount_queue = {}

		# we manage the encrypted partititons
		for partition in [entry for entry in list_part if entry.get('encrypted', False)]:
			# open the luks device and all associate stuff
			if not (password := partition.get('!password', None)) and storage['arguments'].get('!encryption-password'):
				password = storage['arguments'].get('!encryption-password')
			elif not password:
				raise RequirementError(f"Missing partition encryption password in layout: {partition}")
			
			loopdev = f"{storage.get('ENC_IDENTIFIER', 'ai')}{pathlib.Path(partition['device_instance'].path).name}"

			# note that we DON'T auto_unmount (i.e. close the encrypted device so it can be used
			with (luks_handle := luks2(partition['device_instance'], loopdev, password, auto_unmount=False)) as unlocked_device:
				if partition.get('generate-encryption-key-file', False) and not self._has_root(partition):
					list_luks_handles.append([luks_handle, partition, password])
				# this way all the requesrs will be to the dm_crypt device and not to the physical partition
				partition['device_instance'] = unlocked_device

			if self._has_root(partition) and partition.get('generate-encryption-key-file', False) is False:
				if storage['arguments'].get('HSM'):
					hsm_device_path = storage['arguments']['HSM']
					fido2_enroll(hsm_device_path, partition['device_instance'], password)

		btrfs_subvolumes = [entry for entry in list_part if entry.get('btrfs', {}).get('subvolumes', [])]

		for partition in btrfs_subvolumes:
			device_instance = partition['device_instance']
			mount_options = partition.get('filesystem', {}).get('mount_options', [])
			self.mount(device_instance, "/", options=','.join(mount_options))
			setup_subvolumes(installation=self, partition_dict=partition)
			device_instance.unmount()

		# We then handle any special cases, such as btrfs
		for partition in btrfs_subvolumes:
			subvolumes: List[Subvolume] = partition['btrfs']['subvolumes']
			for subvolume in sorted(subvolumes, key=lambda item: item.mountpoint):
				# We cache the mount call for later
				mount_queue[subvolume.mountpoint] = lambda sub_vol=subvolume, device=partition['device_instance']: mount_subvolume(
						installation=self,
						device=device,
						subvolume=sub_vol
					)

		# We mount ordinary partitions, and we sort them by the mountpoint
		for partition in sorted([entry for entry in list_part if entry.get('mountpoint', False)], key=lambda part: part['mountpoint']):
			mountpoint = partition['mountpoint']
			log(f"Mounting {mountpoint} to {self.target}{mountpoint} using {partition['device_instance']}", level=logging.INFO)

			if partition.get('filesystem',{}).get('mount_options',[]):
				mount_options = ','.join(partition['filesystem']['mount_options'])
				mount_queue[mountpoint] = lambda instance=partition['device_instance'], target=f"{self.target}{mountpoint}", options=mount_options: instance.mount(target, options=options)
			else:
				mount_queue[mountpoint] = lambda instance=partition['device_instance'], target=f"{self.target}{mountpoint}": instance.mount(target)

		log(f"Using mount order: {list(sorted(mount_queue.items(), key=lambda item: item[0]))}", level=logging.INFO, fg="white")

		# We mount everything by sorting on the mountpoint itself.
		for mountpoint, frozen_func in sorted(mount_queue.items(), key=lambda item: item[0]):
			frozen_func()

			time.sleep(1)

			try:
				findmnt(pathlib.Path(f"{self.target}{mountpoint}"), traverse=False)
			except DiskError:
				raise DiskError(f"Target {self.target}{mountpoint} never got mounted properly (unable to get mount information using findmnt).")

		# once everything is mounted, we generate the key files in the correct place
		for handle in list_luks_handles:
			ppath = handle[1]['device_instance'].path
			log(f"creating key-file for {ppath}",level=logging.INFO)
			self._create_keyfile(handle[0],handle[1],handle[2])

	def mount(self, partition :Partition, mountpoint :str, create_mountpoint :bool = True, options='') -> None:
		if create_mountpoint and not os.path.isdir(f'{self.target}{mountpoint}'):
			os.makedirs(f'{self.target}{mountpoint}')

		partition.mount(f'{self.target}{mountpoint}', options=options)

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

	def pacstrap(self, *packages :str, **kwargs :str) -> bool:
		if type(packages[0]) in (list, tuple):
			packages = packages[0]

		for plugin in plugins.values():
			if hasattr(plugin, 'on_pacstrap'):
				if (result := plugin.on_pacstrap(packages)):
					packages = result

		self.log(f'Installing packages: {packages}', level=logging.INFO)

		# TODO: We technically only need to run the -Syy once.
		try:
			run_pacman('-Syy', default_cmd='/usr/bin/pacman')
		except SysCallError as error:
			self.log(f'Could not sync a new package database: {error}', level=logging.ERROR, fg="red")

			if storage['arguments'].get('silent', False) is False:
				if input('Would you like to re-try this download? (Y/n): ').lower().strip() in ('', 'y'):
					return self.pacstrap(*packages, **kwargs)

			raise RequirementError(f'Could not sync mirrors: {error}', level=logging.ERROR, fg="red")

		try:
			return SysCommand(f'/usr/bin/pacstrap -C /etc/pacman.conf {self.target} {" ".join(packages)} --noconfirm', peak_output=True).exit_code == 0
		except SysCallError as error:
			self.log(f'Could not strap in packages: {error}', level=logging.ERROR, fg="red")

			if storage['arguments'].get('silent', False) is False:
				if input('Would you like to re-try this download? (Y/n): ').lower().strip() in ('', 'y'):
					return self.pacstrap(*packages, **kwargs)

			raise RequirementError("Pacstrap failed. See /var/log/archinstall/install.log or above message for error details.")

	def set_mirrors(self, mirrors :Mapping[str, Iterator[str]]) -> None:
		for plugin in plugins.values():
			if hasattr(plugin, 'on_mirrors'):
				if result := plugin.on_mirrors(mirrors):
					mirrors = result

		return use_mirrors(mirrors, destination=f'{self.target}/etc/pacman.d/mirrorlist')

	def genfstab(self, flags :str = '-pU') -> bool:
		self.log(f"Updating {self.target}/etc/fstab", level=logging.INFO)

		if not (fstab := SysCommand(f'/usr/bin/genfstab {flags} {self.target}')).exit_code == 0:
			raise RequirementError(f'Could not generate fstab, strapping in packages most likely failed (disk out of space?)\n Error: {fstab}')

		with open(f"{self.target}/etc/fstab", 'a') as fstab_fh:
			fstab_fh.write(fstab.decode())

		if not os.path.isfile(f'{self.target}/etc/fstab'):
			raise RequirementError(f'Could not generate fstab, strapping in packages most likely failed (disk out of space?)\n Error: {fstab}')

		for plugin in plugins.values():
			if hasattr(plugin, 'on_genfstab'):
				if plugin.on_genfstab(self) is True:
					break

		return True

	def set_hostname(self, hostname: str, *args :str, **kwargs :str) -> None:
		with open(f'{self.target}/etc/hostname', 'w') as fh:
			fh.write(hostname + '\n')

	def set_locale(self, locale :str, encoding :str = 'UTF-8', *args :str, **kwargs :str) -> bool:
		if not len(locale):
			return True

		modifier = ''

		# This is a temporary patch to fix #1200
		if '.' in locale:
			locale, potential_encoding = locale.split('.', 1)

			# Override encoding if encoding is set to the default parameter
			# and the "found" encoding differs.
			if encoding == 'UTF-8' and encoding != potential_encoding:
				encoding = potential_encoding

		# Make sure we extract the modifier, that way we can put it in if needed.
		if '@' in locale:
			locale, modifier = locale.split('@', 1)
			modifier = f"@{modifier}"
		# - End patch

		with open(f'{self.target}/etc/locale.gen', 'a') as fh:
			fh.write(f'{locale}.{encoding}{modifier} {encoding}\n')
		with open(f'{self.target}/etc/locale.conf', 'w') as fh:
			fh.write(f'LANG={locale}.{encoding}{modifier}\n')

		return True if SysCommand(f'/usr/bin/arch-chroot {self.target} locale-gen').exit_code == 0 else False

	def set_timezone(self, zone :str, *args :str, **kwargs :str) -> bool:
		if not zone:
			return True
		if not len(zone):
			return True  # Redundant

		for plugin in plugins.values():
			if hasattr(plugin, 'on_timezone'):
				if result := plugin.on_timezone(zone):
					zone = result

		if (pathlib.Path("/usr") / "share" / "zoneinfo" / zone).exists():
			(pathlib.Path(self.target) / "etc" / "localtime").unlink(missing_ok=True)
			SysCommand(f'/usr/bin/arch-chroot {self.target} ln -s /usr/share/zoneinfo/{zone} /etc/localtime')
			return True

		else:
			self.log(
				f"Time zone {zone} does not exist, continuing with system default.",
				level=logging.WARNING,
				fg='red'
			)

		return False

	def activate_ntp(self) -> None:
		log(f"activate_ntp() is deprecated, use activate_time_syncronization()", fg="yellow", level=logging.INFO)
		self.activate_time_syncronization()

	def activate_time_syncronization(self) -> None:
		self.log('Activating systemd-timesyncd for time synchronization using Arch Linux and ntp.org NTP servers.', level=logging.INFO)
		self.enable_service('systemd-timesyncd')

		with open(f"{self.target}/etc/systemd/timesyncd.conf", "w") as fh:
			fh.write("[Time]\n")
			fh.write("NTP=0.arch.pool.ntp.org 1.arch.pool.ntp.org 2.arch.pool.ntp.org 3.arch.pool.ntp.org\n")
			fh.write("FallbackNTP=0.pool.ntp.org 1.pool.ntp.org 0.fr.pool.ntp.org\n")

		from .systemd import Boot
		with Boot(self) as session:
			session.SysCommand(["timedatectl", "set-ntp", 'true'])

	def enable_espeakup(self) -> None:
		self.log('Enabling espeakup.service for speech synthesis (accessibility).', level=logging.INFO)
		self.enable_service('espeakup')

	def enable_periodic_trim(self) -> None:
		self.log("Enabling periodic TRIM")
		# fstrim is owned by util-linux, a dependency of both base and systemd.
		self.enable_service("fstrim.timer")

	def enable_service(self, *services :str) -> None:
		for service in services:
			self.log(f'Enabling service {service}', level=logging.INFO)
			if (output := self.arch_chroot(f'systemctl enable {service}')).exit_code != 0:
				raise ServiceException(f"Unable to start service {service}: {output}")

			for plugin in plugins.values():
				if hasattr(plugin, 'on_service'):
					plugin.on_service(service)

	def run_command(self, cmd :str, *args :str, **kwargs :str) -> None:
		return SysCommand(f'/usr/bin/arch-chroot {self.target} {cmd}')

	def arch_chroot(self, cmd :str, run_as :Optional[str] = None):
		if run_as:
			cmd = f"su - {run_as} -c {shlex.quote(cmd)}"

		return self.run_command(cmd)

	def drop_to_shell(self) -> None:
		subprocess.check_call(f"/usr/bin/arch-chroot {self.target}", shell=True)

	def configure_nic(self, network_config: NetworkConfiguration) -> None:
		from .systemd import Networkd

		if network_config.dhcp:
			conf = Networkd(Match={"Name": network_config.iface}, Network={"DHCP": "yes"})
		else:
			network = {"Address": network_config.ip}
			if network_config.gateway:
				network["Gateway"] = network_config.gateway
			if network_config.dns:
				dns = network_config.dns
				network["DNS"] = dns if isinstance(dns, list) else [dns]

			conf = Networkd(Match={"Name": network_config.iface}, Network=network)

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
						self.pacstrap('iwd')
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
						self.enable_service('systemd-networkd', 'systemd-resolved')

					self.post_base_install.append(post_install_enable_networkd_resolved)
				# Otherwise, we can go ahead and enable the services
				else:
					self.enable_service('systemd-networkd', 'systemd-resolved')

		return True

	def detect_encryption(self, partition :Partition) -> bool:
		from .disk.mapperdev import MapperDev
		from .disk.dmcryptdev import DMCryptDev
		from .disk.helpers import get_filesystem_type

		if type(partition) is MapperDev:
			# Returns MapperDev.partition
			return partition.partition
		elif type(partition) is DMCryptDev:
			return partition.MapperDev.partition
		elif get_filesystem_type(partition.path) == 'crypto_LUKS':
			return partition

		return False

	def mkinitcpio(self, *flags :str) -> bool:
		for plugin in plugins.values():
			if hasattr(plugin, 'on_mkinitcpio'):
				# Allow plugins to override the usage of mkinitcpio altogether.
				if plugin.on_mkinitcpio(self):
					return True

		with open(f'{self.target}/etc/mkinitcpio.conf', 'w') as mkinit:
			mkinit.write(f"MODULES=({' '.join(self.MODULES)})\n")
			mkinit.write(f"BINARIES=({' '.join(self.BINARIES)})\n")
			mkinit.write(f"FILES=({' '.join(self.FILES)})\n")

			if not storage['arguments'].get('HSM'):
				# For now, if we don't use HSM we revert to the old
				# way of setting up encryption hooks for mkinitcpio.
				# This is purely for stability reasons, we're going away from this.
				# * systemd -> udev
				# * sd-vconsole -> keymap
				self.HOOKS = [hook.replace('systemd', 'udev').replace('sd-vconsole', 'keymap') for hook in self.HOOKS]

			mkinit.write(f"HOOKS=({' '.join(self.HOOKS)})\n")

		return SysCommand(f'/usr/bin/arch-chroot {self.target} mkinitcpio {" ".join(flags)}').exit_code == 0

	def minimal_installation(self, testing=False, multilib=False) -> bool:
		# Add necessary packages if encrypting the drive
		# (encrypted partitions default to btrfs for now, so we need btrfs-progs)
		# TODO: Perhaps this should be living in the function which dictates
		#       the partitioning. Leaving here for now.

		for partition in self.partitions:
			if partition.filesystem == 'btrfs':
				# if partition.encrypted:
				if 'btrfs-progs' not in self.base_packages:
					self.base_packages.append('btrfs-progs')
			if partition.filesystem == 'xfs':
				if 'xfs' not in self.base_packages:
					self.base_packages.append('xfsprogs')
			if partition.filesystem == 'f2fs':
				if 'f2fs' not in self.base_packages:
					self.base_packages.append('f2fs-tools')

			# Configure mkinitcpio to handle some specific use cases.
			if partition.filesystem == 'btrfs':
				if 'btrfs' not in self.MODULES:
					self.MODULES.append('btrfs')
				if '/usr/bin/btrfs' not in self.BINARIES:
					self.BINARIES.append('/usr/bin/btrfs')
			# There is not yet an fsck tool for NTFS. If it's being used for the root filesystem, the hook should be removed.
			if partition.filesystem == 'ntfs3' and partition.mountpoint == self.target:
				if 'fsck' in self.HOOKS:
					self.HOOKS.remove('fsck')

			if self.detect_encryption(partition):
				if storage['arguments'].get('HSM'):
					# Required bby mkinitcpio to add support for fido2-device options
					self.pacstrap('libfido2')

					if 'sd-encrypt' not in self.HOOKS:
						self.HOOKS.insert(self.HOOKS.index('filesystems'), 'sd-encrypt')
				else:
					if 'encrypt' not in self.HOOKS:
						self.HOOKS.insert(self.HOOKS.index('filesystems'), 'encrypt')

		if not has_uefi():
			self.base_packages.append('grub')

		if not is_vm():
			vendor = cpu_vendor()
			if vendor == "AuthenticAMD":
				self.base_packages.append("amd-ucode")
				if (ucode := pathlib.Path(f"{self.target}/boot/amd-ucode.img")).exists():
					ucode.unlink()
			elif vendor == "GenuineIntel":
				self.base_packages.append("intel-ucode")
				if (ucode := pathlib.Path(f"{self.target}/boot/intel-ucode.img")).exists():
					ucode.unlink()
			else:
				self.log(f"Unknown CPU vendor '{vendor}' detected. Archinstall won't install any ucode.", level=logging.DEBUG)

		# Determine whether to enable multilib/testing repositories before running pacstrap if testing flag is set.
		# This action takes place on the host system as pacstrap copies over package repository lists.
		if multilib:
			self.log("The multilib flag is set. This system will be installed with the multilib repository enabled.")
			self.enable_multilib_repository()
		else:
			self.log("The multilib flag is not set. This system will be installed without multilib repositories enabled.")

		if testing:
			self.log("The testing flag is set. This system will be installed with testing repositories enabled.")
			self.enable_testing_repositories(multilib)
		else:
			self.log("The testing flag is not set. This system will be installed without testing repositories enabled.")

		self.pacstrap(self.base_packages)
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
		self.set_hostname('archinstall')
		self.set_locale('en_US')

		# TODO: Use python functions for this
		SysCommand(f'/usr/bin/arch-chroot {self.target} chmod 700 /root')

		if storage['arguments'].get('HSM'):
			# TODO:
			# A bit of a hack, but we need to get vconsole.conf in there
			# before running `mkinitcpio` because it expects it in HSM mode.
			if (vconsole := pathlib.Path(f"{self.target}/etc/vconsole.conf")).exists() is False:
				with vconsole.open('w') as fh:
					fh.write(f"KEYMAP={storage['arguments']['keyboard-layout']}\n")

		self.mkinitcpio('-P')

		self.helper_flags['base'] = True

		# Run registered post-install hooks
		for function in self.post_base_install:
			self.log(f"Running post-installation hook: {function}", level=logging.INFO)
			function(self)

		for plugin in plugins.values():
			if hasattr(plugin, 'on_install'):
				plugin.on_install(self)

		return True

	def setup_swap(self, kind :str = 'zram') -> bool:
		if kind == 'zram':
			self.log(f"Setting up swap on zram")
			self.pacstrap('zram-generator')

			# We could use the default example below, but maybe not the best idea: https://github.com/archlinux/archinstall/pull/678#issuecomment-962124813
			# zram_example_location = '/usr/share/doc/zram-generator/zram-generator.conf.example'
			# shutil.copy2(f"{self.target}{zram_example_location}", f"{self.target}/usr/lib/systemd/zram-generator.conf")
			with open(f"{self.target}/etc/systemd/zram-generator.conf", "w") as zram_conf:
				zram_conf.write("[zram0]\n")

			self.enable_service('systemd-zram-setup@zram0.service')

			self._zram_enabled = True

			return True
		else:
			raise ValueError(f"Archinstall currently only supports setting up swap on zram")

	def add_systemd_bootloader(self, boot_partition :Partition, root_partition :Partition) -> bool:
		self.pacstrap('efibootmgr')

		if not has_uefi():
			raise HardwareIncompatibilityError
		# TODO: Ideally we would want to check if another config
		# points towards the same disk and/or partition.
		# And in which case we should do some clean up.

		# Install the boot loader
		try:
			SysCommand(f'/usr/bin/arch-chroot {self.target} bootctl --path=/boot install')
		except SysCallError:
			# Fallback, try creating the boot loader without touching the EFI variables
			SysCommand(f'/usr/bin/arch-chroot {self.target} bootctl --no-variables --path=/boot install')

		# Ensure that the /boot/loader directory exists before we try to create files in it
		if not os.path.exists(f'{self.target}/boot/loader'):
			os.makedirs(f'{self.target}/boot/loader')

		# Modify or create a loader.conf
		if os.path.isfile(f'{self.target}/boot/loader/loader.conf'):
			with open(f'{self.target}/boot/loader/loader.conf', 'r') as loader:
				loader_data = loader.read().split('\n')
		else:
			loader_data = [
				f"default {self.init_time}",
				"timeout 15"
			]

		with open(f'{self.target}/boot/loader/loader.conf', 'w') as loader:
			for line in loader_data:
				if line[:8] == 'default ':
					loader.write(f'default {self.init_time}_{self.kernels[0]}\n')
				elif line[:8] == '#timeout' and 'timeout 15' not in loader_data:
					# We add in the default timeout to support dual-boot
					loader.write(f"{line[1:]}\n")
				else:
					loader.write(f"{line}\n")

		# Ensure that the /boot/loader/entries directory exists before we try to create files in it
		if not os.path.exists(f'{self.target}/boot/loader/entries'):
			os.makedirs(f'{self.target}/boot/loader/entries')

		for kernel in self.kernels:
			# Setup the loader entry
			with open(f'{self.target}/boot/loader/entries/{self.init_time}_{kernel}.conf', 'w') as entry:
				entry.write('# Created by: archinstall\n')
				entry.write(f'# Created on: {self.init_time}\n')
				entry.write(f'title Arch Linux ({kernel})\n')
				entry.write(f"linux /vmlinuz-{kernel}\n")
				if not is_vm():
					vendor = cpu_vendor()
					if vendor == "AuthenticAMD":
						entry.write("initrd /amd-ucode.img\n")
					elif vendor == "GenuineIntel":
						entry.write("initrd /intel-ucode.img\n")
					else:
						self.log(f"Unknown CPU vendor '{vendor}' detected. Archinstall won't add any ucode to systemd-boot config.", level=logging.DEBUG)
				entry.write(f"initrd /initramfs-{kernel}.img\n")
				# blkid doesn't trigger on loopback devices really well,
				# so we'll use the old manual method until we get that sorted out.
				root_fs_type = get_mount_fs_type(root_partition.filesystem)

				if root_fs_type is not None:
					options_entry = f'rw intel_pstate=no_hwp rootfstype={root_fs_type} {" ".join(self.KERNEL_PARAMS)}\n'
				else:
					options_entry = f'rw intel_pstate=no_hwp {" ".join(self.KERNEL_PARAMS)}\n'

				for subvolume in root_partition.subvolumes:
					if subvolume.root is True and subvolume.name != '<FS_TREE>':
						options_entry = f"rootflags=subvol={subvolume.name} " + options_entry

				# Zswap should be disabled when using zram.
				#
				# https://github.com/archlinux/archinstall/issues/881
				if self._zram_enabled:
					options_entry = "zswap.enabled=0 " + options_entry

				if real_device := self.detect_encryption(root_partition):
					# TODO: We need to detect if the encrypted device is a whole disk encryption,
					#       or simply a partition encryption. Right now we assume it's a partition (and we always have)
					log(f"Identifying root partition by PART-UUID on {real_device}: '{real_device.uuid}/{real_device.part_uuid}'.", level=logging.DEBUG)

					kernel_options = f"options"

					if storage['arguments'].get('HSM'):
						# Note: lsblk UUID must be used, not PARTUUID for sd-encrypt to work
						kernel_options += f" rd.luks.name={real_device.uuid}=luksdev"
						# Note: tpm2-device and fido2-device don't play along very well:
						# https://github.com/archlinux/archinstall/pull/1196#issuecomment-1129715645
						kernel_options += f" rd.luks.options=fido2-device=auto,password-echo=no"
					else:
						kernel_options += f" cryptdevice=PARTUUID={real_device.part_uuid}:luksdev"

					entry.write(f'{kernel_options} root=/dev/mapper/luksdev {options_entry}')
				else:
					log(f"Identifying root partition by PARTUUID on {root_partition}, looking for '{root_partition.part_uuid}'.", level=logging.DEBUG)
					entry.write(f'options root=PARTUUID={root_partition.part_uuid} {options_entry}')

		self.helper_flags['bootloader'] = "systemd"

		return True

	def add_grub_bootloader(self, boot_partition :Partition, root_partition :Partition) -> bool:
		self.pacstrap('grub')  # no need?

		root_fs_type = get_mount_fs_type(root_partition.filesystem)

		if real_device := self.detect_encryption(root_partition):
			root_uuid = SysCommand(f"blkid -s UUID -o value {real_device.path}").decode().rstrip()
			_file = "/etc/default/grub"
			add_to_CMDLINE_LINUX = f"sed -i 's/GRUB_CMDLINE_LINUX=\"\"/GRUB_CMDLINE_LINUX=\"cryptdevice=UUID={root_uuid}:cryptlvm rootfstype={root_fs_type}\"/'"
			enable_CRYPTODISK = "sed -i 's/#GRUB_ENABLE_CRYPTODISK=y/GRUB_ENABLE_CRYPTODISK=y/'"

			log(f"Using UUID {root_uuid} of {real_device} as encrypted root identifier.", level=logging.INFO)
			SysCommand(f"/usr/bin/arch-chroot {self.target} {add_to_CMDLINE_LINUX} {_file}")
			SysCommand(f"/usr/bin/arch-chroot {self.target} {enable_CRYPTODISK} {_file}")
		else:
			_file = "/etc/default/grub"
			add_to_CMDLINE_LINUX = f"sed -i 's/GRUB_CMDLINE_LINUX=\"\"/GRUB_CMDLINE_LINUX=\"rootfstype={root_fs_type}\"/'"
			SysCommand(f"/usr/bin/arch-chroot {self.target} {add_to_CMDLINE_LINUX} {_file}")

		log(f"GRUB uses {boot_partition.path} as the boot partition.", level=logging.INFO)
		if has_uefi():
			self.pacstrap('efibootmgr') # TODO: Do we need? Yes, but remove from minimal_installation() instead?
			try:
				SysCommand(f'/usr/bin/arch-chroot {self.target} grub-install --debug --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB --removable', peak_output=True)
			except SysCallError:
				try:
					SysCommand(f'/usr/bin/arch-chroot {self.target} grub-install --debug --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB --removable', peak_output=True)
				except SysCallError as error:
					raise DiskError(f"Could not install GRUB to {self.target}/boot: {error}")
		else:
			try:
				SysCommand(f'/usr/bin/arch-chroot {self.target} grub-install --debug --target=i386-pc --recheck {boot_partition.parent}', peak_output=True)
			except SysCallError as error:
				raise DiskError(f"Could not install GRUB to {boot_partition.path}: {error}")

		try:
			SysCommand(f'/usr/bin/arch-chroot {self.target} grub-mkconfig -o /boot/grub/grub.cfg')
		except SysCallError as error:
			raise DiskError(f"Could not configure GRUB: {error}")

		self.helper_flags['bootloader'] = "grub"

		return True

	def add_efistub_bootloader(self, boot_partition :Partition, root_partition :Partition) -> bool:
		self.pacstrap('efibootmgr')

		if not has_uefi():
			raise HardwareIncompatibilityError
		# TODO: Ideally we would want to check if another config
		# points towards the same disk and/or partition.
		# And in which case we should do some clean up.

		root_fs_type = get_mount_fs_type(root_partition.filesystem)

		for kernel in self.kernels:
			# Setup the firmware entry

			label = f'Arch Linux ({kernel})'
			loader = f"/vmlinuz-{kernel}"

			kernel_parameters = []

			if not is_vm():
				vendor = cpu_vendor()
				if vendor == "AuthenticAMD":
					kernel_parameters.append("initrd=\\amd-ucode.img")
				elif vendor == "GenuineIntel":
					kernel_parameters.append("initrd=\\intel-ucode.img")
				else:
					self.log(f"Unknown CPU vendor '{vendor}' detected. Archinstall won't add any ucode to firmware boot entry.", level=logging.DEBUG)

			kernel_parameters.append(f"initrd=\\initramfs-{kernel}.img")

			# blkid doesn't trigger on loopback devices really well,
			# so we'll use the old manual method until we get that sorted out.
			if real_device := self.detect_encryption(root_partition):
				# TODO: We need to detect if the encrypted device is a whole disk encryption,
				#       or simply a partition encryption. Right now we assume it's a partition (and we always have)
				log(f"Identifying root partition by PART-UUID on {real_device}: '{real_device.part_uuid}'.", level=logging.DEBUG)
				kernel_parameters.append(f'cryptdevice=PARTUUID={real_device.part_uuid}:luksdev root=/dev/mapper/luksdev rw intel_pstate=no_hwp rootfstype={root_fs_type} {" ".join(self.KERNEL_PARAMS)}')
			else:
				log(f"Identifying root partition by PART-UUID on {root_partition}, looking for '{root_partition.part_uuid}'.", level=logging.DEBUG)
				kernel_parameters.append(f'root=PARTUUID={root_partition.part_uuid} rw intel_pstate=no_hwp rootfstype={root_fs_type} {" ".join(self.KERNEL_PARAMS)}')

			SysCommand(f'efibootmgr --disk {boot_partition.path[:-1]} --part {boot_partition.path[-1]} --create --label "{label}" --loader {loader} --unicode \'{" ".join(kernel_parameters)}\' --verbose')

		self.helper_flags['bootloader'] = "efistub"

		return True

	def add_bootloader(self, bootloader :str = 'systemd-bootctl') -> bool:
		"""
		Adds a bootloader to the installation instance.
		Archinstall supports one of three types:
		* systemd-bootctl
		* grub
		* efistub (beta)

		:param bootloader: Can be one of the three strings
			'systemd-bootctl', 'grub' or 'efistub' (beta)
		"""

		for plugin in plugins.values():
			if hasattr(plugin, 'on_add_bootloader'):
				# Allow plugins to override the boot-loader handling.
				# This allows for bot configuring and installing bootloaders.
				if plugin.on_add_bootloader(self):
					return True

		if type(self.target) == str:
			self.target = pathlib.Path(self.target)

		boot_partition = None
		root_partition = None
		for partition in self.partitions:
			if self.target / 'boot' in partition.mountpoints:
				boot_partition = partition
			elif self.target in partition.mountpoints:
				root_partition = partition

		if boot_partition is None or root_partition is None:
			raise ValueError(f"Could not detect root ({root_partition}) or boot ({boot_partition}) in {self.target} based on: {self.partitions}")

		self.log(f'Adding bootloader {bootloader} to {boot_partition if boot_partition else root_partition}', level=logging.INFO)

		if bootloader == 'systemd-bootctl':
			self.add_systemd_bootloader(boot_partition, root_partition)
		elif bootloader == "grub-install":
			self.add_grub_bootloader(boot_partition, root_partition)
		elif bootloader == 'efistub':
			self.add_efistub_bootloader(boot_partition, root_partition)
		else:
			raise RequirementError(f"Unknown (or not yet implemented) bootloader requested: {bootloader}")

		return True

	def add_additional_packages(self, *packages :str) -> bool:
		return self.pacstrap(*packages)

	def install_profile(self, profile :str) -> ModuleType:
		"""
		Installs a archinstall profile script (.py file).
		This profile can be either local, remote or part of the library.

		:param profile: Can be a local path or a remote path (URL)
		:return: Returns the imported script as a module, this way
			you can access any remaining functions exposed by the profile.
		:rtype: module
		"""
		storage['installation_session'] = self

		if type(profile) == str:
			profile = Profile(self, profile)

		self.log(f'Installing archinstall profile {profile}', level=logging.INFO)
		return profile.install()

	def enable_sudo(self, entity: str, group :bool = False):
		self.log(f'Enabling sudo permissions for {entity}.', level=logging.INFO)

		sudoers_dir = f"{self.target}/etc/sudoers.d"

		# Creates directory if not exists
		if not (sudoers_path := pathlib.Path(sudoers_dir)).exists():
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
		os.chmod(pathlib.Path(rule_file_name), 0o440)

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
			self.log(f'Creating user {user}', level=logging.INFO)
			if not (output := SysCommand(f'/usr/bin/arch-chroot {self.target} useradd -m -G wheel {user}')).exit_code == 0:
				raise SystemError(f"Could not create user inside installation: {output}")

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
		self.log(f'Setting password for {user}', level=logging.INFO)

		if user == 'root':
			# This means the root account isn't locked/disabled with * in /etc/passwd
			self.helper_flags['user'] = True

		combo = f'{user}:{password}'
		echo = shlex.join(['echo', combo])
		sh = shlex.join(['sh', '-c', echo])

		result = SysCommand(f"/usr/bin/arch-chroot {self.target} " + sh[:-1] + " | chpasswd'")
		return result.exit_code == 0

	def user_set_shell(self, user :str, shell :str) -> bool:
		self.log(f'Setting shell for {user} to {shell}', level=logging.INFO)

		return SysCommand(f"/usr/bin/arch-chroot {self.target} sh -c \"chsh -s {shell} {user}\"").exit_code == 0

	def chown(self, owner :str, path :str, options :List[str] = []) -> bool:
		cleaned_path = path.replace('\'', '\\\'')
		return SysCommand(f"/usr/bin/arch-chroot {self.target} sh -c 'chown {' '.join(options)} {owner} {cleaned_path}'").exit_code == 0

	def create_file(self, filename :str, owner :Optional[str] = None) -> InstallationFile:
		return InstallationFile(self, filename, owner)

	def set_keyboard_language(self, language: str) -> bool:
		log(f"Setting keyboard language to {language}", level=logging.INFO)
		if len(language.strip()):
			if not verify_keyboard_layout(language):
				self.log(f"Invalid keyboard language specified: {language}", fg="red", level=logging.ERROR)
				return False

			# In accordance with https://github.com/archlinux/archinstall/issues/107#issuecomment-841701968
			# Setting an empty keymap first, allows the subsequent call to set layout for both console and x11.
			from .systemd import Boot
			with Boot(self) as session:
				os.system('/usr/bin/systemd-run --machine=archinstall --pty localectl set-keymap ""')

				if (output := session.SysCommand(["localectl", "set-keymap", language])).exit_code != 0:
					raise ServiceException(f"Unable to set locale '{language}' for console: {output}")

				self.log(f"Keyboard language for this installation is now set to: {language}")
		else:
			self.log('Keyboard language was not changed from default (no language specified).', fg="yellow", level=logging.INFO)

		return True

	def set_x11_keyboard_language(self, language: str) -> bool:
		log(f"Setting x11 keyboard language to {language}", level=logging.INFO)
		"""
		A fallback function to set x11 layout specifically and separately from console layout.
		This isn't strictly necessary since .set_keyboard_language() does this as well.
		"""
		if len(language.strip()):
			if not verify_x11_keyboard_layout(language):
				self.log(f"Invalid x11-keyboard language specified: {language}", fg="red", level=logging.ERROR)
				return False

			from .systemd import Boot
			with Boot(self) as session:
				session.SysCommand(["localectl", "set-x11-keymap", '""'])

				if (output := session.SysCommand(["localectl", "set-x11-keymap", language])).exit_code != 0:
					raise ServiceException(f"Unable to set locale '{language}' for X11: {output}")
		else:
			self.log(f'X11-Keyboard language was not changed from default (no language specified).', fg="yellow", level=logging.INFO)

		return True
