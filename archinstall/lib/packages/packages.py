import dataclasses
import json
import ssl
from typing import Dict, Any, Tuple, List
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from ..exceptions import PackageError, SysCallError
from ..models.gen import PackageSearch, PackageSearchResult, LocalPackage
from ..pacman import Pacman

BASE_URL_PKG_SEARCH = 'https://archlinux.org/packages/search/json/'
# BASE_URL_PKG_CONTENT = 'https://archlinux.org/packages/search/json/'
BASE_GROUP_URL = 'https://archlinux.org/groups/search/json/'


def _make_request(url: str, params: Dict) -> Any:
	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode = ssl.CERT_NONE

	encoded = urlencode(params)
	full_url = f'{url}?{encoded}'

	return urlopen(full_url, context=ssl_context)


def group_search(name :str) -> List[PackageSearchResult]:
	# TODO UPSTREAM: Implement /json/ for the groups search
	try:
		response = _make_request(BASE_GROUP_URL, {'name': name})
	except HTTPError as err:
		if err.code == 404:
			return []
		else:
			raise err

	# Just to be sure some code didn't slip through the exception
	data = response.read().decode('utf-8')

	return [PackageSearchResult(**package) for package in json.loads(data)['results']]


def package_search(package :str) -> PackageSearch:
	"""
	Finds a specific package via the package database.
	It makes a simple web-request, which might be a bit slow.
	"""
	# TODO UPSTREAM: Implement bulk search, either support name=X&name=Y or split on space (%20 or ' ')
	# TODO: utilize pacman cache first, upstream second.
	response = _make_request(BASE_URL_PKG_SEARCH, {'name': package})

	if response.code != 200:
		raise PackageError(f"Could not locate package: [{response.code}] {response}")

	data = response.read().decode('UTF-8')
	json_data = json.loads(data)
	return PackageSearch.from_json(json_data)


def find_package(package :str) -> List[PackageSearchResult]:
	data = package_search(package)
	results = []

	for result in data.results:
		if result.pkgname == package:
			results.append(result)

	# If we didn't find the package in the search results,
	# odds are it's a group package
	if not results:
		# Check if the package is actually a group
		for result in group_search(package):
			results.append(result)

	return results


def find_packages(*names :str) -> Dict[str, Any]:
	"""
	This function returns the search results for many packages.
	The function itself is rather slow, so consider not sending to
	many packages to the search query.
	"""
	result = {}
	for package in names:
		for found_package in find_package(package):
			result[package] = found_package

	return result


def validate_package_list(packages :list) -> Tuple[list, list]:
	"""
	Validates a list of given packages.
	return: Tuple of lists containing valid packavges in the first and invalid
	packages in the second entry
	"""
	valid_packages = {package for package in packages if find_package(package)}
	invalid_packages = set(packages) - valid_packages

	return list(valid_packages), list(invalid_packages)


def installed_package(package :str) -> LocalPackage:
	package_info = {}
	try:
		for line in Pacman.run(f"-Q --info {package}"):
			if b':' in line:
				key, value = line.decode().split(':', 1)
				package_info[key.strip().lower().replace(' ', '_')] = value.strip()
	except SysCallError:
		pass

	return LocalPackage({field.name: package_info.get(field.name) for field in dataclasses.fields(LocalPackage)})  # type: ignore
