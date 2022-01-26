import sys
from collections import OrderedDict
import logging

from typing import Callable, Any, List, Iterator

import archinstall
from archinstall import Menu
from ..output import *

class Selector:
	def __init__(
		self,
		description :str,
		func :Callable = None,
		display_func :Callable = None,
		default :Any = None,
		enabled :bool = False,
		dependencies :List = [],
		dependencies_not :List = [],
		exec_func :Callable = None,
		preview_func :Callable = None,
		mandatory :bool = False
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

		:param exec_func: A function with the result of the selection as input parameter and which returns boolean.
		Can be used for any action deemed necessary after selection. If it returns True, exits the menu loop, if False,
		menu returns to the selection screen. If not specified it is assumed the return is False
		:type exec_func: Callable

		:param preview_func: A callable which invokws a preview screen (not implemented)
		:type preview_func: Callable

		:param mandatory: A boolean which determines that the field is mandatory, i.e. menu can not be exited if it is not set
		:type mandatory: bool
		"""

		self._description = description
		self.func = func
		self._display_func = display_func
		self._current_selection = default
		self.enabled = enabled
		self.text = self.menu_text()
		self._dependencies = dependencies
		self._dependencies_not = dependencies_not
		self.exec_func = exec_func
		self.preview_func = preview_func
		self.mandatory = mandatory

	@property
	def dependencies(self) -> dict:
		return self._dependencies

	@property
	def dependencies_not(self) -> dict:
		return self._dependencies_not

	def set_enabled(self, status :bool = True):
		self.enabled = status

	def update_description(self, description :str):
		self._description = description
		self.text = self.menu_text()

	def menu_text(self) -> str:
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

	def set_current_selection(self, current :str):
		self._current_selection = current
		self.text = self.menu_text()

	def has_selection(self) -> bool:
		if self._current_selection is None:
			return False
		return True

	def get_selection(self) -> Any:
		return self._current_selection

	def is_empty(self) -> bool:
		if self._current_selection is None:
			return True
		elif isinstance(self._current_selection, (str, list, dict)) and len(self._current_selection) == 0:
			return True
		return False

	def is_enabled(self) -> bool:
		return self.enabled

	def is_mandatory(self) -> bool:
		return self.mandatory

	def set_mandatory(self, status :bool = True):
		self.mandatory = status
		if status and not self.is_enabled():
			self.set_enabled(True)

class GeneralMenu():
	def __init__(self,
			data_store :dict = None,
			pre_callback :Callable = None,
			post_callback :Callable = None,
			exit_callback :Callable = None):
		"""
		Create a new selection menu.

		:param data_store:  Area (Dict) where the resulting data will be held. At least an entry for each option. Default area is archinstall.arguments (not preset in the call, due to circular references
		:type  data_store:  Dict

		:param pre_callback: common function which is invoked prior the invocation of a selector function. Accept menu oj. and selectr-name as parameter
		:type pre_callback: Callable

		:param post_callback: common function which is invoked AFTER the invocation of a selector function. AAccept menu oj. selectr-name and new value as parameter
		:type post_callback: Callable

		:param exit_callback: common fmandatory_gti shunction exectued prior to exiting the menu loop. Accepts the class as parameter
		:type pos_callback: Callable

		"""
		self._data_store = data_store if data_store is not None else {}
		self.pre_process_callback = pre_callback
		self.post_process_callback = post_callback
		self.exit_callback = exit_callback
		self.is_context_mgr = False
		self._menu_options = OrderedDict()
		self._setup_selection_menu_options()

	def __enter__(self, *args :Any, **kwargs :Any) -> 'SetupMenu':
		self.is_context_mgr: True
		return self

	def __exit__(self, *args :Any, **kwargs :Any) -> None:
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager
		# TODO: skip processing when it comes from a planified exit
		if len(args) >= 2 and args[1]:
			log(args[1], level=logging.ERROR, fg='red')
			print("    Please submit this issue (and file) to https://github.com/archlinux/archinstall/issues")
			raise args[1]

		for key in self._menu_options:
			sel = self._menu_options[key]
			if key and key not in self._data_store:
				self._data_store[key] = sel._current_selection
		if self.exit_callback:
			self.exit_callback(self)

	def _setup_selection_menu_options(self):
		""" Define the menu options.
			Menu options can be defined here in a subclass or done per progam calling self.set_option()
		"""
		log(f"Method _setup_selection_menu_options has not been coded for {type(self).__name__}",fg="red")
		raise archinstall.RequirementError("Method _setup_selection_menu_options needs to be personalized")

	def enable(self, selector_name :str, omit_if_set :bool = False , mandatory :bool = False):
		""" activates menu options """
		arg = self._data_store.get(selector_name, None)

		# don't display the menu option if it was defined already
		if arg is not None and omit_if_set:
			return

		if self._menu_options.get(selector_name, None):
			self._menu_options[selector_name].set_enabled(True)
			if mandatory:
				self._menu_options[selector_name].set_mandatory(True)

			if arg is not None:
				self._menu_options[selector_name].set_current_selection(arg)
		else:
			print(f'No selector found: {selector_name}')
			sys.exit(1)

	def run(self):
		""" Calls the Menu framework"""
		# Before continuing, set the preferred keyboard layout/language in the current terminal.
		# 	This will just help the user with the next following questions.
		while True:
			self._set_kb_language()
			enabled_menus = self._menus_to_enable()
			menu_text = [m.text for m in enabled_menus.values()]
			selection = Menu('Set/Modify the below options', menu_text, sort=False).run()
			if selection:
				selection = selection.strip()
				# if this calls returns false, we exit the menu. We allow for an callback for special processing on realeasing control
				if not self._process_selection(selection):
					break
		if not self.is_context_mgr:
			self.__exit__()
	def _process_selection(self, selection :str) -> bool:
		"""  determines and executes the selection y
			Can / Should be extended to handle specific selection issues
			Returns true if the menu shall continue, False if it has ended
		"""
		# find the selected option in our option list
		option = [[k, v] for k, v in self._menu_options.items() if v.text.strip() == selection]
		if len(option) != 1:
			raise ValueError(f'Selection not found: {selection}')
		selector_name = option[0][0]
		selector = option[0][1]

		return self.exec_option(selector_name,selector)

	def exec_option(self,selector_name :str, p_selector :Selector = None) -> bool:
		""" processes the exection of a given menu entry
		- pre process callback
		- selection function
		- post process callback
		- exec action
		returns True if the loop has to continue, false if the loop can be closed
		"""
		if not p_selector:
			selector = self.option(selector_name)
		else:
			selector = p_selector

		if self.pre_process_callback:
			self.pre_process_calback(self,selector_name)

		result = None
		if selector.func:
			result = selector.func()
			self._menu_options[selector_name].set_current_selection(result)
			self._data_store[selector_name] = result
		# we allow for a callback after we get the result
		if self.post_process_callback:
			self.post_process_callback(self,selector_name,result)
		# we have a callback, by option, to determine if we can exit the menu. Only if ALL mandatory fields are written
		if selector.exec_func:
			if selector.exec_func(result) and self._check_mandatory_status():
				return False
		return True

	def _set_kb_language(self):
		""" general for ArchInstall"""
		# Before continuing, set the preferred keyboard layout/language in the current terminal.
		# This will just help the user with the next following questions.
		if self._data_store.get('keyboard-layout', None) and len(self._data_store['keyboard-layout']):
			archinstall.set_keyboard_language(self._data_store['keyboard-layout'])

	def _verify_selection_enabled(self, selection_name :str) -> bool:
		""" general """
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

	def _menus_to_enable(self) -> dict:
		""" general """
		enabled_menus = {}

		for name, selection in self._menu_options.items():
			if self._verify_selection_enabled(name):
				enabled_menus[name] = selection

		return enabled_menus

	def option(self,name :str) -> Selector:
		# TODO check inexistent name
		return self._menu_options[name]

	def list_options(self) -> Iterator:
		""" Iterator to retrieve the enabled menu option names
		"""
		for item in self._menu_options:
			yield item

	def list_enabled_options(self) -> Iterator:
		""" Iterator to retrieve the enabled menu options at a given time.
		The results are dynamic (if between calls to the iterator some elements -still not retrieved- are (de)activated
		"""
		for item in self._menu_options:
			if item in self._menus_to_enable():
				yield item

	def set_option(self, name :str, selector :Selector):
		self._menu_options[name] = selector

	def _check_mandatory_status(self) -> bool:
		for field in self._menu_options:
			option = self._menu_options[field]
			if option.is_mandatory() and not option.has_selection():
				return False
		return True

	def set_mandatory(self, field :str, status :bool):
		self.option(field).set_mandatory(status)

	def mandatory_overview(self) -> [int, int]:
		mandatory_fields = 0
		mandatory_waiting = 0
		for field in self._menu_options:
			option = self._menu_options[field]
			if option.is_mandatory():
				mandatory_fields += 1
				if not option.has_selection():
					mandatory_waiting += 1
		return mandatory_fields, mandatory_waiting

class GlobalMenu(GeneralMenu):
	def __init__(self,
			pre_callback :Callable = None,
			post_callback :Callable = None,
			exit_callback :Callable = None):
		# the lambda in the callbacks is needed bc. the callbacks are methods of the
		# class, thus implicitly have the self (menu) parameter. The lambda consumes the explict reference
		# to the menu in the code
		super().__init__(data_store=archinstall.arguments,
				pre_callback=pre_callback,
				post_callback=post_callback if post_callback else lambda m,n,v:self._update_install(n,v),
				exit_callback=exit_callback if exit_callback else lambda m:self._post_processing)

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
				lambda: self._select_harddrives())
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
				display_func=lambda x: archinstall.secret(x) if x else 'None',
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
				display_func=lambda x: archinstall.secret(x) if x else 'None')
		self._menu_options['!superusers'] = \
			Selector(
				'Specify superuser account',
				lambda: self._create_superuser_account(),
				dependencies_not=['!root-password'],
				display_func=lambda x: list(x.keys()) if x else '')
		self._menu_options['!users'] = \
			Selector(
				'Specify user account',
				lambda: self._create_user_account(),
				default={},
				display_func=lambda x: list(x.keys()) if x else '[]')
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
				default=['linux'])
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
			Selector('Select timezone', lambda: archinstall.ask_for_a_timezone())
		self._menu_options['ntp'] = \
			Selector(
				'Set automatic time sync (NTP)',
				lambda: archinstall.ask_ntp(),
				default=True)
		self._menu_options['install'] = \
			Selector(
				self._install_text(),
				exec_func=lambda x: True if self._missing_configs() == 0 else False,
				enabled=True)
		self._menu_options['abort'] = Selector('Abort',exec_func=lambda x: exit(1), enabled=True)

	def _update_install(self,name :str = None ,result :Any = None):
		text = self._install_text()
		self._menu_options.get('install').update_description(text)

	def _post_processing(self):
		if archinstall.arguments.get('harddrives', None) and archinstall.arguments.get('!encryption-password', None):
			# If no partitions was marked as encrypted, but a password was supplied and we have some disks to format..
			# Then we need to identify which partitions to encrypt. This will default to / (root).
			if len(list(archinstall.encrypted_partitions(archinstall.arguments['disk_layouts']))) == 0:
				archinstall.arguments['disk_layouts'] = archinstall.select_encrypted_partitions(
					archinstall.arguments['disk_layouts'], archinstall.arguments['!encryption-password'])

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
		if not check('harddrives'):
			missing += 1
		if check('harddrives'):
			if not self._menu_options.get('harddrives').is_empty() and not check('disk_layouts'):
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

		# in case the harddrives got changed we have to reset the disk layout as well
		if old_haddrives != harddrives:
			self._menu_options.get('disk_layouts').set_current_selection(None)
			archinstall.arguments['disk_layouts'] = {}

		if not harddrives:
			prompt = 'You decided to skip harddrive selection\n'
			prompt += f"and will use whatever drive-setup is mounted at {archinstall.storage['MOUNT_POINT']} (experimental)\n"
			prompt += "WARNING: Archinstall won't check the suitability of this setup\n"

			prompt += 'Do you wish to continue?'
			choice = Menu(prompt, ['yes', 'no'], default_option='yes').run()

			if choice == 'no':
				return self._select_harddrives()

		return harddrives

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
		return superuser

	def _create_user_account(self):
		users, superusers = archinstall.ask_for_additional_users('Enter a username to create an additional user: ')
		if not archinstall.arguments.get('!superusers', None):
			archinstall.arguments['!superusers'] = superusers
		else:
			archinstall.arguments['!superusers'] = {**archinstall.arguments['!superusers'], **superusers}

		return users
