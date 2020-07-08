import archinstall

arguments = {
	'keyboard_layout' : 'sv-latin1',
	"editor" : "nano",
	"mediaplayer" : "lollypop gstreamer gst-plugins-good gnome-keyring",
	"filebrowser" : "nemo gpicview-gtk3",
	"webbrowser" : "chromium",
	"window_manager" : "awesome",
	"window_manager_dependencies" : "xorg-server xorg-xrandr xorg-xinit xterm",
	"window_manager_utilities" : "feh slock xscreensaver terminus-font-otb gnu-free-fonts ttf-liberation xsel",
	"virtulization" : "qemu ovmf",
	"utils" : "openssh sshfs git htop pkgfile scrot dhclient wget smbclient cifs-utils libu2f-host",
	"audio" : "pulseaudio pulseaudio-alsa pavucontrol"
}

installation.add_additional_packages("{_webbrowser} {_utils} {_mediaplayer} {_window_manager} {_window_manager_dependencies} {_window_manager_utilities} {_virtulization} {_filebrowser} {_editor}".format(**arguments))

with open(f'{installation.mountpoint}/etc/X11/xinit/xinitrc', 'a') as X11:
	X11.write('setxkbmap se\n')

with open(f'{installation.mountpoint}/etc/vconsole.conf', 'a') as vconsole:
	vconsole.write('KEYMAP={keyboard_layout}\n'.format(**arguments))
	vconsole.write('FONT=lat9w-16\n')

awesome = archinstall.Application(installation, 'awesome')
awesome.install()