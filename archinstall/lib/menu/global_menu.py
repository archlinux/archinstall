from __future__ import annotations

from typing import Any, List, Optional, Union

import archinstall

from ..menu import Menu
from ..menu.selection_menu import Selector, GeneralMenu
from ..general import SysCommand, secret
from ..hardware import has_uefi
from ..models import NetworkConfiguration
from ..storage import storage
from ..profiles import is_desktop_profile, Profile
from ..disk import encrypted_partitions

from ..user_interaction import get_password, ask_for_a_timezone, save_config
from ..user_interaction import ask_ntp
from ..user_interaction import ask_for_swap
from ..user_interaction import ask_for_bootloader
from ..user_interaction import ask_hostname
from ..user_interaction import ask_for_audio_selection
from ..user_interaction import ask_additional_packages_to_install
from ..user_interaction import ask_to_configure_network
from ..user_interaction import ask_for_superuser_account
from ..user_interaction import ask_for_additional_users
from ..user_interaction import select_language
from ..user_interaction import select_mirror_regions
from ..user_interaction import select_locale_lang
from ..user_interaction import select_locale_enc
from ..user_interaction import select_disk_layout
from ..user_interaction import select_kernel
from ..user_interaction import select_encrypted_partitions
from ..user_interaction import select_harddrives
from ..user_interaction import select_profile
from ..user_interaction import select_additional_repositories

class GlobalMenu(GeneralMenu):
	def __init__(self,data_store):
		super().__init__(data_store=data_store, auto_cursor=True)

	def _setup_selection_menu_options(self):
		# archinstall.Language will not use preset values
		self._menu_options['archinstall-language'] = \
			Selector(
				_('Archinstall language'),
				lambda x: self._select_archinstall_language(x),
				default='English')
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
				lambda preset: self._select_harddrives(preset))
		self._menu_options['disk_layouts'] = \
			Selector(
				_('Disk layout'),
				lambda preset: select_disk_layout(
					preset,
					storage['arguments'].get('harddrives', []),
					storage['arguments'].get('advanced', False)
				),
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
		self._menu_options['!superusers'] = \
			Selector(
				_('Superuser account'),
				lambda preset: self._create_superuser_account(),
				default={},
				exec_func=lambda n,v:self._users_resynch(),
				dependencies_not=['!root-password'],
				display_func=lambda x: self._display_superusers())
		self._menu_options['!users'] = \
			Selector(
				_('User account'),
				lambda x: self._create_user_account(),
				default={},
				exec_func=lambda n,v:self._users_resynch(),
				display_func=lambda x: list(x.keys()) if x else '[]')
		self._menu_options['profile'] = \
			Selector(
				_('Profile'),
				lambda preset: self._select_profile(preset),
				display_func=lambda x: x if x else 'None')
		self._menu_options['audio'] = \
			Selector(
				_('Audio'),
				lambda preset: ask_for_audio_selection(is_desktop_profile(storage['arguments'].get('profile', None)),preset),
				display_func=lambda x: x if x else 'None',
				default=None
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
				display_func=lambda x: self._prev_network_configuration(x),
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
		self._menu_options.get('install').update_description(text)

	def post_callback(self,name :str = None ,result :Any = None):
		self._update_install_text(name, result)

	def exit_callback(self):
		if self._data_store.get('harddrives', None) and self._data_store.get('!encryption-password', None):
			# If no partitions was marked as encrypted, but a password was supplied and we have some disks to format..
			# Then we need to identify which partitions to encrypt. This will default to / (root).
			if len(list(encrypted_partitions(storage['arguments'].get('disk_layouts', [])))) == 0:
				for blockdevice in storage['arguments']['disk_layouts']:
					for partition_index in select_encrypted_partitions(
							title="Select which partitions to encrypt:",
							partitions=storage['arguments']['disk_layouts'][blockdevice]['partitions']
						):

						partition = storage['arguments']['disk_layouts'][blockdevice]['partitions'][partition_index]
						partition['encrypted'] = True
						partition['!password'] = storage['arguments']['!encryption-password']

	def _install_text(self):
		missing = len(self._missing_configs())
		if missing > 0:
			return _('Install ({} config(s) missing)').format(missing)
		return _('Install')

	def _prev_network_configuration(self, cur_value: Union[NetworkConfiguration, List[NetworkConfiguration]]) -> str:
		if not cur_value:
			return _('Not configured, unavailable unless setup manually')
		else:
			if isinstance(cur_value, list):
				ifaces = [x.iface for x in cur_value]
				return f'Configured ifaces: {ifaces}'
			else:
				return str(cur_value)

	def _prev_install_missing_config(self) -> Optional[str]:
		if missing := self._missing_configs():
			text = str(_('Missing configurations:\n'))
			for m in missing:
				text += f'- {m}\n'
			return text[:-1]  # remove last new line
		return None

	def _missing_configs(self) -> List[str]:
		def check(s):
			return self._menu_options.get(s).has_selection()

		missing = []
		if not check('bootloader'):
			missing += ['Bootloader']
		if not check('hostname'):
			missing += ['Hostname']
		if not check('!root-password') and not check('!superusers'):
			missing += [str(_('Either root-password or at least 1 superuser must be specified'))]
		if not check('harddrives'):
			missing += ['Hard drives']
		if check('harddrives'):
			if not self._menu_options.get('harddrives').is_empty() and not check('disk_layouts'):
				missing += ['Disk layout']

		return missing

	def _set_root_password(self):
		prompt = str(_('Enter root password (leave blank to disable root): '))
		password = get_password(prompt=prompt)
		return password

	def _select_encrypted_password(self):
		if passwd := get_password(prompt=str(_('Enter disk encryption password (leave blank for no encryption): '))):
			return passwd
		else:
			return None

	def _select_ntp(self, preset :bool = True) -> bool:
		ntp = ask_ntp(preset)

		value = str(ntp).lower()
		SysCommand(f'timedatectl set-ntp {value}')

		return ntp

	def _select_harddrives(self, old_harddrives : list) -> list:
		harddrives = select_harddrives(old_harddrives)

		if len(harddrives) == 0:
			prompt = _(
				"You decided to skip harddrive selection\nand will use whatever drive-setup is mounted at {} (experimental)\n"
				"WARNING: Archinstall won't check the suitability of this setup\n"
				"Do you wish to continue?"
			).format(storage['MOUNT_POINT'])

			choice = Menu(prompt, Menu.yes_no(), default_option=Menu.yes(), skip=False).run()

			if choice.value == Menu.no():
				return self._select_harddrives(old_harddrives)

		# in case the harddrives got changed we have to reset the disk layout as well
		if old_harddrives != harddrives:
			self._menu_options.get('disk_layouts').set_current_selection(None)
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

	def _create_superuser_account(self):
		superusers = ask_for_superuser_account(str(_('Manage superuser accounts: ')))
		return superusers if superusers else None

	def _create_user_account(self):
		users = ask_for_additional_users(str(_('Manage ordinary user accounts: ')))
		return users

	def _display_superusers(self):
		superusers = self._data_store.get('!superusers', {})

		if self._menu_options.get('!root-password').has_selection():
			return list(superusers.keys()) if superusers else '[]'
		else:
			return list(superusers.keys()) if superusers else ''

	def _users_resynch(self):
		self.synch('!superusers')
		self.synch('!users')
		return False
