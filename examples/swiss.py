"""

Script swiss (army knife)
Designed to make different workflows for the installation process. Which is controlled by  the argument --mode
mode full  guides the full process of installation
mode only_hd only proceeds to the creation of the disk infraestructure (partition, mount points, encryption)
mode only_os processes only the installation of Archlinux and software at --mountpoint (or /mnt/archinstall)
mode minimal (still not implemented)
mode lineal. Instead of a menu, shows a sequence of selection screens (eq. to the old mode for guided.py)

When using the argument --advanced. an additional menu for several special parameters needed during installation appears

This script respects the --dry_run argument

"""
import logging
import os
import time
import pathlib
from typing import TYPE_CHECKING, Any

import archinstall
from archinstall import ConfigurationOutput, NetworkConfigurationHandler, Menu

if TYPE_CHECKING:
	_: Any

if archinstall.arguments.get('help'):
	print("See `man archinstall` for help.")
	exit(0)
if os.getuid() != 0:
	print("Archinstall requires root privileges to run. See --help for more.")
	exit(1)

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
	return archinstall.generic_select(['full','only_hd','only_os','minimal','lineal'],
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
		self.set_option(
			'archinstall-language',
			archinstall.Selector(
				_('Archinstall language'),
				lambda x: self._select_archinstall_language(x),
				display_func=lambda x: x.display_name,
				default=self.translation_handler.get_language_by_abbr('en'),
				enabled=True
			)
		)

		self.set_option(
			'ntp',
			archinstall.Selector(
				'Activate NTP',
				lambda x: select_activate_NTP(),
				default='Y',
				enabled=True
			)
		)

		self.set_option(
			'mode',
			archinstall.Selector(
				'Excution mode',
				lambda x : select_mode(),
				default='full',
				enabled=True)
		)

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
			options_list = ['keyboard-layout', 'mirror-region', 'harddrives', 'disk_layouts',
					'!encryption-password','swap', 'bootloader', 'hostname', '!root-password',
					'!users', 'profile', 'audio', 'kernels', 'packages','additional-repositories','nic',
					'timezone', 'ntp']
			if archinstall.arguments.get('advanced',False):
				options_list.extend(['sys-language','sys-encoding'])
			mandatory_list = ['harddrives','bootloader','hostname']
		elif self._execution_mode == 'only_hd':
			options_list = ['harddrives', 'disk_layouts', '!encryption-password','swap']
			mandatory_list = ['harddrives']
		elif self._execution_mode == 'only_os':
			options_list = ['keyboard-layout', 'mirror-region','bootloader', 'hostname',
					'!root-password', '!users', 'profile', 'audio', 'kernels',
					'packages', 'additional-repositories', 'nic', 'timezone', 'ntp']
			mandatory_list = ['hostname']
			if archinstall.arguments.get('advanced',False):
				options_list.expand(['sys-language','sys-encoding'])
		elif self._execution_mode == 'minimal':
			pass
		else:
			archinstall.log(f"self._execution_mode {self._execution_mode} not supported")
			exit(1)
		if self._execution_mode != 'lineal':
			options_list.extend(['save_config','install','abort'])
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
		self._update_install_text(self._execution_mode)

	def _missing_configs(self,mode='full'):
		def check(s):
			return self.option(s).has_selection()

		def has_superuser() -> bool:
			users = self._menu_options['!users'].current_selection
			return any([u.sudo for u in users])

		_, missing = self.mandatory_overview()
		if mode in ('full','only_os') and (not check('!root-password') and not has_superuser()):
			missing += 1
		if mode in ('full', 'only_hd') and check('harddrives'):
			if not self.option('harddrives').is_empty() and not check('disk_layouts'):
				missing += 1
		return missing

	def _install_text(self,mode='full'):
		missing = self._missing_configs(mode)
		if missing > 0:
			return f'Instalation ({missing} config(s) missing)'
		return 'Install'

	def _update_install_text(self, mode='full'):
		text = self._install_text(mode)
		self.option('install').update_description(text)


"""
Installation general subroutines
"""

def get_current_status():
	# Log various information about hardware before starting the installation. This might assist in troubleshooting
	archinstall.log(f"Hardware model detected: {archinstall.sys_vendor()} {archinstall.product_name()}; UEFI mode: {archinstall.has_uefi()}", level=logging.DEBUG)
	archinstall.log(f"Processor model detected: {archinstall.cpu_model()}", level=logging.DEBUG)
	archinstall.log(f"Memory statistics: {archinstall.mem_available()} available out of {archinstall.mem_total()} total installed", level=logging.DEBUG)
	archinstall.log(f"Virtualization detected: {archinstall.virtualization()}; is VM: {archinstall.is_vm()}", level=logging.DEBUG)
	archinstall.log(f"Graphics devices detected: {archinstall.graphics_devices().keys()}", level=logging.DEBUG)

	# For support reasons, we'll log the disk layout pre installation to match against post-installation layout
	archinstall.log(f"Disk states before installing: {archinstall.disk_layouts()}", level=logging.DEBUG)

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

	with MyMenu(data_store=archinstall.arguments,mode=mode) as global_menu:

		if mode == 'lineal':
			for entry in global_menu.list_enabled_options():
				if entry in ('install','abort'):
					continue
				global_menu.exec_option(entry)
				archinstall.arguments[entry] = global_menu.option(entry).get_selection()
		else:
			global_menu.set_option('install',
							archinstall.Selector(
								global_menu._install_text(mode),
								exec_func=lambda n,v: True if global_menu._missing_configs(mode) == 0 else False,
								enabled=True))

			global_menu.run()

def perform_filesystem_operations():
	"""
		Issue a final warning before we continue with something un-revertable.
		We mention the drive one last time, and count from 5 to 0.
	"""

	if archinstall.arguments.get('harddrives', None):
		print(f" ! Formatting {archinstall.arguments['harddrives']} in ", end='')
		archinstall.do_countdown()

		"""
			Setup the blockdevice, filesystem (and optionally encryption).
			Once that's done, we'll hand over to perform_installation()
		"""

		mode = archinstall.GPT
		if archinstall.has_uefi() is False:
			mode = archinstall.MBR

		for drive in archinstall.arguments.get('harddrives', []):
			if archinstall.arguments.get('disk_layouts', {}).get(drive.path):
				with archinstall.Filesystem(drive, mode) as fs:
					fs.load_layout(archinstall.arguments['disk_layouts'][drive.path])

def disk_setup(installation):
	# Mount all the drives to the desired mountpoint
	# This *can* be done outside of the installation, but the installer can deal with it.
	if archinstall.arguments.get('disk_layouts'):
		installation.mount_ordered_layout(archinstall.arguments['disk_layouts'])

	# Placing /boot check during installation because this will catch both re-use and wipe scenarios.
	for partition in installation.partitions:
		if partition.mountpoint == installation.target + '/boot':
			if partition.size < 0.19:  # ~200 MiB in GiB
				raise archinstall.DiskError(
					f"The selected /boot partition in use is not large enough to properly install a boot loader. Please resize it to at least 200MiB and re-run the installation.")

def os_setup(installation):
	# if len(mirrors):
	# Certain services might be running that affects the system during installation.
	# Currently, only one such service is "reflector.service" which updates /etc/pacman.d/mirrorlist
	# We need to wait for it before we continue since we opted in to use a custom mirror/region.
	installation.log('Waiting for automatic mirror selection (reflector) to complete.', level=logging.INFO)
	while archinstall.service_state('reflector') not in ('dead', 'failed'):
		time.sleep(1)
	# Set mirrors used by pacstrap (outside of installation)
	if archinstall.arguments.get('mirror-region', None):
		archinstall.use_mirrors(archinstall.arguments['mirror-region'])  # Set the mirrors for the live medium
	if installation.minimal_installation():
		installation.set_locale(archinstall.arguments['sys-language'], archinstall.arguments['sys-encoding'].upper())
		installation.set_hostname(archinstall.arguments['hostname'])
		if archinstall.arguments['mirror-region'].get("mirrors", None) is not None:
			installation.set_mirrors(
				archinstall.arguments['mirror-region'])  # Set the mirrors in the installation medium
		if archinstall.arguments["bootloader"] == "grub-install" and archinstall.has_uefi():
			installation.add_additional_packages("grub")
		installation.add_bootloader(archinstall.arguments["bootloader"])
		if archinstall.arguments['swap']:
			installation.setup_swap('zram')

		network_config = archinstall.arguments.get('nic', None)

		if network_config:
			handler = NetworkConfigurationHandler(network_config)
			handler.config_installer(installation)

		if archinstall.arguments.get('audio', None) is not None:
			installation.log(f"This audio server will be used: {archinstall.arguments.get('audio', None)}",level=logging.INFO)
			if archinstall.arguments.get('audio', None) == 'pipewire':
				archinstall.Application(installation, 'pipewire').install()
			elif archinstall.arguments.get('audio', None) == 'pulseaudio':
				print('Installing pulseaudio ...')
				installation.add_additional_packages("pulseaudio")
		else:
			installation.log("No audio server will be installed.", level=logging.INFO)

		if archinstall.arguments.get('packages', None) and archinstall.arguments.get('packages', None)[0] != '':
			installation.add_additional_packages(archinstall.arguments.get('packages', None))

		if archinstall.arguments.get('profile', None):
			installation.install_profile(archinstall.arguments.get('profile', None))

		if users := archinstall.arguments.get('!users', None):
			installation.create_users(users)

		if timezone := archinstall.arguments.get('timezone', None):
			installation.set_timezone(timezone)

		if archinstall.arguments.get('ntp', False):
			installation.activate_time_syncronization()

		if archinstall.accessibility_tools_in_use():
			installation.enable_espeakup()

		if (root_pw := archinstall.arguments.get('!root-password', None)) and len(root_pw):
			installation.user_set_pw('root', root_pw)

		# This step must be after profile installs to allow profiles to install language pre-requisits.
		# After which, this step will set the language both for console and x11 if x11 was installed for instance.
		installation.set_keyboard_language(archinstall.arguments['keyboard-layout'])

		if archinstall.arguments['profile'] and archinstall.arguments['profile'].has_post_install():
			with archinstall.arguments['profile'].load_instructions(
				namespace=f"{archinstall.arguments['profile'].namespace}.py") as imported:
				if not imported._post_install():
					archinstall.log(' * Profile\'s post configuration requirements was not fulfilled.', fg='red')
					exit(1)

	# If the user provided a list of services to be enabled, pass the list to the enable_service function.
	# Note that while it's called enable_service, it can actually take a list of services and iterate it.
	if archinstall.arguments.get('services', None):
		installation.enable_service(*archinstall.arguments['services'])

	# If the user provided custom commands to be run post-installation, execute them now.
	if archinstall.arguments.get('custom-commands', None):
		archinstall.run_custom_user_commands(archinstall.arguments['custom-commands'], installation)


def perform_installation(mountpoint, mode):
	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	with archinstall.Installer(mountpoint, kernels=archinstall.arguments.get('kernels', ['linux'])) as installation:
		if mode in ('full','only_hd'):
			disk_setup(installation)
			if mode == 'only_hd':
				target = pathlib.Path(f"{mountpoint}/etc/fstab")
				if not target.parent.exists():
					target.parent.mkdir(parents=True)

		if mode in ('full','only_os'):
			os_setup(installation)
			installation.log("For post-installation tips, see https://wiki.archlinux.org/index.php/Installation_guide#Post-installation", fg="yellow")
			if not archinstall.arguments.get('silent'):
				prompt = 'Would you like to chroot into the newly created installation and perform post-installation configuration?'
				choice = Menu(prompt, Menu.yes_no(), default_option=Menu.yes()).run()
				if choice == Menu.yes():
					try:
						installation.drop_to_shell()
					except:
						pass

	# For support reasons, we'll log the disk layout post installation (crash or no crash)
	archinstall.log(f"Disk states after installing: {archinstall.disk_layouts()}", level=logging.DEBUG)


if not archinstall.check_mirror_reachable():
	log_file = os.path.join(archinstall.storage.get('LOG_PATH', None), archinstall.storage.get('LOG_FILE', None))
	archinstall.log(f"Arch Linux mirrors are not reachable. Please check your internet connection and the log file '{log_file}'.", level=logging.INFO, fg="red")
	exit(1)

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

if mode in ('full','only_hd'):
	perform_filesystem_operations()
perform_installation(archinstall.storage.get('MOUNT_POINT', '/mnt'), mode)
