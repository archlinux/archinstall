# from typing import List, Dict, Optional, TYPE_CHECKING, Any
#
# from ..lib import menu
# from archinstall.lib.output import log, FormattedOutput
# from archinstall.lib.profile.profiles_handler import profile_handler
# from archinstall.default_profiles.profile import Profile, ProfileType, SelectResult, ProfileInfo, TProfile
#
# if TYPE_CHECKING:
# 	from archinstall.lib.installer import Installer
# 	_: Any
#
#
# class CustomProfileList(menu.ListManager):
# 	def __init__(self, prompt: str, profiles: List[TProfile]):
# 		self._actions = [
# 			str(_('Add profile')),
# 			str(_('Edit profile')),
# 			str(_('Delete profile'))
# 		]
# 		super().__init__(prompt, profiles, [self._actions[0]], self._actions[1:])
#
# 	def reformat(self, data: List[TProfile]) -> Dict[str, Optional[TProfile]]:
# 		table = FormattedOutput.as_table(data)
# 		rows = table.split('\n')
#
# 		# these are the header rows of the table and do not map to any profile obviously
# 		# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
# 		# the selectable rows so the header has to be aligned
# 		display_data: Dict[str, Optional[TProfile]] = {f'  {rows[0]}': None, f'  {rows[1]}': None}
#
# 		for row, profile in zip(rows[2:], data):
# 			row = row.replace('|', '\\|')
# 			display_data[row] = profile
#
# 		return display_data
#
# 	def selected_action_display(self, profile: TProfile) -> str:
# 		return profile.name
#
# 	def handle_action(
# 		self,
# 		action: str,
# 		entry: Optional['CustomTypeProfile'],
# 		data: List['CustomTypeProfile']
# 	) -> List['CustomTypeProfile']:
# 		if action == self._actions[0]:  # add
# 			new_profile = self._add_profile()
# 			if new_profile is not None:
# 				# in case a profile with the same name as an existing profile
# 				# was created we'll replace the existing one
# 				data = [d for d in data if d.name != new_profile.name]
# 				data += [new_profile]
# 		elif entry is not None:
# 			if action == self._actions[1]:  # edit
# 				new_profile = self._add_profile(entry)
# 				if new_profile is not None:
# 					# we'll remove the original profile and add the modified version
# 					data = [d for d in data if d.name != entry.name and d.name != new_profile.name]
# 					data += [new_profile]
# 			elif action == self._actions[2]:  # delete
# 				data = [d for d in data if d != entry]
#
# 		return data
#
# 	def _is_new_profile_name(self, name: str) -> bool:
# 		existing_profile = profile_handler.get_profile_by_name(name)
# 		if existing_profile is not None and existing_profile.profile_type != ProfileType.CustomType:
# 			return False
# 		return True
#
# 	def _add_profile(self, editing: Optional['CustomTypeProfile'] = None) -> Optional['CustomTypeProfile']:
# 		name_prompt = '\n\n' + str(_('Profile name: '))
#
# 		while True:
# 			profile_name = menu.TextInput(name_prompt, editing.name if editing else '').run().strip()
#
# 			if not profile_name:
# 				return None
#
# 			if not self._is_new_profile_name(profile_name):
# 				error_prompt = str(_("The profile name you entered is already in use. Try again"))
# 				print(error_prompt)
# 			else:
# 				break
#
# 		packages_prompt = str(_('Packages to be install with this profile (space separated, leave blank to skip): '))
# 		edit_packages = ' '.join(editing.packages) if editing else ''
# 		packages = menu.TextInput(packages_prompt, edit_packages).run().strip()
#
# 		services_prompt = str(_('Services to be enabled with this profile (space separated, leave blank to skip): '))
# 		edit_services = ' '.join(editing.services) if editing else ''
# 		services = menu.TextInput(services_prompt, edit_services).run().strip()
#
# 		choice = menu.Menu(
# 			str(_('Should this profile be enabled for installation?')),
# 			menu.Menu.yes_no(),
# 			skip=False,
# 			default_option=menu.Menu.no(),
# 			clear_screen=False,
# 			show_search_hint=False
# 		).run()
#
# 		enable_profile = True if choice.value == menu.Menu.yes() else False
#
# 		profile = CustomTypeProfile(
# 			profile_name,
# 			enabled=enable_profile,
# 			packages=packages.split(' '),
# 			services=services.split(' ')
# 		)
#
# 		return profile
#
#
# # TODO
# # Still needs some ironing out
# class CustomProfile():
# 	def __init__(self):
# 		super().__init__(
# 			'Custom',
# 			ProfileType.Custom,
# 			description=str(_('Create your own'))
# 		)
#
# 	def json(self) -> Dict[str, Any]:
# 		data: Dict[str, Any] = {'main': self.name, 'gfx_driver': self.gfx_driver, 'custom': []}
#
# 		for profile in self._current_selection:
# 			data['custom'].append({
# 				'name': profile.name,
# 				'packages': profile.packages,
# 				'services': profile.services,
# 				'enabled': profile.custom_enabled
# 			})
#
# 		return data
#
# 	def do_on_select(self) -> SelectResult:
# 		custom_profile_list = CustomProfileList('', profile_handler.get_custom_profiles())
# 		custom_profiles = custom_profile_list.run()
#
# 		# we'll first remove existing custom default_profiles with
# 		# the same name and then add the new ones this
# 		# will avoid errors of default_profiles with duplicate naming
# 		profile_handler.remove_custom_profiles(custom_profiles)
# 		profile_handler.add_custom_profiles(custom_profiles)
#
# 		self.set_current_selection(custom_profiles)
#
# 		if custom_profile_list.is_last_choice_cancel():
# 			return SelectResult.SameSelection
#
# 		enabled_profiles = [p for p in self._current_selection if p.custom_enabled]
# 		# in  case we only created inactive default_profiles we wanna store them but
# 		# we want to reset the original setting
# 		if not enabled_profiles:
# 			return SelectResult.ResetCurrent
#
# 		return SelectResult.NewSelection
#
# 	def post_install(self, install_session: 'Installer'):
# 		for profile in self._current_selection:
# 			profile.post_install(install_session)
#
# 	def install(self, install_session: 'Installer'):
# 		driver_packages = self.gfx_driver_packages()
# 		install_session.add_additional_packages(driver_packages)
#
# 		for profile in self._current_selection:
# 			if profile.custom_enabled:
# 				log(f'Installing custom profile {profile.name}...')
#
# 				install_session.add_additional_packages(profile.packages)
# 				install_session.enable_service(profile.services)
#
# 				profile.install(install_session)
#
# 	def info(self) -> Optional[ProfileInfo]:
# 		enabled_profiles = [p for p in self._current_selection if p.custom_enabled]
# 		if enabled_profiles:
# 			details = ', '.join([p.name for p in enabled_profiles])
# 			gfx_driver = self.gfx_driver
# 			return ProfileInfo(self.name, details, gfx_driver)
#
# 		return None
#
# 	def reset(self):
# 		for profile in self._current_selection:
# 			profile.set_enabled(False)
#
# 		self.gfx_driver = None
#
#
# class CustomTypeProfile(Profile):
# 	def __init__(
# 		self,
# 		name: str,
# 		enabled: bool = False,
# 		packages: List[str] = [],
# 		services: List[str] = []
# 	):
# 		super().__init__(
# 			name,
# 			ProfileType.CustomType,
# 			packages=packages,
# 			services=services,
# 			support_gfx_driver=True
# 		)
#
# 		self.custom_enabled = enabled
#
# 	def json(self) -> Dict[str, Any]:
# 		return {
# 			'name': self.name,
# 			'packages': self.packages,
# 			'services': self.services,
# 			'enabled': self.custom_enabled
# 		}
