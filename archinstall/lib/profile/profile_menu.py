from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

from archinstall.default_profiles.profile import GreeterType, Profile
from archinstall.tui import Alignment, FrameProperties, MenuItem, MenuItemGroup, Orientation, ResultType, SelectMenu

from ..hardware import GfxDriver
from ..interactions.system_conf import select_driver
from ..menu import AbstractSubMenu
from .profile_model import ProfileConfiguration

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


class ProfileMenu(AbstractSubMenu):
	def __init__(
		self,
		preset: ProfileConfiguration | None = None
	):
		if preset:
			self._preset = preset
		else:
			self._preset = ProfileConfiguration()

		self._data_store: dict[str, Any] = {}

		menu_optioons = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_optioons, checkmarks=True)

		super().__init__(self._item_group, data_store=self._data_store, allow_reset=True)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=str(_('Type')),
				action=self._select_profile,
				value=self._preset.profile,
				preview_action=self._preview_profile,
				key='profile'
			),
			MenuItem(
				text=str(_('Graphics driver')),
				action=self._select_gfx_driver,
				value=self._preset.gfx_driver if self._preset.profile and self._preset.profile.is_graphic_driver_supported() else None,
				preview_action=self._prev_gfx,
				enabled=self._preset.profile.is_graphic_driver_supported() if self._preset.profile else False,
				dependencies=['profile'],
				key='gfx_driver',
			),
			MenuItem(
				text=str(_('Greeter')),
				action=lambda x: select_greeter(preset=x),
				value=self._preset.greeter if self._preset.profile and self._preset.profile.is_greeter_supported() else None,
				enabled=self._preset.profile.is_graphic_driver_supported() if self._preset.profile else False,
				preview_action=self._prev_greeter,
				dependencies=['profile'],
				key='greeter',
			)
		]

	@override
	def run(self) -> ProfileConfiguration | None:
		super().run()

		if self._data_store.get('profile', None):
			return ProfileConfiguration(
				self._data_store.get('profile', None),
				self._data_store.get('gfx_driver', None),
				self._data_store.get('greeter', None),
			)

		return None

	def _select_profile(self, preset: Profile | None) -> Profile | None:
		profile = select_profile(preset)

		if profile is not None:
			if not profile.is_graphic_driver_supported():
				self._item_group.find_by_key('gfx_driver').enabled = False
				self._item_group.find_by_key('gfx_driver').value = None
			else:
				self._item_group.find_by_key('gfx_driver').enabled = True
				self._item_group.find_by_key('gfx_driver').value = GfxDriver.AllOpenSource

			if not profile.is_greeter_supported():
				self._item_group.find_by_key('greeter').enabled = False
				self._item_group.find_by_key('greeter').value = None
			else:
				self._item_group.find_by_key('greeter').enabled = True
				self._item_group.find_by_key('greeter').value = profile.default_greeter_type
		else:
			self._item_group.find_by_key('gfx_driver').value = None
			self._item_group.find_by_key('greeter').value = None

		return profile

	def _select_gfx_driver(self, preset: GfxDriver | None = None) -> GfxDriver | None:
		driver = preset
		profile: Profile | None = self._item_group.find_by_key('profile').value

		if profile:
			if profile.is_graphic_driver_supported():
				driver = select_driver(preset=preset)

			if driver and 'Sway' in profile.current_selection_names():
				if driver.is_nvidia():
					header = str(_('The proprietary Nvidia driver is not supported by Sway.')) + '\n'
					header += str(_('It is likely that you will run into issues, are you okay with that?')) + '\n'

					group = MenuItemGroup.yes_no()
					group.focus_item = MenuItem.no()
					group.default_item = MenuItem.no()

					result = SelectMenu(
						group,
						header=header,
						allow_skip=False,
						columns=2,
						orientation=Orientation.HORIZONTAL,
						alignment=Alignment.CENTER
					).run()

					if result.item() == MenuItem.no():
						return preset

		return driver

	def _prev_gfx(self, item: MenuItem) -> str | None:
		if item.value:
			driver = item.get_value().value
			packages = item.get_value().packages_text()
			return f'Driver: {driver}\n{packages}'
		return None

	def _prev_greeter(self, item: MenuItem) -> str | None:
		if item.value:
			return f'{_("Greeter")}: {item.value.value}'
		return None

	def _preview_profile(self, item: MenuItem) -> str | None:
		profile: Profile | None = item.value
		text = ''

		if profile:
			if (sub_profiles := profile.current_selection) is not None:
				text += str(_('Selected profiles: '))
				text += ', '.join([p.name for p in sub_profiles]) + '\n'

			if packages := profile.packages_text(include_sub_packages=True):
				text += f'{packages}'

			if text:
				return text

		return None


def select_greeter(
	profile: Profile | None = None,
	preset: GreeterType | None = None
) -> GreeterType | None:
	if not profile or profile.is_greeter_supported():
		items = [MenuItem(greeter.value, value=greeter) for greeter in GreeterType]
		group = MenuItemGroup(items, sort_items=True)

		default: GreeterType | None = None
		if preset is not None:
			default = preset
		elif profile is not None:
			default_greeter = profile.default_greeter_type
			default = default_greeter if default_greeter else None

		group.set_default_by_value(default)

		result = SelectMenu(
			group,
			allow_skip=True,
			frame=FrameProperties.min(str(_('Greeter'))),
			alignment=Alignment.CENTER
		).run()

		match result.type_:
			case ResultType.Skip:
				return preset
			case ResultType.Selection:
				return result.get_value()
			case ResultType.Reset:
				raise ValueError('Unhandled result type')

	return None


def select_profile(
	current_profile: Profile | None = None,
	header: str | None = None,
	allow_reset: bool = True,
) -> Profile | None:
	from archinstall.lib.profile.profiles_handler import profile_handler
	top_level_profiles = profile_handler.get_top_level_profiles()

	if header is None:
		header = str(_('This is a list of pre-programmed default_profiles')) + '\n'

	items = [MenuItem(p.name, value=p) for p in top_level_profiles]
	group = MenuItemGroup(items, sort_items=True)
	group.set_selected_by_value(current_profile)

	result = SelectMenu(
		group,
		header=header,
		allow_reset=allow_reset,
		allow_skip=True,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(str(_('Main profile')))
	).run()

	match result.type_:
		case ResultType.Reset:
			return None
		case ResultType.Skip:
			return current_profile
		case ResultType.Selection:
			profile_selection: Profile = result.get_value()
			select_result = profile_selection.do_on_select()

			if not select_result:
				return None

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

	return None
