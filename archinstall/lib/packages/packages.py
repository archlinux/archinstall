import json
import ssl
from functools import lru_cache
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.response import addinfourl

from ..exceptions import PackageError, SysCallError
from ..models.packages import AvailablePackage, LocalPackage, PackageSearch, PackageSearchResult, Repository
from ..output import debug
from ..pacman import Pacman

BASE_URL_PKG_SEARCH = 'https://archlinux.org/packages/search/json/'
# BASE_URL_PKG_CONTENT = 'https://archlinux.org/packages/search/json/'
BASE_GROUP_URL = 'https://archlinux.org/groups/search/json/'


def _make_request(url: str, params: dict[str, str]) -> addinfourl:
	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode = ssl.CERT_NONE

	encoded = urlencode(params)
	full_url = f'{url}?{encoded}'

	return urlopen(full_url, context=ssl_context)


def group_search(name: str) -> list[PackageSearchResult]:
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


def package_search(package: str) -> PackageSearch:
	"""
	Finds a specific package via the package database.
	It makes a simple web-request, which might be a bit slow.
	"""
	# TODO UPSTREAM: Implement bulk search, either support name=X&name=Y or split on space (%20 or ' ')
	# TODO: utilize pacman cache first, upstream second.
	response = _make_request(BASE_URL_PKG_SEARCH, {'name': package})

	if response.code != 200:
		raise PackageError(f'Could not locate package: [{response.code}] {response}')

	data = response.read().decode('UTF-8')
	json_data = json.loads(data)
	return PackageSearch.from_json(json_data)


def find_package(package: str) -> list[PackageSearchResult]:
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


def find_packages(*names: str) -> dict[str, PackageSearchResult]:
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


def validate_package_list(packages: list[str]) -> tuple[list[str], list[str]]:
	"""
	Validates a list of given packages.
	return: Tuple of lists containing valid packavges in the first and invalid
	packages in the second entry
	"""
	valid_packages = {package for package in packages if find_package(package)}
	invalid_packages = set(packages) - valid_packages

	return list(valid_packages), list(invalid_packages)


def installed_package(package: str) -> LocalPackage | None:
	try:
		package_info = []
		for line in Pacman.run(f'-Q --info {package}'):
			package_info.append(line.decode().strip())

		return _parse_package_output(package_info, LocalPackage)
	except SysCallError:
		pass

	return None


@lru_cache
def check_package_upgrade(package: str) -> str | None:
	try:
		for line in Pacman.run(f'-Qu {package}'):
			return line.decode().strip()
	except SysCallError:
		debug(f'Failed to check for package upgrades: {package}')

	return None


@lru_cache
def list_available_packages(
	repositories: tuple[Repository, ...],
) -> dict[str, AvailablePackage]:
	"""
	Returns a list of all available packages in the database
	"""
	packages: dict[str, AvailablePackage] = {}
	current_package: list[str] = []
	filtered_repos = [name for repo in repositories for name in repo.get_repository_list()]

	try:
		Pacman.run('-Sy')
	except Exception as e:
		debug(f'Failed to sync Arch Linux package database: {e}')

	for line in Pacman.run('-S --info'):
		dec_line = line.decode().strip()
		current_package.append(dec_line)

		if dec_line.startswith('Validated'):
			if current_package:
				avail_pkg = _parse_package_output(current_package, AvailablePackage)
				if avail_pkg.repository in filtered_repos:
					packages[avail_pkg.name] = avail_pkg
				current_package = []

	return packages


@lru_cache(maxsize=128)
def _normalize_key_name(key: str) -> str:
	return key.strip().lower().replace(' ', '_')


def _parse_package_output[PackageType: (AvailablePackage, LocalPackage)](
	package_meta: list[str],
	cls: type[PackageType],
) -> PackageType:
	package = {}

	for line in package_meta:
		if ':' in line:
			key, value = line.split(':', 1)
			key = _normalize_key_name(key)
			package[key] = value.strip()

	return cls.model_validate(package)
