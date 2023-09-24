from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Dict

from ..hardware import GfxDriver
from archinstall.default_profiles.profile import Profile, GreeterType

if TYPE_CHECKING:
	_: Any


@dataclass
class ProfileConfiguration:
	profile: Optional[Profile] = None
	gfx_driver: Optional[GfxDriver] = None
	greeter: Optional[GreeterType] = None

	def json(self) -> Dict[str, Any]:
		from .profiles_handler import profile_handler
		return {
			'profile': profile_handler.to_json(self.profile),
			'gfx_driver': self.gfx_driver.value if self.gfx_driver else None,
			'greeter': self.greeter.value if self.greeter else None
		}

	@classmethod
	def parse_arg(cls, arg: Dict[str, Any]) -> 'ProfileConfiguration':
		from .profiles_handler import profile_handler

		profile = profile_handler.parse_profile_config(arg['profile'])
		greeter = arg.get('greeter', None)
		gfx_driver = arg.get('gfx_driver', None)

		return ProfileConfiguration(
			profile,
			GfxDriver(gfx_driver) if gfx_driver else None,
			GreeterType(greeter) if greeter else None
		)
