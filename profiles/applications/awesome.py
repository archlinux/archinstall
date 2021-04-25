import archinstall

__packages__ = ["awesome", "xorg-xrandr", "xterm", "feh", "slock", "terminus-font", "gnu-free-fonts", "ttf-liberation", "xsel"]

installation.install_profile('xorg')

installation.add_additional_packages(__packages__)

with open(f'{installation.target}/etc/X11/xinit/xinitrc', 'r') as xinitrc:
	xinitrc_data = xinitrc.read()

for line in xinitrc_data.split('\n'):
	if "twm &" in line:
		xinitrc_data = xinitrc_data.replace(line, f"# {line}")
	if "xclock" in line:
		xinitrc_data = xinitrc_data.replace(line, f"# {line}")
	if "xterm" in line:
		xinitrc_data = xinitrc_data.replace(line, f"# {line}")

xinitrc_data += '\n'
xinitrc_data += 'exec awesome\n'

with open(f'{installation.target}/etc/X11/xinit/xinitrc', 'w') as xinitrc:
	xinitrc.write(xinitrc_data)
