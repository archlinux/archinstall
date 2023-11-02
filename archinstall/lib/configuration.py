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
		self._default_save_path = storage.get('LOG_PATH', Path('.'))
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
		for key, value in self._config.items():
			if key in self._sensitive:
				self._user_credentials[key] = value
			elif key in self._ignore:
				pass
			else:
				self._user_config[key] = value

			# special handling for encryption password
			if key == 'disk_encryption' and value:
				self._user_credentials['encryption_password'] = value.encryption_password

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

		info(self.user_config_to_json())
		print()

	def _is_valid_path(self, dest_path: Path) -> bool:
		dest_path_ok = dest_path.exists() and dest_path.is_dir()
		if not dest_path_ok:
			warn(
				f'Destination directory {dest_path.resolve()} does not exist or is not a directory\n.',
				'Configuration files can not be saved'
			)
		return dest_path_ok

	def save_user_config(self, dest_path: Path):
		if self._is_valid_path(dest_path):
			target = dest_path / self._user_config_file
			target.write_text(self.user_config_to_json())
			os.chmod(target, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

	def save_user_creds(self, dest_path: Path):
		if self._is_valid_path(dest_path):
			if user_creds := self.user_credentials_to_json():
				target = dest_path / self._user_creds_file
				target.write_text(user_creds)
				os.chmod(target, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

	def save(self, dest_path: Optional[Path] = None):
		dest_path = dest_path or self._default_save_path

		if self._is_valid_path(dest_path):
			self.save_user_config(dest_path)
			self.save_user_creds(dest_path)


def save_config(config: Dict):
	def preview(selection: str):
		match options[selection]:
			case "user_config":
				serialized = config_output.user_config_to_json()
				return f"{config_output.user_configuration_file}\n{serialized}"
			case "user_creds":
				if maybe_serial := config_output.user_credentials_to_json():
					return f"{config_output.user_credentials_file}\n{maybe_serial}"
				return str(_("No configuration"))
			case "all":
				output = [config_output.user_configuration_file]
				if config_output.user_credentials_to_json():
					output.append(config_output.user_credentials_file)
				return '\n'.join(output)
		return None

	try:
		config_output = ConfigurationOutput(config)

		options = {
			str(_("Save user configuration (including disk layout)")): "user_config",
			str(_("Save user credentials")): "user_creds",
			str(_("Save all")): "all",
		}

		save_choice = Menu(
			_("Choose which configuration to save"),
			list(options),
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
		).format(options[str(save_choice.value)], dest_path.absolute())

		save_confirmation = Menu(prompt, Menu.yes_no(), default_option=Menu.yes()).run()
		if save_confirmation == Menu.no():
			return

		debug("Saving {} configuration files to {}".format(options[str(save_choice.value)], dest_path.absolute()))

		match options[str(save_choice.value)]:
			case "user_config":
				config_output.save_user_config(dest_path)
			case "user_creds":
				config_output.save_user_creds(dest_path)
			case "all":
				config_output.save(dest_path)

	except (KeyboardInterrupt, EOFError):
		return
