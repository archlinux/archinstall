from .exceptions import *
from .general import *

def filter_mirrors_by_region(regions, *args, **kwargs):
	"""
	This function will change the active mirrors on the live medium by
	filtering which regions are active based on `regions`.

	:param region: A series of country codes separated by `,`. For instance `SE,US` for sweden and United States.
	:type region: str
	"""
	region_list = []
	for region in regions.split(','):
		region_list.append(f'country={region}')
	o = b''.join(sys_command((f"/usr/bin/wget 'https://www.archlinux.org/mirrorlist/?{'&'.join(region_list)}&protocol=https&ip_version=4&ip_version=6&use_mirror_status=on' -O /root/mirrorlist")))
	o = b''.join(sys_command(("/usr/bin/sed -i 's/#Server/Server/' /root/mirrorlist")))
	o = b''.join(sys_command(("/usr/bin/mv /root/mirrorlist /etc/pacman.d/")))
	
	return True

def add_custom_mirrors(mirrors:list, *args, **kwargs):
	"""
	This will append custom mirror definitions in pacman.conf

	:param mirrors: A list of mirror data according to: `{'url': 'http://url.com', 'signcheck': 'Optional', 'signoptions': 'TrustAll', 'name': 'testmirror'}`
	:type mirrors: dict
	"""
	with open('/etc/pacman.conf', 'a') as pacman:
		for mirror in mirrors:
			pacman.write(f"[{mirror['name']}]\n")
			pacman.write(f"SigLevel = {mirror['signcheck']} {mirror['signoptions']}\n")
			pacman.write(f"Server = {mirror['url']}\n")

	return True

def insert_mirrors(mirrors, *args, **kwargs):
	"""
	This function will insert a given mirror-list at the top of `/etc/pacman.d/mirrorlist`.
	It will not flush any other mirrors, just insert new ones.

	:param mirrors: A dictionary of `{'url' : 'country', 'url2' : 'country'}`
	:type mirrors: dict
	"""
	original_mirrorlist = ''
	with open('/etc/pacman.d/mirrorlist', 'r') as original:
		original_mirrorlist = original.read()

	with open('/etc/pacman.d/mirrorlist', 'w') as new_mirrorlist:
		for mirror, country in mirrors.items():
			new_mirrorlist.write(f'## {country}\n')
			new_mirrorlist.write(f'Server = {mirror}\n')
		new_mirrorlist.write('\n')
		new_mirrorlist.write(original_mirrorlist)

	return True

def re_rank_mirrors(top=10, *positionals, **kwargs):
	if sys_command((f'/usr/bin/rankmirrors -n {top} /etc/pacman.d/mirrorlist > /etc/pacman.d/mirrorlist')).exit_code == 0:
		return True
	return False