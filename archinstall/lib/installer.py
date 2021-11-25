import time
from typing import Union
import logging
import os
import shutil
import shlex
import pathlib
import subprocess
import glob
from .disk import get_partitions_in_use, Partition
from .general import SysCommand, generate_password
from .hardware import has_uefi, is_vm, cpu_vendor
from .locale_helpers import verify_keyboard_layout, verify_x11_keyboard_layout
from .disk.helpers import get_mount_info
from .mirrors import use_mirrors
from .plugins import plugins
from .storage import storage
# from .user_interaction import *
from .output import log
from .profiles import Profile
from .disk.btrfs import create_subvolume, mount_subvolume
from .disk.partition import get_mount_fs_type
from .exceptions import DiskError, ServiceException, RequirementError, HardwareIncompatibilityError

# Any package that the Installer() is responsible for (optional and the default ones)
__packages__ = ["base", "base-devel", "linux-firmware", "linux", "linux-lts", "linux-zen", "linux-hardened"]

# Additional packages that are installed if the user is running the Live ISO with accessibility tools enabled
__accessibility_packages__ = ["brltty", "espeakup", "alsa-utils"]


class InstallationFile:
	def __init__(self, installation, filename, owner, mode="w"):
		self.installation = installation
		self.filename = filename
		self.owner = owner
		self.mode = mode
		self.fh = None

	def __enter__(self):
		self.fh = open(self.filename, self.mode)
		return self

	def __exit__(self, *args):
		self.fh.close()
		self.installation.chown(self.owner, self.filename)

	def write(self, data: Union[str, bytes]):
		return self.fh.write(data)

	def read(self, *args):
		return self.fh.read(*args)

	def poll(self, *args):
		return self.fh.poll(*args)


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

	def __init__(self, target, *, base_packages=None, kernels=None):
		if base_packages is None:
			base_packages = __packages__[:3]
		if kernels is None:
			kernels = ['linux']
		self.kernels = kernels
		self.target = target
		self.init_time = time.strftime('%Y-%m-%d_%H-%M-%S')
		self.milliseconds = int(str(time.time()).split('.')[1])

		self.helper_flags = {
			'base': False,
			'bootloader': False
		}

		self.base_packages = base_packages.split(' ') if type(base_packages) is str else base_packages
		for kernel in kernels:
			self.base_packages.append(kernel)

		# If using accessibility tools in the live environment, append those to the packages list
		if accessibility_tools_in_use():
			self.base_packages.extend(__accessibility_packages__)

		self.post_base_install = []

		storage['session'] = self

		self.MODULES = []
		self.BINARIES = []
		self.FILES = []
		self.HOOKS = ["base", "udev", "autodetect", "keyboard", "keymap", "modconf", "block", "filesystems", "fsck"]
		self.KERNEL_PARAMS = []

	def log(self, *args, level=logging.DEBUG, **kwargs):
		"""
		installer.log() wraps output.log() mainly to set a default log-level for this install session.
		Any manual override can be done per log() call.
		"""
		log(*args, level=level, **kwargs)

	def __enter__(self, *args, **kwargs):
		return self

	def __exit__(self, *args, **kwargs):
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if len(args) >= 2 and args[1]:
			self.log(args[1], level=logging.ERROR, fg='red')

			self.sync_log_to_install_medium()

			# We avoid printing /mnt/<log path> because that might confuse people if they note it down
			# and then reboot, and a identical log file will be found in the ISO medium anyway.
			print(f"[!] A log file has been created here: {os.path.join(storage['LOG_PATH'], storage['LOG_FILE'])}")
			print("    Please submit this issue (and file) to https://github.com/archlinux/archinstall/issues")
			raise args[1]

		self.genfstab()

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
	def partitions(self):
		return get_partitions_in_use(self.target)

	def sync_log_to_install_medium(self):
		# Copy over the install log (if there is one) to the install medium if
		# at least the base has been strapped in, otherwise we won't have a filesystem/structure to copy to.
		if self.helper_flags.get('base-strapped', False) is True:
			if filename := storage.get('LOG_FILE', None):
				absolute_logfile = os.path.join(storage.get('LOG_PATH', './'), filename)

				if not os.path.isdir(f"{self.target}/{os.path.dirname(absolute_logfile)}"):
					os.makedirs(f"{self.target}/{os.path.dirname(absolute_logfile)}")

				shutil.copy2(absolute_logfile, f"{self.target}/{absolute_logfile}")

		return True

	def mount_ordered_layout(self, layouts: dict):
		from .luks import luks2

		mountpoints = {}
		for blockdevice in layouts:
			for partition in layouts[blockdevice]['partitions']:
				mountpoints[partition['mountpoint']] = partition

		for mountpoint in sorted(mountpoints.keys()):
			partition = mountpoints[mountpoint]

			if partition.get('encrypted', False):
				loopdev = f"{storage.get('ENC_IDENTIFIER', 'ai')}{pathlib.Path(partition['mountpoint']).name}loop"
				if not (password := partition.get('!password', None)):
					raise RequirementError(f"Missing mountpoint {mountpoint} encryption password in layout: {partition}")

				with (luks_handle := luks2(partition['device_instance'], loopdev, password, auto_unmount=False)) as unlocked_device:
					if partition.get('generate-encryption-key-file'):
						if not (cryptkey_dir := pathlib.Path(f"{self.target}/etc/cryptsetup-keys.d")).exists():
							cryptkey_dir.mkdir(parents=True)

						# Once we store the key as ../xyzloop.key systemd-cryptsetup can automatically load this key
						# if we name the device to "xyzloop".
						encryption_key_path = f"/etc/cryptsetup-keys.d/{pathlib.Path(partition['mountpoint']).name}loop.key"
						with open(f"{self.target}{encryption_key_path}", "w") as keyfile:
							keyfile.write(generate_password(length=512))

						os.chmod(f"{self.target}{encryption_key_path}", 0o400)

						luks_handle.add_key(pathlib.Path(f"{self.target}{encryption_key_path}"), password=password)
						luks_handle.crypttab(self, encryption_key_path, options=["luks", "key-slot=1"])

					log(f"Mounting {mountpoint} to {self.target}{mountpoint} using {unlocked_device}", level=logging.INFO)
					unlocked_device.mount(f"{self.target}{mountpoint}")

			else:
				log(f"Mounting {mountpoint} to {self.target}{mountpoint} using {partition['device_instance']}", level=logging.INFO)
				partition['device_instance'].mount(f"{self.target}{mountpoint}")

			time.sleep(1)
			try:
				get_mount_info(f"{self.target}{mountpoint}", traverse=False)
			except DiskError:
				raise DiskError(f"Target {self.target}{mountpoint} never got mounted properly (unable to get mount information using findmnt).")

			if (subvolumes := partition.get('btrfs', {}).get('subvolumes', {})):
				for name, location in subvolumes.items():
					create_subvolume(self, location)
					mount_subvolume(self, location)

	def mount(self, partition, mountpoint, create_mountpoint=True):
		if create_mountpoint and not os.path.isdir(f'{self.target}{mountpoint}'):
			os.makedirs(f'{self.target}{mountpoint}')

		partition.mount(f'{self.target}{mountpoint}')

	def post_install_check(self, *args, **kwargs):
		return [step for step, flag in self.helper_flags.items() if flag is False]

	def pacstrap(self, *packages, **kwargs):
		if type(packages[0]) in (list, tuple):
			packages = packages[0]

		for plugin in plugins.values():
			if hasattr(plugin, 'on_pacstrap'):
				if (result := plugin.on_pacstrap(packages)):
					packages = result

		self.log(f'Installing packages: {packages}', level=logging.INFO)

		if (sync_mirrors := SysCommand('/usr/bin/pacman -Syy')).exit_code == 0:
			if (pacstrap := SysCommand(f'/usr/bin/pacstrap {self.target} {" ".join(packages)} --noconfirm', peak_output=True)).exit_code == 0:
				return True
			else:
				self.log(f'Could not strap in packages: {pacstrap}', level=logging.ERROR, fg="red")
				self.log(f'Could not strap in packages: {pacstrap.exit_code}', level=logging.ERROR, fg="red")
				raise RequirementError("Pacstrap failed. See /var/log/archinstall/install.log or above message for error details.")
		else:
			self.log(f'Could not sync mirrors: {sync_mirrors.exit_code}', level=logging.INFO)

	def set_mirrors(self, mirrors):
		for plugin in plugins.values():
			if hasattr(plugin, 'on_mirrors'):
				if result := plugin.on_mirrors(mirrors):
					mirrors = result

		return use_mirrors(mirrors, destination=f'{self.target}/etc/pacman.d/mirrorlist')

	def genfstab(self, flags='-pU'):
		self.log(f"Updating {self.target}/etc/fstab", level=logging.INFO)

		with open(f"{self.target}/etc/fstab", 'a') as fstab_fh:
			fstab_fh.write((fstab := SysCommand(f'/usr/bin/genfstab {flags} {self.target}')).decode())

		if not os.path.isfile(f'{self.target}/etc/fstab'):
			raise RequirementError(f'Could not generate fstab, strapping in packages most likely failed (disk out of space?)\n{fstab}')

		for plugin in plugins.values():
			if hasattr(plugin, 'on_genfstab'):
				plugin.on_genfstab(self)

		return True

	def set_hostname(self, hostname: str, *args, **kwargs):
		with open(f'{self.target}/etc/hostname', 'w') as fh:
			fh.write(hostname + '\n')

	def set_locale(self, locale, encoding='UTF-8', *args, **kwargs):
		if not len(locale):
			return True

		with open(f'{self.target}/etc/locale.gen', 'a') as fh:
			fh.write(f'{locale}.{encoding} {encoding}\n')
		with open(f'{self.target}/etc/locale.conf', 'w') as fh:
			fh.write(f'LANG={locale}.{encoding}\n')

		return True if SysCommand(f'/usr/bin/arch-chroot {self.target} locale-gen').exit_code == 0 else False

	def set_timezone(self, zone, *args, **kwargs):
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

	def activate_ntp(self):
		log(f"activate_ntp() is deprecated, use activate_time_syncronization()", fg="yellow", level=logging.INFO)
		self.activate_time_syncronization()

	def activate_time_syncronization(self):
		self.log('Activating systemd-timesyncd for time synchronization using Arch Linux and ntp.org NTP servers.', level=logging.INFO)
		self.enable_service('systemd-timesyncd')

		with open(f"{self.target}/etc/systemd/timesyncd.conf", "w") as fh:
			fh.write("[Time]\n")
			fh.write("NTP=0.arch.pool.ntp.org 1.arch.pool.ntp.org 2.arch.pool.ntp.org 3.arch.pool.ntp.org\n")
			fh.write("FallbackNTP=0.pool.ntp.org 1.pool.ntp.org 0.fr.pool.ntp.org\n")

		from .systemd import Boot
		with Boot(self) as session:
			session.SysCommand(["timedatectl", "set-ntp", 'true'])

	def enable_espeakup(self):
		self.log('Enabling espeakup.service for speech synthesis (accessibility).', level=logging.INFO)
		self.enable_service('espeakup')

	def enable_service(self, *services):
		for service in services:
			self.log(f'Enabling service {service}', level=logging.INFO)
			if (output := self.arch_chroot(f'systemctl enable {service}')).exit_code != 0:
				raise ServiceException(f"Unable to start service {service}: {output}")

			for plugin in plugins.values():
				if hasattr(plugin, 'on_service'):
					plugin.on_service(service)

	def run_command(self, cmd, *args, **kwargs):
		return SysCommand(f'/usr/bin/arch-chroot {self.target} {cmd}')

	def arch_chroot(self, cmd, run_as=None):
		if run_as:
			cmd = f"su - {run_as} -c {shlex.quote(cmd)}"

		return self.run_command(cmd)

	def drop_to_shell(self):
		subprocess.check_call(f"/usr/bin/arch-chroot {self.target}", shell=True)

	def configure_nic(self, nic, dhcp=True, ip=None, gateway=None, dns=None, *args, **kwargs):
		from .systemd import Networkd

		if dhcp:
			conf = Networkd(Match={"Name": nic}, Network={"DHCP": "yes"})
		else:
			assert ip

			network = {"Address": ip}
			if gateway:
				network["Gateway"] = gateway
			if dns:
				assert type(dns) == list
				network["DNS"] = dns

			conf = Networkd(Match={"Name": nic}, Network=network)

		for plugin in plugins.values():
			if hasattr(plugin, 'on_configure_nic'):
				if (new_conf := plugin.on_configure_nic(nic, dhcp, ip, gateway, dns)):
					conf = new_conf

		with open(f"{self.target}/etc/systemd/network/10-{nic}.network", "a") as netconf:
			netconf.write(str(conf))

	def copy_iso_network_config(self, enable_services=False):
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
						def post_install_enable_iwd_service(*args, **kwargs):
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

					def post_install_enable_networkd_resolved(*args, **kwargs):
						self.enable_service('systemd-networkd', 'systemd-resolved')

					self.post_base_install.append(post_install_enable_networkd_resolved)
				# Otherwise, we can go ahead and enable the services
				else:
					self.enable_service('systemd-networkd', 'systemd-resolved')

		return True

	def detect_encryption(self, partition):
		part = Partition(partition.parent, None, autodetect_filesystem=True)
		if partition.encrypted:
			return partition
		elif partition.parent not in partition.path and part.filesystem == 'crypto_LUKS':
			return part

		return False

	def mkinitcpio(self, *flags):
		for plugin in plugins.values():
			if hasattr(plugin, 'on_mkinitcpio'):
				# Allow plugins to override the usage of mkinitcpio altogether.
				if plugin.on_mkinitcpio(self):
					return True

		with open(f'{self.target}/etc/mkinitcpio.conf', 'w') as mkinit:
			mkinit.write(f"MODULES=({' '.join(self.MODULES)})\n")
			mkinit.write(f"BINARIES=({' '.join(self.BINARIES)})\n")
			mkinit.write(f"FILES=({' '.join(self.FILES)})\n")
			mkinit.write(f"HOOKS=({' '.join(self.HOOKS)})\n")
		SysCommand(f'/usr/bin/arch-chroot {self.target} mkinitcpio {" ".join(flags)}')

	def minimal_installation(self):
		# Add necessary packages if encrypting the drive
		# (encrypted partitions default to btrfs for now, so we need btrfs-progs)
		# TODO: Perhaps this should be living in the function which dictates
		#       the partitioning. Leaving here for now.

		for partition in self.partitions:
			if partition.filesystem == 'btrfs':
				# if partition.encrypted:
				self.base_packages.append('btrfs-progs')
			if partition.filesystem == 'xfs':
				self.base_packages.append('xfsprogs')
			if partition.filesystem == 'f2fs':
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

		self.pacstrap(self.base_packages)
		self.helper_flags['base-strapped'] = True

		# TODO: Support locale and timezone
		# os.remove(f'{self.target}/etc/localtime')
		# sys_command(f'/usr/bin/arch-chroot {self.target} ln -s /usr/share/zoneinfo/{localtime} /etc/localtime')
		# sys_command('/usr/bin/arch-chroot /mnt hwclock --hctosys --localtime')
		self.set_hostname('archinstall')
		self.set_locale('en_US')

		# TODO: Use python functions for this
		SysCommand(f'/usr/bin/arch-chroot {self.target} chmod 700 /root')

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

	def setup_swap(self, kind='zram'):
		if kind == 'zram':
			self.log(f"Setting up swap on zram")
			self.pacstrap('zram-generator')

			# We could use the default example below, but maybe not the best idea: https://github.com/archlinux/archinstall/pull/678#issuecomment-962124813
			# zram_example_location = '/usr/share/doc/zram-generator/zram-generator.conf.example'
			# shutil.copy2(f"{self.target}{zram_example_location}", f"{self.target}/usr/lib/systemd/zram-generator.conf")
			with open(f"{self.target}/etc/systemd/zram-generator.conf", "w") as zram_conf:
				zram_conf.write("[zram0]\n")

			if self.enable_service('systemd-zram-setup@zram0.service'):
				return True
		else:
			raise ValueError(f"Archinstall currently only supports setting up swap on zram")

	def add_bootloader(self, bootloader='systemd-bootctl'):
		for plugin in plugins.values():
			if hasattr(plugin, 'on_add_bootloader'):
				# Allow plugins to override the boot-loader handling.
				# This allows for bot configuring and installing bootloaders.
				if plugin.on_add_bootloader(self):
					return True

		boot_partition = None
		root_partition = None
		root_partition_fs = None
		for partition in self.partitions:
			if partition.mountpoint == self.target + '/boot':
				boot_partition = partition
			elif partition.mountpoint == self.target:
				root_partition = partition
				root_partition_fs = partition.filesystem
				root_fs_type = get_mount_fs_type(root_partition_fs)

		if boot_partition is None and root_partition is None:
			raise ValueError(f"Could not detect root (/) or boot (/boot) in {self.target} based on: {self.partitions}")

		self.log(f'Adding bootloader {bootloader} to {boot_partition if boot_partition else root_partition}', level=logging.INFO)

		if bootloader == 'systemd-bootctl':
			self.pacstrap('efibootmgr')

			if not has_uefi():
				raise HardwareIncompatibilityError
			# TODO: Ideally we would want to check if another config
			# points towards the same disk and/or partition.
			# And in which case we should do some clean up.

			# Install the boot loader
			if SysCommand(f'/usr/bin/arch-chroot {self.target} bootctl --path=/boot install').exit_code != 0:
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
					"timeout 5"
				]

			with open(f'{self.target}/boot/loader/loader.conf', 'w') as loader:
				for line in loader_data:
					if line[:8] == 'default ':
						loader.write(f'default {self.init_time}_{self.kernels[0]}\n')
					elif line[:8] == '#timeout' and 'timeout 5' not in loader_data:
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
							self.log("unknow cpu vendor, not adding ucode to systemd-boot config")
					entry.write(f"initrd /initramfs-{kernel}.img\n")
					# blkid doesn't trigger on loopback devices really well,
					# so we'll use the old manual method until we get that sorted out.

					if real_device := self.detect_encryption(root_partition):
						# TODO: We need to detect if the encrypted device is a whole disk encryption,
						#       or simply a partition encryption. Right now we assume it's a partition (and we always have)
						log(f"Identifying root partition by PART-UUID on {real_device}: '{real_device.uuid}'.", level=logging.DEBUG)
						entry.write(f'options cryptdevice=PARTUUID={real_device.uuid}:luksdev root=/dev/mapper/luksdev rw intel_pstate=no_hwp rootfstype={root_fs_type} {" ".join(self.KERNEL_PARAMS)}\n')
					else:
						log(f"Identifying root partition by PART-UUID on {root_partition}, looking for '{root_partition.uuid}'.", level=logging.DEBUG)
						entry.write(f'options root=PARTUUID={root_partition.uuid} rw intel_pstate=no_hwp rootfstype={root_fs_type} {" ".join(self.KERNEL_PARAMS)}\n')

					self.helper_flags['bootloader'] = bootloader

		elif bootloader == "grub-install":
			self.pacstrap('grub')  # no need?

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
				if not (handle := SysCommand(f'/usr/bin/arch-chroot {self.target} grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB')).exit_code == 0:
					raise DiskError(f"Could not install GRUB to {self.target}/boot: {handle}")
			else:
				if not (handle := SysCommand(f'/usr/bin/arch-chroot {self.target} grub-install --target=i386-pc --recheck {boot_partition.parent}')).exit_code == 0:
					raise DiskError(f"Could not install GRUB to {boot_partition.path}: {handle}")

			if not (handle := SysCommand(f'/usr/bin/arch-chroot {self.target} grub-mkconfig -o /boot/grub/grub.cfg')).exit_code == 0:
				raise DiskError(f"Could not configure GRUB: {handle}")

			self.helper_flags['bootloader'] = True
		elif bootloader == 'efistub':
			self.pacstrap('efibootmgr')

			if not has_uefi():
				raise HardwareIncompatibilityError
			# TODO: Ideally we would want to check if another config
			# points towards the same disk and/or partition.
			# And in which case we should do some clean up.

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
						self.log("unknow cpu vendor, not adding ucode to firmware boot entry")

				kernel_parameters.append(f"initrd=\\initramfs-{kernel}.img")

				# blkid doesn't trigger on loopback devices really well,
				# so we'll use the old manual method until we get that sorted out.
				if real_device := self.detect_encryption(root_partition):
					# TODO: We need to detect if the encrypted device is a whole disk encryption,
					#       or simply a partition encryption. Right now we assume it's a partition (and we always have)
					log(f"Identifying root partition by PART-UUID on {real_device}: '{real_device.uuid}'.", level=logging.DEBUG)
					kernel_parameters.append(f'cryptdevice=PARTUUID={real_device.uuid}:luksdev root=/dev/mapper/luksdev rw intel_pstate=no_hwp rootfstype={root_fs_type} {" ".join(self.KERNEL_PARAMS)}')
				else:
					log(f"Identifying root partition by PART-UUID on {root_partition}, looking for '{root_partition.uuid}'.", level=logging.DEBUG)
					kernel_parameters.append(f'root=PARTUUID={root_partition.uuid} rw intel_pstate=no_hwp rootfstype={root_fs_type} {" ".join(self.KERNEL_PARAMS)}')

				SysCommand(f'efibootmgr --disk {boot_partition.path[:-1]} --part {boot_partition.path[-1]} --create --label "{label}" --loader {loader} --unicode \'{" ".join(kernel_parameters)}\' --verbose')

			self.helper_flags['bootloader'] = bootloader
		else:
			raise RequirementError(f"Unknown (or not yet implemented) bootloader requested: {bootloader}")

		return True

	def add_additional_packages(self, *packages):
		return self.pacstrap(*packages)

	def install_profile(self, profile):
		storage['installation_session'] = self

		if type(profile) == str:
			profile = Profile(self, profile)

		self.log(f'Installing network profile {profile}', level=logging.INFO)
		return profile.install()

	def enable_sudo(self, entity: str, group=False):
		self.log(f'Enabling sudo permissions for {entity}.', level=logging.INFO)
		with open(f'{self.target}/etc/sudoers', 'a') as sudoers:
			sudoers.write(f'{"%" if group else ""}{entity} ALL=(ALL) ALL\n')
		return True

	def user_create(self, user: str, password=None, groups=None, sudo=False):
		if groups is None:
			groups = []

		# This plugin hook allows for the plugin to handle the creation of the user.
		# Password and Group management is still handled by user_create()
		handled_by_plugin = False
		for plugin in plugins.values():
			if hasattr(plugin, 'on_user_create'):
				if result := plugin.on_user_create(user):
					handled_by_plugin = result

		if not handled_by_plugin:
			self.log(f'Creating user {user}', level=logging.INFO)
			SysCommand(f'/usr/bin/arch-chroot {self.target} useradd -m -G wheel {user}')

		if password:
			self.user_set_pw(user, password)

		if groups:
			for group in groups:
				SysCommand(f'/usr/bin/arch-chroot {self.target} gpasswd -a {user} {group}')

		if sudo and self.enable_sudo(user):
			self.helper_flags['user'] = True

	def user_set_pw(self, user, password):
		self.log(f'Setting password for {user}', level=logging.INFO)

		if user == 'root':
			# This means the root account isn't locked/disabled with * in /etc/passwd
			self.helper_flags['user'] = True

		SysCommand(f"/usr/bin/arch-chroot {self.target} sh -c \"echo '{user}:{password}' | chpasswd\"")

	def user_set_shell(self, user, shell):
		self.log(f'Setting shell for {user} to {shell}', level=logging.INFO)

		SysCommand(f"/usr/bin/arch-chroot {self.target} sh -c \"chsh -s {shell} {user}\"")

	def chown(self, owner, path, options=[]):
		return SysCommand(f"/usr/bin/arch-chroot {self.target} sh -c 'chown {' '.join(options)} {owner} {path}")

	def create_file(self, filename, owner=None):
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
				session.SysCommand(["localectl", "set-keymap", '""'])

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
