import json
import readline
import stat
from pathlib import Path
from typing import TYPE_CHECKING, Any

from archinstall.tui import Alignment, FrameProperties, MenuItem, MenuItemGroup, Orientation, PreviewStyle, ResultType, SelectMenu, Tui

from .general import JSON, UNSAFE_JSON
from .output import debug, warn
from .storage import storage
from .utils.util import prompt_dir

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


class ConfigurationOutput:
	def __init__(self, config: dict[str, Any]):
		"""
		Configuration output handler to parse the existing configuration data structure and prepare for output on the
		console and for saving it to configuration files

		:param config: A dictionary containing configurations (basically archinstall.arguments)
		:type config: dict
		"""
		self._config = config
		self._user_credentials: dict[str, Any] = {}
		self._user_config: dict[str, Any] = {}
		self._default_save_path = storage.get('LOG_PATH', Path('.'))
		self._user_config_file = 'user_configuration.json'
		self._user_creds_file = "user_credentials.json"

		self._sensitive = ['!users', '!root-password']
		self._ignore = ['abort', 'install', 'config', 'creds', 'dry_run']

		self._process_config()

	@property
	def user_credentials_file(self) -> str:
		return self._user_creds_file

	@property
	def user_configuration_file(self) -> str:
		return self._user_config_file

	def _process_config(self) -> None:
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

	def user_credentials_to_json(self) -> str | None:
		if self._user_credentials:
			return json.dumps(self._user_credentials, indent=4, sort_keys=True, cls=UNSAFE_JSON)
		return None

	def write_debug(self) -> None:
		debug(" -- Chosen configuration --")
		debug(self.user_config_to_json())

	def confirm_config(self) -> bool:
		header = f'{_("The specified configuration will be applied")}. '
		header += str(_('Would you like to continue?')) + '\n'

		with Tui():
			group = MenuItemGroup.yes_no()
			group.focus_item = MenuItem.yes()
			group.set_preview_for_all(lambda x: self.user_config_to_json())

			result = SelectMenu(
				group,
				header=header,
				alignment=Alignment.CENTER,
				columns=2,
				orientation=Orientation.HORIZONTAL,
				allow_skip=False,
				preview_size='auto',
				preview_style=PreviewStyle.BOTTOM,
				preview_frame=FrameProperties.max(str(_('Configuration')))
			).run()

			if result.item() != MenuItem.yes():
				return False

		return True

	def _is_valid_path(self, dest_path: Path) -> bool:
		dest_path_ok = dest_path.exists() and dest_path.is_dir()
		if not dest_path_ok:
			warn(
				f'Destination directory {dest_path.resolve()} does not exist or is not a directory\n.',
				'Configuration files can not be saved'
			)
		return dest_path_ok

	def save_user_config(self, dest_path: Path) -> None:
		if self._is_valid_path(dest_path):
			target = dest_path / self._user_config_file
			target.write_text(self.user_config_to_json())
			target.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

	def save_user_creds(self, dest_path: Path) -> None:
		if self._is_valid_path(dest_path):
			if user_creds := self.user_credentials_to_json():
				target = dest_path / self._user_creds_file
				target.write_text(user_creds)
				target.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

	def save(self, dest_path: Path | None = None) -> None:
		save_path = dest_path or self._default_save_path

		if self._is_valid_path(save_path):
			self.save_user_config(save_path)
			self.save_user_creds(save_path)


def save_config(config: dict[str, Any]) -> None:
	def preview(item: MenuItem) -> str | None:
		match item.value:
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

	config_output = ConfigurationOutput(config)

	items = [
		MenuItem(
			str(_("Save user configuration (including disk layout)")),
			value="user_config",
			preview_action=preview
		),
		MenuItem(
			str(_("Save user credentials")),
			value="user_creds",
			preview_action=preview
		),
		MenuItem(
			str(_("Save all")),
			value="all",
			preview_action=preview
		)
	]

	group = MenuItemGroup(items)
	result = SelectMenu(
		group,
		allow_skip=True,
		preview_frame=FrameProperties.max(str(_('Configuration'))),
		preview_size='auto',
		preview_style=PreviewStyle.RIGHT
	).run()

	match result.type_:
		case ResultType.Skip:
			return
		case ResultType.Selection:
			save_option = result.get_value()
		case _:
			raise ValueError('Unhandled return type')

	readline.set_completer_delims("\t\n=")
	readline.parse_and_bind("tab: complete")

	dest_path = prompt_dir(
		str(_('Directory')),
		str(_('Enter a directory for the configuration(s) to be saved (tab completion enabled)')) + '\n',
		allow_skip=True
	)

	if not dest_path:
		return

	header = str(_("Do you want to save the configuration file(s) to {}?")).format(dest_path)

	group = MenuItemGroup.yes_no()
	group.focus_item = MenuItem.yes()

	result = SelectMenu(
		group,
		header=header,
		allow_skip=False,
		alignment=Alignment.CENTER,
		columns=2,
		orientation=Orientation.HORIZONTAL
	).run()

	match result.type_:
		case ResultType.Selection:
			if result.item() == MenuItem.no():
				return

	debug(f"Saving configuration files to {dest_path.absolute()}")

	match save_option:
		case "user_config":
			config_output.save_user_config(dest_path)
		case "user_creds":
			config_output.save_user_creds(dest_path)
		case "all":
			config_output.save(dest_path)
