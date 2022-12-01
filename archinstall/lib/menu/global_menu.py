from __future__ import annotations

from typing import Any, List, Optional, Union, Dict, TYPE_CHECKING

from archinstall.profiles.profiles import Profile
from ..disk.device_handler import BDevice, DeviceModification
from ..general import SysCommand, secret
from ..menu import Menu
from ..menu.abstract_menu import Selector, AbstractMenu
from ..models import NetworkConfiguration
from ..models.bootloader import Bootloader
from ..models.disk_encryption import DiskEncryption, EncryptionType
from ..models.disk_layout import DiskLayoutConfiguration
from ..models.users import User
from ..output import FormattedOutput
from ..storage import storage
from ..user_interaction import ask_additional_packages_to_install
from ..user_interaction import add_number_of_parrallel_downloads
from ..user_interaction import ask_for_additional_users
from ..user_interaction import ask_for_audio_selection
from ..user_interaction import ask_for_bootloader
from ..user_interaction import ask_for_swap
from ..user_interaction import ask_hostname
from ..user_interaction import ask_ntp
from ..user_interaction import ask_to_configure_network
from ..user_interaction import get_password, ask_for_a_timezone
from ..user_interaction import select_additional_repositories
from ..user_interaction import select_disk_layout
from ..user_interaction import select_kernel
from ..user_interaction import select_language
from ..user_interaction import select_locale_enc
from ..user_interaction import select_locale_lang
from ..user_interaction import select_mirror_regions
from ..user_interaction import select_profile
from ..user_interaction.disk_conf import select_devices
from ..user_interaction.save_conf import save_config

if TYPE_CHECKING:
	_: Any


