from __future__ import annotations

import logging
from typing import List, Any, Optional, Dict, TYPE_CHECKING

from ..menu.text_input import TextInput

from ..locale_helpers import list_keyboard_languages, list_timezones
from ..menu import Menu
from ..output import log
from ..profiles import Profile, list_profiles
from ..mirrors import list_mirrors

from ..translation import Translation
from ..packages.packages import validate_package_list

if TYPE_CHECKING:
	_: Any


def ask_ntp(preset: bool = True) -> bool:
	prompt = str(_('Would you like to use automatic time synchronization (NTP) with the default time servers?\n'))
	prompt += str(_('Hardware time and other post-configuration steps might be required in order for NTP to work.\nFor more information, please check the Arch wiki'))
	if preset:
		preset_val = 'yes'
	else:
		preset_val = 'no'
	choice = Menu(prompt, ['yes', 'no'], skip=False, preset_values=preset_val, default_option='yes').run()
	return False if choice == 'no' else True


def ask_hostname(preset: str = None) -> str:
	hostname = TextInput(_('Desired hostname for the installation: '), preset).run().strip(' ')
	return hostname


def ask_for_a_timezone(preset: str = None) -> str:
	timezones = list_timezones()
	default = 'UTC'

	selected_tz = Menu(_('Select a timezone'),
						list(timezones),
						skip=False,
						preset_values=preset,
						default_option=default).run()

	return selected_tz


def ask_for_audio_selection(desktop: bool = True, preset: str = None) -> str:
	audio = 'pipewire' if desktop else 'none'
	choices = ['pipewire', 'pulseaudio'] if desktop else ['pipewire', 'pulseaudio', 'none']
	selected_audio = Menu(_('Choose an audio server'), choices, preset_values=preset, default_option=audio, skip=False).run()
	return selected_audio


def select_language(default_value: str, preset_value: str = None) -> str:
	"""
	Asks the user to select a language
	Usually this is combined with :ref:`archinstall.list_keyboard_languages`.

	:return: The language/dictionary key of the selected language
	:rtype: str
	"""
	kb_lang = list_keyboard_languages()
	# sort alphabetically and then by length
	# it's fine if the list is big because the Menu
	# allows for searching anyways
	sorted_kb_lang = sorted(sorted(list(kb_lang)), key=len)

	selected_lang = Menu(_('Select Keyboard layout'),
							sorted_kb_lang,
							default_option=default_value,
							preset_values=preset_value,
							sort=False).run()
	return selected_lang


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
	selected_mirror = Menu(_('Select one of the regions to download packages from'),
							list(mirrors.keys()),
							preset_values=preselected,
							multi=True).run()

	if selected_mirror is not None:
		return {selected: mirrors[selected] for selected in selected_mirror}

	return {}


def select_archinstall_language(default='English'):
	languages = Translation.get_all_names()
	language = Menu(_('Select Archinstall language'), languages, default_option=default).run()
	return language


def select_profile() -> Optional[Profile]:
	"""
	# Asks the user to select a profile from the available profiles.
	#
	# :return: The name/dictionary key of the selected profile
	# :rtype: str
	# """
	top_level_profiles = sorted(list(list_profiles(filter_top_level_profiles=True)))
	options = {}

	for profile in top_level_profiles:
		profile = Profile(None, profile)
		description = profile.get_profile_description()

		option = f'{profile.profile}: {description}'
		options[option] = profile

	title = _('This is a list of pre-programmed profiles, they might make it easier to install things like desktop environments')

	selection = Menu(title=title, p_options=list(options.keys())).run()

	if selection is not None:
		return options[selection]

	return None


def ask_additional_packages_to_install(pre_set_packages: List[str] = []) -> List[str]:
	# Additional packages (with some light weight error handling for invalid package names)
	print(_('Only packages such as base, base-devel, linux, linux-firmware, efibootmgr and optional profile packages are installed.'))
	print(_('If you desire a web browser, such as firefox or chromium, you may specify it in the following prompt.'))

	def read_packages(already_defined: list = []) -> list:
		display = ' '.join(already_defined)
		input_packages = TextInput(_('Write additional packages to install (space separated, leave blank to skip): '), display).run()
		return input_packages.split(' ') if input_packages else []

	pre_set_packages = pre_set_packages if pre_set_packages else []
	packages = read_packages(pre_set_packages)

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


def select_additional_repositories(preset: List[str]) -> List[str]:
	"""
	Allows the user to select additional repositories (multilib, and testing) if desired.

	:return: The string as a selected repository
	:rtype: string
	"""

	repositories = ["multilib", "testing"]

	additional_repositories = Menu(_('Choose which optional additional repositories to enable'),
									repositories,
									sort=False,
									multi=True,
									preset_values=preset,
									default_option=[]).run()

	if additional_repositories is not None:
		return additional_repositories

	return []
