# A desktop environemtn using "Awesome" window manager.

import archinstall

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

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

	arguments = {
		'keyboard_layout' : 'sv-latin1',
		"editor" : "nano",
		"mediaplayer" : "lollypop gstreamer gst-plugins-good gnome-keyring",
		"filebrowser" : "nemo gpicview-gtk3",
		"webbrowser" : "chromium",
		"window_manager" : "awesome",
		"virtulization" : "qemu ovmf",
		"utils" : "openssh sshfs git htop pkgfile scrot dhclient wget smbclient cifs-utils libu2f-host",
		"audio" : "pulseaudio pulseaudio-alsa pavucontrol"
	}

	installation.add_additional_packages("{webbrowser} {utils} {mediaplayer} {window_manager} {virtulization} {filebrowser} {editor}".format(**arguments))

	with open(f'{installation.mountpoint}/etc/X11/xinit/xinitrc', 'a') as X11:
		X11.write('setxkbmap se\n')

	with open(f'{installation.mountpoint}/etc/vconsole.conf', 'a') as vconsole:
		vconsole.write('KEYMAP={keyboard_layout}\n'.format(**arguments))
		vconsole.write('FONT=lat9w-16\n')

	awesome = archinstall.Application(installation, 'awesome')
	awesome.install()