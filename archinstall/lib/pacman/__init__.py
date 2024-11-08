import time
import re
import typing
import pathlib
import tempfile
import pyalpm
import pydantic
import platform
import traceback
import urllib.parse
import shutil
from typing import TYPE_CHECKING, Any, Callable, Union

from ..general import SysCommand
from ..output import warn, error, info
from .repo import Repo
from .config import Config
from ..exceptions import RequirementError
from ..plugins import plugins

if TYPE_CHECKING:
	_: Any


class PacmanServer(pydantic.BaseModel):
	address :urllib.parse.ParseResult

	def geturl(self):
		return self.address.geturl()


class PacmanTransaction:
	def __init__(self,
		session :pyalpm.Handle,
		cascade=False,
		nodeps=False,
		force=True,
		dbonly=False,
		downloadonly=False,
		nosave=False,
		recurse=False,
		recurseall=False,
		unneeded=False,
		alldeps=False,
		allexplicit=False
	):
		self.cascade = cascade
		self.nodeps = nodeps
		self.force = force
		self.dbonly = dbonly
		self.downloadonly = downloadonly
		self.nosave = nosave
		self.recurse = recurse
		self.recurseall = recurseall
		self.unneeded = unneeded
		self.alldeps = alldeps
		self.allexplicit = allexplicit

		self._session = session
		self._transaction = None

	def __enter__(self):
		try:
			self._transaction = self._session.init_transaction(
				cascade=self.cascade,
				nodeps=self.nodeps,
				force=self.force,
				dbonly=self.dbonly,
				downloadonly=self.downloadonly,
				nosave=self.nosave,
				recurse=self.recurse,
				recurseall=self.recurseall,
				unneeded=self.unneeded,
				alldeps=self.alldeps,
				allexplicit=self.allexplicit
			)
		except pyalpm.error as error:
			message, code, _ = error.args

			if code == 10:
				raise PermissionError(f"Could not lock database {db.name}.db in {self.dbpath}")

			raise error
		return self

	def __exit__(self, exit_type, exit_value, exit_tb) -> None:
		if self._transaction:
			try:
				self._transaction.prepare()
				self._transaction.commit()
			except pyalpm.error as error:
				message, code, _ = error.args

				if code == 28:
					# Transaction was not prepared
					pass
				else:
					traceback.print_exc()
					self._transaction.release()
					return False
			self._transaction.release()
		return True

	def __getattr__(self, key):
		# Transparency function to route calls directly towards
		# self._transaction rather than implementing add_pkg() for instance
		# in this class.
		if self._transaction:
			return getattr(self._transaction, key, None)

		return None


