from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import archinstall
from archinstall import SysInfo, debug, info
from archinstall.lib import disk, locale, models
from archinstall.lib.configuration import ConfigurationOutput
from archinstall.lib.global_menu import GlobalMenu
from archinstall.lib.installer import Installer
from archinstall.lib.interactions.general_conf import ask_chroot
from archinstall.lib.models import AudioConfiguration
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.tui import Alignment, FrameProperties, MenuItem, MenuItemGroup, ResultType, SelectMenu, Tui

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


class ExecutionMode(Enum):
	Guided = 'guided'
	Lineal = 'lineal'
	Only_HD = 'only-hd'
	Only_OS = 'only-os'
	Minimal = 'minimal'


class SwissMainMenu(GlobalMenu):
	def __init__(
		self,
		data_store: dict[str, Any],
		mode: ExecutionMode = ExecutionMode.Guided,
		advanced: bool = False
	):
		self._execution_mode = mode
		self._advanced = advanced
		super().__init__(data_store)

	def execute(self) -> None:
		ignore = ['install', 'abort']

		match self._execution_mode:
			case ExecutionMode.Guided:
				from archinstall.scripts.guided import guided
				guided()
			case ExecutionMode.Only_HD:
				from archinstall.scripts.only_hd import only_hd
				only_hd()
			case ExecutionMode.Minimal:
				from archinstall.scripts.minimal import minimal
				minimal()
			case ExecutionMode.Lineal:
				for item in self._menu_item_group.items:
					if self._menu_item_group.should_enable_item(item):
						if item.action is not None and item.key is not None:
							if item.key not in ignore:
								archinstall.arguments[item.key] = item.action(item.value)

				perform_installation(
					archinstall.arguments.get('mount_point', Path('/mnt')),
					self._execution_mode
				)
			case ExecutionMode.Only_OS:
				menu_items = [
					'mirror_config', 'bootloader', 'hostname',
					'!root-password', '!users', 'profile_config',
					'audio_config', 'kernels', 'packages',
					'additional-repositories', 'network_config', 'timezone', 'ntp'
				]
				mandatory_list = ['hostname']

				if self._advanced:
					menu_items += ['locale_config']

				for item in self._menu_item_group.items:
					if self._menu_item_group.should_enable_item(item):
						if item.action is not None and item.key is not None:
							if item.key not in ignore and item.key in menu_items:
								while True:
									value = item.action(item.value)
									if value not in mandatory_list or value is not None:
										archinstall.arguments[item.key] = item.action(item.value)
										break

				perform_installation(
					archinstall.arguments.get('mount_point', Path('/mnt')),
					self._execution_mode
				)
			case _:
				info(f' Execution mode {self._execution_mode} not supported')
				exit(1)


def ask_user_questions(mode: ExecutionMode = ExecutionMode.Guided) -> None:
	advanced = archinstall.arguments.get('advanced', False)

	with Tui():
		if advanced:
			header = str(_('Select execution mode'))
			items = [MenuItem(ex.name, value=ex) for ex in ExecutionMode]
			group = MenuItemGroup(items, sort_items=True)
			group.set_default_by_value(ExecutionMode.Guided)

			result = SelectMenu(
				group,
				header=header,
				allow_skip=True,
				alignment=Alignment.CENTER,
				frame=FrameProperties.min(str(_('Modes')))
			).run()

			if result.type_ == ResultType.Skip:
				exit(0)

			mode = result.get_value()

		SwissMainMenu(
			data_store=archinstall.arguments,
			mode=mode,
			advanced=advanced
		).execute()


def perform_installation(mountpoint: Path, exec_mode: ExecutionMode) -> None:
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
		installation.mount_ordered_layout()

		installation.sanity_check()

		if disk_config.config_type != disk.DiskLayoutType.Pre_mount:
			if disk_encryption and disk_encryption.encryption_type != disk.EncryptionType.NoEncryption:
				# generate encryption key files for the mounted luks devices
				installation.generate_key_files()

		if mirror_config := archinstall.arguments.get('mirror_config', None):
			installation.set_mirrors(mirror_config)

		installation.minimal_installation(
			testing=enable_testing,
			multilib=enable_multilib,
			hostname=archinstall.arguments.get('hostname', 'archlinux'),
			locale_config=locale_config
		)

		if mirror_config := archinstall.arguments.get('mirror_config', None):
			installation.set_mirrors(mirror_config, on_target=True)

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

		audio_config: AudioConfiguration | None = archinstall.arguments.get('audio_config', None)
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
			with Tui():
				chroot = ask_chroot()

			if chroot:
				try:
					installation.drop_to_shell()
				except Exception:
					pass

		debug(f"Disk states after installing:\n{disk.disk_layouts()}")


def swiss() -> None:
	param_mode = archinstall.arguments.get('mode', ExecutionMode.Guided.value).lower()

	try:
		mode = ExecutionMode(param_mode)
	except KeyError:
		info(f'Mode "{param_mode}" is not supported')
		exit(1)

	if not archinstall.arguments.get('silent'):
		ask_user_questions(mode)

	config = ConfigurationOutput(archinstall.arguments)
	config.write_debug()
	config.save()

	if archinstall.arguments.get('dry_run'):
		exit(0)

	if not archinstall.arguments.get('silent'):
		with Tui():
			if not config.confirm_config():
				debug('Installation aborted')
				swiss()

	fs_handler = disk.FilesystemHandler(
		archinstall.arguments['disk_config'],
		archinstall.arguments.get('disk_encryption', None)
	)

	fs_handler.perform_filesystem_operations()
	perform_installation(archinstall.arguments.get('mount_point', Path('/mnt')), mode)


swiss()
