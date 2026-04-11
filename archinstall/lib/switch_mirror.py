from pathlib import Path

from archinstall.lib.installer import Installer
from archinstall.lib.models.device import DiskLayoutConfiguration, DiskLayoutType
from archinstall.lib.mirror.mirror_handler import MirrorListHandler
from archinstall.lib.mirror.mirror_menu import MirrorMenu
from archinstall.lib.output import debug, error, info, warn
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.components import tui

def switch_mirror_sources() -> bool:
    info(tr('Switching mirror sources.'))
    mirror_list_handler = MirrorListHandler()

    try:
        mirror_configuration = tui.run(lambda: MirrorMenu(mirror_list_handler).run())
    except Exception as e:
        error(tr('Could not open mirror configuration menu.'))
        debug(f'Failed to switch mirror sources: {e}')
        return False

    if mirror_configuration is None:
        warn(tr('Mirror source selection cancelled.'))
        return False

    try:
        installer = Installer(
            Path('/'),
            DiskLayoutConfiguration(DiskLayoutType.Pre_mount, mountpoint=Path('/')),
        )
        installer.set_mirrors(mirror_list_handler, mirror_configuration, on_target=False)
        info(tr('Mirror sources have been updated.'))
        return True
    except Exception as e:
        error(tr('Failed to update the local mirror list.'))
        debug(f'Failed to update the mirror list: {e}')
        return False
