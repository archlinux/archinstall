import os, stat, time, shutil, pathlib

from .exceptions import *
from .disk import *
from .general import *
from .user_interaction import *
from .profiles import Profile
from .mirrors import *
from .systemd import Networkd
from .output import log, LOG_LEVELS
from .storage import storage

class Installer():
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
	def __init__(self, partition, boot_partition, *, base_packages='base base-devel linux linux-firmware efibootmgr nano', profile=None, mountpoint='/mnt', hostname='ArchInstalled', logdir=None, logfile=None):
		self.profile = profile
		self.hostname = hostname
		self.mountpoint = mountpoint
		self.init_time = time.strftime('%Y-%m-%d_%H-%M-%S')
		self.milliseconds = int(str(time.time()).split('.')[1])

		if logdir:
			storage['LOG_PATH'] = logdir
		if logfile:
			storage['LOG_FILE'] = logfile

		self.helper_flags = {
			'bootloader' : False,
			'base' : False,
			'user' : False # Root counts as a user, if additional users are skipped.
		}

		self.base_packages = base_packages.split(' ')
		self.post_base_install = []
		storage['session'] = self

		self.partition = partition
		self.boot_partition = boot_partition

	def log(self, *args, level=LOG_LEVELS.Debug, **kwargs):
		"""
		installer.log() wraps output.log() mainly to set a default log-level for this install session.
		Any manual override can be done per log() call.
		"""
		log(*args, level=level, **kwargs)

	def __enter__(self, *args, **kwargs):
		self.partition.mount(self.mountpoint)
		os.makedirs(f'{self.mountpoint}/boot', exist_ok=True)
		self.boot_partition.mount(f'{self.mountpoint}/boot')
		return self

	def __exit__(self, *args, **kwargs):
		# b''.join(sys_command(f'sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if len(args) >= 2 and args[1]:
			#self.log(self.trace_log.decode('UTF-8'), level=LOG_LEVELS.Debug)
			self.log(args[1], level=LOG_LEVELS.Error, fg='red')

			self.sync_log_to_install_medium()

			# We avoid printing /mnt/<log path> because that might confuse people if they note it down
			# and then reboot, and a identical log file will be found in the ISO medium anyway.
			print(f"[!] A log file has been created here: {os.path.join(storage['LOG_PATH'], storage['LOG_FILE'])}")
			print(f"    Please submit this issue (and file) to https://github.com/archlinux/archinstall/issues")
			raise args[1]

		self.genfstab()

		if not (missing_steps := self.post_install_check()):
			self.log('Installation completed without any errors. You may now reboot.', bg='black', fg='green', level=LOG_LEVELS.Info)
			self.sync_log_to_install_medium()
			return True
		else:
			self.log('Some required steps were not successfully installed/configured before leaving the installer:', bg='black', fg='red', level=LOG_LEVELS.Warning)
			for step in missing_steps:
				self.log(f' - {step}', bg='black', fg='red', level=LOG_LEVELS.Warning)
            
			self.log(f"Detailed error logs can be found at: {storage['LOG_PATH']}", level=LOG_LEVELS.Warning)
			self.log(f"Submit this zip file as an issue to https://github.com/archlinux/archinstall/issues", level=LOG_LEVELS.Warning)
               
			self.sync_log_to_install_medium()
			return False

	def sync_log_to_install_medium(self):
		# Copy over the install log (if there is one) to the install medium if
		# at least the base has been strapped in, otherwise we won't have a filesystem/structure to copy to.
		if self.helper_flags.get('base-strapped', False) is True:
			if (filename := storage.get('LOG_FILE', None)):
				absolute_logfile = os.path.join(storage.get('LOG_PATH', './'), filename)

				if not os.path.isdir(f"{self.mountpoint}/{os.path.dirname(absolute_logfile)}"):
					os.makedirs(f"{self.mountpoint}/{os.path.dirname(absolute_logfile)}")
				
				shutil.copy2(absolute_logfile, f"{self.mountpoint}/{absolute_logfile}")

		return True

	def mount(self, partition, mountpoint, create_mountpoint=True):
		if create_mountpoint and not os.path.isdir(f'{self.mountpoint}{mountpoint}'):
			os.makedirs(f'{self.mountpoint}{mountpoint}')
			
		partition.mount(f'{self.mountpoint}{mountpoint}')

	def post_install_check(self, *args, **kwargs):
		return [step for step, flag in self.helper_flags.items() if flag is False]

	def pacstrap(self, *packages, **kwargs):
		if type(packages[0]) in (list, tuple): packages = packages[0]
		self.log(f'Installing packages: {packages}', level=LOG_LEVELS.Info)

		if (sync_mirrors := sys_command('/usr/bin/pacman -Syy')).exit_code == 0:
			if (pacstrap := sys_command(f'/usr/bin/pacstrap {self.mountpoint} {" ".join(packages)}', **kwargs)).exit_code == 0:
				return True
			else:
				self.log(f'Could not strap in packages: {pacstrap.exit_code}', level=LOG_LEVELS.Info)
		else:
			self.log(f'Could not sync mirrors: {sync_mirrors.exit_code}', level=LOG_LEVELS.Info)

	def set_mirrors(self, mirrors):
		return use_mirrors(mirrors, destination=f'{self.mountpoint}/etc/pacman.d/mirrorlist')

	def genfstab(self, flags='-pU'):
		self.log(f"Updating {self.mountpoint}/etc/fstab", level=LOG_LEVELS.Info)
		
		fstab = sys_command(f'/usr/bin/genfstab {flags} {self.mountpoint}').trace_log
		with open(f"{self.mountpoint}/etc/fstab", 'ab',newline='\n') as fstab_fh:
			fstab_fh.write(fstab)

		if not os.path.isfile(f'{self.mountpoint}/etc/fstab'):
			raise RequirementError(f'Could not generate fstab, strapping in packages most likely failed (disk out of space?)\n{b"".join(fstab)}')
		
		return True

	def set_hostname(self, hostname=None, *args, **kwargs):
		if not hostname: hostname = self.hostname
		with open(f'{self.mountpoint}/etc/hostname', 'w') as fh:
			fh.write(self.hostname + '\n')

	def set_locale(self, locale, encoding='UTF-8', *args, **kwargs):
		if not len(locale): return True

		with open(f'{self.mountpoint}/etc/locale.gen', 'a') as fh:
			fh.write(f'{locale}.{encoding} {encoding}\n')
		with open(f'{self.mountpoint}/etc/locale.conf', 'w') as fh:
			fh.write(f'LANG={locale}.{encoding}\n')

		return True if sys_command(f'/usr/bin/arch-chroot {self.mountpoint} locale-gen').exit_code == 0 else False

	def set_timezone(self, zone, *args, **kwargs):
		if not zone: return True
		if not len(zone): return True # Redundant

		if (pathlib.Path("/usr")/"share"/"zoneinfo"/zone).exists():
			(pathlib.Path(self.mountpoint)/"etc"/"localtime").unlink(missing_ok=True)
			sys_command(f'/usr/bin/arch-chroot {self.mountpoint} ln -s /usr/share/zoneinfo/{zone} /etc/localtime')
			return True
		else:
			self.log(
				f"Time zone {zone} does not exist, continuing with system default.",
				level=LOG_LEVELS.Warning,
				fg='red'
			)

	def activate_ntp(self):
		self.log(f'Installing and activating NTP.', level=LOG_LEVELS.Info)
		if self.pacstrap('ntp'):
			if self.enable_service('ntpd'):
				return True

	def enable_service(self, service):
		self.log(f'Enabling service {service}', level=LOG_LEVELS.Info)
		return self.arch_chroot(f'systemctl enable {service}').exit_code == 0

	def run_command(self, cmd, *args, **kwargs):
		return sys_command(f'/usr/bin/arch-chroot {self.mountpoint} {cmd}')

	def arch_chroot(self, cmd, *args, **kwargs):
		return self.run_command(cmd)

	def configure_nic(self, nic, dhcp=True, ip=None, gateway=None, dns=None, *args, **kwargs):
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
		
		with open(f"{self.mountpoint}/etc/systemd/network/10-{nic}.network", "a") as netconf:
			netconf.write(str(conf))

	def copy_ISO_network_config(self, enable_services=False):
		# Copy (if any) iwd password and config files
		if os.path.isdir('/var/lib/iwd/'):
			if (psk_files := glob.glob('/var/lib/iwd/*.psk')):
				if not os.path.isdir(f"{self.mountpoint}/var/lib/iwd"):
					os.makedirs(f"{self.mountpoint}/var/lib/iwd")

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
					shutil.copy2(psk, f"{self.mountpoint}/var/lib/iwd/{os.path.basename(psk)}")

		# Copy (if any) systemd-networkd config files
		if (netconfigurations := glob.glob('/etc/systemd/network/*')):
			if not os.path.isdir(f"{self.mountpoint}/etc/systemd/network/"):
				os.makedirs(f"{self.mountpoint}/etc/systemd/network/")

			for netconf_file in netconfigurations:
				shutil.copy2(netconf_file, f"{self.mountpoint}/etc/systemd/network/{os.path.basename(netconf_file)}")

			if enable_services:
				# If we haven't installed the base yet (function called pre-maturely)
				if self.helper_flags.get('base', False) is False:
					def post_install_enable_networkd_resolved(*args, **kwargs):
						self.enable_service('systemd-networkd')
						self.enable_service('systemd-resolved')

					self.post_base_install.append(post_install_enable_networkd_resolved)
				# Otherwise, we can go ahead and enable the services
				else:
					self.enable_service('systemd-networkd')
					self.enable_service('systemd-resolved')

		return True

	def minimal_installation(self):
		## Add necessary packages if encrypting the drive
		## (encrypted partitions default to btrfs for now, so we need btrfs-progs)
		## TODO: Perhaps this should be living in the function which dictates
		##       the partitioning. Leaving here for now.
		if self.partition.filesystem == 'btrfs':
		#if self.partition.encrypted:
			self.base_packages.append('btrfs-progs')
		if self.partition.filesystem == 'xfs':
			self.base_packages.append('xfsprogs')
		if self.partition.filesystem == 'f2fs':
			self.base_packages.append('f2fs-tools')
		self.pacstrap(self.base_packages)
		self.helper_flags['base-strapped'] = True
		#self.genfstab()

		with open(f"{self.mountpoint}/etc/fstab", "a") as fstab:
			fstab.write(
				"\ntmpfs /tmp tmpfs defaults,noatime,mode=1777 0 0\n"
			)  # Redundant \n at the start? who knows?

		## TODO: Support locale and timezone
		#os.remove(f'{self.mountpoint}/etc/localtime')
		#sys_command(f'/usr/bin/arch-chroot {self.mountpoint} ln -s /usr/share/zoneinfo/{localtime} /etc/localtime')
		#sys_command('/usr/bin/arch-chroot /mnt hwclock --hctosys --localtime')
		self.set_hostname()
		self.set_locale('en_US')

		# TODO: Use python functions for this
		sys_command(f'/usr/bin/arch-chroot {self.mountpoint} chmod 700 /root')

		# Configure mkinitcpio to handle some specific use cases.
		# TODO: Yes, we should not overwrite the entire thing, but for now this should be fine
		# since we just installed the base system.
		if self.partition.filesystem == 'btrfs':
			with open(f'{self.mountpoint}/etc/mkinitcpio.conf', 'w') as mkinit:
				mkinit.write('MODULES=(btrfs)\n')
				mkinit.write('BINARIES=(/usr/bin/btrfs)\n')
				mkinit.write('FILES=()\n')
				mkinit.write('HOOKS=(base udev autodetect keyboard keymap modconf block encrypt filesystems fsck)\n')
			sys_command(f'/usr/bin/arch-chroot {self.mountpoint} mkinitcpio -p linux')
		elif self.partition.encrypted:
			with open(f'{self.mountpoint}/etc/mkinitcpio.conf', 'w') as mkinit:
				mkinit.write('MODULES=()\n')
				mkinit.write('BINARIES=()\n')
				mkinit.write('FILES=()\n')
				mkinit.write('HOOKS=(base udev autodetect keyboard keymap modconf block encrypt filesystems fsck)\n')
			sys_command(f'/usr/bin/arch-chroot {self.mountpoint} mkinitcpio -p linux')

		self.helper_flags['base'] = True

		# Run registered post-install hooks
		for function in self.post_base_install:
			self.log(f"Running post-installation hook: {function}", level=LOG_LEVELS.Info)
			function(self)

		return True

	def add_bootloader(self, bootloader='systemd-bootctl'):
		self.log(f'Adding bootloader {bootloader} to {self.boot_partition}', level=LOG_LEVELS.Info)

		if bootloader == 'systemd-bootctl':
			# TODO: Ideally we would want to check if another config
			# points towards the same disk and/or partition.
			# And in which case we should do some clean up.

			# Install the boot loader
			sys_command(f'/usr/bin/arch-chroot {self.mountpoint} bootctl --no-variables --path=/boot install')

			# Modify or create a loader.conf
			if os.path.isfile(f'{self.mountpoint}/boot/loader/loader.conf'):
				with open(f'{self.mountpoint}/boot/loader/loader.conf', 'r') as loader:
					loader_data = loader.read().split('\n')
			else:
				loader_data = [
					f"default {self.init_time}",
					f"timeout 5"
				]
			
			with open(f'{self.mountpoint}/boot/loader/loader.conf', 'w') as loader:
				for line in loader_data:
					if line[:8] == 'default ':
						loader.write(f'default {self.init_time}\n')
					else:
						loader.write(f"{line}")

			## For some reason, blkid and /dev/disk/by-uuid are not getting along well.
			## And blkid is wrong in terms of LUKS.
			#UUID = sys_command('blkid -s PARTUUID -o value {drive}{partition_2}'.format(**args)).decode('UTF-8').strip()

			# Setup the loader entry
			with open(f'{self.mountpoint}/boot/loader/entries/{self.init_time}.conf', 'w') as entry:
				entry.write(f'# Created by: archinstall\n')
				entry.write(f'# Created on: {self.init_time}\n')
				entry.write(f'title Arch Linux\n')
				entry.write(f'linux /vmlinuz-linux\n')
				entry.write(f'initrd /initramfs-linux.img\n')
				## blkid doesn't trigger on loopback devices really well,
				## so we'll use the old manual method until we get that sorted out.


				if self.partition.encrypted:
					log(f"Identifying root partition by DISK-UUID on {self.partition}, looking for '{os.path.basename(self.partition.real_device)}'.", level=LOG_LEVELS.Debug)
					for root, folders, uids in os.walk('/dev/disk/by-uuid'):
						for uid in uids:
							real_path = os.path.realpath(os.path.join(root, uid))

							log(f"Checking root partition match {os.path.basename(real_path)} against {os.path.basename(self.partition.real_device)}: {os.path.basename(real_path) == os.path.basename(self.partition.real_device)}", level=LOG_LEVELS.Debug)
							if not os.path.basename(real_path) == os.path.basename(self.partition.real_device): continue

							entry.write(f'options cryptdevice=UUID={uid}:luksdev root=/dev/mapper/luksdev rw intel_pstate=no_hwp\n')

							self.helper_flags['bootloader'] = bootloader
							return True
						break
				else:
					log(f"Identifying root partition by PART-UUID on {self.partition}, looking for '{os.path.basename(self.partition.path)}'.", level=LOG_LEVELS.Debug)
					entry.write(f'options root=PARTUUID={self.partition.uuid} rw intel_pstate=no_hwp\n')

					self.helper_flags['bootloader'] = bootloader
					return True

			raise RequirementError(f"Could not identify the UUID of {self.partition}, there for {self.mountpoint}/boot/loader/entries/arch.conf will be broken until fixed.")
		else:
			raise RequirementError(f"Unknown (or not yet implemented) bootloader added to add_bootloader(): {bootloader}")

	def add_additional_packages(self, *packages):
		return self.pacstrap(*packages)

	def install_profile(self, profile):
		# TODO: Replace this with a import archinstall.session instead in the profiles.
		# The tricky thing with doing the import archinstall.session instead is that
		# profiles might be run from a different chroot, and there's no way we can
		# guarantee file-path safety when accessing the installer object that way.
		# Doing the __builtins__ replacement, ensures that the global variable "installation"
		# is always kept up to date. It's considered a nasty hack - but it's a safe way
		# of ensuring 100% accuracy of archinstall session variables.
		__builtins__['installation'] = self

		if type(profile) == str:
			profile = Profile(self, profile)

		self.log(f'Installing network profile {profile}', level=LOG_LEVELS.Info)
		return profile.install()

	def enable_sudo(self, entity :str, group=False):
		self.log(f'Enabling sudo permissions for {entity}.', level=LOG_LEVELS.Info)
		with open(f'{self.mountpoint}/etc/sudoers', 'a') as sudoers:
			sudoers.write(f'{"%" if group else ""}{entity} ALL=(ALL) ALL\n')
		return True

	def user_create(self, user :str, password=None, groups=[], sudo=False):
		self.log(f'Creating user {user}', level=LOG_LEVELS.Info)
		o = b''.join(sys_command(f'/usr/bin/arch-chroot {self.mountpoint} useradd -m -G wheel {user}'))
		if password:
			self.user_set_pw(user, password)

		if groups:
			for group in groups:
				o = b''.join(sys_command(f'/usr/bin/arch-chroot {self.mountpoint} gpasswd -a {user} {group}'))

		if sudo and self.enable_sudo(user):
			self.helper_flags['user'] = True

	def user_set_pw(self, user, password):
		self.log(f'Setting password for {user}', level=LOG_LEVELS.Info)

		if user == 'root':
			# This means the root account isn't locked/disabled with * in /etc/passwd
			self.helper_flags['user'] = True

		o = b''.join(sys_command(f"/usr/bin/arch-chroot {self.mountpoint} sh -c \"echo '{user}:{password}' | chpasswd\""))
		pass

	def set_keyboard_language(self, language):
		if len(language.strip()):
			with open(f'{self.mountpoint}/etc/vconsole.conf', 'w') as vconsole:
				vconsole.write(f'KEYMAP={language}\n')
				vconsole.write(f'FONT=lat9w-16\n')
		return True
