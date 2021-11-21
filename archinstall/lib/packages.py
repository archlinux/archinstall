import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

from .exceptions import RequirementError

BASE_URL = 'https://archlinux.org/packages/search/json/?name={package}'
BASE_GROUP_URL = 'https://archlinux.org/groups/x86_64/{group}/'


def find_group(name):
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


def find_package(name):
	"""
	Finds a specific package via the package database.
	It makes a simple web-request, which might be a bit slow.
	"""
	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode = ssl.CERT_NONE
	response = urllib.request.urlopen(BASE_URL.format(package=name), context=ssl_context)
	data = response.read().decode('UTF-8')
	return json.loads(data)


def find_packages(*names):
	"""
	This function returns the search results for many packages.
	The function itself is rather slow, so consider not sending to
	many packages to the search query.
	"""
	return {package: find_package(package) for package in names}


def validate_package_list(packages: list):
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
