import ssl
import urllib.request
import json
from typing import Dict, Any
from ..general import SysCommand
from ..models.dataclasses import PackageSearch, PackageSearchResult, LocalPackage
from ..exceptions import PackageError, SysCallError, RequirementError

BASE_URL_PKG_SEARCH = 'https://archlinux.org/packages/search/json/?name={package}'
# BASE_URL_PKG_CONTENT = 'https://archlinux.org/packages/search/json/'
BASE_GROUP_URL = 'https://archlinux.org/groups/x86_64/{group}/'


def find_group(name :str) -> bool:
	# TODO UPSTREAM: Implement /json/ for the groups search
	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode = ssl.CERT_NONE
	try:
		response = urllib.request.urlopen(BASE_GROUP_URL.format(group=name), context=ssl_context)
	except urllib.error.HTTPError as err:
		if err.code == 404:
			return False
		else:
			raise err

	# Just to be sure some code didn't slip through the exception
	if response.code == 200:
		return True

	return False

def package_search(package :str) -> PackageSearch:
	"""
	Finds a specific package via the package database.
	It makes a simple web-request, which might be a bit slow.
	"""
	# TODO UPSTREAM: Implement bulk search, either support name=X&name=Y or split on space (%20 or ' ')
	# TODO: utilize pacman cache first, upstream second.
	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode = ssl.CERT_NONE
	response = urllib.request.urlopen(BASE_URL_PKG_SEARCH.format(package=package), context=ssl_context)

	if response.code != 200:
		raise PackageError(f"Could not locate package: [{response.code}] {response}")

	data = response.read().decode('UTF-8')

	return PackageSearch(**json.loads(data))

class IsGroup(BaseException):
	pass

def find_package(package :str) -> PackageSearchResult:
	data = package_search(package)

	if not data.results:
		# Check if the package is actually a group
		if find_group(package):
			# TODO: Until upstream adds a JSON result for group searches
			# there is no way we're going to parse HTML reliably.
			raise IsGroup("Implement group search")

		raise PackageError(f"Could not locate {package} while looking for repository category")

	# If we didn't find the package in the search results,
	# odds are it's a group package
	for result in data.results:
		if result.pkgname == package:
			return result

	raise PackageError(f"Could not locate {package} in result while looking for repository category")

def find_packages(*names :str) -> Dict[str, Any]:
	"""
	This function returns the search results for many packages.
	The function itself is rather slow, so consider not sending to
	many packages to the search query.
	"""
	return {package: find_package(package) for package in names}


def validate_package_list(packages: list) -> bool:
	"""
	Validates a list of given packages.
	Raises `RequirementError` if one or more packages are not found.
	"""
	invalid_packages = [
		package
		for package in packages
		if not find_package(package)['results'] and not find_group(package)
	]
	if invalid_packages:
		raise RequirementError(f"Invalid package names: {invalid_packages}")

	return True

def installed_package(package :str) -> LocalPackage:
	package_info = {}
	try:
		for line in SysCommand(f"pacman -Q --info {package}"):
			print(line)
			if b':' in line:
				key, value = line.decode().split(':', 1)
				package_info[key.strip().lower().replace(' ', '_')] = value.strip()
	except SysCallError:
		pass
	
	print(package_info)
	return LocalPackage(**package_info)