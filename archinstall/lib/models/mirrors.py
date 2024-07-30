import datetime
import pydantic
import typing

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
	last_sync :datetime.datetime|None=None
	duration_avg :float|None = None
	duration_stddev :float|None = None
	completion_pct :float|None = None
	score :float|None = None

class MirrorStatusListV3(pydantic.BaseModel):
	cutoff :int
	last_check :datetime.datetime
	num_checks :int
	urls :typing.List[MirrorStatusEntryV3]
	version :int

	@pydantic.model_validator(mode='before')
	@classmethod
	def check_model(cls, data: typing.Dict[str, int|datetime.datetime|typing.List[MirrorStatusEntryV3]]) -> typing.Dict[str, int|datetime.datetime|typing.List[MirrorStatusEntryV3]]:
		if data.get('version') == 3:
			return data

		raise ValueError(f"MirrorStatusListV3 only accepts version 3 data from https://archlinux.org/mirrors/status/json/")