from typing import List, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class AwesomeProfile(XorgProfile):
	def __init__(self):
		super().__init__('Awesome', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> List[str]:
		return super().packages + [
			'awesome',
			'alacritty',
			'xorg-xinit',
			'xorg-xrandr',
			'xterm',
			'feh',
			'slock',
			'terminus-font',
			'gnu-free-fonts',
			'ttf-liberation',
			'xsel',
		]

	def install(self, install_session: 'Installer'):
		super().install(install_session)

		# TODO: Copy a full configuration to ~/.config/awesome/rc.lua instead.
		with open(f"{install_session.target}/etc/xdg/awesome/rc.lua", 'r') as fh:
			awesome_lua = fh.read()

		# Replace xterm with alacritty for a smoother experience.
		awesome_lua = awesome_lua.replace('"xterm"', '"alacritty"')

		with open(f"{install_session.target}/etc/xdg/awesome/rc.lua", 'w') as fh:
			fh.write(awesome_lua)

		# TODO: Configure the right-click-menu to contain the above packages that were installed. (as a user config)

		# TODO: check if we selected a greeter,
		# but for now, awesome is intended to run without one.
		with open(f"{install_session.target}/etc/X11/xinit/xinitrc", 'r') as xinitrc:
			xinitrc_data = xinitrc.read()

		for line in xinitrc_data.split('\n'):
			if "twm &" in line:
				xinitrc_data = xinitrc_data.replace(line, f"# {line}")
			if "xclock" in line:
				xinitrc_data = xinitrc_data.replace(line, f"# {line}")
			if "xterm" in line:
				xinitrc_data = xinitrc_data.replace(line, f"# {line}")

		xinitrc_data += '\n'
		xinitrc_data += 'exec awesome\n'

		with open(f"{install_session.target}/etc/X11/xinit/xinitrc", 'w') as xinitrc:
			xinitrc.write(xinitrc_data)