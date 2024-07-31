import datetime
import pydantic
import urllib.parse
import urllib.request
from typing import (
	Dict,
	List
)

from ..networking import ping, DownloadTimer
from ..output import info, debug


class MirrorStatusEntryV3(pydantic.BaseModel):
	url :str
	protocol :str
	active :bool
	country :str
	country_code :str
	isos :bool
	ipv4 :bool
	ipv6 :bool
	details :str
	delay :int|None = None
	last_sync :datetime.datetime|None = None
	duration_avg :float|None = None
	duration_stddev :float|None = None
	completion_pct :float|None = None
	score :int|None = None
	_latency :float|None = None
	_speed :float|None = None
	_hostname :str|None = None

	@property
	def speed(self):
		if self._speed is None:
			info(f"Checking download speed of {self._hostname} by getting {self.url}core/os/x86_64/core.db")
			req = urllib.request.Request(url=f"{self.url}core/os/x86_64/core.db")
			with urllib.request.urlopen(req, None, 5) as handle, DownloadTimer(timeout=5) as timer:
				size = len(handle.read())

			self._speed = size / timer.time
			debug(f"    speed: {self._speed} ({int(self._speed / 1024 / 1024 * 100) / 100}MiB/s)")

		return self._speed

	@property
	def latency(self):
		"""
		Latency measures the miliseconds between one ICMP request & response.
		It only does so once because we check if self._latency is None, and a ICMP timeout result in -1
		We do this because some hosts blocks ICMP so we'll have to rely on .speed() instead which is slower.
		"""
		if self._latency is None:
			info(f"Checking latency for {self.url}")
			self._latency = ping(self._hostname, timeout=2)
			debug(f"  latency: {self._latency}")

		return self._latency

	@pydantic.field_validator('score', mode='before')
	def validate_score(cls, value):
		if value is not None:
			value = round(value)
			debug(f"    score: {value}")

		return value

	@pydantic.model_validator(mode='before')
	def debug_output(cls, data: str|bool|int|datetime.datetime|float|None) -> str|bool|int|datetime.datetime|float|None:
		parsed_uri = urllib.parse.urlparse(data['url'])
		hostname, *port = parsed_uri.netloc.split(':', 1)
		debug(f"Loaded mirror {hostname}" + (f"with current score of {round(data['score'])}" if data['score'] else ''))

class MirrorStatusListV3(pydantic.BaseModel):
	cutoff :int
	last_check :datetime.datetime
	num_checks :int
	urls :List[MirrorStatusEntryV3]
	version :int

	@pydantic.model_validator(mode='before')
	@classmethod
	def check_model(cls, data: Dict[str, int|datetime.datetime|List[MirrorStatusEntryV3]]) -> Dict[str, int|datetime.datetime|List[MirrorStatusEntryV3]]:
		if data.get('version') == 3:
			return data

		raise ValueError(f"MirrorStatusListV3 only accepts version 3 data from https://archlinux.org/mirrors/status/json/")