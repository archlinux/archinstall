from __future__ import annotations

from typing import List, Any, Dict, TYPE_CHECKING

from ..disk import all_blockdevices
from ..exceptions import RequirementError
from ..hardware import AVAILABLE_GFX_DRIVERS, has_uefi, has_amd_graphics, has_intel_graphics, has_nvidia_graphics
from ..menu import Menu
from ..storage import storage

from ..translation import DeferredTranslation

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

	selected_kernels = Menu(_('Choose which kernels to use or leave blank for default "{}"').format(default_kernel),
							kernels,
							sort=True,
							multi=True,
							preset_values=preset,
							default_option=default_kernel).run()
	return selected_kernels


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

	selected_harddrive = Menu(_('Select one or more hard drives to use and configure'),
								list(options.keys()),
								preset_values=list(preset_disks.keys()),
								multi=True).run()

	if selected_harddrive and len(selected_harddrive) > 0:
		return [options[i] for i in selected_harddrive]

	return []


def select_driver(options: Dict[str, Any] = AVAILABLE_GFX_DRIVERS, force_ask: bool = False) -> str:
	"""
	Some what convoluted function, whose job is simple.
	Select a graphics driver from a pre-defined set of popular options.

	(The template xorg is for beginner users, not advanced, and should
	there for appeal to the general public first and edge cases later)
	"""

	drivers = sorted(list(options))

	if drivers:
		arguments = storage.get('arguments', {})
		title = DeferredTranslation('')

		if has_amd_graphics():
			title += _(
				'For the best compatibility with your AMD hardware, you may want to use either the all open-source or AMD / ATI options.'
			) + '\n'
		if has_intel_graphics():
			title += _(
				'For the best compatibility with your Intel hardware, you may want to use either the all open-source or Intel options.\n'
			)
		if has_nvidia_graphics():
			title += _(
				'For the best compatibility with your Nvidia hardware, you may want to use the Nvidia proprietary driver.\n'
			)

		if not arguments.get('gfx_driver', None) or force_ask:
			title += _('\n\nSelect a graphics driver or leave blank to install all open-source drivers')
			arguments['gfx_driver'] = Menu(title, drivers).run()

		if arguments.get('gfx_driver', None) is None:
			arguments['gfx_driver'] = _("All open-source (default)")

		return options.get(arguments.get('gfx_driver'))

	raise RequirementError("Selecting drivers require a least one profile to be given as an option.")


def ask_for_bootloader(advanced_options: bool = False, preset: str = None) -> str:

	if preset == 'systemd-bootctl':
		preset_val = 'systemd-boot' if advanced_options else 'no'
	elif preset == 'grub-install':
		preset_val = 'grub' if advanced_options else 'yes'
	else:
		preset_val = preset

	bootloader = "systemd-bootctl" if has_uefi() else "grub-install"
	if has_uefi():
		if not advanced_options:
			bootloader_choice = Menu(_('Would you like to use GRUB as a bootloader instead of systemd-boot?'),
										['yes', 'no'],
										preset_values=preset_val,
										default_option='no').run()

			if bootloader_choice == "yes":
				bootloader = "grub-install"
		else:
			# We use the common names for the bootloader as the selection, and map it back to the expected values.
			choices = ['systemd-boot', 'grub', 'efistub']
			selection = Menu(_('Choose a bootloader'), choices, preset_values=preset_val).run()
			if selection != "":
				if selection == 'systemd-boot':
					bootloader = 'systemd-bootctl'
				elif selection == 'grub':
					bootloader = 'grub-install'
				else:
					bootloader = selection

	return bootloader


def ask_for_swap(preset: bool = True) -> bool:
	if preset:
		preset_val = 'yes'
	else:
		preset_val = 'no'
	prompt = _('Would you like to use swap on zram?')
	choice = Menu(prompt, ['yes', 'no'], default_option='yes', preset_values=preset_val).run()
	return False if choice == 'no' else True
