from __future__ import annotations

import logging
import shlex
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from .utils.diskinfo import get_lsblk_info

from .general import SysCommand, generate_password, SysCommandWorker
from .output import log
from .exceptions import SysCallError, DiskError
from .storage import storage


@dataclass
class Luks2:
	luks_dev_path: Path
	mapper_name: Optional[str] = None
	password: Optional[str] = None
	key_file: Optional[Path] = None
	auto_unmount: bool = False

	# will be set internally after unlocking the device
	_mapper_dev: Optional[Path] = None

	@property
	def mapper_dev(self) -> Optional[Path]:
		return self._mapper_dev

	def __post_init__(self):
		if self.luks_dev_path is None:
			raise ValueError('Partition must have a path set')

	def __enter__(self):
		self.unlock()

	def __exit__(self, *args: str, **kwargs: str) -> bool:
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		if self.auto_unmount:
			self.lock()

		if len(args) >= 2 and args[1]:
			raise args[1]

		return True

	def _default_key_file(self) -> Path:
		return Path(f'/tmp/{self.luks_dev_path.name}.disk_pw')  # TODO: Make disk-pw-file randomly unique?

	def encrypt(
		self,
		key_size: int = 512,
		hash_type: str = 'sha512',
		iter_time: int = 10000,
		key_file: Optional[str] = None
	) -> Path:
		if self.password is None:
			raise ValueError('Password was not defined')

		log(f'Encrypting {self.luks_dev_path} (This might take a while)', level=logging.INFO)

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
			'luksFormat', str(self.luks_dev_path),
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
				raise DiskError(f'Could not encrypt volume "{self.luks_dev_path}": {b"".join(cmd_handle)}')
		except SysCallError as err:
			if err.exit_code == 256:
				log(f'luks2 partition currently in use: {self.luks_dev_path}')
				log('Attempting to unmount, crypt-close and trying encryption again')

				self.lock()
				# Then try again to set up the crypt-device
				SysCommand(cryptsetup_args)
			else:
				raise err

		return key_file

	def _get_luks_uuid(self) -> str:
		command = f'/usr/bin/cryptsetup luksUUID {self.luks_dev_path}'

		try:
			result = SysCommand(command)
			if result.exit_code != 0:
				raise DiskError(f'Unable to get UUID for Luks device: {result.decode()}')

			return result.decode()
		except SysCallError as err:
			log(f'Unable to get UUID for Luks device: {self.luks_dev_path}', level=logging.INFO)
			raise err

	def is_unlocked(self) -> bool:
		return self._mapper_dev is not None

	def unlock(self, mapper_name: Optional[str] = None, key_file: Optional[Path] = None) -> Path:
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
		while Path(self.luks_dev_path).exists() is False and time.time() - wait_timer < 10:
			time.sleep(0.025)

		SysCommand(f'/usr/bin/cryptsetup open {self.luks_dev_path} {mapper_name} --key-file {key_file} --type luks2')
		mapper_dev = Path(f'/dev/mapper/{mapper_name}')

		if mapper_dev.is_symlink():
			self._mapper_dev = mapper_dev
		else:
			raise DiskError(f'Failed to open luks2 device: {self.luks_dev_path}')

	def lock(self):
		from .disk.device_handler import device_handler

		device_handler.umount(self.luks_dev_path)

		# Get crypt-information about the device by doing a reverse lookup starting with the partition path
		# For instance: /dev/sda
		device_handler.partprobe()
		lsblk_info = get_lsblk_info(self.luks_dev_path)

		# For each child (sub-partition/sub-device)
		for child in lsblk_info.children:
			# Unmount the child location
			for mountpoint in child.mountpoints:
				log(f'Unmounting {mountpoint}', level=logging.DEBUG)
				device_handler.umount(mountpoint, recursive=True)

			# And close it if possible.
			log(f"Closing crypt device {child.name}", level=logging.DEBUG)
			SysCommand(f"cryptsetup close {child.name}")

		self._mapper_dev = None

	def create_keyfile(self, target_path: Path):
		"""
		Routine to create keyfiles, so it can be moved elsewhere
		"""
		if self.mapper_name is None:
			raise ValueError('Mapper name must be provided')

		# Once we store the key as ../xyzloop.key systemd-cryptsetup can
		# automatically load this key if we name the device to "xyzloop"
		key_file_path = target_path / 'etc/cryptsetup-keys.d/' / self.mapper_name / '.key'
		crypttab_path = target_path / 'etc/crypttab'

		key_file_path.mkdir(parents=True, exist_ok=True)

		with open(key_file_path, "w") as keyfile:
			keyfile.write(generate_password(length=512))

		key_file_path.chmod(0o400)

		self._add_key(key_file_path)
		self._crypttab(crypttab_path, key_file_path, options=["luks", "key-slot=1"])

	def _add_key(self, key_file_path: Path):
		log(f'Adding additional key-file {key_file_path}', level=logging.INFO)

		command = f'/usr/bin/cryptsetup -q -v luksAddKey {self.luks_dev_path} {key_file_path}'
		worker = SysCommandWorker(command, environment_vars={'LC_ALL': 'C'})
		pw_injected = False

		while worker.is_alive():
			if b'Enter any existing passphrase' in worker and pw_injected is False:
				worker.write(bytes(self.password, 'UTF-8'))
				pw_injected = True

		if worker.exit_code != 0:
			raise DiskError(f'Could not add encryption key {key_file_path} to {self.luks_dev_path}: {worker.decode()}')

	def _crypttab(
		self,
		crypttab_path: Path,
		key_file_path: Path,
		options: List[str]
	) -> None:
		log(f'Adding crypttab entry for key {key_file_path}', level=logging.INFO)

		with open(crypttab_path, 'a') as crypttab:
			opt = ','.join(options)
			uuid = self._get_luks_uuid()
			row = f"{self.mapper_name} UUID={uuid} {key_file_path} {opt}\n"
			crypttab.write(row)
