import sys
from typing import Dict

from .menu import Menu
from ..general import SysCommand
from ..storage import storage
from ..output import log
from ..profiles import is_desktop_profile
from ..disk import encrypted_partitions
from ..locale_helpers import set_keyboard_language
from ..user_interaction import get_password
from ..user_interaction import ask_ntp
from ..user_interaction import ask_for_swap
from ..user_interaction import ask_for_bootloader
from ..user_interaction import ask_hostname
from ..user_interaction import ask_for_audio_selection
from ..user_interaction import ask_additional_packages_to_install
from ..user_interaction import ask_to_configure_network
from ..user_interaction import ask_timezone
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
from ..user_interaction import select_archinstall_language
from ..translation import Translation


class Selector:
	def __init__(
		self,
		description,
		func=None,
		display_func=None,
		default=None,
		enabled=False,
		dependencies=[],
		dependencies_not=[]
	):
		"""
		Create a new menu selection entry

		:param description: Text that will be displayed as the menu entry
		:type description: str

		:param func: Function that is called when the menu entry is selected
		:type func: Callable

		:param display_func: After specifying a setting for a menu item it is displayed
		on the right side of the item as is; with this function one can modify the entry
		to be displayed; e.g. when specifying a password one can display **** instead
		:type display_func: Callable

		:param default: Default value for this menu entry
		:type default: Any

		:param enabled: Specify if this menu entry should be displayed
		:type enabled: bool

		:param dependencies: Specify dependencies for this menu entry; if the dependencies
		are not set yet, then this item is not displayed; e.g. disk_layout depends on selectiong
		harddrive(s) first
		:type dependencies: list

		:param dependencies_not: These are the exclusive options; the menu item will only be
		displayed if non of the entries in the list have been specified
		:type dependencies_not: list
		"""

		self._description = description
		self.func = func
		self._display_func = display_func
		self._current_selection = default
		self.enabled = enabled
		self._dependencies = dependencies
		self._dependencies_not = dependencies_not

	@property
	def dependencies(self):
		return self._dependencies

	@property
	def dependencies_not(self):
		return self._dependencies_not

	@property
	def current_selection(self):
		return self._current_selection

	def set_enabled(self):
		self.enabled = True

	def update_description(self, description):
		self._description = description

	def menu_text(self):
		current = ''

		if self._display_func:
			current = self._display_func(self._current_selection)
		else:
			if self._current_selection is not None:
				current = str(self._current_selection)

		if current:
			padding = 35 - len(self._description)
			current = ' ' * padding + f'SET: {current}'

		return f'{self._description} {current}'

	def set_current_selection(self, current):
		self._current_selection = current

	def has_selection(self):
		if self._current_selection is None:
			return False
		return True

	def is_empty(self):
		if self._current_selection is None:
			return True
		elif isinstance(self._current_selection, (str, list, dict)) and len(self._current_selection) == 0:
			return True

		return False


