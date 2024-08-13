from __future__ import annotations

import pathlib
from typing import List, Any, Optional, TYPE_CHECKING

from ..locale import list_timezones
from ..models.audio_configuration import Audio, AudioConfiguration
from ..output import warn
from ..packages.packages import validate_package_list
from ..storage import storage
from ..translationhandler import Language
from archinstall.tui import (
	MenuItemGroup, MenuItem, SelectMenu,
	FrameProperties, Alignment, Result, ResultType, EditMenu
)
from archinstall.tui import (
	MenuItemGroup, MenuItem, SelectMenu,
	FrameProperties, Alignment, EditMenu,
	Orientation, tui
)

if TYPE_CHECKING:
	_: Any


def ask_ntp(preset: bool = True) -> bool:
	header = str(_('Would you like to use automatic time synchronization (NTP) with the default time servers?\n')) + '\n'
	header += str( _('Hardware time and other post-configuration steps might be required in order for NTP to work.\nFor more information, please check the Arch wiki')) + '\n'

	preset_val = MenuItem.yes() if preset else MenuItem.no()
	group = MenuItemGroup.yes_no()
	group.focus_item = preset_val

	result = SelectMenu(
		group,
		header=header,
		allow_skip=True,
		alignment=Alignment.CENTER,
		columns=2,
		orientation=Orientation.HORIZONTAL
	).single()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			if result.item is None:
				return preset

			return result.item == MenuItem.yes()

	return False


def ask_hostname(preset: str = '') -> str:
	result = EditMenu(
		str(_('Hostname')),
		alignment=Alignment.CENTER,
		allow_skip=True,
	).input()

	if not result.item:
		return preset

	return result.item


def ask_for_a_timezone(preset: Optional[str] = None) -> Optional[str]:
	default = 'UTC'

	items = [MenuItem(tz, value=tz) for tz in list_timezones()]
	group = MenuItemGroup(items, sort_items=True)
	group.set_selected_by_value(preset)
	group.set_default_by_value(default)

	result = SelectMenu(
		group,
		allow_reset=True,
		allow_skip=True,
		frame=FrameProperties.minimal(str(_('Timezone'))),
		alignment=Alignment.CENTER,
	).single()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return default
		case ResultType.Selection:
			if result.item is None:
				return preset
			return result.item.value


def ask_for_audio_selection(preset: Optional[AudioConfiguration] = None) -> Optional[AudioConfiguration]:
	items = [MenuItem(a.value, value=a) for a in Audio]
	group = MenuItemGroup(items)

	if preset:
		group.set_focus_by_value(preset.audio)

	result = SelectMenu(
		group,
		allow_skip=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.minimal(str(_('Audio')))
	).single()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			if result.item is None or result.item.value is None:
				return None
			return AudioConfiguration(audio=result.item.value)

	return None


def select_language(preset: Optional[str] = None) -> Optional[str]:
	from ..locale.locale_menu import select_kb_layout

	# We'll raise an exception in an upcoming version.
	# from ..exceptions import Deprecated
	# raise Deprecated("select_language() has been deprecated, use select_kb_layout() instead.")

	# No need to translate this i feel, as it's a short lived message.
	warn(
		"select_language() is deprecated, use select_kb_layout() instead. select_language() will be removed in a future version")

	return select_kb_layout(preset)


def select_archinstall_language(languages: List[Language], preset: Language) -> Language:
	# these are the displayed language names which can either be
	# the english name of a language or, if present, the
	# name of the language in its own language

	items = [MenuItem(lang.display_name, lang) for lang in languages]
	group = MenuItemGroup(items, sort_items=True)
	group.set_focus_by_value(preset)

	title = 'NOTE: If a language can not displayed properly, a proper font must be set manually in the console.\n'
	title += 'All available fonts can be found in "/usr/share/kbd/consolefonts"\n'
	title += 'e.g. setfont LatGrkCyr-8x16 (to display latin/greek/cyrillic characters)\n'

	choice: Result[MenuItem] = SelectMenu(
		group,
		header=title,
		allow_skip=True,
		allow_reset=False,
		alignment=Alignment.CENTER,
		frame=FrameProperties.minimal(header=str(_('Select language')))
	).single()

	match choice.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return choice.item.value

	raise ValueError('Language selection not handled')


def ask_additional_packages_to_install(preset: List[str] = []) -> List[str]:
	# Additional packages (with some light weight error handling for invalid package names)
	header = str(_('Only packages such as base, base-devel, linux, linux-firmware, efibootmgr and optional profile packages are installed.')) + '\n'
	header += str(_('If you desire a web browser, such as firefox or chromium, you may specify it in the following prompt.')) + '\n'
	header += str(_('Write additional packages to install (space separated, leave blank to skip)'))

	def validator(value: str) -> Optional[str]:
		packages = value.split() if value else []

		if len(packages) == 0:
			return None

		if storage['arguments']['offline'] or storage['arguments']['no_pkg_lookups']:
			return None

		# Verify packages that were given
		out = str(_("Verifying that additional packages exist (this might take a few seconds)"))
		tui.print(out, 0)
		valid, invalid = validate_package_list(packages)

		if invalid:
			return f'{str(_("Some packages could not be found in the repository"))}: {invalid}'

		return None

	result = EditMenu(
		str(_('Additional packages')),
		alignment=Alignment.CENTER,
		allow_skip=True,
		edit_width=100,
		validator=validator
	).input()

	if result.item:
		packages = result.item.split()
		return packages

	return preset


def add_number_of_parallel_downloads(preset: Optional[int] = None) -> Optional[int]:
	max_recommended = 5

	header = str(_('This option enables the number of parallel downloads that can occur during package downloads')) + '\n'
	header += str(_('Enter the number of parallel downloads to be enabled.\n\nNote:\n'))
	header += str(_(' - Maximum recommended value : {} ( Allows {} parallel downloads at a time )')).format(max_recommended, max_recommended) + '\n'
	header += str(_(' - Disable/Default : 0 ( Disables parallel downloading, allows only 1 download at a time )\n'))

	def validator(s: str) -> Optional[str]:
		try:
			value = int(s)
			if value >= 0:
				return None
		except Exception:
			pass

		return str(_('Invalid download number'))

	result = EditMenu(
		str(_('Number downloads')),
		header=header,
		allow_skip=True,
		allow_reset=True,
		validator=validator
	).input()

	if result.type_ == ResultType.Skip:
		return preset

	downloads: int = int(result.item)

	pacman_conf_path = pathlib.Path("/etc/pacman.conf")
	with pacman_conf_path.open() as f:
		pacman_conf = f.read().split("\n")

	with pacman_conf_path.open("w") as fwrite:
		for line in pacman_conf:
			if "ParallelDownloads" in line:
				fwrite.write(f"ParallelDownloads = {downloads}\n")
			else:
				fwrite.write(f"{line}\n")

	return downloads


def select_additional_repositories(preset: List[str]) -> List[str]:
	"""
	Allows the user to select additional repositories (multilib, and testing) if desired.

	:return: The string as a selected repository
	:rtype: string
	"""

	repositories = ["multilib", "testing"]
	items = [MenuItem(r, value=r) for r in repositories]
	group = MenuItemGroup(items, sort_items=True)
	group.set_selected_by_value(preset)

	result = SelectMenu(
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.minimal('Additional repositories'),
		allow_reset=True,
		allow_skip=True
	).multi()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return []
		case ResultType.Selection:
			if not result.item:
				return preset

			values = [i.value for i in result.item]
			return values
