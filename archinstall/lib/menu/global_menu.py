from __future__ import annotations

from typing import Any, List, Optional, Union

from ..menu import Menu
from ..menu.selection_menu import Selector, GeneralMenu
from ..general import SysCommand, secret
from ..hardware import has_uefi
from ..models import NetworkConfiguration
from ..storage import storage
from ..output import log
from ..profiles import is_desktop_profile
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
				_('Select Archinstall language'),
				lambda x: self._select_archinstall_language('English'),
				default='English')
		self._menu_options['keyboard-layout'] = \
			Selector(_('Select keyboard layout'), lambda preset: select_language('us',preset), default='us')
		self._menu_options['mirror-region'] = \
			Selector(
				_('Select mirror region'),
				select_mirror_regions,
				display_func=lambda x: list(x.keys()) if x else '[]',
				default={})
		self._menu_options['sys-language'] = \
			Selector(_('Select locale language'), lambda preset: select_locale_lang('en_US',preset), default='en_US')
		self._menu_options['sys-encoding'] = \
			Selector(_('Select locale encoding'), lambda preset: select_locale_enc('utf-8',preset), default='utf-8')
		self._menu_options['harddrives'] = \
			Selector(
				_('Select harddrives'),
				self._select_harddrives)
		self._menu_options['disk_layouts'] = \
			Selector(
				_('Select disk layout'),
				lambda x: select_disk_layout(
					storage['arguments'].get('harddrives', []),
					storage['arguments'].get('advanced', False)
				),
				dependencies=['harddrives'])
		self._menu_options['!encryption-password'] = \
			Selector(
				_('Set encryption password'),
				lambda x: self._select_encrypted_password(),
				display_func=lambda x: secret(x) if x else 'None',
				dependencies=['harddrives'])
		self._menu_options['swap'] = \
			Selector(
				_('Use swap'),
				lambda preset: ask_for_swap(preset),
				default=True)
		self._menu_options['bootloader'] = \
			Selector(
				_('Select bootloader'),
				lambda preset: ask_for_bootloader(storage['arguments'].get('advanced', False),preset),
				default="systemd-bootctl" if has_uefi() else "grub-install")
		self._menu_options['hostname'] = \
			Selector(
				_('Specify hostname'),
				ask_hostname,
				default='archlinux')
		# root password won't have preset value
		self._menu_options['!root-password'] = \
			Selector(
				_('Set root password'),
				lambda preset:self._set_root_password(),
				display_func=lambda x: secret(x) if x else 'None')
		self._menu_options['!superusers'] = \
			Selector(
				_('Specify superuser account'),
				lambda preset: self._create_superuser_account(),
				default={},
				exec_func=lambda n,v:self._users_resynch(),
				dependencies_not=['!root-password'],
				display_func=lambda x: self._display_superusers())
		self._menu_options['!users'] = \
			Selector(
				_('Specify user account'),
				lambda x: self._create_user_account(),
				default={},
				exec_func=lambda n,v:self._users_resynch(),
				display_func=lambda x: list(x.keys()) if x else '[]')
		self._menu_options['profile'] = \
			Selector(
				_('Specify profile'),
				lambda x: self._select_profile(),
				display_func=lambda x: x if x else 'None')
		self._menu_options['audio'] = \
			Selector(
				_('Select audio'),
				lambda preset: ask_for_audio_selection(is_desktop_profile(storage['arguments'].get('profile', None)),preset),
				display_func=lambda x: x if x else 'None',
				default=None
			)
		self._menu_options['kernels'] = \
			Selector(
				_('Select kernels'),
				lambda preset: select_kernel(preset),
				default=['linux'])
		self._menu_options['packages'] = \
			Selector(
				_('Additional packages to install'),
				# lambda x: ask_additional_packages_to_install(storage['arguments'].get('packages', None)),
				ask_additional_packages_to_install,
				default=[])
		self._menu_options['additional-repositories'] = \
			Selector(
				_('Additional repositories to enable'),
				select_additional_repositories,
				default=[])
		self._menu_options['nic'] = \
			Selector(
				_('Configure network'),
				ask_to_configure_network,
				display_func=lambda x: self._prev_network_configuration(x),
				default={})
		self._menu_options['timezone'] = \
			Selector(
				_('Select timezone'),
				lambda preset: ask_for_a_timezone(preset),
				default='UTC')
		self._menu_options['ntp'] = \
			Selector(
				_('Set automatic time sync (NTP)'),
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
				storage['arguments']['disk_layouts'] = select_encrypted_partitions(
					storage['arguments']['disk_layouts'], storage['arguments']['!encryption-password'])

	def _install_text(self):
		missing = len(self._missing_configs())
		if missing > 0:
			return _('Install ({} config(s) missing)').format(missing)
		return 'Install'

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
		# old_haddrives = storage['arguments'].get('harddrives', [])
		harddrives = select_harddrives(old_harddrives)

		# in case the harddrives got changed we have to reset the disk layout as well
		if old_harddrives != harddrives:
			self._menu_options.get('disk_layouts').set_current_selection(None)
			storage['arguments']['disk_layouts'] = {}

		if not harddrives:
			prompt = _(
				"You decided to skip harddrive selection\nand will use whatever drive-setup is mounted at {} (experimental)\n"
				"WARNING: Archinstall won't check the suitability of this setup\n"
				"Do you wish to continue?"
			).format(storage['MOUNT_POINT'])

			choice = Menu(prompt, ['yes', 'no'], default_option='yes').run()

			if choice == 'no':
				exit(1)

		return harddrives

	def _select_profile(self):
		profile = select_profile()

		# Check the potentially selected profiles preparations to get early checks if some additional questions are needed.
		if profile and profile.has_prep_function():
			namespace = f'{profile.namespace}.py'
			with profile.load_instructions(namespace=namespace) as imported:
				if not imported._prep_function():
					log(' * Profile\'s preparation requirements was not fulfilled.', fg='red')
					exit(1)

		return profile

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
