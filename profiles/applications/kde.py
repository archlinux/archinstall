import archinstall

installation.add_additional_packages("plasma-meta kde-applications-meta") # We'll support plasma-desktop (minimal) later

with open(f'{installation.mountpoint}/etc/X11/xinit/xinitrc', 'r') as xinitrc:
	xinitrc_data = xinitrc.read()

# Remove Xorg defaults
for line in xinitrc_data.split('\n'):
	if 'twm &' in line: xinitrc_data = xinitrc_data.replace(line, f"# {line}")
	if 'xclock' in line: xinitrc_data = xinitrc_data.replace(line, f"# {line}")
	if 'xterm' in line: xinitrc_data = xinitrc_data.replace(line, f"# {line}")

# Add the KDE specifics
xinitrc_data += '\n'
xinitrc_data += 'export DESKTOP_SESSION=plasma\n'
xinitrc_data += 'exec startplasma-x11\n'

# And save it
with open(f'{installation.mountpoint}/etc/X11/xinit/xinitrc', 'w') as xinitrc:
	xinitrc.write(xinitrc_data)