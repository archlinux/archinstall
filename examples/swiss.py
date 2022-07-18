"""

Script swiss (army knife)
Designed to make different workflows for the installation process. Which is controlled by  the argument --mode
mode full  guides the full process of installation
mode disk only proceeds to the creation of the disk infraestructure (partition, mount points, encryption)
mode software processes only the installation of Archlinux and software at --mountpoint (or /mnt/archinstall)
mode recover (still not implemented)
mode lineal. Instead of a menu, shows a sequence of selection screens (eq. to the old mode for guided.py)

When using the argument --advanced. an additional menu for several special parameters needed during installation appears

This script respects the --dry_run argument

"""
import logging
import os
from typing import TYPE_CHECKING, Any
if TYPE_CHECKING:
	_: Any

from inspect import getsourcefile

if __name__ == '__main__':
	# to be able to execute simply as python examples/guided.py or (from inside examples python guided.py)
	# will work only with the copy at examples
	# this solution was taken from https://stackoverflow.com/questions/714063/importing-modules-from-parent-folder/33532002#33532002
	import sys
	current_path = os.path.abspath(getsourcefile(lambda: 0))
	current_dir = os.path.dirname(current_path)
	parent_dir = current_dir[:current_dir.rfind(os.path.sep)]
	sys.path.append(parent_dir)

import archinstall
from archinstall import ConfigurationOutput, Menu
from archinstall.examples.guided import perform_filesystem_operations, perform_installation

"""
particular routines to SetupMenu
TODO exec con return parameter
"""
def select_activate_NTP():
	prompt = "Would you like to use automatic time synchronization (NTP) with the default time servers? [Y/n]: "
	choice = Menu(prompt, Menu.yes_no(), default_option=Menu.yes()).run()
	if choice == Menu.yes():
		return True
	else:
		return False


def select_mode():
	return archinstall.generic_select(['full','disk','software','recover','lineal'],
								'Select one execution mode',
								default=archinstall.arguments.get('mode','full'))


"""
following functions will be at locale_helpers, so they will have to be called prefixed by archinstall
"""
def get_locale_mode_text(mode):
	if mode == 'LC_ALL':
		mode_text = "general (LC_ALL)"
	elif mode == "LC_CTYPE":
		mode_text = "Character set"
	elif mode == "LC_NUMERIC":
		mode_text = "Numeric values"
	elif mode == "LC_TIME":
		mode_text = "Time Values"
	elif mode == "LC_COLLATE":
		mode_text = "sort order"
	elif mode == "LC_MESSAGES":
		mode_text = "text messages"
	else:
		mode_text = "Unassigned"
	return mode_text

def reset_cmd_locale():
	""" sets the cmd_locale to its saved default """
	archinstall.storage['CMD_LOCALE'] = archinstall.storage.get('CMD_LOCALE_DEFAULT',{})

def unset_cmd_locale():
	""" archinstall will use the execution environment default """
	archinstall.storage['CMD_LOCALE'] = {}

def set_cmd_locale(general :str = None,
				charset :str = 'C',
				numbers :str = 'C',
				time :str = 'C',
				collate :str = 'C',
				messages :str = 'C'):
	"""
	Set the cmd locale.
	If the parameter general is specified, it takes precedence over the rest (might as well not exist)
	The rest define some specific settings above the installed default language. If anyone of this parameters is none means the installation default
	"""
	installed_locales = list_installed_locales()
	result = {}
	if general:
		if general in installed_locales:
			archinstall.storage['CMD_LOCALE'] = {'LC_ALL':general}
		else:
			archinstall.log(f"{get_locale_mode_text('LC_ALL')} {general} is not installed. Defaulting to C",fg="yellow",level=logging.WARNING)
		return

	if numbers:
		if numbers in installed_locales:
			result["LC_NUMERIC"] = numbers
		else:
			archinstall.log(f"{get_locale_mode_text('LC_NUMERIC')} {numbers} is not installed. Defaulting to installation language",fg="yellow",level=logging.WARNING)
	if charset:
		if charset in installed_locales:
			result["LC_CTYPE"] = charset
		else:
			archinstall.log(f"{get_locale_mode_text('LC_CTYPE')} {charset} is not installed. Defaulting to installation language",fg="yellow",level=logging.WARNING)
	if time:
		if time in installed_locales:
			result["LC_TIME"] = time
		else:
			archinstall.log(f"{get_locale_mode_text('LC_TIME')} {time} is not installed. Defaulting to installation language",fg="yellow",level=logging.WARNING)
	if collate:
		if collate in installed_locales:
			result["LC_COLLATE"] = collate
		else:
			archinstall.log(f"{get_locale_mode_text('LC_COLLATE')} {collate} is not installed. Defaulting to installation language",fg="yellow",level=logging.WARNING)
	if messages:
		if messages in installed_locales:
			result["LC_MESSAGES"] = messages
		else:
			archinstall.log(f"{get_locale_mode_text('LC_MESSAGES')} {messages} is not installed. Defaulting to installation language",fg="yellow",level=logging.WARNING)
	archinstall.storage['CMD_LOCALE'] = result

