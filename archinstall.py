import os, stat

from exceptions import *
from helpers.disk import *
from helpers.general import *
from helpers.user_interaction import *

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
		return True

	def minimal_installation(self):
		if (sync_mirrors := sys_command('/usr/bin/pacman -Syy')).exit_code == 0:
			if (pacstrap := sys_command(f'/usr/bin/pacstrap {self.mountpoint} base base-devel linux linux-firmware btrfs-progs efibootmgr nano wpa_supplicant dialog')).exit_code == 0:
				return True
			else:
				log(f'Could not strap in base: {pacstrap.exit_code}')
		else:
			log(f'Could not sync mirrors: {sync_mirrors.exit_code}')

	def add_bootloader(self, partition):
		os.makedirs(f'{self.mountpoint}/boot', exist_ok=True)
		partition.mount(f'{self.mountpoint}/boot')
		o = b''.join(sys_command(f'/usr/bin/arch-chroot {self.mountpoint} bootctl --no-variables --path=/boot install'))

		with open('/mnt/boot/loader/loader.conf', 'w') as loader:
			loader.write('default arch\n')
			loader.write('timeout 5\n')

		## For some reason, blkid and /dev/disk/by-uuid are not getting along well.
		## And blkid is wrong in terms of LUKS.
		#UUID = sys_command('blkid -s PARTUUID -o value {drive}{partition_2}'.format(**args)).decode('UTF-8').strip()
		with open('/mnt/boot/loader/entries/arch.conf', 'w') as entry:
			entry.write('title Arch Linux\n')
			entry.write('linux /vmlinuz-linux\n')
			entry.write('initrd /initramfs-linux.img\n')
			## blkid doesn't trigger on loopback devices really well,
			## so we'll use the old manual method until we get that sorted out.
			# UUID = simple_command(f"blkid -s PARTUUID -o value /dev/{os.path.basename(args['drive'])}{args['partitions']['2']}").decode('UTF-8').strip()
			# entry.write('options root=PARTUUID={UUID} rw intel_pstate=no_hwp\n'.format(UUID=UUID))
			UUID = b''.join(sys_command(f"ls -l /dev/disk/by-uuid/ | grep {os.path.basename(partition['path'])} | awk '{{print $9}}'")).decode('UTF-8').strip()
			entry.write(f'options cryptdevice=UUID={UUID}:luksdev root=/dev/mapper/luksdev rw intel_pstate=no_hwp\n')