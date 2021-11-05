import logging
import urllib.error
import urllib.request
from typing import Union, Mapping, Iterable

from .general import SysCommand
from .output import log

def sort_mirrorlist(raw_data :bytes, sort_order=["https", "http"]) -> bytes:
	"""
	This function can sort /etc/pacman.d/mirrorlist according to the
	mirror's URL prefix. By default places HTTPS before HTTP but it also
	preserves the country/rank-order.

	This assumes /etc/pacman.d/mirrorlist looks like the following:

	## Comment
	Server = url

	or

	## Comment
	#Server = url

	But the Comments need to start with double-hashmarks to be distringuished
	from server url definitions (commented or uncommented).
	"""
	comments_and_whitespaces = b""

	categories = {key: [] for key in sort_order + ["Unknown"]}
	for line in raw_data.split(b"\n"):
		if line[0:2] in (b'##', b''):
			comments_and_whitespaces += line + b'\n'
		elif line[:6].lower() == b'server' or line[:7].lower() == b'#server':
			opening, url = line.split(b'=', 1)
			opening, url = opening.strip(), url.strip()
			if (category := url.split(b'://',1)[0].decode('UTF-8')) in categories:
				categories[category].append(comments_and_whitespaces)
				categories[category].append(opening + b' = ' + url + b'\n')
			else:
				categories["Unknown"].append(comments_and_whitespaces)
				categories["Unknown"].append(opening + b' = ' + url + b'\n')

			comments_and_whitespaces = b""

	new_raw_data = b''
	for category in sort_order + ["Unknown"]:
		for line in categories[category]:
			new_raw_data += line

	return new_raw_data


def filter_mirrors_by_region(regions, destination='/etc/pacman.d/mirrorlist', sort_order=["https", "http"], *args, **kwargs) -> Union[bool, bytes]:
	"""
	This function will change the active mirrors on the live medium by
	filtering which regions are active based on `regions`.

	:param regions: A series of country codes separated by `,`. For instance `SE,US` for sweden and United States.
	:type regions: str
	"""
	region_list = [f'country={region}' for region in regions.split(',')]
	response = urllib.request.urlopen(urllib.request.Request(f"https://archlinux.org/mirrorlist/?{'&'.join(region_list)}&protocol=https&protocol=http&ip_version=4&ip_version=6&use_mirror_status=on'", headers={'User-Agent': 'ArchInstall'}))
	new_list = response.read().replace(b"#Server", b"Server")

	if sort_order:
		new_list = sort_mirrorlist(new_list, sort_order=sort_order)

	if destination:
		with open(destination, "wb") as mirrorlist:
			mirrorlist.write(new_list)

		return True
	else:
		return new_list.decode('UTF-8')


def add_custom_mirrors(mirrors: list, *args, **kwargs):
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


def use_mirrors(
	regions: Mapping[str, Iterable[str]],
	destination: str = '/etc/pacman.d/mirrorlist'
) -> None:
	log(f'A new package mirror-list has been created: {destination}', level=logging.INFO)
	with open(destination, 'w') as mirrorlist:
		for region, mirrors in regions.items():
			for mirror in mirrors:
				mirrorlist.write(f'## {region}\n')
				mirrorlist.write(f'Server = {mirror}\n')


def re_rank_mirrors(
	top: int = 10,
	src: str = '/etc/pacman.d/mirrorlist',
	dst: str = '/etc/pacman.d/mirrorlist',
) -> bool:
	cmd = SysCommand(f"/usr/bin/rankmirrors -n {top} {src}")
	if cmd.exit_code != 0:
		return False
	with open(dst, 'w') as f:
		f.write(str(cmd))
	return True


def list_mirrors(sort_order=["https", "http"]):
	url = "https://archlinux.org/mirrorlist/?protocol=https&protocol=http&ip_version=4&ip_version=6&use_mirror_status=on"
	regions = {}

	try:
		response = urllib.request.urlopen(url)
	except urllib.error.URLError as err:
		log(f'Could not fetch an active mirror-list: {err}', level=logging.WARNING, fg="yellow")
		return regions

	mirrorlist = response.read()
	if sort_order:
		mirrorlist = sort_mirrorlist(mirrorlist, sort_order=sort_order)

	region = 'Unknown region'
	for line in mirrorlist.split(b'\n'):
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
