from __future__ import annotations

import logging
import shlex
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .disk.device_handler import PartitionModification, device_handler
from .utils.diskinfo import get_lsblk_info

from .general import SysCommand
from .output import log
from .exceptions import SysCallError, DiskError
from .storage import storage


@dataclass
class Luks2:
	partition: PartitionModification
	mapper_name: Optional[str] = None
	password: Optional[str] = None
	key_file: Optional[Path] = None
	auto_unmount: bool = False

	def __post_init__(self):
		if self.partition.path is None:
			raise ValueError('Partition must have a path set')

	def __enter__(self) -> Path:
		return self.unlock()

	def __exit__(self, *args: str, **kwargs: str) -> bool:
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		if self.auto_unmount:
			self.lock()

		if len(args) >= 2 and args[1]:
			raise args[1]

		return True

	def _default_key_file(self) -> Path:
		return Path(f'/tmp/{self.partition.path.name}.disk_pw')  # TODO: Make disk-pw-file randomly unique?

	def encrypt(
		self,
		key_size: int = 512,
		hash_type: str = 'sha512',
		iter_time: int = 10000,
		key_file: Optional[str] = None
	) -> Path:
		log(f'Encrypting {self.partition.path} (This might take a while)', level=logging.INFO)

		if type(self.password) != bytes:
			byte_password = bytes(self.password, 'UTF-8')
		else:
			byte_password = self.password

		if not key_file:
			if self.key_file:
				key_file = self.key_file
			else:
				key_file = self._default_key_file()

				with open(key_file, 'wb') as fh:
					fh.write(byte_password)

		cryptsetup_args = shlex.join([
			'/usr/bin/cryptsetup',
			'--batch-mode',
			'--verbose',
			'--type', 'luks2',
			'--pbkdf', 'argon2id',
			'--hash', hash_type,
			'--key-size', str(key_size),
			'--iter-time', str(iter_time),
			'--key-file', str(key_file),
			'--use-urandom',
			'luksFormat', str(self.partition.path),
		])

		try:
			# Retry formatting the volume because archinstall can some times be too quick
			# which generates a "Device /dev/sdX does not exist or access denied." between
			# setting up partitions and us trying to encrypt it.
			cmd_handle = None
			for i in range(storage['DISK_RETRY_ATTEMPTS']):
				if (cmd_handle := SysCommand(cryptsetup_args)).exit_code != 0:
					time.sleep(storage['DISK_TIMEOUTS'])
				else:
					break

			if cmd_handle is not None and cmd_handle.exit_code != 0:
				raise DiskError(f'Could not encrypt volume "{self.partition.path}": {b"".join(cmd_handle)}')
		except SysCallError as err:
			if err.exit_code == 256:
				log(
					f'{self.partition.path} is being used, trying to unmount and crypt-close the device and running one more attempt at encrypting the device.',
					level=logging.DEBUG
				)
				self.lock()
				# Then try again to set up the crypt-device
				SysCommand(cryptsetup_args)
			else:
				raise err

		return key_file

	def unlock(self, mapper_name: Optional[str] = None, key_file: Optional[Path] = None) -> Optional[Path]:
		"""
		Mounts a luks2 compatible partition to a given mountpoint.
		Keyfile must be specified as there's no way to interact with the pw-prompt atm.

		:param mapper_name: An alternative mapping name, for instance "luksdev" will point to /dev/mapper/luksdev
		:type mapper_name: str

		:param key_file: An alternative key file
		:type key_file: Path
		"""

		if type(self.password) != bytes:
			byte_password = bytes(self.password, 'UTF-8')
		else:
			byte_password = self.password

		if not key_file:
			if self.key_file:
				key_file = self.key_file
			else:
				key_file = self._default_key_file()

				with open(key_file, 'wb') as fh:
					fh.write(byte_password)

		if not mapper_name:
			mapper_name = self.mapper_name

		if not mapper_name:
			raise ValueError('mapper name missing')

		if '/' in mapper_name:
			raise ValueError('mapper_name cannot contain "/"')

		wait_timer = time.time()
		while Path(self.partition.path).exists() is False and time.time() - wait_timer < 10:
			time.sleep(0.025)

		SysCommand(f'/usr/bin/cryptsetup open {self.partition.path} {mapper_name} --key-file {key_file} --type luks2')
		mapper_dev = Path(f'/dev/mapper{mapper_name}')

		if mapper_dev.is_symlink():
			return mapper_dev

		return None

	def lock(self):
		device_handler.umount(self.partition.path)

		# Get crypt-information about the device by doing a reverse lookup starting with the partition path
		# For instance: /dev/sda
		device_handler.partprobe()
		lsblk_info = get_lsblk_info(self.partition.path)

		# For each child (sub-partition/sub-device)
		for child in lsblk_info.children:
			# Unmount the child location
			for mountpoint in child.mountpoints:
				log(f'Unmounting {mountpoint}', level=logging.DEBUG)
				device_handler.umount(mountpoint, recursive=True)

			# And close it if possible.
			log(f"Closing crypt device {child.name}", level=logging.DEBUG)
			SysCommand(f"cryptsetup close {child.name}")

	# def add_key(self, path :Path, password :str) -> bool:
	# 	if not path.exists():
	# 		raise OSError(2, f"Could not import {path} as a disk encryption key, file is missing.", str(path))
	#
	# 	log(f'Adding additional key-file {path} for {self.partition}', level=logging.INFO)
	# 	worker = SysCommandWorker(f"/usr/bin/cryptsetup -q -v luksAddKey {self.partition.path} {path}",
	# 						environment_vars={'LC_ALL':'C'})
	# 	pw_injected = False
	# 	while worker.is_alive():
	# 		if b'Enter any existing passphrase' in worker and pw_injected is False:
	# 			worker.write(bytes(password, 'UTF-8'))
	# 			pw_injected = True
	#
	# 	if worker.exit_code != 0:
	# 		raise DiskError(f'Could not add encryption key {path} to {self.partition} because: {worker}')
	#
	# 	return True
	#
	# def crypttab(self, installation :Installer, key_path :str, options :List[str] = ["luks", "key-slot=1"]) -> None:
	# 	log(f'Adding a crypttab entry for key {key_path} in {installation}', level=logging.INFO)
	# 	with open(f"{installation.target}/etc/crypttab", "a") as crypttab:
	# 		crypttab.write(f"{self.mapper_name} UUID={convert_device_to_uuid(self.partition.path)} {key_path} {','.join(options)}\n")
