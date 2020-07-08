import os
from .exceptions import *
from .general import *
from .disk import Partition

class luks2():
	def __init__(self, partition, mountpoint, password, *args, **kwargs):
		self.password = password
		self.partition = partition
		self.mountpoint = mountpoint
		self.args = args
		self.kwargs = kwargs

	def __enter__(self):
		key_file = self.encrypt(self.partition, self.password, *self.args, **self.kwargs)
		return self.unlock(self.partition, self.mountpoint, key_file)

	def __exit__(self, *args, **kwargs):
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		if len(args) >= 2 and args[1]:
			raise args[1]
		return True

	def encrypt(self, partition, password, key_size=512, hash_type='sha512', iter_time=10000, key_file=None):
		log(f'Encrypting {partition}')
		if not key_file: key_file = f'/tmp/{os.path.basename(self.partition.path)}.disk_pw' #TODO: Make disk-pw-file randomly unique?
		if type(password) != bytes: password = bytes(password, 'UTF-8')

		with open(key_file, 'wb') as fh:
			fh.write(password)

		o = b''.join(sys_command(f'/usr/bin/cryptsetup -q -v --type luks2 --pbkdf argon2i --hash {hash_type} --key-size {key_size} --iter-time {iter_time} --key-file {os.path.abspath(key_file)} --use-urandom luksFormat {partition.path}'))
		if not b'Command successful.' in o:
			raise DiskError(f'Could not encrypt volume "{partition.path}": {o}')
	
		return key_file

	def unlock(self, partition, mountpoint, key_file):
		"""
		Mounts a lukts2 compatible partition to a certain mountpoint.
		Keyfile must be specified as there's no way to interact with the pw-prompt atm.

		:param mountpoint: The name without absolute path, for instance "luksdev" will point to /dev/mapper/luksdev
		:type mountpoint: str
		"""
		if '/' in mountpoint: os.path.basename(mountpoint) # TODO: Raise exception instead?
		sys_command(f'/usr/bin/cryptsetup open {partition.path} {mountpoint} --key-file {os.path.abspath(key_file)} --type luks2')
		if os.path.islink(f'/dev/mapper/{mountpoint}'):
			return Partition(f'/dev/mapper/{mountpoint}', encrypted=True)

	def close(self, mountpoint):
		sys_command(f'cryptsetup close /dev/mapper/{mountpoint}')
		return os.path.islink(f'/dev/mapper/{mountpoint}') is False