class GlobalMenu:
	def __init__(self):
		self._translation = Translation.load_nationalization()
		self._menu_options = {}
		self._setup_selection_menu_options()

	def _setup_selection_menu_options(self):
		self._menu_options['archinstall-language'] = \
			Selector(
				_('Select Archinstall language'),
				lambda: self._select_archinstall_language('English'),
				default='English',
				enabled=True)
		self._menu_options['keyboard-layout'] = \
			Selector(_('Select keyboard layout'), lambda: select_language('us'), default='us')
		self._menu_options['mirror-region'] = \
			Selector(
				_('Select mirror region'),
				lambda: select_mirror_regions(),
				display_func=lambda x: list(x.keys()) if x else '[]',
				default={})
		self._menu_options['sys-language'] = \
			Selector(_('Select locale language'), lambda: select_locale_lang('en_US'), default='en_US')
		self._menu_options['sys-encoding'] = \
			Selector(_('Select locale encoding'), lambda: select_locale_enc('utf-8'), default='utf-8')
		self._menu_options['harddrives'] = \
			Selector(
				_('Select harddrives'),
				lambda: self._select_harddrives())
		self._menu_options['disk_layouts'] = \
			Selector(
				_('Select disk layout'),
				lambda: select_disk_layout(
					storage['arguments'].get('harddrives', []),
					storage['arguments'].get('advanced', False)
				),
				dependencies=['harddrives'])
		self._menu_options['!encryption-password'] = \
			Selector(
				_('Set encryption password'),
				lambda: get_password(prompt=str(_('Enter disk encryption password (leave blank for no encryption): '))),
				display_func=lambda x: self._secret(x) if x else 'None',
				dependencies=['harddrives'])
		self._menu_options['swap'] = \
			Selector(
				_('Use swap'),
				lambda: ask_for_swap(),
				default=True)
		self._menu_options['bootloader'] = \
			Selector(
				_('Select bootloader'),
				lambda: ask_for_bootloader(storage['arguments'].get('advanced', False)),)
		self._menu_options['hostname'] = \
			Selector(_('Specify hostname'), lambda: ask_hostname())
		self._menu_options['!root-password'] = \
			Selector(
				_('Set root password'),
				lambda: self._set_root_password(),
				display_func=lambda x: self._secret(x) if x else 'None')
		self._menu_options['!superusers'] = \
			Selector(
				_('Specify superuser account'),
				lambda: self._create_superuser_account(),
				dependencies_not=['!root-password'],
				display_func=lambda x: list(x.keys()) if x else '')
		self._menu_options['!users'] = \
			Selector(
				_('Specify user account'),
				lambda: self._create_user_account(),
				default={},
				display_func=lambda x: list(x.keys()) if x else '[]')
		self._menu_options['profile'] = \
			Selector(
				_('Specify profile'),
				lambda: self._select_profile(),
				display_func=lambda x: x if x else 'None')
		self._menu_options['audio'] = \
			Selector(
				_('Select audio'),
				lambda: ask_for_audio_selection(is_desktop_profile(storage['arguments'].get('profile', None))))
		self._menu_options['kernels'] = \
			Selector(
				_('Select kernels'),
				lambda: select_kernel(),
				default=['linux'])
		self._menu_options['packages'] = \
			Selector(
				_('Additional packages to install'),
				lambda: ask_additional_packages_to_install(storage['arguments'].get('packages', None)),
				default=[])
		self._menu_options['nic'] = \
			Selector(
				_('Configure network'),
				lambda: ask_to_configure_network(),
				display_func=lambda x: x if x else _('Not configured, unavailable unless setup manually'),
				default={})
		self._menu_options['timezone'] = \
			Selector(_('Select timezone'), lambda: ask_timezone())
		self._menu_options['ntp'] = \
			Selector(
				_('Set automatic time sync (NTP)'),
				lambda: self._select_ntp(),
				default=True)
		self._menu_options['install'] = \
			Selector(
				self._install_text(),
				enabled=True)
		self._menu_options['abort'] = Selector(_('Abort'), enabled=True)

	def enable(self, selector_name, omit_if_set=False):
		arg = storage['arguments'].get(selector_name, None)

		# don't display the menu option if it was defined already
		if arg is not None and omit_if_set:
			return

		if self._menu_options.get(selector_name, None):
			self._menu_options[selector_name].set_enabled()
			if arg is not None:
				self._menu_options[selector_name].set_current_selection(arg)
		else:
			print(f'No selector found: {selector_name}')
			sys.exit(1)

	def run(self):
		while True:
			# # Before continuing, set the preferred keyboard layout/language in the current terminal.
			# # This will just help the user with the next following questions.
			self._set_kb_language()

			enabled_menus = self._menus_to_enable()
			menu_text = [m.menu_text() for m in enabled_menus.values()]
			selection = Menu(_('Set/Modify the below options'), menu_text, sort=False).run()

			if selection:
				selection = selection.strip()
				if str(_('Abort')) in selection:
					exit(0)
				elif str(_('Install')) in selection:
					if self._missing_configs() == 0:
						break
				else:
					self._process_selection(selection)

		for key in self._menu_options:
			sel = self._menu_options[key]
			if key not in storage['arguments']:
				storage['arguments'][key] = sel.current_selection

		self._post_processing()

	def _process_selection(self, selection):
		# find the selected option in our option list
		option = [[k, v] for k, v in self._menu_options.items() if v.menu_text().strip() == selection]

		if len(option) != 1:
			raise ValueError(f'Selection not found: {selection}')

		selector_name = option[0][0]
		selector = option[0][1]
		result = selector.func()
		self._menu_options[selector_name].set_current_selection(result)
		storage['arguments'][selector_name] = result

		self._update_install()

	def _update_install(self):
		text = self._install_text()
		self._menu_options.get('install').update_description(text)

	def _post_processing(self):
		if storage['arguments'].get('harddrives', None) and storage['arguments'].get('!encryption-password', None):
			# If no partitions was marked as encrypted, but a password was supplied and we have some disks to format..
			# Then we need to identify which partitions to encrypt. This will default to / (root).
			if len(list(encrypted_partitions(storage['arguments'].get('disk_layouts', [])))) == 0:
				storage['arguments']['disk_layouts'] = select_encrypted_partitions(
					storage['arguments']['disk_layouts'], storage['arguments']['!encryption-password'])

	def _install_text(self):
		missing = self._missing_configs()
		if missing > 0:
			return _('Install ({} config(s) missing)').format(missing)
		return 'Install'

	def _missing_configs(self):
		def check(s):
			return self._menu_options.get(s).has_selection()

		missing = 0
		if not check('bootloader'):
			missing += 1
		if not check('hostname'):
			missing += 1
		if not check('audio'):
			missing += 1
		if not check('timezone'):
			missing += 1
		if not check('!root-password') and not check('!superusers'):
			missing += 1
		if not check('harddrives'):
			missing += 1
		if check('harddrives'):
			if not self._menu_options.get('harddrives').is_empty() and not check('disk_layouts'):
				missing += 1

		return missing

	def _select_archinstall_language(self, default_lang):
		language = select_archinstall_language(default_lang)
		self._translation.activate(language)
		return language

	def _set_root_password(self):
		prompt = str(_('Enter root password (leave blank to disable root): '))
		password = get_password(prompt=prompt)

		# TODO: Do we really wanna wipe the !superusers and !users if root password is set?
		# What if they set a superuser first, but then decides to set a root password?
		if password is not None:
			self._menu_options.get('!superusers').set_current_selection(None)
			storage['arguments']['!users'] = {}
			storage['arguments']['!superusers'] = {}

		return password

	def _select_ntp(self) -> bool:
		ntp = ask_ntp()

		value = str(ntp).lower()
		SysCommand(f'timedatectl set-ntp {value}')

		return ntp

	def _select_harddrives(self):
		old_haddrives = storage['arguments'].get('harddrives', [])
		harddrives = select_harddrives()

		# in case the harddrives got changed we have to reset the disk layout as well
		if old_haddrives != harddrives:
			self._menu_options.get('disk_layouts').set_current_selection(None)
			storage['arguments']['disk_layouts'] = {}

		if not harddrives:
			prompt = _(
				"You decided to skip harddrive selection\nand will use whatever drive-setup is mounted at {} (experimental)\n"
				"WARNING: Archinstall won't check the suitability of this setup\n"
				"Do you wish to continue?"
			).format(archinstall.storage['MOUNT_POINT'])

			choice = Menu(prompt, ['yes', 'no'], default_option='yes').run()

			if choice == 'no':
				return self._select_harddrives()

		return harddrives

	def _secret(self, x):
		return '*' * len(x)

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
		superuser = ask_for_superuser_account(str(_('Create a required super-user with sudo privileges: ')), forced=True)
		return superuser

	def _create_user_account(self):
		users, superusers = ask_for_additional_users(str(_('Enter a username to create an additional user (leave blank to skip): ')))
		storage['arguments']['!superusers'] = {**storage['arguments'].get('!superusers', {}), **superusers}

		return users

	def _set_kb_language(self):
		# Before continuing, set the preferred keyboard layout/language in the current terminal.
		# This will just help the user with the next following questions.
		if len(storage['arguments'].get('keyboard-layout', [])):
			set_keyboard_language(storage['arguments']['keyboard-layout'])

	def _verify_selection_enabled(self, selection_name):
		if selection := self._menu_options.get(selection_name, None):
			if not selection.enabled:
				return False

			if len(selection.dependencies) > 0:
				for d in selection.dependencies:
					if not self._verify_selection_enabled(d) or self._menu_options.get(d).is_empty():
						return False

			if len(selection.dependencies_not) > 0:
				for d in selection.dependencies_not:
					if not self._menu_options.get(d).is_empty():
						return False

			return True

		raise ValueError(f'No selection found: {selection_name}')

	def _menus_to_enable(self) -> Dict[str, Selector]:
		enabled_menus = {}

		for name, selection in self._menu_options.items():
			if self._verify_selection_enabled(name):
				enabled_menus[name] = selection

		return enabled_menus
