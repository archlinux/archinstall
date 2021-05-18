import logging

from .installer import Installer
from .general import SysCommand
from .output import log

class Ini:
	def __init__(self, *args, **kwargs):
		"""
		Limited INI handler for now.
		Supports multiple keywords through dictionary list items.
		"""
		self.kwargs = kwargs

	def __str__(self):
		result = ''
		first_row_done = False
		for top_level in self.kwargs:
			if first_row_done:
				result += f"\n[{top_level}]\n"
			else:
				result += f"[{top_level}]\n"
				first_row_done = True

			for key, val in self.kwargs[top_level].items():
				if type(val) == list:
					for item in val:
						result += f"{key}={item}\n"
				else:
					result += f"{key}={val}\n"

		return result


class Systemd(Ini):
	"""
	Placeholder class to do systemd specific setups.
	"""


class Networkd(Systemd):
	"""
	Placeholder class to do systemd-network specific setups.
	"""

class Boot:
	def __init__(self, installation :Installer):
		self.instance = installation
		self.session = None

	def __enter__(self):
		self.session = SysCommand([
			'/usr/bin/systemd-nspawn',
			'-D', self.instance.target,
			'-b',
			'--machine', 'temporary'
		])

		return self

	def __exit__(self, *args, **kwargs):
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if len(args) >= 2 and args[1]:
			log(args[1], level=logging.ERROR, fg='red')
			log(f"The error above occured in a temporary boot-up of the installation {installation}", level=logging.ERROR, fg="red")