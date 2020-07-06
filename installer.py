import archinstall, getpass

## dd if=/dev/zero of=test.img bs=1G count=4
## losetup -fP test.img
archinstall.sys_command(f'umount -R /mnt', surpress_errors=True)
archinstall.sys_command(f'cryptsetup close /dev/mapper/luksloop', surpress_errors=True)

#harddrive = archinstall.select_disk(archinstall.all_disks())
harddrive = archinstall.all_disks()['/dev/loop0']
disk_password = '1234' # getpass.getpass(prompt='Disk password (won\'t echo): ')

with archinstall.Filesystem(harddrive, archinstall.GPT) as fs:
	fs.use_entire_disk('luks2')
	with archinstall.luks2(fs) as crypt:
		if harddrive.partition[1].size == '512M':
			raise OSError('Trying to encrypt the boot partition for petes sake..')

		key_file = crypt.encrypt(harddrive.partition[1], password=disk_password, key_size=512, hash_type='sha512', iter_time=10000, key_file='./pwfile')

		unlocked_device = crypt.unlock(harddrive.partition[1], 'luksloop', key_file)
		
		harddrive.partition[0].format('fat32')
		unlocked_device.format('btrfs')
		
		with archinstall.Installer(unlocked_device, hostname='testmachine') as installation:
			if installation.minimal_installation():
				installation.add_bootloader(harddrive.partition[0])

				installation.add_additional_packages(['nano', 'wget', 'git'])
				installation.install_profile('desktop')

				installation.user_create('anton', 'test')
				installation.user_set_pw('root', 'toor')

				installation.add_AUR_support()