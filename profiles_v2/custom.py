from profiles_v2.profiles_v2 import ProfileV2, ProfileType, SelectResult
from archinstall import log, ProfileHandler


class CustomProfileV2(ProfileV2):
	def __init__(self):
		super().__init__(
			'Custom',
			ProfileType.Custom,
			description=str(_('Create your own'))
		)

	def do_on_select(self) -> SelectResult:
		# list manager
		pass

	def post_install(self, install_session: 'Installer'):
		for profile in self._current_selection:
			profile.post_install(install_session)

	def install(self, install_session: 'Installer'):
		for profile in self._current_selection:
			log(f'Installing custom profile {profile.name}...')

			install_session.add_additional_packages(profile.packages())
			install_session.enable_service(profile.services())

			profile.install(install_session)

