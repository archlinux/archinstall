import argparse
import json
import urllib.error
import urllib.parse
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from pydantic.dataclasses import dataclass as p_dataclass

from archinstall.lib.mirrors import MirrorConfiguration
from archinstall.lib.models import AudioConfiguration, Bootloader, NetworkConfiguration, User
from archinstall.lib.models.device_model import DiskEncryption, DiskLayoutConfiguration
from archinstall.lib.models.locale import LocaleConfiguration
from archinstall.lib.models.profile_model import ProfileConfiguration
from archinstall.lib.output import error, warn
from archinstall.lib.plugins import load_plugin
from archinstall.lib.storage import storage
from archinstall.lib.translationhandler import Language, translation_handler


@p_dataclass
class Arguments:
	config: Path | None = None
	config_url: str | None = None
	creds: Path | None = None
	creds_url: str | None = None
	silent: bool = False
	dry_run: bool = False
	script: str = 'guided'
	mountpoint: Path = Path('/mnt')
	skip_ntp: bool = False
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
	locale_config: LocaleConfiguration | None = None
	archinstall_language: Language = field(default_factory=lambda: translation_handler.get_language_by_abbr('en'))
	disk_config: DiskLayoutConfiguration | None = None
	profile_config: ProfileConfiguration | None = None
	mirror_config: MirrorConfiguration | None = None
	network_config: NetworkConfiguration | None = None
	bootloader: Bootloader = field(default=Bootloader.get_default())
	uki: bool = False
	audio_config: AudioConfiguration | None = None
	hostname: str = 'archlinux'
	kernels: list[str] = field(default_factory=lambda: ['linux'])
	ntp: bool = False
	packages: list[str] = field(default_factory=list)
	parallel_downloads: int = 0
	swap: bool = True
	timezone: str = 'UTC'
	additional_repositories: list[str] = field(default_factory=list)
	services: list[str] = field(default_factory=list)
	custom_commands: list[str] = field(default_factory=list)

	# Special fields that should be handle with care due to security implications
	users: list[User] = field(default_factory=list)
	disk_encryption: DiskEncryption | None = None
	root_password: str | None = None

	def unsafe_json(self) -> dict[str, Any]:
		config = {
			'!users': [user.json() for user in self.users],
			'!root-password': self.root_password,
		}

		if self.disk_encryption:
			config['encryption_password'] = self.disk_encryption.encryption_password

		return config

	def safe_json(self) -> dict[str, Any]:
		config = {
			'version': self.version,
			'archinstall-language': self.archinstall_language.json(),
			'hostname': self.hostname,
			'kernels': self.kernels,
			'ntp': self.ntp,
			'packages': self.packages,
			'parallel_downloads': self.parallel_downloads,
			'swap': self.swap,
			'timezone': self.timezone,
			'additional-repositories': self.additional_repositories,
			'services': self.services,
			'custom_commands': self.custom_commands,
			'bootloader': self.bootloader.json(),
			'audio_config': self.audio_config.json() if self.audio_config else None,
		}

		if self.locale_config:
			config['locale_config'] = self.locale_config.json()

		if self.disk_config:
			config['disk_config'] = self.disk_config.json()

		if self.disk_encryption:
			config['disk_encryption'] = self.disk_encryption.json()

		if self.profile_config:
			config['profile_config'] = self.profile_config.json()

		if self.mirror_config:
			config['mirror_config'] = self.mirror_config.json()

		if self.network_config:
			config['network_config'] = self.network_config.json()

		return config

	@classmethod
	def from_config(cls, args_config: dict[str, Any]) -> 'ArchConfig':
		arch_config = ArchConfig()

		arch_config.locale_config = LocaleConfiguration.parse_arg(args_config)

		if archinstall_lang := args_config.get('archinstall-language', None):
			arch_config.archinstall_language = translation_handler.get_language_by_name(archinstall_lang)

		if disk_config := args_config.get('disk_config', {}):
			arch_config.disk_config = DiskLayoutConfiguration.parse_arg(disk_config)

		if profile_config := args_config.get('profile_config', None):
			arch_config.profile_config = ProfileConfiguration.parse_arg(profile_config)

		if mirror_config := args_config.get('mirror_config', None):
			arch_config.mirror_config = MirrorConfiguration.parse_args(mirror_config)

		if net_config := args_config.get('network_config', None):
			arch_config.network_config = NetworkConfiguration.parse_arg(net_config)

		users = args_config.get('!users', None)
		superusers = args_config.get('!superusers', None)
		if users is not None or superusers is not None:
			arch_config.users = User.parse_arguments(users, superusers)

		if bootloader_config := args_config.get('bootloader', None):
			arch_config.bootloader = Bootloader.from_arg(bootloader_config)

		if args_config.get('uki') and not arch_config.bootloader.has_uki_support():
			arch_config.uki = False

		if audio_config := args_config.get('audio_config', None):
			arch_config.audio_config = AudioConfiguration.parse_arg(audio_config)

		if args_config.get('disk_encryption', None) is not None and arch_config.disk_config is not None:
			arch_config.disk_encryption = DiskEncryption.parse_arg(
				arch_config.disk_config,
				args_config['disk_encryption'],
				args_config.get('encryption_password', '')
			)

		if hostname := args_config.get('hostname', ''):
			arch_config.hostname = hostname

		if kernels := args_config.get('kernels', []):
			arch_config.kernels = kernels

		if ntp := args_config.get('ntp', False):
			arch_config.ntp = ntp

		if packages := args_config.get('packages', []):
			arch_config.packages = packages

		if parallel_downloads := args_config.get('parallel_downloads', 0):
			arch_config.parallel_downloads = parallel_downloads

		arch_config.swap = args_config.get('swap', True)

		if timezone := args_config.get('timezone', 'UTC'):
			arch_config.timezone = timezone

		if additional_repositories := args_config.get('additional-repositories', []):
			arch_config.additional_repositories = additional_repositories

		if services := args_config.get('services', []):
			arch_config.services = services

		if root_password := args_config.get('!root-password', None):
			arch_config.root_password = root_password

		if custom_commands := args_config.get('custom_commands', []):
			arch_config.custom_commands = custom_commands

		return arch_config


