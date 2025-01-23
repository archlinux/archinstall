from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from archinstall.default_profiles.profile import GreeterType, Profile

from ..hardware import GfxDriver


@dataclass
class ProfileConfiguration:
	profile: Profile | None = None
	gfx_driver: GfxDriver | None = None
	greeter: GreeterType | None = None

	def json(self) -> dict[str, Any]:
		from .profiles_handler import profile_handler
		return {
			'profile': profile_handler.to_json(self.profile),
			'gfx_driver': self.gfx_driver.value if self.gfx_driver else None,
			'greeter': self.greeter.value if self.greeter else None
		}

	@classmethod
	def parse_arg(cls, arg: dict[str, Any]) -> 'ProfileConfiguration':
		from .profiles_handler import profile_handler

		profile = profile_handler.parse_profile_config(arg['profile'])
		greeter = arg.get('greeter', None)
		gfx_driver = arg.get('gfx_driver', None)

		return ProfileConfiguration(
			profile,
			GfxDriver(gfx_driver) if gfx_driver else None,
			GreeterType(greeter) if greeter else None
		)
