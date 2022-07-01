from __future__ import annotations

from typing import List, Any, Dict, TYPE_CHECKING

from ..disk import all_blockdevices
from ..exceptions import RequirementError
from ..hardware import AVAILABLE_GFX_DRIVERS, has_uefi, has_amd_graphics, has_intel_graphics, has_nvidia_graphics
from ..menu import Menu
from ..menu.menu import MenuSelectionType
from ..storage import storage

if TYPE_CHECKING:
	_: Any


def select_kernel(preset: List[str] = None) -> List[str]:
	"""
	Asks the user to select a kernel for system.

	:return: The string as a selected kernel
	:rtype: string
	"""

	kernels = ["linux", "linux-lts", "linux-zen", "linux-hardened"]
	default_kernel = "linux"

	warning = str(_('Are you sure you want to reset this setting?'))

	choice = Menu(
		_('Choose which kernels to use or leave blank for default "{}"').format(default_kernel),
		kernels,
		sort=True,
		multi=True,
		preset_values=preset,
		raise_error_on_interrupt=True,
		raise_error_warning_msg=warning
	).run()

	match choice.type_:
		case MenuSelectionType.Esc: return preset
		case MenuSelectionType.Ctrl_c: return []
		case MenuSelectionType.Selection: return choice.value


def select_harddrives(preset: List[str] = []) -> List[str]:
	"""
	Asks the user to select one or multiple hard drives

	:return: List of selected hard drives
	:rtype: list
	"""
	hard_drives = all_blockdevices(partitions=False).values()
	options = {f'{option}': option for option in hard_drives}

	if preset:
		preset_disks = {f'{option}': option for option in preset}
	else:
		preset_disks = {}

	title = str(_('Select one or more hard drives to use and configure\n'))
	title += str(_('Any modifications to the existing setting will reset the disk layout!'))

	warning = str(_('If you reset the harddrive selection this will also reset the current disk layout. Are you sure?'))

	selected_harddrive = Menu(
		title,
		list(options.keys()),
		preset_values=list(preset_disks.keys()),
		multi=True,
		raise_error_on_interrupt=True,
		raise_error_warning_msg=warning
	).run()

	match selected_harddrive.type_:
		case MenuSelectionType.Ctrl_c: return []
		case MenuSelectionType.Esc: return preset
		case MenuSelectionType.Selection: return [options[i] for i in selected_harddrive.value]


def select_driver(options: Dict[str, Any] = AVAILABLE_GFX_DRIVERS) -> str:
	"""
	Some what convoluted function, whose job is simple.
	Select a graphics driver from a pre-defined set of popular options.

	(The template xorg is for beginner users, not advanced, and should
	there for appeal to the general public first and edge cases later)
	"""

	drivers = sorted(list(options))

	if drivers:
		arguments = storage.get('arguments', {})
		title = ''

		if has_amd_graphics():
			title += str(_(
				'For the best compatibility with your AMD hardware, you may want to use either the all open-source or AMD / ATI options.'
			)) + '\n'
		if has_intel_graphics():
			title += str(_(
				'For the best compatibility with your Intel hardware, you may want to use either the all open-source or Intel options.\n'
			))
		if has_nvidia_graphics():
			title += str(_(
				'For the best compatibility with your Nvidia hardware, you may want to use the Nvidia proprietary driver.\n'
			))

		title += str(_('\n\nSelect a graphics driver or leave blank to install all open-source drivers'))
		choice = Menu(title, drivers).run()

		if choice.type_ != MenuSelectionType.Selection:
			return arguments.get('gfx_driver')

		arguments['gfx_driver'] = choice.value
		return options.get(choice.value)

	raise RequirementError("Selecting drivers require a least one profile to be given as an option.")


def ask_for_bootloader(advanced_options: bool = False, preset: str = None) -> str:
	if preset == 'systemd-bootctl':
		preset_val = 'systemd-boot' if advanced_options else Menu.no()
	elif preset == 'grub-install':
		preset_val = 'grub' if advanced_options else Menu.yes()
	else:
		preset_val = preset

	bootloader = "systemd-bootctl" if has_uefi() else "grub-install"

	if has_uefi():
		if not advanced_options:
			selection = Menu(
				_('Would you like to use GRUB as a bootloader instead of systemd-boot?'),
				Menu.yes_no(),
				preset_values=preset_val,
				default_option=Menu.no()
			).run()

			match selection.type_:
				case MenuSelectionType.Esc: return preset
				case MenuSelectionType.Selection: bootloader = 'grub-install' if selection.value == Menu.yes() else bootloader
		else:
			# We use the common names for the bootloader as the selection, and map it back to the expected values.
			choices = ['systemd-boot', 'grub', 'efistub']
			selection = Menu(_('Choose a bootloader'), choices, preset_values=preset_val).run()

			value = ''
			match selection.type_:
				case MenuSelectionType.Esc: value = preset_val
				case MenuSelectionType.Selection: value = selection.value

			if value != "":
				if value == 'systemd-boot':
					bootloader = 'systemd-bootctl'
				elif value == 'grub':
					bootloader = 'grub-install'
				else:
					bootloader = value

	return bootloader


def ask_for_swap(preset: bool = True) -> bool:
	if preset:
		preset_val = Menu.yes()
	else:
		preset_val = Menu.no()

	prompt = _('Would you like to use swap on zram?')
	choice = Menu(prompt, Menu.yes_no(), default_option=Menu.yes(), preset_values=preset_val).run()

	match choice.type_:
		case MenuSelectionType.Esc: return preset
		case MenuSelectionType.Selection: return False if choice.value == Menu.no() else True
