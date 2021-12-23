import sys

import archinstall
from archinstall import Menu


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
		self.text = self.menu_text()
		self._dependencies = dependencies
		self._dependencies_not = dependencies_not

	@property
	def dependencies(self):
		return self._dependencies

	@property
	def dependencies_not(self):
		return self._dependencies_not

	def set_enabled(self):
		self.enabled = True

	def update_description(self, description):
		self._description = description
		self.text = self.menu_text()

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
		self.text = self.menu_text()

	def has_selection(self):
		if self._current_selection is None:
			return False
		elif isinstance(self._current_selection, (str, list, dict)):
			if len(self._current_selection) == 0:
				return False

		return True


class GlobalMenu:
	def __init__(self):
		self._menu_options = {}
		self._setup_selection_menu_options()

	def _setup_selection_menu_options(self):
		self._menu_options['keyboard-layout'] = \
			Selector('Select keyboard layout', lambda: archinstall.select_language('us'), default='us')
		self._menu_options['mirror-region'] = \
			Selector(
				'Select mirror region',
				lambda: archinstall.select_mirror_regions(),
				display_func=lambda x: list(x.keys()) if x else '[]',
				default={})
		self._menu_options['sys-language'] = \
			Selector('Select locale language', lambda: archinstall.select_locale_lang('en_US'), default='en_US')
		self._menu_options['sys-encoding'] = \
			Selector('Select locale encoding', lambda: archinstall.select_locale_enc('utf-8'), default='utf-8')
		self._menu_options['harddrives'] = \
			Selector(
				'Select harddrives',
				lambda: self._select_harddrives(),
				default=[])
		self._menu_options['disk_layouts'] = \
			Selector(
				'Select disk layout',
				lambda: archinstall.select_disk_layout(
					archinstall.arguments['harddrives'],
					archinstall.arguments.get('advanced', False)
				),
				dependencies=['harddrives'])
		self._menu_options['!encryption-password'] = \
			Selector(
				'Set encryption password',
				lambda: archinstall.get_password(prompt='Enter disk encryption password (leave blank for no encryption): '),
				display_func=lambda x: self._secret(x) if x else 'None',
				dependencies=['harddrives'])
		self._menu_options['swap'] = \
			Selector(
				'Use swap',
				lambda: archinstall.ask_for_swap(),
				default=True)
		self._menu_options['bootloader'] = \
			Selector(
				'Select bootloader',
				lambda: archinstall.ask_for_bootloader(archinstall.arguments.get('advanced', False)),)
		self._menu_options['hostname'] = \
			Selector('Specify hostname', lambda: archinstall.ask_hostname())
		self._menu_options['!root-password'] = \
			Selector(
				'Set root password',
				lambda: self._set_root_password(),
				display_func=lambda x: self._secret(x) if x else 'None')
		self._menu_options['!superusers'] = \
			Selector(
				'Specify superuser account', lambda: self._create_superuser_account(),
				dependencies_not=['!root-password'],
				display_func=lambda x: list(x.keys()) if x else '')
		self._menu_options['profile'] = \
			Selector(
				'Specify profile',
				lambda: self._select_profile(),
				display_func=lambda x: x if x else 'None')
		self._menu_options['audio'] = \
			Selector(
				'Select audio',
				lambda: archinstall.ask_for_audio_selection(archinstall.is_desktop_profile(archinstall.arguments.get('profile', None))))
		self._menu_options['kernels'] = \
			Selector(
				'Select kernels',
				lambda: archinstall.select_kernel(),
				default='linux')
		self._menu_options['packages'] = \
			Selector(
				'Additional packages to install',
				lambda: archinstall.ask_additional_packages_to_install(archinstall.arguments.get('packages', None)),
				default=[])
		self._menu_options['nic'] = \
			Selector(
				'Configure network',
				lambda: archinstall.ask_to_configure_network(),
				display_func=lambda x: x if x else 'Not configured, unavailable unless setup manually',
				default={})
		self._menu_options['timezone'] = \
			Selector('Select timezone', lambda: archinstall.ask_timezone())
		self._menu_options['ntp'] = \
			Selector(
				'Set automatic time sync (NTP)',
				lambda: archinstall.ask_ntp(),
				default=True)
		self._menu_options['install'] = \
			Selector(
				self._install_text(),
				enabled=True)
		self._menu_options['abort'] = Selector('Abort', enabled=True)

	def enable(self, selector_name, omit_if_set=False):
		arg = archinstall.arguments.get(selector_name, None)

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
			menu_text = [m.text for m in enabled_menus.values()]
			selection = Menu('Set/Modify the below options', menu_text, sort=False).run()
			if selection:
				selection = selection.strip()
				if 'Abort' in selection:
					exit(0)
				elif 'Install' in selection:
					if self._missing_configs() == 0:
						self._post_processing()
						break
				else:
					self._process_selection(selection)

	def _process_selection(self, selection):
		# find the selected option in our option list
		option = [[k, v] for k, v in self._menu_options.items() if v.text.strip() == selection]

		if len(option) != 1:
			raise ValueError(f'Selection not found: {selection}')

		selector_name = option[0][0]
		selector = option[0][1]
		result = selector.func()
		self._menu_options[selector_name].set_current_selection(result)
		archinstall.arguments[selector_name] = result

		self._update_install()

	def _update_install(self):
		text = self._install_text()
		self._menu_options.get('install').update_description(text)

	def _post_processing(self):
		if archinstall.arguments.get('harddrives', None) and archinstall.arguments.get('!encryption-password', None):
			# If no partitions was marked as encrypted, but a password was supplied and we have some disks to format..
			# Then we need to identify which partitions to encrypt. This will default to / (root).
			if len(list(archinstall.encrypted_partitions(archinstall.storage['disk_layouts']))) == 0:
				archinstall.storage['disk_layouts'] = archinstall.select_encrypted_partitions(
					archinstall.storage['disk_layouts'], archinstall.arguments['!encryption-password'])

	def _install_text(self):
		missing = self._missing_configs()
		if missing > 0:
			return f'Install ({missing} config(s) missing)'
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
		if check('harddrives') and not check('disk_layouts'):
			missing += 1

		return missing

	def _set_root_password(self):
		prompt = 'Enter root password (leave blank to disable root & create superuser): '
		password = archinstall.get_password(prompt=prompt)

		if password is not None:
			self._menu_options.get('!superusers').set_current_selection(None)
			archinstall.arguments['!users'] = {}
			archinstall.arguments['!superusers'] = {}

		return password

	def _select_harddrives(self):
		old_haddrives = archinstall.arguments.get('harddrives')
		harddrives = archinstall.select_harddrives()

		# in case the harddrives got changed we have to
		# reset the disk layout as well
		if old_haddrives != harddrives:
			self._menu_options.get('disk_layouts').set_current_selection(None)
			archinstall.arguments['disk_layouts'] = {}

		return harddrives

	def _secret(self, x):
		return '*' * len(x)

	def _select_profile(self):
		profile = archinstall.select_profile()

		# Check the potentially selected profiles preparations to get early checks if some additional questions are needed.
		if profile and profile.has_prep_function():
			namespace = f'{profile.namespace}.py'
			with profile.load_instructions(namespace=namespace) as imported:
				if not imported._prep_function():
					archinstall.log(' * Profile\'s preparation requirements was not fulfilled.', fg='red')
					exit(1)

		return profile

	def _create_superuser_account(self):
		superuser = archinstall.ask_for_superuser_account('Create a required super-user with sudo privileges: ', forced=True)
		users, superusers = archinstall.ask_for_additional_users('Enter a username to create an additional user (leave blank to skip & continue): ')
		archinstall.arguments['!users'] = users
		return {**superuser, **superusers}

	def _set_kb_language(self):
		# Before continuing, set the preferred keyboard layout/language in the current terminal.
		# This will just help the user with the next following questions.
		if archinstall.arguments.get('keyboard-layout', None) and len(archinstall.arguments['keyboard-layout']):
			archinstall.set_keyboard_language(archinstall.arguments['keyboard-layout'])

	def _verify_selection_enabled(self, selection_name):
		if selection := self._menu_options.get(selection_name, None):
			if not selection.enabled:
				return False

			if len(selection.dependencies) > 0:
				for d in selection.dependencies:
					if not self._verify_selection_enabled(d) or not self._menu_options.get(d).has_selection():
						return False

			if len(selection.dependencies_not) > 0:
				for d in selection.dependencies_not:
					if self._menu_options.get(d).has_selection():
						return False

			return True

		raise ValueError(f'No selection found: {selection_name}')

	def _menus_to_enable(self):
		enabled_menus = {}

		for name, selection in self._menu_options.items():
			if self._verify_selection_enabled(name):
				enabled_menus[name] = selection

		return enabled_menus
