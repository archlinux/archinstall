from __future__ import annotations

from typing import Any, List, Optional, Union, Dict, TYPE_CHECKING

import archinstall
from ..disk import encrypted_partitions
from ..general import SysCommand, secret
from ..hardware import has_uefi
from ..menu import Menu
from ..menu.selection_menu import Selector, GeneralMenu
from ..models import NetworkConfiguration
from ..models.users import User
from ..output import FormattedOutput
from ..profiles import is_desktop_profile, Profile
from ..storage import storage
from ..user_interaction import add_number_of_parrallel_downloads
from ..user_interaction import ask_additional_packages_to_install
from ..user_interaction import ask_for_additional_users
from ..user_interaction import ask_for_audio_selection
from ..user_interaction import ask_for_bootloader
from ..user_interaction import ask_for_swap
from ..user_interaction import ask_hostname
from ..user_interaction import ask_ntp
from ..user_interaction import ask_to_configure_network
from ..user_interaction import get_password, ask_for_a_timezone, save_config
from ..user_interaction import select_additional_repositories
from ..user_interaction import select_disk_layout
from ..user_interaction import select_encrypted_partitions
from ..user_interaction import select_harddrives
from ..user_interaction import select_kernel
from ..user_interaction import select_language
from ..user_interaction import select_locale_enc
from ..user_interaction import select_locale_lang
from ..user_interaction import select_mirror_regions
from ..user_interaction import select_profile
from ..user_interaction.partitioning_conf import current_partition_layout

if TYPE_CHECKING:
	_: Any


