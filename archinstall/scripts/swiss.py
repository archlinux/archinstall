import logging
import os
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

import archinstall
from archinstall import Selector, GlobalMenu, \
	log, Installer, DiskLayoutConfiguration, DiskEncryption, use_mirrors, Bootloader
from ..lib.configuration import ConfigurationOutput
from ..lib.disk.device_handler import disk_layouts
from ..lib.disk.device_model import DiskLayoutType, EncryptionType
from ..lib.disk.filesystem import Filesystem
from ..lib.menu import Menu
from ..lib.models.network_configuration import NetworkConfigurationHandler
from ..profiles.applications.pipewire import PipewireProfile

if TYPE_CHECKING:
	_: Any


if archinstall.arguments.get('help'):
	print("See `man archinstall` for help.")
	exit(0)


if os.getuid() != 0:
	print("Archinstall requires root privileges to run. See --help for more.")
	exit(1)


class ExecutionMode(Enum):
	Full = 'full'
	Lineal = 'lineal'
	Only_HD = 'only-hd'
	Only_OS = 'only-os'
	Minimal = 'minimal'


def select_mode() -> ExecutionMode:
	options = [str(e.value) for e in ExecutionMode]
	choice = Menu(
		str(_('Select an execution mode')),
		options,
		default_option=ExecutionMode.Full.value,
		skip=False
	).run()

	return ExecutionMode(choice.single_value)


class SetupMenu(GlobalMenu):
	def __init__(self, storage_area: Dict[str, Any]):
		super().__init__(data_store=storage_area)

	def setup_selection_menu_options(self):
		super().setup_selection_menu_options()

		self._menu_options['mode'] = Selector(
			'Excution mode',
			lambda x : select_mode(),
			display_func=lambda x: x.value if x else '',
			default=ExecutionMode.Full)

		self._menu_options['continue'] = Selector(
			'Continue',
			exec_func=lambda n,v: True)

		self.enable('archinstall-language')
		self.enable('ntp')
		self.enable('mode')
		self.enable('continue')
		self.enable('abort')

	def exit_callback(self):
		if self._data_store.get('ntp', False):
			archinstall.SysCommand('timedatectl set-ntp true')

		if self._data_store.get('mode', None):
			archinstall.arguments['mode'] = self._data_store['mode']
			log(f"Archinstall will execute under {archinstall.arguments['mode']} mode")


class SwissMainMenu(GlobalMenu):
	def __init__(
		self,
		data_store: Dict[str, Any],
		exec_mode: ExecutionMode = ExecutionMode.Full
	):
		self._execution_mode = exec_mode
		super().__init__(data_store)

	def setup_selection_menu_options(self):
		super().setup_selection_menu_options()

		options_list = []
		mandatory_list = []

		match self._execution_mode:
			case ExecutionMode.Full | ExecutionMode.Lineal:
				options_list = [
					'keyboard-layout', 'mirror-region', 'disk_config',
					'disk_encryption', 'swap', 'bootloader', 'hostname', '!root-password',
					'!users', 'profile', 'audio', 'kernels', 'packages', 'additional-repositories', 'nic',
					'timezone', 'ntp'
				]

				if archinstall.arguments.get('advanced', False):
					options_list.extend(['sys-language', 'sys-encoding'])

				mandatory_list = ['disk_config', 'bootloader', 'hostname']
			case ExecutionMode.Only_HD:
				options_list = ['disk_config', 'disk_encryption','swap']
				mandatory_list = ['disk_config']
			case ExecutionMode.Only_OS:
				options_list = [
					'keyboard-layout', 'mirror-region','bootloader', 'hostname',
					'!root-password', '!users', 'profile', 'audio', 'kernels',
					'packages', 'additional-repositories', 'nic', 'timezone', 'ntp'
				]

				mandatory_list = ['hostname']

				if archinstall.arguments.get('advanced', False):
					options_list += ['sys-language','sys-encoding']
			case ExecutionMode.Minimal:
				pass
			case _:
				archinstall.log(f' Execution mode {self._execution_mode} not supported')
				exit(1)

		if self._execution_mode != ExecutionMode.Lineal:
			options_list += ['save_config', 'install']

			if not archinstall.arguments.get('advanced', False):
				options_list.append('archinstall-language')

		options_list += ['abort']

		for entry in mandatory_list:
			self.enable(entry, mandatory=True)

		for entry in options_list:
			self.enable(entry)


