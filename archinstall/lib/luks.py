import os
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
		# TODO: We should be able to integrate this into the main log some how.
		#       Perhaps post-mortem?
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

		o = b''.join(sys_command(f'/usr/bin/cryptsetup -q -v --type luks2 --pbkdf argon2i --hash {hash_type} --key-size {key_size} --iter-time {iter_time} --key-file {os.path.abspath(key_file)} --use-urandom luksFormat {partition.path}'))
		if b'Command successful.' not in o:
			raise DiskError(f'Could not encrypt volume "{partition.path}": {o}')
	
		return key_file

	def unlock(self, partition, mountpoint, key_file):
		"""
		Mounts a lukts2 compatible partition to a certain mountpoint.
		Keyfile must be specified as there's no way to interact with the pw-prompt atm.

		:param mountpoint: The name without absolute path, for instance "luksdev" will point to /dev/mapper/luksdev
		:type mountpoint: str
		"""
		from .disk import get_filesystem_type
		if '/' in mountpoint:
			os.path.basename(mountpoint)  # TODO: Raise exception instead?
		sys_command(f'/usr/bin/cryptsetup open {partition.path} {mountpoint} --key-file {os.path.abspath(key_file)} --type luks2')
		if os.path.islink(f'/dev/mapper/{mountpoint}'):
			return Partition(f'/dev/mapper/{mountpoint}', encrypted=True, filesystem=get_filesystem_type(f'/dev/mapper/{mountpoint}'))

	def close(self, mountpoint=None):
		if not mountpoint:
			mountpoint = self.partition.path 
			
		sys_command(f'cryptsetup close /dev/mapper/{mountpoint}')
		return os.path.islink(f'/dev/mapper/{mountpoint}') is False

	def format(self, path):
		if (handle := sys_command(f"/usr/bin/cryptsetup -q -v luksErase {path}")).exit_code != 0:
			raise DiskError(f'Could not format {path} with {self.filesystem} because: {b"".join(handle)}')