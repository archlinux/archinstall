from __future__ import annotations

import logging
import pathlib
from typing import List, Any, Optional, Dict, TYPE_CHECKING, Union

from .system_conf import select_driver

from archinstall.profiles_v2.profiles_v2 import ProfileV2
from ..locale_helpers import list_keyboard_languages, list_timezones
from ..menu import Menu
from ..menu.menu import MenuSelectionType
from ..menu.text_input import TextInput
from ..mirrors import list_mirrors
from ..output import log, FormattedOutput
from ..packages.packages import validate_package_list
from ..profiles_handler import ProfileHandler
from ..storage import storage
from ..translationhandler import Language

if TYPE_CHECKING:
	_: Any


def ask_ntp(preset: bool = True) -> bool:
	prompt = str(_('Would you like to use automatic time synchronization (NTP) with the default time servers?\n'))
	prompt += str(_('Hardware time and other post-configuration steps might be required in order for NTP to work.\nFor more information, please check the Arch wiki'))
	if preset:
		preset_val = Menu.yes()
	else:
		preset_val = Menu.no()
	choice = Menu(prompt, Menu.yes_no(), skip=False, preset_values=preset_val, default_option=Menu.yes()).run()

	return False if choice.value == Menu.no() else True


def ask_hostname(preset: str = None) -> str:
	hostname = TextInput(_('Desired hostname for the installation: '), preset).run().strip(' ')
	return hostname


def ask_for_a_timezone(preset: str = None) -> str:
	timezones = list_timezones()
	default = 'UTC'

	choice = Menu(
		_('Select a timezone'),
		list(timezones),
		preset_values=preset,
		default_option=default
	).run()

	match choice.type_:
		case MenuSelectionType.Esc: return preset
		case MenuSelectionType.Selection: return choice.value


def ask_for_audio_selection(desktop: bool = True, preset: Union[str, None] = None) -> Union[str, None]:
	no_audio = str(_('No audio server'))
	choices = ['pipewire', 'pulseaudio'] if desktop else ['pipewire', 'pulseaudio', no_audio]
	default = 'pipewire' if desktop else no_audio

	choice = Menu(_('Choose an audio server'), choices, preset_values=preset, default_option=default).run()

	match choice.type_:
		case MenuSelectionType.Esc: return preset
		case MenuSelectionType.Selection: return choice.value


def select_language(preset_value: str = None) -> str:
	"""
	Asks the user to select a language
	Usually this is combined with :ref:`archinstall.list_keyboard_languages`.

	:return: The language/dictionary key of the selected language
	:rtype: str
	"""
	kb_lang = list_keyboard_languages()
	# sort alphabetically and then by length
	sorted_kb_lang = sorted(sorted(list(kb_lang)), key=len)

	selected_lang = Menu(
		_('Select keyboard layout'),
		sorted_kb_lang,
		preset_values=preset_value,
		sort=False
	).run()

	if selected_lang.value is None:
		return preset_value

	return selected_lang.value


def select_mirror_regions(preset_values: Dict[str, Any] = {}) -> Dict[str, Any]:
	"""
	Asks the user to select a mirror or region
	Usually this is combined with :ref:`archinstall.list_mirrors`.

	:return: The dictionary information about a mirror/region.
	:rtype: dict
	"""
	if preset_values is None:
		preselected = None
	else:
		preselected = list(preset_values.keys())
	mirrors = list_mirrors()
	selected_mirror = Menu(
		_('Select one of the regions to download packages from'),
		list(mirrors.keys()),
		preset_values=preselected,
		multi=True,
		raise_error_on_interrupt=True
	).run()

	match selected_mirror.type_:
		case MenuSelectionType.Ctrl_c: return {}
		case MenuSelectionType.Esc: return preset_values
		case _: return {selected: mirrors[selected] for selected in selected_mirror.value}


def select_archinstall_language(languages: List[Language], preset_value: Language) -> Language:
	# these are the displayed language names which can either be
	# the english name of a language or, if present, the
	# name of the language in its own language
	options = {lang.display_name: lang for lang in languages}

	choice = Menu(
		_('Archinstall language'),
		list(options.keys()),
		default_option=preset_value.display_name
	).run()

	match choice.type_:
		case MenuSelectionType.Esc: return preset_value
		case MenuSelectionType.Selection:
			return options[choice.value]


