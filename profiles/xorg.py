# A system with "xorg" installed

import os
from archinstall import generic_select, sys_command, RequirementError

is_top_level_profile = True


def _prep_function(*args, **kwargs):
    """
    Magic function called by the importing installer
    before continuing any further. It also avoids executing any
    other code in this stage. So it's a safe way to ask the user
    for more input before any other installer steps start.
    """

    __builtins__['_gfx_driver_packages'] = archinstall.select_driver()

    # TODO: Add language section and/or merge it with the locale selected
    #       earlier in for instance guided.py installer.

    return True


# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("xorg", "/somewhere/xorg.py")
# or through conventional import xorg
if __name__ == 'xorg':
    try:
        installation.add_additional_packages(
            f"xorg-server xorg-xinit {' '.join(_gfx_driver_packages)}")
    except:
        # Prep didn't run, so there's no driver to install
        installation.add_additional_packages(f"xorg-server xorg-xinit")

    # with open(f'{installation.mountpoint}/etc/X11/xinit/xinitrc', 'a') as X11:
    # 	X11.write('setxkbmap se\n')

    # with open(f'{installation.mountpoint}/etc/vconsole.conf', 'a') as vconsole:
    # 	vconsole.write('KEYMAP={keyboard_layout}\n'.format(**arguments))
    # 	vconsole.write('FONT=lat9w-16\n')

    # awesome = archinstall.Application(installation, 'awesome')
    # awesome.install()
