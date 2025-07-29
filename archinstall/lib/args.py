import argparse
import json
import os
import urllib.error
import urllib.parse
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from pydantic.dataclasses import dataclass as p_dataclass

from archinstall.lib.crypt import decrypt
from archinstall.lib.models.application import ApplicationConfiguration
from archinstall.lib.models.authentication import AuthenticationConfiguration
from archinstall.lib.models.bootloader import Bootloader
from archinstall.lib.models.device import DiskEncryption, DiskLayoutConfiguration
from archinstall.lib.models.locale import LocaleConfiguration
from archinstall.lib.models.mirrors import MirrorConfiguration
from archinstall.lib.models.network import NetworkConfiguration
from archinstall.lib.models.packages import Repository
from archinstall.lib.models.profile import ProfileConfiguration
from archinstall.lib.models.users import Password, User, UserSerialization
from archinstall.lib.output import debug, error, logger, warn
from archinstall.lib.plugins import load_plugin
from archinstall.lib.translationhandler import Language, tr, translation_handler
from archinstall.lib.utils.util import get_password
from archinstall.tui.curses_menu import Tui


@p_dataclass
class Arguments:
	config: Path | None = None
	config_url: str | None = None
	creds: Path | None = None
	creds_url: str | None = None
	creds_decryption_key: str | None = None
	silent: bool = False
	dry_run: bool = False
	script: str | None = None
	mountpoint: Path = Path('/mnt')
	skip_ntp: bool = False
	skip_wkd: bool = False
	skip_boot: bool = False
	debug: bool = False
	offline: bool = False
	no_pkg_lookups: bool = False
	plugin: str | None = None
	skip_version_check: bool = False
	advanced: bool = False
	verbose: bool = False