def select_profile_v2(
	current_profile: Optional[ProfileV2] = None,
	title: str = None,
	allow_reset: bool = True,
	multi: bool = False
) -> Optional[ProfileV2]:
	handler = ProfileHandler()
	top_level_profiles = handler.get_top_level_profiles()

	display_title = title
	if not display_title:
		display_title = str(_('This is a list of pre-programmed profiles_bck, they might make it easier to install things like desktop environments'))

	if current_profile is not None:
		if profile_info := current_profile.info():
			output = FormattedOutput.as_table([profile_info])
			display_title += '\n\n' + str(_('Current profile selection'))
			display_title += '\n\n' + output

	choice = handler.select_profile(
		top_level_profiles,
		current_profile=current_profile,
		title=display_title,
		allow_reset=allow_reset,
		multi=multi,
		with_back_option=True
	)

	match choice.type_:
		case MenuSelectionType.Selection:
			profile_selection: ProfileV2 = choice.value
			select_result = profile_selection.do_on_select()

			if not select_result:
				return select_profile_v2(
					current_profile=current_profile,
					title=title,
					allow_reset=allow_reset,
					multi=multi
				)

			# we're going to reset the currently selected profile(s) to avoid
			# any stale data laying around
			match select_result:
				case select_result.NewSelection:
					if profile_selection.is_graphic_driver_enabled():
						profile_selection.gfx_driver = select_driver(current_value=profile_selection.gfx_driver)

					handler.reset_top_level_profiles(exclude=[profile_selection])
					current_profile = profile_selection
				case select_result.ResetCurrent:
					handler.reset_top_level_profiles()
					current_profile = None
				case select_result.SameSelection:
					pass

			# we're keep showing the profile menu unless we're actively exiting it
			# by pressing ctrl+c or Esc
			return select_profile_v2(
				current_profile=current_profile,
				title=title,
				allow_reset=allow_reset,
				multi=multi
			)
		case MenuSelectionType.Ctrl_c:
			return None
		case MenuSelectionType.Esc:
			return current_profile


def ask_additional_packages_to_install(pre_set_packages: List[str] = []) -> List[str]:
	# Additional packages (with some light weight error handling for invalid package names)
	print(_('Only packages such as base, base-devel, linux, linux-firmware, efibootmgr and optional profile packages are installed.'))
	print(_('If you desire a web browser, such as firefox or chromium, you may specify it in the following prompt.'))

	def read_packages(already_defined: list = []) -> list:
		display = ' '.join(already_defined)
		input_packages = TextInput(_('Write additional packages to install (space separated, leave blank to skip): '), display).run().strip()
		return input_packages.split() if input_packages else []

	pre_set_packages = pre_set_packages if pre_set_packages else []
	packages = read_packages(pre_set_packages)

	if not storage['arguments']['offline'] and not storage['arguments']['no_pkg_lookups']:
		while True:
			if len(packages):
				# Verify packages that were given
				print(_("Verifying that additional packages exist (this might take a few seconds)"))
				valid, invalid = validate_package_list(packages)

				if invalid:
					log(f"Some packages could not be found in the repository: {invalid}", level=logging.WARNING, fg='red')
					packages = read_packages(valid)
					continue
			break

	return packages


def add_number_of_parrallel_downloads(input_number :Optional[int] = None) -> Optional[int]:
	max_downloads = 5
	print(_(f"This option enables the number of parallel downloads that can occur during installation"))
	print(_(f"Enter the number of parallel downloads to be enabled.\n (Enter a value between 1 to {max_downloads})\nNote:"))
	print(_(f" - Maximum value   : {max_downloads} ( Allows {max_downloads} parallel downloads, allows {max_downloads+1} downloads at a time )"))
	print(_(f" - Minimum value   : 1 ( Allows 1 parallel download, allows 2 downloads at a time )"))
	print(_(f" - Disable/Default : 0 ( Disables parallel downloading, allows only 1 download at a time )"))

	while True:
		try:
			input_number = int(TextInput("[Default value: 0] > ").run().strip() or 0)
			if input_number <= 0:
				input_number = 0
			elif input_number > max_downloads:
				input_number = max_downloads
			break
		except:
			print(_(f"Invalid input! Try again with a valid input [1 to {max_downloads}, or 0 to disable]"))

	pacman_conf_path = pathlib.Path("/etc/pacman.conf")
	with pacman_conf_path.open() as f:
		pacman_conf = f.read().split("\n")

	with pacman_conf_path.open("w") as fwrite:
		for line in pacman_conf:
			if "ParallelDownloads" in line:
				fwrite.write(f"ParallelDownloads = {input_number+1}\n") if not input_number == 0 else fwrite.write("#ParallelDownloads = 0\n")
			else:
				fwrite.write(f"{line}\n")

	return input_number


def select_additional_repositories(preset: List[str]) -> List[str]:
	"""
	Allows the user to select additional repositories (multilib, and testing) if desired.

	:return: The string as a selected repository
	:rtype: string
	"""

	repositories = ["multilib", "testing"]

	choice = Menu(
		_('Choose which optional additional repositories to enable'),
		repositories,
		sort=False,
		multi=True,
		preset_values=preset,
		raise_error_on_interrupt=True
	).run()

	match choice.type_:
		case MenuSelectionType.Esc: return preset
		case MenuSelectionType.Ctrl_c: return []
		case MenuSelectionType.Selection: return choice.value
