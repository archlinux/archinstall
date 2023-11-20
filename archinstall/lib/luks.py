from __future__ import annotations

import shlex
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from . import disk
from .general import SysCommand, generate_password, SysCommandWorker
from .output import info, debug
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
		if self.mapper_name:
			return Path(f'/dev/mapper/{self.mapper_name}')
		return None

	def __post_init__(self):
		if self.luks_dev_path is None:
			raise ValueError('Partition must have a path set')

	def __enter__(self):
		self.unlock(self.key_file)

	def __exit__(self, *args: str, **kwargs: str):
		if self.auto_unmount:
			self.lock()

	def _default_key_file(self) -> Path:
		return Path(f'/tmp/{self.luks_dev_path.name}.disk_pw')

	def _password_bytes(self) -> bytes:
		if not self.password:
			raise ValueError('Password for luks2 device was not specified')

		if isinstance(self.password, bytes):
			return self.password
		else:
			return bytes(self.password, 'UTF-8')

	def encrypt(
		self,
		key_size: int = 512,
		hash_type: str = 'sha512',
		iter_time: int = 10000,
		key_file: Optional[Path] = None
	) -> Path:
		info(f'Luks2 encrypting: {self.luks_dev_path}')

		byte_password = self._password_bytes()

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

		# Retry formatting the volume because archinstall can some times be too quick
		# which generates a "Device /dev/sdX does not exist or access denied." between
		# setting up partitions and us trying to encrypt it.
		for retry_attempt in range(storage['DISK_RETRY_ATTEMPTS'] + 1):
			try:
				SysCommand(cryptsetup_args)
				break
			except SysCallError as err:
				time.sleep(storage['DISK_TIMEOUTS'])

				if retry_attempt != storage['DISK_RETRY_ATTEMPTS']:
					continue

				if err.exit_code == 1:
					info(f'luks2 partition currently in use: {self.luks_dev_path}')
					info('Attempting to unmount, crypt-close and trying encryption again')

					self.lock()
					# Then try again to set up the crypt-device
					SysCommand(cryptsetup_args)
				else:
					raise DiskError(f'Could not encrypt volume "{self.luks_dev_path}": {err}')

		return key_file

	def _get_luks_uuid(self) -> str:
		command = f'/usr/bin/cryptsetup luksUUID {self.luks_dev_path}'

		try:
			return SysCommand(command).decode()
		except SysCallError as err:
			info(f'Unable to get UUID for Luks device: {self.luks_dev_path}')
			raise err

	def is_unlocked(self) -> bool:
		return self.mapper_name is not None and Path(f'/dev/mapper/{self.mapper_name}').exists()

	def unlock(self, key_file: Optional[Path] = None):
		"""
		Unlocks the luks device, an optional key file location for unlocking can be specified,
		otherwise a default location for the key file will be used.

		:param key_file: An alternative key file
		:type key_file: Path
		"""
		debug(f'Unlocking luks2 device: {self.luks_dev_path}')

		if not self.mapper_name:
			raise ValueError('mapper name missing')

		byte_password = self._password_bytes()

		if not key_file:
			if self.key_file:
				key_file = self.key_file
			else:
				key_file = self._default_key_file()

				with open(key_file, 'wb') as fh:
					fh.write(byte_password)

		wait_timer = time.time()
		while Path(self.luks_dev_path).exists() is False and time.time() - wait_timer < 10:
			time.sleep(0.025)

		SysCommand(f'/usr/bin/cryptsetup open {self.luks_dev_path} {self.mapper_name} --key-file {key_file} --type luks2')

		if not self.mapper_dev or not self.mapper_dev.is_symlink():
			raise DiskError(f'Failed to open luks2 device: {self.luks_dev_path}')

	def lock(self):
		disk.device_handler.umount(self.luks_dev_path)

		# Get crypt-information about the device by doing a reverse lookup starting with the partition path
		# For instance: /dev/sda
		lsblk_info = disk.get_lsblk_info(self.luks_dev_path)

		# For each child (sub-partition/sub-device)
		for child in lsblk_info.children:
			# Unmount the child location
			for mountpoint in child.mountpoints:
				debug(f'Unmounting {mountpoint}')
				disk.device_handler.umount(mountpoint, recursive=True)

			# And close it if possible.
			debug(f"Closing crypt device {child.name}")
			SysCommand(f"cryptsetup close {child.name}")

		self._mapper_dev = None

	def create_keyfile(self, target_path: Path, override: bool = False):
		"""
		Routine to create keyfiles, so it can be moved elsewhere
		"""
		if self.mapper_name is None:
			raise ValueError('Mapper name must be provided')

		# Once we store the key as ../xyzloop.key systemd-cryptsetup can
		# automatically load this key if we name the device to "xyzloop"
		kf_path = Path(f'/etc/cryptsetup-keys.d/{self.mapper_name}.key')
		key_file = target_path / kf_path.relative_to(kf_path.root)
		crypttab_path = target_path / 'etc/crypttab'

		if key_file.exists():
			if not override:
				info(f'Key file {key_file} already exists, keeping existing')
				return
			else:
				info(f'Key file {key_file} already exists, overriding')

		key_file.parent.mkdir(parents=True, exist_ok=True)

		with open(key_file, "w") as keyfile:
			keyfile.write(generate_password(length=512))

		key_file.chmod(0o400)

		self._add_key(key_file)
		self._crypttab(crypttab_path, kf_path, options=["luks", "key-slot=1"])

	def _add_key(self, key_file: Path):
		info(f'Adding additional key-file {key_file}')

		command = f'/usr/bin/cryptsetup -q -v luksAddKey {self.luks_dev_path} {key_file}'
		worker = SysCommandWorker(command, environment_vars={'LC_ALL': 'C'})
		pw_injected = False

		while worker.is_alive():
			if b'Enter any existing passphrase' in worker and pw_injected is False:
				worker.write(self._password_bytes())
				pw_injected = True

		if worker.exit_code != 0:
			raise DiskError(f'Could not add encryption key {key_file} to {self.luks_dev_path}: {worker.decode()}')

	def _crypttab(
		self,
		crypttab_path: Path,
		key_file: Path,
		options: List[str]
	) -> None:
		info(f'Adding crypttab entry for key {key_file}')

		with open(crypttab_path, 'a') as crypttab:
			opt = ','.join(options)
			uuid = self._get_luks_uuid()
			row = f"{self.mapper_name} UUID={uuid} {key_file} {opt}\n"
			crypttab.write(row)
