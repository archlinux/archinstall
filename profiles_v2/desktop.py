# A desktop environment selector.
from typing import Any, TYPE_CHECKING, List, Optional

from archinstall.lib.menu.menu import MenuSelectionType, MenuSelection
from archinstall.lib.profiles_handler import ProfileHandler
from profiles_v2.profiles_v2 import Profile_v2, ProfileType

if TYPE_CHECKING:
	_: Any


class DesktopProfileV2(Profile_v2):
	def __init__(self, current_selection: Optional[Profile_v2] = None):
		super().__init__(
			'Desktop',
			ProfileType.Generic,
			description=str(_('Provides a selection of desktop environments and tiling window managers, e.g. gnome, kde, sway'))
		)

		self._desktop_profile = current_selection

	def preview_text(self) -> Optional[str]:
		if self._desktop_profile:
			return self._desktop_profile.identifier
		return None

	def packages(self) -> List[str]:
		return [
			'nano',
			'vim',
			'openssh',
			'htop',
			'wget',
			'iwd',
			'wireless_tools',
			'wpa_supplicant',
			'smartmontools',
			'xdg-utils'
		]

	def do_on_select(self):
		handler = ProfileHandler()
		choice = handler.select_profile(
			handler.get_desktop_profiles(),
			self.current_selection,
			title=str(_('Select your desired desktop environment'))
		)

		if choice.type_ == MenuSelectionType.Selection:
			self._desktop_profile = choice.value



# def _prep_function(*args, **kwargs) -> bool:
# 	"""
# 	Magic function called by the importing installer
# 	before continuing any further. It also avoids executing any
# 	other code in this stage. So it's a safe way to ask the user
# 	for more input before any other installer steps start.
# 	"""
# 	choice = Menu(str(_('Select your desired desktop environment')), __supported__).run()
#
# 	if choice.type_ != MenuSelectionType.Selection:
# 		return False
#
# 	if choice.value:
# 		# Temporarily store the selected desktop profile
# 		# in a session-safe location, since this module will get reloaded
# 		# the next time it gets executed.
# 		if not archinstall.storage.get('_desktop_profile', None):
# 			archinstall.storage['_desktop_profile'] = choice.value
# 		if not archinstall.arguments.get('desktop-environment', None):
# 			archinstall.arguments['desktop-environment'] = choice.value
# 		profile = archinstall.Profile(None, choice.value)
# 		# Loading the instructions with a custom namespace, ensures that a __name__ comparison is never triggered.
# 		with profile.load_instructions(namespace=f"{choice.value}.py") as imported:
# 			if hasattr(imported, '_prep_function'):
# 				return imported._prep_function()
# 			else:
# 				log(f"Deprecated (??): {choice.value} profile has no _prep_function() anymore")
# 				exit(1)
#
# 	return False
#
#
# if __name__ == 'desktop':
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
# 	# Install common packages for all desktop environments
# 	archinstall.storage['installation_session'].add_additional_packages(__packages__)
#
# 	archinstall.storage['installation_session'].install_profile(archinstall.storage['_desktop_profile'])
