import os
import json
import stat
import logging
import pathlib
from typing import Optional, Dict

from .storage import storage
from .general import JSON, UNSAFE_JSON
from .output import log
from .exceptions import RequirementError
from .hsm import get_fido2_devices

def configuration_sanity_check():
	if storage['arguments'].get('HSM'):
		if not get_fido2_devices():
			raise RequirementError(
				f"In order to use HSM to pair with the disk encryption,"
				+ f" one needs to be accessible through /dev/hidraw* and support"
				+ f" the FIDO2 protocol. You can check this by running"
				+ f" 'systemd-cryptenroll --fido2-device=list'."
			)

class ConfigurationOutput:
	def __init__(self, config: Dict):
		"""
		Configuration output handler to parse the existing configuration data structure and prepare for output on the
		console and for saving it to configuration files

		:param config: A dictionary containing configurations (basically archinstall.arguments)
		:type config: Dict
		"""
		self._config = config
		self._user_credentials = {}
		self._disk_layout = None
		self._user_config = {}
		self._default_save_path = pathlib.Path(storage.get('LOG_PATH', '.'))
		self._user_config_file = 'user_configuration.json'
		self._user_creds_file = "user_credentials.json"
		self._disk_layout_file = "user_disk_layout.json"

		self._sensitive = ['!users', '!encryption-password']
		self._ignore = ['abort', 'install', 'config', 'creds', 'dry_run']

		self._process_config()

	@property
	def user_credentials_file(self):
		return self._user_creds_file

	@property
	def user_configuration_file(self):
		return self._user_config_file

	@property
	def disk_layout_file(self):
		return self._disk_layout_file

	def _process_config(self):
		for key in self._config:
			if key in self._sensitive:
				self._user_credentials[key] = self._config[key]
			elif key == 'disk_layouts':
				self._disk_layout = self._config[key]
			elif key in self._ignore:
				pass
			else:
				self._user_config[key] = self._config[key]

	def user_config_to_json(self) -> str:
		return json.dumps({
			'config_version': storage['__version__'],  # Tells us what version was used to generate the config
			**self._user_config,  # __version__ will be overwritten by old version definition found in config
			'version': storage['__version__']
		}, indent=4, sort_keys=True, cls=JSON)

	def disk_layout_to_json(self) -> Optional[str]:
		if self._disk_layout:
			return json.dumps(self._disk_layout, indent=4, sort_keys=True, cls=JSON)
		return None

	def user_credentials_to_json(self) -> Optional[str]:
		if self._user_credentials:
			return json.dumps(self._user_credentials, indent=4, sort_keys=True, cls=UNSAFE_JSON)
		return None

	def show(self):
		print(_('\nThis is your chosen configuration:'))
		log(" -- Chosen configuration --", level=logging.DEBUG)

		user_conig = self.user_config_to_json()
		disk_layout = self.disk_layout_to_json()
		log(user_conig, level=logging.INFO)

		if disk_layout:
			log(disk_layout, level=logging.INFO)

		print()

	def _is_valid_path(self, dest_path :pathlib.Path) -> bool:
		if (not dest_path.exists()) or not (dest_path.is_dir()):
			log(
				'Destination directory {} does not exist or is not a directory,\n Configuration files can not be saved'.format(dest_path.resolve()),
				fg="yellow"
			)
			return False
		return True

	def save_user_config(self, dest_path :pathlib.Path = None):
		if self._is_valid_path(dest_path):
			target = dest_path / self._user_config_file

			with open(target, 'w') as config_file:
				config_file.write(self.user_config_to_json())

			os.chmod(str(dest_path / self._user_config_file), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

	def save_user_creds(self, dest_path :pathlib.Path = None):
		if self._is_valid_path(dest_path):
			if user_creds := self.user_credentials_to_json():
				target = dest_path / self._user_creds_file

				with open(target, 'w') as config_file:
					config_file.write(user_creds)

				os.chmod(str(target), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

	def save_disk_layout(self, dest_path :pathlib.Path = None):
		if self._is_valid_path(dest_path):
			if disk_layout := self.disk_layout_to_json():
				target = dest_path / self._disk_layout_file

				with target.open('w') as config_file:
					config_file.write(disk_layout)

				os.chmod(str(target), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

	def save(self, dest_path :pathlib.Path = None):
		if not dest_path:
			dest_path = self._default_save_path

		if self._is_valid_path(dest_path):
			self.save_user_config(dest_path)
			self.save_user_creds(dest_path)
			self.save_disk_layout(dest_path)