class GlobalMenu(AbstractMenu):
	def __init__(self,data_store):
		self._disk_check = True
		super().__init__(data_store=data_store, auto_cursor=True, preview_size=0.3)

	def _setup_selection_menu_options(self):
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
		# self._menu_options['devices'] = \
		# 	Selector(
		# 		_('Drive(s)'),
		# 		lambda preset: self._select_devices(preset),
		# 		display_func=lambda x: f'{len(x)} ' + str(_('Drive(s)')) if x is not None and len(x) > 0 else '',
		# 		preview_func=self._prev_devices,
		# )
		self._menu_options['disk_layouts'] = \
			Selector(
				_('Disk layout'),
				lambda preset: self._select_disk_layout(preset),
				preview_func=self._prev_disk_layouts,
				display_func=lambda x: self._display_disk_layout(x),
				# dependencies=['devices']
			)
		self._menu_options['disk_encryption'] = \
			Selector(
				_('Disk encryption'),
				lambda preset: self._disk_encryption(preset),
				preview_func=self._prev_disk_encryption,
				display_func=lambda x: self._display_disk_encryption(x),
				dependencies=['disk_layouts'])
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
				ask_hostname,
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
		self._menu_options['profile'] = \
			Selector(
				_('Profile'),
				lambda preset: self._select_profile(preset),
				display_func=lambda x: x.name if x else 'None',
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
				lambda preset: self._select_ntp(preset),
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

	def _update_install_text(self, name :str = None, result :Any = None):
		text = self._install_text()
		self._menu_options['install'].update_description(text)

	def post_callback(self,name :str = None ,result :Any = None):
		self._update_install_text(name, result)

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

	def _disk_encryption(self, preset: Optional[DiskEncryption]) -> Optional[DiskEncryption]:
		from ..disk.encryption import DiskEncryptionMenu
		data_store: Dict[str, Any] = {}

		selector = self._menu_options['disk_layouts']

		if selector.has_selection():
			layouts: List[DeviceModification] = selector.current_selection
		else:
			# this should not happen as the encryption menu has the disk layout as dependency
			raise ValueError('No disk layout specified')

		disk_encryption = DiskEncryptionMenu(data_store, preset, layouts).run()
		return disk_encryption

	def _prev_network_config(self) -> Optional[str]:
		selector = self._menu_options['nic']
		if selector.has_selection():
			ifaces = selector.current_selection
			if isinstance(ifaces, list):
				return FormattedOutput.as_table(ifaces)
		return None

	def _prev_devices(self) -> Optional[str]:
		selector = self._menu_options['devices']
		if selector.has_selection():
			devices: List[BDevice] = selector.current_selection
			infos = [device.device_info for device in devices]
			return FormattedOutput.as_table(infos)
		return None

	def _prev_disk_layouts(self) -> Optional[str]:
		selector = self._menu_options['disk_layouts']
		if selector.has_selection():
			disk_layout_conf: DiskLayoutConfiguration = selector.current_selection

			device_modifications: List[DeviceModification] = \
				list(filter(lambda x: len(x.partitions) > 0, disk_layout_conf.modifictions))

			if device_modifications:
				disk_layout_output = disk_layout_conf.layout_type.value + '\n'
				output_partition = ''
				output_btrfs = ''

				for modification in device_modifications:
					# create partition table
					partition_table = FormattedOutput.as_table(modification.partitions)
					output_partition += f'{modification.device.device_info.path}\n'
					output_partition += partition_table + '\n'

					# create btrfs table
					btrfs_partitions = list(
						filter(lambda p: len(p.btrfs) > 0, modification.partitions)
					)
					for partition in btrfs_partitions:
						output_btrfs += FormattedOutput.as_table(partition.btrfs) + '\n'

				output = disk_layout_output + output_partition + output_btrfs
				return output.rstrip()

		return None

	def _display_disk_layout(self, current_value: Optional[DiskLayoutConfiguration] = None) -> str:
		if current_value:
			partitions = [len(mod.partitions) for mod in current_value.modifictions if mod.partitions]
			if partitions:
				total = sum(partitions)
				return f'{total} {_("Partitions")}'
		return ''

	def _prev_disk_encryption(self) -> Optional[str]:
		selector = self._menu_options['disk_encryption']
		if selector.has_selection():
			encryption: DiskEncryption = selector.current_selection

			enc_type = EncryptionType.type_to_text(encryption.encryption_type)
			output = str(_('Encryption type')) + f': {enc_type}\n'
			output += str(_('Password')) + f': {secret(encryption.encryption_password)}\n'

			if encryption.partitions:
				output += 'Partitions: {} selected'.format(len(encryption.partitions)) + '\n'

			if encryption.hsm_device:
				output += f'HSM: {encryption.hsm_device.manufacturer}'

			return output

		return None

	def _display_disk_encryption(self, current_value: Optional[DiskEncryption]) -> str:
		if current_value:
			return EncryptionType.type_to_text(current_value.encryption_type)
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
		if selector.has_selection():
			users: List[User] = selector.current_selection
			return FormattedOutput.as_table(users)
		return None

	def _prev_profile(self) -> Optional[str]:
		selector = self._menu_options['profile']
		if selector.has_selection():
			profile: Profile = selector.current_selection
			return FormattedOutput.as_table([profile.info()])
		return None

	def _missing_configs(self) -> List[str]:
		def check(s):
			return self._menu_options.get(s).has_selection()

		def has_superuser() -> bool:
			users = self._menu_options['!users'].current_selection
			return any([u.sudo for u in users])

		missing = []
		if not check('bootloader'):
			missing += ['Bootloader']
		if not check('hostname'):
			missing += ['Hostname']
		if not check('!root-password') and not has_superuser():
			missing += [str(_('Either root-password or at least 1 user with sudo privileges must be specified'))]
		if self._disk_check:
			# if not check('devices'):
			# 	missing += [self._menu_options['devices'].description]
			# if check('devices'):
			# 	if not self._menu_options['devices'].is_empty() and not check('disk_layouts'):
			# 		missing += [self._menu_options['disk_layouts'].description]
			if check('disk_layouts'):
				missing += [self._menu_options['disk_layouts'].description]

		return missing

	def _set_root_password(self) -> Optional[str]:
		prompt = str(_('Enter root password (leave blank to disable root): '))
		password = get_password(prompt=prompt)
		return password

	def _select_ntp(self, preset :bool = True) -> bool:
		ntp = ask_ntp(preset)

		value = str(ntp).lower()
		SysCommand(f'timedatectl set-ntp {value}')

		return ntp

	def _select_disk_layout(self, preset: Optional[DiskLayoutConfiguration] = None) -> DiskLayoutConfiguration:
		return select_disk_layout(
			preset,
			storage['arguments'].get('advanced', False)
		)

	def _select_profile(self, current_profile: Optional[Profile]):
		profile = select_profile(current_profile)
		return profile

	def _select_audio(self, current: Union[str, None]) -> Union[str, None]:
		profile: Profile = self._menu_options['profile'].current_selection
		is_desktop = profile.is_desktop_profile() if profile else False
		selection = ask_for_audio_selection(is_desktop, current)
		return selection

	def _create_user_account(self, defined_users: List[User]) -> List[User]:
		users = ask_for_additional_users(defined_users=defined_users)
		return users