@dataclass
class ArchConfig:
	version: str | None = None
	script: str | None = None
	locale_config: LocaleConfiguration | None = None
	archinstall_language: Language = field(default_factory=lambda: translation_handler.get_language_by_abbr('en'))
	disk_config: DiskLayoutConfiguration | None = None
	profile_config: ProfileConfiguration | None = None
	mirror_config: MirrorConfiguration | None = None
	network_config: NetworkConfiguration | None = None
	bootloader: Bootloader | None = None
	uki: bool = False
	app_config: ApplicationConfiguration | None = None
	auth_config: AuthenticationConfiguration | None = None
	hostname: str = 'archlinux'
	kernels: list[str] = field(default_factory=lambda: ['linux'])
	ntp: bool = True
	packages: list[str] = field(default_factory=list)
	parallel_downloads: int = 0
	swap: bool = True
	timezone: str = 'UTC'
	services: list[str] = field(default_factory=list)
	custom_commands: list[str] = field(default_factory=list)

	def unsafe_json(self) -> dict[str, Any]:
		config: dict[str, list[UserSerialization] | str | None] = {}

		if self.auth_config:
			if self.auth_config.users:
				config['users'] = [user.json() for user in self.auth_config.users]

			if self.auth_config.root_enc_password:
				config['root_enc_password'] = self.auth_config.root_enc_password.enc_password

		if self.disk_config:
			disk_encryption = self.disk_config.disk_encryption
			if disk_encryption and disk_encryption.encryption_password:
				config['encryption_password'] = disk_encryption.encryption_password.plaintext

		return config

	def safe_json(self) -> dict[str, Any]:
		config: Any = {
			'version': self.version,
			'script': self.script,
			'archinstall-language': self.archinstall_language.json(),
			'hostname': self.hostname,
			'kernels': self.kernels,
			'ntp': self.ntp,
			'packages': self.packages,
			'parallel_downloads': self.parallel_downloads,
			'swap': self.swap,
			'timezone': self.timezone,
			'services': self.services,
			'custom_commands': self.custom_commands,
			'bootloader': self.bootloader.json() if self.bootloader else None,
			'app_config': self.app_config.json() if self.app_config else None,
			'auth_config': self.auth_config.json() if self.auth_config else None,
		}

		if self.locale_config:
			config['locale_config'] = self.locale_config.json()

		if self.disk_config:
			config['disk_config'] = self.disk_config.json()

		if self.profile_config:
			config['profile_config'] = self.profile_config.json()

		if self.mirror_config:
			config['mirror_config'] = self.mirror_config.json()

		if self.network_config:
			config['network_config'] = self.network_config.json()

		return config

	@classmethod
	def from_config(cls, args_config: dict[str, Any], args: Arguments) -> 'ArchConfig':
		arch_config = ArchConfig()

		arch_config.locale_config = LocaleConfiguration.parse_arg(args_config)

		if script := args_config.get('script', None):
			arch_config.script = script

		if archinstall_lang := args_config.get('archinstall-language', None):
			arch_config.archinstall_language = translation_handler.get_language_by_name(archinstall_lang)

		if disk_config := args_config.get('disk_config', {}):
			enc_password = args_config.get('encryption_password', '')
			password = Password(plaintext=enc_password) if enc_password else None
			arch_config.disk_config = DiskLayoutConfiguration.parse_arg(disk_config, password)

			# DEPRECATED
			# backwards compatibility for main level disk_encryption entry
			disk_encryption: DiskEncryption | None = None

			if args_config.get('disk_encryption', None) is not None and arch_config.disk_config is not None:
				disk_encryption = DiskEncryption.parse_arg(
					arch_config.disk_config,
					args_config['disk_encryption'],
					Password(plaintext=args_config.get('encryption_password', '')),
				)

				if disk_encryption:
					arch_config.disk_config.disk_encryption = disk_encryption

		if profile_config := args_config.get('profile_config', None):
			arch_config.profile_config = ProfileConfiguration.parse_arg(profile_config)

		if mirror_config := args_config.get('mirror_config', None):
			backwards_compatible_repo = []
			if additional_repositories := args_config.get('additional-repositories', []):
				backwards_compatible_repo = [Repository(r) for r in additional_repositories]

			arch_config.mirror_config = MirrorConfiguration.parse_args(
				mirror_config,
				backwards_compatible_repo,
			)

		if net_config := args_config.get('network_config', None):
			arch_config.network_config = NetworkConfiguration.parse_arg(net_config)

		if bootloader_config := args_config.get('bootloader', None):
			arch_config.bootloader = Bootloader.from_arg(bootloader_config, args.skip_boot)

		if args_config.get('uki') and (arch_config.bootloader is None or not arch_config.bootloader.has_uki_support()):
			arch_config.uki = False

		# deprecated: backwards compatibility
		audio_config_args = args_config.get('audio_config', None)
		app_config_args = args_config.get('app_config', None)

		if audio_config_args is not None or app_config_args is not None:
			arch_config.app_config = ApplicationConfiguration.parse_arg(app_config_args, audio_config_args)

		if auth_config_args := args_config.get('auth_config', None):
			arch_config.auth_config = AuthenticationConfiguration.parse_arg(auth_config_args)

		if hostname := args_config.get('hostname', ''):
			arch_config.hostname = hostname

		if kernels := args_config.get('kernels', []):
			arch_config.kernels = kernels

		arch_config.ntp = args_config.get('ntp', True)

		if packages := args_config.get('packages', []):
			arch_config.packages = packages

		if parallel_downloads := args_config.get('parallel_downloads', 0):
			arch_config.parallel_downloads = parallel_downloads

		arch_config.swap = args_config.get('swap', True)

		if timezone := args_config.get('timezone', 'UTC'):
			arch_config.timezone = timezone

		if services := args_config.get('services', []):
			arch_config.services = services

		# DEPRECATED: backwards compatibility
		root_password = None
		if root_password := args_config.get('!root-password', None):
			root_password = Password(plaintext=root_password)

		if enc_password := args_config.get('root_enc_password', None):
			root_password = Password(enc_password=enc_password)

		if root_password is not None:
			if arch_config.auth_config is None:
				arch_config.auth_config = AuthenticationConfiguration()
			arch_config.auth_config.root_enc_password = root_password

		# DEPRECATED: backwards copatibility
		users: list[User] = []
		if args_users := args_config.get('!users', None):
			users = User.parse_arguments(args_users)

		if args_users := args_config.get('users', None):
			users = User.parse_arguments(args_users)

		if users:
			if arch_config.auth_config is None:
				arch_config.auth_config = AuthenticationConfiguration()
			arch_config.auth_config.users = users

		if custom_commands := args_config.get('custom_commands', []):
			arch_config.custom_commands = custom_commands

		return arch_config


