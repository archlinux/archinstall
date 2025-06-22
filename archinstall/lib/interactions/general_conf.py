from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import assert_never

from archinstall.lib.models.packages import Repository
from archinstall.lib.packages.packages import list_available_packages
from archinstall.lib.translationhandler import tr
from archinstall.tui.curses_menu import EditMenu, SelectMenu, Tui
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType
from archinstall.tui.types import Alignment, FrameProperties, Orientation, PreviewStyle

from ..locale.utils import list_timezones
from ..models.packages import AvailablePackage, PackageGroup
from ..output import warn
from ..translationhandler import Language


class PostInstallationAction(Enum):
	EXIT = tr('Exit archinstall')
	REBOOT = tr('Reboot system')
	CHROOT = tr('chroot into installation for post-installation configurations')


def ask_ntp(preset: bool = True) -> bool:
	header = tr('Would you like to use automatic time synchronization (NTP) with the default time servers?\n') + '\n'
	header += (
		tr(
			'Hardware time and other post-configuration steps might be required in order for NTP to work.\nFor more information, please check the Arch wiki',
		)
		+ '\n'
	)

	preset_val = MenuItem.yes() if preset else MenuItem.no()
	group = MenuItemGroup.yes_no()
	group.focus_item = preset_val

	result = SelectMenu[bool](
		group,
		header=header,
		allow_skip=True,
		alignment=Alignment.CENTER,
		columns=2,
		orientation=Orientation.HORIZONTAL,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.item() == MenuItem.yes()
		case _:
			raise ValueError('Unhandled return type')


def ask_hostname(preset: str | None = None) -> str | None:
	result = EditMenu(
		tr('Hostname'),
		alignment=Alignment.CENTER,
		allow_skip=True,
		default_text=preset,
	).input()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			hostname = result.text()
			if len(hostname) < 1:
				return None
			return hostname
		case ResultType.Reset:
			raise ValueError('Unhandled result type')


def ask_for_a_timezone(preset: str | None = None) -> str | None:
	default = 'UTC'
	timezones = list_timezones()

	items = [MenuItem(tz, value=tz) for tz in timezones]
	group = MenuItemGroup(items, sort_items=True)
	group.set_selected_by_value(preset)
	group.set_default_by_value(default)

	result = SelectMenu[str](
		group,
		allow_reset=True,
		allow_skip=True,
		frame=FrameProperties.min(tr('Timezone')),
		alignment=Alignment.CENTER,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return default
		case ResultType.Selection:
			return result.get_value()


def select_language(preset: str | None = None) -> str | None:
	from ..locale.locale_menu import select_kb_layout

	# We'll raise an exception in an upcoming version.
	# from ..exceptions import Deprecated
	# raise Deprecated("select_language() has been deprecated, use select_kb_layout() instead.")

	# No need to translate this i feel, as it's a short lived message.
	warn('select_language() is deprecated, use select_kb_layout() instead. select_language() will be removed in a future version')

	return select_kb_layout(preset)


def select_archinstall_language(languages: list[Language], preset: Language) -> Language:
	# these are the displayed language names which can either be
	# the english name of a language or, if present, the
	# name of the language in its own language

	items = [MenuItem(lang.display_name, lang) for lang in languages]
	group = MenuItemGroup(items, sort_items=True)
	group.set_focus_by_value(preset)

	title = 'NOTE: If a language can not displayed properly, a proper font must be set manually in the console.\n'
	title += 'All available fonts can be found in "/usr/share/kbd/consolefonts"\n'
	title += 'e.g. setfont LatGrkCyr-8x16 (to display latin/greek/cyrillic characters)\n'

	result = SelectMenu[Language](
		group,
		header=title,
		allow_skip=True,
		allow_reset=False,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(header=tr('Select language')),
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Reset:
			raise ValueError('Language selection not handled')


def ask_additional_packages_to_install(
	preset: list[str] = [],
	repositories: set[Repository] = set(),
) -> list[str]:
	repositories |= {Repository.Core, Repository.Extra}

	respos_text = ', '.join([r.value for r in repositories])
	output = tr('Repositories: {}').format(respos_text) + '\n'

	output += tr('Loading packages...')
	Tui.print(output, clear_screen=True)

	packages = list_available_packages(tuple(repositories))
	package_groups = PackageGroup.from_available_packages(packages)

	# Additional packages (with some light weight error handling for invalid package names)
	header = tr('Only packages such as base, base-devel, linux, linux-firmware, efibootmgr and optional profile packages are installed.') + '\n'
	header += tr('Select any packages from the below list that should be installed additionally') + '\n'

	# there are over 15k packages so this needs to be quick
	preset_packages: list[AvailablePackage | PackageGroup] = []
	for p in preset:
		if p in packages:
			preset_packages.append(packages[p])
		elif p in package_groups:
			preset_packages.append(package_groups[p])

	items = [
		MenuItem(
			name,
			value=pkg,
			preview_action=lambda x: x.value.info(),
		)
		for name, pkg in packages.items()
	]

	items += [
		MenuItem(
			name,
			value=group,
			preview_action=lambda x: x.value.info(),
		)
		for name, group in package_groups.items()
	]

	menu_group = MenuItemGroup(items, sort_items=True)
	menu_group.set_selected_by_value(preset_packages)

	result = SelectMenu[AvailablePackage | PackageGroup](
		menu_group,
		header=header,
		alignment=Alignment.LEFT,
		allow_reset=True,
		allow_skip=True,
		multi=True,
		preview_frame=FrameProperties.max('Package info'),
		preview_style=PreviewStyle.RIGHT,
		preview_size='auto',
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return []
		case ResultType.Selection:
			selected_pacakges = result.get_values()
			return [pkg.name for pkg in selected_pacakges]


def add_number_of_parallel_downloads(preset: int | None = None) -> int | None:
	max_recommended = 5

	header = tr('This option enables the number of parallel downloads that can occur during package downloads') + '\n'
	header += tr('Enter the number of parallel downloads to be enabled.\n\nNote:\n')
	header += tr(' - Maximum recommended value : {} ( Allows {} parallel downloads at a time )').format(max_recommended, max_recommended) + '\n'
	header += tr(' - Disable/Default : 0 ( Disables parallel downloading, allows only 1 download at a time )\n')

	def validator(s: str | None) -> str | None:
		if s is not None:
			try:
				value = int(s)
				if value >= 0:
					return None
			except Exception:
				pass

		return tr('Invalid download number')

	result = EditMenu(
		tr('Number downloads'),
		header=header,
		allow_skip=True,
		allow_reset=True,
		validator=validator,
		default_text=str(preset) if preset is not None else None,
	).input()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return 0
		case ResultType.Selection:
			downloads: int = int(result.text())
		case _:
			assert_never(result.type_)

	pacman_conf_path = Path('/etc/pacman.conf')
	with pacman_conf_path.open() as f:
		pacman_conf = f.read().split('\n')

	with pacman_conf_path.open('w') as fwrite:
		for line in pacman_conf:
			if 'ParallelDownloads' in line:
				fwrite.write(f'ParallelDownloads = {downloads}\n')
			else:
				fwrite.write(f'{line}\n')

	return downloads


def ask_post_installation() -> PostInstallationAction:
	header = tr('Installation completed') + '\n\n'
	header += tr('What would you like to do next?') + '\n'

	items = [MenuItem(action.value, value=action) for action in PostInstallationAction]
	group = MenuItemGroup(items)

	result = SelectMenu[PostInstallationAction](
		group,
		header=header,
		allow_skip=False,
		alignment=Alignment.CENTER,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case _:
			raise ValueError('Post installation action not handled')


def ask_abort() -> None:
	prompt = tr('Do you really want to abort?') + '\n'
	group = MenuItemGroup.yes_no()

	result = SelectMenu[bool](
		group,
		header=prompt,
		allow_skip=False,
		alignment=Alignment.CENTER,
		columns=2,
		orientation=Orientation.HORIZONTAL,
	).run()

	if result.item() == MenuItem.yes():
		exit(0)
