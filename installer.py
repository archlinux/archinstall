import archinstall, getpass

archinstall.sys_command(f'cryptsetup close /dev/mapper/luksloop')

#selected_hdd = archinstall.select_disk(archinstall.all_disks())
selected_hdd = archinstall.all_disks()['/dev/loop0']
disk_password = '1234' # getpass.getpass(prompt='Disk password (won\'t echo): ')

with archinstall.Filesystem(selected_hdd, archinstall.GPT) as fs:
	fs.use_entire_disk('luks2')
	with archinstall.luks2(fs) as crypt:
		if selected_hdd.partition[1]['size'] == '512M':
			raise OSError('Trying to encrypt the boot partition for petes sake..')

		key_file = crypt.encrypt(selected_hdd.partition[1], password=disk_password, key_size=512, hash_type='sha512', iter_time=10000, key_file='./pwfile')
		crypt.mount(selected_hdd.partition[1], 'luksloop', key_file)
	exit(1)
	with archinstall.installer(root_partition, hostname='testmachine') as installation:
		if installation.minimal_installation():
			installation.add_bootloader()

			installation.add_additional_packages(['nano', 'wget', 'git'])
			installation.install_profile('desktop')

			installation.user_create('anton', 'test')
			installation.user_set_pw('root', 'toor')

			installation.add_AUR_support()