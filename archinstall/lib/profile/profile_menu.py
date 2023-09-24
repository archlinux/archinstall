from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Dict

from archinstall.default_profiles.profile import Profile, GreeterType
from .profile_model import ProfileConfiguration
from ..menu import Menu, MenuSelectionType, AbstractSubMenu, Selector
from ..interactions.system_conf import select_driver
from ..hardware import GfxDriver

if TYPE_CHECKING:
	_: Any


class ProfileMenu(AbstractSubMenu):
	def __init__(
		self,
		data_store: Dict[str, Any],
		preset: Optional[ProfileConfiguration] = None
	):
		if preset:
			self._preset = preset
		else:
			self._preset = ProfileConfiguration()

		super().__init__(data_store=data_store)

	def setup_selection_menu_options(self):
		self._menu_options['profile'] = Selector(
			_('Type'),
			lambda x: self._select_profile(x),
			display_func=lambda x: x.name if x else None,
			preview_func=self._preview_profile,
			default=self._preset.profile,
			enabled=True
		)

		self._menu_options['gfx_driver'] = Selector(
			_('Graphics driver'),
			lambda preset: self._select_gfx_driver(preset),
			display_func=lambda x: x.value if x else None,
			dependencies=['profile'],
			default=self._preset.gfx_driver if self._preset.profile and self._preset.profile.is_graphic_driver_supported() else None,
			enabled=self._preset.profile.is_graphic_driver_supported() if self._preset.profile else False
		)

		self._menu_options['greeter'] = Selector(
			_('Greeter'),
			lambda preset: select_greeter(self._menu_options['profile'].current_selection, preset),
			display_func=lambda x: x.value if x else None,
			dependencies=['profile'],
			default=self._preset.greeter if self._preset.profile and self._preset.profile.is_greeter_supported() else None,
			enabled=self._preset.profile.is_greeter_supported() if self._preset.profile else False
		)

	def run(self, allow_reset: bool = True) -> Optional[ProfileConfiguration]:
		super().run(allow_reset=allow_reset)

		if self._data_store.get('profile', None):
			return ProfileConfiguration(
				self._menu_options['profile'].current_selection,
				self._menu_options['gfx_driver'].current_selection,
				self._menu_options['greeter'].current_selection
			)

		return None

	def _select_profile(self, preset: Optional[Profile]) -> Optional[Profile]:
		profile = select_profile(preset)
		if profile is not None:
			if not profile.is_graphic_driver_supported():
				self._menu_options['gfx_driver'].set_enabled(False)
				self._menu_options['gfx_driver'].set_current_selection(None)
			else:
				self._menu_options['gfx_driver'].set_enabled(True)
				self._menu_options['gfx_driver'].set_current_selection(GfxDriver.AllOpenSource)

			if not profile.is_greeter_supported():
				self._menu_options['greeter'].set_enabled(False)
				self._menu_options['greeter'].set_current_selection(None)
			else:
				self._menu_options['greeter'].set_enabled(True)
				self._menu_options['greeter'].set_current_selection(profile.default_greeter_type)
		else:
			self._menu_options['gfx_driver'].set_current_selection(None)
			self._menu_options['greeter'].set_current_selection(None)

		return profile

	def _select_gfx_driver(self, preset: Optional[GfxDriver] = None) -> Optional[GfxDriver]:
		driver = preset
		profile: Optional[Profile] = self._menu_options['profile'].current_selection

		if profile:
			if profile.is_graphic_driver_supported():
				driver = select_driver(current_value=preset)

			if driver and 'Sway' in profile.current_selection_names():
				if driver.is_nvidia():
					prompt = str(_('The proprietary Nvidia driver is not supported by Sway. It is likely that you will run into issues, are you okay with that?'))
					choice = Menu(prompt, Menu.yes_no(), default_option=Menu.no(), skip=False).run()

					if choice.value == Menu.no():
						return None

		return driver

	def _preview_profile(self) -> Optional[str]:
		profile: Optional[Profile] = self._menu_options['profile'].current_selection

		if profile:
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

		default: Optional[GreeterType] = None

		if preset is not None:
			default = preset
		elif profile is not None:
			default_greeter = profile.default_greeter_type
			default = default_greeter if default_greeter else None

		choice = Menu(
			title,
			greeter_options,
			skip=True,
			default_option=default.value if default else None
		).run()

		match choice.type_:
			case MenuSelectionType.Skip:
				return default

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