class GlobalMenu(GeneralMenu):
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
		self._menu_options['harddrives'] = \
			Selector(
				_('Drive(s)'),
				lambda preset: self._select_harddrives(preset),
				display_func=lambda x: f'{len(x)} ' + str(_('Drive(s)')) if x is not None and len(x) > 0 else '',
				preview_func=self._prev_harddrives,
		)
		self._menu_options['disk_layouts'] = \
			Selector(
				_('Disk layout'),
				lambda preset: select_disk_layout(
					preset,
					storage['arguments'].get('harddrives', []),
					storage['arguments'].get('advanced', False)
				),
				preview_func=self._prev_disk_layouts,
				display_func=lambda x: self._display_disk_layout(x),
				dependencies=['harddrives'])
		self._menu_options['!encryption-password'] = \
			Selector(
				_('Encryption password'),
				lambda x: self._select_encrypted_password(),
				display_func=lambda x: secret(x) if x else 'None',
				dependencies=['harddrives'])
		self._menu_options['HSM'] = Selector(
			description=_('Use HSM to unlock encrypted drive'),
			func=lambda preset: self._select_hsm(preset),
			dependencies=['!encryption-password'],
			default=None
		)
		self._menu_options['swap'] = \
			Selector(
				_('Swap'),
				lambda preset: ask_for_swap(preset),
				default=True)
		self._menu_options['bootloader'] = \
			Selector(
				_('Bootloader'),
				lambda preset: ask_for_bootloader(storage['arguments'].get('advanced', False),preset),
				default="systemd-bootctl" if has_uefi() else "grub-install")
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
				display_func=lambda x: x if x else 'None'
			)
		self._menu_options['audio'] = \
			Selector(
				_('Audio'),
				lambda preset: ask_for_audio_selection(is_desktop_profile(storage['arguments'].get('profile', None)),preset),
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

	def exit_callback(self):
		if self._data_store.get('harddrives', None) and self._data_store.get('!encryption-password', None):
			# If no partitions was marked as encrypted, but a password was supplied and we have some disks to format..
			# Then we need to identify which partitions to encrypt. This will default to / (root).
			if len(list(encrypted_partitions(storage['arguments'].get('disk_layouts', [])))) == 0:
				for blockdevice in storage['arguments']['disk_layouts']:
					if storage['arguments']['disk_layouts'][blockdevice].get('partitions'):
						for partition_index in select_encrypted_partitions(
								title=_('Select which partitions to encrypt:'),
								partitions=storage['arguments']['disk_layouts'][blockdevice]['partitions'],
								filter_=(lambda p: p['mountpoint'] != '/boot')
							):

							partition = storage['arguments']['disk_layouts'][blockdevice]['partitions'][partition_index]
							partition['encrypted'] = True
							partition['!password'] = storage['arguments']['!encryption-password']

							# We make sure generate-encryption-key-file is set on additional partitions
							# other than the root partition. Otherwise they won't unlock properly #1279
							if partition['mountpoint'] != '/':
								partition['generate-encryption-key-file'] = True

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

	def _prev_network_config(self) -> Optional[str]:
		selector = self._menu_options['nic']
		if selector.has_selection():
			ifaces = selector.current_selection
			if isinstance(ifaces, list):
				return FormattedOutput.as_table(ifaces)
		return None

	def _prev_harddrives(self) -> Optional[str]:
		selector = self._menu_options['harddrives']
		if selector.has_selection():
			drives = selector.current_selection
			return FormattedOutput.as_table(drives)
		return None

	def _prev_disk_layouts(self) -> Optional[str]:
		selector = self._menu_options['disk_layouts']
		if selector.has_selection():
			layouts: Dict[str, Dict[str, Any]] = selector.current_selection

			output = ''
			for device, layout in layouts.items():
				output += f'{_("Device")}: {device}\n\n'
				output += current_partition_layout(layout['partitions'], with_title=False)
				output += '\n\n'

			return output.rstrip()

		return None

	def _display_disk_layout(self, current_value: Optional[Dict[str, Any]]) -> str:
		if current_value:
			total_partitions = [entry['partitions'] for entry in current_value.values()]
			total_nr = sum([len(p) for p in total_partitions])
			return f'{total_nr} {_("Partitions")}'
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
			if not check('harddrives'):
				missing += [str(_('Drive(s)'))]
			if check('harddrives'):
				if not self._menu_options['harddrives'].is_empty() and not check('disk_layouts'):
					missing += [str(_('Disk layout'))]

		return missing

	def _set_root_password(self) -> Optional[str]:
		prompt = str(_('Enter root password (leave blank to disable root): '))
		password = get_password(prompt=prompt)
		return password

	def _select_encrypted_password(self) -> Optional[str]:
		if passwd := get_password(prompt=str(_('Enter disk encryption password (leave blank for no encryption): '))):
			return passwd
		else:
			return None

	def _select_ntp(self, preset :bool = True) -> bool:
		ntp = ask_ntp(preset)

		value = str(ntp).lower()
		SysCommand(f'timedatectl set-ntp {value}')

		return ntp

	def _select_harddrives(self, old_harddrives : list) -> List:
		harddrives = select_harddrives(old_harddrives)

		if harddrives is not None:
			if len(harddrives) == 0:
				prompt = _(
					"You decided to skip harddrive selection\nand will use whatever drive-setup is mounted at {} (experimental)\n"
					"WARNING: Archinstall won't check the suitability of this setup\n"
					"Do you wish to continue?"
				).format(storage['MOUNT_POINT'])

				choice = Menu(prompt, Menu.yes_no(), default_option=Menu.yes(), skip=False).run()

				if choice.value == Menu.no():
					self._disk_check = True
					return self._select_harddrives(old_harddrives)
				else:
					self._disk_check = False

			# in case the harddrives got changed we have to reset the disk layout as well
			if old_harddrives != harddrives:
				self._menu_options['disk_layouts'].set_current_selection(None)
				storage['arguments']['disk_layouts'] = {}

		return harddrives

	def _select_profile(self, preset):
		profile = select_profile(preset)
		ret = None

		if profile is None:
			if any([
				archinstall.storage.get('profile_minimal', False),
				archinstall.storage.get('_selected_servers', None),
				archinstall.storage.get('_desktop_profile', None),
				archinstall.arguments.get('desktop-environment', None),
				archinstall.arguments.get('gfx_driver_packages', None)
			]):
				return preset
			else:  # ctrl+c was actioned and all profile settings have been reset
				return None

		servers = archinstall.storage.get('_selected_servers', [])
		desktop = archinstall.storage.get('_desktop_profile', None)
		desktop_env = archinstall.arguments.get('desktop-environment', None)
		gfx_driver = archinstall.arguments.get('gfx_driver_packages', None)

		# Check the potentially selected profiles preparations to get early checks if some additional questions are needed.
		if profile and profile.has_prep_function():
			namespace = f'{profile.namespace}.py'
			with profile.load_instructions(namespace=namespace) as imported:
				if imported._prep_function(servers=servers, desktop=desktop, desktop_env=desktop_env, gfx_driver=gfx_driver):
					ret: Profile = profile

					match ret.name:
						case 'minimal':
							reset = ['_selected_servers', '_desktop_profile', 'desktop-environment', 'gfx_driver_packages']
						case 'server':
							reset = ['_desktop_profile', 'desktop-environment']
						case 'desktop':
							reset = ['_selected_servers']
						case 'xorg':
							reset = ['_selected_servers', '_desktop_profile', 'desktop-environment']

					for r in reset:
						archinstall.storage[r] = None
				else:
					return self._select_profile(preset)
		elif profile:
			ret = profile

		return ret

	def _create_user_account(self, defined_users: List[User]) -> List[User]:
		users = ask_for_additional_users(defined_users=defined_users)
		return users
