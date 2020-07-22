import archinstall

installation.add_additional_packages("awesome xorg-server xorg-xrandr xorg-xinit xterm feh slock xscreensaver terminus-font-otb gnu-free-fonts ttf-liberation xsel")

with open(f'{installation.mountpoint}/etc/X11/xinit/xinitrc', 'r') as xinitrc:
	xinitrc_data = xinitrc.read()

xinitrc_data = xinitrc_data.replace('twm &', '# twm &').replace('\nxclock ', '\n# xclock').replace('exec xterm', '# exec xterm')
xinitrc_data += '\nxscreensaver -no-splash &\n'
xinitrc_data += 'exec awesome\n'
with open(f'{installation.mountpoint}/etc/X11/xinit/xinitrc', 'w') as xinitrc:
	xinitrc.write(xinitrc_data)

with open(f'{installation.mountpoint}/etc/xdg/awesome/rc.lua', 'r') as awesome_rc_lua:
	awesome = awesome_rc_lua.read()

awesome = awesome.replace('xterm', 'xterm -ls -xrm "XTerm*selectToClipboard: true"')
awesome = awesome.replace('{ "open terminal", terminal, ','{ "Chromium", "chromium" },\n    "open terminal", terminal, ')
awesome = awesome.replace('{ "open terminal", terminal, ', '{ "File handler", "nemo" },\n    "open terminal", terminal, ')
awesome = awesome.replace('\nglobalkeys = gears.table.join(', 'globalkeys = gears.table.join(\n    awful.key({ modkey,    }, \"l\",  function() awful.spawn(\"xscreensaver-command -lock &\") end),\n')
# "awk -i inplace -v RS='' '{gsub(/awful.key\\({ modkey,.*?}, \"Tab\",.*?\"client\"}\\),/, \"awful.key({ modkey,      }, \"Tab\",\n      function ()\n        awful.client.focus.byidx(-1)\n        if client.focus then\n          client.focus:raise()\n        end\n      end),\n    awful.key({ modkey, \"Shift\"    }, \"Tab\",\n    function ()\n      awful.client.focus.byidx(1)\n        if client.focus then\n           client.focus.raise()\n        end\n      end),\"); print}' {installation.mountpoint}/etc/xdg/awesome/rc.lua" : {"no-chroot" : true},

with open(f'{installation.mountpoint}/etc/xdg/awesome/rc.lua', 'w') as awesome_rc_lua:
	awesome_rc_lua.write(awesome)

installation.arch_chroot('gsettings set org.nemo.desktop show-desktop-icons false')
installation.arch_chroot('xdg-mime default nemo.desktop inode/directory application/x-gnome-saved-search')