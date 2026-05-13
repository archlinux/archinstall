import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Self
from urllib.request import Request, urlopen

from pydantic.dataclasses import dataclass as p_dataclass

from archinstall.lib.crypt import decrypt
from archinstall.lib.menu.util import get_password
from archinstall.lib.models.application import ApplicationConfiguration, ZramConfiguration
from archinstall.lib.models.authentication import AuthenticationConfiguration
from archinstall.lib.models.bootloader import Bootloader, BootloaderConfiguration
from archinstall.lib.models.config import SubConfig
from archinstall.lib.models.device import DiskEncryption, DiskLayoutConfiguration
from archinstall.lib.models.locale import LocaleConfiguration
from archinstall.lib.models.mirrors import MirrorConfiguration
from archinstall.lib.models.network import NetworkConfiguration
from archinstall.lib.models.package_types import DEFAULT_KERNEL
from archinstall.lib.models.packages import Repository
from archinstall.lib.models.pacman import PacmanConfiguration
from archinstall.lib.models.profile import ProfileConfiguration
from archinstall.lib.models.users import Password, User, UserSerialization
from archinstall.lib.output import debug, error, logger, warn
from archinstall.lib.plugins import load_plugin
from archinstall.lib.translationhandler import Language, tr, translation_handler
from archinstall.lib.version import get_version
from archinstall.tui.components import tui


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
    skip_wifi_check: bool = False
    advanced: bool = False
    verbose: bool = False


