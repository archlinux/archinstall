# A desktop environemtn using "Awesome" window manager.

import archinstall

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