import json
import logging
import os
import pathlib
import shlex
import time
from .disk import Partition, convert_device_to_uuid
from .general import SysCommand, SysCommandWorker
from .output import log
from .exceptions import SysCallError, DiskError
from .storage import storage

class luks2:
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
		log(f'Encrypting {partition} (This might take a while)', level=logging.INFO)

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

		SysCommand(f'bash -c "partprobe"') # Might be redundant

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
			# Retry formatting the volume because archinstall can some times be too quick
			# which generates a "Device /dev/sdX does not exist or access denied." between
			# setting up partitions and us trying to encrypt it.
			for i in range(storage['DISK_RETRY_ATTEMPTS']):
				if (cmd_handle := SysCommand(cryptsetup_args)).exit_code != 0:
					time.sleep(storage['DISK_TIMEOUTS'])
				else:
					break

			if cmd_handle.exit_code != 0:
				raise DiskError(f'Could not encrypt volume "{partition.path}": {b"".join(cmd_handle)}')
		except SysCallError as err:
			if err.exit_code == 256:
				log(f'{partition} is being used, trying to unmount and crypt-close the device and running one more attempt at encrypting the device.', level=logging.DEBUG)
				# Partition was in use, unmount it and try again
				partition.unmount()

				# Get crypt-information about the device by doing a reverse lookup starting with the partition path
				# For instance: /dev/sda
				SysCommand(f'bash -c "partprobe"')
				devinfo = json.loads(b''.join(SysCommand(f"lsblk --fs -J {partition.path}")).decode('UTF-8'))['blockdevices'][0]

				# For each child (sub-partition/sub-device)
				if len(children := devinfo.get('children', [])):
					for child in children:
						# Unmount the child location
						if child_mountpoint := child.get('mountpoint', None):
							log(f'Unmounting {child_mountpoint}', level=logging.DEBUG)
							SysCommand(f"umount -R {child_mountpoint}")

						# And close it if possible.
						log(f"Closing crypt device {child['name']}", level=logging.DEBUG)
						SysCommand(f"cryptsetup close {child['name']}")

				# Then try again to set up the crypt-device
				cmd_handle = SysCommand(cryptsetup_args)
			else:
				raise err

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

		SysCommand(f'/usr/bin/cryptsetup open {partition.path} {mountpoint} --key-file {os.path.abspath(key_file)} --type luks2')
		if os.path.islink(f'/dev/mapper/{mountpoint}'):
			self.mapdev = f'/dev/mapper/{mountpoint}'
			unlocked_partition = Partition(self.mapdev, None, encrypted=True, filesystem=get_filesystem_type(self.mapdev), autodetect_filesystem=False)
			return unlocked_partition

	def close(self, mountpoint=None):
		if not mountpoint:
			mountpoint = self.mapdev

		SysCommand(f'/usr/bin/cryptsetup close {self.mapdev}')
		return os.path.islink(self.mapdev) is False

	def format(self, path):
		if (handle := SysCommand(f"/usr/bin/cryptsetup -q -v luksErase {path}")).exit_code != 0:
			raise DiskError(f'Could not format {path} with {self.filesystem} because: {b"".join(handle)}')

	def add_key(self, path :pathlib.Path, password :str):
		if not path.exists():
			raise OSError(2, f"Could not import {path} as a disk encryption key, file is missing.", str(path))

		log(f'Adding additional key-file {path} for {self.partition}', level=logging.INFO)

		worker = SysCommandWorker(f"/usr/bin/cryptsetup -q -v luksAddKey {self.partition.path} {path}")
		pw_injected = False
		while worker.is_alive():
			if b'Enter any existing passphrase' in worker and pw_injected is False:
				worker.write(bytes(password, 'UTF-8'))
				pw_injected = True

		if worker.exit_code != 0:
			raise DiskError(f'Could not add encryption key {path} to {self.partition} because: {worker}')

	def crypttab(self, installation, key_path :str, options=["luks", "key-slot=1"]):
		log(f'Adding a crypttab entry for key {key_path} in {installation}', level=logging.INFO)
		with open(f"{installation.target}/etc/crypttab", "a") as crypttab:
			crypttab.write(f"{self.mountpoint} UUID={convert_device_to_uuid(self.partition.path)} {key_path} {','.join(options)}\n")