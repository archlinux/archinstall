import urllib.request, urllib.parse
import ssl, json

BASE_URL = 'https://www.archlinux.org/packages/search/json/?name={package}'

def find_package(name):
	"""
	Finds a specific package via the package database.
	It makes a simple web-request, which might be a bit slow.
	"""
	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode=ssl.CERT_NONE
	response = urllib.request.urlopen(BASE_URL.format(package=name), context=ssl_context)
	data = response.read().decode('UTF-8')
	return json.loads(data)

def find_packages(*names):
	"""
	This function returns the search results for many packages.
	The function itself is rather slow, so consider not sending to
	many packages to the search query.
	"""
	result = {}
	for package in names:
		result[package] = find_package(package)
	return result