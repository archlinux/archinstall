from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from archinstall.tui import Alignment, EditMenu, FrameProperties, MenuItem, MenuItemGroup, Orientation, ResultType, SelectMenu, Tui

from ..locale import list_timezones
from ..models.audio_configuration import Audio, AudioConfiguration
from ..output import warn
from ..packages.packages import validate_package_list
from ..storage import storage
from ..translationhandler import Language

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


def ask_ntp(preset: bool = True) -> bool:
	header = str(_('Would you like to use automatic time synchronization (NTP) with the default time servers?\n')) + '\n'
	header += str(_(
		'Hardware time and other post-configuration steps might be required in order for NTP to work.\n'
		'For more information, please check the Arch wiki'
	)) + '\n'

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
		str(_('Hostname')),
		alignment=Alignment.CENTER,
		allow_skip=True,
		default_text=preset
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

	result = SelectMenu(
		group,
		allow_reset=True,
		allow_skip=True,
		frame=FrameProperties.min(str(_('Timezone'))),
		alignment=Alignment.CENTER,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return default
		case ResultType.Selection:
			return result.get_value()


def ask_for_audio_selection(preset: AudioConfiguration | None = None) -> AudioConfiguration | None:
	items = [MenuItem(a.value, value=a) for a in Audio]
	group = MenuItemGroup(items)

	if preset:
		group.set_focus_by_value(preset.audio)

	result = SelectMenu(
		group,
		allow_skip=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(str(_('Audio')))
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return AudioConfiguration(audio=result.get_value())
		case ResultType.Reset:
			raise ValueError('Unhandled result type')


def select_language(preset: str | None = None) -> str | None:
	from ..locale.locale_menu import select_kb_layout

	# We'll raise an exception in an upcoming version.
	# from ..exceptions import Deprecated
	# raise Deprecated("select_language() has been deprecated, use select_kb_layout() instead.")

	# No need to translate this i feel, as it's a short lived message.
	warn(
		"select_language() is deprecated, use select_kb_layout() instead. select_language() will be removed in a future version")

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

	result = SelectMenu(
		group,
		header=title,
		allow_skip=True,
		allow_reset=False,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(header=str(_('Select language')))
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Reset:
			raise ValueError('Language selection not handled')


def ask_additional_packages_to_install(preset: list[str] = []) -> list[str]:
	# Additional packages (with some light weight error handling for invalid package names)
	header = str(_('Only packages such as base, base-devel, linux, linux-firmware, efibootmgr and optional profile packages are installed.')) + '\n'
	header += str(_('If you desire a web browser, such as firefox or chromium, you may specify it in the following prompt.')) + '\n'
	header += str(_('Write additional packages to install (space separated, leave blank to skip)'))

	def validator(value: str) -> str | None:
		packages = value.split() if value else []

		if len(packages) == 0:
			return None

		if storage['arguments']['offline'] or storage['arguments']['no_pkg_lookups']:
			return None

		# Verify packages that were given
		out = str(_("Verifying that additional packages exist (this might take a few seconds)"))
		Tui.print(out, 0)
		_valid, invalid = validate_package_list(packages)

		if invalid:
			return f'{_("Some packages could not be found in the repository")}: {invalid}'

		return None

	result = EditMenu(
		str(_('Additional packages')),
		alignment=Alignment.CENTER,
		allow_skip=True,
		allow_reset=True,
		edit_width=100,
		validator=validator,
		default_text=' '.join(preset)
	).input()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return []
		case ResultType.Selection:
			packages = result.text()
			return packages.split(' ')


def add_number_of_parallel_downloads(preset: int | None = None) -> int | None:
	max_recommended = 5

	header = str(_('This option enables the number of parallel downloads that can occur during package downloads')) + '\n'
	header += str(_('Enter the number of parallel downloads to be enabled.\n\nNote:\n'))
	header += str(_(' - Maximum recommended value : {} ( Allows {} parallel downloads at a time )')).format(max_recommended, max_recommended) + '\n'
	header += str(_(' - Disable/Default : 0 ( Disables parallel downloading, allows only 1 download at a time )\n'))

	def validator(s: str) -> str | None:
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
		validator=validator,
		default_text=str(preset) if preset is not None else None
	).input()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return 0
		case ResultType.Selection:
			downloads: int = int(result.text())

	pacman_conf_path = Path("/etc/pacman.conf")
	with pacman_conf_path.open() as f:
		pacman_conf = f.read().split("\n")

	with pacman_conf_path.open("w") as fwrite:
		for line in pacman_conf:
			if "ParallelDownloads" in line:
				fwrite.write(f"ParallelDownloads = {downloads}\n")
			else:
				fwrite.write(f"{line}\n")

	return downloads


def select_additional_repositories(preset: list[str]) -> list[str]:
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
		frame=FrameProperties.min('Additional repositories'),
		allow_reset=True,
		allow_skip=True,
		multi=True
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return []
		case ResultType.Selection:
			return result.get_values()


def ask_chroot() -> bool:
	prompt = str(_('Would you like to chroot into the newly created installation and perform post-installation configuration?')) + '\n'
	group = MenuItemGroup.yes_no()

	result = SelectMenu(
		group,
		header=prompt,
		alignment=Alignment.CENTER,
		columns=2,
		orientation=Orientation.HORIZONTAL,
	).run()

	return result.item() == MenuItem.yes()


def ask_abort() -> None:
	prompt = str(_('Do you really want to abort?')) + '\n'
	group = MenuItemGroup.yes_no()

	result = SelectMenu(
		group,
		header=prompt,
		allow_skip=False,
		alignment=Alignment.CENTER,
		columns=2,
		orientation=Orientation.HORIZONTAL
	).run()

	if result.item() == MenuItem.yes():
		exit(0)
