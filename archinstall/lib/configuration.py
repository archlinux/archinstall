import os
import json
import stat
import logging
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING

from .menu import Menu, MenuSelectionType
from .storage import storage
from .general import JSON, UNSAFE_JSON, SysCommand
from .output import log

if TYPE_CHECKING:
	_: Any


class ConfigurationOutput:
	def __init__(self, config: Dict):
		"""
		Configuration output handler to parse the existing configuration data structure and prepare for output on the
		console and for saving it to configuration files

		:param config: A dictionary containing configurations (basically archinstall.arguments)
		:type config: Dict
		"""
		self._config = config
		self._user_credentials: Dict[str, Any] = {}
		self._user_config: Dict[str, Any] = {}
		self._default_save_path = Path(storage.get('LOG_PATH', '.'))
		self._user_config_file = 'user_configuration.json'
		self._user_creds_file = "user_credentials.json"

		self._sensitive = ['!users']
		self._ignore = ['abort', 'install', 'config', 'creds', 'dry_run']

		self._process_config()

	@property
	def user_credentials_file(self):
		return self._user_creds_file

	@property
	def user_configuration_file(self):
		return self._user_config_file

	def _process_config(self):
		for key in self._config:
			if key in self._sensitive:
				self._user_credentials[key] = self._config[key]
			elif key in self._ignore:
				pass
			else:
				self._user_config[key] = self._config[key]

			# special handling for encryption password
			if key == 'disk_encryption' and self._config[key] is not None:
				self._user_credentials['encryption_password'] = self._config[key].encryption_password

	def user_config_to_json(self) -> str:
		return json.dumps({
			'config_version': storage['__version__'],  # Tells us what version was used to generate the config
			**self._user_config,  # __version__ will be overwritten by old version definition found in config
			'version': storage['__version__']
		}, indent=4, sort_keys=True, cls=JSON)

	def user_credentials_to_json(self) -> Optional[str]:
		if self._user_credentials:
			return json.dumps(self._user_credentials, indent=4, sort_keys=True, cls=UNSAFE_JSON)
		return None

	def show(self):
		print(_('\nThis is your chosen configuration:'))
		log(" -- Chosen configuration --", level=logging.DEBUG)

		user_conig = self.user_config_to_json()
		log(user_conig, level=logging.INFO)

		print()

	def _is_valid_path(self, dest_path: Path) -> bool:
		if (not dest_path.exists()) or not (dest_path.is_dir()):
			log(
				'Destination directory {} does not exist or is not a directory,\n Configuration files can not be saved'.format(dest_path.resolve()),
				fg="yellow"
			)
			return False
		return True

	def save_user_config(self, dest_path: Path):
		if self._is_valid_path(dest_path):
			target = dest_path / self._user_config_file

			with open(target, 'w') as config_file:
				config_file.write(self.user_config_to_json())

			os.chmod(str(dest_path / self._user_config_file), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

	def save_user_creds(self, dest_path: Path):
		if self._is_valid_path(dest_path):
			if user_creds := self.user_credentials_to_json():
				target = dest_path / self._user_creds_file

				with open(target, 'w') as config_file:
					config_file.write(user_creds)

				os.chmod(str(target), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

	def save(self, dest_path: Optional[Path] = None):
		if not dest_path:
			dest_path = self._default_save_path

		if self._is_valid_path(dest_path):
			self.save_user_config(dest_path)
			self.save_user_creds(dest_path)


def save_config(config: Dict):
	def preview(selection: str):
		if options['user_config'] == selection:
			serialized = config_output.user_config_to_json()
			return f'{config_output.user_configuration_file}\n{serialized}'
		elif options['user_creds'] == selection:
			if maybe_serial := config_output.user_credentials_to_json():
				return f'{config_output.user_credentials_file}\n{maybe_serial}'
			else:
				return str(_('No configuration'))
		elif options['all'] == selection:
			output = f'{config_output.user_configuration_file}\n'
			if config_output.user_credentials_to_json():
				output += f'{config_output.user_credentials_file}\n'
			return output[:-1]
		return None

	config_output = ConfigurationOutput(config)

	options = {
		'user_config': str(_('Save user configuration')),
		'user_creds': str(_('Save user credentials')),
		'disk_layout': str(_('Save disk layout')),
		'all': str(_('Save all'))
	}

	choice = Menu(
		_('Choose which configuration to save'),
		list(options.values()),
		sort=False,
		skip=True,
		preview_size=0.75,
		preview_command=preview
	).run()

	if choice.type_ == MenuSelectionType.Skip:
		return

	save_config_value = choice.single_value
	saving_key = [k for k, v in options.items() if v == save_config_value][0]

	dirs_to_exclude = [
		'/bin',
		'/dev',
		'/lib',
		'/lib64',
		'/lost+found',
		'/opt',
		'/proc',
		'/run',
		'/sbin',
		'/srv',
		'/sys',
		'/usr',
		'/var',
	]

	log('Ignore configuration option folders: ' + ','.join(dirs_to_exclude), level=logging.DEBUG)
	log(_('Finding possible directories to save configuration files ...'), level=logging.INFO)

	find_exclude = '-path ' + ' -prune -o -path '.join(dirs_to_exclude) + ' -prune '
	file_picker_command = f'find / {find_exclude} -o -type d -print0'

	directories = SysCommand(file_picker_command).decode()

	if directories is None:
		raise ValueError('Failed to retrieve possible configuration directories')

	possible_save_dirs = list(filter(None, directories.split('\x00')))

	selection = Menu(
		_('Select directory (or directories) for saving configuration files'),
		possible_save_dirs,
		multi=True,
		skip=True,
		allow_reset=False,
	).run()

	match selection.type_:
		case MenuSelectionType.Skip:
			return

	save_dirs = selection.multi_value

	log(f'Saving {saving_key} configuration files to {save_dirs}', level=logging.DEBUG)

	if save_dirs is not None:
		for save_dir_str in save_dirs:
			save_dir = Path(save_dir_str)
			if options['user_config'] == save_config_value:
				config_output.save_user_config(save_dir)
			elif options['user_creds'] == save_config_value:
				config_output.save_user_creds(save_dir)
			elif options['all'] == save_config_value:
				config_output.save_user_config(save_dir)
				config_output.save_user_creds(save_dir)
