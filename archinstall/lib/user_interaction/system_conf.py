from __future__ import annotations

from typing import List, Any, Dict, TYPE_CHECKING, Optional

from ..disk import all_blockdevices
from ..hardware import AVAILABLE_GFX_DRIVERS, has_uefi, has_amd_graphics, has_intel_graphics, has_nvidia_graphics
from ..menu import Menu
from ..menu.menu import MenuSelectionType
from ..models.bootloader import Bootloader
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
		allow_reset=True,
		allow_reset_warning_msg=warning
	).run()

	match choice.type_:
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Reset: return []
		case MenuSelectionType.Selection: return choice.value


def select_harddrives(preset: List[str] = []) -> List[str]:
	"""
	Asks the user to select one or multiple hard drives

	:return: List of selected hard drives
	:rtype: list
	"""
	hard_drives = all_blockdevices(partitions=False).values()
	options = {f'{option}': option for option in hard_drives}

	title = str(_('Select one or more hard drives to use and configure\n'))
	title += str(_('Any modifications to the existing setting will reset the disk layout!'))

	warning = str(_('If you reset the harddrive selection this will also reset the current disk layout. Are you sure?'))

	selected_harddrive = Menu(
		title,
		list(options.keys()),
		preset_values=preset,
		multi=True,
		allow_reset=True,
		allow_reset_warning_msg=warning
	).run()

	match selected_harddrive.type_:
		case MenuSelectionType.Reset: return []
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Selection: return [options[i] for i in selected_harddrive.value]


def ask_for_bootloader(preset: Bootloader) -> Bootloader:
	# when the system only supports grub
	if not has_uefi():
		options = [Bootloader.Grub.value]
		default = Bootloader.Grub.value
	else:
		options = Bootloader.values()
		default = Bootloader.Systemd.value

	preset_value = preset.value if preset else None

	choice = Menu(
		_('Choose a bootloader'),
		options,
		preset_values=preset_value,
		sort=False,
		default_option=default
	).run()

	match choice.type_:
		case MenuSelectionType.Esc: return preset
		case MenuSelectionType.Selection: return Bootloader(choice.value)


def select_driver(options: Dict[str, Any] = None, current_value: str = None) -> Optional[str]:
	"""
	Some what convoluted function, whose job is simple.
	Select a graphics driver from a pre-defined set of popular options.

	(The template xorg is for beginner users, not advanced, and should
	there for appeal to the general public first and edge cases later)
	"""

	if options is None or len(options) == 0:
		options = AVAILABLE_GFX_DRIVERS

	drivers = sorted(list(options.keys()))

	if drivers:
		title = ''
		if has_amd_graphics():
			title += str(_('For the best compatibility with your AMD hardware, you may want to use either the all open-source or AMD / ATI options.')) + '\n'
		if has_intel_graphics():
			title += str(_('For the best compatibility with your Intel hardware, you may want to use either the all open-source or Intel options.\n'))
		if has_nvidia_graphics():
			title += str(_('For the best compatibility with your Nvidia hardware, you may want to use the Nvidia proprietary driver.\n'))

		title += str(_('\n\nSelect a graphics driver or leave blank to install all open-source drivers'))

		preset = current_value if current_value else None
		choice = Menu(title, drivers, preset_values=preset).run()

		if choice.type_ != MenuSelectionType.Selection:
			return None

		return choice.value

	return current_value


def ask_for_swap(preset: bool = True) -> bool:
	if preset:
		preset_val = Menu.yes()
	else:
		preset_val = Menu.no()

	prompt = _('Would you like to use swap on zram?')
	choice = Menu(prompt, Menu.yes_no(), default_option=Menu.yes(), preset_values=preset_val).run()

	match choice.type_:
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Selection: return False if choice.value == Menu.no() else True
