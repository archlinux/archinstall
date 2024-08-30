from __future__ import annotations

from typing import Any, List, Optional, Dict, TYPE_CHECKING

from . import disk
from .general import secret
from .hardware import SysInfo
from .locale.locale_menu import LocaleConfiguration, LocaleMenu
from .menu import AbstractMenu
from .mirrors import MirrorConfiguration, MirrorMenu
from .models import NetworkConfiguration, NicType
from .models.bootloader import Bootloader
from .models.audio_configuration import AudioConfiguration
from .models.users import User
from .output import FormattedOutput
from .profile.profile_menu import ProfileConfiguration
from .interactions import ask_for_additional_users
from .interactions import (
	ask_for_audio_selection, ask_for_swap,
	ask_for_bootloader, ask_for_uki, ask_hostname,
	add_number_of_parallel_downloads, select_kernel,
	ask_additional_packages_to_install, select_additional_repositories,
	ask_for_a_timezone, ask_ntp, ask_to_configure_network
)
from .utils.util import get_password
from .utils.util import format_cols
from .configuration import save_config

from archinstall.tui import (
	MenuItemGroup, MenuItem
)


from .translationhandler import Language, TranslationHandler

if TYPE_CHECKING:
	_: Any


class GlobalMenu(AbstractMenu):
	def __init__(self, data_store: Dict[str, Any]):
		self._data_store = data_store
		self._translation_handler = TranslationHandler()

		if 'archinstall-language' not in data_store:
			data_store['archinstall-language'] = self._translation_handler.get_language_by_abbr('en')

		menu_optioons = self._get_menu_options(data_store)
		self._item_group = MenuItemGroup(
			menu_optioons,
			sort_items=False,
			checkmarks=True
		)

		super().__init__(self._item_group, data_store)

	def _get_menu_options(self, data_store: Dict[str, Any]) -> List[MenuItem]:
		return [
			MenuItem(
				text=str(_('Archinstall language')),
				action=lambda x: self._select_archinstall_language(x),
				display_action=lambda x: x.display_name if x else '',
				key='archinstall-language'
			),
			MenuItem(
				text=str(_('Locales')),
				action=lambda x: self._locale_selection(x),
				preview_action=self._prev_locale,
				key='locale_config'
			),
			MenuItem(
				text=str(_('Mirrors')),
				action=lambda x: self._mirror_configuration(x),
				preview_action=self._prev_mirror_config,
				key='mirror_config'
			),
			MenuItem(
				text=str(_('Disk configuration')),
				action=lambda x: self._select_disk_config(x),
				preview_action=self._prev_disk_config,
				mandatory=True,
				key='disk_config'
			),
			MenuItem(
				text=str(_('Disk encryption')),
				action=lambda x: self._disk_encryption(x),
				preview_action=self._prev_disk_encryption,
				key='disk_encryption',
				dependencies=['disk_config']
			),
			MenuItem(
				text=str(_('Swap')),
				value=True,
				action=lambda x: ask_for_swap(x),
				preview_action=self._prev_swap,
				key='swap',
			),
			MenuItem(
				text=str(_('Bootloader')),
				value=Bootloader.get_default(),
				action=lambda x: self._select_bootloader(x),
				preview_action=self._prev_bootloader,
				mandatory=True,
				key='bootloader',
			),
			MenuItem(
				text=str(_('Unified kernel images')),
				value=False,
				action=lambda x: ask_for_uki(x),
				preview_action=self._prev_uki,
				key='uki',
			),
			MenuItem(
				text=str(_('Hostname')),
				value='archlinux',
				action=lambda x: ask_hostname(x),
				preview_action=self._prev_hostname,
				key='hostname',
			),
			MenuItem(
				text=str(_('Root password')),
				action=lambda x: self._set_root_password(x),
				preview_action=self._prev_root_pwd,
				key='!root-password',
			),
			MenuItem(
				text=str(_('User account')),
				action=lambda x: self._create_user_account(x),
				preview_action=self._prev_users,
				key='!users'
			),
			MenuItem(
				text=str(_('Profile')),
				action=lambda x: self._select_profile(x),
				preview_action=self._prev_profile,
				key='profile_config'
			),
			MenuItem(
				text=str(_('Audio')),
				action=lambda x: ask_for_audio_selection(x),
				preview_action=self._prev_audio,
				key='audio_config'
			),
			MenuItem(
				text=str(_('Kernels')),
				value=['linux'],
				action=lambda x: select_kernel(x),
				preview_action=self._prev_kernel,
				mandatory=True,
				key='kernels'
			),
			MenuItem(
				text=str(_('Network configuration')),
				action=lambda x: ask_to_configure_network(x),
				value={},
				preview_action=self._prev_network_config,
				key='network_config'
			),
			MenuItem(
				text=str(_('Parallel Downloads')),
				action=lambda x: add_number_of_parallel_downloads(x),
				value=0,
				preview_action=self._prev_parallel_dw,
				key='parallel downloads'
			),
			MenuItem(
				text=str(_('Additional packages')),
				action=lambda x: ask_additional_packages_to_install(x),
				value=[],
				preview_action=self._prev_additional_pkgs,
				key='packages'
			),
			MenuItem(
				text=str(_('Optional repositories')),
				action=lambda x: select_additional_repositories(x),
				value=[],
				preview_action=self._prev_additional_repos,
				key='additional-repositories'
			),
			MenuItem(
				text=str(_('Timezone')),
				action=lambda x: ask_for_a_timezone(x),
				value='UTC',
				preview_action=self._prev_tz,
				key='timezone'
			),
			MenuItem(
				text=str(_('Automatic time sync (NTP)')),
				action=lambda x: ask_ntp(x),
				value=True,
				preview_action=self._prev_ntp,
				key='ntp'
			),
			MenuItem(
				text=''
			),
			MenuItem(
				text=str(_('Save configuration')),
				action=lambda x: self._safe_config(),
				key='save_config'
			),
			MenuItem(
				text=str(_('Install')),
				preview_action=self._prev_install_invalid_config,
				key='install'
			),
			MenuItem(
				text=str(_('Abort')),
				action=lambda x: exit(1),
				key='abort'
			)
		]

	def _safe_config(self) -> None:
		data = {}
		for item in self._item_group.items:
			data[item.key] = item.value

		save_config(data)

	def _missing_configs(self) -> List[str]:
		def check(s) -> bool:
			item = self._item_group.find_by_key(s)
			return item.has_value()

		def has_superuser() -> bool:
			item = self._item_group.find_by_key('!users')

			from .output import debug

			debug(item)
			if item.has_value():
				users = item.value
				return any([u.sudo for u in users])
			return False

		missing = set()

		for item in self._item_group.items:
			if item.key in ['!root-password', '!users']:
				if not check('!root-password') and not has_superuser():
					missing.add(
						str(_('Either root-password or at least 1 user with sudo privileges must be specified'))
					)
			elif item.mandatory:
				if not check(item.key):
					missing.add(item.text)

		return list(missing)

	def _is_config_valid(self) -> bool:
		"""
		Checks the validity of the current configuration.
		"""
		if len(self._missing_configs()) != 0:
			return False
		return self._validate_bootloader() is None

	def _select_archinstall_language(self, preset: Language) -> Language:
		from .interactions.general_conf import select_archinstall_language
		language = select_archinstall_language(self._translation_handler.translated_languages, preset)
		self._translation_handler.activate(language)

		self._upate_lang_text()

		return language

	def _upate_lang_text(self) -> None:
		"""
		The options for the global menu are generated with a static text;
		each entry of the menu needs to be updated with the new translation
		"""
		new_options = self._get_menu_options(self._data_store)

		for o in new_options:
			self._item_group.find_by_key(o.key).text = o.text

	def _disk_encryption(self, preset: Optional[disk.DiskEncryption]) -> Optional[disk.DiskEncryption]:
		disk_config: Optional[disk.DiskLayoutConfiguration] = self._item_group.find_by_key('disk_config').value

		if not disk_config:
			# this should not happen as the encryption menu has the disk_config as dependency
			raise ValueError('No disk layout specified')

		if not disk.DiskEncryption.validate_enc(disk_config):
			return None

		disk_encryption = disk.DiskEncryptionMenu(disk_config, preset=preset).run()
		return disk_encryption

	def _locale_selection(self, preset: LocaleConfiguration) -> LocaleConfiguration:
		locale_config = LocaleMenu(preset).run()
		return locale_config

	def _prev_locale(self, item: MenuItem) -> Optional[str]:
		if not item.value:
			return

		config: LocaleConfiguration = item.value
		return config.preview()

	def _prev_network_config(self, item: MenuItem) -> Optional[str]:
		if item.value:
			network_config: NetworkConfiguration = item.value
			if network_config.type == NicType.MANUAL:
				output = FormattedOutput.as_table(network_config.nics)
			else:
				output = f'{str(_('Network configuration'))}:\n{network_config.type.display_msg()}'

			return output
		return None

	def _prev_additional_pkgs(self, item: MenuItem) -> Optional[str]:
		if item.value:
			return format_cols(item.value, None)
		return None

	def _prev_additional_repos(self, item: MenuItem) -> Optional[str]:
		if item.value:
			repos = ', '.join(item.value)
			return f'{str(_("Additional repositories"))}: {repos}'
		return None

	def _prev_tz(self, item: MenuItem) -> Optional[str]:
		if item.value:
			return f'{str(_("Timezone"))}: {item.value}'
		return None

	def _prev_ntp(self, item: MenuItem) -> Optional[str]:
		if item.value is not None:
			output = f'{str(_("NTP"))}: '
			output += str(_('Enabled')) if item.value else str(_('Disabled'))
			return output
		return None

	def _prev_disk_config(self, item: MenuItem) -> Optional[str]:
		disk_layout_conf: Optional[disk.DiskLayoutConfiguration] = item.value

		if disk_layout_conf:
			output = str(_('Configuration type: {}')).format(disk_layout_conf.config_type.display_msg())

			if disk_layout_conf.lvm_config:
				output += '\n{}: {}'.format(str(_('LVM configuration type')), disk_layout_conf.lvm_config.config_type.display_msg())

			return output

		return None

	def _prev_swap(self, item: MenuItem) -> Optional[str]:
		if item.value is not None:
			output = f'{str(_("Swap on zram"))}: '
			output += str(_('Enabled')) if item.value else str(_('Disabled'))
			return output
		return None

	def _prev_uki(self, item: MenuItem) -> Optional[str]:
		if item.value is not None:
			output = f'{str(_('Unified kernel images'))}: '
			output += str(_('Enabled')) if item.value else str(_('Disabled'))
			return output
		return None

	def _prev_hostname(self, item: MenuItem) -> Optional[str]:
		if item.value is not None:
			return f'{str(_("Hostname"))}: {item.value}'
		return None

	def _prev_root_pwd(self, item: MenuItem) -> Optional[str]:
		if item.value is not None:
			return f'{str(_("Root password"))}: {secret(item.value)}'
		return None

	def _prev_audio(self, item: MenuItem) -> Optional[str]:
		if item.value is not None:
			config: AudioConfiguration = item.value
			return f'{str(_("Audio"))}: {config.audio.value}'
		return None

	def _prev_parallel_dw(self, item: MenuItem) -> Optional[str]:
		if item.value is not None:
			return f'{str(_("Parallel Downloads"))}: {item.value}'
		return None

	def _prev_kernel(self, item: MenuItem) -> Optional[str]:
		if item.value is not None:
			from archinstall.lib.output import debug
			debug(item.value)
			kernel = ', '.join(item.value)
			return f'{str(_("Kernel"))}: {kernel}'
		return None

	def _prev_bootloader(self, item: MenuItem) -> Optional[str]:
		if item.value is not None:
			return f'{str(_("Bootloader"))}: {item.value.value}'
		return None

	def _prev_disk_encryption(self, item: MenuItem) -> Optional[str]:
		disk_config: Optional[disk.DiskLayoutConfiguration] = self._item_group.find_by_key('disk_config').value
		enc_config: Optional[disk.DiskEncryption] = item.value

		if disk_config and not disk.DiskEncryption.validate_enc(disk_config):
			return str(_('LVM disk encryption with more than 2 partitions is currently not supported'))

		if enc_config:
			enc_type = disk.EncryptionType.type_to_text(enc_config.encryption_type)
			output = str(_('Encryption type')) + f': {enc_type}\n'
			output += str(_('Password')) + f': {secret(enc_config.encryption_password)}\n'

			if enc_config.partitions:
				output += 'Partitions: {} selected'.format(len(enc_config.partitions)) + '\n'
			elif enc_config.lvm_volumes:
				output += 'LVM volumes: {} selected'.format(len(enc_config.lvm_volumes)) + '\n'

			if enc_config.hsm_device:
				output += f'HSM: {enc_config.hsm_device.manufacturer}'

			return output

		return None

	def _validate_bootloader(self) -> Optional[str]:
		"""
		Checks the selected bootloader is valid for the selected filesystem
		type of the boot partition.

		Returns [`None`] if the bootloader is valid, otherwise returns a
		string with the error message.

		XXX: The caller is responsible for wrapping the string with the translation
			shim if necessary.
		"""
		bootloader = self._item_group.find_by_key('bootloader').value
		boot_partition: Optional[disk.PartitionModification] = None

		if disk_config := self._item_group.find_by_key('disk_config').value:
			for layout in disk_config.device_modifications:
				if boot_partition := layout.get_boot_partition():
					break
		else:
			return "No disk layout selected"

		if boot_partition is None:
			return "Boot partition not found"

		if bootloader == Bootloader.Limine:
			if boot_partition.fs_type != disk.FilesystemType.Fat32:
				return "Limine does not support booting from filesystems other than FAT32"

		return None

	def _prev_install_invalid_config(self, item: MenuItem) -> Optional[str]:
		if missing := self._missing_configs():
			text = str(_('Missing configurations:\n'))
			for m in missing:
				text += f'- {m}\n'
			return text[:-1]  # remove last new line

		if error := self._validate_bootloader():
			return str(_(f"Invalid configuration: {error}"))

		return None

	def _prev_users(self, item: MenuItem) -> Optional[str]:
		users: Optional[List[User]] = item.value

		if users:
			return FormattedOutput.as_table(users)
		return None

	def _prev_profile(self, item: MenuItem) -> Optional[str]:
		profile_config: Optional[ProfileConfiguration] = item.value

		if profile_config and profile_config.profile:
			output = str(_('Profiles')) + ': '
			if profile_names := profile_config.profile.current_selection_names():
				output += ', '.join(profile_names) + '\n'
			else:
				output += profile_config.profile.name + '\n'

			if profile_config.gfx_driver:
				output += str(_('Graphics driver')) + ': ' + profile_config.gfx_driver.value + '\n'

			if profile_config.greeter:
				output += str(_('Greeter')) + ': ' + profile_config.greeter.value + '\n'

			return output

		return None

	def _set_root_password(self, preset: Optional[str] = None) -> Optional[str]:
		password = get_password(text=str(_('Root password')), allow_skip=True)
		return password

	def _select_disk_config(
		self,
		preset: Optional[disk.DiskLayoutConfiguration] = None
	) -> Optional[disk.DiskLayoutConfiguration]:
		disk_config = disk.DiskLayoutConfigurationMenu(preset).run()

		if disk_config != preset:
			self._menu_item_group.find_by_key('disk_encryption').value = None

		return disk_config

	def _select_bootloader(self, preset: Optional[Bootloader]) -> Optional[Bootloader]:
		bootloader = ask_for_bootloader(preset)

		if bootloader:
			uki = self._item_group.find_by_key('uki')
			if not SysInfo.has_uefi() or not bootloader.has_uki_support():
				uki.value = False
				uki.enabled = False
			else:
				uki.enabled = True

		return bootloader

	def _select_profile(self, current_profile: Optional[ProfileConfiguration]):
		from .profile.profile_menu import ProfileMenu
		profile_config = ProfileMenu(preset=current_profile).run()
		return profile_config

	def _create_user_account(self, preset: Optional[List[User]] = None) -> List[User]:
		preset = [] if preset is None else preset
		users = ask_for_additional_users(defined_users=preset)
		return users

	def _mirror_configuration(self, preset: Optional[MirrorConfiguration] = None) -> Optional[MirrorConfiguration]:
		mirror_configuration = MirrorMenu(preset=preset).run()
		return mirror_configuration

	def _prev_mirror_config(self, item: MenuItem) -> Optional[str]:
		if not item.value:
			return None

		mirror_config: MirrorConfiguration = item.value

		output = ''
		if mirror_config.regions:
			output += '{}: {}\n\n'.format(str(_('Mirror regions')), mirror_config.regions)
		if mirror_config.custom_mirrors:
			table = FormattedOutput.as_table(mirror_config.custom_mirrors)
			output += '{}\n{}'.format(str(_('Custom mirrors')), table)

		return output.strip()

