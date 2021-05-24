# A desktop environment using "Sway"

import archinstall

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
	"alacritty",
]


def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""
	archinstall.storage["gfx_driver_packages"] = archinstall.select_driver()

	return True


# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("sway", "/somewhere/sway.py")
# or through conventional import sway
if __name__ == "sway":
	if "nvidia" in archinstall.storage.get("gfx_driver_packages", None):
		choice = input("The proprietary Nvidia driver is not supported by Sway. It is likely that you will run into issues. Continue anyways? [y/N] ")
		if choice.lower() in ("n", ""):
			raise archinstall.lib.exceptions.HardwareIncompatibilityError("Sway does not support the proprietary nvidia drivers.")

	# Install the Sway packages
	archinstall.storage['installation_session'].add_additional_packages(__packages__)

	# Install the graphics driver packages
	archinstall.storage['installation_session'].add_additional_packages(f"xorg-server xorg-xinit {' '.join(archinstall.storage.get('gfx_driver_packages', None))}")
