# A desktop environment using "Awesome" window manager.

import archinstall


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
	# Install dependency profiles
	installation.install_profile('xorg')

	# Install the application awesome from the template under /applications/
	awesome = archinstall.Application(installation, 'awesome')
	awesome.install()

	# Then setup and configure the desktop environment: awesome
	editor = "nano"
	filebrowser = "nemo gpicview-gtk3"
	webbrowser = "chromium"
	window_manager = "awesome"
	virtulization = "qemu ovmf"
	utils = "openssh sshfs git htop pkgfile scrot dhclient wget smbclient cifs-utils libu2f-host"

	installation.add_additional_packages(f"{webbrowser} {utils} {window_manager} {virtulization} {filebrowser} {editor}")


	# with open(f'{installation.mountpoint}/etc/xdg/awesome/rc.lua', 'r') as awesome_rc_lua:
	#	awesome_lua = awesome_rc_lua.read()

	## Insert slock as a shortcut on Modkey+l   (window+l)
	# awesome_lua = awesome_lua.replace(
	# 	"\nglobalkeys = gears.table.join(",
	# 	"globalkeys = gears.table.join(\n    awful.key({ modkey,    }, \"l\",  function() awful.spawn(\"slock &\") end,\n"
	# )

	## Insert some useful applications:
	# awesome = awesome.replace('{ "open terminal", terminal, ','{ "Chromium", "chromium" },\n    "open terminal", terminal, ')
	# awesome = awesome.replace('{ "open terminal", terminal, ', '{ "File handler", "nemo" },\n    "open terminal", terminal, ')

	# Insert "normal" alt-tab  via Modkey+Tab that most new users are used to
	# "awk -i inplace -v RS='' '{gsub(/awful.key\\({ modkey,.*?}, \"Tab\",.*?\"client\"}\\),/, \"awful.key({ modkey,      }, \"Tab\",\n      function ()\n        awful.client.focus.byidx(-1)\n        if client.focus then\n          client.focus:raise()\n        end\n      end),\n    awful.key({ modkey, \"Shift\"    }, \"Tab\",\n    function ()\n      awful.client.focus.byidx(1)\n        if client.focus then\n           client.focus.raise()\n        end\n      end),\"); print}' {installation.mountpoint}/etc/xdg/awesome/rc.lua" : {"no-chroot" : true},

	# with open(f'{installation.mountpoint}/etc/xdg/awesome/rc.lua', 'w') as awesome_rc_lua:
	#	awesome_rc_lua.write(awesome_lua)
	
	## Remove some interfering nemo settings
	installation.arch_chroot("gsettings set org.nemo.desktop show-desktop-icons false")
	installation.arch_chroot("xdg-mime default nemo.desktop inode/directory application/x-gnome-saved-search")