def list_installed_locales() -> list[str]:
	lista = []
	for line in archinstall.SysCommand('locale -a'):
		lista.append(line.decode('UTF-8').strip())
	return lista


"""
end of locale helpers
"""

def select_installed_locale(mode):
	mode_text = get_locale_mode_text(mode)
	if mode == 'LC_ALL':
		texto = "Select the default execution locale \nIf none, you will be prompted for specific settings"
	else:
		texto = f"Select the {mode_text} ({mode}) execution locale \nIf none, you will get the installation default"
	return archinstall.generic_select([None] + list_installed_locales(),
								texto,
								allow_empty_input=True,
								default=archinstall.storage.get('CMD_LOCALE',{}).get(mode,'C'))


"""
	_menus
"""

class SetupMenu(archinstall.GeneralMenu):
	def __init__(self,storage_area):
		super().__init__(data_store=storage_area)

	def _setup_selection_menu_options(self):
		self.set_option('archinstall-language',
			archinstall.Selector(
				_('Archinstall language'),
				lambda x: self._select_archinstall_language(x),
				default='English',
				enabled=True))
		self.set_option('ntp',
		archinstall.Selector(
			'Activate NTP',
			lambda x: select_activate_NTP(),
			default='Y',
			enabled=True))
		self.set_option('mode',
			archinstall.Selector(
				'Excution mode',
				lambda x : select_mode(),
				default='full',
				enabled=True))
		for item in ['LC_ALL','LC_CTYPE','LC_NUMERIC','LC_TIME','LC_MESSAGES','LC_COLLATE']:
			self.set_option(item,
				archinstall.Selector(
					f'{get_locale_mode_text(item)} locale',
					lambda x,item=item: select_installed_locale(item),   # the parameter is needed for the lambda in the loop
					enabled=True,
					dependencies_not=['LC_ALL'] if item != 'LC_ALL' else []))
		self.option('LC_ALL').set_enabled(True)
		self.set_option('continue',
		archinstall.Selector(
			'Continue',
			exec_func=lambda n,v: True,
			enabled=True))

	def exit_callback(self):
		if self._data_store.get('ntp',False):
			archinstall.log("Hardware time and other post-configuration steps might be required in order for NTP to work. For more information, please check the Arch wiki.", fg="yellow")
			archinstall.SysCommand('timedatectl set-ntp true')
		if self._data_store.get('mode',None):
			archinstall.arguments['mode'] = self._data_store['mode']
			archinstall.log(f"Archinstall will execute under {archinstall.arguments['mode']} mode")
		if self._data_store.get('LC_ALL',None):
			archinstall.storage['CMD_LOCALE'] = {'LC_ALL':self._data_store['LC_ALL']}
		else:
			exec_locale = {}
			for item in ['LC_COLLATE','LC_CTYPE','LC_MESSAGES','LC_NUMERIC','LC_TIME']:
				if self._data_store.get(item,None):
					exec_locale[item] = self._data_store[item]
			archinstall.storage['CMD_LOCALE'] = exec_locale
		archinstall.log(f"Archinstall will execute with {archinstall.storage.get('CMD_LOCALE',None)} locale")

