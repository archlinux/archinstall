import logging
import time
from .general import SysCommand, SysCommandWorker, locate_binary
from .installer import Installer
from .output import log
from .storage import storage


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
	def __init__(self, installation: Installer, user=None):
		self.instance = installation
		self.container_name = 'archinstall'
		self.session = None
		self.ready = False
		self.user = user

	def __enter__(self):
		if (existing_session := storage.get('active_boot', None)) and existing_session.instance != self.instance:
			raise KeyError("Archinstall only supports booting up one instance, and a active session is already active and it is not this one.")

		if not self.user:
			if (user := self.instance.cached_credentials.get('root', None)):
				self.user = user # We'll use root
			elif (user := self.instance.cached_credentials.keys()[0]):
				self.user = user # We'll use the first available user
			else:
				raise ValueError(f"archinstall.Boot() requires you to first call either archinstall.user_create(), archinstall.user_set_pw() or specify user=X in Boot() for at least one user before Boot() can be used."
								" This in order to get passed the login prompt when booting up the installed system.")

		if existing_session:
			self.session = existing_session.session
			self.ready = existing_session.ready
		else:
			self.session = SysCommandWorker([
				'/usr/bin/systemd-nspawn',
				'-D', self.instance.target,
				'--timezone=off',
				'-b',
				'--no-pager',
				'--machine', self.container_name
			])
			# '-P' or --console=pipe  could help us not having to do a bunch of os.write() calls, but instead use pipes (stdin, stdout and stderr) as usual.

		if not self.ready:
			while self.session.is_alive():
				if b' login:' in self.session:
					self.session.write(bytes(self.user, 'UTF-8'))
					time.sleep(2)

					if b'Password: ' in self.session:
						if not (password := self.instance.cached_credentials[self.user]):
							raise ValueError(f"No password found for {self.user} when trying to archinstall.Boot() into the system. The attempted boot will hang indefinitely so the installer cannot continue. call archinstall.user_set_pw() on {self.user} before calling archinstall.Boot()")
						
						self.session.write(bytes(password, 'UTF-8'))
						time.sleep(2)

					self.ready = True
					break

		storage['active_boot'] = self
		return self

	def __exit__(self, *args, **kwargs):
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if len(args) >= 2 and args[1]:
			log(args[1], level=logging.ERROR, fg='red')
			log(f"The error above occured in a temporary boot-up of the installation {self.instance}", level=logging.ERROR, fg="red")

		if SysCommand(f'machinectl shell {self.container_name} /bin/bash -c "shutdown now"').exit_code == 0:
			storage['active_boot'] = None

	def __iter__(self):
		if self.session:
			for value in self.session:
				yield value

	def __contains__(self, key: bytes):
		if self.session is None:
			return False

		return key in self.session

	def is_alive(self):
		if self.session is None:
			return False

		return self.session.is_alive()

	def SysCommand(self, cmd: list, *args, **kwargs):
		if cmd[0][0] != '/' and cmd[0][:2] != './':
			# This check is also done in SysCommand & SysCommandWorker.
			# However, that check is done for `machinectl` and not for our chroot command.
			# So this wrapper for SysCommand will do this additionally.

			cmd[0] = locate_binary(cmd[0])

		return SysCommand(["machinectl", "shell", self.container_name, *cmd], *args, **kwargs)

	def SysCommandWorker(self, cmd: list, *args, **kwargs):
		if cmd[0][0] != '/' and cmd[0][:2] != './':
			cmd[0] = locate_binary(cmd[0])

		return SysCommandWorker(["machinectl", "shell", self.container_name, *cmd], *args, **kwargs)
