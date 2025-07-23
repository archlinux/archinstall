from __future__ import annotations

from typing import override

from archinstall.lib.disk.disk_menu import DiskLayoutConfigurationMenu
from archinstall.lib.models.application import ApplicationConfiguration
from archinstall.lib.models.authentication import AuthenticationConfiguration
from archinstall.lib.models.device import DiskLayoutConfiguration, DiskLayoutType, EncryptionType, FilesystemType, PartitionModification
from archinstall.lib.packages import list_available_packages
from archinstall.tui.menu_item import MenuItem, MenuItemGroup

from .applications.application_menu import ApplicationMenu
from .args import ArchConfig
from .authentication.authentication_menu import AuthenticationMenu
from .configuration import save_config
from .hardware import SysInfo
from .interactions.general_conf import (
	add_number_of_parallel_downloads,
	ask_additional_packages_to_install,
	ask_for_a_timezone,
	ask_hostname,
	ask_ntp,
)
from .interactions.network_menu import ask_to_configure_network
from .interactions.system_conf import ask_for_bootloader, ask_for_swap, ask_for_uki, select_kernel
from .locale.locale_menu import LocaleMenu
from .menu.abstract_menu import CONFIG_KEY, AbstractMenu
from .mirrors import MirrorMenu
from .models.bootloader import Bootloader
from .models.locale import LocaleConfiguration
from .models.mirrors import MirrorConfiguration
from .models.network import NetworkConfiguration, NicType
from .models.packages import Repository
from .models.profile import ProfileConfiguration
from .output import FormattedOutput
from .pacman.config import PacmanConfig
from .translationhandler import Language, tr, translation_handler


