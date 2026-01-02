from archinstall.lib.args import ArchConfig, arch_config_handler
from archinstall.lib.configuration import ConfigurationHandler
from archinstall.lib.output import error, info, logger
from archinstall.tui import Tui
from archinstall.tui.curses_menu import SelectMenu
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType
from archinstall.tui.types import Alignment


def _check_for_saved_config() -> None:
	"""Check for saved config and offer to resume"""
	if not arch_config_handler.args.debug:
		return
	if not ConfigurationHandler.has_saved_config() or arch_config_handler.args.silent:
		return

	with Tui():
		items = [
			MenuItem(text=('Resume from saved selections'), value='resume'),
			MenuItem(text=('Start fresh'), value='fresh'),
		]

		group = MenuItemGroup(items)
		group.focus_item = group.items[0]  # Focus on resume

		result = SelectMenu[str](
			group,
			header=('Saved configuration found: \n'),
			alignment=Alignment.CENTER,
			allow_skip=False,
		).run()

		if result.type_ == ResultType.Selection:
			choice = result.get_value()

			if choice == 'resume':
				cached_config = ConfigurationHandler.load_saved_config()
				if cached_config:
					try:
						new_config = ArchConfig.from_config(cached_config, arch_config_handler.args)
						arch_config_handler._config = new_config
						info('Saved selections loaded successfully')
					except Exception as e:
						error(f'Failed to load saved selections: {e}')
			elif choice == 'fresh':
				# Remove both saved config files
				config_file = logger.directory / ConfigurationHandler._USER_CONFIG_FILENAME
				creds_file = logger.directory / ConfigurationHandler._USER_CREDS_FILENAME

				if config_file.exists():
					config_file.unlink()
				if creds_file.exists():
					creds_file.unlink()
