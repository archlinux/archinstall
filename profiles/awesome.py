# A desktop environment using "Awesome" window manager.

import archinstall

is_top_level_profile = False

# New way of defining packages for a profile, which is iterable and can be used out side
# of the profile to get a list of "what packages will be installed".
__packages__ = ['nemo', 'gpicview-gtk3', 'scrot']

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	# Awesome WM requires that xorg is installed
	profile = archinstall.Profile(None, 'xorg')
	with profile.load_instructions(namespace='xorg.py') as imported:
		if hasattr(imported, '_prep_function'):
			return imported._prep_function()
		else:
			print('Deprecated (??): xorg profile has no _prep_function() anymore')


# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("awesome", "/somewhere/awesome.py")
# or through conventional import awesome
if __name__ == 'awesome':
	# Install the application awesome from the template under /applications/
	awesome = archinstall.Application(installation, 'awesome')
	awesome.install()

	installation.add_additional_packages(__packages__)

	alacritty = archinstall.Application(installation, 'alacritty')
	alacritty.install()

	# TODO: Copy a full configuration to ~/.config/awesome/rc.lua instead.
	with open(f'{installation.target}/etc/xdg/awesome/rc.lua', 'r') as fh:
		awesome_lua = fh.read()

	## Replace xterm with alacritty for a smoother experience.
	awesome_lua = awesome_lua.replace('"xterm"', '"alacritty"')

	with open(f'{installation.target}/etc/xdg/awesome/rc.lua', 'w') as fh:
		fh.write(awesome_lua)

	## TODO: Configure the right-click-menu to contain the above packages that were installed. (as a user config)
	
	## Remove some interfering nemo settings
	installation.arch_chroot("gsettings set org.nemo.desktop show-desktop-icons false")
	installation.arch_chroot("xdg-mime default nemo.desktop inode/directory application/x-gnome-saved-search")