class ArchConfigHandler:
	def __init__(self) -> None:
		self._parser: ArgumentParser = self._define_arguments()
		self._args: Arguments = self._parse_args()

		config = self._parse_config()
		self._config = ArchConfig.from_config(config)

	@property
	def config(self) -> ArchConfig:
		return self._config

	@property
	def args(self) -> Arguments:
		return self._args

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
			"-v",
			"--version",
			action="version",
			default=False,
			version="%(prog)s " + self._get_version()
		)
		parser.add_argument(
			"--config",
			type=Path,
			nargs="?",
			default=None,
			help="JSON configuration file"
		)
		parser.add_argument(
			"--config-url",
			type=str,
			nargs="?",
			default=None,
			help="Url to a JSON configuration file"
		)
		parser.add_argument(
			"--creds",
			type=Path,
			nargs="?",
			default=None,
			help="JSON credentials configuration file"
		)
		parser.add_argument(
			"--creds-url",
			type=str,
			nargs="?",
			default=None,
			help="Url to a JSON credentials configuration file"
		)
		parser.add_argument(
			"--silent",
			action="store_true",
			default=False,
			help="WARNING: Disables all prompts for input and confirmation. If no configuration is provided, this is ignored"
		)
		parser.add_argument(
			"--dry-run",
			"--dry_run",
			action="store_true",
			default=False,
			help="Generates a configuration file and then exits instead of performing an installation"
		)
		parser.add_argument(
			"--script",
			default="guided",
			nargs="?",
			help="Script to run for installation",
			type=str
		)
		parser.add_argument(
			"--mount-point",
			"--mount_point",
			type=Path,
			nargs="?",
			default=Path('/mnt'),
			help="Define an alternate mount point for installation"
		)
		parser.add_argument(
			"--skip-ntp",
			action="store_true",
			help="Disables NTP checks during installation",
			default=False
		)
		parser.add_argument(
			"--debug",
			action="store_true",
			default=False,
			help="Adds debug info into the log"
		)
		parser.add_argument(
			"--offline",
			action="store_true",
			default=False,
			help="Disabled online upstream services such as package search and key-ring auto update."
		)
		parser.add_argument(
			"--no-pkg-lookups",
			action="store_true",
			default=False,
			help="Disabled package validation specifically prior to starting installation."
		)
		parser.add_argument(
			"--plugin",
			nargs="?",
			type=str,
			default=None,
			help='File path to a plugin to load'
		)
		parser.add_argument(
			"--skip-version-check",
			action="store_true",
			default=False,
			help="Skip the version check when running archinstall"
		)
		parser.add_argument(
			"--advanced",
			action="store_true",
			default=False,
			help="Enabled advanced options"
		)
		parser.add_argument(
			"--verbose",
			action="store_true",
			default=False,
			help="Enabled verbose options"
		)

		return parser

	def _parse_args(self) -> Arguments:
		argparse_args = vars(self._parser.parse_args())
		args: Arguments = Arguments(**argparse_args)

		# amend the parameters (check internal consistency)
		# Installation can't be silent if config is not passed
		if args.config is None:
			args.silent = False

		if args.debug:
			warn(f"Warning: --debug mode will write certain credentials to {storage['LOG_PATH']}/{storage['LOG_FILE']}!")

		if args.plugin:
			plugin_path = Path(args.plugin)
			load_plugin(plugin_path)

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
			config.update(json.loads(creds_data))

		config = self._cleanup_config(config)

		return config

	def _fetch_from_url(self, url: str) -> str:
		if urllib.parse.urlparse(url).scheme:
			try:
				req = Request(url, headers={'User-Agent': 'ArchInstall'})
				with urlopen(req) as resp:
					return resp.read()
			except urllib.error.HTTPError as err:
				error(f"Could not fetch JSON from {url}: {err}")
		else:
			error('Not a valid url')

		exit(1)

	def _read_file(self, path: Path) -> str:
		if not path.exists():
			error(f"Could not find file {path}")
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
