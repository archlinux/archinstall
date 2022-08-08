from typing import List

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class AwesomeProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('Awesome', ProfileType.WindowMgr, description='')

	def packages(self) -> List[str]:
		xorg_packages = super().packages()
		return xorg_packages + [
			'alacritty',
		]

	def do_on_select(self):
		super().do_on_select()



#
# # Ensures that this code only gets executed if executed
# # through importlib.util.spec_from_file_location("awesome", "/somewhere/awesome.py")
# # or through conventional import awesome
# if __name__ == 'awesome':
# 	# Install the application awesome from the template under /applications/
# 	awesome = archinstall.Application(archinstall.storage['installation_session'], 'awesome')
# 	awesome.install()
#
# 	archinstall.storage['installation_session'].add_additional_packages(__packages__)
#
# 	# TODO: Copy a full configuration to ~/.config/awesome/rc.lua instead.
# 	with open(f"{archinstall.storage['installation_session'].target}/etc/xdg/awesome/rc.lua", 'r') as fh:
# 		awesome_lua = fh.read()
#
# 	# Replace xterm with alacritty for a smoother experience.
# 	awesome_lua = awesome_lua.replace('"xterm"', '"alacritty"')
#
# 	with open(f"{archinstall.storage['installation_session'].target}/etc/xdg/awesome/rc.lua", 'w') as fh:
# 		fh.write(awesome_lua)
#
# 	# TODO: Configure the right-click-menu to contain the above packages that were installed. (as a user config)
