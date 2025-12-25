from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from archinstall.default_profiles.profile import GreeterType, Profile

from ..hardware import GfxDriver

if TYPE_CHECKING:
	from archinstall.lib.profile.profiles_handler import ProfileSerialization


class _ProfileConfigurationSerialization(TypedDict):
	profile: ProfileSerialization
	gfx_driver: str | None
	greeter: str | None


@dataclass
class ProfileConfiguration:
	profile: Profile | None = None
	gfx_driver: GfxDriver | None = None
	greeter: GreeterType | None = None

	def json(self) -> _ProfileConfigurationSerialization:
		from ..profile.profiles_handler import profile_handler

		return {
			'profile': profile_handler.to_json(self.profile),
			'gfx_driver': self.gfx_driver.name if self.gfx_driver else None,
			'greeter': self.greeter.name if self.greeter else None,
		}

	@staticmethod
	def _parse_gfx_driver(value: str) -> GfxDriver:
		"""Parse graphics driver with backwards compatibility for old configs."""
		# Mapping for deprecated driver values to new enum members
		deprecated_map = {
			'Nvidia (proprietary)': GfxDriver.Nvidia,
			'Nvidia (open kernel module for newer GPUs, Turing+)': GfxDriver.Nvidia,
		}

		# Try deprecated value mapping first
		if value in deprecated_map:
			return deprecated_map[value]

		# Try parsing as enum name (new format)
		try:
			return GfxDriver[value]
		except KeyError:
			# Fall back to enum value (old format)
			return GfxDriver(value)

	@staticmethod
	def _parse_greeter(value: str) -> GreeterType:
		"""Parse greeter with backwards compatibility for old configs."""
		# Try parsing as enum name (new format)
		try:
			return GreeterType[value]
		except KeyError:
			# Fall back to enum value (old format)
			return GreeterType(value)

	@classmethod
	def parse_arg(cls, arg: _ProfileConfigurationSerialization) -> 'ProfileConfiguration':
		from ..profile.profiles_handler import profile_handler

		profile = profile_handler.parse_profile_config(arg['profile'])
		greeter = arg.get('greeter', None)
		gfx_driver = arg.get('gfx_driver', None)

		return ProfileConfiguration(
			profile,
			cls._parse_gfx_driver(gfx_driver) if gfx_driver else None,
			cls._parse_greeter(greeter) if greeter else None,
		)