class ArchConfigType(StrEnum):
	VERSION = 'version'
	SCRIPT = 'script'
	LOCALE_CONFIG = 'locale_config'
	ARCHINSTALL_LANGUAGE = 'archinstall_language'
	DISK_CONFIG = 'disk_config'
	PROFILE_CONFIG = 'profile_config'
	MIRROR_CONFIG = 'mirror_config'
	NETWORK_CONFIG = 'network_config'
	BOOTLOADER_CONFIG = 'bootloader_config'
	APP_CONFIG = 'app_config'
	AUTH_CONFIG = 'auth_config'
	SWAP = 'swap'
	USERS = 'users'
	ROOT_ENC_PASSWORD = 'root_enc_password'
	ENCRYPTION_PASSWORD = 'encryption_password'
	HOSTNAME = 'hostname'
	KERNELS = 'kernels'
	NTP = 'ntp'
	TIMEZONE = 'timezone'
	SERVICES = 'services'
	PACKAGES = 'packages'
	PACMAN_CONFIG = 'pacman_config'
	CUSTOM_COMMANDS = 'custom_commands'

	def text(self) -> str:
		match self:
			case ArchConfigType.ARCHINSTALL_LANGUAGE:
				return tr('ArchInstall Language')
			case ArchConfigType.VERSION:
				return tr('Version')
			case ArchConfigType.SCRIPT:
				return tr('Installation Script')
			case ArchConfigType.LOCALE_CONFIG:
				return tr('Locales')
			case ArchConfigType.DISK_CONFIG:
				return tr('Disk configuration')
			case ArchConfigType.PROFILE_CONFIG:
				return tr('Profile')
			case ArchConfigType.MIRROR_CONFIG:
				return tr('Mirrors and repositories')
			case ArchConfigType.NETWORK_CONFIG:
				return tr('Network')
			case ArchConfigType.BOOTLOADER_CONFIG:
				return tr('Bootloader')
			case ArchConfigType.APP_CONFIG:
				return tr('Application')
			case ArchConfigType.AUTH_CONFIG:
				return tr('Authentication')
			case ArchConfigType.SWAP:
				return tr('Swap')
			case ArchConfigType.HOSTNAME:
				return tr('Hostname')
			case ArchConfigType.KERNELS:
				return tr('Kernels')
			case ArchConfigType.NTP:
				return tr('Automatic time sync (NTP)')
			case ArchConfigType.TIMEZONE:
				return tr('Timezone')
			case ArchConfigType.SERVICES:
				return tr('Services')
			case ArchConfigType.PACKAGES:
				return tr('Additional packages')
			case ArchConfigType.PACMAN_CONFIG:
				return tr('Pacman')
			case ArchConfigType.CUSTOM_COMMANDS:
				return tr('Custom commands')
			case ArchConfigType.USERS:
				return tr('Users')
			case ArchConfigType.ROOT_ENC_PASSWORD:
				return tr('Root encrypted password')
			case ArchConfigType.ENCRYPTION_PASSWORD:
				return tr('Disk encryption password')


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
	bootloader_config: BootloaderConfiguration | None = None
	app_config: ApplicationConfiguration | None = None
	auth_config: AuthenticationConfiguration | None = None
	swap: ZramConfiguration | None = None
	hostname: str = 'archlinux'
	kernels: list[str] = field(default_factory=lambda: [DEFAULT_KERNEL.value])
	ntp: bool = True
	packages: list[str] = field(default_factory=list)
	pacman_config: PacmanConfiguration = field(default_factory=PacmanConfiguration.default)
	timezone: str = 'UTC'
	services: list[str] = field(default_factory=list)
	custom_commands: list[str] = field(default_factory=list)

	def unsafe_config(self) -> dict[ArchConfigType, Any]:
		config: dict[ArchConfigType, list[UserSerialization] | str | None] = {}

		if self.auth_config:
			if self.auth_config.users:
				config[ArchConfigType.USERS] = [user.json() for user in self.auth_config.users]

			if self.auth_config.root_enc_password:
				config[ArchConfigType.ROOT_ENC_PASSWORD] = self.auth_config.root_enc_password.enc_password

		if self.disk_config:
			disk_encryption = self.disk_config.disk_encryption
			if disk_encryption and disk_encryption.encryption_password:
				config[ArchConfigType.ENCRYPTION_PASSWORD] = disk_encryption.encryption_password.plaintext

		return config

	def safe_config(self) -> dict[ArchConfigType, Any]:
		base_config: dict[ArchConfigType, Any] = {
			ArchConfigType.VERSION: self.version,
			ArchConfigType.SCRIPT: self.script,
			ArchConfigType.ARCHINSTALL_LANGUAGE: self.archinstall_language.json(),
		}

		base_config.update(self.plain_cfg())
		sub_config = self.sub_cfg()

		for config_type, value in sub_config.items():
			if not hasattr(value, 'json'):
				raise ValueError(f'Config value for {config_type} must implement json() method')
			base_config[config_type] = value.json()

		return base_config

	def plain_cfg(self) -> dict[ArchConfigType, str | list[str] | bool]:
		return {
			ArchConfigType.HOSTNAME: self.hostname,
			ArchConfigType.KERNELS: self.kernels,
			ArchConfigType.NTP: self.ntp,
			ArchConfigType.TIMEZONE: self.timezone,
			ArchConfigType.SERVICES: self.services,
			ArchConfigType.PACKAGES: self.packages,
			ArchConfigType.CUSTOM_COMMANDS: self.custom_commands,
		}

	def sub_cfg(self) -> dict[ArchConfigType, SubConfig]:
		cfg: dict[ArchConfigType, SubConfig] = {
			ArchConfigType.PACMAN_CONFIG: self.pacman_config,
		}

		if self.mirror_config:
			cfg[ArchConfigType.MIRROR_CONFIG] = self.mirror_config

		if self.bootloader_config:
			cfg[ArchConfigType.BOOTLOADER_CONFIG] = self.bootloader_config

		if self.disk_config:
			cfg[ArchConfigType.DISK_CONFIG] = self.disk_config

		if self.swap:
			cfg[ArchConfigType.SWAP] = self.swap

		if self.auth_config:
			cfg[ArchConfigType.AUTH_CONFIG] = self.auth_config

		if self.locale_config:
			cfg[ArchConfigType.LOCALE_CONFIG] = self.locale_config

		if self.profile_config:
			cfg[ArchConfigType.PROFILE_CONFIG] = self.profile_config

		if self.network_config:
			cfg[ArchConfigType.NETWORK_CONFIG] = self.network_config

		if self.app_config:
			cfg[ArchConfigType.APP_CONFIG] = self.app_config

		return cfg

	@classmethod
	def from_config(cls, args_config: dict[str, Any], args: Arguments) -> Self:
		arch_config = cls()

		arch_config.locale_config = LocaleConfiguration.parse_arg(args_config)

		if script := args_config.get('script', None):
			arch_config.script = script

		if archinstall_lang := args_config.get('archinstall-language', None):
			arch_config.archinstall_language = translation_handler.get_language_by_name(archinstall_lang)
			translation_handler.activate(arch_config.archinstall_language, set_font=False)

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

        if bootloader_config_dict := args_config.get('bootloader_config', None):
            arch_config.bootloader_config = BootloaderConfiguration.parse_arg(bootloader_config_dict, args.skip_boot)
        # DEPRECATED: separate bootloader and uki fields (backward compatibility)
        elif bootloader_str := args_config.get('bootloader', None):
            bootloader = Bootloader.from_arg(bootloader_str, args.skip_boot)
            uki = args_config.get('uki', False)
            if uki and not bootloader.has_uki_support():
                uki = False
            arch_config.bootloader_config = BootloaderConfiguration(bootloader=bootloader, uki=uki, removable=True)

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

        if pacman_config := args_config.get('pacman_config', None):
            arch_config.pacman_config = PacmanConfiguration.parse_arg(pacman_config)
        elif parallel_downloads := args_config.get('parallel_downloads', 0):
            arch_config.pacman_config = PacmanConfiguration(parallel_downloads=int(parallel_downloads))

        swap_arg = args_config.get('swap')
        if swap_arg is not None:
            arch_config.swap = ZramConfiguration.parse_arg(swap_arg)

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

        # DEPRECATED: backwards compatibility
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
			self._config.version = get_version()
		except ValueError as err:
			warn(str(err))
			sys.exit(1)

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

	def _define_arguments(self) -> ArgumentParser:
		parser = ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
		parser.add_argument(
			'-v',
			'--version',
			action='version',
			default=False,
			version='%(prog)s ' + get_version(),
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
			'--skip-wifi-check',
			action='store_true',
			default=False,
			help='Skip wifi check when running archinstall',
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
						sys.exit(1)
					else:
						debug(f'Error decrypting credentials file: {err}')
						raise err from err
			else:
				header = tr('Enter credentials file decryption password')
				wrong_pwd_text = tr('Incorrect password')
				prompt = header

				while True:
					decryption_pwd: Password | None = tui.run(
						lambda p=prompt: get_password(  # type: ignore[misc]
							header=p,
							allow_skip=False,
							no_confirmation=True,
						)
					)

					if not decryption_pwd:
						return None

					try:
						creds_data = decrypt(creds_data, decryption_pwd.plaintext)
						break
					except ValueError as err:
						if 'Invalid password' in str(err):
							debug('Incorrect credentials file decryption password')
							prompt = f'{header}' + f'\n\n{wrong_pwd_text}'
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

		sys.exit(1)

	def _read_file(self, path: Path) -> str:
		if not path.exists():
			error(f'Could not find file {path}')
			sys.exit(1)

		return path.read_text()

	def _cleanup_config(self, config: Namespace | dict[str, Any]) -> dict[str, Any]:
		clean_args = {}
		for key, val in config.items():
			if isinstance(val, dict):
				val = self._cleanup_config(val)

			if val is not None:
				clean_args[key] = val

		return clean_args
