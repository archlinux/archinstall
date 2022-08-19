from typing import Optional, List

from profiles_v2.profiles_v2 import ProfileType
from profiles_v2.xorg import XorgProfileV2


class I3wmProfileV2(XorgProfileV2):
	def __init__(self):
		super().__init__('i3-wm', ProfileType.WindowMgr, description='')

	@classmethod
	def packages(cls) -> List[str]:
		return super().packages() + [
			'i3lock',
			'i3status',
			'i3blocks',
			'xterm',
			'lightdm-gtk-greeter',
			'lightdm',
			'dmenu',
			'i3-wm'
		]

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()




#
# if __name__ == 'i3':
# 	"""
# 	This "profile" is a meta-profile.
# 	There are no desktop-specific steps, it simply routes
# 	the installer to whichever desktop environment/window manager was chosen.
#
# 	Maybe in the future, a network manager or similar things *could* be added here.
# 	We should honor that Arch Linux does not officially endorse a desktop-setup, nor is
# 	it trying to be a turn-key desktop distribution.
#
# 	There are plenty of desktop-turn-key-solutions based on Arch Linux,
# 	this is therefore just a helper to get started
# 	"""
#
# 	# Install common packages for all i3 configurations
# 	archinstall.storage['installation_session'].add_additional_packages(__packages__[:4])
#
# 	# Install dependency profiles
# 	archinstall.storage['installation_session'].install_profile('xorg')
#
# 	# gaps is installed by default so we are overriding it here with lightdm
# 	archinstall.storage['installation_session'].add_additional_packages(__packages__[4:])
#
# 	# Auto start lightdm for all users
# 	archinstall.storage['installation_session'].enable_service('lightdm')
#
# 	# install the i3 group now
# 	archinstall.storage['installation_session'].add_additional_packages(archinstall.storage['_i3_configuration'])
