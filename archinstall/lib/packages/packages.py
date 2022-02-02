import pathlib
import ssl
import urllib.request
import json
import logging
import glob
from typing import List, Dict, Any
from ..output import log
from ..general import SysCommand
from ..models import PackageSearch, PackageSearchResult
from ..exceptions import PackageError, SysCallError
from ..storage import storage

BASE_URL_PKG_SEARCH = 'https://archlinux.org/packages/search/json/?name={package}'
# BASE_URL_PKG_CONTENT = 'https://archlinux.org/packages/search/json/'
BASE_GROUP_URL = 'https://archlinux.org/groups/x86_64/{group}/'

class VersionDef:
	major = None
	minor = None
	patch = None

	def __init__(self, version_string :str):
		self.version_raw = version_string
		if '.' in version_string:
			self.versions = version_string.split('.')
		else:
			self.versions = [version_string]

		if '-' in self.versions[-1]:
			version, patch_version = self.versions[-1].split('-', 1)
			self.verions = self.versions[:-1] + [version]
			self.patch = patch_version

		self.major = self.versions[0]
		if len(self.versions) >= 2:
			self.minor = self.versions[1]
		if len(self.versions) >= 3:
			self.patch = self.versions[2]

	def __eq__(self, other :'VersionDef') -> bool:
		if other.major == self.major and \
			other.minor == self.minor and \
			other.patch == self.patch:

			return True
		return False
		
	def __lt__(self, other :'VersionDef') -> bool:
		print(f"Comparing {self} against {other}")
		if self.major > other.major:
			return False
		elif self.minor and other.minor and self.minor > other.minor:
			return False
		elif self.patch and other.patch and self.patch > other.patch:
			return False

	def __str__(self) -> str:
		return self.version_raw


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
		if (is_group := find_group(package)):
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

def download_package(package :str, repo :str, url :str, destination :pathlib.Path, filename :str, include_signature=True) -> bool:

	if (url := urllib.parse.urlparse(url)).scheme and url.scheme in ('https', 'http'):
		destination.mkdir(parents=True, exist_ok=True)

		# If it's a repository we haven't configured yet:
		database_path = destination/f"{repo}.db.tar.gz"

		try:
			SysCommand(f"repo-add {database_path} __init__")
		except SysCallError as error:
			if error.exit_code not in (0, 256):
				raise RepositoryError(f"Could not initiate repository {database_path}: [{error.exit_code}] {error}")

		with (destination/filename).open('wb') as output:
			output.write(urllib.request.urlopen(url.geturl()).read())

		if include_signature:
			with (destination/f"{filename}.sig").open('wb') as output:
				output.write(urllib.request.urlopen(f"{url.geturl()}.sig").read())

		return True

	raise PackageError(f"Unknown or unsupported URL scheme when downloading package: {[url.scheme]}")

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

def installed_package(package :str) -> Dict[str, str]:
	package_info = {}
	try:
		for line in SysCommand(f"pacman -Q --info {package}"):
			if b':' in line:
				key, value = line.decode().split(':', 1)
				package_info[key.strip()] = value.strip()
	except SysCallError:
		pass

	print(package_info)

	return package_info