import json
import readline
import stat
from pathlib import Path

from archinstall.lib.menu.helpers import Confirmation, Selection
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType

from .args import ArchConfig
from .crypt import encrypt
from .general import JSON, UNSAFE_JSON
from .output import debug, logger, warn
from .utils.util import get_password, prompt_dir


class ConfigurationOutput:
	def __init__(self, config: ArchConfig):
		"""
		Configuration output handler to parse the existing
		configuration data structure and prepare for output on the
		console and for saving it to configuration files

		:param config: Archinstall configuration object
		:type config: ArchConfig
		"""

		self._config = config
		self._default_save_path = logger.directory
		self._user_config_file = Path('user_configuration.json')
		self._user_creds_file = Path('user_credentials.json')

	@property
	def user_configuration_file(self) -> Path:
		return self._user_config_file

	@property
	def user_credentials_file(self) -> Path:
		return self._user_creds_file

	def user_config_to_json(self) -> str:
		out = self._config.safe_json()
		return json.dumps(out, indent=4, sort_keys=True, cls=JSON)

	def user_credentials_to_json(self) -> str:
		out = self._config.unsafe_json()
		return json.dumps(out, indent=4, sort_keys=True, cls=UNSAFE_JSON)

	def write_debug(self) -> None:
		debug(' -- Chosen configuration --')
		debug(self.user_config_to_json())

	def confirm_config(self) -> bool:
		header = f'{tr("The specified configuration will be applied")}. '
		header += tr('Would you like to continue?') + '\n'

		group = MenuItemGroup.yes_no()
		group.set_preview_for_all(lambda x: self.user_config_to_json())

		result = Confirmation(
			group=group,
			header=header,
			allow_skip=False,
			preset=True,
			preview_location='bottom',
			preview_header=tr('Configuration preview'),
		).show()

		if not result.get_value():
			return False

		return True

	def _is_valid_path(self, dest_path: Path) -> bool:
		dest_path_ok = dest_path.exists() and dest_path.is_dir()
		if not dest_path_ok:
			warn(
				f'Destination directory {dest_path.resolve()} does not exist or is not a directory\n.',
				'Configuration files can not be saved',
			)
		return dest_path_ok

	def save_user_config(self, dest_path: Path) -> None:
		if self._is_valid_path(dest_path):
			target = dest_path / self._user_config_file
			target.write_text(self.user_config_to_json())
			target.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

	def save_user_creds(
		self,
		dest_path: Path,
		password: str | None = None,
	) -> None:
		data = self.user_credentials_to_json()

		if password:
			data = encrypt(password, data)

		if self._is_valid_path(dest_path):
			target = dest_path / self._user_creds_file
			target.write_text(data)
			target.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

	def save(
		self,
		dest_path: Path | None = None,
		creds: bool = False,
		password: str | None = None,
	) -> None:
		save_path = dest_path or self._default_save_path

		if self._is_valid_path(save_path):
			self.save_user_config(save_path)
			if creds:
				self.save_user_creds(save_path, password=password)


def save_config(config: ArchConfig) -> None:
	def preview(item: MenuItem) -> str | None:
		match item.value:
			case 'user_config':
				serialized = config_output.user_config_to_json()
				return f'{config_output.user_configuration_file}\n{serialized}'
			case 'user_creds':
				if maybe_serial := config_output.user_credentials_to_json():
					return f'{config_output.user_credentials_file}\n{maybe_serial}'
				return tr('No configuration')
			case 'all':
				output = [str(config_output.user_configuration_file)]
				config_output.user_credentials_to_json()
				output.append(str(config_output.user_credentials_file))
				return '\n'.join(output)
		return None

	config_output = ConfigurationOutput(config)

	items = [
		MenuItem(
			tr('Save user configuration (including disk layout)'),
			value='user_config',
			preview_action=preview,
		),
		MenuItem(
			tr('Save user credentials'),
			value='user_creds',
			preview_action=preview,
		),
		MenuItem(
			tr('Save all'),
			value='all',
			preview_action=preview,
		),
	]

	group = MenuItemGroup(items)
	result = Selection[str](
		group,
		allow_skip=True,
		preview_location='right',
	).show()

	match result.type_:
		case ResultType.Skip:
			return
		case ResultType.Selection:
			save_option = result.get_value()
		case _:
			raise ValueError('Unhandled return type')

	readline.set_completer_delims('\t\n=')
	readline.parse_and_bind('tab: complete')

	dest_path = prompt_dir(
		tr('Enter a directory for the configuration(s) to be saved') + '\n',
		allow_skip=True,
	)

	if not dest_path:
		return

	header = tr('Do you want to save the configuration file(s) to {}?').format(dest_path)

	save_result = Confirmation(
		header=header,
		allow_skip=False,
		preset=True,
	).show()

	match save_result.type_:
		case ResultType.Selection:
			if not save_result.get_value():
				return
		case _:
			return

	debug(f'Saving configuration files to {dest_path.absolute()}')

	header = tr('Do you want to encrypt the user_credentials.json file?')

	enc_result = Confirmation(
		header=header,
		allow_skip=False,
		preset=False,
	).show()

	enc_password: str | None = None
	if enc_result.type_ == ResultType.Selection:
		if enc_result.get_value():
			password = get_password(
				header=tr('Credentials file encryption password'),
				allow_skip=True,
			)

			if password:
				enc_password = password.plaintext

	match save_option:
		case 'user_config':
			config_output.save_user_config(dest_path)
		case 'user_creds':
			config_output.save_user_creds(dest_path, password=enc_password)
		case 'all':
			config_output.save(dest_path, creds=True, password=enc_password)
