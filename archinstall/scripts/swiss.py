from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

import archinstall
from archinstall import SysInfo, info, debug
from archinstall.lib import mirrors
from archinstall.lib import models
from archinstall.lib import disk
from archinstall.lib import locale
from archinstall.lib.models import AudioConfiguration
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.lib import menu
from archinstall.lib.global_menu import GlobalMenu
from archinstall.lib.installer import Installer
from archinstall.lib.configuration import ConfigurationOutput

if TYPE_CHECKING:
	_: Any


class ExecutionMode(Enum):
	Full = 'full'
	Lineal = 'lineal'
	Only_HD = 'only-hd'
	Only_OS = 'only-os'
	Minimal = 'minimal'


def select_mode() -> ExecutionMode:
	options = [str(e.value) for e in ExecutionMode]
	choice = menu.Menu(
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

		self._menu_options['mode'] = menu.Selector(
			'Execution mode',
			lambda x : select_mode(),
			display_func=lambda x: x.value if x else '',
			default=ExecutionMode.Full)

		self._menu_options['continue'] = menu.Selector(
			'Continue',
			exec_func=lambda n,v: True)

		self.enable('archinstall-language')
		self.enable('ntp')
		self.enable('mode')
		self.enable('continue')
		self.enable('abort')

	def exit_callback(self):
		if self._data_store.get('mode', None):
			archinstall.arguments['mode'] = self._data_store['mode']
			info(f"Archinstall will execute under {archinstall.arguments['mode']} mode")


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
					'mirror_config', 'disk_config',
					'disk_encryption', 'swap', 'bootloader', 'hostname', '!root-password',
					'!users', 'profile_config', 'audio_config', 'kernels', 'packages', 'additional-repositories', 'network_config',
					'timezone', 'ntp'
				]

				if archinstall.arguments.get('advanced', False):
					options_list.extend(['locale_config'])

				mandatory_list = ['disk_config', 'bootloader', 'hostname']
			case ExecutionMode.Only_HD:
				options_list = ['disk_config', 'disk_encryption','swap']
				mandatory_list = ['disk_config']
			case ExecutionMode.Only_OS:
				options_list = [
					'mirror_config','bootloader', 'hostname',
					'!root-password', '!users', 'profile_config', 'audio_config', 'kernels',
					'packages', 'additional-repositories', 'network_config', 'timezone', 'ntp'
				]

				mandatory_list = ['hostname']

				if archinstall.arguments.get('advanced', False):
					options_list += ['locale_config']
			case ExecutionMode.Minimal:
				pass
			case _:
				info(f' Execution mode {self._execution_mode} not supported')
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
	disk_config: disk.DiskLayoutConfiguration = archinstall.arguments['disk_config']
	disk_encryption: disk.DiskEncryption = archinstall.arguments.get('disk_encryption', None)

	enable_testing = 'testing' in archinstall.arguments.get('additional-repositories', [])
	enable_multilib = 'multilib' in archinstall.arguments.get('additional-repositories', [])
	locale_config: locale.LocaleConfiguration = archinstall.arguments['locale_config']

	with Installer(
		mountpoint,
		disk_config,
		disk_encryption=disk_encryption,
		kernels=archinstall.arguments.get('kernels', ['linux'])
	) as installation:
		if exec_mode in [ExecutionMode.Full, ExecutionMode.Only_HD]:
			installation.mount_ordered_layout()

			installation.sanity_check()

			if disk_config.config_type != disk.DiskLayoutType.Pre_mount:
				if disk_encryption and disk_encryption.encryption_type != disk.EncryptionType.NoEncryption:
					# generate encryption key files for the mounted luks devices
					installation.generate_key_files()

			# Set mirrors used by pacstrap (outside of installation)
			if mirror_config := archinstall.arguments.get('mirror_config', None):
				if mirror_config.mirror_regions:
					mirrors.use_mirrors(mirror_config.mirror_regions)
				if mirror_config.custom_mirrors:
					mirrors.add_custom_mirrors(mirror_config.custom_mirrors)

			installation.minimal_installation(
				testing=enable_testing,
				multilib=enable_multilib,
				hostname=archinstall.arguments.get('hostname', 'archlinux'),
				locale_config=locale_config
			)

			if mirror_config := archinstall.arguments.get('mirror_config', None):
				installation.set_mirrors(mirror_config)  # Set the mirrors in the installation medium

			if archinstall.arguments.get('swap'):
				installation.setup_swap('zram')

			if archinstall.arguments.get("bootloader") == models.Bootloader.Grub and SysInfo.has_uefi():
				installation.add_additional_packages("grub")

			installation.add_bootloader(archinstall.arguments["bootloader"])

			# If user selected to copy the current ISO network configuration
			# Perform a copy of the config
			network_config = archinstall.arguments.get('network_config', None)

			if network_config:
				network_config.install_network_config(
					installation,
					archinstall.arguments.get('profile_config', None)
				)

			if users := archinstall.arguments.get('!users', None):
				installation.create_users(users)

			audio_config: Optional[AudioConfiguration] = archinstall.arguments.get('audio_config', None)
			if audio_config:
				audio_config.install_audio_config(installation)
			else:
				info("No audio server will be installed")

			if archinstall.arguments.get('packages', None) and archinstall.arguments.get('packages', None)[0] != '':
				installation.add_additional_packages(archinstall.arguments.get('packages', []))

			if profile_config := archinstall.arguments.get('profile_config', None):
				profile_handler.install_profile_config(installation, profile_config)

			if timezone := archinstall.arguments.get('timezone', None):
				installation.set_timezone(timezone)

			if archinstall.arguments.get('ntp', False):
				installation.activate_time_synchronization()

			if archinstall.accessibility_tools_in_use():
				installation.enable_espeakup()

			if (root_pw := archinstall.arguments.get('!root-password', None)) and len(root_pw):
				installation.user_set_pw('root', root_pw)

			# This step must be after profile installs to allow profiles_bck to install language pre-requisites.
			# After which, this step will set the language both for console and x11 if x11 was installed for instance.
			installation.set_keyboard_language(locale_config.kb_layout)

			if profile_config := archinstall.arguments.get('profile_config', None):
				profile_config.profile.post_install(installation)

			# If the user provided a list of services to be enabled, pass the list to the enable_service function.
			# Note that while it's called enable_service, it can actually take a list of services and iterate it.
			if archinstall.arguments.get('services', None):
				installation.enable_service(archinstall.arguments.get('services', []))

			# If the user provided custom commands to be run post-installation, execute them now.
			if archinstall.arguments.get('custom-commands', None):
				archinstall.run_custom_user_commands(archinstall.arguments['custom-commands'], installation)

			installation.genfstab()

			info("For post-installation tips, see https://wiki.archlinux.org/index.php/Installation_guide#Post-installation")

			if not archinstall.arguments.get('silent'):
				prompt = str(
					_('Would you like to chroot into the newly created installation and perform post-installation configuration?'))
				choice = menu.Menu(prompt, menu.Menu.yes_no(), default_option=menu.Menu.yes()).run()
				if choice.value == menu.Menu.yes():
					try:
						installation.drop_to_shell()
					except:
						pass

		debug(f"Disk states after installing: {disk.disk_layouts()}")


param_mode = archinstall.arguments.get('mode', ExecutionMode.Full.value).lower()

try:
	mode = ExecutionMode(param_mode)
except KeyError:
	info(f'Mode "{param_mode}" is not supported')
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
	fs_handler = disk.FilesystemHandler(
		archinstall.arguments['disk_config'],
		archinstall.arguments.get('disk_encryption', None)
	)

	fs_handler.perform_filesystem_operations()

perform_installation(archinstall.storage.get('MOUNT_POINT', Path('/mnt')), mode)