class GlobalMenu(AbstractMenu[None]):
	def __init__(self, arch_config: ArchConfig) -> None:
		self._arch_config = arch_config
		menu_optioons = self._get_menu_options()

		self._item_group = MenuItemGroup(
			menu_optioons,
			sort_items=False,
			checkmarks=True,
		)

		super().__init__(self._item_group, config=arch_config)

	def _get_menu_options(self) -> list[MenuItem]:
		menu_options = [
			MenuItem(
				text=tr('Archinstall language'),
				action=self._select_archinstall_language,
				display_action=lambda x: x.display_name if x else '',
				key='archinstall_language',
			),
			MenuItem(
				text=tr('Locales'),
				action=self._locale_selection,
				preview_action=self._prev_locale,
				key='locale_config',
			),
			MenuItem(
				text=tr('Mirrors and repositories'),
				action=self._mirror_configuration,
				preview_action=self._prev_mirror_config,
				key='mirror_config',
			),
			MenuItem(
				text=tr('Disk configuration'),
				action=self._select_disk_config,
				preview_action=self._prev_disk_config,
				mandatory=True,
				key='disk_config',
			),
			MenuItem(
				text=tr('Swap'),
				value=True,
				action=ask_for_swap,
				preview_action=self._prev_swap,
				key='swap',
			),
			MenuItem(
				text=tr('Bootloader'),
				value=Bootloader.get_default(),
				action=self._select_bootloader,
				preview_action=self._prev_bootloader,
				mandatory=True,
				key='bootloader',
			),
			MenuItem(
				text=tr('Unified kernel images'),
				value=False,
				enabled=SysInfo.has_uefi(),
				action=ask_for_uki,
				preview_action=self._prev_uki,
				key='uki',
			),
			MenuItem(
				text=tr('Hostname'),
				value='archlinux',
				action=ask_hostname,
				preview_action=self._prev_hostname,
				key='hostname',
			),
			MenuItem(
				text=tr('Authentication'),
				action=self._select_authentication,
				preview_action=self._prev_authentication,
				key='auth_config',
			),
			MenuItem(
				text=tr('Profile'),
				action=self._select_profile,
				preview_action=self._prev_profile,
				key='profile_config',
			),
			MenuItem(
				text=tr('Applications'),
				action=self._select_applications,
				value=[],
				preview_action=self._prev_applications,
				key='app_config',
			),
			MenuItem(
				text=tr('Kernels'),
				value=['linux'],
				action=select_kernel,
				preview_action=self._prev_kernel,
				mandatory=True,
				key='kernels',
			),
			MenuItem(
				text=tr('Network configuration'),
				action=ask_to_configure_network,
				value={},
				preview_action=self._prev_network_config,
				key='network_config',
			),
			MenuItem(
				text=tr('Parallel Downloads'),
				action=add_number_of_parallel_downloads,
				value=0,
				preview_action=self._prev_parallel_dw,
				key='parallel_downloads',
			),
			MenuItem(
				text=tr('Additional packages'),
				action=self._select_additional_packages,
				value=[],
				preview_action=self._prev_additional_pkgs,
				key='packages',
			),
			MenuItem(
				text=tr('Timezone'),
				action=ask_for_a_timezone,
				value='UTC',
				preview_action=self._prev_tz,
				key='timezone',
			),
			MenuItem(
				text=tr('Automatic time sync (NTP)'),
				action=ask_ntp,
				value=True,
				preview_action=self._prev_ntp,
				key='ntp',
			),
			MenuItem(
				text='',
			),
			MenuItem(
				text=tr('Save configuration'),
				action=lambda x: self._safe_config(),
				key=f'{CONFIG_KEY}_save',
			),
			MenuItem(
				text=tr('Install'),
				preview_action=self._prev_install_invalid_config,
				key=f'{CONFIG_KEY}_install',
			),
			MenuItem(
				text=tr('Abort'),
				action=lambda x: exit(1),
				key=f'{CONFIG_KEY}_abort',
			),
		]

		return menu_options

	def _safe_config(self) -> None:
		# data: dict[str, Any] = {}
		# for item in self._item_group.items:
		# 	if item.key is not None:
		# 		data[item.key] = item.value

		self.sync_all_to_config()
		save_config(self._arch_config)

	def _missing_configs(self) -> list[str]:
		item: MenuItem = self._item_group.find_by_key('auth_config')
		auth_config: AuthenticationConfiguration | None = item.value

		def check(s: str) -> bool:
			item = self._item_group.find_by_key(s)
			return item.has_value()

		def has_superuser() -> bool:
			if auth_config and auth_config.users:
				return any([u.sudo for u in auth_config.users])
			return False

		missing = set()

		if (auth_config is None or auth_config.root_enc_password is None) and not has_superuser():
			missing.add(
				tr('Either root-password or at least 1 user with sudo privileges must be specified'),
			)

		for item in self._item_group.items:
			if item.mandatory:
				assert item.key is not None
				if not check(item.key):
					missing.add(item.text)

		return list(missing)

	@override
	def _is_config_valid(self) -> bool:
		"""
		Checks the validity of the current configuration.
		"""
		if len(self._missing_configs()) != 0:
			return False
		return self._validate_bootloader() is None

	def _select_archinstall_language(self, preset: Language) -> Language:
		from .interactions.general_conf import select_archinstall_language

		language = select_archinstall_language(translation_handler.translated_languages, preset)
		translation_handler.activate(language)

		self._update_lang_text()

		return language

	def _select_applications(self, preset: ApplicationConfiguration | None) -> ApplicationConfiguration | None:
		app_config = ApplicationMenu(preset).run()
		return app_config

	def _select_authentication(self, preset: AuthenticationConfiguration | None) -> AuthenticationConfiguration | None:
		auth_config = AuthenticationMenu(preset).run()
		return auth_config

	def _update_lang_text(self) -> None:
		"""
		The options for the global menu are generated with a static text;
		each entry of the menu needs to be updated with the new translation
		"""
		new_options = self._get_menu_options()

		for o in new_options:
			if o.key is not None:
				self._item_group.find_by_key(o.key).text = o.text

	def _locale_selection(self, preset: LocaleConfiguration) -> LocaleConfiguration:
		locale_config = LocaleMenu(preset).run()
		return locale_config

	def _prev_locale(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		config: LocaleConfiguration = item.value
		return config.preview()

	def _prev_network_config(self, item: MenuItem) -> str | None:
		if item.value:
			network_config: NetworkConfiguration = item.value
			if network_config.type == NicType.MANUAL:
				output = FormattedOutput.as_table(network_config.nics)
			else:
				output = f'{tr("Network configuration")}:\n{network_config.type.display_msg()}'

			return output
		return None

	def _prev_additional_pkgs(self, item: MenuItem) -> str | None:
		if item.value:
			output = '\n'.join(sorted(item.value))
			return output
		return None

	def _prev_authentication(self, item: MenuItem) -> str | None:
		if item.value:
			auth_config: AuthenticationConfiguration = item.value
			output = ''

			if auth_config.root_enc_password:
				output += f'{tr("Root password")}: {auth_config.root_enc_password.hidden()}\n'

			if auth_config.users:
				output += FormattedOutput.as_table(auth_config.users) + '\n'

			if auth_config.u2f_config:
				u2f_config = auth_config.u2f_config
				login_method = u2f_config.u2f_login_method.display_value()
				output = tr('U2F login method: ') + login_method

				output += '\n'
				output += tr('Passwordless sudo: ') + (tr('Enabled') if u2f_config.passwordless_sudo else tr('Disabled'))

			return output

		return None

	def _prev_applications(self, item: MenuItem) -> str | None:
		if item.value:
			app_config: ApplicationConfiguration = item.value
			output = ''

			if app_config.bluetooth_config:
				output += f'{tr("Bluetooth")}: '
				output += tr('Enabled') if app_config.bluetooth_config.enabled else tr('Disabled')
				output += '\n'

			if app_config.audio_config:
				audio_config = app_config.audio_config
				output += f'{tr("Audio")}: {audio_config.audio.value}'
				output += '\n'

			return output

		return None

	def _prev_tz(self, item: MenuItem) -> str | None:
		if item.value:
			return f'{tr("Timezone")}: {item.value}'
		return None

	def _prev_ntp(self, item: MenuItem) -> str | None:
		if item.value is not None:
			output = f'{tr("NTP")}: '
			output += tr('Enabled') if item.value else tr('Disabled')
			return output
		return None

	def _prev_disk_config(self, item: MenuItem) -> str | None:
		disk_layout_conf: DiskLayoutConfiguration | None = item.value

		if disk_layout_conf:
			output = tr('Configuration type: {}').format(disk_layout_conf.config_type.display_msg()) + '\n'

			if disk_layout_conf.config_type == DiskLayoutType.Pre_mount:
				output += tr('Mountpoint') + ': ' + str(disk_layout_conf.mountpoint)

			if disk_layout_conf.lvm_config:
				output += '{}: {}'.format(tr('LVM configuration type'), disk_layout_conf.lvm_config.config_type.display_msg()) + '\n'

			if disk_layout_conf.disk_encryption:
				output += tr('Disk encryption') + ': ' + EncryptionType.type_to_text(disk_layout_conf.disk_encryption.encryption_type) + '\n'

			if disk_layout_conf.btrfs_options:
				btrfs_options = disk_layout_conf.btrfs_options
				if btrfs_options.snapshot_config:
					output += tr('Btrfs snapshot type: {}').format(btrfs_options.snapshot_config.snapshot_type.value) + '\n'

			return output

		return None

	def _prev_swap(self, item: MenuItem) -> str | None:
		if item.value is not None:
			output = f'{tr("Swap on zram")}: '
			output += tr('Enabled') if item.value else tr('Disabled')
			return output
		return None

	def _prev_uki(self, item: MenuItem) -> str | None:
		if item.value is not None:
			output = f'{tr("Unified kernel images")}: '
			output += tr('Enabled') if item.value else tr('Disabled')
			return output
		return None

	def _prev_hostname(self, item: MenuItem) -> str | None:
		if item.value is not None:
			return f'{tr("Hostname")}: {item.value}'
		return None

	def _prev_parallel_dw(self, item: MenuItem) -> str | None:
		if item.value is not None:
			return f'{tr("Parallel Downloads")}: {item.value}'
		return None

	def _prev_kernel(self, item: MenuItem) -> str | None:
		if item.value:
			kernel = ', '.join(item.value)
			return f'{tr("Kernel")}: {kernel}'
		return None

	def _prev_bootloader(self, item: MenuItem) -> str | None:
		if item.value is not None:
			return f'{tr("Bootloader")}: {item.value.value}'
		return None

	def _validate_bootloader(self) -> str | None:
		"""
		Checks the selected bootloader is valid for the selected filesystem
		type of the boot partition.

		Returns [`None`] if the bootloader is valid, otherwise returns a
		string with the error message.

		XXX: The caller is responsible for wrapping the string with the translation
			shim if necessary.
		"""
		bootloader: Bootloader | None = None
		root_partition: PartitionModification | None = None
		boot_partition: PartitionModification | None = None
		efi_partition: PartitionModification | None = None

		bootloader = self._item_group.find_by_key('bootloader').value

		if disk_config := self._item_group.find_by_key('disk_config').value:
			for layout in disk_config.device_modifications:
				if root_partition := layout.get_root_partition():
					break
			for layout in disk_config.device_modifications:
				if boot_partition := layout.get_boot_partition():
					break
			if SysInfo.has_uefi():
				for layout in disk_config.device_modifications:
					if efi_partition := layout.get_efi_partition():
						break
		else:
			return 'No disk layout selected'

		if root_partition is None:
			return 'Root partition not found'

		if boot_partition is None:
			return 'Boot partition not found'

		if SysInfo.has_uefi():
			if efi_partition is None:
				return 'EFI system partition (ESP) not found'

			if efi_partition.fs_type not in [FilesystemType.Fat12, FilesystemType.Fat16, FilesystemType.Fat32]:
				return 'ESP must be formatted as a FAT filesystem'

		if bootloader == Bootloader.Limine:
			if boot_partition.fs_type not in [FilesystemType.Fat12, FilesystemType.Fat16, FilesystemType.Fat32]:
				return 'Limine does not support booting with a non-FAT boot partition'

		return None

	def _prev_install_invalid_config(self, item: MenuItem) -> str | None:
		if missing := self._missing_configs():
			text = tr('Missing configurations:\n')
			for m in missing:
				text += f'- {m}\n'
			return text[:-1]  # remove last new line

		if error := self._validate_bootloader():
			return tr(f'Invalid configuration: {error}')

		return None

	def _prev_profile(self, item: MenuItem) -> str | None:
		profile_config: ProfileConfiguration | None = item.value

		if profile_config and profile_config.profile:
			output = tr('Profiles') + ': '
			if profile_names := profile_config.profile.current_selection_names():
				output += ', '.join(profile_names) + '\n'
			else:
				output += profile_config.profile.name + '\n'

			if profile_config.gfx_driver:
				output += tr('Graphics driver') + ': ' + profile_config.gfx_driver.value + '\n'

			if profile_config.greeter:
				output += tr('Greeter') + ': ' + profile_config.greeter.value + '\n'

			return output

		return None

	def _select_disk_config(
		self,
		preset: DiskLayoutConfiguration | None = None,
	) -> DiskLayoutConfiguration | None:
		disk_config = DiskLayoutConfigurationMenu(preset).run()

		return disk_config

	def _select_bootloader(self, preset: Bootloader | None) -> Bootloader | None:
		bootloader = ask_for_bootloader(preset)

		if bootloader:
			uki = self._item_group.find_by_key('uki')
			if not SysInfo.has_uefi() or not bootloader.has_uki_support():
				uki.value = False
				uki.enabled = False
			else:
				uki.enabled = True

		return bootloader

	def _select_profile(self, current_profile: ProfileConfiguration | None) -> ProfileConfiguration | None:
		from .profile.profile_menu import ProfileMenu

		profile_config = ProfileMenu(preset=current_profile).run()
		return profile_config

	def _select_additional_packages(self, preset: list[str]) -> list[str]:
		config: MirrorConfiguration | None = self._item_group.find_by_key('mirror_config').value

		repositories: set[Repository] = set()
		if config:
			repositories = set(config.optional_repositories)

		packages = ask_additional_packages_to_install(
			preset,
			repositories=repositories,
		)

		return packages

	def _mirror_configuration(self, preset: MirrorConfiguration | None = None) -> MirrorConfiguration:
		mirror_configuration = MirrorMenu(preset=preset).run()

		if mirror_configuration.optional_repositories:
			# reset the package list cache in case the repository selection has changed
			list_available_packages.cache_clear()

			# enable the repositories in the config
			pacman_config = PacmanConfig(None)
			pacman_config.enable(mirror_configuration.optional_repositories)
			pacman_config.apply()

		return mirror_configuration

	def _prev_mirror_config(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		mirror_config: MirrorConfiguration = item.value

		output = ''
		if mirror_config.mirror_regions:
			title = tr('Selected mirror regions')
			divider = '-' * len(title)
			regions = mirror_config.region_names
			output += f'{title}\n{divider}\n{regions}\n\n'

		if mirror_config.custom_servers:
			title = tr('Custom servers')
			divider = '-' * len(title)
			servers = mirror_config.custom_server_urls
			output += f'{title}\n{divider}\n{servers}\n\n'

		if mirror_config.optional_repositories:
			title = tr('Optional repositories')
			divider = '-' * len(title)
			repos = ', '.join([r.value for r in mirror_config.optional_repositories])
			output += f'{title}\n{divider}\n{repos}\n\n'

		if mirror_config.custom_repositories:
			title = tr('Custom repositories')
			table = FormattedOutput.as_table(mirror_config.custom_repositories)
			output += f'{title}:\n\n{table}'

		return output.strip()
