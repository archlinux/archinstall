import os, stat

from .exceptions import *
from .disk import *
from .general import *
from .user_interaction import *
from .profiles import Profile

class Installer():
	def __init__(self, partition, *, profile=None, mountpoint='/mnt', hostname='ArchInstalled'):
		self.profile = profile
		self.hostname = hostname
		self.mountpoint = mountpoint

		self.partition = partition

	def __enter__(self, *args, **kwargs):
		self.partition.mount(self.mountpoint)
		return self

	def __exit__(self, *args, **kwargs):
		# b''.join(sys_command(f'sync')) # No need to, since the underlaying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		if len(args) >= 2 and args[1]:
			raise args[1]
		log('Installation completed without any errors.', bg='black', fg='green')
		return True

	def pacstrap(self, *packages):
		if type(packages[0]) in (list, tuple): packages = packages[0]
		log(f'Installing packages: {packages}')

		if (sync_mirrors := sys_command('/usr/bin/pacman -Syy')).exit_code == 0:
			if (pacstrap := sys_command(f'/usr/bin/pacstrap {self.mountpoint} {" ".join(packages)}')).exit_code == 0:
				return True
			else:
				log(f'Could not strap in packages: {pacstrap.exit_code}')
		else:
			log(f'Could not sync mirrors: {sync_mirrors.exit_code}')

	def minimal_installation(self):
		return self.pacstrap('base base-devel linux linux-firmware btrfs-progs efibootmgr nano wpa_supplicant dialog'.split(' '))

	def add_bootloader(self, partition):
		log(f'Adding bootloader to {partition}')
		os.makedirs(f'{self.mountpoint}/boot', exist_ok=True)
		partition.mount(f'{self.mountpoint}/boot')
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
			# UUID = simple_command(f"blkid -s PARTUUID -o value /dev/{os.path.basename(args['drive'])}{args['partitions']['2']}").decode('UTF-8').strip()
			# entry.write('options root=PARTUUID={UUID} rw intel_pstate=no_hwp\n'.format(UUID=UUID))
			for root, folders, uids in os.walk('/dev/disk/by-uuid'):
				for uid in uids:
					real_path = os.path.realpath(os.path.join(root, uid))
					if not os.path.basename(real_path) == os.path.basename(partition.path): continue

					entry.write(f'options cryptdevice=UUID={uid}:luksdev root=/dev/mapper/luksdev rw intel_pstate=no_hwp\n')
					return True
				break
		raise RequirementError(f'Could not identify the UUID of {partition}, there for {self.mountpoint}/boot/loader/entries/arch.conf will be broken until fixed.')

	def add_additional_packages(self, *packages):
		self.pacstrap(*packages)

	def install_profile(self, profile):
		profile = Profile(self, profile)

		log(f'Installing network profile {profile}')
		profile.install()

	def user_create(self, user :str, password=None, groups=[]):
		log(f'Creating user {user}')
		o = b''.join(sys_command(f'/usr/bin/arch-chroot {self.mountpoint} useradd -m -G wheel {user}'))
		if password:
			self.user_set_pw(user, password)
		if groups:
			for group in groups:
				o = b''.join(sys_command(f'/usr/bin/arch-chroot {self.mountpoint} gpasswd -a {user} {group}'))

	def user_set_pw(self, user, password):
		log(f'Setting password for {user}')
		o = b''.join(sys_command(f"/usr/bin/arch-chroot {self.mountpoint} sh -c \"echo '{user}:{password}' | chpasswd\""))
		pass

	def add_AUR_support(self):
		log(f'Building and installing yay support into {self.mountpoint}')
		self.add_additional_packages(['git', 'base-devel']) # TODO: Remove if not explicitly added at one point
		o = b''.join(sys_command(f'/usr/bin/arch-chroot {self.mountpoint} sh -c "useradd -m -G wheel aibuilder"'))
		o = b''.join(sys_command(f"/usr/bin/sed -i 's/# %wheel ALL=(ALL) NO/%wheel ALL=(ALL) NO/' {self.mountpoint}/etc/sudoers"))

		o = b''.join(sys_command(f'/usr/bin/arch-chroot {self.mountpoint} sh -c "su - aibuilder -c \\"(cd /home/aibuilder; git clone https://aur.archlinux.org/yay.git)\\""'))
		o = b''.join(sys_command(f'/usr/bin/arch-chroot {self.mountpoint} sh -c "chown -R aibuilder.aibuilder /home/aibuilder/yay"'))
		o = b''.join(sys_command(f'/usr/bin/arch-chroot {self.mountpoint} sh -c "su - aibuilder -c \\"(cd /home/aibuilder/yay; makepkg -si --noconfirm)\\" >/dev/null"'))

		o = b''.join(sys_command(f'/usr/bin/arch-chroot {self.mountpoint} sh -c "userdel aibuilder; rm -rf /hoem/aibuilder"'))