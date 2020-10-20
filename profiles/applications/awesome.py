import archinstall

installation.add_additional_packages(
	"awesome xorg-xrandr xterm feh slock terminus-font-otb gnu-free-fonts ttf-liberation xsel"
)

with open(f'{installation.mountpoint}/etc/X11/xinit/xinitrc', 'r') as xinitrc:
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

with open(f'{installation.mountpoint}/etc/X11/xinit/xinitrc', 'w') as xinitrc:
	xinitrc.write(xinitrc_data)

with open(f'{installation.mountpoint}/etc/xdg/awesome/rc.lua', 'r') as awesome_rc_lua:
	awesome = awesome_rc_lua.read()

awesome = awesome.replace('xterm', 'xterm -ls -xrm \\"XTerm*selectToClipboard: true\\"')

with open(f'{installation.mountpoint}/etc/xdg/awesome/rc.lua', 'w') as awesome_rc_lua:
	awesome_rc_lua.write(awesome)
