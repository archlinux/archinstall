from __future__ import annotations

import pathlib
from typing import List, Any, Optional, TYPE_CHECKING

from ..locale import list_timezones
from ..menu import MenuSelectionType, Menu, TextInput
from ..models.audio_configuration import Audio, AudioConfiguration
from ..output import warn
from ..packages.packages import validate_package_list
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


def ask_hostname(preset: str = '') -> str:
	hostname = TextInput(
		str(_('Desired hostname for the installation: ')),
		preset
	).run().strip()

	if not hostname:
		return preset

	return hostname


def ask_for_a_timezone(preset: Optional[str] = None) -> Optional[str]:
	timezones = list_timezones()
	default = 'UTC'

	choice = Menu(
		_('Select a timezone'),
		timezones,
		preset_values=preset,
		default_option=default
	).run()

	match choice.type_:
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Selection: return choice.single_value

	return None


def ask_for_audio_selection(
	current: Optional[AudioConfiguration] = None
) -> Optional[AudioConfiguration]:
	choices = [
		Audio.Pipewire.name,
		Audio.Pulseaudio.name,
		Audio.no_audio_text()
	]

	preset = current.audio.name if current else None

	choice = Menu(
		_('Choose an audio server'),
		choices,
		preset_values=preset
	).run()

	match choice.type_:
		case MenuSelectionType.Skip: return current
		case MenuSelectionType.Selection:
			value = choice.single_value
			if value == Audio.no_audio_text():
				return None
			else:
				return AudioConfiguration(Audio[value])

	return None


def select_language(preset: Optional[str] = None) -> Optional[str]:
	from ..locale.locale_menu import select_kb_layout

	# We'll raise an exception in an upcoming version.
	# from ..exceptions import Deprecated
	# raise Deprecated("select_language() has been deprecated, use select_kb_layout() instead.")

	# No need to translate this i feel, as it's a short lived message.
	warn("select_language() is deprecated, use select_kb_layout() instead. select_language() will be removed in a future version")

	return select_kb_layout(preset)


def select_archinstall_language(languages: List[Language], preset: Language) -> Language:
	# these are the displayed language names which can either be
	# the english name of a language or, if present, the
	# name of the language in its own language
	options = {lang.display_name: lang for lang in languages}

	title = 'NOTE: If a language can not displayed properly, a proper font must be set manually in the console.\n'
	title += 'All available fonts can be found in "/usr/share/kbd/consolefonts"\n'
	title += 'e.g. setfont LatGrkCyr-8x16 (to display latin/greek/cyrillic characters)\n'

	choice = Menu(
		title,
		list(options.keys()),
		default_option=preset.display_name,
		preview_size=0.5
	).run()

	match choice.type_:
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Selection: return options[choice.single_value]

	raise ValueError('Language selection not handled')


def ask_additional_packages_to_install(preset: List[str] = []) -> List[str]:
	# Additional packages (with some light weight error handling for invalid package names)
	print(_('Only packages such as base, base-devel, linux, linux-firmware, efibootmgr and optional profile packages are installed.'))
	print(_('If you desire a web browser, such as firefox or chromium, you may specify it in the following prompt.'))

	def read_packages(p: List = []) -> list:
		display = ' '.join(p)
		input_packages = TextInput(_('Write additional packages to install (space separated, leave blank to skip): '), display).run().strip()
		return input_packages.split() if input_packages else []

	preset = preset if preset else []
	packages = read_packages(preset)

	if not storage['arguments']['offline'] and not storage['arguments']['no_pkg_lookups']:
		while True:
			if len(packages):
				# Verify packages that were given
				print(_("Verifying that additional packages exist (this might take a few seconds)"))
				valid, invalid = validate_package_list(packages)

				if invalid:
					warn(f"Some packages could not be found in the repository: {invalid}")
					packages = read_packages(valid)
					continue
			break

	return packages


def add_number_of_parallel_downloads(input_number :Optional[int] = None) -> Optional[int]:
	max_recommended = 5
	print(_(f"This option enables the number of parallel downloads that can occur during package downloads"))
	print(_("Enter the number of parallel downloads to be enabled.\n\nNote:\n"))
	print(str(_(" - Maximum recommended value : {} ( Allows {} parallel downloads at a time )")).format(max_recommended, max_recommended))
	print(_(" - Disable/Default : 0 ( Disables parallel downloading, allows only 1 download at a time )\n"))

	while True:
		try:
			input_number = int(TextInput(_("[Default value: 0] > ")).run().strip() or 0)
			if input_number <= 0:
				input_number = 0
			break
		except:
			print(str(_("Invalid input! Try again with a valid input [or 0 to disable]")).format(max_recommended))

	pacman_conf_path = pathlib.Path("/etc/pacman.conf")
	with pacman_conf_path.open() as f:
		pacman_conf = f.read().split("\n")

	with pacman_conf_path.open("w") as fwrite:
		for line in pacman_conf:
			if "ParallelDownloads" in line:
				fwrite.write(f"ParallelDownloads = {input_number}\n") if not input_number == 0 else fwrite.write("#ParallelDownloads = 0\n")
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
		allow_reset=True
	).run()

	match choice.type_:
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Reset: return []
		case MenuSelectionType.Selection: return choice.single_value

	return []