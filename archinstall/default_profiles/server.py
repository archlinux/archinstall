from typing import TYPE_CHECKING, override

from archinstall.default_profiles.profile import Profile, ProfileType, SelectResult
from archinstall.lib.output import info
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.tui.curses_menu import SelectMenu
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType
from archinstall.tui.types import FrameProperties, PreviewStyle

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class ServerProfile(Profile):
	def __init__(self, current_value: list[Profile] = []):
		super().__init__(
			'Server',
			ProfileType.Server,
			current_selection=current_value,
		)

	@override
	def do_on_select(self) -> SelectResult:
		items = [
			MenuItem(
				p.name,
				value=p,
				preview_action=lambda x: x.value.preview_text(),
			)
			for p in profile_handler.get_server_profiles()
		]

		group = MenuItemGroup(items, sort_items=True)
		group.set_selected_by_value(self.current_selection)

		result = SelectMenu[Profile](
			group,
			allow_reset=True,
			allow_skip=True,
			preview_style=PreviewStyle.RIGHT,
			preview_size='auto',
			preview_frame=FrameProperties.max('Info'),
			multi=True,
		).run()

		match result.type_:
			case ResultType.Selection:
				selections = result.get_values()
				self.current_selection = selections
				return SelectResult.NewSelection
			case ResultType.Skip:
				return SelectResult.SameSelection
			case ResultType.Reset:
				return SelectResult.ResetCurrent

	@override
	def post_install(self, install_session: 'Installer') -> None:
		for profile in self.current_selection:
			profile.post_install(install_session)

	@override
	def install(self, install_session: 'Installer') -> None:
		server_info = self.current_selection_names()
		details = ', '.join(server_info)
		info(f'Now installing the selected servers: {details}')

		for server in self.current_selection:
			info(f'Installing {server.name}...')
			install_session.add_additional_packages(server.packages)
			install_session.enable_service(server.services)
			server.install(install_session)

		info('If your selections included multiple servers with the same port, you may have to reconfigure them.')
