import archinstall, getpass

# Unmount and close previous runs
archinstall.sys_command(f'umount -R /mnt', suppress_errors=True)
archinstall.sys_command(f'cryptsetup close /dev/mapper/luksloop', suppress_errors=True)

# Select a harddrive and a disk password
harddrive = archinstall.select_disk(archinstall.all_disks())
disk_password = getpass.getpass(prompt='Disk password (won\'t echo): ')

with archinstall.Filesystem(harddrive, archinstall.GPT) as fs:
	# Use the entire disk instead of setting up partitions on your own
	fs.use_entire_disk('luks2')

	if harddrive.partition[1].size == '512M':
		raise OSError('Trying to encrypt the boot partition for petes sake..')
	harddrive.partition[0].format('fat32')

	with archinstall.luks2(harddrive.partition[1], 'luksloop', disk_password) as unlocked_device:
		unlocked_device.format('btrfs')
		
		with archinstall.Installer(unlocked_device, boot_partition=harddrive.partition[0], hostname='testmachine') as installation:
			if installation.minimal_installation():
				installation.add_bootloader()

				installation.add_additional_packages(['nano', 'wget', 'git'])
				installation.install_profile('awesome')

				installation.user_create('anton', 'test')
				installation.user_set_pw('root', 'toor')