def ask_user_questions(exec_mode: ExecutionMode = ExecutionMode.Full):
	"""
		First, we'll ask the user for a bunch of user input.
		Not until we're satisfied with what we want to install
		will we continue with the actual installation steps.
	"""
	if archinstall.arguments.get('advanced', None):
		setup_area: Dict[str, Any] = {}
		setup = SetupMenu(setup_area)

		if exec_mode == ExecutionMode.Lineal:
			for entry in setup.list_enabled_options():
				if entry in ('continue', 'abort'):
					continue
				if not setup.option(entry).enabled:
					continue
				setup.exec_option(entry)
		else:
			setup.run()

		archinstall.arguments['archinstall-language'] = setup_area.get('archinstall-language')

	with SwissMainMenu(data_store=archinstall.arguments, exec_mode=exec_mode) as menu:
		if mode == ExecutionMode.Lineal:
			for entry in menu.list_enabled_options():
				if entry in ('install', 'abort'):
					continue
				menu.exec_option(entry)
				archinstall.arguments[entry] = menu.option(entry).get_selection()
		else:
			menu.run()


def perform_installation(mountpoint: Path, exec_mode: ExecutionMode):
	disk_config: DiskLayoutConfiguration = archinstall.arguments['disk_config']
	disk_encryption: DiskEncryption = archinstall.arguments.get('disk_encryption', None)

	enable_testing = 'testing' in archinstall.arguments.get('additional-repositories', [])
	enable_multilib = 'multilib' in archinstall.arguments.get('additional-repositories', [])

	locale = f"{archinstall.arguments.get('sys-language', 'en_US')} {archinstall.arguments.get('sys-encoding', 'UTF-8').upper()}"

	with Installer(
		mountpoint,
		disk_config,
		disk_encryption=disk_encryption,
		kernels=archinstall.arguments.get('kernels', ['linux'])
	) as installation:
		if exec_mode in [ExecutionMode.Full, ExecutionMode.Only_HD]:
			installation.mount_ordered_layout()

			installation.sanity_check()

			if disk_config.config_type != DiskLayoutType.Pre_mount:
				if disk_encryption and disk_encryption.encryption_type != EncryptionType.NoEncryption:
					# generate encryption key files for the mounted luks devices
					installation.generate_key_files()

			if archinstall.arguments.get('ntp', False):
				installation.activate_ntp()

			# Set mirrors used by pacstrap (outside of installation)
			if archinstall.arguments.get('mirror-region', None):
				use_mirrors(archinstall.arguments['mirror-region'])  # Set the mirrors for the live medium

			installation.minimal_installation(
				testing=enable_testing,
				multilib=enable_multilib,
				hostname=archinstall.arguments.get('hostname', 'archlinux'),
				locales=[locale]
			)

			if archinstall.arguments.get('mirror-region') is not None:
				if archinstall.arguments.get("mirrors", None) is not None:
					installation.set_mirrors(
						archinstall.arguments['mirror-region'])  # Set the mirrors in the installation medium

			if archinstall.arguments.get('swap'):
				installation.setup_swap('zram')

			if archinstall.arguments.get("bootloader") == Bootloader.Grub and archinstall.has_uefi():
				installation.add_additional_packages("grub")

			installation.add_bootloader(archinstall.arguments["bootloader"])

			# If user selected to copy the current ISO network configuration
			# Perform a copy of the config
			network_config = archinstall.arguments.get('nic', None)

			if network_config:
				handler = NetworkConfigurationHandler(network_config)
				handler.config_installer(installation)

			if archinstall.arguments.get('packages', None) and archinstall.arguments.get('packages', None)[0] != '':
				installation.add_additional_packages(archinstall.arguments.get('packages', None))

			if users := archinstall.arguments.get('!users', None):
				installation.create_users(users)

			if audio := archinstall.arguments.get('audio', None):
				log(f'Installing audio server: {audio}', level=logging.INFO)
				if audio == 'pipewire':
					PipewireProfile().install(installation)
				elif audio == 'pulseaudio':
					installation.add_additional_packages("pulseaudio")
			else:
				installation.log("No audio server will be installed.", level=logging.INFO)

			if archinstall.arguments.get('profile', None):
				installation.install_profile(archinstall.arguments.get('profile', None))

			if timezone := archinstall.arguments.get('timezone', None):
				installation.set_timezone(timezone)

			if archinstall.arguments.get('ntp', False):
				installation.activate_time_syncronization()

			if archinstall.accessibility_tools_in_use():
				installation.enable_espeakup()

			if (root_pw := archinstall.arguments.get('!root-password', None)) and len(root_pw):
				installation.user_set_pw('root', root_pw)

			# This step must be after profile installs to allow profiles_bck to install language pre-requisits.
			# After which, this step will set the language both for console and x11 if x11 was installed for instance.
			installation.set_keyboard_language(archinstall.arguments['keyboard-layout'])

			if profile := archinstall.arguments.get('profile', None):
				profile.post_install(installation)

			# If the user provided a list of services to be enabled, pass the list to the enable_service function.
			# Note that while it's called enable_service, it can actually take a list of services and iterate it.
			if archinstall.arguments.get('services', None):
				installation.enable_service(*archinstall.arguments['services'])

			# If the user provided custom commands to be run post-installation, execute them now.
			if archinstall.arguments.get('custom-commands', None):
				archinstall.run_custom_user_commands(archinstall.arguments['custom-commands'], installation)

			installation.genfstab()

			installation.log(
				"For post-installation tips, see https://wiki.archlinux.org/index.php/Installation_guide#Post-installation",
				fg="yellow")

			if not archinstall.arguments.get('silent'):
				prompt = str(
					_('Would you like to chroot into the newly created installation and perform post-installation configuration?'))
				choice = Menu(prompt, Menu.yes_no(), default_option=Menu.yes()).run()
				if choice.value == Menu.yes():
					try:
						installation.drop_to_shell()
					except:
						pass

		archinstall.log(f"Disk states after installing: {disk_layouts()}", level=logging.DEBUG)


