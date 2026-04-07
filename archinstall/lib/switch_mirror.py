from pathlib import Path

from archinstall.lib.installer import Installer
from archinstall.lib.models.device import DiskLayoutConfiguration, DiskLayoutType
from archinstall.lib.mirror.mirror_handler import MirrorListHandler
from archinstall.lib.mirror.mirror_menu import MirrorMenu
from archinstall.lib.network.wifi_handler import WifiHandler
from archinstall.lib.output import debug, error, info, warn
from archinstall.lib.translationhandler import tr
from archinstall.lib.networking import ping
from archinstall.tui.ui.components import tui


def check_online(wifi_handler: WifiHandler | None = None) -> bool:
    try:
        ping('1.1.1.1')
    except OSError as ex:
        if 'Network is unreachable' in str(ex):
            if wifi_handler is not None:
                result: bool = tui.run(wifi_handler)
                if not result:
                    return False

    return True

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