class ArchConfigHandler:
	def __init__(self) -> None:
		self._parser: ArgumentParser = self._define_arguments()
		args: Arguments = self._parse_args()
		self._args = args

		config = self._parse_config()

		try:
			self._config = ArchConfig.from_config(config, args)
			self._config.version = self._get_version()
		except ValueError as err:
			warn(str(err))
			exit(1)

	@property
	def config(self) -> ArchConfig:
		return self._config

	@property
	def args(self) -> Arguments:
		return self._args

	def get_script(self) -> str:
		if script := self.args.script:
			return script

		if script := self.config.script:
			return script

		return 'guided'

	def print_help(self) -> None:
		self._parser.print_help()

	def _get_version(self) -> str:
		try:
			return version('archinstall')
		except Exception:
			return 'Archinstall version not found'

	def _define_arguments(self) -> ArgumentParser:
		parser = ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
		parser.add_argument(
			'-v',
			'--version',
			action='version',
			default=False,
			version='%(prog)s ' + self._get_version(),
		)
		parser.add_argument(
			'--config',
			type=Path,
			nargs='?',
			default=None,
			help='JSON configuration file',
		)
		parser.add_argument(
			'--config-url',
			type=str,
			nargs='?',
			default=None,
			help='Url to a JSON configuration file',
		)
		parser.add_argument(
			'--creds',
			type=Path,
			nargs='?',
			default=None,
			help='JSON credentials configuration file',
		)
		parser.add_argument(
			'--creds-url',
			type=str,
			nargs='?',
			default=None,
			help='Url to a JSON credentials configuration file',
		)
		parser.add_argument(
			'--creds-decryption-key',
			type=str,
			nargs='?',
			default=None,
			help='Decryption key for credentials file',
		)
		parser.add_argument(
			'--silent',
			action='store_true',
			default=False,
			help='WARNING: Disables all prompts for input and confirmation. If no configuration is provided, this is ignored',
		)
		parser.add_argument(
			'--dry-run',
			'--dry_run',
			action='store_true',
			default=False,
			help='Generates a configuration file and then exits instead of performing an installation',
		)
		parser.add_argument(
			'--script',
			nargs='?',
			help='Script to run for installation',
			type=str,
		)
		parser.add_argument(
			'--mountpoint',
			type=Path,
			nargs='?',
			default=Path('/mnt'),
			help='Define an alternate mount point for installation',
		)
		parser.add_argument(
			'--skip-ntp',
			action='store_true',
			help='Disables NTP checks during installation',
			default=False,
		)
		parser.add_argument(
			'--skip-wkd',
			action='store_true',
			help='Disables checking if archlinux keyring wkd sync is complete.',
			default=False,
		)
		parser.add_argument(
			'--skip-boot',
			action='store_true',
			help='Disables installation of a boot loader (note: only use this when problems arise with the boot loader step).',
			default=False,
		)
		parser.add_argument(
			'--debug',
			action='store_true',
			default=False,
			help='Adds debug info into the log',
		)
		parser.add_argument(
			'--offline',
			action='store_true',
			default=False,
			help='Disabled online upstream services such as package search and key-ring auto update.',
		)
		parser.add_argument(
			'--no-pkg-lookups',
			action='store_true',
			default=False,
			help='Disabled package validation specifically prior to starting installation.',
		)
		parser.add_argument(
			'--plugin',
			nargs='?',
			type=str,
			default=None,
			help='File path to a plugin to load',
		)
		parser.add_argument(
			'--skip-version-check',
			action='store_true',
			default=False,
			help='Skip the version check when running archinstall',
		)
		parser.add_argument(
			'--advanced',
			action='store_true',
			default=False,
			help='Enabled advanced options',
		)
		parser.add_argument(
			'--verbose',
			action='store_true',
			default=False,
			help='Enabled verbose options',
		)

		return parser

	def _parse_args(self) -> Arguments:
		argparse_args = vars(self._parser.parse_args())
		args: Arguments = Arguments(**argparse_args)

		# amend the parameters (check internal consistency)
		# Installation can't be silent if config is not passed
		if args.config is None and args.config_url is None:
			args.silent = False

		if args.debug:
			warn(f'Warning: --debug mode will write certain credentials to {logger.path}!')

		if args.plugin:
			plugin_path = Path(args.plugin)
			load_plugin(plugin_path)

		if args.creds_decryption_key is None:
			if os.environ.get('ARCHINSTALL_CREDS_DECRYPTION_KEY'):
				args.creds_decryption_key = os.environ.get('ARCHINSTALL_CREDS_DECRYPTION_KEY')

		return args

	def _parse_config(self) -> dict[str, Any]:
		config: dict[str, Any] = {}
		config_data: str | None = None
		creds_data: str | None = None

		if self._args.config is not None:
			config_data = self._read_file(self._args.config)
		elif self._args.config_url is not None:
			config_data = self._fetch_from_url(self._args.config_url)

		if config_data is not None:
			config.update(json.loads(config_data))

		if self._args.creds is not None:
			creds_data = self._read_file(self._args.creds)
		elif self._args.creds_url is not None:
			creds_data = self._fetch_from_url(self._args.creds_url)

		if creds_data is not None:
			json_data = self._process_creds_data(creds_data)
			if json_data is not None:
				config.update(json_data)

		config = self._cleanup_config(config)

		return config

	def _process_creds_data(self, creds_data: str) -> dict[str, Any] | None:
		if creds_data.startswith('$'):  # encrypted data
			if self._args.creds_decryption_key is not None:
				try:
					creds_data = decrypt(creds_data, self._args.creds_decryption_key)
					return json.loads(creds_data)
				except ValueError as err:
					if 'Invalid password' in str(err):
						error(tr('Incorrect credentials file decryption password'))
						exit(1)
					else:
						debug(f'Error decrypting credentials file: {err}')
						raise err from err
			else:
				incorrect_password = False

				with Tui():
					while True:
						header = tr('Incorrect password') if incorrect_password else None

						decryption_pwd = get_password(
							text=tr('Credentials file decryption password'),
							header=header,
							allow_skip=False,
							skip_confirmation=True,
						)

						if not decryption_pwd:
							return None

						try:
							creds_data = decrypt(creds_data, decryption_pwd.plaintext)
							break
						except ValueError as err:
							if 'Invalid password' in str(err):
								debug('Incorrect credentials file decryption password')
								incorrect_password = True
							else:
								debug(f'Error decrypting credentials file: {err}')
								raise err from err

		return json.loads(creds_data)

	def _fetch_from_url(self, url: str) -> str:
		if urllib.parse.urlparse(url).scheme:
			try:
				req = Request(url, headers={'User-Agent': 'ArchInstall'})
				with urlopen(req) as resp:
					return resp.read().decode('utf-8')
			except urllib.error.HTTPError as err:
				error(f'Could not fetch JSON from {url}: {err}')
		else:
			error('Not a valid url')

		exit(1)

	def _read_file(self, path: Path) -> str:
		if not path.exists():
			error(f'Could not find file {path}')
			exit(1)

		return path.read_text()

	def _cleanup_config(self, config: Namespace | dict[str, Any]) -> dict[str, Any]:
		clean_args = {}
		for key, val in config.items():
			if isinstance(val, dict):
				val = self._cleanup_config(val)

			if val is not None:
				clean_args[key] = val

		return clean_args


arch_config_handler: ArchConfigHandler = ArchConfigHandler()
