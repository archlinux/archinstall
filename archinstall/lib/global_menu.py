from __future__ import annotations

from typing import Any, List, Optional, Union, Dict, TYPE_CHECKING

from . import disk
from .general import secret
from .menu import Selector, AbstractMenu
from .models import NetworkConfiguration
from .models.bootloader import Bootloader
from .models.users import User
from .output import FormattedOutput
from .profile.profile_menu import ProfileConfiguration
from .storage import storage
from .user_interaction import add_number_of_parrallel_downloads
from .user_interaction import ask_additional_packages_to_install
from .user_interaction import ask_for_additional_users
from .user_interaction import ask_for_audio_selection
from .user_interaction import ask_for_bootloader
from .user_interaction import ask_for_swap
from .user_interaction import ask_hostname
from .user_interaction import ask_to_configure_network
from .user_interaction import get_password, ask_for_a_timezone
from .user_interaction import select_additional_repositories
from .user_interaction import select_kernel
from .user_interaction import select_language
from .user_interaction import select_locale_enc
from .user_interaction import select_locale_lang
from .user_interaction import select_mirror_regions
from .user_interaction.disk_conf import select_disk_config
from .user_interaction.save_conf import save_config

if TYPE_CHECKING:
	_: Any


class GlobalMenu(AbstractMenu):
	def __init__(self, data_store: Dict[str, Any]):
		super().__init__(data_store=data_store, auto_cursor=True, preview_size=0.3)

	def setup_selection_menu_options(self):
		# archinstall.Language will not use preset values
		self._menu_options['archinstall-language'] = \
			Selector(
				_('Archinstall language'),
				lambda x: self._select_archinstall_language(x),
				display_func=lambda x: x.display_name,
				default=self.translation_handler.get_language_by_abbr('en'))
		self._menu_options['keyboard-layout'] = \
			Selector(
				_('Keyboard layout'),
				lambda preset: select_language(preset),
				default='us')
		self._menu_options['mirror-region'] = \
			Selector(
				_('Mirror region'),
				lambda preset: select_mirror_regions(preset),
				display_func=lambda x: list(x.keys()) if x else '[]',
				default={})
		self._menu_options['sys-language'] = \
			Selector(
				_('Locale language'),
				lambda preset: select_locale_lang(preset),
				default='en_US')
		self._menu_options['sys-encoding'] = \
			Selector(
				_('Locale encoding'),
				lambda preset: select_locale_enc(preset),
				default='UTF-8')
		self._menu_options['disk_config'] = \
			Selector(
				_('Disk configuration'),
				lambda preset: self._select_disk_config(preset),
				preview_func=self._prev_disk_layouts,
				display_func=lambda x: self._display_disk_layout(x),
			)
		self._menu_options['disk_encryption'] = \
			Selector(
				_('Disk encryption'),
				lambda preset: self._disk_encryption(preset),
				preview_func=self._prev_disk_encryption,
				display_func=lambda x: self._display_disk_encryption(x),
				dependencies=['disk_config'])
		self._menu_options['swap'] = \
			Selector(
				_('Swap'),
				lambda preset: ask_for_swap(preset),
				default=True)
		self._menu_options['bootloader'] = \
			Selector(
				_('Bootloader'),
				lambda preset: ask_for_bootloader(preset),
				display_func=lambda x: x.value,
				default=Bootloader.get_default())
		self._menu_options['hostname'] = \
			Selector(
				_('Hostname'),
				lambda preset: ask_hostname(preset),
				default='archlinux')
		# root password won't have preset value
		self._menu_options['!root-password'] = \
			Selector(
				_('Root password'),
				lambda preset:self._set_root_password(),
				display_func=lambda x: secret(x) if x else 'None')
		self._menu_options['!users'] = \
			Selector(
				_('User account'),
				lambda x: self._create_user_account(x),
				default={},
				display_func=lambda x: f'{len(x)} {_("User(s)")}' if len(x) > 0 else None,
				preview_func=self._prev_users)
		self._menu_options['profile_config'] = \
			Selector(
				_('Profile'),
				lambda preset: self._select_profile(preset),
				display_func=lambda x: x.profile.name if x else 'None',
				preview_func=self._prev_profile
			)
		self._menu_options['audio'] = \
			Selector(
				_('Audio'),
				lambda preset: self._select_audio(preset),
				display_func=lambda x: x if x else 'None',
				default=None
			)
		self._menu_options['parallel downloads'] = \
			Selector(
				_('Parallel Downloads'),
				add_number_of_parrallel_downloads,
				display_func=lambda x: x if x else '0',
				default=0
			)
		self._menu_options['kernels'] = \
			Selector(
				_('Kernels'),
				lambda preset: select_kernel(preset),
				display_func=lambda x: ', '.join(x) if x else None,
				default=['linux'])
		self._menu_options['packages'] = \
			Selector(
				_('Additional packages'),
				# lambda x: ask_additional_packages_to_install(storage['arguments'].get('packages', None)),
				ask_additional_packages_to_install,
				default=[])
		self._menu_options['additional-repositories'] = \
			Selector(
				_('Optional repositories'),
				select_additional_repositories,
				display_func=lambda x: ', '.join(x) if x else None,
				default=[])
		self._menu_options['nic'] = \
			Selector(
				_('Network configuration'),
				ask_to_configure_network,
				display_func=lambda x: self._display_network_conf(x),
				preview_func=self._prev_network_config,
				default={})
		self._menu_options['timezone'] = \
			Selector(
				_('Timezone'),
				lambda preset: ask_for_a_timezone(preset),
				default='UTC')
		self._menu_options['ntp'] = \
			Selector(
				_('Automatic time sync (NTP)'),
				default=True)
		self._menu_options['__separator__'] = \
			Selector('')
		self._menu_options['save_config'] = \
			Selector(
				_('Save configuration'),
				lambda preset: save_config(self._data_store),
				no_store=True)
		self._menu_options['install'] = \
			Selector(
				self._install_text(),
				exec_func=lambda n,v: True if len(self._missing_configs()) == 0 else False,
				preview_func=self._prev_install_missing_config,
				no_store=True)

		self._menu_options['abort'] = Selector(_('Abort'), exec_func=lambda n,v:exit(1))

	def _update_install_text(self, name: str, value: str):
		text = self._install_text()
		self._menu_options['install'].update_description(text)

	def post_callback(self, name: str, value: str):
		self._update_install_text(name, value)

	def _install_text(self):
		missing = len(self._missing_configs())
		if missing > 0:
			return _('Install ({} config(s) missing)').format(missing)
		return _('Install')

	def _display_network_conf(self, cur_value: Union[NetworkConfiguration, List[NetworkConfiguration]]) -> str:
		if not cur_value:
			return _('Not configured, unavailable unless setup manually')
		else:
			if isinstance(cur_value, list):
				return str(_('Configured {} interfaces')).format(len(cur_value))
			else:
				return str(cur_value)

	def _disk_encryption(self, preset: Optional[disk.DiskEncryption]) -> Optional[disk.DiskEncryption]:
		mods: Optional[List[disk.DeviceModification]] = self._menu_options['disk_config'].current_selection

		if not mods:
			# this should not happen as the encryption menu has the disk_config as dependency
			raise ValueError('No disk layout specified')

		data_store: Dict[str, Any] = {}
		disk_encryption = disk.DiskEncryptionMenu(mods, data_store, preset=preset).run()
		return disk_encryption

	def _prev_network_config(self) -> Optional[str]:
		selector = self._menu_options['nic']
		if selector.has_selection():
			ifaces = selector.current_selection
			if isinstance(ifaces, list):
				return FormattedOutput.as_table(ifaces)
		return None

	def _prev_disk_layouts(self) -> Optional[str]:
		selector = self._menu_options['disk_config']
		disk_layout_conf: Optional[disk.DiskLayoutConfiguration] = selector.current_selection

		if disk_layout_conf:
			device_mods: List[disk.DeviceModification] = \
				list(filter(lambda x: len(x.partitions) > 0, disk_layout_conf.device_modifications))

			if device_mods:
				output_partition = '{}: {}\n'.format(str(_('Configuration')), disk_layout_conf.config_type.display_msg())
				output_btrfs = ''

				for mod in device_mods:
					# create partition table
					partition_table = FormattedOutput.as_table(mod.partitions)

					output_partition += f'{mod.device_path}: {mod.device.device_info.model}\n'
					output_partition += partition_table + '\n'

					# create btrfs table
					btrfs_partitions = list(
						filter(lambda p: len(p.btrfs_subvols) > 0, mod.partitions)
					)
					for partition in btrfs_partitions:
						output_btrfs += FormattedOutput.as_table(partition.btrfs_subvols) + '\n'

				output = output_partition + output_btrfs
				return output.rstrip()

		return None

	def _display_disk_layout(self, current_value: Optional[disk.DiskLayoutConfiguration] = None) -> str:
		if current_value:
			return current_value.config_type.display_msg()
		return ''

	def _prev_disk_encryption(self) -> Optional[str]:
		encryption: Optional[disk.DiskEncryption] = self._menu_options['disk_encryption'].current_selection
		if encryption:
			enc_type = disk.EncryptionType.type_to_text(encryption.encryption_type)
			output = str(_('Encryption type')) + f': {enc_type}\n'
			output += str(_('Password')) + f': {secret(encryption.encryption_password)}\n'

			if encryption.partitions:
				output += 'Partitions: {} selected'.format(len(encryption.partitions)) + '\n'

			if encryption.hsm_device:
				output += f'HSM: {encryption.hsm_device.manufacturer}'

			return output

		return None

	def _display_disk_encryption(self, current_value: Optional[disk.DiskEncryption]) -> str:
		if current_value:
			return disk.EncryptionType.type_to_text(current_value.encryption_type)
		return ''

	def _prev_install_missing_config(self) -> Optional[str]:
		if missing := self._missing_configs():
			text = str(_('Missing configurations:\n'))
			for m in missing:
				text += f'- {m}\n'
			return text[:-1]  # remove last new line
		return None

	def _prev_users(self) -> Optional[str]:
		selector = self._menu_options['!users']
		users: Optional[List[User]] = selector.current_selection

		if users:
			return FormattedOutput.as_table(users)
		return None

	def _prev_profile(self) -> Optional[str]:
		selector = self._menu_options['profile_config']
		profile_config: Optional[ProfileConfiguration] = selector.current_selection

		if profile_config and profile_config.profile:
			output = str(_('Profiles')) + ': '
			if profile_names := profile_config.profile.current_selection_names():
				output += ', '.join(profile_names) + '\n'
			else:
				output += profile_config.profile.name + '\n'

			if profile_config.gfx_driver:
				output += str(_('Graphics driver')) + ': ' + profile_config.gfx_driver + '\n'

			if profile_config.greeter:
				output += str(_('Greeter')) + ': ' + profile_config.greeter.value + '\n'

			return output

		return None

	def _set_root_password(self) -> Optional[str]:
		prompt = str(_('Enter root password (leave blank to disable root): '))
		password = get_password(prompt=prompt)
		return password

	def _select_disk_config(
		self,
		preset: Optional[disk.DiskLayoutConfiguration] = None
	) -> Optional[disk.DiskLayoutConfiguration]:
		disk_config = select_disk_config(
			preset,
			storage['arguments'].get('advanced', False)
		)

		if disk_config != preset:
			self._menu_options['disk_encryption'].set_current_selection(None)

		return disk_config

	def _select_profile(self, current_profile: Optional[ProfileConfiguration]):
		from .profile.profile_menu import ProfileMenu
		store: Dict[str, Any] = {}
		profile_config = ProfileMenu(store, preset=current_profile).run()
		return profile_config

	def _select_audio(self, current: Union[str, None]) -> Optional[str]:
		profile_config: Optional[ProfileConfiguration] = self._menu_options['profile_config'].current_selection
		if profile_config and profile_config.profile:
			is_desktop = profile_config.profile.is_desktop_profile() if profile_config else False
			selection = ask_for_audio_selection(is_desktop, current)
			return selection
		return None

	def _create_user_account(self, defined_users: List[User]) -> List[User]:
		users = ask_for_additional_users(defined_users=defined_users)
		return users
