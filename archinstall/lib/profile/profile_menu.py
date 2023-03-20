from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Dict

from archinstall import profile_handler, AVAILABLE_GFX_DRIVERS
from archinstall.default_profiles.profile import Profile, GreeterType
from archinstall.lib.menu.abstract_menu import AbstractSubMenu, Selector
from archinstall.lib.menu.menu import Menu, MenuSelectionType
from archinstall.lib.user_interaction.system_conf import select_driver

if TYPE_CHECKING:
	_: Any


@dataclass
class ProfileConfiguration:
	profile: Profile
	gfx_driver: Optional[str] = None
	greeter: Optional[GreeterType] = None

	def json(self) -> Dict[str, Any]:
		return {
			'profile': profile_handler.to_json(self.profile),
			'gfx_driver': self.gfx_driver,
			'greeter': self.greeter.value if self.greeter else None
		}

	@classmethod
	def parse_arg(cls, arg: Dict[str, Any]) -> 'ProfileConfiguration':
		greeter = arg.get('greeter', None)

		return ProfileConfiguration(
			profile_handler.parse_profile_config(arg['profile']),
			arg.get('gfx_driver', None),
			GreeterType(greeter) if greeter else None
		)


class ProfileMenu(AbstractSubMenu):
	def __init__(self, preset: Optional[ProfileConfiguration]):
		self._preset = preset
		super().__init__()

	def setup_selection_menu_options(self):
		self._menu_options['profile'] = \
			Selector(
				_('Profile'),
				lambda x: select_profile(),
				display_func=lambda x: x.name if x else None,
				preview_func=self._preview_profile,
				default=self._preset.profile if self._preset else None,
				enabled=True
			)

		self._menu_options['gfx_driver'] = \
			Selector(
				_('Graphics driver'),
				lambda preset: self._select_gfx_driver(preset),
				display_func=lambda x: x if x else None,
				dependencies=['profile'],
				enabled=True,
				default=self._preset.gfx_driver if self._preset else 'All open-source (default)'
			)

		self._menu_options['greeter'] = \
			Selector(
				_('Greeter'),
				lambda preset: select_greeter(self._menu_options['profile'].current_selection, preset),
				display_func=lambda x: x.value if x else None,
				dependencies=['profile'],
				default=self._preset.greeter if self._preset else None,
				enabled=True
			)

	def run(self, allow_reset: bool = True) -> Optional[ProfileConfiguration]:
		super().run(allow_reset=allow_reset)

		if self._data_store.get('profile', None):
			return ProfileConfiguration(
				self._data_store.get('profile', None),
				self._data_store.get('gfx_driver', None),
				self._data_store.get('greeter', None)
			)

		return None

	def _select_gfx_driver(self, preset: Optional[str] = None) -> Optional[str]:
		driver = None
		selector = self._menu_options['profile']

		if selector.has_selection():
			profile: Profile = selector.current_selection
			if profile.is_graphic_driver_supported():
				driver = select_driver(current_value=preset)

		profile: Profile = self._menu_options['profile'].current_selection

		if driver and 'Sway' in profile.current_selection_names():
			packages = AVAILABLE_GFX_DRIVERS[driver]

			if packages and "nvidia" in packages:
				prompt = str(
					_('The proprietary Nvidia driver is not supported by Sway. It is likely that you will run into issues, are you okay with that?'))
				choice = Menu(prompt, Menu.yes_no(), default_option=Menu.no(), skip=False).run()

				if choice.value == Menu.no():
					return None

		return driver

	def _preview_profile(self) -> Optional[str]:
		selector = self._menu_options['profile']
		if selector.has_selection():
			profile: Profile = selector.current_selection
			names = profile.current_selection_names()
			return '\n'.join(names)

		return None


def select_greeter(
	profile: Optional[Profile] = None,
	preset: Optional[GreeterType] = None
) -> Optional[GreeterType]:
	if not profile or profile.is_greeter_supported():
		title = str(_('Please chose which greeter to install'))
		greeter_options = [greeter.value for greeter in GreeterType]

		if preset is not None:
			default_value = preset.value
		elif profile is not None:
			default_greeter = profile.default_greeter_type
			default_value = default_greeter.value if default_greeter else None
		else:
			default_value = None

		choice = Menu(title, greeter_options, skip=False, default_option=default_value).run()
		return GreeterType(choice.single_value)

	return None


def select_profile(
	current_profile: Optional[Profile] = None,
	title: Optional[str] = None,
	allow_reset: bool = True,
	multi: bool = False
) -> Optional[Profile]:
	from archinstall.lib.profile.profiles_handler import profile_handler
	top_level_profiles = profile_handler.get_top_level_profiles()

	display_title = title
	if not display_title:
		display_title = str(_('This is a list of pre-programmed default_profiles'))

	choice = profile_handler.select_profile(
		top_level_profiles,
		current_profile=current_profile,
		title=display_title,
		allow_reset=allow_reset,
		multi=multi
	)

	match choice.type_:
		case MenuSelectionType.Selection:
			profile_selection: Profile = choice.single_value
			select_result = profile_selection.do_on_select()

			if not select_result:
				return select_profile(
					current_profile=current_profile,
					title=title,
					allow_reset=allow_reset,
					multi=multi
				)

			# we're going to reset the currently selected profile(s) to avoid
			# any stale data laying around
			match select_result:
				case select_result.NewSelection:
					profile_handler.reset_top_level_profiles(exclude=[profile_selection])
					current_profile = profile_selection
				case select_result.ResetCurrent:
					profile_handler.reset_top_level_profiles()
					current_profile = None
				case select_result.SameSelection:
					pass

			return current_profile
		case MenuSelectionType.Reset:
			return None
		case MenuSelectionType.Skip:
			return current_profile
