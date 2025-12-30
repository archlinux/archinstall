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
			'greeter': self.greeter.value if self.greeter else None,
		}

	@classmethod
	def parse_arg(cls, arg: _ProfileConfigurationSerialization) -> 'ProfileConfiguration':
		from ..profile.profiles_handler import profile_handler

		profile = profile_handler.parse_profile_config(arg['profile'])
		greeter = arg.get('greeter', None)
		gfx_driver = arg.get('gfx_driver', None)

		_gfx_driver: GfxDriver | None = None
		if gfx_driver:
			# Note: This is for backwards compatability with older configs.
			# We fall back to the open-source nouveau driver here because if
			# we end up installing the open kernel modules on a machine with pre-Turing
			# hardware, the user will end up with a broken install (unresponsive black screen).
			if gfx_driver == 'Nvidia (proprietary)':
				_gfx_driver = GfxDriver.NvidiaOpenSource
			else:
				try:
					_gfx_driver = GfxDriver(gfx_driver)
				except Exception:
					_gfx_driver = GfxDriver[gfx_driver]

		return ProfileConfiguration(
			profile,
			_gfx_driver,
			GreeterType(greeter) if greeter else None,
		)