# Log various information about hardware before starting the installation. This might assist in troubleshooting
archinstall.log(f"Hardware model detected: {archinstall.sys_vendor()} {archinstall.product_name()}; UEFI mode: {archinstall.has_uefi()}", level=logging.DEBUG)
archinstall.log(f"Processor model detected: {archinstall.cpu_model()}", level=logging.DEBUG)
archinstall.log(f"Memory statistics: {archinstall.mem_available()} available out of {archinstall.mem_total()} total installed", level=logging.DEBUG)
archinstall.log(f"Virtualization detected: {archinstall.virtualization()}; is VM: {archinstall.is_vm()}", level=logging.DEBUG)
archinstall.log(f"Graphics devices detected: {archinstall.graphics_devices().keys()}", level=logging.DEBUG)

# For support reasons, we'll log the disk layout pre installation to match against post-installation layout
archinstall.log(f"Disk states before installing: {disk_layouts()}", level=logging.DEBUG)


if not archinstall.check_mirror_reachable():
	log_file = os.path.join(archinstall.storage.get('LOG_PATH', None), archinstall.storage.get('LOG_FILE', None))
	archinstall.log(f"Arch Linux mirrors are not reachable. Please check your internet connection and the log file '{log_file}'.", level=logging.INFO, fg="red")
	exit(1)

param_mode = archinstall.arguments.get('mode', ExecutionMode.Full.value).lower()

try:
	mode = ExecutionMode(param_mode)
except KeyError:
	log(f'Mode "{param_mode}" is not supported')
	exit(1)

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

if mode in (ExecutionMode.Full, ExecutionMode.Only_HD):
	fs = Filesystem(
		archinstall.arguments['disk_config'],
		archinstall.arguments.get('disk_encryption', None)
	)

	fs.perform_filesystem_operations()

perform_installation(archinstall.storage.get('MOUNT_POINT', Path('/mnt')), mode)
