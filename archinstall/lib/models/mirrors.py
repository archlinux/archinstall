import datetime
import http.client
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, field_validator, model_validator

from ..networking import DownloadTimer, fetch_data_from_url, ping
from ..output import debug
from ..storage import storage


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
				debug(f"Checking download speed of {self._hostname}[{self.score}] by fetching: {self.url}core/os/x86_64/core.db")
				req = urllib.request.Request(url=f"{self.url}core/os/x86_64/core.db")

				try:
					with urllib.request.urlopen(req, None, 5) as handle, DownloadTimer(timeout=5) as timer:
						size = len(handle.read())

					assert timer.time is not None
					self._speed = size / timer.time
					debug(f"    speed: {self._speed} ({int(self._speed / 1024 / 1024 * 100) / 100}MiB/s)")
				# Do not retry error
				except urllib.error.URLError as error:
					debug(f"    speed: <undetermined> ({error}), skip")
					self._speed = 0
				# Do retry error
				except (http.client.IncompleteRead, ConnectionResetError) as error:
					debug(f"    speed: <undetermined> ({error}), retry")
				# Catch all
				except Exception as error:
					debug(f"    speed: <undetermined> ({error}), skip")
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
			debug(f"Checking latency for {self.url}")
			self._latency = ping(self._hostname, timeout=2)
			debug(f"  latency: {self._latency}")

		return self._latency

	@classmethod
	@field_validator('score', mode='before')
	def validate_score(cls, value: float) -> int | None:
		if value is not None:
			value = round(value)
			debug(f"    score: {value}")

		return value

	@model_validator(mode='after')
	def debug_output(self, validation_info) -> 'MirrorStatusEntryV3':
		self._hostname, *port = urllib.parse.urlparse(self.url).netloc.split(':', 1)
		self._port = int(port[0]) if port and len(port) >= 1 else None

		debug(f"Loaded mirror {self._hostname}" + (f" with current score of {self.score}" if self.score else ''))
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
		data: dict[str, int | datetime.datetime | list[MirrorStatusEntryV3]]
	) -> dict[str, int | datetime.datetime | list[MirrorStatusEntryV3]]:
		if data.get('version') == 3:
			return data

		raise ValueError("MirrorStatusListV3 only accepts version 3 data from https://archlinux.org/mirrors/status/json/")


@dataclass
class MirrorRegion:
	name: str
	urls: list[str]

	def json(self) -> dict[str, list[str]]:
		return {self.name: self.urls}

	def __eq__(self, other: object) -> bool:
		if not isinstance(other, MirrorRegion):
			return NotImplemented
		return self.name == other.name


class MirrorListHandler:
	def __init__(
		self,
		local_mirrorlist: Path = Path('/etc/pacman.d/mirrorlist'),
	) -> None:
		self._local_mirrorlist = local_mirrorlist
		self._status_mappings: dict[str, list[MirrorStatusEntryV3]] | None = None

	def _mappings(self) -> dict[str, list[MirrorStatusEntryV3]]:
		if self._status_mappings is None:
			self.load_mirrors()

		assert self._status_mappings is not None
		return self._status_mappings

	def get_mirror_regions(self) -> list[MirrorRegion]:
		available_mirrors = []
		mappings = self._mappings()

		for region_name, status_entry in mappings.items():
			urls = [entry.server_url for entry in status_entry]
			region = MirrorRegion(region_name, urls)
			available_mirrors.append(region)

		return available_mirrors

	def load_mirrors(self) -> None:
		if storage['arguments']['offline']:
			self.load_local_mirrors()
		else:
			if not self.load_remote_mirrors():
				self.load_local_mirrors()

	def load_remote_mirrors(self) -> bool:
		url = "https://archlinux.org/mirrors/status/json/"
		attempts = 3

		for attempt_nr in range(attempts):
			try:
				mirrorlist = fetch_data_from_url(url)
				self._status_mappings = self._parse_remote_mirror_list(mirrorlist)
				return True
			except Exception as e:
				debug(f'Error while fetching mirror list: {e}')
				time.sleep(attempt_nr + 1)

		debug('Unable to fetch mirror list remotely, falling back to local mirror list')
		return False

	def load_local_mirrors(self) -> None:
		with self._local_mirrorlist.open('r') as fp:
			mirrorlist = fp.read()
			self._status_mappings = self._parse_locale_mirrors(mirrorlist)

	def get_status_by_region(self, region: str, speed_sort: bool) -> list[MirrorStatusEntryV3]:
		mappings = self._mappings()
		region_list = mappings[region]
		return sorted(region_list, key=lambda mirror: (mirror.score, mirror.speed))

	def _parse_remote_mirror_list(self, mirrorlist: str) -> dict[str, list[MirrorStatusEntryV3]] | None:
		mirror_status = MirrorStatusListV3.model_validate_json(mirrorlist)

		sorting_placeholder: dict[str, list[MirrorStatusEntryV3]] = {}

		for mirror in mirror_status.urls:
			# We filter out mirrors that have bad criteria values
			if any([
				mirror.active is False,  # Disabled by mirror-list admins
				mirror.last_sync is None,  # Has not synced recently
				# mirror.score (error rate) over time reported from backend:
				# https://github.com/archlinux/archweb/blob/31333d3516c91db9a2f2d12260bd61656c011fd1/mirrors/utils.py#L111C22-L111C66
				(mirror.score is None or mirror.score >= 100),
			]):
				continue

			if mirror.country == "":
				# TODO: This should be removed once RFC!29 is merged and completed
				# Until then, there are mirrors which lacks data in the backend
				# and there is no way of knowing where they're located.
				# So we have to assume world-wide
				mirror.country = "Worldwide"

			if mirror.url.startswith('http'):
				sorting_placeholder.setdefault(mirror.country, []).append(mirror)

		sorted_by_regions: dict[str, list[MirrorStatusEntryV3]] = dict({
			region: unsorted_mirrors
			for region, unsorted_mirrors in sorted(sorting_placeholder.items(), key=lambda item: item[0])
		})

		return sorted_by_regions

	def _parse_locale_mirrors(self, mirrorlist: str) -> dict[str, list[MirrorStatusEntryV3]] | None:
		lines = mirrorlist.splitlines()

		# remove empty lines
		# lines = [line for line in lines if line]

		mirror_list: dict[str, list[MirrorStatusEntryV3]] = {}

		current_region = ''

		for line in lines:
			line = line.strip()

			if line.startswith('## '):
				current_region = line.replace('## ', '').strip()
				mirror_list.setdefault(current_region, [])

			if line.startswith('Server = '):
				if not current_region:
					current_region = 'Local'
					mirror_list.setdefault(current_region, [])

				url = line.removeprefix('Server = ')

				mirror_entry = MirrorStatusEntryV3(
					url=url.removesuffix('$repo/os/$arch'),
					protocol=urllib.parse.urlparse(url).scheme,
					active=True,
					country=current_region or 'Worldwide',
					# The following values are normally populated by
					# archlinux.org mirror-list endpoint, and can't be known
					# from just the local mirror-list file.
					country_code='WW',
					isos=True,
					ipv4=True,
					ipv6=True,
					details='Locally defined mirror',
				)

				mirror_list[current_region].append(mirror_entry)

		return mirror_list


mirror_list_handler = MirrorListHandler()