class MyMenu(archinstall.GlobalMenu):
	def __init__(self,data_store=archinstall.arguments,mode='full'):
		self._execution_mode = mode
		super().__init__(data_store)

	def _setup_selection_menu_options(self):
		super()._setup_selection_menu_options()
		options_list = []
		mandatory_list = []
		if self._execution_mode in ('full','lineal'):
			options_list = ['keyboard-layout', 'mirror-region', 'sys-language',
							'sys-encoding','harddrives', 'disk_layouts','!encryption-password', 'bootloader', 'swap',
							'hostname', '!root-password', '!users','profile', 'audio', 'kernels',
							'packages', 'nic', 'timezone', 'ntp', 'additional-repositories']
			if archinstall.arguments.get('advanced',False) or archinstall.arguments.get('HSM',False):
				options_list.append('HSM')
			mandatory_list = ['bootloader','hostname']
		elif self._execution_mode == 'disk':
			options_list = ['harddrives', 'disk_layouts', '!encryption-password','swap']
			if archinstall.arguments.get('advanced',False) or archinstall.arguments.get('HSM',False):
				options_list.append('HSM')
			mandatory_list = []
		elif self._execution_mode == 'software':
			self._disk_check = False
			options_list = ['keyboard-layout', 'mirror-region', 'sys-language',
							'sys-encoding',
							'hostname', '!root-password', '!users','profile', 'audio', 'kernels',
							'packages', 'nic', 'timezone', 'ntp', 'additional-repositories']
			mandatory_list = ['hostname']
		elif self._execution_mode == 'recover':
			pass
		else:
			archinstall.log(f"self._execution_mode {self._execution_mode} not supported")
			exit(1)
		if self._execution_mode != 'lineal':
			options_list.extend(['__separator__','save_config','install','abort'])
			if not archinstall.arguments.get('advanced'):
				options_list.append('archinstall-language')

		for entry in self._menu_options:
			if entry in options_list:
				# for not lineal executions, only self.option(entry).set_enabled and set_mandatory are necessary
				if entry in mandatory_list:
					self.enable(entry,mandatory=True)
				else:
					self.enable(entry)
			else:
				self.option(entry).set_enabled(False)
		self._update_install_text()

	def post_callback(self,option=None,value=None):
		self._update_install_text()

	def _missing_configs(self):
		def check(s):
			return self.option(s).has_selection()

		def has_superuser() -> bool:
			users = self._menu_options['!users'].current_selection
			return any([u.sudo for u in users])

		mandatory_nr, missing_ones, missing = self.mandatory_overview()
		if self._disk_check :
			if not check('harddrives'):
				missing += [str(_('Drive(s)'))]
			if check('harddrives'):
				if not self._menu_options['harddrives'].is_empty() and not check('disk_layouts'):
					missing += [str(_('Disk layout'))]

		if self._execution_mode in ('full','software'):
			if not check('!root-password') and not has_superuser():
				missing += [str(_('Either root-password or at least 1 user with sudo privileges must be specified'))]

		return missing

	def _install_text(self):
		missing = len(self._missing_configs())
		if missing > 0:
			return _('Install ({} config(s) missing)').format(missing)
		return _('Install')

	def _update_install_text(self):
		text = self._install_text()
		self.option('install').update_description(text)


def ask_user_questions(mode):
	"""
		First, we'll ask the user for a bunch of user input.
		Not until we're satisfied with what we want to install
		will we continue with the actual installation steps.
	"""
	if archinstall.arguments.get('advanced',None):
		# 3.9 syntax. former x = {**y,**z} or x.update(y)
		set_cmd_locale(charset='es_ES.utf8',collate='es_ES.utf8')
		setup_area = archinstall.storage.get('CMD_LOCALE',{}) | {}
		with SetupMenu(setup_area) as setup:
			if mode == 'lineal':
				for entry in setup.list_enabled_options():
					if entry in ('continue','abort'):
						continue
					if not setup.option(entry).enabled:
						continue
					setup.exec_option(entry)
			else:
				setup.run()
		archinstall.arguments['archinstall-language'] = setup_area.get('archinstall-language')
	else:
		archinstall.log("Hardware time and other post-configuration steps might be required in order for NTP to work. For more information, please check the Arch wiki.", fg="yellow")
		archinstall.SysCommand('timedatectl set-ntp true')

	with MyMenu(data_store=archinstall.arguments,mode=archinstall.arguments.get('mode', 'full')) as global_menu:

		if mode == 'lineal':
			for entry in global_menu.list_enabled_options():
				if entry in ('install','abort'):
					continue
				global_menu.exec_option(entry)
				archinstall.arguments[entry] = global_menu.option(entry).get_selection()
		else:
			global_menu.set_option('install',
							archinstall.Selector(
								global_menu._install_text(),
								exec_func=lambda n,v: True if global_menu._missing_configs() == 0 else False,
								preview_func=global_menu._prev_install_missing_config,
								no_store=True, enabled=True))
			global_menu.run()


nomen = getsourcefile(lambda: 0)
script_name = nomen[nomen.rfind(os.path.sep) + 1:nomen.rfind('.')]

if __name__ in ('__main__',script_name):
	mode = archinstall.arguments.get('mode', 'full').lower()
	if not archinstall.arguments.get('silent'):
		ask_user_questions(mode)

	config_output = ConfigurationOutput(archinstall.arguments)
	if not archinstall.arguments.get('silent'):
		config_output.show()
	config_output.save()

	if archinstall.arguments.get('dry_run'):
		exit(0)
	if not archinstall.arguments.get('silent'):
		input('Press Enter to continue.')

	if mode in ('full','disk'):
		perform_filesystem_operations()
	perform_installation(archinstall.storage.get('MOUNT_POINT', '/mnt'), archinstall.arguments.get('mode', 'full').lower())
