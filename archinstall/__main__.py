from urllib.parse import urlparse
import archinstall
import sys
import os
import glob
import urllib.request

# TODO: Learn the dark arts of argparse...
#	   (I summon thee dark spawn of cPython)


class ProfileNotFound(BaseException):
	pass


def find_examples():
	"""
	Used to locate the examples, bundled with the module or executable.

	:return: {'guided.py' : './examples/guided.py', '<profile #2>' : '<path #2>'}
	:rtype: dict
	"""
	cwd = os.path.abspath(f'{os.path.dirname(__file__)}')
	examples = f"{cwd}/examples"

	return {os.path.basename(path): path for path in glob.glob(f'{examples}/*.py')}


def find(url):
	parsed_url = urlparse(url)
	if not parsed_url.scheme:
		examples = find_examples()
		if f"{url}.py" in examples:
			return open(examples[f"{url}.py"]).read()
		try:
			return open(url, 'r').read()
		except FileNotFoundError:
			return ProfileNotFound(f"File {url} does not exist")
	elif parsed_url.scheme in ('https', 'http'):
		return urllib.request.urlopen(url).read().decode('utf-8')
	else:
		return ProfileNotFound(f"Cannot handle scheme {parsed_url.scheme}")


def run_as_a_module():
	"""
	Since we're running this as a 'python -m archinstall' module OR
	a nuitka3 compiled version of the project.
	This function and the file __main__ acts as a entry point.
	"""

	if len(sys.argv) == 1:
		sys.argv.append('guided')

	try:
		profile = find(sys.argv[1])
	except ProfileNotFound as err:
		print(f"Couldn't find file: {err}")
		sys.exit(1)

	os.chdir(os.path.abspath(os.path.dirname(__file__)))

	try:
		exec(profile)  # Is this is very safe?
	except Exception as err:
		print(f"Failed to run profile... {err}")
		sys.exit(1)  # Should prompt for another profile path instead

		
if __name__ == '__main__':
	run_as_a_module()
