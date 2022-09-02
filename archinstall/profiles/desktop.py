from typing import Any, TYPE_CHECKING, List, Optional

from archinstall.lib.menu.menu import MenuSelectionType, Menu
from archinstall.lib.output import log
from archinstall.lib.profiles_handler import ProfileHandler
from archinstall.profiles.profiles import Profile, ProfileType, SelectResult, GreeterType

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class DesktopProfile(Profile):
	def __init__(self, current_selection: List[Profile] = []):
		super().__init__(
			'Desktop',
			ProfileType.Desktop,
			description=str(_('Provides a selection of desktop environments and tiling window managers, e.g. gnome, kde, sway')),
			current_selection=current_selection
		)

		self._greeter_type: Optional[GreeterType] = None

	@property
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

	def _select_greeter(self):
		if not self.current_selection:
			return

		combined_greeters = set()
		for profile in self.current_selection:
			if profile.greeter_type:
				combined_greeters.add(profile.greeter_type)

		if len(combined_greeters) >= 1:
			profile_names = ', '.join([profile.name for profile in self.current_selection])
			title = str(_('Please chose which greeter to install for the chosen profiles: {}')).format(profile_names)

			greeter_options = [greeter.value for greeter in GreeterType]

			default_option = None
			if len(combined_greeters) == 1:
				default_option = list(combined_greeters)[0].value

			choice = Menu(title, greeter_options, skip=False, default_option=default_option).run()
			self._greeter_type = choice.value

	def do_on_select(self) -> SelectResult:
		handler = ProfileHandler()
		choice = handler.select_profile(
			handler.get_desktop_profiles(),
			self._current_selection,
			title=str(_('Select your desired desktop environment')),
			multi=True
		)

		match choice.type_:
			case MenuSelectionType.Selection:
				self.set_current_selection(choice.value)  # type: ignore
				self._select_greeter()
				return SelectResult.NewSelection
			case MenuSelectionType.Esc:
				return SelectResult.SameSelection
			case MenuSelectionType.Ctrl_c:
				return SelectResult.ResetCurrent

	def post_install(self, install_session: 'Installer'):
		for profile in self._current_selection:
			profile.post_install(install_session)

	def _install_greeter(self, install_session: 'Installer'):
		if self._greeter_type is None:
			return

		packages = []
		service = None

		match self._greeter_type:
			case GreeterType.Lightdm:
				packages = ['lightdm', 'lightdm-gtk-greeter']
				service = ['lightdm']
			case GreeterType.Sddm:
				packages = ['sddm']
				service = ['sddm']
			case GreeterType.Gdm:
				packages = ['gdm']
				service = ['gdm']

		if packages:
			install_session.add_additional_packages(packages)
		if service:
			install_session.enable_service(service)

	def install(self, install_session: 'Installer'):
		# Install common packages for all desktop environments
		install_session.add_additional_packages(self.packages)

		self._install_greeter(install_session)

		for profile in self._current_selection:
			log(f'Installing profile {profile.name}...')

			install_session.add_additional_packages(profile.packages)
			install_session.enable_service(profile.services)

			profile.install(install_session)
