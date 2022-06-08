# A desktop environment using "Sway"
import archinstall
from archinstall import Menu

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
		prompt = 'The proprietary Nvidia driver is not supported by Sway. It is likely that you will run into issues, are you okay with that?'
		choice = Menu(prompt, Menu.yes_no(), default_option=Menu.no(), skip=False).run()

		if choice.value == Menu.no():
			return False

	return True


def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""
	driver = archinstall.select_driver()

	if driver:
		archinstall.storage["gfx_driver_packages"] = driver
		if not _check_driver():
			return _prep_function(args, kwargs)
		return True

	return False


# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("sway", "/somewhere/sway.py")
# or through conventional import sway
if __name__ == "sway":
	if not _check_driver():
		raise archinstall.lib.exceptions.HardwareIncompatibilityError("Sway does not support the proprietary nvidia drivers.")

	# Install the Sway packages
	archinstall.storage['installation_session'].add_additional_packages(__packages__)

	# Install the graphics driver packages
	archinstall.storage['installation_session'].add_additional_packages(f"xorg-server xorg-xinit {' '.join(archinstall.storage.get('gfx_driver_packages', None))}")
