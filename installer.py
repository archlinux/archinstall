import archinstall, getpass

selected_hdd = archinstall.select_disk(archinstall.all_disks())
disk_password = getpass.getpass(prompt='Disk password (won\'t echo): ')

with archinstall.Formatter(selected_hdd, archinstall.GPT) as formatter:
	exit(1)
	disk.encrypt('luks2', password=disk_password, key_size=512, hash_type='sha512', iter_time=10000, key_file='./pwfile')

	root_partition = disk.partition['/']

with archinstall.installer(root_partition, hostname='testmachine') as installation:
	if installation.minimal_installation():
		installation.add_bootloader()

		installation.add_additional_packages(['nano', 'wget', 'git'])
		installation.install_profile('desktop')

		installation.user_create('anton', 'test')
		installation.user_set_pw('root', 'toor')

		installation.add_AUR_support()