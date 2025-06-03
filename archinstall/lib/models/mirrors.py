import datetime
import http.client
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypedDict, override

from pydantic import BaseModel, field_validator, model_validator

from ..models.packages import Repository
from ..networking import DownloadTimer, ping
from ..output import debug


class MirrorStatusEntryV3(BaseModel):
	url: str
	protocol: str
	active: bool
	country: str
	country_code: str
	isos: bool
	ipv4: bool
	ipv6: bool
	details: str
	delay: int | None = None
	last_sync: datetime.datetime | None = None
	duration_avg: float | None = None
	duration_stddev: float | None = None
	completion_pct: float | None = None
	score: float | None = None
	_latency: float | None = None
	_speed: float | None = None
	_hostname: str | None = None
	_port: int | None = None
	_speedtest_retries: int | None = None

	@property
	def server_url(self) -> str:
		return f'{self.url}$repo/os/$arch'

	@property
	def speed(self) -> float:
		if self._speed is None:
			if not self._speedtest_retries:
				self._speedtest_retries = 3
			elif self._speedtest_retries < 1:
				self._speedtest_retries = 1

			retry = 0
			while retry < self._speedtest_retries and self._speed is None:
				debug(f'Checking download speed of {self._hostname}[{self.score}] by fetching: {self.url}core/os/x86_64/core.db')
				req = urllib.request.Request(url=f'{self.url}core/os/x86_64/core.db')

				try:
					with urllib.request.urlopen(req, None, 5) as handle, DownloadTimer(timeout=5) as timer:
						size = len(handle.read())

					assert timer.time is not None
					self._speed = size / timer.time
					debug(f'    speed: {self._speed} ({int(self._speed / 1024 / 1024 * 100) / 100}MiB/s)')
				# Do not retry error
				except urllib.error.URLError as error:
					debug(f'    speed: <undetermined> ({error}), skip')
					self._speed = 0
				# Do retry error
				except (http.client.IncompleteRead, ConnectionResetError) as error:
					debug(f'    speed: <undetermined> ({error}), retry')
				# Catch all
				except Exception as error:
					debug(f'    speed: <undetermined> ({error}), skip')
					self._speed = 0

				retry += 1

			if self._speed is None:
				self._speed = 0

		return self._speed

	@property
	def latency(self) -> float | None:
		"""
		Latency measures the miliseconds between one ICMP request & response.
		It only does so once because we check if self._latency is None, and a ICMP timeout result in -1
		We do this because some hosts blocks ICMP so we'll have to rely on .speed() instead which is slower.
		"""
		if self._latency is None:
			debug(f'Checking latency for {self.url}')
			assert self._hostname is not None
			self._latency = ping(self._hostname, timeout=2)
			debug(f'  latency: {self._latency}')

		return self._latency

	@classmethod
	@field_validator('score', mode='before')
	def validate_score(cls, value: float) -> int | None:
		if value is not None:
			value = round(value)
			debug(f'    score: {value}')

		return value

	@model_validator(mode='after')
	def debug_output(self) -> 'MirrorStatusEntryV3':
		self._hostname, *port = urllib.parse.urlparse(self.url).netloc.split(':', 1)
		self._port = int(port[0]) if port and len(port) >= 1 else None

		debug(f'Loaded mirror {self._hostname}' + (f' with current score of {self.score}' if self.score else ''))
		return self


class MirrorStatusListV3(BaseModel):
	cutoff: int
	last_check: datetime.datetime
	num_checks: int
	urls: list[MirrorStatusEntryV3]
	version: int

	@model_validator(mode='before')
	@classmethod
	def check_model(
		cls,
		data: dict[str, int | datetime.datetime | list[MirrorStatusEntryV3]],
	) -> dict[str, int | datetime.datetime | list[MirrorStatusEntryV3]]:
		if data.get('version') == 3:
			return data

		raise ValueError('MirrorStatusListV3 only accepts version 3 data from https://archlinux.org/mirrors/status/json/')


@dataclass
class MirrorRegion:
	name: str
	urls: list[str]

	def json(self) -> dict[str, list[str]]:
		return {self.name: self.urls}

	@override
	def __eq__(self, other: object) -> bool:
		if not isinstance(other, MirrorRegion):
			return NotImplemented
		return self.name == other.name


class SignCheck(Enum):
	Never = 'Never'
	Optional = 'Optional'
	Required = 'Required'


class SignOption(Enum):
	TrustedOnly = 'TrustedOnly'
	TrustAll = 'TrustAll'


