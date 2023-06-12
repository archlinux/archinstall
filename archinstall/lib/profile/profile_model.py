from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Dict

from archinstall.default_profiles.profile import Profile, GreeterType

if TYPE_CHECKING:
	_: Any


@dataclass
class ProfileConfiguration:
	profile: Optional[Profile] = None
	gfx_driver: Optional[str] = None
	greeter: Optional[GreeterType] = None

	def json(self) -> Dict[str, Any]:
		from .profiles_handler import profile_handler
		return {
			'profile': profile_handler.to_json(self.profile),
			'gfx_driver': self.gfx_driver,
			'greeter': self.greeter.value if self.greeter else None
		}

	@classmethod
	def parse_arg(cls, arg: Dict[str, Any]) -> 'ProfileConfiguration':
		from .profiles_handler import profile_handler
		greeter = arg.get('greeter', None)

		return ProfileConfiguration(
			profile_handler.parse_profile_config(arg['profile']),
			arg.get('gfx_driver', None),
			GreeterType(greeter) if greeter else None
		)
