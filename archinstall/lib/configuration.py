import os
import json
import stat
import readline
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING

from .menu import Menu, MenuSelectionType
from .storage import storage
from .general import JSON, UNSAFE_JSON
from .output import debug, info, warn

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

		self._sensitive = ['!users', '!root-password']
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
		debug(" -- Chosen configuration --")

		user_conig = self.user_config_to_json()
		info(user_conig)

		print()

	def _is_valid_path(self, dest_path: Path) -> bool:
		if (not dest_path.exists()) or not (dest_path.is_dir()):
			warn(
				f'Destination directory {dest_path.resolve()} does not exist or is not a directory\n.',
				'Configuration files can not be saved'
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
		if options["user_config"] == selection:
			serialized = config_output.user_config_to_json()
			return f"{config_output.user_configuration_file}\n{serialized}"
		elif options["user_creds"] == selection:
			if maybe_serial := config_output.user_credentials_to_json():
				return f"{config_output.user_credentials_file}\n{maybe_serial}"
			else:
				return str(_("No configuration"))
		elif options["all"] == selection:
			output = f"{config_output.user_configuration_file}\n"
			if config_output.user_credentials_to_json():
				output += f"{config_output.user_credentials_file}\n"
			return output[:-1]
		return None

	try:
		config_output = ConfigurationOutput(config)

		options = {
			"user_config": str(_("Save user configuration (including disk layout)")),
			"user_creds": str(_("Save user credentials")),
			"all": str(_("Save all")),
		}

		save_choice = Menu(
			_("Choose which configuration to save"),
			list(options.values()),
			sort=False,
			skip=True,
			preview_size=0.75,
			preview_command=preview,
		).run()

		if save_choice.type_ == MenuSelectionType.Skip:
			return

		readline.set_completer_delims("\t\n=")
		readline.parse_and_bind("tab: complete")
		while True:
			path = input(
				_(
					"Enter a directory for the configuration(s) to be saved (tab completion enabled)\nSave directory: "
				)
			).strip(" ")
			dest_path = Path(path)
			if dest_path.exists() and dest_path.is_dir():
				break
			info(_("Not a valid directory: {}").format(dest_path), fg="red")

		if not path:
			return

		prompt = _(
			"Do you want to save {} configuration file(s) in the following location?\n\n{}"
		).format(
			list(options.keys())[list(options.values()).index(str(save_choice.value))],
			dest_path.absolute(),
		)
		save_confirmation = Menu(prompt, Menu.yes_no(), default_option=Menu.yes()).run()
		if save_confirmation == Menu.no():
			return

		debug(
			_("Saving {} configuration files to {}").format(
				list(options.keys())[list(options.values()).index(str(save_choice.value))],
				dest_path.absolute(),
			)
		)

		if options["user_config"] == save_choice.value:
			config_output.save_user_config(dest_path)
		elif options["user_creds"] == save_choice.value:
			config_output.save_user_creds(dest_path)
		elif options["all"] == save_choice.value:
			config_output.save_user_config(dest_path)
			config_output.save_user_creds(dest_path)
	except KeyboardInterrupt:
		return