class _CustomRepositorySerialization(TypedDict):
	name: str
	url: str
	sign_check: str
	sign_option: str


@dataclass
class CustomRepository:
	name: str
	url: str
	sign_check: SignCheck
	sign_option: SignOption

	def table_data(self) -> dict[str, str]:
		return {
			'Name': self.name,
			'Url': self.url,
			'Sign check': self.sign_check.value,
			'Sign options': self.sign_option.value,
		}

	def json(self) -> _CustomRepositorySerialization:
		return {
			'name': self.name,
			'url': self.url,
			'sign_check': self.sign_check.value,
			'sign_option': self.sign_option.value,
		}

	@classmethod
	def parse_args(cls, args: list[dict[str, str]]) -> list['CustomRepository']:
		configs = []
		for arg in args:
			configs.append(
				CustomRepository(
					arg['name'],
					arg['url'],
					SignCheck(arg['sign_check']),
					SignOption(arg['sign_option']),
				),
			)

		return configs


@dataclass
class CustomServer:
	url: str

	def table_data(self) -> dict[str, str]:
		return {'Url': self.url}

	def json(self) -> dict[str, str]:
		return {'url': self.url}

	@classmethod
	def parse_args(cls, args: list[dict[str, str]]) -> list['CustomServer']:
		configs = []
		for arg in args:
			configs.append(
				CustomServer(arg['url']),
			)

		return configs


class _MirrorConfigurationSerialization(TypedDict):
	mirror_regions: dict[str, list[str]]
	custom_servers: list[CustomServer]
	optional_repositories: list[str]
	custom_repositories: list[_CustomRepositorySerialization]


@dataclass
class MirrorConfiguration:
	mirror_regions: list[MirrorRegion] = field(default_factory=list)
	custom_servers: list[CustomServer] = field(default_factory=list)
	optional_repositories: list[Repository] = field(default_factory=list)
	custom_repositories: list[CustomRepository] = field(default_factory=list)

	@property
	def region_names(self) -> str:
		return '\n'.join([m.name for m in self.mirror_regions])

	@property
	def custom_server_urls(self) -> str:
		return '\n'.join([s.url for s in self.custom_servers])

	def json(self) -> _MirrorConfigurationSerialization:
		regions = {}
		for m in self.mirror_regions:
			regions.update(m.json())

		return {
			'mirror_regions': regions,
			'custom_servers': self.custom_servers,
			'optional_repositories': [r.value for r in self.optional_repositories],
			'custom_repositories': [c.json() for c in self.custom_repositories],
		}

	def custom_servers_config(self) -> str:
		config = ''

		if self.custom_servers:
			config += '## Custom Servers\n'
			for server in self.custom_servers:
				config += f'Server = {server.url}\n'

		return config.strip()

	def regions_config(self, speed_sort: bool = True) -> str:
		from ..mirrors import mirror_list_handler

		config = ''

		for mirror_region in self.mirror_regions:
			sorted_stati = mirror_list_handler.get_status_by_region(
				mirror_region.name,
				speed_sort=speed_sort,
			)

			config += f'\n\n## {mirror_region.name}\n'

			for status in sorted_stati:
				config += f'Server = {status.server_url}\n'

		return config

	def repositories_config(self) -> str:
		config = ''

		for repo in self.custom_repositories:
			config += f'\n\n[{repo.name}]\n'
			config += f'SigLevel = {repo.sign_check.value} {repo.sign_option.value}\n'
			config += f'Server = {repo.url}\n'

		return config

	@classmethod
	def parse_args(
		cls,
		args: dict[str, Any],
		backwards_compatible_repo: list[Repository] = [],
	) -> 'MirrorConfiguration':
		config = MirrorConfiguration()

		mirror_regions = args.get('mirror_regions', [])
		if mirror_regions:
			for region, urls in mirror_regions.items():
				config.mirror_regions.append(MirrorRegion(region, urls))

		if args.get('custom_servers'):
			config.custom_servers = CustomServer.parse_args(args['custom_servers'])

		# backwards compatibility with the new custom_repository
		if 'custom_mirrors' in args:
			config.custom_repositories = CustomRepository.parse_args(args['custom_mirrors'])
		if 'custom_repositories' in args:
			config.custom_repositories = CustomRepository.parse_args(args['custom_repositories'])

		if 'optional_repositories' in args:
			config.optional_repositories = [Repository(r) for r in args['optional_repositories']]

		if backwards_compatible_repo:
			for r in backwards_compatible_repo:
				if r not in config.optional_repositories:
					config.optional_repositories.append(r)

		return config
