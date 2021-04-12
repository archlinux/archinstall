import os
import shlex
import time
import pathlib
from .exceptions import *
from .general import *
from .disk import Partition
from .output import log, LOG_LEVELS
from .storage import storage

class luks2():
	def __init__(self, partition, mountpoint, password, key_file=None, auto_unmount=False, *args, **kwargs):
		self.password = password
		self.partition = partition
		self.mountpoint = mountpoint
		self.args = args
		self.kwargs = kwargs
		self.key_file = key_file
		self.auto_unmount = auto_unmount
		self.filesystem = 'crypto_LUKS'
		self.mapdev = None

	def __enter__(self):
		#if self.partition.allow_formatting:
		#	self.key_file = self.encrypt(self.partition, *self.args, **self.kwargs)
		#else:
		if not self.key_file:
			self.key_file = f"/tmp/{os.path.basename(self.partition.path)}.disk_pw"  # TODO: Make disk-pw-file randomly unique?
		
		if type(self.password) != bytes:
			self.password = bytes(self.password, 'UTF-8')

		with open(self.key_file, 'wb') as fh:
			fh.write(self.password)

		return self.unlock(self.partition, self.mountpoint, self.key_file)

	def __exit__(self, *args, **kwargs):
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		if self.auto_unmount:
			self.close()

		if len(args) >= 2 and args[1]:
			raise args[1]
		return True

	def encrypt(self, partition, password=None, key_size=512, hash_type='sha512', iter_time=10000, key_file=None):
		if not self.partition.allow_formatting:
			raise DiskError(f'Could not encrypt volume {self.partition} due to it having a formatting lock.')

		log(f'Encrypting {partition} (This might take a while)', level=LOG_LEVELS.Info)

		if not key_file:
			if self.key_file:
				key_file = self.key_file
			else:
				key_file = f"/tmp/{os.path.basename(self.partition.path)}.disk_pw"  # TODO: Make disk-pw-file randomly unique?

		if not password:
			password = self.password

		if type(password) != bytes:
			password = bytes(password, 'UTF-8')

		with open(key_file, 'wb') as fh:
			fh.write(password)

		cryptsetup_args = shlex.join([
			'/usr/bin/cryptsetup',
			'--batch-mode',
			'--verbose',
			'--type', 'luks2',
			'--pbkdf', 'argon2id',
			'--hash', hash_type,
			'--key-size', str(key_size),
			'--iter-time', str(iter_time),
			'--key-file', os.path.abspath(key_file),
			'--use-urandom',
			'luksFormat', partition.path,
		])

		try:
			# Try to setup the crypt-device
			cmd_handle = sys_command(cryptsetup_args)
		except SysCallError as err:
			if err.exit_code == 256:
				log(f'{partition} is being used, trying to unmount and crypt-close the device and running one more attempt at encrypting the device.', level=LOG_LEVELS.Debug)
				# Partition was in use, unmount it and try again
				partition.unmount()

				# Get crypt-information about the device by doing a reverse lookup starting with the partition path
				# For instance: /dev/sda
				devinfo = json.loads(b''.join(sys_command(f"lsblk --fs -J {partition.path}")).decode('UTF-8'))['blockdevices'][0]

				# For each child (sub-partition/sub-device)
				if len(children := devinfo.get('children', [])):
					for child in children:
						# Unmount the child location
						if child_mountpoint := child.get('mountpoint', None):
							log(f'Unmounting {child_mountpoint}', level=LOG_LEVELS.Debug)
							sys_command(f"umount -R {child_mountpoint}")

						# And close it if possible.
						log(f"Closing crypt device {child['name']}", level=LOG_LEVELS.Debug)
						sys_command(f"cryptsetup close {child['name']}")

				# Then try again to set up the crypt-device
				cmd_handle = sys_command(cryptsetup_args)
			else:
				raise err

		if cmd_handle.exit_code != 0:
			raise DiskError(f'Could not encrypt volume "{partition.path}": {cmd_output}')
	
		return key_file

	def unlock(self, partition, mountpoint, key_file):
		"""
		Mounts a luks2 compatible partition to a certain mountpoint.
		Keyfile must be specified as there's no way to interact with the pw-prompt atm.

		:param mountpoint: The name without absolute path, for instance "luksdev" will point to /dev/mapper/luksdev
		:type mountpoint: str
		"""
		from .disk import get_filesystem_type
		if '/' in mountpoint:
			os.path.basename(mountpoint)  # TODO: Raise exception instead?

		wait_timer = time.time()
		while pathlib.Path(partition.path).exists() is False and time.time() - wait_timer < 10:
			time.sleep(0.025)

		sys_command(f'/usr/bin/cryptsetup open {partition.path} {mountpoint} --key-file {os.path.abspath(key_file)} --type luks2')
		if os.path.islink(f'/dev/mapper/{mountpoint}'):
			self.mapdev = f'/dev/mapper/{mountpoint}'
			unlocked_partition = Partition(self.mapdev, None, encrypted=True, filesystem=get_filesystem_type(self.mapdev), autodetect_filesystem=False)
			unlocked_partition.allow_formatting = self.partition.allow_formatting
			return unlocked_partition

	def close(self, mountpoint=None):
		if not mountpoint:
			mountpoint = self.mapdev

		sys_command(f'/usr/bin/cryptsetup close {self.mapdev}')
		return os.path.islink(self.mapdev) is False

	def format(self, path):
		if (handle := sys_command(f"/usr/bin/cryptsetup -q -v luksErase {path}")).exit_code != 0:
			raise DiskError(f'Could not format {path} with {self.filesystem} because: {b"".join(handle)}')
