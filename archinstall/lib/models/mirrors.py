import datetime
import pydantic
import http.client
import urllib.error
import urllib.parse
import urllib.request
from typing import (
	Dict,
	List
)

from ..networking import ping, DownloadTimer
from ..output import debug


class MirrorStatusEntryV3(pydantic.BaseModel):
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
	score: int | None = None
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

			_retry = 0
			while _retry < self._speedtest_retries and self._speed is None:
				debug(f"Checking download speed of {self._hostname}[{self.score}] by fetching: {self.url}core/os/x86_64/core.db")
				req = urllib.request.Request(url=f"{self.url}core/os/x86_64/core.db")

				try:
					with urllib.request.urlopen(req, None, 5) as handle, DownloadTimer(timeout=5) as timer:
						size = len(handle.read())

					self._speed = size / timer.time
					debug(f"    speed: {self._speed} ({int(self._speed / 1024 / 1024 * 100) / 100}MiB/s)")
				# Do not retry error
				except (urllib.error.URLError, ) as error:
					debug(f"    speed: <undetermined> ({error}), skip")
					self._speed = 0
				# Do retry error
				except (http.client.IncompleteRead, ConnectionResetError) as error:
					debug(f"    speed: <undetermined> ({error}), retry")
				# Catch all
				except Exception as error:
					debug(f"    speed: <undetermined> ({error}), skip")
					self._speed = 0

				_retry += 1

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

	@pydantic.field_validator('score', mode='before')
	def validate_score(cls, value) -> int | None:
		if value is not None:
			value = round(value)
			debug(f"    score: {value}")

		return value

	@pydantic.model_validator(mode='after')
	def debug_output(self, validation_info) -> 'MirrorStatusEntryV3':
		self._hostname, *_port = urllib.parse.urlparse(self.url).netloc.split(':', 1)
		self._port = int(_port[0]) if _port and len(_port) >= 1 else None

		debug(f"Loaded mirror {self._hostname}" + (f" with current score of {round(self.score)}" if self.score else ''))
		return self


class MirrorStatusListV3(pydantic.BaseModel):
	cutoff: int
	last_check: datetime.datetime
	num_checks: int
	urls: List[MirrorStatusEntryV3]
	version: int

	@pydantic.model_validator(mode='before')
	@classmethod
	def check_model(cls, data: Dict[str, int | datetime.datetime | List[MirrorStatusEntryV3]]) -> Dict[str, int | datetime.datetime | List[MirrorStatusEntryV3]]:
		if data.get('version') == 3:
			return data

		raise ValueError("MirrorStatusListV3 only accepts version 3 data from https://archlinux.org/mirrors/status/json/")
