import json
import readline
import stat
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from archinstall.lib.args import ArchConfig
from archinstall.lib.crypt import encrypt
from archinstall.lib.menu.helpers import Confirmation, Selection
from archinstall.lib.menu.util import get_password, prompt_dir
from archinstall.lib.models.bootloader import Bootloader
from archinstall.lib.models.network import NetworkConfiguration
from archinstall.lib.output import debug, logger, warn
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType


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
		config = self._config.safe_config()

		adapter = TypeAdapter(dict[str, Any])
		python_dict = adapter.dump_python(config)
		return json.dumps(python_dict, indent=4, sort_keys=True)

	def user_credentials_to_json(self) -> str:
		config = self._config.unsafe_config()

		adapter = TypeAdapter(dict[str, Any])
		python_dict = adapter.dump_python(config)
		return json.dumps(python_dict, indent=4, sort_keys=True)

	def write_debug(self) -> None:
		debug(' -- Chosen configuration --')
		debug(self.user_config_to_json())

	def as_summary(self) -> str:
		"""
		Render a concise two-column summary of the current configuration.

		The left column holds section labels, the right column holds values.
		Column width adapts to the longest translated label so translations
		do not break the alignment. Rows whose underlying config is not set
		are skipped.

		Returns an empty string if nothing meaningful to show.
		"""
		rows: list[tuple[str, str]] = []

		disk_config = self._config.disk_config
		if disk_config and disk_config.device_modifications:
			disk_parts: list[str] = []
			for mod in disk_config.device_modifications:
				path = str(mod.device_path)
				root_part = mod.get_root_partition()
				flags: list[str] = []
				if root_part and root_part.fs_type:
					flags.append(root_part.fs_type.value)
				if disk_config.disk_encryption:
					flags.append(tr('LUKS'))
				disk_parts.append(f'{path} ({" + ".join(flags)})' if flags else path)
			rows.append((tr('Disks'), ', '.join(disk_parts)))

		bl_config = self._config.bootloader_config
		if bl_config and bl_config.bootloader != Bootloader.NO_BOOTLOADER:
			rows.append((tr('Bootloader'), bl_config.bootloader.value))

		kernels = self._config.kernels
		if kernels:
			rows.append((tr('Kernel'), ', '.join(kernels)))

		profile_config = self._config.profile_config
		if profile_config and profile_config.profile:
			names = profile_config.profile.current_selection_names()
			rows.append((tr('Profile'), ', '.join(names) if names else profile_config.profile.name))
			if profile_config.greeter:
				rows.append((tr('Greeter'), profile_config.greeter.value))

		packages = self._config.packages
		if packages:
			rows.append((tr('Packages'), str(len(packages))))

		net_config = self._config.network_config
		if isinstance(net_config, NetworkConfiguration):
			rows.append((tr('Network'), net_config.type.display_msg()))

		locale_config = self._config.locale_config
		if locale_config:
			rows.append((tr('Locale'), locale_config.sys_lang))

		tz = self._config.timezone
		if tz:
			rows.append((tr('Timezone'), tz))

		if not rows:
			return ''

		label_width = max(len(label) for label, _ in rows) + 2
		return '\n'.join(f'{label:<{label_width}}{value}' for label, value in rows)

	async def confirm_config(self, show_install_warnings: bool = False) -> bool:
		header = f'{tr("The specified configuration will be applied")}. '
		header += tr('Would you like to continue?') + '\n'

		if show_install_warnings:
			header += self._render_install_warnings()

		group = MenuItemGroup.yes_no()
		group.set_preview_for_all(lambda x: self.user_config_to_json())

		result = await Confirmation(
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

	def get_install_warnings(self) -> list[str]:
		warnings: list[str] = []

		if not isinstance(self._config.network_config, NetworkConfiguration):
			warnings.append(tr('Warning: no network configuration selected. Network will need to be set up manually on the installed system.'))

		return warnings

	def _render_install_warnings(self) -> str:
		warnings = self.get_install_warnings()

		if not warnings:
			return ''

		return '\n' + '\n'.join(f'[yellow]{w}[/]' for w in warnings) + '\n'

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


async def save_config(config: ArchConfig) -> None:
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
	result = await Selection[str](
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

	dest_path = await prompt_dir(
		tr('Enter a directory for the configuration(s) to be saved') + '\n',
		allow_skip=True,
	)

	if not dest_path:
		return

	header = tr('Do you want to save the configuration file(s) to {}?').format(dest_path)

	save_result = await Confirmation(
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

	enc_result = await Confirmation(
		header=header,
		allow_skip=False,
		preset=False,
	).show()

	enc_password: str | None = None
	if enc_result.type_ == ResultType.Selection:
		if enc_result.get_value():
			password = await get_password(
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
