import urllib.request

from .exceptions import *
from .general import *
from .output import log
from .storage import storage

def filter_mirrors_by_region(regions, destination='/etc/pacman.d/mirrorlist', tmp_dir='/root', *args, **kwargs):
	"""
	This function will change the active mirrors on the live medium by
	filtering which regions are active based on `regions`.

	:param region: A series of country codes separated by `,`. For instance `SE,US` for sweden and United States.
	:type region: str
	"""
	region_list = []
	for region in regions.split(','):
		region_list.append(f'country={region}')
	o = b''.join(sys_command((f"/usr/bin/wget 'https://archlinux.org/mirrorlist/?{'&'.join(region_list)}&protocol=https&ip_version=4&ip_version=6&use_mirror_status=on' -O {tmp_dir}/mirrorlist")))
	o = b''.join(sys_command((f"/usr/bin/sed -i 's/#Server/Server/' {tmp_dir}/mirrorlist")))
	o = b''.join(sys_command((f"/usr/bin/mv {tmp_dir}/mirrorlist {destination}")))
	
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

def use_mirrors(regions :dict, destination='/etc/pacman.d/mirrorlist'):
	log(f'A new package mirror-list has been created: {destination}', level=LOG_LEVELS.Info)
	for region, mirrors in regions.items():
		with open(destination, 'w') as mirrorlist:
			for mirror in mirrors:
				mirrorlist.write(f'## {region}\n')
				mirrorlist.write(f'Server = {mirror}\n')
	return True

def re_rank_mirrors(top=10, *positionals, **kwargs):
	if sys_command((f'/usr/bin/rankmirrors -n {top} /etc/pacman.d/mirrorlist > /etc/pacman.d/mirrorlist')).exit_code == 0:
		return True
	return False

def list_mirrors():
	url = f"https://archlinux.org/mirrorlist/?protocol=https&ip_version=4&ip_version=6&use_mirror_status=on"
	regions = {}

	try:
		response = urllib.request.urlopen(url)
	except urllib.error.URLError as err:
		log(f'Could not fetch an active mirror-list: {err}', level=LOG_LEVELS.Warning, fg="yellow")
		return regions


	region = 'Unknown region'
	for line in response.readlines():
		if len(line.strip()) == 0:
			continue

		line = line.decode('UTF-8').strip('\n').strip('\r')
		if line[:3] == '## ':
			region = line[3:]
		elif line[:10] == '#Server = ':
			regions.setdefault(region, {})

			url = line.lstrip('#Server = ')
			regions[region][url] = True

	return regions