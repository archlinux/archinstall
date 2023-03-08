# A desktop environment using "Sway"
from typing import Any, TYPE_CHECKING

import archinstall
from archinstall import Menu
from archinstall.lib.menu.menu import MenuSelectionType

if TYPE_CHECKING:
	_: Any

is_top_level_profile = False

__packages__ = [
	"sway",
	"swaylock",
	"swayidle",
	"waybar",
	"dmenu",
	"light",
	"grim",
	"slurp",
	"pavucontrol",
	"foot",
]


def _check_driver() -> bool:
	packages = archinstall.storage.get("gfx_driver_packages", [])

	if packages and "nvidia" in packages:
		prompt = _('The proprietary Nvidia driver is not supported by Sway. It is likely that you will run into issues, are you okay with that?')
		choice = Menu(prompt, Menu.yes_no(), default_option=Menu.no(), skip=False).run()

		if choice.value == Menu.no():
			return False

	return True

def _get_system_privelege_control_preference():
	# need to activate seat service and add to seat group
	title = str(_('Sway needs access to your seat (collection of hardware devices i.e. keyboard, mouse, etc)'))
	title += str(_('\n\nChoose an option to give Sway access to your hardware'))
	choice = Menu(title, ["polkit", "seatd"]).run()

	if choice.type_ != MenuSelectionType.Selection:
		return False

	archinstall.storage['sway_sys_priv_ctrl'] = [choice.value]
	archinstall.arguments['sway_sys_priv_ctrl'] = [choice.value]
	return True

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""
	if not _get_system_privelege_control_preference():
		return False

	driver = archinstall.select_driver()

	if driver:
		archinstall.storage["gfx_driver_packages"] = driver
		if not _check_driver():
			return _prep_function(args, kwargs)
		return True

	return False


"""
def _post_install(*args, **kwargs):
	if "seatd" in sway_sys_priv_ctrl:
		print(_('After booting, add user(s) to the `seat` user group and re-login to use Sway'))
	return True
"""

# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("sway", "/somewhere/sway.py")
# or through conventional import sway
if __name__ == "sway":
	if not _check_driver():
		raise archinstall.lib.exceptions.HardwareIncompatibilityError(_('Sway does not support the proprietary nvidia drivers.'))

	# Install the Sway packages
	archinstall.storage['installation_session'].add_additional_packages(__packages__)
	if "seatd" in archinstall.storage['sway_sys_priv_ctrl']:
		archinstall.storage['installation_session'].add_additional_packages(['seatd'])
		archinstall.storage['installation_session'].enable_service('seatd')
	elif "polkit" in archinstall.storage['sway_sys_priv_ctrl']:
		archinstall.storage['installation_session'].add_additional_packages(['polkit'])
	else:
		raise archinstall.lib.exceptions.ProfileError(_('Sway requires either seatd or polkit to run'))

	# Install the graphics driver packages
	archinstall.storage['installation_session'].add_additional_packages(f"xorg-server xorg-xinit {' '.join(archinstall.storage.get('gfx_driver_packages', None))}")