class Pacman:
	def __init__(self,
		config :pathlib.Path = pathlib.Path('/etc/pacman.conf'),
		servers :typing.List[str] | typing.Dict[str, PacmanServer] | None = None,
		dbpath :pathlib.Path | None = None, # pathlib.Path('/var/lib/pacman/')
		cachedir :pathlib.Path | None = None, # pathlib.Path('/var/cache/pacman/pkg')
		hooks :typing.List[pathlib.Path] | None = None,
		repos :typing.List[str] | None = None,
		# hooks = [
		# 	pathlib.Path('/usr/share/libalpm/hooks/'),
		# 	pathlib.Path('/etc/pacman.d/hooks/')
		# ],
		logfile :pathlib.Path | None = None, # pathlib.Path('/var/log/pacman.log'),
		gpgdir :pathlib.Path | None = None, # pathlib.Path('/etc/pacman.d/gnupg/'),
		lock :pathlib.Path | None = None,
		include_config_mirrors :bool = False,
		temporary :bool = False,
		silent :bool = False,
		synced :float | None = None,
		**kwargs
	):
		self.config = config
		self.servers = servers
		self.dbpath = dbpath
		self.cachedir = cachedir
		self.hookdir = hooks
		self.logfile = logfile
		self.gpgdir = gpgdir
		self.lock = lock
		self.repos = repos
		self.temporary = temporary
		self.silent = silent
		self.synced = synced

		self._temporary_pacman_root = None
		self._session = None
		self._source_config_mirrors = True if servers is None or include_config_mirrors is True else False

		self._config = self.load_config()

		if self.repos is None:
			# Get the activated repositories from the config
			self.repos = list(set(self._config.keys()) - {'options'})

		if isinstance(self.servers, list):
			_mapped_to_repos = {

			}

			for repo in self.repos:
				_mapped_to_repos[repo] = [
					PacmanServer(address=urllib.parse.urlparse(server)) for server in self.servers
				]

			self.servers = _mapped_to_repos
		elif self.servers is None:
			self.servers = {
				repo: self._config[repo]
				for repo in self.repos
			}

	def load_config(self):
		"""
		Loads the given pacman.conf (usually /etc/pacman.conf)
		and initiates not-None-values.
		So if you want to use a temporary location make sure
		to specify values first and then load the config to not ovveride them.
		"""

		print(f"Loading pacman configuration {self.config}")

		config = {}
		with self.config.open('r') as fh:
			_section = None
			for line in fh:
				if len(line.strip()) == 0 or line.startswith('#'):
					continue

				if line.startswith('[') and line.endswith(']\n'):
					_section = line[1:-2]
					continue

				config_item = line.strip()
				
				if _section not in config:
					config[_section] = {}

				if _section.lower() == 'options':
					if '=' in config_item:
						# Key = Value pair
						key, value = config_item.split('=', 1)
						key = key.lower()

						config[_section][key] = value
					else:
						config[_section][key] = True

				elif _section.lower() != 'options':
					repo = _section
					if isinstance(config[_section], dict):
						# Only the [options] section is "key: value" pairs
						# the repo sections are only Server= entries.
						config[_section] = []

					if self._source_config_mirrors:
						# if self.servers is None:
						# 	self.servers = {}

						if '=' in config_item:
							key, value = config_item.split('=', 1)
							key = key.strip().lower()
							value = value.strip()

							if key.lower() == 'include':
								value = pathlib.Path(value).expanduser().resolve().absolute()
								if value.exists() is False:
									raise PermissionError(f"Could not open mirror definitions for [{repo}] by including {value}")

								with value.open('r') as mirrors:
									for mirror_line in mirrors:
										if len(mirror_line.strip()) == 0 or mirror_line.startswith('#'):
											continue

										if '=' in mirror_line:
											_, url = mirror_line.split('=', 1)
											url = url.strip()
											url_obj = urllib.parse.urlparse(url)

											config[repo].append(
												PacmanServer(address=url_obj)
											)
		return config

	def __enter__(self) -> 'Pacman':
		"""
		Because transactions in pacman rhymes well with python's context managers.
		We implement transactions via the `with Pacman() as session` context.
		This allows us to do Pacman(temporary=True) for temporary sessions
		or Pacman() to use system-wide operations.
		"""

		# A lot of inspiration is taken from pycman: https://github.com/archlinux/pyalpm/blob/6a0b75dac7151dfa2ea28f368db22ade1775ee2b/pycman/action_sync.py#L184
		if self.temporary:
			with tempfile.TemporaryDirectory(delete=False) as temporary_pacman_root:
				# First we set a bunch of general configurations
				# which load_config() will honor as long as they are not None
				# (Anything we set here = is honored by load_config())
				#
				# These general configs point to our temporary directory
				# to not interferer with the system-wide pacman stuff
				self.rootdir = temporary_pacman_root
				self._temporary_pacman_root = pathlib.Path(temporary_pacman_root)
				self.cachedir = self._temporary_pacman_root / 'cache'
				self.dbpath = self._temporary_pacman_root / 'db'
				self.logfile = self._temporary_pacman_root / 'pacman.log'
				self.cachedir.mkdir(parents=True, exist_ok=True)
				self.dbpath.mkdir(parents=True, exist_ok=True)

				if self.lock is None:
					self.lock = self.dbpath / 'db.lck'

		for key, value in self._config['options'].items():
			if getattr(self, key, None) is None:
				setattr(self, key, value)

		if getattr(self, 'rootdir', None) is None:
			self.rootdir = '/'
		if getattr(self, 'dbpath', None) is None:
			self.dbpath = '/var/lib/pacman/'

		# Session is our libalpm handle with 2 databases
		self._session = pyalpm.Handle(str(self.rootdir), str(self.dbpath))
		for repo in self.repos:
			self._session.register_syncdb(repo, pyalpm.SIG_DATABASE_OPTIONAL)

		self._session.cachedirs = [
			str(self.cachedir)
		]

		if self.temporary:
			self.update()

		return self

	def __exit__(self, exit_type, exit_value, exit_tb) -> None:
		if self.temporary:
			shutil.rmtree(self._temporary_pacman_root.expanduser().resolve().absolute())

		return None

	def update(self):
		# We update our temporary (fresh) database so that
		# we ensure we rely on the latest information
		for db in self._session.get_syncdbs():
			# Set up a transaction with some sane defaults
			with PacmanTransaction(session=self._session) as _transaction:
				# Populate the database with the servers
				# listed in the configuration (we could manually override a list here)
				db.servers = [
					server.geturl().replace('$repo', db.name).replace('$arch', platform.machine())
					for server in self.servers[db.name]
				]

				db.update(force=True)

	def install(self, *packages):
		pyalpm_package_list = []
		missing_packages = []

		for package in packages:
			if not (results := self.search(package, exact=True)):
				missing_packages.append(package)
				continue

			pyalpm_package_list += results
		
		if missing_packages:
			raise ValueError(f"Could not find package(s): {' '.join(missing_packages)}")

		with PacmanTransaction(session=self._session) as _transaction:
			print(f"Installing packages: {pyalpm_package_list}")
			[_transaction.add_pkg(pkg) for pkg in pyalpm_package_list]

	def search(self, *patterns, exact=True):
		results = []
		queries = []

		if exact:
			for pattern in patterns:
				if pattern.startswith('^') is False:
					pattern = "^" + pattern
				if pattern.endswith('$') is False:
					pattern += '$'
				queries.append(pattern)
		else:
			queries = patterns

		for db in self._session.get_syncdbs():
			# print(f"Searching {db.name} for: {' '.join(patterns)}")
			results += db.search(*queries)

		# !! Workaround for https://gitlab.archlinux.org/pacman/pacman/-/issues/204
		# 
		# Since the regex ^<package>$ should make absolute matches
		# but doesn't. This could be because I assume (incorrectly) that
		# `pacman -Ss <name>` should match on `pkgname` and `pkgdescr` in PKGBUILD
		# or because it's a bug.
		# But we can remove the following workaround once that is sorted out:
		if exact:
			results = [
				package
				for package in results
				if package.name in patterns or f"^{package.name}$" in patterns
			]

		return results

	def query(self, *patterns, exact=True):
		results = []
		queries = []

		if exact:
			for pattern in patterns:
				if pattern.startswith('^') is False:
					pattern = "^" + pattern
				if pattern.endswith('$') is False:
					pattern += '$'
				queries.append(pattern)
		else:
			queries = patterns

		db = self._session.get_localdb()
		results += db.search(*queries)

		# !! Workaround for https://gitlab.archlinux.org/pacman/pacman/-/issues/204
		# 
		# Since the regex ^<package>$ should make absolute matches
		# but doesn't. This could be because I assume (incorrectly) that
		# `pacman -Ss <name>` should match on `pkgname` and `pkgdescr` in PKGBUILD
		# or because it's a bug.
		# But we can remove the following workaround once that is sorted out:
		if exact:
			results = [
				package
				for package in results
				if package.name in patterns or f"^{package.name}$" in patterns
			]

		return results

	# These are the old functions, that have been retrofitted
	# to work as before - but with the new pacman logic.
	@staticmethod
	def run(args: str, default_cmd: str = 'pacman') -> SysCommand:
		"""
		A centralized function to call `pacman` from.
		It also protects us from colliding with other running pacman sessions (if used locally).
		The grace period is set to 10 minutes before exiting hard if another pacman instance is running.
		"""
		pacman_db_lock = pathlib.Path('/var/lib/pacman/db.lck')

		if pacman_db_lock.exists():
			warn(_('Pacman is already running, waiting maximum 10 minutes for it to terminate.'))

		started = time.time()
		while pacman_db_lock.exists():
			time.sleep(0.25)

			if time.time() - started > (60 * 10):
				error(_('Pre-existing pacman lock never exited. Please clean up any existing pacman sessions before using archinstall.'))
				exit(1)

		return SysCommand(f'{default_cmd} {args}')

	def ask(self, error_message: str, bail_message: str, func: Callable, *args, **kwargs) -> None:
		while True:
			try:
				func(*args, **kwargs)
				break
			except Exception as err:
				error(f'{error_message}: {err}')
				if not self.silent and input('Would you like to re-try this download? (Y/n): ').lower().strip() in 'y':
					continue
				raise RequirementError(f'{bail_message}: {err}')

	def sync(self) -> None:
		if self.synced:
			return
		self.update()
		self.synced = True

	def strap(self, target, packages: Union[str, list[str]]) -> None:
		self.sync()
		if isinstance(packages, str):
			packages = [packages]

		for plugin in plugins.values():
			if hasattr(plugin, 'on_pacstrap'):
				if (result := plugin.on_pacstrap(packages)):
					packages = result

		info(f'Installing packages: {packages}')

		self.ask(
			'Could not strap in packages',
			'Pacstrap failed. See /var/log/archinstall/install.log or above message for error details',
			SysCommand,
			f'/usr/bin/pacstrap -C /etc/pacman.conf -K {target} {" ".join(packages)} --noconfirm',
			peek_output=True
		)