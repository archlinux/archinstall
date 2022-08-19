from typing import List, Optional

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class AwesomeProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Awesome', ProfileType.WindowMgr, description='')

	@classmethod
	def packages(cls) -> List[str]:
		xorg_packages = super().packages()
		return xorg_packages + [
			'alacritty',
		]

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()

	def install(self, install_session: 'Installer'):
		super().install(install_session)
		install_session.add_additional_packages(self.packages())

		# TODO: Copy a full configuration to ~/.config/awesome/rc.lua instead.
		with open(f"{install_session.target}/etc/xdg/awesome/rc.lua", 'r') as fh:
			awesome_lua = fh.read()

		# Replace xterm with alacritty for a smoother experience.
		awesome_lua = awesome_lua.replace('"xterm"', '"alacritty"')

		with open(f"{install_session.target}/etc/xdg/awesome/rc.lua", 'w') as fh:
			fh.write(awesome_lua)

		# TODO: Configure the right-click-menu to contain the above packages that were installed. (as a user config)
