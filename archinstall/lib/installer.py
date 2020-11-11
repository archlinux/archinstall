import os, stat, time

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
	def __init__(self, partition, boot_partition, *, base_packages='base base-devel linux linux-firmware efibootmgr nano', profile=None, mountpoint='/mnt', hostname='ArchInstalled'):
		self.profile = profile
		self.hostname = hostname
		self.mountpoint = mountpoint
		self.init_time = time.strftime('%Y-%m-%d_%H-%M-%S')
		self.milliseconds = int(str(time.time()).split('.')[1])

		self.helper_flags = {
			'bootloader' : False,
			'base' : False,
			'user' : False # Root counts as a user, if additional users are skipped.
		}

		self.base_packages = base_packages.split(' ')
		storage['session'] = self

		self.partition = partition
		self.boot_partition = boot_partition

	def log(self, *args, level=LOG_LEVELS.Debug, file=None, **kwargs):
		if not file:
			if 'logfile' not in storage:
				log_root = os.path.join(os.path.expanduser('~/'), '.cache/archinstall')
				if not os.path.isdir(log_root):
					os.makedirs(log_root)

				storage['logfile'] = f"{log_root}/install-session_{self.init_time}.{self.milliseconds}.log"

			file = storage['logfile']

		log(*args, level=level, file=file, **kwargs)

	def __enter__(self, *args, **kwargs):
		self.partition.mount(self.mountpoint)
		os.makedirs(f'{self.mountpoint}/boot', exist_ok=True)
		self.boot_partition.mount(f'{self.mountpoint}/boot')
		return self

	def __exit__(self, *args, **kwargs):
		# b''.join(sys_command(f'sync')) # No need to, since the underlaying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		if len(args) >= 2 and args[1]:
			raise args[1]

		if not (missing_steps := self.post_install_check()):
			self.log('Installation completed without any errors. You may now reboot.', bg='black', fg='green', level=LOG_LEVELS.Info)
			return True
		else:
			self.log('Some required steps were not successfully installed/configured before leaving the installer:', bg='black', fg='red', level=LOG_LEVELS.Warning)
			for step in missing_steps:
				self.log(f' - {step}', bg='black', fg='red', level=LOG_LEVELS.Warning)
			self.log(f"Detailed error logs can be found at: {log_path}", level=LOG_LEVELS.Warning)
			self.log(f"Submit this zip file as an issue to https://github.com/Torxed/archinstall/issues", level=LOG_LEVELS.Warning)
			return False

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

	def genfstab(self, flags='-Pu'):
		o = b''.join(sys_command(f'/usr/bin/genfstab -pU {self.mountpoint} >> {self.mountpoint}/etc/fstab'))
		if not os.path.isfile(f'{self.mountpoint}/etc/fstab'):
			raise RequirementError(f'Could not generate fstab, strapping in packages most likely failed (disk out of space?)\n{o}')
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
		if not len(zone): return True

		o = b''.join(sys_command(f'/usr/bin/arch-chroot {self.mountpoint} ln -s /usr/share/zoneinfo/{zone} /etc/localtime'))
		return True

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

	def minimal_installation(self):
		## Add nessecary packages if encrypting the drive
		## (encrypted partitions default to btrfs for now, so we need btrfs-progs)
		## TODO: Perhaps this should be living in the function which dictates
		##       the partitioning. Leaving here for now.
		if self.partition.filesystem == 'btrfs':
		#if self.partition.encrypted:
			self.base_packages.append('btrfs-progs')

		self.pacstrap(self.base_packages)
		self.genfstab()

		with open(f"{self.mountpoint}/etc/fstab", "a") as fstab:
			fstab.write(
				"\ntmpfs /tmp tmpfs defaults,noatime,mode=1777 0 0\n"
			)  # Redundant \n at the start? who knows?

		## TODO: Support locale and timezone
		#os.remove(f'{self.mountpoint}/etc/localtime')
		#sys_command(f'/usr/bin/arch-chroot {self.mountpoint} ln -s /usr/share/zoneinfo/{localtime} /etc/localtime')
		#sys_command('/usr/bin/arch-chroot /mnt hwclock --hctosys --localtime')
		self.set_hostname()
		self.set_locale('en_US.UTF-8')

		# TODO: Use python functions for this
		sys_command(f'/usr/bin/arch-chroot {self.mountpoint} chmod 700 /root')

		if self.partition.filesystem == 'btrfs':
			with open(f'{self.mountpoint}/etc/mkinitcpio.conf', 'w') as mkinit:
				## TODO: Don't replace it, in case some update in the future actually adds something.
				mkinit.write('MODULES=(btrfs)\n')
				mkinit.write('BINARIES=(/usr/bin/btrfs)\n')
				mkinit.write('FILES=()\n')
				mkinit.write('HOOKS=(base udev autodetect modconf block encrypt filesystems keyboard fsck)\n')
			sys_command(f'/usr/bin/arch-chroot {self.mountpoint} mkinitcpio -p linux')

		self.helper_flags['base'] = True
		return True

	def add_bootloader(self, bootloader='systemd-bootctl'):
		self.log(f'Adding bootloader {bootloader} to {self.boot_partition}', level=LOG_LEVELS.Info)

		if bootloader == 'systemd-bootctl':
			o = b''.join(sys_command(f'/usr/bin/arch-chroot {self.mountpoint} bootctl --no-variables --path=/boot install'))
			with open(f'{self.mountpoint}/boot/loader/loader.conf', 'w') as loader:
				loader.write('default arch\n')
				loader.write('timeout 5\n')

			## For some reason, blkid and /dev/disk/by-uuid are not getting along well.
			## And blkid is wrong in terms of LUKS.
			#UUID = sys_command('blkid -s PARTUUID -o value {drive}{partition_2}'.format(**args)).decode('UTF-8').strip()
			with open(f'{self.mountpoint}/boot/loader/entries/arch.conf', 'w') as entry:
				entry.write('title Arch Linux\n')
				entry.write('linux /vmlinuz-linux\n')
				entry.write('initrd /initramfs-linux.img\n')
				## blkid doesn't trigger on loopback devices really well,
				## so we'll use the old manual method until we get that sorted out.


				if self.partition.encrypted:
					for root, folders, uids in os.walk('/dev/disk/by-uuid'):
						for uid in uids:
							real_path = os.path.realpath(os.path.join(root, uid))
							if not os.path.basename(real_path) == os.path.basename(self.partition.real_device): continue

							entry.write(f'options cryptdevice=UUID={uid}:luksdev root=/dev/mapper/luksdev rw intel_pstate=no_hwp\n')

							self.helper_flags['bootloader'] = bootloader
							return True
						break
				else:
					for root, folders, uids in os.walk('/dev/disk/by-partuuid'):
						for uid in uids:
							real_path = os.path.realpath(os.path.join(root, uid))
							if not os.path.basename(real_path) == os.path.basename(self.partition.path): continue

							entry.write(f'options root=PARTUUID={uid} rw intel_pstate=no_hwp\n')

							self.helper_flags['bootloader'] = bootloader
							return True
						break
			raise RequirementError(f"Could not identify the UUID of {self.partition}, there for {self.mountpoint}/boot/loader/entries/arch.conf will be broken until fixed.")
		else:
			raise RequirementError(f"Unknown (or not yet implemented) bootloader added to add_bootloader(): {bootloader}")

	def add_additional_packages(self, *packages):
		return self.pacstrap(*packages)

	def install_profile(self, profile):
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