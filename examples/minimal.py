import archinstall

# Select a harddrive and a disk password
archinstall.log("Minimal only supports:")
archinstall.log(" * Being installed to a single disk")

if archinstall.arguments.get('help', None):
	archinstall.log(" - Optional disk encryption via --!encryption-password=<password>")
	archinstall.log(" - Optional filesystem type via --filesystem=<fs type>")
	archinstall.log(" - Optional systemd network via --network")

archinstall.arguments['harddrive'] = archinstall.select_disk(archinstall.all_disks())


def install_on(mountpoint):
	# We kick off the installer by telling it where the
	with archinstall.Installer(mountpoint) as installation:
		# Strap in the base system, add a boot loader and configure
		# some other minor details as specified by this profile and user.
		if installation.minimal_installation():
			installation.set_hostname('minimal-arch')
			installation.add_bootloader()

			# Optionally enable networking:
			if archinstall.arguments.get('network', None):
				installation.copy_iso_network_config(enable_services=True)

			installation.add_additional_packages(['nano', 'wget', 'git'])
			installation.install_profile('minimal')

			installation.user_create('devel', 'devel')
			installation.user_set_pw('root', 'airoot')

	# Once this is done, we output some useful information to the user
	# And the installation is complete.
	archinstall.log("There are two new accounts in your installation after reboot:")
	archinstall.log(" * root (password: airoot)")
	archinstall.log(" * devel (password: devel)")


if archinstall.arguments['harddrive']:
	archinstall.arguments['harddrive'].keep_partitions = False

	print(f" ! Formatting {archinstall.arguments['harddrive']} in ", end='')
	archinstall.do_countdown()

	# First, we configure the basic filesystem layout
	with archinstall.Filesystem(archinstall.arguments['harddrive'], archinstall.GPT) as fs:
		# We use the entire disk instead of setting up partitions on your own
		if archinstall.arguments['harddrive'].keep_partitions is False:
			fs.use_entire_disk(root_filesystem_type=archinstall.arguments.get('filesystem', 'btrfs'))

		boot = fs.find_partition('/boot')
		root = fs.find_partition('/')

		boot.format('fat32')

		# We encrypt the root partition if we got a password to do so with,
		# Otherwise we just skip straight to formatting and installation
		if archinstall.arguments.get('!encryption-password', None):
			root.encrypted = True
			root.encrypt(password=archinstall.arguments.get('!encryption-password', None))

			with archinstall.luks2(root, 'luksloop', archinstall.arguments.get('!encryption-password', None)) as unlocked_root:
				unlocked_root.format(root.filesystem)
				unlocked_root.mount('/mnt')
		else:
			root.format(root.filesystem)
			root.mount('/mnt')

		boot.mount('/mnt/boot')

install_on('/mnt')
